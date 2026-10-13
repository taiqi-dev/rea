# 58 肢体子树复制、宿主替换与重挂

[目录](README.md) · [部件定义](37-part-definition-edit-controls-rigs-and-capabilities.md) · [镜像](41-mirroring-mount-frames-and-action-coordinates.md) · [重建/Undo](44-editor-rebuild-undo-and-animation-cache-consistency.md) · [连接](49-editor-surface-snapping-attachment-and-connection-validation.md) · [功能预览](57-editor-animation-preview-and-functional-validation.md)。仍限定陆地Creature及其编辑器。

问题是整条上臂→前臂→手→指怎样复制，替换上臂时哪些后代保留，重挂时参考姿态如何迁移。**本轮确认原作有父子/对称/造型保存表示，但尚未确认原作整链复制、保留后代替换的具体支持与算法。** 后面的事务和身份规则是为自己的游戏独立设计。

## 原作证据与明确缺口

固定SDK中，EditorRigblock保存parent/children、CSnap连接骨与框架、替换位移/吸附类型列表、对称伙伴与造型参数。Editor.h的RemovePart带PLACEHOLDER；`mbModelCopyConsequence`是另一个名字，不能视为CloneSubtree实现。所查范围未找到明确CopyPart/CloneSubtree/Reparent方法体，不据此证明原作没有相应交互。

保存块其实定义在`cEditorResource.h`，不是同名独立头文件。本轮先查后者404，随后核对实际定义第31–56行：parentIndex、symmetricIndex、位置/朝向、造型权重/通道和涂装。它支持配方保存层级，**数组索引不是永久部件UUID，也不说明复制会怎样生成身份。** [固定声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/cEditorResource.h)

官方手册第10页描述拖动/删除部件、造型把手和整体缩放，第11页描述Undo/Redo；本轮文字检索没有明确解释任意整链复制、宿主替换保留指头及其身份/价格。[官方手册](https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/17390/manuals/manual.pdf?t=1642702281) 图片未核验，没有操作游戏快捷键，因此不把“可能Alt拖拽”写成已验证原作方法。

原作候选字段`modelTypesToSnapReplace`、`modelReplaceSnapDelta`与父连接规则可继续追消费者；没有读取实际替换模板函数体。37的选定手Rigblock包含内部骨架，不意味着每根指骨都是独立编辑部件。来源与阴性范围见[公共契约](evidence/public-editor-preview-subtree-contracts.json)。57的10份预览配置不证明复制/替换行为，两个模块的证据问题分别保留。

## 自研表示：定义、部件实例与内部骨不同

以下全部自研。一个手的定义可以带内部指骨；它们随手的内部rig保留。若产品允许独立拼装手指，则手指有自己的PartInstanceId与连接定义。本例为了演算，将手掌和两指作为可安装节点；不能把计价推广到所有内部骨。

```text
PartInstance {
    partId, definitionId/version, parentPartId, connectorId,
    referenceMount, referenceJoints, semanticShapeParameters,
    mirrorPartnerId?, sourceRecipeNamespace
}
SubtreeEditPlan {
    expectedGeneration, beforeDigest, selectedRootId,
    operation: Copy|ReplaceDefinition|Reparent,
    oldToNewPartId, connectorMigration, parameterMigration,
    posePolicy, costDelta, changedDependencies, diagnostics
}
CommittedEdit { operationId, beforeRecipe, afterRecipe, generation, ledgerEntry }
```

复制定义可以共享只读资产，运行部件实例必须有新ID。复制不复制伤口、冷却、正在握持物、灵魂记忆、动作预约或旧AI计划；这是编辑配方操作，不克隆当前活体状态。

替换时本规格为被换件创建新PartInstanceId，保留未被替换的后代ID。宿主槽位/位置可以保留，但不能由此说上臂还是同一个实例。重挂沿用既有整条子树ID，只改外部父/连接和选择的参考框架；三种操作不同。

## 自研算法一：整条子树复制

```text
PlanOwnCopySubtree(recipe, root, newHost):
    validate root/host and current generation
    members = traverse all descendants by parent graph, detecting invalid graph
    allocate a complete bijection oldPartId→freshPartId for every member
    require no new ID collision in recipe namespace
    for each source part in parent-before-child order:
        copy definition references, reference data and own shape parameters
        remap internal parent and all internal stable references through the bijection
        attach only copied root to explicit new host/connector
        map internal symmetry pairs when both participants copied
        otherwise clear external mirror relation with explicit diagnostic or use declared pair-copy mode
    validate new host slots, graph/shape/rig and budget for complete candidate
    return immutable plan; do not publish/charge until commit
```

