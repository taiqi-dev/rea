# 16 灵魂 AI：肉体评估、联合决策与变化后的重新评估

[目录](README.md) · [能力聚合](10-capability-aggregation-and-ability-eligibility.md) · [执行器](11-action-plans-and-execution.md) · [所有权](13-soul-body-contracts.md) · [完整战斗](17-soul-ai-complete-battle.md)。

本页是为用户的肢体拼装游戏独立设计的规格，**不是 Spore 的灵魂 AI**。延续 14 的效用决策原则，把原来的固定特征演算细化为肉体评估与动作生命周期。灵魂既拥有独立技能，也决定使用肉体的方式。续篇时间锚点：2026-10-12 00:04:31 PDT，America/Los_Angeles。

## 先回答“这副肉体能做什么”

不能只统计手数、腿数或总攻击力。一个完整评估包含三个不同结果：

| 层 | 输入 | 输出 | 更新条件 |
| --- | --- | --- | --- |
| 身体潜力 | 身体图、功能连接、伤势、部件配置 | 能力提供者、执行模式、感官、移动方式 | 拼装、断肢、功能损坏、变形 |
| 此刻可执行性 | 潜力、目标、姿态、通道、资源、冷却 | 当前可行方案与拒绝原因 | 决策时读取，并在预约/提交时复核 |
| 战术价值 | 可行方案、认知、任务、灵魂偏好 | 预测结果、分数、首选与备选 | 新威胁、目标变化、动作完成或失败 |

健康的施法手被占用：仍有施法潜力，但当前不能用。右手断裂：右手提供的潜力消失。灵魂还记得火球：知识仍在，但需要手势的执行模式可能不可用。三者不能共用一个 `hasSkill` 布尔值。

## 肉体图与能力快照

```text
BodyCapabilitySnapshot {
    bodyId, anatomyRevision
    providersByCapability: Capability -> Provider[]
    bodyAbilityDescriptors[]
    senses[], locomotionModes[]
    structuralGroups[], diagnostics[]
}
Provider {
    partId, attachmentGeneration, functionalPathVersions[]
    capability, localLevel, damageModel, costModel
    restFrame, chainLengths[], jointLimits[], contactShape
    aimAnchor, permittedChannels[], structuralDependencies[]
}
LiveFeasibilitySnapshot {
    controlLease, poseRevision, channelRevision
    resourceLedgerVersions[], cooldownState, perceptionRevision
    currentPose, currentProvidersAvailability
}
```

提供者必须能够沿有效路径连接到受控躯干；不能把地上刚断掉的手还算进身体能力。功能路径是否依赖血液、神经、骨骼或魔法连接由游戏规则定义，不强加真实人体结构。父链失效可影响整条分支；装饰破损通常不影响无关攻击。

全身“爪击等级 3”可以是最高部件等级摘要，**不能因此让等级 1 的另一只爪也打出等级 3 伤害**。提供者本地等级决定本例的实际动作参数；全身加成若存在，需由独立规则明确加在哪一层。

```text
AssessBody(body):
    graph = ValidateAndBuildFunctionalGraph(body.parts)
    if graph.invalid: return Error(InvalidBodyGraph, graph.diagnostics)
    reachable = graph.FunctionallyConnectedToControlledRoot()
    out = NewCapabilitySnapshot(body.id, body.anatomyRevision)
    for part in reachable:
        if !part.functionEnabled: out.record(DisabledPart, part.id); continue
        for capability in part.config.capabilities:
            provider = DeriveProvider(part, graph, body.deformation)
            if provider.invalid: out.record(provider.error); continue
            out.providersByCapability[capability].add(provider)
    out.bodyAbilityDescriptors = ResolveBodyAbilitiesWithProvenance(out)
    out.senses = ResolveSupportedSenses(out)
    out.locomotionModes = ResolveSupportedLocomotion(out)
    return Assessed(out)
```

移动能力也是有条件的：两条腿存在，不代表能在当前地形站稳。输出应包含支撑、速度、转向、可达地形和必要肢体。四足少一足后可能降速、改步态，或完全失去某种移动模式；由产品规则决定，见 04–05。不能统一写成“少一腿速度减 25%”。

## 从技能扩展成“技能＋目标＋执行方式＋肢体”

```text
BoundPlan {
    abilityId, originOwner, modeId
    targetEntityId, targetGeneration, targetObservationId
    providersByRole, intendedStandPosition, approachPath
    durationEstimate, hitEstimate, effectsEstimate, costsByOwner
    channelClaims, exactDependencies, controlLease
    versionsUsed, forecastAssumptions
}
```

灵魂技能与肉体技能先合并成“拥有的技能”；每项技能再展开自己的执行模式。例如火球需要一只符印手，意识脉冲无物理手，咬击需要嘴，双手仪式要求两只不同的手分工。一个部件不能未经规则允许同时填两个互斥角色。

目标来自实时观测或有时间/置信度的记忆。敌人的真实生命、隐藏技能、完整地图、尚未暴露的行动不能自动进入输入。本例用可见战斗信息；实际项目可用区间生命、已观察伤害和带置信度的威胁估计。去最后位置搜索与直接向不可见目标精确施法是不同方案。

