# 40 选定肢体之后：动作事件、发射点、伤害窗口与旧回调

[目录](README.md) · [39执行者与绑定](39-same-role-effectors-variant-binding-and-default-mixing.md) · [11行动生命周期](11-action-plans-and-execution.md) · [25命中](25-body-reach-attack-ranges-and-hit-resolution.md) · [28通道协调](28-parallel-actions-channel-ownership-and-conflicts.md)。范围为陆地Creature及其编辑器；本轮起点2026-10-12 22:21:18 PDT，America/Los_Angeles。此篇对应用户要求的第1项，41–44对应其余四项。

重点是三个连接：动画通道怎样引用事件，事件怎样指定位置/朝向来源，游戏怎样决定实际技能效果。前两者可继续读取格式和实际资源；**原作伤害提交、多部位去重及取消旧回调的消费者尚未恢复。** 本篇不会把一个特效事件直接命名成攻击伤害窗口。

## 原作格式：通道INFO索引与全局事件表

固定社区FX格式的SPAnimation头部保存eventCount/eventPointer，ANIM事件记录为96字节；通道INFO关键帧另存time、eventStartIndex、eventCount。工具实际写出/展开`eventStartIndex+i`，提供“某条通道某个时点→全局事件记录”的具体连接。[固定事件格式与SDK接口](evidence/public-action-event-format-contracts.json)

| 层次 | 可以核对的表示 | 不能直接等同 |
| --- | --- | --- |
| ANIM头部 | 全局事件表数量/地址 | 技能次数、伤害次数 |
| INFO关键帧 | 原始time、uint16起始索引、uint8计数 | 最终技能有效窗口或秒单位 |
| 事件记录 | 类型/标志、消息或名称及来源选择器 | 实际调用成功或效果已提交 |
| 运行消息 | SDK的messageID、pName、pCreature、blockIndex、parameter0/1 | 跨重建稳定的partId或伤害归属 |

ANIM解压坐标与包内压缩存储偏移分开。所选资源的INFO/事件定位及检查见[本机事件记录](evidence/local-selected-action-events.json)。既有原位段继续保留，不自动执行社区兼容改写。

本轮沿28已选资源取四个键，在Game/Patch各读一次，共8份版本记录；EXE完整文件、两包及各资源存储/解压摘要与此前一致。EXE本轮只散列身份，没有重新解释PE/版本资源或执行代码。没有扩大到新动画键。实际遍历770条INFO、60条事件、48条非零INFO引用行，共60次事件索引引用，非零范围均合法；这8份中没有同一个event index被重复引用。零count的起始索引保留原值，不将无引用的哨兵值强行判错。

| 所选ANIM instance | Game / Patch事件数 | Game / Patch INFO行数 |
| --- | --- | --- |
| 2f7ea086，路径com_charge_rush_hit | 10 / 10 | 101 / 98 |
| 38ed1075，路径com_spit | 5 / 5 | 81 / 79 |
| d4772d6f，路径com_strike_lvl01 | 8 / 8 | 113 / 113 |
| dc542b67，路径com_bite_lvl01_a | 7 / 7 | 93 / 92 |

名字只用于选样和定位，不能据rush_hit或bite名判定事件已造成伤害。header的0x11c字保留raw与SDK float候选，FX读取器对它没有给出明确语义；不由约0.033333的浮点候选强行换算事件time为秒。

## 本机具体例子：喷吐动画有两条同名hit事件

所选Patch ANIM `ee17c6ad:00000000:38ed1075`中：

| 通道原名 / 主查询cap | INFO原始time | start / count → event indices | 事件原值 |
| --- | ---: | --- | --- |
| head / mout | 0 | 0 / 1 → 0 | sound，vcom_spit |
| shoot_rng / shot | 16 | 1 / 2 → 1,2 | eventControl hit；sound sfx_crg_mucus_launch |
| poison_cell / wpps | 16 | 3 / 2 → 3,4 | eventControl hit；sound sfx_crg_mucus_launch |

