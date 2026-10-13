# 03 核心数据结构、动作绑定与逐帧流程

[目录](README.md) · [证据边界](00-evidence-and-scope.md)。目标是解释：生物有四只手、八只脚时，程序怎样知道“手是什么”“哪个通道作用于哪一只”，以及姿态如何进入绘制。

## 输入、状态、输出

身体节点到绘制骨骼的映射、参考矩阵、顶点权重及接缝关系进一步见[29网格与蒙皮](29-creature-mesh-joins-and-automatic-skinning.md)。不能仅凭身体图就认为所有部件一对一映射到渲染骨骼。

输入是玩家的身体配方、动作请求、角色位置和时间。持久状态是配方；派生状态是身体图与绑定缓存；帧状态是动作目标和求解姿态。输出是用于蒙皮的骨骼变换与可诊断结果，不能由帧姿态反写玩家的造型。

公开设计及社区字段入口见 00；**以下所有类型、缓存键和流程顺序是独立规格，未恢复本机内存布局。**

```text
CreatureRecipe {
    parts: Map<PartId, PartRecipe>          // 稳定身份，删除再添加产生新 ID
    spine: OrderedSpineControls
    skin: { baseScript, coatScript, detailScript, colors, seed }
    revision: { topology, shape, rest, capability, paint }
}
PartRecipe {
    id, assetReference, parentId, mirrorId?
    mount: { hostId, longitudinalU, sideAngle, normalOffset }
    jointControls[], userRotation, morphWeights[]
}
BodyGraph {
    nodes: Map<NodeId, BodyNode>
    renderBoneOfNode, capabilityIndex
    recipeRevision
}
BodyNode {
    id, sourcePartId, parentId?, children[]
    tags: Set<Capability>                  // Mouth, Grasper, Foot 等
    symmetryPeer?, restLocalTransform, referenceFrame
    chainLength, shapeBounds, attachmentFrame
}
PoseGoals { positionGoals[], orientationGoals[], deformGoals[] }
PositionGoal { nodeId, frame, target, weight, priority, sourceChannel }
BindingCacheKey { animationId, topologyRev, capabilityRev, restRev }
PoseResult { transforms[], residuals[], diagnostics[], recipeRevision }
```

图允许一条骨链末端分叉。一个标签不能代替连接关系：同为 Foot 的节点可能有不同祖先、腿长、对称伙伴。把所有节点塞入固定“左大腿/右大腿”数组会丢掉自定义身体的结构。

自研建图必须校验 parent 存在、没有环、镜像关系互相一致，且源部件到渲染骨骼的映射完整。无效配方返回带 PartId 的错误，不静默遗漏一条肢体。

## 从动作通道到具体肢体

本机能否一次选前手、全部手或一个变体，必须追具体资源和调用者。我们的规格将“资格”“选择模式”“混合”“命中事件”分开。这里不假设攻击永远选最高、最近或最前的手。

```text
BindChannel(channel, body, policy):
    candidates = body.nodes where channel.requiredTags ⊆ node.tags
    candidates = filter(candidates, channel.spatialPredicate)
    candidates = filter(candidates, channel.ancestorPredicate)
    candidates = stableSort(candidates, by NodeId)

    if candidates.empty:
        if channel.required: return Error(MissingRequiredBody, channel.id)
        return Ok(EmptyBinding(reason = OptionalChannelUnavailable))

    if channel.selectionMode in {One, Variant} and policy is absent:
        return Error(UnresolvedSelectionPolicy, channel.id)
    switch channel.selectionMode:
        All:      selected = candidates
        Pair:     selected = requireValidSymmetryPairs(candidates)
        One:      selected = [policy.chooseOne(candidates)]
        Variant:  selected = policy.chooseVariantGroup(candidates,
                                                     channel.variantGroupId)
    if selected contains an invalid node:
        return Error(UnresolvedSelectionPolicy, channel.id)

    return Ok(map(selected, n => {channel.id, n.id, n.referenceFrame}))
```

