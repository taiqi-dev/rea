# 21 群体配合：共享意图、个体决策与执行肢体

[目录](README.md) · [人口组织](20-species-herds-and-population.md) · [个体肉体评估](16-soul-ai-body-assessment.md) · [社交](22-social-sessions-and-relationships.md)。只研究陆地生物阶段，完整协调算法是面向用户游戏的独立规格。

关于亲眼观察、族群报告、旧情报与失去感官的区别，见[27感知与目标记忆](27-perception-target-memory-and-motive-selection.md)。共享任务不能将隐藏敌人的实时位置或过期消息变成每个成员的精确锁定。

## 1 原作AI入口与证据边界

社区 `cCreatureAnimal` 暴露 `NPCTickAI` 与 `AvatarTickAI`，个体关联族群并有人格入口；`cCreatureBase` 有目标和对目标意图、能力播放等接口。`cBehaviorTreeData` 声明decider节点、子节点、根节点，以及行为激活/更新/解除回调。[个体声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCreatureAnimal.h)、[生物基类](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCreatureBase.h)、[决策结构](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/AI/cBehaviorTreeData.h)。

因此能定位“个体接收意图后选择并执行行为”的调查入口。尚没有调用关系证明原作采用下文的效用评分、角色竞价、队长统一指挥或伤害预约；decider回调返回float也不足以判定具体选择算法。公开头文件中的函数地址未对齐本机EXE，不能直接当本机入口。

“大家一起冲过来”可由共同感知、受击报警、共享目标或单独追同一个目标产生。要区分它们，应在视野外、报警范围外和隔障场景比较响应，不能仅凭围攻画面推断存在复杂战术。

## 2 自研分工：群体提出任务，灵魂选择完整行动

**用户反馈：愿意考虑这一方向，作为候选设计保留。** 范围是群体提出共享任务，每个灵魂根据当前肉体选择技能、目标与执行部件，结构变化后重评估。该反馈不是已决定实施全部协调系统；当前没有用户游戏仓库，未修改生产代码，也不因此将本页算法解释成Spore实现。

```text
SharedIntent { revision, mode, leaderId, perceivedTarget,
               observedPosition, observationTime, expiresAt, priority }
RoleRequest  { roleId, intentRevision, roleType, targetId,
               capacity, allowedRisk, expiresAt }
RoleClaim    { actorId, roleId, bodyVersion, controllerEpoch, expiresAt }
ActionPlan   { skillId, targetId, limbBindings, movementPlan,
               resourceReservations, expectedEffects, validityStamp }
```

群体可以提出“跟随”“防卫”“攻击”“社交”“逃离”等共享意图。每个成员仍用16的能力快照与灵魂偏好评估：能否追上、是否有合法技能/肢体、是否愿意冒险。角色是任务约束，最后仍生成 **技能+目标+具体部件** 的行动方案。

灵魂自带的法术也参与竞选；法术是否需要嘴、手或意识通道由技能契约决定。身体带有手并不等于所有灵魂必须打拳；小队也不能绕过个体的冷却、资源和动作占用。

### 候选落地范围

第一步可限定为一个共享目标、近战/远程/保护三个角色、有限容量与有期限的预约，接入既有个体行动方案。先验证：同伴不会抢同一个容量1角色；断肢后旧执行部件与角色释放；灵魂可以根据风险拒绝任务。跨族群传播、复杂队形和更大规模调度可待基础行为稳定后评估。

角色评价还需真实的行动距离、可达性与命中规则，否则“近战角色最优”可能建立在无法击中的方案上。建议结合[24下一轮机制研究](24-next-land-mechanism-investigations.md)优先补这条基础契约。

## 3 自研感知与报警

```text
OnWitnessedIncident(observer, incident):
    if incident expired or observer cannot perceive incident: return reason
    update observer's local belief with confidence and observation time
    if observer policy allows warning:
        publish Alarm(incidentId, lastSeenPosition, sourceId, ttl, signalRange)

OnAlarmReceived(member, alarm):
    reject duplicates, expired messages, unauthenticated hostile spoofing
    if not in signal range / no configured communication route: reject
    record reported position with lower confidence than own observation
    reevaluate safety, faction relation and shared intent
```

报警给出的是最后所知位置。目标离开视野后不提供实时坐标；消息也不会无条件传给地图上全部同物种成员。物种、阵营和临时小队的接收规则分开配置。这部分为自研；Spore实际信号范围、传播与认知模型未知。