这里poison_cell仅是**陆地Creature动画内部通道原名**，本轮不据该名字扩查水中阶段。两条hit是不同表项1和3，但name同为hit、id同为428ae400、flags同为0x62。两者positionSource均为flags2，即社区TYPE_DEFAULT；disabled/predicate位在这两条记录中未置位，但身体查询/绑定及消费者仍会影响执行。

这提供了比“未重复引用同索引”更有用的区别：**不同通道和不同eventIndex也可能指向同名/同ID通知。** 不能按名称全局去重，也不能按事件表项数给技能乘伤害。当前不知道shot/wpps在当前身体会选到几个实例、这些eventControl是否都被派发、以及hit消费者做什么；没有证明原作重复扣血或采用下文的逻辑slot账本。

## 原作格式：事件来源选择器与动作身体查询分别处理

AnimationEvent具有positionSource、rotationSource、scaleSource及source4四份独立选择器；每份12字节。source4的确切用途保持未知，不把四者全叫目标选择器。事件的位置、旋转、尺度也可能来自不同选择结果，不能只取某根骨的一个世界矩阵就称还原了原作。

固定社区枚举中TYPE_DEFAULT=2的注释关联触发通道的bodies；另有STANDARD_BODIES、OTHER_CREATURE、OTHER_STANDARD_BODIES等类型，以及FILTER_FIRSTONLY和FILTER_ALLEXCEPTFIRST。它们是**事件来源的查询/过滤表示**，不回填为39动画通道的选手政策。

FIRSTONLY表示社区格式支持一种筛选标签，不证明按稳定ID、最高技能或最近距离挑选。即使某事件只选一个来源，仍需消费者确定它是音效、特效、消息还是玩法提交，不能由此保证技能只伤害一次。反之，多只脚各有落脚声可以是正常表现，不能全局禁止重复事件名称。

本机确实读到FIRSTONLY，但出现在所选近战`impact_event`：position/rotation/scale的flags均0x12（default + firstOnly），source4为0x4015，保留未知用途。该事件类型是社区仍叫unk3的3，不是已知伤害类型。所选Bite的parameter0浮点75、Strike/Charge为100，也不当成伤害量。

Patch的实际时点和触发通道还有差异：Charge的head上hit与head_sec上impact_event都在原始time5；Bite的head上两者都在12；Strike的root上hit在11、R hand 2上impact_event在12。因此声音/特效/控制事件不能机械归为一个“攻击瞬间”，也不能把触发通道身体当成最终伤害肢体。八份样本的类型统计为effect26、sound18、eventControl10、unk3六条；本次没有type0x20001的message记录，SDK消息声明不因此成为本机已观察到的派发调用。

社区AnimatedCreature的AnimationMessage和Creature事件控制/能力接口提供消息接入入口；已读声明没有展示消息→投射物→命中→伤害函数体。blockIndex属于当前动画身体实例表示，不能沿用到另一版本肉体。

## 自研：表现通知、效果槽、命中窗口分开

以下结构、算法、数值全部是用户拼装/灵魂游戏的独立规格，未声称Spore采取同样政策。

| 对象 | 所有者 | 身份和职责 |
| --- | --- | --- |
| VisualEvent | 动画播放实例 | 播放代次/事件索引/循环次数/绑定部位；声音、特效、镜头 |
| EffectSlot | 技能ActionInstance | actionId + effectOrdinal；单次发射、生成护盾等逻辑提交 |
| HitWindow | 技能ActionInstance | windowOrdinal + 明确起止时间 + 固定执行者；期间采样攻击轨迹 |
| SpawnedEffect | 世界效果管理器 | effectId及出生来源；已经发射后独立移动/命中/结束 |

