# 52 注视、头身方向与多器官注意力

[目录](README.md) · [感知与目标记忆](27-perception-target-memory-and-motive-selection.md) · [并行动作](28-parallel-actions-channel-ownership-and-conflicts.md) · [角色绑定](39-same-role-effectors-variant-binding-and-default-mixing.md) · [完整身体](50-complete-creature-recipe-runtime-bones-and-bindings.md)。范围是登陆后Creature与编辑预览，两个范围分开标记。

**原作已有根方向、编辑注视目标及外部目标相对旋转的格式入口，但没有恢复眼→颈→躯干求解或多个器官各看不同目标的运行规则。** 所读612通道有9条置社区LOOKAT位，实际全部使用`skrs`手部查询，而非眼或嘴查询；因此LOOKAT这个名字不能直接证明凝视实现。后半篇为我们的双头身体设计独立注意力与方向分配。

## 原作：已有目标，不等于每个器官独立瞄准

固定SDK提交`2d71289adc71aa5c58f4516c6c835c99f5f9ca19`和FX提交`a482c51d8d37fc8cf416acecc3c00a5b0723f2e5`。来源原字节、完整摘要、行段与读取覆盖见[本轮证据](evidence/gaze-head-attention-observations.json)，均是社区声明/格式或社区辅助代码，不是原游戏执行体。

| 入口 | 实际字段/操作 | 边界 |
| --- | --- | --- |
| EditorCreatureController.h 28–30、42–59 | SetTargetPosition/Angle；位置/角度字段；mTargetLookAt@0x58、mCurrentLookAt@0x64、mSmoothLookAt@0x84 | 是编辑控制器；没有逐眼/多头目标列表，平滑公式未知 |
| cEditorAnimWorld.h 26–28 | SetTargetPosition/Angle以creatureID为键 | 不是逐器官目标接口；也不证明直接设置AI目标 |
| AnimatedCreature.h 128–153 | 根mPosition/mOrientation、p_cid和mpModel | 根方向与骨姿态分开；未知field164的dest注释仍有问号 |
| IAnimWorld.h 13、34–43 | 整生物加载/更新；带方向与输出normal的回调类型 | 回调角色与调用者未明确，不猜成凝视求解器 |
| Animations.cpp 26–38、71–88 | 社区helper按固定idle_walk/lookat相关ID分类 | 可读的类别辅助代码；不能作为眼球转向算法 |
| AnimationChannel.java 87–90、469–474 | LOOKAT位8；文本输出`rotRelativeExtTarg` | 外部目标相对旋转编码；目标坐标、槽位、来源与器官分配未知 |