## 4 自研角色分配与肢体绑定

初版可采用少量容量明确的角色：近战接敌、远程支援、保护受伤成员、社交响应、跟随。采用稳定实体ID排序，避免名单变化使每个人突然交换队形位置。

```text
CoordinatorTick(group, now):
    expire old intent, stale observations and role claims
    requests = build role slots from current observed situation
    for member in group.liveMembers:
        snapshot = AssessBodyAndSoul(member)  // module 16
        for request in requests:
            proposals += BuildLegalPlans(member, snapshot, request)
            score = ExpectedBenefit - travelCost - executionRisk
                    + personalityWeightedCooperation
    assignments = choose feasible proposals with role capacities
                  and retain valid old claims unless improvement > hysteresis
    atomically reserve selected role slots for this intent revision
    send task offers to members

MemberAcceptOffer(member, offer):
    revalidate bodyVersion, controllerEpoch, target, cooldown and resources
    if member intent changed or offer no longer acceptable: reject(reason)
    bind actual skill to eligible limbs / soul channels
    reserve execution resources using module 11
    execute movement and action; report start, success, failure or cancellation
```

群体预约解决多人抢同一角色；个体预约解决一只手同时被两个动作占用。两者不是同一个锁。若并发竞选，角色提交需归于唯一协调者或事务所有者，否则两个成员可能同时占到容量1的槽。

可保存预计伤害减少过度集火，但只能作为不确定的预测；不能提前把目标算作死亡。预测要有期限，实际命中/失败后纠正。路径不可达、友军挡位、技能失效均返回原因，让协调者重新分配。

## 5 自研完整协作例子：断手后重分配

前置状态：甲是近战灵魂，四足双手；乙是谨慎施法灵魂，有意识护盾但移动较慢；丙六足长颈，嘴提供远程喷吐。三者在同一临时小队，感知到一个正在接近甲的敌人。这三个成员数量仅是示例。

| 时刻 | 共享任务 | 个体完整方案 | 原因 |
| --- | --- | --- | --- |
| t0 | 近战容量1、支援容量1、保护容量1 | 甲右手打击；丙嘴喷吐；乙灵魂护盾 | 能力、距离与人格分别匹配 |
| t1 | 敌人仍可见，甲右手被打断 | 甲取消右手预约和旧伤害预测 | bodyVersion变化，旧绑定无效 |
| t2 | 仍需接敌，保护优先级提高 | 甲左手可达且支撑足够则改左手；乙加强护盾 | 不是让断掉的手继续动画 |
| t3 | 甲再失去支撑足，稳定近战不可用 | 甲退出近战角色并撤退；丙继续远程；乙掩护 | 协作依据真实剩余能力重算 |
| t4 | 甲换成无手带角身体 | 更新肉体快照；若冲撞满足距离/支撑条件再申请近战 | SoulId不变，bodyVersion/controllerEpoch更新 |

若甲人格强烈求生，可能在t2就拒绝接敌；这是灵魂策略影响配合。队长可以调整任务优先级，是否允许强制服从应是显式产品规则。

```text
OnBodyOrControllerChanged(actor):
    invalidate old action validity stamps
    cancel obsolete limb/resource reservations and pending effect predictions
    release incompatible role claim
    rebuild capability snapshot
    notify coordinator with capability change and reason
    replan using updated body + same or newly assigned soul
```

取消仍要遵守11的已提交效果规则：已经命中的伤害不会因断手回滚，尚未提交的旧回调因版本失效而拒绝。更换队长或小队解散同样需要终止旧意图，不能留下无限期角色占用。

## 6 更新频率与验证

自研可让局部感知与个体决策在事件发生、任务失效、定期检查时运行，移动/动画按帧执行；远处族群降低行为更新频率。具体频率必须依据你的预算测量，不能将这个常见优化当成Spore已验证策略。

核对示例应包括：两个成员抢容量1角色、报警过期、不可达目标、退出小队、断肢与换体期间的旧动作回调。相关不变量检查见[算例检查](checks/verify_group_social_examples.py)。原作未知：报警传播、选目标规则、跟随队形、同伴技能分配和社交跟随者行为；未做游戏运行、原生反编译或性能测试，原因与20相同。风险：这里的协作伪代码是独立设计规格，尚未接入用户游戏。