```text
ActionBinding { actionId, bodyId, bodyRevision, controlGeneration,
                bindingEpoch, selectedPartInstances[], helperInstances[],
                socketsByRole, claimedOutputs, reservedCosts }
EffectSlot { ordinal, markerTime, emitterRole, costPolicy, spawnDefinition }
HitWindow { ordinal, startTime, endTime, weaponRole, repeatHitPolicy }
SimulationTicket { actionId, ordinal, exactEmitterId, markerTime,
                   bodyRevision, controlGeneration, bindingEpoch }
```

默认选择独立模拟时间线负责玩法窗口。动画通知由适配器映射到表现，不能直接访问扣血接口；想用动画创作时点，可以把经过校验的时点编译到技能时间线，但运行提交仍经过行动调度器。这里的SimulationTicket是内部模拟凭据，不是客户端发送一个相同字符串即可取得网络权威。

## 自研：发射点绑定到选中部件的明确socket

为自己的部件资产定义稳定socket语义，例如Muzzle、Palm、ClawTip、BiteContact。编译时由具体partInstance/definitionVersion映射到当前稳定骨与局部框架；四个相同嘴共享socket定义，各自有实例位置。缺socket返回RequiredSocketMissing，避免静默从身体中心喷射。

```text
ResolveEmitter(ticket, currentBody, poseAtMarker):
    verify exact action, selected emitter, body/control versions and bindingEpoch
    reject missing/disconnected part, wrong slot or expired/cancelled action
    socket = lookup compiled socket by exact emitter instance and semantic role
    require socket belongs to current edited reference and current pose
    worldFrame = rootWorld * partPoseFrame * socketLocalFrame
    origin = transform socket point
    direction = normalize transformed declared forward under own frame policy
    reject nonfinite/degenerate direction; return origin/direction and identities
```

永久拉长嘴已更新参考socket，就不能发射时再次乘相同造型缩放。镜像及非均匀缩放的方向政策详见41；本文数值例只有绕Z旋转和位移，不能外推为通用仿射方向公式。

单嘴技能明确绑定M2，事件里出现M1来源时报告UnexpectedEmitter；双嘴齐射则声明两个EffectSlot与各自执行者，不从“查询出了两张嘴”自动扩增。纯灵魂技能可以使用另有定义的SoulOrigin，不伪造一张嘴提供资格。

## 自研：一次发射的去重与事务

```text
OnSimulationMarker(ticket):
    action = exact live action lookup; reject unknown/inactive action
    verify ticket/body/control/binding identities and owned marker time
    verify slot and exact emitter dependency, claim and resource reservation
    key = (actionId, effectOrdinal)  // single-use logical slot
    if key is committed: return DuplicateIgnored(key)
    spawnPose = resolve current valid emitter pose at this logical marker
    within this actor's serialized effect transaction:
        consume declared reserved cost
        create owned effect with immutable birth source and spawn pose
        record slot commit and its result
    return committed effect or explicit failed result
```

这个键故意不包含动画通道名或嘴partId：同一个逻辑发射槽收到两份通道通知仍只提交一次。真正双发使用ordinal0/1；周期技能另外定义periodOrdinal，不靠反复播放同一特效事件模拟持续伤害。

去重必须与消费/生成的同一事务边界提交。生产系统如果效果创建失败，需明确未提交/补偿/重试状态并保留预约所有者，不能先扣资源或标成功再吞掉创建错误。本文可执行算例只验证actor内串行成功/拒绝路径，不保证联网或崩溃后的exactly-once。

表现可以用更细的键`(playbackEpoch,eventIndex,cycleOccurrence,bindingPartId)`：不同脚落脚声各自保留。它的重复政策与单次玩法槽不同。禁止用“事件名相同”全局去重，或用“每只嘴一份”制造多个玩法提交。

## 自研：伤害窗口需要轨迹裁剪，而不是一个消息时点

