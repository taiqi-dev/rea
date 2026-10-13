# 47 受击反应、行为中断与AI恢复

[目录](README.md) · [攻击距离与命中](25-body-reach-attack-ranges-and-hit-resolution.md) · [感知与动机](27-perception-target-memory-and-motive-selection.md) · [并行动作](28-parallel-actions-channel-ownership-and-conflicts.md) · [事件与提交](40-action-events-emitters-hit-windows-and-stale-callbacks.md) · [共享关节](42-branched-limbs-shared-joints-and-goal-conflicts.md)。

限定陆地Creature。受击画面、生命值变化、技能取消、已发射效果、导航停顿和逃跑决策是不同环节。原作公开声明与旧配置能提供入口，**尚未恢复它们之间的执行顺序或中断政策**。第1节是原作证据；之后是自研规格、伪代码与构造演算，灵魂/断肢/换体不归成Spore机制。

## 1 原作：找到字段，不等于找到中断链

本轮重新核对固定SDK提交的相关字段及包装调用。来源字节摘要、实际行范围、有界阴性和既有JSON复用见[证据清单](evidence/public-reaction-secondary-contracts.json)。

| 已核对入口 | 能确认什么 | 未确认什么 |
| --- | --- | --- |
| cCombatant.TakeDamage | 伤害接口与HP/最后攻击者字段；CreatureBase继承该接口 | 身体受击动画、Vector3用途及技能取消顺序 |
| cCreatureAbility | mReactionAnimation/DeathAnimation/LiveAnimation/Duration声明 | 属于哪种技能/阶段、作用于哪方及默认值消费 |
| cCreatureAnimal | mNoDamageTimer、mLastAvatarDamageTimer、NPC/Avatar TickAI入口 | 计时器的条件、单位、受击保护或恢复规则 |
| cCreatureBase | 当前攻击、能力使用/冷却位、UpdateMotiveState | 哪类伤害清哪个状态，受击是否必然停步 |
| cCreatureAnimal.cpp | PlayAbility、NPC/Avatar TickAI等auto_METHOD包装 | 包装没有呈现原作函数内部逻辑 |
| cCombatSimulator | 投射物容器与更新标记的共享声明 | 陆地投射物如何响应取消、来源死亡或目标失效 |

cCombatant自身注释还将大部分战斗逻辑放在外部模拟器。该类也用于其他对象，本轮只把Creature继承关系当接口关联，不把载具武器或冒险字段套成陆地受击算法。[战斗对象](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCombatant.h)、[能力声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCreatureAbility.h)、[动物包装调用](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/SourceCode/Simulator/cCreatureAnimal.cpp)

社区登记表给出四个reaction属性精确ID：075e00b7、07a7ffd5、07a7ffd9、075e0100。它们在25已选50份攻击等级/模板记录的完整property_ids列表中均未直接写入；本轮复核每份列表长度等于已记录property_count。**这只是所选资源的直接序列化阴性**，不能推出没有受击动画、没有代码默认值、其他配置或继承。[旧攻击配置](evidence/local-selected-attack-properties.json)、[固定登记表](https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/reg_property.txt)

27中CreatureGameTuning键00b1b104:ad56080c:7c340397确有FleeDistance=25、FleeTime=5、FleeRememberTime=90及HitPointsTurnAndFightPercentage=.75，单位、比较方向和条件仍未知。低健康动机枚举及UpdateMotiveState存在，不等于“每次受击都逃跑”。NPCReactionTime是通用候选，StarvationPain是饥饿候选，均不当成武器受击时序；登记表检索误命中的SkinPaint也已排除。[既有感知参数](evidence/local-selected-perception-properties.json)

40所选喷吐动画有不同索引的同名hit通知，这不能定义受击次数或取消事件。当前没有匹配“实际受伤→能力状态清理→导航→AI”的本机消费者。本轮不再读取新包载荷，不根据pain、tail等名字挑动画或恢复算法。

## 2 自研：反应控制与行动账本分别拥有状态