不只复制根模型然后继续引用原手指对象；否则两条手臂编辑会串联。深复制实例参数，定义与授权只读几何可以共享；皮肤/绑定派生缓存须以新身体输入键重建或验证复用，不能共享运行矩阵数组。

镜像复制是另一个明确模式，沿41应用自己的镜像profile一次。普通复制只是保留局部参考配置，不自动取负角度；复制到另一侧前先确认参考框架/连接适配。外部伙伴关系不能让新臂“抢走”原臂的镜像对象。

## 自研算法二：换上臂，保留下方结构

```text
PlanOwnReplaceHost(recipe, oldHostId, newDefinition):
    snapshot direct children and their stable IDs/connector semantics
    instantiate new host with fresh partId, preserving selected mount slot
    for each child:
        lookup explicit oldConnector→newConnector compatibility
        reject missing mapping, incompatible axis or insufficient slot capacity
    migrate only shape parameters with same semantic name, units and allowed range
    adapt reference joint semantics/pole using explicit definition profile
    attach retained children to new host, recompute reference globals from new frames
    retain deeper descendants' identities and local data
    validate complete candidate, role/profile changes and all derived dependencies
    return plan or explicit failure; do not silently drop children/parameters
```

形变把手索引不是语义身份：旧handle0可能是宽度，新handle0可能是curl。没有映射时返回ShapeParameterUnsupported；超新范围返回ShapeParameterOutOfRange，不擅自限幅使玩家造型改变。愿意恢复新件默认造型时，应该是明确的另一个编辑选项及报告。

新宿主的distal socket可以叫不同名称，只要自有目录声明兼容关系和局部坐标转换。两个孩子迁到同一单容量插槽需拒绝；允许多容量时按声明实际容量统计。检查脚本为单容量slot的简化演算，实际把F的parent_socket写为新宿主允许的elbowMount，并拒绝未知slot；尚未实现完整3D接头框架与蒙皮迁移。

保留后代不要求末端世界位置完全不动。默认政策是保留后代局部参考与骨长，新宿主缩短后末端随新接头移动；若用户选择保持末端世界参考，则需新的IK/造型适配并验收，可失败。不能让“保留手指”暗中改变指骨长度来追旧位置。

## 自研算法三：整条子树重挂

```text
PlanOwnReparent(recipe, subtreeRoot, newHost, newConnector, posePolicy):
    members = complete subtree
    reject newHost inside members, self-parent or invalid host slot
    oldGlobalRoot = EvaluateReferenceGlobal(subtreeRoot)
    newHostFrame = EvaluateCurrentReferenceConnector(newHost, newConnector)
    if posePolicy == KeepWorldReference:
        newRootLocal = inverse(newHostFrame) * oldGlobalRoot
    if posePolicy == KeepLocalReference:
        newRootLocal = mapped prior local reference under declared connector axes
    validate resulting orientation, mount limits, pose and overlap constraints
    preserve all subtree IDs and internal parents; change only external root edge
    invalidate host-dependent bindings/contacts/plans and return candidate
```

KeepWorldReference可能令部件悬离新接头，需同时满足连接契约才能采用；不能只计算矩阵就宣布连接成功。KeepLocalReference随新宿主框架改变整体位置/朝向，更适合“这条腿搬到新的髋”。用户模式必须写进历史，Undo才知道该恢复哪个参考，不能从当前摆腿姿态推回去。

## 自研算法四：事务、成本、Undo与旧计划

三种计划都先生成完整不可变candidate，连接/参数/预算全部验证后一次提交。镜像伙伴替换以整组事务进行，任何一侧失败都不改变另一侧。49的最新非法preview不保留旧候选提交资格；44的迟到bake和旧generation报告同样拒绝。

成本从自己部件目录计算：复制对新的可计价实例收费，替换为newCost−oldCost，重挂结构不增件时费用0。镜像/套餐价格是另外的产品规则，不能把这里的逐实例收费断言为Spore原作规则。预算/账本提交沿34；Undo用差额做新反向条目，外部奖励保留。

```text
CommitOwnSubtreePlan(plan):
    require current generation/digest equal plan base
    recheck complete candidate graph/slots/parameters/cost and derived manifest
    atomically commit recipe+ledger+history and increment generation
    invalidate old action reservations and AI plans that depend on changed body
    compile/rebind current skeleton, capabilities, local profiles and contacts
    publish one current complete body; invalidate old previews/results
```