直接来源：[编辑控制器](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/EditorCreatureController.h#L42)、[编辑动画世界](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/cEditorAnimWorld.h#L26)、[运行实例](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/AnimatedCreature.h#L128)、[动画世界](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/IAnimWorld.h#L13)、[社区分类helper](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/SourceCode/Anim/Animations.cpp#L26)、[LOOKAT字段](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimationChannel.java#L469)。

`AnimChannelParser`58–63把`rotRelativeExtTarg`编码到LOOKAT8；secondary命令在191–197独立设置SECONDARY1。通道主次查询、外部相对旋转、blend/variant组及眼部局部deform不是同一个开关。[固定解析器](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimChannelParser.java#L58)

本轮IAnimManager.h完整49行限定查look/gaze/eye/head/target/orientation，没有对应匹配；其他已选声明也没有给出逐眼目标分配方法体。这项有限阴性不证明原游戏没有多器官能力。27取得的感知/脱离目标调参也没有建立“AI目标→眼/头姿态”的调用链，不借它们补注视TTL或优先级。

## 本机通道：真正看到的是哪一类

复用45的46份实际解压ANIM元数据，重新读取其完整JSON并记录摘要；本轮52没有再读ANIM包payload，没有新增lookat名称的动画资源。612通道中，主context的mout有104条、eye有46条；LOOKAT8共有9条，全部主cap原字节`736b7273`（`skrs`）。没有eye/mout通道同时置LOOKAT8，不据此推断它们运行时不能看目标。

| 所选原记录 | decoded CHAN起点 | movementFlags @CHAN+0x88 | 主context位置与原值 |
| --- | ---: | --- | --- |
| Game `d4772d6f` #8 `R hand 2` | 32856 | `0x00000009` @32992 | @32996，flags8、cap`skrs` |
| Patch `d4772d6f` #7 `R hand 2` | 14500 | `0x00000009` @14636 | @14640，flags8、cap`skrs` |
| Patch `32183549` #7 `R hand sec` | 25884 | `0x00000008` @26020 | @26024，flags`0x00800108`、cap`skrs` |
| Game `0af13430` #5 `eyes` | 11940 | `0x00000000` @12076 | @12080，flags0、cap bytes`65796500` |
| 同资源 #3 `head` | 6508 | `0x00000000` @6644 | @6648，flags0、cap`mout` |

所有资源类型/组为`EE17C6AD:00000000`；文件存储位置和压缩前后摘要在证据中保存。上表是解压后的内部偏移，不是包文件offset或函数地址。前三条secondary均是flags2/空tag；其中movement9包含SECONDARY1也不能据空tag猜一个活动外部目标。`eyes`/`head`是作者通道名，mout不是“整颗头”的永久ID。眼部通道可以承载眨眼或其他标量，而不必是凝视方向；本轮没有解曲线或播放观察。

EXE身份复用45的固定SHA256`f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d`，52没有重新散列EXE。50另复核了Game/Patch包并读取小配方候选；那项工作不构成注视算法证据。当前能回答表示入口，仍不能回答原作怎样让多眼/多头独立观察、怎样与走路/攻击协调，以及目标丢失的处理时机。

## 自研：注意力意图、方向目标与骨骼输出分层

以下类型、优先级、限角、TTL和公式全部为自研。沿用50的H0/H1、E0–E3、M0/M1及共享脊柱。肉体提供每个器官稳定ID、可写自由度、父链与约束；灵魂提供希望观察的对象与行为理由。

```text
AttentionIntent { controllerRevision, targetId, purpose, priority, organRole,
                  observedPosition, observedAt, memoryPermission }
GazeRig { headId, eyeIds, mouthId?, neckChain, sharedSpineDofs,
          referenceFrames, limits, couplingProfile }
GazePlan { bodyRevision, soulRevision, perHeadTarget,
           perEyeGoals, neckGoals, sharedSpineGoal, residuals, diagnostics }
PoseReservations { ownerAction, jointDof, lockedPoseOrLimit, expiry }
```

观察目标不能自动变成攻击目标；攻击选定M0及其头链后，注意力可以协助瞄准，但不得另选M1造成射击/咬击目标不一致。双眼默认属于同一头的耦合组，注视同一目标；允许分眼独立目标的身体须另声明限制与可读表现。多个嘴、眼、颈共享骨链时，由DOF协调器一次提交共享姿态，不能每个器官各写同一脊柱。

每头的目标候选先过滤为当前灵魂可以知道、仍存在且该器官可观察的对象。优先级由自有行为目录显式给出：攻击协助100、其他头警戒20等。相等按稳定head/targetID排序；若引入保持旧目标的滞后阈值，需要另列数值和测试，本文没有暗设原作策略。不同头可接受不同候选，但共享躯干只由当前合法最高优先请求提出方向增量；运动/攻击已预约的DOF优先锁定，不靠简单平均牺牲瞄准或支撑。

## 自研算法：眼→颈→共享躯干的受约束分配

```text
BuildOwnGazePlan(bodySnapshot, soulSnapshot, intents, reservations):
    reject mismatched body/soul revisions and unresolved organ IDs
    for each head group:
        choose a permitted current target or explicitly labelled memory target
        compute finite target direction in that head's reference/world frames
        if near-zero direction: return CoincidentTarget; no divide-by-zero pose
        derive desired orientation and own anatomical limits
        spend allowed eye range first, then available neck range
        offer the unsatisfied residual to shared spine, without changing root
    shared spine:
        obey motion/attack reservations and support controller constraints
        select legal highest-priority residual request with stable tie-break
        clamp by shared limits; never let separate heads overwrite it
    recompute each head's remaining direction after shared spine contribution
    clamp eye and neck outputs, retaining locked joint poses
    rate-limit goals; recompute residual from actual scheduled output
    verify plan generations and all output ownership, then commit pose goals
    report incomplete aim without forcing unavailable joints past limits
```

对一般三维身体，方向先转换到正确参考框架，以四元数/关节轴和实际关节链进行限位与求解；不能把世界yaw/pitch直接写进侧装眼球或分叉颈。41/42的安装框架、共享骨段和DOF约束继续适用。**下面脚本只验证共同参考轴的两个角度分配，不实现通用3D IK。** 目标失配应保留误差而非声称眼已对准。

在例子的+Y前、+Z上坐标中，`yaw=atan2(dx,dy)`，`pitch=atan2(dz,sqrt(dx²+dy²))`，均转为度。距离≤`1e-8`米时拒绝方向；这是我们的数值阈值。对一个角度轴，未被锁定时：

```text
offeredTorso = desired - clamp(desired, ±(eyeLimit + neckLimit))
torsoGoal = clamp(highestPriorityOffer, ±torsoLimit)  // or reserved fixed pose
remaining = desired - torsoGoal
eyeGoal = clamp(remaining, ±eyeLimit)
neckGoal = clamp(remaining - eyeGoal, ±neckLimit)
error = desired - (torsoGoal + eyeGoal + neckGoal)
```

眼先迅速转、颈随后补角，脊柱只补二者覆盖不了的残差；并非让眼永远满偏角是唯一美术选择。需要更自然的注视舒适区时，可以增加明确的rest preference与代价求解，但它不是本轮已测试政策。躯干扭转与根朝向分开；超过可用扭转时向移动控制器提出转身请求，由它决定可否转身，注意力不直接改变导航或世界速度。

## 贯通算例：两个头看两边

自有H0请求yaw80°/pitch20°、priority100；H1请求yaw-60°/pitch-10°、priority20。H0眼yaw±25°、颈±50°；H1眼±20°、颈±35°；共享脊柱yaw±20°。两头eye pitch±15°、neck±20°，共享pitch±10°。

| 轴/头 | 分配 | 实现方向与误差 |
| --- | --- | --- |
| 共享yaw | H0需要80−(25+50)=5°；最高优先合法请求取5° | 两头共同继承5° |
| H0 yaw | 剩75°→眼25°＋颈50° | 世界80°，误差0 |
| H1 yaw | 剩-65°→眼-20°＋颈-35° | 世界-50°，还差-10°，记录AimIncomplete |
| H0 pitch | 共享0°，眼15°＋颈5° | 20°，误差0 |
| H1 pitch | 共享0°，眼-10°＋颈0° | -10°，误差0 |

H1的不完整方向不允许抢走H0已经需要的共享脊柱。若导航/支撑预约脊柱yaw=0，H0最多75°，误差5°；若攻击还把H0颈锁在20°，眼只能补25°，世界45°，误差35°。这里的攻击锁定姿态是当前合法动作所有者提供的输入，不是注意力自行改写攻击姿态。

输出再限速：眼180°/s、颈90°/s、躯干45°/s，首帧`dt=0.1s`从0出发，H0实际最多眼18°、颈9°、脊柱4.5°，世界yaw31.5°，**此帧并未达到最终80°目标**。只按理想目标求残差会误报AimComplete；提交/展示须使用实际限速后的角度。本文记录最终几何目标与首帧速率计算，未模拟任意帧数的完整物理运动。

## 自研丢失目标与换魂

自有示例的记忆窗口为0.25秒。目标最后于t=0观察到，在t=0.2可使用标为remembered的位置；t=0.4已经lost，停止为它建立新的攻击/注视授权，按自有规则回中立或选择另一个已知目标。记忆位置是最后一次观测，不是继续读取真实隐藏目标坐标。不可见与已删除分别处理；对象已销毁时稳定实体引用必须失效，不能拿复用索引追另一个目标。

```text
OnOwnAttentionInvalidation(reason):
    remove unauthorized target intents and future callbacks under their owner
    preserve last physical pose as smoothing start, not as still-valid target
    release attention-owned reservations; do not release attack-owned locks
    if body changed: rebuild stable organ/neck/spine bindings before new goals
    if soul changed: clear old soul's target permission and memory attachment
    acquire only current controller-permitted targets, or smoothly return neutral
```

bodyRevision8/soulRevision3的计划在换魂至4时失效，即使同一目标还活着、同一眼球仍存在也不能继续旧灵魂授权；肉体姿态与伤口保留。断开某头使该头和附属眼/嘴目标失效，另一头按其仍有效的绑定重新规划，共享脊柱任务也要重算。保存/加载默认重建注意力计划而非保存裸关节下标，明确保存的记忆按时间与权限验证。

## 验证、未做与风险

[检查脚本](checks/verify_creature_recipe_and_gaze_examples.py)实际运行42项全部通过；本模块20项覆盖方向计算、重合/非有限目标、双头共享分配、pitch、运动/攻击锁、重复/缺头、非法限位与锁、空目标、角速率与跨±180°、非法dt、记忆TTL和换魂/换体失效。50另有22项配方检查。[研究检查记录](evidence/creature-recipe-and-gaze-verification.json)

[静态读取入口](checks/read_creature_recipe_and_gaze_metadata.py)记录45元数据摘要、612通道覆盖和全部9个LOOKAT实例的键/偏移/context原值；没有把来源名称当运行算法。一次公开源路径404已经纠正，诊断保留在证据中，不当成成功读取。

**未做：** 未启动或附加游戏、未调用目标接口、未取得原作多头/多眼场景观察；没有重新读取眼模型或全身姿态曲线，也没有恢复原生外部目标生产者/坐标转换/凝视消费者。

**风险：** 当前阳性位全部来自手部动作，不能证明陆地眼睛的凝视机制；编辑控制器声明不能泛化为局内AI。自有两轴模型不涵盖任意安装方向、三维关节耦合或生物视觉表现，后续产品实现须使用真实自有rig并验收限位/冲突/时序。原作精确优先级、独立器官目标与丢失策略仍未回答。