以下字段、阈值和规则全部是独立设计。伤害确认先经25的权威命中政策；本模块消费已确认事件，不能用播放受击动画再次扣血。

~~~text
AcceptedDamage {
    worldHitId, targetEntityLifetime, damageCommitId
    healthDamage, poiseImpact, damageKind
    knownSourceObservation, contactFeature, simulationTick
}
ReactionState {
    bodyId, bodyGeneration, controlGeneration, reactionEpoch
    status: Ready | Staggered | Dying
    episodeStartTick, blockedUntilTick, immuneUntilTick
    visualProfile, ownedPoseOutputs, reasons[]
}
ActionInstance {
    actionId, bindingEpoch, bodyRevision, controlGeneration
    phase, requiredCohort, reservedCost, committedEffectSlots
    interruptPolicy, dependencyOutputs
}
WorldEffect {
    effectId, immutableBirthAction, birthEmitter, birthControl
    independentLifetimePolicy, ownHitLedger
}
RecoverySnapshot {
    health, functionalParts, resourceAvailability, cooldowns
    currentContactsAndSupport, observationsWithAge
    cancelledActions, activeWorldEffects, navigationEpoch
}
~~~

伤害账本去重键是worldHitId加目标生命期；表现通知可另带damageCommitId。actor生命周期变了则拒绝旧事件，非法数值在修改HP/账本之前拒绝。不能把同名音效、同名hit或部件数量当伤害次数。

反应政策分三层：

- VisualFlinch：声音、表情或未被占用的表现通道。它不自动取消技能或改变导航，也不会把纯表现骨偏移当权威武器轨迹。
- Stagger：取得明确姿态/控制权限，阻止新的技能提交；依政策取消不兼容cohort，清理其尚未提交窗口和预约。
- PhysicalDisplacement：由身体运动/物理拥有者更新根位移，并使旧导航/接触预测失效。它不能只移动画面而继续用旧判定体。本例不施加冲量。

反应想驱动同一肩、嘴或脚时仍经过28/42的自由度与共同求解协调。硬直不能静默把旧技能的手目标留着；轻反应也不能隐式覆盖已选发射点。触发部位失效时可降级为声音/通用表现并保留诊断，不假装找到了正确骨骼。

## 3 自研具体流程：取消未来，保留已提交结果

~~~text
AcceptOwnDamage(event):
    verify target lifetime, finite nonnegative amounts and authority receipt
    if damage ledger already contains this worldHitId: return DuplicateIgnored
    in target actor's serialized transaction:
        record damage commit; apply HP and poise change
        update limited source observation, without inventing line of sight
        classify VisualFlinch / Stagger / terminal transition
        if Stagger:
            advance reaction/binding epoch and close action commit gates
            for each incompatible action cohort:
                mark Cancelled; invalidate future marker/window tickets
                release unspent reservation; release owned pose/output claims
                preserve committed slots, cooldown and world-effect birth records
            cancel owned navigation request; advance navigationEpoch
    publish damage result and reaction request
~~~

本方案对中断型技能选择永久取消，恢复后重规划；不把剩余关键帧在解除硬直时补播并补发效果。若自有产品需要可暂停技能，应另外声明暂停时间线、资源保持和重新绑定政策，不能把“取消”和“暂停”混用。

已经提交的近战扣血、生成的投射物和消费的资源不回滚。尚未提交的槽取消并释放预约；生成失败/补偿仍依40的事务政策处理。WorldEffect有自己的生存政策：本例的投射物已交世界管理器，即使攻击动作取消或控制者换代仍继续；持续光束若要求当前施法者维持，则必须另有连接租约，不能用投射物规则替代。

同模拟tick选择“确认伤害/反应裁决在尚未提交的新效果marker之前”，同类按稳定事件序号排序。若marker已经在更早tick提交，后来的受击不能追溯删除效果。这个顺序是自研政策，不是静态SDK恢复结果。