后代ID仍在也不代表旧行动可以继续：H的肩骨/可达范围/代价改变，必须重评。新计划可再次选H；旧U执行者被删除时返回ExecutorMissing，不自动换成copy_U或U2继续旧伤害窗口。已经提交的伤害/世界投射物按11/54生命周期处理，不随编辑撤回。

## 自研完整数值例：两节臂→手掌→两指

平面XY演算，单位米，正角逆时针。原肩mount=(0.4,0)，五个可计价节点：U上臂长0.5/局部30°/成本20；F前臂0.4/−20°/15；H手掌0.1/0°/10；D1手指0.08/+15°/5；D2手指0.06/−10°/5。父链Body→U→F→H，D1/D2挂H。总成本55。全部成本和参数是自己的教学目录。

1. 初始D1尖端：累积角为30°→10°→10°→25°，得到(1.397921,0.370634)。这是参考姿态几何，不是运行中的攻击轨迹。
2. 整链复制到另一个合法mount=(0.4,1.0)。U/F/H/D1/D2全部分配copy_前缀的新ID，内部父映射完整，局部配置不变；D1尖端变(1.397921,1.370634)。原臂不变。复制不是镜像，未改角度符号。
3. 钱包原余额120，复制成本55，提交generation2后余额65。若一次还要复制两条则需110而不足，必须明确拒绝，不能按“只复制根上臂20”漏计后代。
4. 将原U替换为U2，新上臂长0.35、参考30°、成本25，旧thickness=0.1按同单位/范围兼容参数迁移；F通过映射迁到U2的elbowMount。U获得新ID，F/H/D1/D2保留；复制臂仍然使用原定义，不连带改变。
5. U缩短0.15 m后，原臂所有后代全局位置变化`−0.15(cos30°,sin30°)=(-0.129904,-0.075)`，D1尖端成为(1.268017,0.295634)，指长仍0.08。差价5，余额60，generation3。缺socket/形状映射则整次替换失败。
6. 将U2整树重挂到新的合法mount=(0.7,0.2)，选择KeepLocalReference且宿主轴兼容。所有内部角和骨长不变，尖端成为(1.568017,0.495634)，IDs不变，根外部父/连接更新；费用0，generation4。挂到自己的D1则ReparentIntoDescendant，整树不变。
7. generation4之前的AI计划即使执行者仍H，也返回StaleAIPlan；重新评估后generation4/H可绑定。若旧计划指定U，不改选U2或copy_U。57的功能预览也必须针对4的当前bundle运行。
8. 期间外部奖励7使余额67。Undo重挂只还原父/参考内容，余额67；Undo替换退款5至72；Undo复制退款55至127。每次都是新generation，不恢复旧任务/冷却。检查脚本贯通三步编辑和三次Undo，核对新generation7、参考mount恢复、身份与余额；它仍是单进程顺序模型，没有实现可持久化的生产事务。

本例手掌/指头是独立可计价节点。如果自己的手指仅是H内的骨骼，其身份/形变随H内部rig保存，不额外收5+5，也不作为子树PartId单独复制；算法先确认实际层级再操作。

## 验证、未做与风险

[同一检查脚本](checks/verify_editor_preview_subtree_examples.py)中58有16项：全量后代/新ID、碰撞映射拒绝、替换保留ID与实际socket改变、几何位移/指长、socket/形状缺失、未知slot拒绝不扣费、重挂拒环、完整复制/替换/重挂/三次Undo、价差/外部奖励、预算与stale事务、无效父图/负成本、外部镜像关系清除诊断、保留手也失效旧AI计划和删除执行者不改选。57另有14项，总30项。实际结果见[专属验证](evidence/editor-preview-subtree-verification.json)。

原作已回答：保存与活动部件的层级/参考/对称表示。未回答：真实整链复制支持、快捷键、身份生成、保留后代替换/重挂、socket迁移、退款和失效协议。最有价值下一步是具体鼠标/替换属性消费者，而不是把parentIndex或CopyConsequence扩写成复制算法。

未做：运行游戏、私人配方、原生方法体、新复制模板解码、生产编辑器实现、三维完整socket/skin验证、数据库/并发事务。风险：新资产拓扑或插槽可能无法保留全部后代，参考姿态迁移可能不可行；数学与顺序状态检查不证明任何资产都能无损替换。
