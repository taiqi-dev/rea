# 28 多动作并行：移动、技能、骨链与动作通道怎样协调

[目录](README.md) · [绑定与帧管线](03-core-structures-and-frame-pipeline.md) · [技能执行](11-action-plans-and-execution.md) · [移动与步态](26-land-approach-stopping-avoidance-and-gait.md)。限定登陆后、部落前的Creature Stage。调查锚点：**2026-10-12 14:38:19 PDT，America/Los_Angeles**。

本轮取得两包的攻击播放组与引用动画通道的实际元数据。原作动画系统支持叠层与自由度混合有开发团队来源；**两条攻击技能是否能同时执行、具体骨骼抢占、被覆盖动作是否继续产生伤害，仍未恢复。** 第1–4节列原作证据，第5节以后是用户肢体拼装／灵魂游戏的独立规格。

后续[39](39-same-role-effectors-variant-binding-and-default-mixing.md)沿本篇46份ANIM重读主次context，补左右/局部左右字段与开发团队的集合查询/变体选择说明。该续查没有恢复技能并发或本机混合消费者，不扩张本篇原验证范围。

## 1 原作：动画叠层、身体选择与技能并发不是一件事

开发团队论文§3.2.3及脚注5描述：通道可选中相同身体，控制归属细分到动画自由度；先选中者取得混合组归属，同组后续通道可按权重共同贡献。§4描述多个播放动画生成目标，与合成步态一起进入IK，再加入附属运动。§4.1.2的身体变体组可让手和对应肩一起选择；它与混合组的用途不同。[开发团队论文，PDF第5–7页](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

[论文记录](evidence/public-multi-action-paper-observations.json)保留本轮重新读取的完整相关页、摘要与事实定位。这是历史系统设计，没有逐项对齐本机执行。

| 层次 | 问题 | 当前证据 |
| --- | --- | --- |
| 技能行动 | 是否允许同时启动两个技能、怎样花资源和算伤害 | 状态接口与配置入口；实际并发政策未知 |
| 播放组TLSA | 选哪种动画、是否允许移动、优先级与混入时间 | 本轮读取指定攻击组的实际字段 |
| 动画通道ANIM | 查询哪些身体、位置／旋转／变形由哪些曲线提供 | 本轮读取指定引用动画的元数据 |
| 身体变体 | 此次是哪只手，哪些辅助部位随它一起选择 | 开发团队机制；具体本机技能选择仍未知 |
| 混合与姿态求解 | 竞争同一自由度时怎样形成最终姿态 | 历史规则与元数据；本机排序、权重和冲突执行未知 |

动画系统能同时混合几个动画，不能证明游戏允许几只手各自启动不同攻击技能。反过来，多个使用位和一个“当前攻击”字段也不能证明整只生物只能播一个动画。

## 2 原作：从技能ID追到实际移动许可与优先级

[专项读取器](checks/read_selected_action_channels.py)沿25已有四类攻击1–5级配置中的正常／冲刺动画ID，匹配TLSA播放组，再读取其引用ANIM。没有用动画文件名全盘猜技能，没有沿Building/Baby字段扩展到其他阶段。

两包各有一条TLSA资源：基础包版本7、补丁包版本10。为了定位指定ID，需要按格式完整遍历两条列表，分别经过1864／1875组；只导出每条列表中选定的13组。其余阶段只作为格式遍历经过，不分析或导出行为。播放组资源键不同，**没有证明两个列表谁被加载或怎样合并**。

| 所选播放组 | 基础／补丁`allowLocomotion` | 补丁`priorityOverride` | 其他原值 |
| --- | --- | --- | --- |
| Strike 1级，`0x044ddd75` | true / true | 1.5 | blendInTime=-1；endMode=0 |
| Strike 2–5级，`0x044ddd76`–`79` | true / true | 约1.01 | 同上 |
| Bite 1–5级，`0x044ddea6`–`aa` | true / true | 1.0 | 同上 |
| Spit，`0x044ddeaf` | false / false | 1.0 | 同上 |
| Charge rush，`0x04a3b4fb` | true / true | 1.0 | blendInTime=-1；endMode=1 |
| Charge hit，`0x04a3b511` | true / true | 1.0 | blendInTime=-1；endMode=0 |

这是读取出的**配置许可差异**，支持继续追“移动与攻击怎样协调”。还不能说打击总能一边奔跑一边命中，或喷吐一发起就强制制动：消费者、技能前后阶段、速度／站位条件与实际根运动都未知。冲撞的移动也不能自动归为普通步态。

基础TLSA v7没有序列化priorityOverride，本轮保存`null`，不拿社区对象默认值填成配置。`blendInTime=-1`不解释为负时间或瞬间切换；`endMode`的0／1不擅自命名为单次／循环。优先级1.5和1.0也未证明在所有动作之间直接按数值相比较。

补丁的Strike各级有6个choice，每个choice包含4条动画引用，涉及`hd/tl/lb/bd`标签；基础对应组只含一条引用。**列表中有4条引用不等于四只手、四条技能同时播放，或四次伤害**；choice内的组合、分支筛选与执行顺序仍需调用者。TLSA choice也不是身体variant索引。

配置与定位见[本机播放组及通道记录](evidence/local-selected-action-channels.json)。TLSA格式来自固定SporeModder-FX提交；新旧字段顺序不同，旧版不能套新版读取。[固定TLSA格式](https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/tlsa/TLSAAnimationGroup.java)

## 3 原作：攻击动画实际涉及多个身体部位

本轮读取46条ANIM资源记录：基础13、补丁33，共33个不同引用实例ID；它们的内嵌路径均标为`creature`。只解释头、通道、组件元数据，共612条通道记录，未导出曲线、像素或动画资产。路径标签用于限定候选，不证明每条资源都在当前局内执行。

### 具体例：基础`com_strike_lvl01`

有14个资源通道；下列是其中部分，组号按社区格式位段提取，不是恢复的运行占用表：

| 通道名 | 主查询cap字节 | blendGroup | variantGroup | 位置／旋转组件 |
| --- | --- | ---: | ---: | --- |
| root | root类型查询 | 1 | 0 | 两者启用 |
| head | `mout` | 3 | 0 | 两者启用 |
| R hand / R hand 2 | `skrs` | 7 | 1 | 两者启用 |
| FX R hand | `skrs` | 7 | 1 | 两者未启用；不因此判定没有事件 |
| R hand (base) / L hand | `grsp` | 8 | 0 | 两者启用 |
| R foot / L foot | `foot` | 9 / 10 | 0 | 两者启用 |

`com_bite_lvl01_a`有12个通道；head与mouthMorphs的variantGroup均为1，head与FX head的blendGroup均为3。`com_spit`也有12个通道，包含root、head、左右脚和`shoot_rng`等。**技能的动作覆盖可以超过技能提供部件**，需要同时考虑辅助姿态、脚和根；通道出现仍不证明抢占了步态。

补丁引用的`com_strike_hd_lvl01`有11个通道，另有`strike`查询cap`strk`。不能根据`hd`或“R hand”的名称直接决定实际参与者；应读取选择器和运行身体。查询结果可能零个、一个或多个，没有模型绑定就不能给出实际骨骼下标。

社区格式分开保存：主／次上下文、movementFlags、bindFlags、以及位置／旋转／局部变形组件；bindFlags的16–23位、24–31位分别被解释为blendGroup和variantGroup。组号是各资源的元数据，**相同数字不保证跨两个动画实例可以混合**。[固定通道格式](https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimationChannel.java)、[组件格式](https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimationComponentData.java)

所选基础ANIM版本为21，补丁ANIM版本为25；本轮保留原位段，不运行社区读取器的旧版本修正，因此表中的启用状态指原始组件位。社区旧版修正还涉及变形命名和部分移动标志，不能把原位段全部按新版渲染语义解释。`length`原值保留但不换算秒；关键帧范围只检查元数据指向，未完整解码曲线、事件、分支和重定位。完整来源身份见[7份ANIM格式摘要](evidence/public-action-channel-format-sources.json)及[5份TLSA格式摘要](evidence/public-tlsa-action-format-sources.json)。

## 4 原作：公开接口、本机入口与未回答问题

固定ModAPI声明的TLSA组有移动许可、优先级、混入、结束模式等；AnimatedCreature有播放／加载／循环及显式淡入时间接口。未命名float方法不当成权重或淡出函数。[TLSA声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/TLSA.h)、[播放对象](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/AnimatedCreature.h)

本机EXE重新散列与00一致；完整ASCII字面量包括：

| 字面量 | 文件偏移 | 入口性质 |
| --- | --- | --- |
| priorityOverride / blendInTime | `0x1047d48` / `0x1047d84` | 播放组参数词汇 |
| allowLocomotion | `0x1047da0` | 移动许可消费者待查 |
| DisableAnimationOverlay | `0x1069b44` | 生物公共控制候选 |
| SetAnimEventControl / SetAnimationTarget | `0x1069b5c` / `0x1069b70` | 事件／目标接入候选 |
| mInUseAbilityBits / mRechargingAbilityBits | `0x1069bec` / `0x1069c00` | 技能使用／冷却状态候选 |
| mCurrentAttackAnimId / mCurrentAttackIdx | `0x1069cc8` / `0x1069ce0` | 当前攻击状态候选 |

[27个完整本机入口](evidence/local-multi-action-entry-observations.json)和[8份固定声明](evidence/public-multi-action-contracts.json)保留来源。通用blendWeight、layer、channel、numChannels的其他命中分别邻近网格、渲染、粒子和音频，未用于动画调度结论。

| 原作问题 | 当前状态 |
| --- | --- |
| 动画可否分层，与步态合成 | 部分回答：开发团队明确机制，所选技能有移动许可差异 |
| 通道是否区分身体选择、位置、旋转和变形 | 部分回答：历史机制与本机元数据支持 |
| 本机哪些骨骼实际受哪次攻击控制 | 未回答：缺本次身体与动作的运行绑定 |
| 不同技能能否同时施放／扣资源／提交效果 | 未回答：不能从动画叠层或位集推出 |
| 同自由度的排序、权重、抢占、恢复与事件抑制 | 未回答：没有本机调用链与运行验证 |

## 5 自研核心：技能占用、姿态贡献、物理支撑分别管理

你的游戏可以允许两个肢体施放不同技能，但必须独立规定游戏行动的并发。不能只用“动画权重很低”判断技能已中断，也不能因为动作还在计时就让一只被抢占的手继续命中。

建议在11的行动实例上增加：

```text
ActionMode { movementPolicy, speedLimit, supportPolicy,
             requiredProviders[], requiredPoseQuality,
             claimsByPhase[], interruptionPolicy, effectPolicy }
BoundChannel { actionId, providerIds[], selectedNodes[],
               frame, animatedDOFs[], blendContract, curveBinding,
               dependencyRevisions }
Claim { token, ownerActionId, bodyId, controllerEpoch,
        resourceKey, accessMode, priority, phase, expiry, contract }
PoseContribution { nodeId, dof, valueOrGoal, referenceFrame,
                   ownerActionId, weight, stableOrder, compositionMode }
ConstraintFootprint { drivenEndpoints[], mutableChainSegments[],
                      sharedAncestors[], contacts[], rootRequirements }
```

资源键可以是`(partId, position)`、`(partId, rotation)`、`(partId, jawOpen)`，也可以是根移动控制、发声、瞄准稳定、支撑脚或灵魂专注。动作通道不是固定“全身／上半身／下半身”：你可能有四手、两个头、腿上分叉的手，必须由身体图查询结果建键。

逻辑层预约技能提供者和必要约束；姿态层混合曲线／目标；物理／运动主人保证碰撞、骨长和合法接触。它们可以由单一模拟线程顺序执行，不需要先做复杂多线程框架。

## 6 自研绑定：不同手也可能竞争同一肩或躯干

```text
BuildActionFootprint(plan, body):
    providers = exact stable part IDs chosen by 16
    bindings = semantic query + provider roles + shared variant selection
    for bound channel:
        record exactly animated DOFs and explicit value frame
        if endpoint IK goal:
            trace actual movable chain to configured boundary
            record shared ancestors and required contacts
    classify each influence:
        essential action control / compatible shared style / read dependency
    emit claims and constraint footprint, or explicit MissingBinding reason
```

末端位置目标不是只写手骨：IK可能调整肘、肩和躯干。两只手不一样不代表完全独立；分叉两手甚至共享同一上臂。反过来，把所有祖先直到根全部锁成Exclusive会让任何动作都只能串行。需要在动作定义里选择：固定肩以内求解、允许有限共享躯干调整，或需要独占躯干的全身动作。

共享祖先可以同时参与一个统一求解；实际可达性仍需评估。两个相反拉扯目标若无法兼得，应拒绝一个方案、修改站位或改成协同动作，不能对两套独立IK结果最后覆盖同一父骨。

### 自研占用规则

| 模式 | 适用 | 冲突处理 |
| --- | --- | --- |
| Exclusive | 一只手的必要攻击控制、根位移请求、持续发声 | 同键不共存；排队、拒绝、改选提供者或显式抢占 |
| Blend | 同一目的的目标过渡，例如同动作从外部目标到身体目标 | 只有显式兼容契约相同才共享；组号相同不够 |
| Additive | 躯干小幅反冲、呼吸、表情等增量 | 限定参考框架、组合顺序和总预算；不能破坏必要动作与接触 |
| ProtectedContact | 当前仍承担支撑的脚位置等硬要求 | 攻击不能直接覆盖；先申请支撑转换，或进入明确的跌落／击退模式 |

位置与旋转可分别拥有，但不保证机械上独立。例如手腕旋转影响武器接触、足部转向影响接地，必须在动作可达／姿态质量检查里体现，不能只靠DOF键判断成功。

### 原子预约与抢占

```text
TryReserve(plan):
    validate current body/control/ability/route revisions
    compute all conflicting claims and resource costs
    if conflict cannot be preempted: return Conflict(keys, owners, phase)
    if costs or additive budgets fail: return Rejected(reasons)
    # 在此之前，不取消旧动作，也不留下半套新预约。
    within one authoritative transaction:
        recheck owners and versions
        cancel allowed victim actions using their original tokens
        reserve all new claims and costs, or roll back transaction
    return Reserved(actionId, tokens)
```

优先级只是规则输入。高优先级不能不顾动作“不可中断的有效点”或非法资源状态强行施放；若必须受击打断，可将受击作为明确终止政策。排队带截止时间与依赖快照，到时重新选部件；不无限等待一个已断的手。抢占释放旧令牌，晚到的旧清理不得释放新主人。

## 7 自研边走边攻击：根运动、脚目标与攻击目标的合成

移动许可分四种候选：Allowed、SpeedLimited、MustStop、RootOwnedByAction。普通挥手可以Allowed，重型瞄准可SpeedLimited，双手仪式可MustStop，冲撞／跃击可RootOwnedByAction。这是自研动作定义，不把上面的Spore布尔值直接扩成四种政策。

根平移由一个运动主人执行；攻击若要改变根运动，先改变移动请求或获取明确根运动权限。不让导航和攻击动画各自推动角色一次。身体视觉反冲可叠加局部姿态，但不能偷偷改变碰撞体位置。

```text
TickActor(dt):
    resolve action transitions, claims and movement policy
    motion = integrate one authorized root request with collisions
    gaitGoals = update gait from achieved motion, yaw and current support set
    actionGoals = sample each active bound action on its own timeline
    semanticGoals = specialize into compatible world/local goal frames
    composedGoals = arbitrate and blend by DOF and explicit contracts
    constraints = add bone lengths, joint limits and current legal contacts
    pose = solve one shared body graph(composedGoals, constraints)
    quality = check essential action goals and support residuals
    authorize/cancel/fail effect windows according to action policy and quality
    produce final skin transforms and allowed secondary motion
    record contributors, blocked DOFs, residuals and result reasons
```

走路时脚锚点在世界中，攻击手的目标可随敌人变化，躯干同时支持二者。目标先统一参考框架，不能把世界位置和肩局部偏移直接平均。26的实际移动速度继续驱动步态；攻击减速后，六足相位连续调整，不因新动画开始就把所有脚重置为同一相位。

自研例：六足实际速度1.2米／秒、周期位移0.6米时步频2Hz；移动施法限速0.6米／秒后变1Hz；被堵住且没有转向时进入Settling。手的0.4秒攻击时间线可以独立前进，是否仍合法出手由具体技能决定，而不是跟脚周期共用时间。

### 用一只脚攻击

脚有Foot标签也不表示随时可踢。先从支撑集合移出它，再生成攻击轨迹：

1. 预测剩余接触与动作期间的身体负担。失败则等待、安排补充落脚、降低速度或换另一种动作。
2. 在合法转换时释放该脚的接地锚点控制，交给攻击行动；其他脚继续维护锚点。
3. 攻击结束后规划可达落脚点并确认接触，再回到步态；不瞬移回旧位置。

教学采用平地准静态支撑凸包，质心投影距边至少0.1米。仅有三脚支撑时抬起其中一只，剩两脚不能满足本规则。先停稳使六脚接地，再用一脚踢击，剩五脚可能合格。奔跑惯性、跃击、墙面接触和外力不能靠此静态模型保证，需要产品物理契约。

## 8 自研姿态混合：权重解决过渡，不解决技能资格

本候选扩展03的自由度混合：先去掉零权重贡献，再按优先级与稳定次序确定赢家组，只混合同优先级且显式兼容的贡献。基准姿态用剩余影响平滑承接；不能让低优先级控制同一必需攻击自由度。

```text
BlendPosition(base, contributions):
    reject nonfinite or negative weights with channel/action identity
    active = contributions whose weight > 0
    if none: return base with explicit BasePose reason
    winner = first in descending priority, ascending stableOrder
    group = active with winner.priority and winner.compatibilityContract
    W = sum(weights); target = sum(weight*compatiblePosition)/W
    alpha = min(1, W)
    return (1-alpha)*base + alpha*target
```

独立演算：同组位置目标`(1,0)`与`(0,1)`，权重0.6／0.4，结果`(0.6,0.4)`。单目标`(2,0)`权重0.25，从基准`(0,0)`得到`(0.5,0)`。权重为0的高优先级通道不会抢占所有权；不兼容的两个攻击目标不因为都有权重就自动平均。

旋转采用单位四元数、同半球修正和确定次序的球面插值；`q`和`-q`代表同一旋转，不能平均成零。自研同轴60°与120°等权得到90°。多目标旋转需要明确定义次序或旋转均值，不宣称普通分量平均足够。

Additive旋转使用相对于指定参考姿态的增量，顺序确定且有幅度预算。例：右手挥击要求躯干+8°，后手防护要求−6°，若声明为兼容小幅增量，可以形成约+2°的同轴示例；预算按绝对需求8+6=14°计算，不因正负抵消就认为没有负担。预算上限15°时再加2°需求要拒绝或显式降级，不能静默截断必要攻击目标。

跨动画的“group7”需附带动作语义、目标关系与参考框架。来源不同而编号相同，默认不兼容。纯表现淡出可留在冻结／受限姿态贡献中，但玩法行动已取消就不能继续产生效果；淡出不应继续占着已交给新动作的必要通道。

## 9 自研完整并行例：六足移动、右前手攻击、左后手防护

身体有四手六足；灵魂能量40。行动A右前手斩击需预约10，行动B左后手护盾需预约15；A效果时点0.4秒，B效果时点0.15秒。躯干采用上面的兼容增量契约。所有数值和时间为自研构造。

| 时刻 | 请求／状态 | 协调结果 |
| --- | --- | --- |
| t=0 | 以1.2米／秒移动；启动A与B | RF攻击控制、LB防护控制分别预约；躯干增量需求14°≤15°。六足步频2Hz，两动作各有时间线 |
| t=0.1 | 左前手又请求成本20的法术 | 肢体虽然空闲，剩余可用能量40−10−15=15；拒绝InsufficientEnergy，不能只查骨骼 |
| t=0.15 | B有效点 | 验证控制、部件与效果条件，扣15，提交一次世界护盾；A的10仍预约 |
| t=0.2 | 受击进入本例可抢占两臂的踉跄 | 取消A未提交效果并释放10；终止B动作剩余姿态；已提交护盾由自己的世界生命周期继续。根运动和支撑转入受击政策 |
| t=0.4 | A旧动画回调到达 | ActionInactive，不能扣伤害或重扣能量；旧释放令牌不触及新动作 |
| t=0.6 | 踉跄结束 | 从实际当前姿态平滑恢复，重新验证瞄准与运动；不是瞬间回参考姿态，也不自动续接A的前摇 |
| t=0.8 | 前左脚想踢击，但目前只有三只脚支撑 | 剩两脚违反本例支撑契约；安排减速停稳和额外落脚，暂不释放该脚接触 |
| t=1.0 | 六脚已接地，且准静态支撑检查合格 | 转移前左脚给踢击，剩五脚保持接触；踢击结束后落脚确认再回步态 |

如果A与B都要求独占躯干yaw，即使不同手也必须拒绝、排队或改选执行模式。若第三法术成本只有10且不竞争必要自由度／专注资源，可以允许；若灵魂同时施法要专注，也应预约该资源，不能假设“灵魂技能不动身体就无限并发”。

右手断裂只取消依赖右手的行动；左后手或左脚动作仍需复核质量，但不无条件终止。失去手可能改变质心和支撑，需重新评估共享约束。换肉体时按16／27更换控制代次，旧动作不自动转移到新身体，已提交效果仍归原效果主人。

## 10 自研效果、中断与诊断

动画权重与行动状态分别存。一个被姿态覆盖的动作，按声明选择Cancel、PauseBeforeCommit或ContinueCosmeticOnly；暂停若允许，需有超时和恢复重验证。纯意识技能可以无实体手，但必要的发射／瞄准或灵魂资源仍按技能政策检查。

本例A被踉跄取消，不能从隐藏曲线事件再提交；B护盾已经存在，终止身体动画不回滚护盾。攻击因不可达或姿态残差过大失效时，按25／11的效果与消耗政策结算，不用“看起来挥了”认定命中。多个通道触发同一个窗口按`(actionId, effectOrdinal)`去重；明确双击才有两个ordinal。

诊断至少记录：动作与提供者、通道选中节点、每DOF赢家／参与者、兼容契约、权重、共享骨链、支撑转移、资源预约、抢占原因、姿态残差、提交／跳过事件及body/control版本。失败保留ChannelConflict、SharedAncestorConflict、SupportUnsafe、PoseNotAchieved、DependencyLost等具体原因。

## 11 验证、未做和剩余风险

[读取器检查](checks/verify_action_channel_reader.py)覆盖TLSA v7–10、缺省保留、布尔／浮点／截断／计数错误、ANIM指针范围、组件与组位段、所选移动许可差异及补丁引用变化。[独立并行检查](checks/verify_parallel_action_examples.py)覆盖不同肢体／DOF、共享祖先冲突、原子失败、抢占、资源不足、旧令牌、重复事件、混合与旋转、踢击支撑转换。[本轮验证记录](evidence/parallel-action-verification.json)保留实际结果与覆盖。

未做：没有启动／附加游戏、运行真实边走边攻击、恢复本机混合器与技能调度调用链、完整曲线／事件／分支解码，或实施用户游戏。没有修改生产代码，因此未跑仓库生产构建；专项检查不证明原作行为。REA/provider阻塞沿用既有记录，未重复安装或改配置。

风险：所选TLSA的实际加载／合并未知，通道旧版本修正未应用，历史设计与本机运行尚未对齐。自研共享骨链、多约束IK、复杂地形与受击动力学需要在产品中验证；当前教学支撑模型只适用于平地准静态情境。

下一步原作验证应固定同一身体与技能，分别移动施放打击／咬击／喷吐，记录移动请求、实际速度、播放实例、绑定结果、通道权重、脚接触及效果事件；再在两技能请求重叠和受击时比较中断。只有画面重叠，无法确认两个技能同时处于有效状态。