近战窗口每步与当前模拟区间求交集，仅在交集里求武器扫掠。即使一帧跨过窗口的起点和终点，也应计算中间有效轨迹，不能先关窗口后漏掉整次攻击。

```text
StepMelee(action, previousTime, currentTime):
    validate current bound weapon and required pose/dependencies
    for each declared window:
        lo = max(previousTime, window.start)
        hi = min(currentTime, window.end)
        if lo >= hi: record NoActiveSweep; continue
        trajectory = sample/subdivide own weapon motion only on [lo, hi]
        candidates = broadphase bounds of this swept weapon
        for target in candidates permitted by skill:
            reject stale target lifetime, team/policy or missing hit shape
            hit = swept shape intersection against target's matching-time motion
            if hit:
                key = (actionId, windowOrdinal, targetEntityLifetime)
                commit only if own repeat policy and ledger permit
```

同一窗口可以命中多个合法目标，但每目标是否只算一次由技能声明。两个手部通道产生同一逻辑窗口时，共用windowOrdinal与命中账本；明确左右各挥一次才声明两个窗口。去重键不包括部件，避免同一窗口重复打同一目标；目标生命代次避免实体编号复用污染。

投射物在发射时只提交生成与成本，伤害在世界投射物实际接触时提交。它另外维护impact去重、穿透/爆炸/多目标政策，不能将发射动画结束解释为投射物消失。相对运动、弯曲武器、高速旋转等需要产品实际碰撞契约；下面用二维线性扫掠构造演算。

## 自研：中断、断肢和迟到事件

断肢、换魂是用户产品需求，本轮没有取得Spore陆地阶段具有这些机制的证据。原作这一方向只追动画事件/消息、停播及身体重建入口；下面的断肢结算全部是我们的设计。

| 发生时点 | 当前行动处理 | 已提交世界效果 |
| --- | --- | --- |
| 发射/命中前中断 | 取消未提交槽/窗口，释放未消费预约，递增bindingEpoch | 无新的效果 |
| 发射后中断 | 停止后续槽、动作与所属表现 | 已发射投射物继续按自己的生命周期 |
| 执行嘴/手断开 | DependencyLost，取消依赖该部件的行动 | 已提交结果不回滚 |
| 非依赖部件改变 | 重新验证相关姿态/碰撞/绑定，按技能政策重绑或取消 | 不无条件删除其他效果 |
| 换魂/换肉体 | controlGeneration改变，旧控制与绑定事件失效 | 保留出生时的施法/归属快照 |
| 骨骼重排/重编译 | 新映射和bindingEpoch提交后拒绝旧blockIndex/旧token | 不拿旧下标发射新嘴 |

迟到事件要经过live action和代次检查；不能只因为它还携带一个合法eventIndex就执行。资源释放令牌仍由旧行动持有，迟到清理不能释放新行动的预约。取消可重复调用，释放结果可诊断；缺依赖先拒绝提交，再由行动状态机结算取消，不隐式退款已经消费的成本。

编辑时若允许正在进行的行动继续，需重新核对依赖、socket、轨迹与输出预约，显式提交新绑定代次；旧队列条目作废。颜色编辑等纯视觉变化不应被误认为碰撞身体版本，相关版本分层见44。

## 自研完整例子：两嘴身体，单嘴喷射与断肢

身体revision42、控制代次7有M1/M2两张嘴。灵魂选择单次技能A17，唯一slot0绑定M2，markerTime=0.3s、能量成本5；初始能量20。这里只用自研秒与米，不替换原ANIM原始time单位。