~~~text
RecoverOwnActor(nowTick):
    if nowTick < blockedUntilTick: return StillBlocked
    acquire current body/pose/functional/resource snapshot
    end episode; begin declared short reaction-immunity interval
    discard old navigation result and cancelled action checkpoints
    refresh perception; keep aged memory as estimates
    evaluate legal skill-target-executor plans from current state
    choose current utility winner and create a new action/navigation lease
    do not resurrect the previous action ID or its uncommitted markers
~~~

免疫间隔只限制反复硬直，不否定已确认伤害；其上限、叠加与抗性需要自己的肉体/技能契约。死亡走独立生命周期，不能在普通恢复计时到期时复活；终态推进导航代次，技能提交与导航接收还要显式拒绝TerminalActor，即使请求恰好带着新代次。断肢、换体或换魂使绑定/控制代次失效；已提交效果保留出生归属，不转给新灵魂。

## 4 自研完整数值例子

模拟tick=0.05 s，所有规则都是构造参数。HP=100、韧性poise=25、能量=20；双段技能A预留8能量，槽0花5、槽1花3。首个效果提交时开始100tick冷却。硬直持续12tick，同一episode最多延长到起点+24tick；解除后4tick反应免疫。

| 时刻 | 输入与演算 | 状态 |
| --- | --- | --- |
| tick0 | A预留8 | 能量20、预约8、可用12 |
| tick6=.30 s | 槽0提交，消耗5，生成投射物E11 | 能量15、预约3、可用12；冷却到tick106 |
| tick8=.40 s | H901：HP伤害12、poise影响8 | HP88、poise17；VisualFlinch，A继续 |
| tick9=.45 s | H902：伤害18、poise影响20 | HP70、poise0；Stagger到tick21 |
| 取消事务 | A binding epoch推进；未来槽1取消，释放预约3 | 能量仍15、预约0、可用15；E11继续，冷却仍106 |
| tick12=.60 s | 旧槽1marker到达 | StaleAction，无第二个效果、无额外消费 |
| tick21=1.05 s | 硬直到期 | 新快照/新规划，不恢复A；免疫到tick25 |

H901被重复投递时，HP/poise不再变化；重复取消也不重复释放。取消A不能清掉其他动作拥有的预约。若在槽0提交前就硬直，则释放全部8，能量仍20；这与当前已经花掉5的情况分别核对。

此时最后视觉观察在.10 s，初始置信度.8；借用27的自研教学衰减c=.8·exp(−.95/4)≈.630878，误差半径r=.1+2·.95=2.0 m。记忆仍可用于大致撤退方向，但没有新的精确敌方坐标或视线。A技能还在冷却，且本例新精确射击要求可靠当前视线，故该候选不合法。

自有策略给“往已知掩体撤退”收益5、移动成本1，净值4；防御姿态净值2，选择撤退并发新导航租约。它是当前状态下的策略选择，不是“受击事件直接命令逃跑”，也不把原作.75字段套成阈值。E11稍后是否命中仍由其自己的轨迹/目标规则决定。

## 5 验证、未知与风险

[独立检查脚本](checks/verify_reaction_secondary_examples.py)共30项通过：本篇14项、48有14项，另2项核对旧JSON。覆盖轻反应保持行动、伤害去重、提交/预约分离、旧marker拒绝、同tick顺序、重复取消、目标生命期、非法输入、硬直上限/免疫、恢复重规划、冷却、感知记忆与导航代次。[验证记录](evidence/reaction-secondary-verification.json)

原作未知：受击是否中断哪种能力、反应资源如何选择、伤害/硬直/击退顺序、位集合如何清理、冷却/资源是否退回、已生成效果政策、目标遗忘与恐惧触发。最小后续自有场景是同一技能分别在预备、首次发射后、第二marker同tick受击，核对效果账本、预约、姿态权限与新导航任务；原作验证则需已匹配函数入口或另行授权运行范围。

未做：游戏启动/附加、私人数据、新包载荷、原生函数恢复、完整资产导出、生产实现、联网或崩溃恢复验证。风险：现有接口包含共享阶段字段；30项是actor内串行算例和状态检查，不保证跨线程/联网的恰好一次效果，也不证明原作采用本方案。
