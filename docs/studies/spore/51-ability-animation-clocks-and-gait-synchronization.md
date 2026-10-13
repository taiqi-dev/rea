# 51：技能、动画与多足步态的时间同步

范围仅为陆地 Creature Stage。能够确认的是多个时间字段及其编码、公开的播放接口和历史步态设计；本机技能时钟怎样驱动动画时钟仍未恢复。本篇后半给出独立规格，不把自研秒数、循环规则或频率公式说成 Spore 算法。

来源清单、原始文件 SHA256、实际读取范围与阴性边界见 [public-animation-clock-contracts.json](evidence/public-animation-clock-contracts.json)。独立验证见 [animation-clock-verification.json](evidence/animation-clock-verification.json) 和 [检查脚本](checks/verify_animation_clock_examples.py)。五模块整体验证由根代理汇总至 [land-runtime-five-topics-verification.json](evidence/land-runtime-five-topics-verification.json)。本轮没有新读游戏 payload，因此没有新建 `local-selected-animation-clocks.json`。

## 原作和公开代码：时间没有收敛成一个已知单位

| 证据层 | 确认内容 | 不能直接推出的结论 |
|---|---|---|
| SDK 声明 C08 | `cCreatureAbility` 分别有 `mEffectDuration`、`mRefresh`、`mDuration`、`mRecharge`、`mReactionDuration` 与动画 ID 列表 | 技能 duration 等于动画 length；冷却等于播放时长；这些 float 的本机单位 |
| FX 格式代码 C01/C02 | ANIM `length` 是 `0x120` 的 LE float；INFO `time` 是每条记录 `+0` 的 LE int32，文本解析范围为 `0..(int)(length-1)` | `time=16` 是16秒、16毫秒或16显示帧；原生系统用怎样的公式推进此整数坐标 |
| FX 生产者 C01，SDK C05 | FX writer 在 `0x11c` 固定写 `0x3d088889`；SDK 把此处命名为 `frameLength` 并注释 `1/30` | 所有播放固定30 FPS；`length*frameLength` 就是本机最终秒数；渲染帧率控制技能时钟 |
| TLSA C03/C04 | 旧格式把一个 `durationScale/duration` 对赋给组内引用；新格式每个动画引用保存一对。另有 `blendInTime`、`allowLocomotion`、`endMode`、`randomizeChoicePerLoop` | `durationScale` 必然乘或除播放速度；`-1` 的原生回退规则；endMode 的枚举意义 |
| SDK 播放接口 C07 | `SetAnimationBlendInTime`、`SetLoop`、`SetLoopTimes`、`GetCurrentAnimation` 的可选 float 时间输出、`GetAnimationLength` 及 `anim_query` 引用字段 | 未命名 float 接口就是调速/暂停；`field_A8 //current time?` 是已经验证的进度字段 |
| SDK 世界接口 C06 | `Update/UpdateCreatures/PostUpdateCreatures` 接收 float `deltaTime`；seconds 注释带问号 | 本机秒单位、调用次序、帧率、暂停所有权 |
| GAIT C09/C10 | LE float `speedi/stepLength`、相位字段、成对的 `trigger/dutyFactors` 和路径记录 | `speedi` 就是米/秒；原生频率等于速度除步长；资源槽位就是某只实际脚 |