`chooseOne` 是显式配置的自研接口，不是推测原游戏选择算法。对于同一个变体组，我们规定相关通道共享同一选择记录，以免手通道选前手、肩通道却选后肩；实际资源如何分组仍待核对。

例：四手标签如下。独立设定“打击”仅接受 Strike 标签，并选择身体前侧一对。

| 节点 | 标签 | 身体位置 | 自研选择结果 |
| --- | --- | --- | --- |
| LF/RF | Grasper、Strike | 前侧 | 两者参加 |
| LB | Grasper | 后侧 | 缺少 Strike，不参加 |
| RB | Grasper、Strike | 后侧 | 有资格，但不满足前侧条件 |

选中的手得到动作目标；未选中的手保留其他姿态层。伤害逻辑消费技能事件，不按“有几只手在动”自动乘以几份伤害，详见 02。

## 从参考姿态生成目标

为便于实现，自研规格把位移曲线看成相对于某个参考框架的偏移，而不是每种生物录制一次完整动作。

```text
offset = animationCurve.sample(time)       // 自研单位：无量纲
scale  = diagonal(bodyWidth, bodyHeight, bodyLength)
localGoal = restPoint + referenceRotation * scale * offset
worldGoal = bodyWorldTransform * localGoal
```

这是我们选择的包围尺度模型；其他模式可以按肢体长度或接地高度定义，但必须有枚举和单位，不能将三种模式混乘。例如身高 1 m / 2 m，竖直偏移参数 0.1，在该模式产生 0.1 m / 0.2 m。它不证明原游戏此通道使用身高。

姿态混合也要按自由度定义：同一个手的位置与旋转可能由不同通道负责。独立规则是最高优先级层内正权重归一化；位置线性加权，旋转用四元数球面插值，不能逐分量平均四元数。低优先级是否还能影响剩余自由度必须写入契约。

## 每一帧的管线

```text
TickCreature(dt, request, runtime):
    require finite(dt) and dt >= 0
    validateRelevantBodyRevisions(runtime.body, runtime.recipe)
    bindings = GetOrBind(request.animation, runtime.body, selectionPolicy)
    if bindings.failed: return Failure(bindings.error)

    root = UpdateOwnCharacterMotion(dt, request.navigation)
    actionGoals = SampleBoundChannels(bindings, request.actionTime, root)
    footGoals = UpdateOwnGait(dt, root, runtime.gait, runtime.terrain)
    goals = BlendByDegreeOfFreedom(actionGoals, footGoals, blendPolicy)
    pose = SolveOwnPose(runtime.body, goals, runtime.previousPose)
    secondary = UpdateOwnPassiveParts(dt, pose, runtime.passiveState)
    result = BuildRenderTransforms(pose, secondary)
    events = CollectActionEventsExactlyOnce(request.actionInstance)
    return {result, events, diagnostics = pose.diagnostics}
```

这里的 passive parts 是自研附属运动层。我们规定它不反推攻击和脚部目标，以便故障有清楚边界；不是本机已验证调用顺序。

上面为单请求的教学管线。多个同时活跃的行动需先处理占用和移动许可，再采样各自时间线，将全部目标交给共享身体求解，详见[28多动作并行](28-parallel-actions-channel-ownership-and-conflicts.md)。28也补充零权重、兼容契约与淡入的独立政策；不把“同一数字混合组”自动当成跨动作共享许可。

## 所有权与失效

配方拥有编辑值；BodyGraph 拥有参考结构；绑定缓存拥有查询结果；动作实例拥有事件游标；步态拥有落脚锚点；求解器拥有迭代状态；材质系统拥有贴图和烘焙任务。拓扑改动让绑定与步态失效；颜色改动不重绑手脚。06 给出更细的版本依赖。

失败要包含对象与原因：缺脚可切到明确配置的无脚模式，不能悄悄假造两条腿；动作缺必需部位要报告不可播放；求解不可达可输出最佳近似，但必须同时输出残差。

未做：没有恢复本机类型布局、缓存策略或 Tick 调用图。风险：这份完整管线比已知原游戏证据更具体，必须作为我们自研规格阅读。