```text
EnumeratePlans(soul, bodyCaps, live, knowledge, budget):
    owned = UnionOwnedAbilities(bodyCaps, soul.learnedAbilities)
    targets = BuildPermittedKnownTargets(knowledge)
    for ability in owned:
        for mode in ability.executionModes:
            groups = MatchDistinctProvidersToRoles(mode, bodyCaps)
            # 无物理部件模式也要检查感知、控制、能量、施法锚点。
            for target in CompatibleTargets(ability, targets):
                for group in groups:
                    if budget.exhausted: return Partial(plans, prunedCounts)
                    candidate = Bind(ability, mode, target, group)
                    gate = CheckHardConditions(candidate, live)
                    if gate.failed: record Rejected(candidate, gate.reason); continue
                    poses = FindPermittedCastOrAttackPositions(candidate, live)
                    for pose in poses:
                        plan = DeriveTimingReachCosts(candidate, pose, live)
                        if plan.invalid: record Rejected(plan.reason); continue
                        emit plan
    return Complete(plans, rejectionCounts)
```

硬条件包括控制租约、目标类型、必要部件、当前功能、冷却、资源、通道、姿态和合法射线。它们不进入可被高分抵消的加权和。资源归属明确为灵魂、身体或部件；“总蓝量”不能替代多个池。

对近战，先用 `distance(anchor, targetContact) <= sum(chainLengths) + contactRadius` 做便宜的距离筛选，再检查关节限制、朝向、遮挡和实际目标姿态。距离通过只证明可能可达，不证明 IK 一定能解。身体变宽、骨链变长或初始姿态变化，会更新锚点与可达区域；眼前有目标不能保证每只手都能打到。

距离不足可生成“先接近再使用”的方案，包含路径时间、转向、沿路风险和到达后的再确认。当前不能施放与永远不能施放必须区分。占用预计释放后再施法同理；等待时间不能从评分中省略。

## 本轮战斗使用的可计算评分

下面是独立的“保护同伴”配置，与 14 的四列教学配置并存；并非修正原作参数。所有方案使用共同的伤害、资源和时间尺度。

```text
U = D/30 + 1.5*B/30 - R/30 - 0.25*K - 0.10*T/2
K = soulEnergyCost/20 + bodyStaminaCost/10

D = pHit * min(damageIfHit, estimatedTargetHealth)
B = 预期避免的下一次同伴生命损失（最多覆盖一个已识别威胁事件）
R = 动作完成前预计自身受到的生命损失
T = 接近/等待 + 前摇 + 恢复，单位秒
```

D 是对敌人的有效伤害；B 是对同伴的保护；R 是自身风险，分别属于不同对象。30 点是统一价值尺度。1.5 表示该灵魂更看重同伴；成本同时考虑灵魂与肉体池，身体技能不会因为不花灵魂能量而被当成免费。

对于预计造成 30 点伤害、同伴仅剩 24 HP 的威胁：

- 若一次攻击足以击杀施法者且效果早于威胁截止，`B = pHit * 24`。
- 若打断能取消该威胁且提前生效，`B = pInterrupt * 24`。
- 若护盾可在截止前生效并吸收 20，`B = pShieldReady * min(20,24)`。
- 若伤害不足以击杀、无法打断或效果太晚，则该方案 `B=0`。

这里保护评分只覆盖**下一次**威胁，不代表敌人永远不再攻击。打断后冷却结束、敌人重新蓄力，会形成新的威胁并触发再评价。最远预测窗口为 4 秒；更远/未知事件不当成精确信息。本例的命中估计、暴露概率和敌人技能参数是教学输入，不是从真实对局学得。确定性推演不能证明其概率校准正确。

如果敌人生命只知在 [20,35]，30 伤害不能被当成必杀：用明确的估计分布计算击杀概率或采用保守边界，并保存假设。无可靠概率时返回带置信度的先验；NaN、负成本、非法概率应诊断为模型输入错误。

```text
ScorePlan(plan, context, policy):
    prediction = PredictUsingKnownInformation(plan, context)
    require probability in [0,1], durations >= 0, costs >= 0
    D = prediction.pHit * min(prediction.damage, prediction.knownHealth)
    threat = context.nextRelevantAllyThreat(within = 4 seconds)
    B = AvoidedLossForOneThreat(plan, prediction, threat)
    R = PredictSelfLossUntilCompletion(plan, context)
    K = plan.soulCost/20 + plan.bodyCost/10
    U = D/30 + policy.allyWeight*B/30 - R/30 - .25*K - .05*plan.T
    return Scored(plan, U, {D,B,R,K,T}, prediction.assumptions)
```

无攻击价值时，等待、寻路、拉开距离、寻找目标或防守也可成为候选。它们需要真实结果模型，不能把“AI 无技能”静默变成非法普攻。致命环境、强制失控等紧急规则先决定允许的行动集合。

## 联合选择以后还要由执行器确认