这些代码分别来自固定 [FX SPAnimation.java](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/SPAnimation.java#L69)、[InfoComponent.java](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/InfoComponent.java#L130)、[TLSAAnimationGroup.java](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/tlsa/TLSAAnimationGroup.java#L69)、[SDK SPAnimation.h](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/SPAnimation.h#L33) 和 [AnimatedCreature.h](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/AnimatedCreature.h#L71)。它们是社区读写实现或接口声明，不能升级为 Maxis 原生源码。

`SetLoopTimes` 的社区注释明确允许小数，例如0.5只播半段；大于1须启用循环，-1无限循环。该注释只约束我们怎样理解公开接口，不证明目标内部怎样触发边界事件。FX 的动画文本 `length/time` 读写没有单位换算；INFO 的整数类型及与 length 的大小关系是“索引式坐标”的线索，仍不足以落实秒数。[SDK 循环声明](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/AnimatedCreature.h#L84)

另外，社区 [AnimEditor.java 84–143行](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/view/editors/AnimEditor.java#L84) 的2000ms Timer 轮询文件修改并重载，不是动画播放器节拍。固定 FX 文件名检索没有 `AnimationPlayer/AnimPlayer` 命中；这只是有界路径检索，不是“游戏没有播放器实现”的证据。

## 开发团队历史说明：步态与动作目标在姿态层合成

重新完整读取 [SIGGRAPH 动画论文](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf) PDF第5–7页。第5页§3.3/§4说明曲线包含姿态、deform、权重与离散视听/数据事件；运行时逐帧计算并混合姿态目标，再合成 locomotion、IK 与次级运动。第6–7页§4.2把腿按近似长度分组，以小有理数近似长度比决定相对周期频率；duty 是落地时间占周期的比例，trigger 是单脚周期的偏移。速度用于插值步态参数，不同腿组可同时用不同样式。

这支持“行走与手部动作在姿态目标层共同参与”的历史解释。论文没有给 INFO 原始整数时间的消费公式、技能 duration 与动画时间的连接、循环事件去重、暂停或长手自动减速规则。不要用历史步态频率设计替代本机尚未恢复的时间代码。

## 本机已选资源：复用原始坐标，不换算秒

身份沿用已有完整摘要：`SporeApp.exe` SHA256 `f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d`。28/40/26 的 Game/Patch 包身份、资源字节摘要与读取范围均在旧 JSON 中，本轮重新校验的是这些 JSON 的摘要，不是重新读取/计算整个游戏包。

复用 [40事件记录](evidence/local-selected-action-events.json) 的同组 `ee17c6ad:00000000` 四个 ANIM key，Game/Patch 各一份，共8个版本：

| instance | 名称线索 | raw length | 已引用 INFO 的不同 raw time |
|---|---|---:|---|
| `2f7ea086` | charge rush hit | 51 | 0,1,5,13,17 |
| `38ed1075` | spit | 50 | 0,16 |
| `d4772d6f` | strike level1 | 46 | 0,7,8,11,12,14 |
| `dc542b67` | bite level1 | 39 | 0,4,10,12,14 |

Game 为 ANIM v21，Patch 为v25；八份 `0x11c` word 都是 `0x3d088889`，解释成 IEEE float 的候选值为约0.0333333351。40保存770个INFO行，其中48个非零行引用60个事件 occurrence；一行可以引用多条事件，不能把行数和事件数混用。上述候选浮点值没有被乘到事件 time 上。

复用 [28动作引用](evidence/local-selected-action-channels.json)：TLSA key `4aeb6bc6:00006f14:f8cc4670` v7 与 `4aeb6bc6:000082d0:142cba20` v10，各13个已选组；引用数分别13/128。它们全部 `durationScale=1`、`duration=-1`，组 `blendInTime=-1`。这些值缺少原生消费者，不能被宣布为1倍速、自动动画长度或无过渡。

复用 [26步态记录](evidence/local-selected-movement-resources.json) 的两份 `25df0112:00000000:b00eaf60` gait6 v11：八个 speedi 为0、2.5、4、5.5、6.5、7.5、8.5、10，每组有六对trigger/duty。speedi=0的trigger约 `[0,.5,.3333,.8333,.6666,.1666]`，duty全为.5。格式由 [GaitGroupKey.java 53–139行](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/gait/GaitGroupKey.java#L53) 说明；原生脚绑定、插值、相位推进、急停与单位仍未知。

## 独立规格：让权威动作时间、视觉时间和步态时间各有所有者

下面全部是自研秒、米与周期，不读取 Spore 时间坐标。保持 [40事件](40-action-events-emitters-hit-windows-and-stale-callbacks.md)、[42共享关节](42-branched-limbs-shared-joints-and-goal-conflicts.md)、[47中断](47-hit-reactions-action-interruption-and-ai-recovery.md) 的“候选事件与实际效果分开”原则；目标接触权威另由接触模块确定。

| 状态/所有者 | 核心字段 | 规则 |
|---|---|---|
| 模拟器 ActionClock | action ID、controller generation、body revision、action epoch、elapsed秒、duration秒、rate、状态、已处理tick、resolved effect slots | 决定资格窗口和效果提交机会。完成、取消、换身体/控制者后旧票据失效 |
| 动作定义 | 排序的秒标记、独立effect-slot ID、执行肢体集合、允许移动策略 | 定义可触发窗口；伤害效果由接触和目标验证判定。效果槽无论Hit/Miss都解析一次 |
| 视觉实例 | playback epoch、clip自身明确单位、unwrapped cursor、loop period、marker ordinal、rate、transition weight | 产生姿态/视听事件。视觉重复不再次提交同一动作效果 |
| 腿组 GaitClock | 连续 cycles、实际位移、自己的stride米、六足相位偏移、stance/flight、脚锚点、stop模式 | 依据实际移动推进，挥击、镜像或换视觉片段不清零腿相位 |
| 过渡实例 | outgoing/incoming实例、各自时间、过渡elapsed秒、长度、权重曲线 | 两个片段可同时采样，游戏效果所有者仍是同一个ActionClock |

ActionClock 使用模拟时间，与显示FPS无关。自研公式 `elapsed'=min(duration,elapsed+dt*actionRate)`，先验证有限非负输入和递增tick，再处理 `(old,new]` 内所有标记。零时刻标记在start时显式处理，末尾标记在Completed之前处理。一个大步跨过两个标记就按时间顺序处理两次；暂停冻结elapsed，恢复后不补发暂停期间未流逝的动作时间。暂停期间实际移动是否继续由动作策略决定，本例允许。

视觉有两种明确策略：与动作绑定时 `clipPosition=clipLength*elapsed/duration`；装饰或循环待机可独立推进。视觉单独倍速/暂停不能反向改变伤害时刻。若动作获准加速，模拟器先切分到倍率变更点，再让后续dt乘新actionRate；与动作绑定的视觉相应重采样。不得先按旧倍率推进整段，再回头修正事件。世界暂停则统一冻结模拟、动作与权威步态，显示插值不创造模拟事件。

播放率0作为显式停播，自研禁止负倍率、NaN、无穷值。导入原资源时，未知的`-1`先保留为带来源的未解析配置，不能直接喂给非负rate，也不能偷偷取绝对值。

### 伪代码：跨步事件、循环与过渡

~~~text
StepAction(action, segmentWorldStart, dtSeconds, tick, approvedRate):
  reject nonfinite/negative dt/rate, nonincreasing tick, inactive action
  old = action.elapsed
  next = paused ? old : min(duration, old + dtSeconds * approvedRate)
  pending = sorted markers satisfying old < marker.seconds <= next
  ticket = action.creationTicket; reserve this tick against duplicate scheduling
  for marker in pending:
    eventWorldTime = segmentWorldStart + (marker.seconds-old)/approvedRate
    enqueue into ordered simulation event queue, ahead of segment completion
  enqueue segment completion; consume queue chronologically:
    advance authoritative world/root/targets to each eventWorldTime
    process earlier cancellation/death/body-change events before skill commits
    update action.elapsed to this marker coordinate
    revalidate captured ticket and execution bodies at this logical marker point
    if effectSlot already resolved: continue with DuplicateSlot diagnostic
    resolve contact/target eligibility: Hit or Miss; mark slot resolved
    commit eligible effect once; queue visual/audio event separately
  after segment completion: publish next/tick only if ticket is still valid and Running
  when ticket valid, still Running and next == duration: Completed; release unused reservations

LoopOccurrences(previous, current, L, markerOrdinals):
  require 0 <= previous <= current, L > 0, each 0 <= markerTime < L
  for each marker m:
    firstCycle = max(0, floor((previous-m)/L)+1)
    lastCycle = floor((current-m)/L)
  preflight total occurrence count; on overflow return diagnostic without advance
  enumerate occurrences k*L+m in (previous,current], ordered by time then ordinal
  identity = (playbackEpoch, cycleOrdinal, markerOrdinal)
  dispatch fresh identities; advance unwrapped cursor
  handle initial cycle's time-zero marker only at explicit start

Transition(outgoing, incoming, dt):
  sample each using its own approved cursor
  transitionElapsed += dt in explicitly chosen visual clock domain
  alpha = min(1, transitionElapsed / transitionDuration)
  blend matching pose DOF with (1-alpha, alpha)
  ActionClock remains sole gameplay effect owner
  on cancel/rebind invalidate outgoing callbacks and keep resolved gameplay effects
~~~

零标记放在半开周期 `[0,L)` 内；`m=L` 作为循环标记拒绝，避免它与下一圈零时刻混淆。只比较wrap后的两个phase会漏掉整圈；按unwrapped cursor与cycle ordinal识别可覆盖多圈。循环视觉event名字相同也要保留不同ordinal；与同一个gameplay effect-slot是否等价由动作定义明确决定。

一帧跳过十亿圈时，不逐圈盲目分配列表。先算 occurrence 数并检查容量，失败保持cursor不变并返回 `OccurrenceCapacityExceeded`。调用者按模拟预算分段消费，或显式丢弃非关键视听事件并记录Dropped计数；战斗标记不能静默丢弃。发生取消时保留已提交效果，后续marker与旧generation/body revision/epoch票据都拒绝；视觉淡出可以继续，但没有提交权。

上面的权威事件队列要求模拟状态按标记时间推进，或具有覆盖同一时间段的权威状态历史。缺少二者时应返回 `MissingSubtickWorldState`，不能把整段末尾的目标/肢体位置当作较早hit时刻的位置。暂停或rate=0没有pending，因而不会执行除法。不同事件同一世界时刻时先处理死亡/取消/结构变化，再验技能提交票据；这个顺序必须成为产品契约。检查脚本只实现标记枚举、时钟与票据，不声称已经实现物理队列或历史回溯。

## 独立贯通算例：六足移动，同时一只手挥击

构造参数：六只脚，自己的stride=1m，实际根移动2m/s；足偏移 `[0,1/2,1/3,5/6,2/3,1/6]`，本例偏移开始stance，stance条件为局部phase<.5。定义 `cycles += actualDistance/stride`，其中actualDistance是本段实际前进距离；侧移/倒退/原地转身需要各自路径策略，本例不涉及。足phase为 `(cycles+offset)%1`。这个频率公式和槽位绑定都是自研，虽然选用了易理解的六槽偏移。

同一生物手A发动1.0s挥击：hit标记在动作.35s，recover在.65s，示例接触检查通过一次，目标HP50减12至38。动作启动选择实际手A及肩祖先，冻结时长/marker，取得其DOF预约；腿组继续掌管支撑目标，共享躯干通过 [42协调规格](42-branched-limbs-shared-joints-and-goal-conflicts.md) 合成。假定两个动作视觉片段已经对齐自己的hit位置；进入片段用独立.2s线性过渡，其权重不会移动权威hit。

| 世界秒 | 动作elapsed | 手部视觉进度（本例clip1s、绑定动作） | 腿组cycles/phase | 结果 |
|---:|---:|---:|---|---|
| 0 | 0 | 0，incoming权重0 | 0/0 | start、预约手A；零时刻事件单独处理 |
| .2 | .2 | .2，incoming权重1 | .4/.4 | 过渡结束，脚继续循环 |
| .35 | .35 | .35 | .7/.7 | hit资格成立，提交12伤害；HP38 |
| .4 | .4 | .4 | .8/.8 | 暂停手动作，腿继续移动 |
| .6 | .4 | .4 | 1.2/.2 | 恢复手动作，之后动作rate=2 |
| .725 | .65 | .65 | 1.45/.45 | `.4+(.725-.6)*2=.65`，recover一次 |
| .9 | 1 | 1 | 1.8/.8 | 动作完成；根急停，腿进入Settling |
| 1.05 | 完成 | 已退出动作片段 | 1.8/.8保持 | 三只飞行脚完成落脚，转Stopped |

若模拟器直接从世界.6跳到.9，动作从.4推进到1，recover和完成仍发生；如果世界.0跳到.8，则必须先切成 `[0,.4]`、暂停段`[.4,.6]`、倍速段`[.6,.8]`，不能用单一倍率处理全部时间。示例没有把伤害交给视觉渲染帧；丢渲染帧不会漏hit。

在.9急停，六足phase为 `[.8,.3,2/15,19/30,7/15,29/30]`，脚2/3/5处于stance，脚1/4/6在flight。立即固定根和当前支撑脚世界锚点，保持cycles=1.8；给三只飞行脚基于当前姿态、可达范围和地面采样的落脚终点，.15s内完成独立settle轨迹，不能瞬移脚或把整个gait归零。检查脚本只核对相位冻结/三脚到六脚接触状态和时限，不证明地形碰撞、真实IK或轨迹速度连续；这些须在自研引擎验证。恢复移动时保留脚锚点与phase，重新选可行步长/落足计划，不能把phase重启视作脚锚点自动正确。

循环视觉另举独立数值：L=1s，marker ordinal0在0，ordinal1在.25。显式start发出`(epoch11,cycle0,ordinal0)`；一次推进到3.25跨过7个新occurrence：.25、1、1.25、2、2.25、3、3.25。再以dt=0调用没有新事件。重复callback按完整occurrence身份去重；这不意味着同一技能跨圈重复造成伤害，技能是否重复命中由自己的effect-slot/attack-window定义。

### 长手：改几何轨迹，时长在开招前锁定

本例短手到hit路径.4m，长手路径.8m，hit间隔均为.35s。选择自研最小jerk时间曲线 `s(u)=10u³-15u⁴+6u⁵`，u属于[0,1]；其导数最大值1.875，因此峰值速度分别为 `1.875*.4/.35≈2.142857m/s` 和 `1.875*.8/.35≈4.285714m/s`，均低于自定5m/s预算。长手改变可达路径和肢体姿态，动作时长、hit时刻以及腿的cycle都保持上述表格。

若路径改为1.1m，平均速度约3.142857m/s仍低于预算，但峰值约5.892857m/s已经越界。开招前拒绝 `ArmPeakVelocityBudgetExceeded`，或由明确动作变体重新规划轨迹/获准选择更长时长，再冻结新的标记。不能只检查平均速度，也不能开招后悄悄拉长权威duration；若允许中途改时序，必须生成新action epoch、明确重映射尚未触发marker并使旧票据失效，已提交hit不重播。该复杂策略本篇未实施。

共享骨架和目标冲突也可能使几何不可行：在42的协调器里降低非支撑目标、重选执行手或拒绝动作，并保留诊断，不能通过偷偷重置脚相位修复。骨骼DOF混合的租约/约束和时钟所有权是两种问题。

## 实际验证、未做与风险

[检查脚本](checks/verify_animation_clock_examples.py) 实际通过35项：20项动作/视觉时钟，8项步态/几何，1项上述完整六足挥击时间表，6项既有证据一致性。包含跨帧与分帧等价、精确边界、循环整圈、同时间不同event ordinal、pause/2倍速、取消、旧tick/代次/身体版本、十亿圈容量拒绝、结束clamp、六足相位和急停、峰值速度拒绝、原始字段范围与文件摘要。使用有理数核对本例边界，生产时钟的浮点容差、tick整数表示和并发提交仍需产品实现时确定。

未做：没有游戏启动、附加、私存档、原生反编译、新包payload读取或完整资产导出；没有安装、配置、provider setup或Git写入。REA/native消费者仍缺失，沿用此前阻塞。网络普通读取DNS失败后，正式只读恢复成功，失败与恢复均记录在manifest。

原目标问题状态：字段编码、公开循环接口和历史多腿周期设计已回答；`INFO.time`到秒的公式、TLSA倍率/负值解析、技能duration与clip关系、原生pause/transition/loop事件语义、实际腿槽绑定及长手重定时策略均未回答。优先的后续判别场景是固定技能、同形态不同渲染帧率与同形态不同批准动作倍率，记录模拟开始/效果/动画结束三种时间；仅改变外形长度再比较同一组时间。此处只提出场景，没有声称运行过。

剩余风险：独立检查不验证Spore运行时；静态资源的同名事件与未解析sentinel不能直接成为生产效果/播放规则。本例尚未验证实际地形、IK、共享关节约束和渲染过渡的视觉质量。