1. 启动A17预约5，可用余额15，但尚未消费；M1不能因也有Muzzle而参与slot0。动作辅助嘴部曲线与特效通道不改变slot数量。
2. 模拟从0.2s跨到0.4s，调度器发现`0.2<0.3≤0.4`，产生一次内部marker。起点0的marker另在启动时显式处理；普通区间用左开右闭，避免每帧端点重复。
3. 自研身体根位置(10,2,0)m、绕Z旋转90°；选定嘴安装位(.6,.2,.8)m、已编辑socket(.3,0,0)m。先得根局部点(.9,.2,.8)，旋转后(-.2,.9,.8)，所以发射点(9.8,2.9,.8)，单位方向(0,1,0)。它不是身体根(10,2,0)，也不使用M1的位置。
4. 提交slot0，能量20→15、预约5→0，生成P17并记录(A17,0)。两个模拟通知重复到达返回DuplicateIgnored；来自M1的错误执行请求返回UnexpectedEmitter；纯AnimationVFX通知返回NonAuthoritativeEvent。
5. 本例P17以12m/s沿方向前进，静止目标位于(9.8,8.9,.8)，6m距离对应0.5s旅行。实际碰撞确认后，伤害12，HP100→88；impact重复通知不再扣血。这里只演算固定直线目标，移动目标需要实际扫掠检查。
6. 若M2在0.2s断开，A17取消且旧ticket失效，能量仍20，无P17。若在0.4s、发射后断开，行动结束但P17已经存在，仍可在后续接触目标；能量保持15，不回滚已消费成本。
7. 若定义真正两嘴齐射，slot0=M1、slot1=M2，各5成本；总预约10，两次合法提交后能量10、投射物数2。半途只发第一发再取消时，保留一发/已消费5，释放第二发的5预约；没有自动补发。

## 自研完整例子：多手通知与一次爪击窗口

一次爪击A18固定手H2，window0=[0.25,0.4]s。模拟一步0.2→0.45s，简化二维爪尖匀速从(0,0)→(2,0)m：有效区间裁到0.25→0.4，归一化进度0.2→0.8，实际扫掠线段(.4,0)→(1.6,0)。

目标中心(1,.2)m、半径.15m，爪尖扫掠半径.1m，目标到线段距离.2m≤.25m，命中一次并记(A18,0,targetLife1)。另一个通道请求同窗口返回DuplicateHitIgnored，不因四只手而乘四。目标若在(1.95,0)、半径.05m，与有效线段距离.35m>.15m，判定Miss；整帧末端虽接近它，也不属于有效窗口。

显式第二挥window1可再命中同一目标；编号复用但生命代次不同的targetLife2按新对象处理。断H2使窗口失效，不能仅把相同window0搬到H4继续算命中；改选H4需新行动或技能明确规定的转换，并重新验证时间线和轨迹。

## 检查、未知与下一步

[独立事件/效果检查](checks/verify_action_effect_lifecycle_examples.py)27项通过，覆盖跨帧marker、多嘴slot、错来源/非权威事件、窗口裁剪、每目标去重、中断/断肢前后、旧代次、资源预约和无效输入。[事件格式读取器](checks/verify_action_event_reader.py)20项通过；[本机记录一致性](checks/verify_five_topic_event_evidence.py)8项通过，核对资源子集、身份、原字节/索引、同名hit和实际firstOnly。五篇合计111项研究/算例检查及整体文档检查见[本轮总验证](evidence/land-five-topics-verification.json)，不与先前模块合并；检查不证明原作实际执行或生产战斗实现。

已回答/部分回答：固定格式的通道→事件表索引、事件位置/旋转/尺度来源表示和SDK消息入口。未回答：本机事件消费者是否/何时提交伤害、原作多手多嘴去重、真实有效窗口、重建/中断后旧消息抑制。实际资源数量/读取结果以本机记录为准。

未做：启动/附加、原生反编译、私人存档、完整动画/模型/纹理导出、用户产品实现。REA/provider缺口沿用00，未安装/构建或改配置。

风险：事件名称、类型和source标志不能替代运行消费者；独立模拟时间线与actor内账本需要在产品的物理/网络/持久化契约中验证。后续最有判别力的原作证据是AnimationMessage消费者及技能发射/伤害函数，而不是再用特效名字猜攻击时点。