```text
DecisionTick(controller):
    caps = GetOrRebuildBodyAssessment(controller.body)
    live = CaptureCurrentFeasibility(controller)
    knowledge = CaptureSoulKnowledgeWithObservationProvenance(controller)
    plans = EnumeratePlans(controller.soul, caps, live, knowledge, budget)
    scored = plans.map(ScorePlan).exclude(ModelInvalid)
    selected = SelectWithCommitmentAndStableTieBreak(scored)
    if none: return NoAction(reasons, permittedFallbacks)
    result = executor.TryReserve(selected)  # 原子确认、预约，可能拒绝。
    if result.rejected:
        RecordDecisionInvalidated(result.reason, selected)
        ScheduleFreshDecision()  # 不沿用旧快照无限重试。
    return result
```

“最高分”只属于被检查的候选集；有预算裁剪必须记录。执行器拒绝最高分后不能直接递归到无限重试。可以在同一受限循环中检查少量备选，再等待状态事件。相同分数用稳定 ID 和模式顺序打破平局，方便复现。

旧动作不合法时立即退出，不受 14 的分数惯性保护。合法旧动作的剩余收益仍高时避免反复取消。对当前前摇已经耗掉的时间，不应再完整计算为未来成本；不同方案必须从同一个“现在”比较。

## 断肢：沿依赖失效，而不是重置整只角色

```text
OnAnatomyChanged(body, changedParts):
    affected = ExpandStructuralAndFunctionalDependents(changedParts)
    UpdateFunctionStateAndAttachmentGenerations(body, affected)
    body.anatomyRevision += 1
    InvalidateAssessmentEntries(affected)
    for action in ActiveActionsOwnedBy(body.id):
        check = RevalidateExactDependencies(action)
        if check.failed: CancelAction(action, DependencyLost, check.details)
        else: RefreshPoseBindingIfNeeded(action)
    RefreshAffectedSensesLocomotionAndCapabilities(body)
    ScheduleFreshDecision()
```

右手断裂应同时失去右手本身及依赖它的武器/符印；不自动删除左手和嘴。若姿态变化影响整个躯干，要复核其它动作的可达性，不能只看提供者仍在就完全忽略变化。最小实现可以重建整份能力快照，后来有性能证据再做增量；**不能无条件取消所有动作**。

正在右手蓄力的火球需要取消。剩余左手即使仍能施法，也需要新动作、新绑定、重新验证成本与前摇；本例不允许原动作自动换手并继承 90% 蓄力。允许蓄力接续时需显式设计兼容规则。

## 换肉体：控制代次切换，不是清空灵魂

```text
TransferControl(soul, oldBody, newBody, expectedLease):
    ValidateTransferPermissionAndNewBodyAvailability()
    within one authoritative control transition:
        compare expectedLease with activeLease
        revoke old lease
        cancel its body-bound actions using their original tokens/owners
        preserve already committed world effects by their own lifecycle
        create new lease(soul.id, newBody.id, generation + 1)
    caps = AssessBody(newBody)
    PreserveSoulKnowledgeEnergyAndOwnerCooldownLedgers()
    # 身体伤口、体力、弹药、部件冷却继续归各自肉体。
    RebuildCurrentSensingFromNewBody()
    MarkOldObservationsAsMemoryWithTimeAndConfidence()
    ScheduleFreshDecision(caps)
```

转移涉及清理失败时保留旧动作和令牌的诊断/所有权，不丢弃记录后留下永久占用。本页提供逻辑事务契约；实装应使控制切换对其它系统不可见半完成状态，并定义失败结果。新身体不可用时，转移验证失败，仍保持旧控制；不先撤销再寻找肉体。

火球已经发射后可由世界管理继续飞行，这是可选的明确效果规则；尚未发射的旧回调不能往新身体上发射。目标、部件和控制都有身份/代次校验，避免对象编号复用。旧动作清理必须拿原令牌，不能操作“当前身体”的新通道。

经验可以归灵魂保留，但不同射程、姿态和感官的身体要选对应情境模型。技能知识保留不等于当前能力保留；敌人记忆保留不等于持续实时看见。

关于最后位置、消息时效、感官断裂、灵魂感知技能和行为切换，见[27的专项规格与完整遭遇](27-perception-target-memory-and-motive-selection.md)。它将本页的perceptionRevision进一步拆为带来源/时间的观察、认知估计和当前感知资格；原作证据独立列出。

## 诊断、验证和局限

每次决策至少输出：控制租约、肉体版本、已知目标及观测来源、候选数量/裁剪、逐项拒绝原因、具体提供者、预测 D/B/R/K/T、分数、预约结果和后续中断原因。

例：`Firebolt → C / RF` 被取消的原因应为 `ProviderDetached(RF)`；`Firebolt → C / LF` 当前拒绝原因可同时含 `ChannelBusy` 与当前姿态不可行，不能统一记录为“火球失败”。

完整数值与动作状态见 17。未做：真实 AI 对局、概率拟合、IK/寻路测量、用户项目实现和并发/保存恢复测试。风险：单威胁浅预测会忽略续招、群攻和联合战术；本例要说明决策结构，不保证最佳打法。实际检查范围由 17 列出。
