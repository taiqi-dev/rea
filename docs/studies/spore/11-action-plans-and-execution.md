# 11 从技能请求到具体肢体、动画和效果

[目录](README.md) · [资格](10-capability-aggregation-and-ability-eligibility.md) · [灵魂](13-soul-body-contracts.md)。技能是谁提供的、AI 为什么选择它、由哪只手执行、什么时候扣资源与产生效果，需要分层定义。

## Spore 接口证据

社区原始声明分别表示 PlayAbility、PlayAnimation、使用/冷却状态以及技能的伤害、范围、动画和效果资源；未提供完整执行函数体。[cCreatureBase.h](https://github.com/Spore-Community/Spore-ModAPI/blob/master/Spore%20ModAPI/Spore/Simulator/cCreatureBase.h)、[cCreatureAbility.h](https://github.com/Spore-Community/Spore-ModAPI/blob/master/Spore%20ModAPI/Spore/Simulator/cCreatureAbility.h)

AnimatedCreature 的消息含 blockIndex，而 TLSA choice 与动画加载/启动分开；choice 不能直接解释成某只手。[AnimatedCreature.h](https://github.com/Spore-Community/Spore-ModAPI/blob/master/Spore%20ModAPI/Spore/Anim/AnimatedCreature.h)。社区格式文档说明事件可关联通道与时点，并可能对被选身体分别产生效果；它没有证明这些效果都会分别扣血。[动画导出文档](https://github.com/Spore-Community/SporeModder-FX/wiki/Exporting-creature-animations-from-Blender)

因此以下是**独立执行规格**，没有宣称恢复了 Spore 的逐技能链。

后续[25：距离、可达与命中](25-body-reach-attack-ranges-and-hit-resolution.md)已局部解码本机四类攻击的等级与模板配置，补上“选定肢体→前摇→有效点重查→命中/落空”的独立算例。它同时区分动作参与部件与效果部件；范围数值已取得，原作体型修正与实际伤害提交链仍未恢复。

## 行动是带具体参与者的实例

```text
ActionRequest { requesterId, abilityId, targetId, optionalPreferredParts[] }
ActionInstance {
    actionId, plan, phase, startTick, committedEffectOrdinals[]
    bodyId, soulId, controlGeneration, dependencyPartVersions
    resourceReservationIds[], channelClaimIds[], result
}
Phase = Planned | Reserved | Windup | EffectCommitted | Recovery
      | Completed | Cancelled | Failed
```

参与者用稳定 PartInstanceId 记录；只有播放适配器将其转换成当前身体图节点或骨骼索引。不能把旧动画 blockIndex 当作跨断肢/重建仍有效的部件身份。

## 怎样选择哪只手

```text
MakeOwnPlan(request, body, soul, world):
    descriptor = ResolveOwnedAbility(request.abilityId, body, soul)
    modes = descriptor.executionModes
    for mode in modes:
        candidates = FindFunctionalProviders(body, mode.partRequirements)
        candidates = filter(candidates, reachable/available/channel-compatible)
        if mode.requiresNoBodyPart: candidates = {NoPhysicalProvider}
        groups = FormOwnRequiredProviderGroups(candidates, mode.roleCount)
        for group in groups:
            if !ValidateJointStructuralRequirements(group): reject with reason
            plan = {descriptor, mode, group, request.targetId}
            EvaluateOwnTimingReachAndCosts(plan)
            emit plan
    return Plans or Unavailable(reasonCounts)
```

两只手协同动作可以有施法手、稳定手两种角色，不能用“所有 Grasper 都参加”替代角色分配。每个方案要验证共享祖先、通道占用和目标可达。四手组合太多时可以明确裁剪，但必须报告候选覆盖范围。

构造例：左前手已占用，右前手可达目标，后手不具备符印能力。灵魂提出印记火球，方案选择右前手；伤害与资源仍按该技能定义，不因为模型有四手就乘四。换到纯意识灵魂弹，可以没有物理执行手，但仍有发射位置/方向与效果时序。

## 通道与资源预约

后续[28](28-parallel-actions-channel-ownership-and-conflicts.md)已读取指定原作攻击播放组的移动许可及动画通道元数据，并将本节独立预约细化到具体部件/自由度、共享祖先、抢占与恢复。动画叠层和游戏技能并发分别判定；原作两技能同时提交效果仍未知。

动作占用和资源不足是不同失败。爪击可占右手运动；双手仪式占两手；吟唱占口部；奔跑占 locomotion 通道。允许走路施法或移动打断施法应由执行模式声明。

```text
ReserveOwnAction(plan, coordinator):
    revalidate control and plan dependencies
    within one authoritative simulation transaction:
        verify all channel claims are compatible
        verify available body and soul resources minus existing reservations
        reserve every cost and channel, or reserve none
    return Reserved(actionId) or Rejected(reason)
```

这要求原子化的逻辑边界，不要求提前引入多线程锁框架。在单一模拟线程上也应保证一项事务不会预约半套资源后失败。冷却归属可为灵魂技能、肉体技能或部件；它们的键不能仅是当前角色 ID，详见 13。

## 效果时点与重复事件

我们建议将玩法效果提交到行动调度器；动画提供表达和可配置时点输入。命中需要目标/碰撞/范围验证，不能由“动画看起来击中”直接确认。多人网络权威另需项目契约，目前未假定有网络系统。

```text
OnOwnEffectWindow(actionId, ordinal, event):
    action = FindAction(actionId)
    if absent: return Rejected(UnknownAction)
    if action not in a permitted phase: return Rejected(ActionNotActive)
    if ordinal already committed: return DuplicateIgnored(with event key)
    ValidateControlAndExactDependentParts(action)
    hits = ResolveOwnTargetsAndHitTests(action, event)
    within one authoritative transaction:
        consume reserved costs required at this commit point
        apply own effects to validated hits
        mark ordinal committed; update cooldown ledger
    return EffectCommitResult(hits, misses, costs)
```

这是本地权威模拟中的去重契约，不保证跨服务器/崩溃恢复的 exactly-once。实际并发、提交失败和保存恢复必须另验证。即使没有命中，也可能消耗资源、进入冷却；由技能 policy 规定，不能只在有伤害时结算消耗。

两手各触发同一逻辑窗口时，仅有一个 effect ordinal；如果技能本来是两次独立打击，则定义 ordinal 0/1。粒子、音效、镜头效果可以有多个，但不能据此自动复制玩法效果。

## 中断、断肢和换灵魂

前摇中依赖手断裂：报告 DependencyLost，按技能中断政策取消；未支付的预约资源释放。效果已经提交：不回滚此前伤害；后续恢复或持续效果按定义处理。已经发射的投射物保留自己的生命周期和施法身份，不能因当前动画停止而复制或归给新控制者。

换灵魂/身体递增 controlGeneration，使旧控制请求失效；旧动作与已生成效果的归属不自动改变。体型变化但依赖部件仍有效时，可以按动作契约继续或暂停重绑；不能无条件令每个颜色编辑都取消攻击。

动作终止后，释放尚未消费的预约、通道与实例资源，记录终止原因。资源释放失败要保留拥有者和可重试状态，不能将引用丢掉后报告成功。

## 边界与后续

已定位 Spore 的接口分离；实际选手、最终伤害公式、逐事件扣血和冷却写入链未恢复。本文的动作状态、事务和 partId 是自研建议。没有执行原游戏或用户项目动作测试。风险集中于重复提交、预约泄漏、过期部件映射和换控制后旧事件生效。
