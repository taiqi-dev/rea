# 26 陆地移动：接近、停靠、避让与多足步态

[目录](README.md) · [步态](04-gait-synthesis-and-foot-targets.md) · [攻击可达与命中](25-body-reach-attack-ranges-and-hit-resolution.md) · [群体协作](21-pack-coordination-and-shared-intents.md)。只研究登陆后、部落前的生物阶段及对应身体编辑。锚点：2026-10-12 02:18:33 PDT。

**原作能确认移动入口有两项停距、对象另有占地信息，步态按速度插值；本机还取得了停止、加减速及步态资源的配置值。** 身体变宽是否改变原作寻路、攻击前怎样计算停点、避让选何种算法、实际速度如何传进步态，仍没有恢复调用链。第1–4节是原作资料与未知，第5节起全部是我们自己的设计候选。

## 1 证据覆盖与职责

| 用户问题 | 当前原作证据 | 仍缺什么 |
| --- | --- | --- |
| 身体变宽影响通行吗 | SDK占地/包围半径；本机同名空间数据、障碍管理词；actor命令有使用足迹半径/目标宽度的选项 | Creature自然移动的读取者、导航形状与编辑重建关系 |
| 攻击前停在哪里 | WalkTo目标位置与两项停距；能力范围配置；Avatar GoalStopDistance实值 | 从技能、双方形态到目标位置/停距的函数 |
| 其他生物怎样避让 | 邻居检查半径、容器、速度与转向入口；本机对应词汇 | 邻居更新、局部预测、绕行/让路和堵塞处理 |
| 速度怎样接多足步态 | 开发团队论文的速度插值；本机GAIT速度键、步长、触发偏移、着地比例 | 速度量的来源、单位/归一化、步频公式与停步处理 |

EXE身份仍为 `SporeBin/SporeApp.exe`，20,626,168 bytes，SHA256 `f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d`。两份选定DBPF的SHA与25一致，本轮重新散列并核对索引跨度。原生provider仍不可用；本轮数据均为普通只读调查，**不是 REA Evidence 或游戏运行观察**。

## 2 移动入口：目标、停止距离、速度与邻居

社区声明固定提交 `2d71289adc71aa5c58f4516c6c835c99f5f9ca19`，本轮再次校验三个头文件的原始字节摘要。

| 声明 | 位置 | 能说明什么 |
| --- | --- | --- |
| `cCreatureBase.WalkTo` | 119行 | 接收速度状态、目标位置、另一个向量，以及goalStopDistance/acceptableStopDistance两项参数 |
| 创建移动策略 | cCreatureBase 216行 | 移动有策略入口；未恢复具体策略 |
| 移动请求中的目标与两项停距 | cLocomotiveObject 28–37行 | 目标停距是请求数据，未说明容差比较式 |
| 期望/标准速度接口 | cLocomotiveObject 64–66行 | 两种速度概念分别存在 |
| 移动、停止、清理邻居 | cLocomotiveObject 75–84行 | 有移动生命周期与邻居维护入口 |
| 速度、角速度、转向、邻居数据 | cLocomotiveObject 99–104、124–127行 | 提供局部运动研究入口，未证明具体避让算法 |
| 位置、尺度、包围与占地半径 | cSpatialObject 67–72、89–93、124–133行 | 几何信息与请求停距分别声明，计算关系未知 |

[生物入口](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCreatureBase.h)、[移动对象](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cLocomotiveObject.h)、[空间对象](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cSpatialObject.h)。摘要与完整读取范围见[来源记录](evidence/public-land-motion-entry-observations.json)。

WalkTo默认停距1和2只是社区声明里的默认参数，未确认单位，更不能理解成“距目标中心1就停、距2继续走”。NeighborCheckRadius注释的20也不是已读取的游戏值；邻居容器模板参数128不能直接认定为游戏硬上限。MoveTo末尾bool的注释带问号、来自车辆试验，不套给陆地动物。

### 本机线索与必须排除的误读

限定`.rdata/.data`的完整ASCII NUL词查询发现：`mDesiredSpeed/mStandardSpeed/mNeighborCheckRadius`位于同一小邻域；`mFootprintRadius/mBoundingRadius`位于一般空间数据邻域；步态另有`steplength/stepheight/speedi/gaitgroupkey`。记录包含实际PE节表、文件偏移和首选数据VA，**不是函数地址或SDK字段偏移**。[本机记录](evidence/local-land-motion-entry-observations.json)

actor移动命令帮助包含可选stopDistance、使用actor足迹半径及目标最大宽度作为偏移乘数的选项。这说明这些概念存在于命令接口，但没有证明普通Creature玩家/NPC采用它，也未说明停距是否相加。

`Simulator/AStar`只是候选词汇，未找到调用者，因此不宣称Creature采用A*或它负责避让。载具状态文案和含城市、武器、货物的`mAcceptableMinDist/mAcceptableMaxDist`邻域明确排除。`mNeighbors`仅是完整字符串`aDmNeighbors`的后缀，不计为完整字面量命中。目标停距相关完整字面量未在该ASCII覆盖中匹配，也不代表功能不存在。

## 3 本机移动调参的实值

所选`CreatureGameTuning`有四个不同组变体，两包各四项，共八项PROP。中央组ID为`0xad56080c`，与注册名CreatureGame的FNV-1对应；中央变体249个属性已完整解析，只导出当前研究需要的字段。其他变体保留组键和父引用，不猜成幼体、Epic或难度档。[配置记录](evidence/local-selected-movement-resources.json)

| 中央变体属性 | 原始数值，便于阅读四舍五入 |
| --- | ---: |
| creatureAvatarGoalStopDistance | 0.4 |
| creatureMouseMoveGoalDistance | 10 |
| creatureMouseMoveMinRadius | 0.5 |
| creatureAvatarMinMouseRadius / MaxMouseRadius | 0.2 / 10 |
| creatureAvatarWASDTurningSpeed / SlowTurningSpeed | 10 / 4 |
| creatureAccelerationSpeedMultiplier | 1 |
| creatureDecelerationSpeedMultiplier | 2 |
| creatureBaseAcceleration / BaseDeceleration | 0 / 0 |

这些值在两包对应记录的所选字段一致。它们仍是配置原值，**不是米、秒或已恢复的运算公式**。Avatar停距不能代替NPC攻击停距，鼠标目标距离也不能直接代替目标表面间距。BaseAcceleration=0不意味着“生物瞬间达到最大速度”，因为尚未找到默认值、乘数及最终求值路径。

注册表有globalCreatureSpeedGear0–5、SprintSpeedBoost、GaitBlendTime、PolypodGaitStyle、GaitIsWalkingThreshold等名字，但未直接写入此次选定的PROP；不补造默认值。[公开注册与上下文](evidence/public-land-movement-registry.json)

本轮名称清单还定位到`CreatureTuning`的不同类型资源，只核对压缩后头部，未解释其内部结构；它不是上述PROP，不使用PROP解析器强行读取。GAIT按自己的格式读取。公开注册表混有其他阶段和其他游戏的项目，载具、水中、Darkspore等候选没有用于本轮行为结论。

## 4 速度与多足步态：公开设计和本机参数

开发团队论文§4.2（物理PDF第6–7页）说明：按近似腿长分组，以小整数比协调周期；触发偏移与着地比例组织脚循环；移动速度在针对不同速度制作的参数组间插值；每组1–6只脚使用动画师配置，7只以上程序生成。这个数量是**组内脚数**，不是腿对数。[开发团队论文](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

论文没有说移动速度等于SDK的DesiredSpeed或StandardSpeed，也没有给本机完整速度转换公式。身体实际推进、期望速度、动画节奏因此不能只凭名称合并。

### 4.1 本机GAIT记录

两包各读取`gait0..6`七项，共14项。依据固定SporeModder-FX提交`a482c51d8d37fc8cf416acecc3c00a5b0723f2e5`的GAIT格式，检查魔数、版本11、文件长度、变长数量、键值有限性及逐记录跨度。只导出步态参数与曲线计数，没有导出或复用原作路径曲线。[格式来源](evidence/public-gait-format-sources.json)、[选定资源清单](evidence/local-movement-resource-inventory.json)

| 数据 | 本机读到的结构 | 不可自动推出 |
| --- | --- | --- |
| StepLengthKey | speedi、stepLength | speedi的单位；步长是否还乘腿长/体型 |
| GaitGroupKey | speedi、stepHeight、taxon、着地比例、触发偏移、身体摆动/姿态参数 | 配置槽映射到哪条实际腿 |
| 路径数据 | 位置、旋转、弯曲键的计数与跨度 | 原作逐帧求值及混合顺序 |

以两包一致的`gait6`所选参数为例：

| speedi | 0 | 2.5 | 4 | 5.5 | 6.5 | 7.5 | 8.5 | 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| stepLength，约值 | 0.7 | 0.75 | 0.75 | 0.85 | 0.9 | 1 | 0.85 | 0.9 |

八个group键各有六个触发/着地槽和六条路径；速度键还会改变这些槽的时序：

| speedi | 六个触发偏移，约值 | 每槽着地比例 |
| --- | --- | --- |
| 0、2.5、4 | `[0,0.5,0.3333,0.8333,0.6666,0.1666]` | 0.5 |
| 5.5 | `[0,0.5,0.33,0.83,0.66,0.16]` | 0.5 |
| 6.5 | 同5.5 | 0.4 |
| 7.5 | 同5.5 | 0.5 |
| 8.5、10 | `[0.65,0.6,0.55,0.5,0,0.05]` | 0.4 |

因此速度适配包含**步长、触发偏移与接地时段的变化**，不只是统一加快循环。接地比例也不是严格单调曲线，不主动整理成另一套参数。它不等于04中的自研六足交替三脚示例；这里仍未把槽0–5映射成左前、右中等具体腿。

步长并不随speedi严格单调增加，所以“速度加倍就只把每只脚动作加倍”不能完整描述这些配置。若仅做**参数演算**：假定按相邻键线性插值，speedi=4.75位于4与5.5之间，stepLength约为0.8。论文支持速度插值概念；本机读取者是否线性、如何夹取越界仍未知，这个演算不是恢复代码。

另一个可确认的资源差异：基础包`gait2`有八个速度/步长键，补丁包有十个，额外speedi=11.5与12，stepLength约1.2与1.5。两包分开保留，尚未确认实际加载优先级；不能据此宣称本机一定用了新增高速段。

`gait0`的taxon为0，但仍有两个触发/着地槽、路径数0；不能仅按文件名恢复“无脚爬行”的实现。

### 4.2 格式调查中的差异

社区读取器要求每个样条参数末尾的四字节为`0xcdcdcdcd`；基础包实际还有0、`0xffffffff`等不同值，补丁包所选非零脚数资源在该位置均为`0xcdcdcdcd`。其用途未知。独立读取器将该槽保留为**不解释的uint32分布**，不把它当必须满足的语义常量，也不把原值改写成社区值。其余字段的结构、跨度、完整消费与数值检查分别保留。不能声称严格原样运行社区解析器已成功或两包所有曲线等价。

## 5 自研结构：身体通行、攻击站位与步态各自负责什么

本节起是面向肢体拼装游戏的**独立设计候选**，未在用户产品中实施。

```text
BodyMotionProfile {
    bodyId, geometryVersion, mobilityVersion
    rigidCoreShape, rigidParts[], permittedFoldModes[]
    navigationShapeByMode, collisionShapeByMode
    maxSpeed, acceleration, braking, yawRate, canStrafe
    supportFeet[], reachProfiles[]
}
MoveRequest {
    requestId, soulId, controlGeneration, targetId
    arrivalPolicy, attackPlan, movementMode
    preferredPose, hardValidRegion, settleRegion
    bodyVersions, targetGeometryVersion
}
MotionSample {
    achievedSelfPropelledVelocityRelativeToGround
    achievedYawRate, displacement, dt, obstructionResult
}
```

身体宽度通过真实需要通行的形状影响路线与避让；攻击可达通过25中的执行部件影响站位；有效脚列表影响步态。三个变化可以发生在同一次重建中，但没有一个“全用途radius”能替代全部规则。柔软/可折叠附属肢体若允许收起，需要明确姿态模式及碰撞变化，不能只在寻路时忽略而让实际碰撞卡住。

## 6 身体变宽怎样影响通行

圆形代理的简化平面条件是`通道宽度 >= 2×代理半径 + 2×边缘余量`。它容易实现，但细长身体的外接圆会过度保守。若采用带方向的矩形/胶囊体，需要检查沿路线的旋转扫掠；不能只验证起点和终点。

矩形教学模型中，身体宽w、长l，纵轴相对通道方向偏转θ，横向投影宽度：

```text
Wprojected(θ) = w*abs(cos θ) + l*abs(sin θ)
fits = Wprojected(θ) + 2*clearance <= passageWidth
```

例：通道宽1.2 m、两侧各留0.1 m；身体原宽0.8 m、长1.6 m，正向通行需1.0 m，可以通过。变宽到1.4 m后需1.6 m，不能通过；改走宽1.8 m的路线。旧身体在窄道内转30°也需约1.693 m，因此“正向能通过”不等于“里面能自由转身”。这是构造几何，与Spore通行政策无关。

```text
OnGeometryCommitted(bodyChange):
    RebuildAffectedMotionAndReachProfiles(bodyChange)
    InvalidateRoutesUsingOldNavigationShape(bodyChange)
    ReleaseOldPassageAndAttackSlotReservations(bodyChange)
    InvalidateOldBodyBoundActions(bodyChange)
    RequestRouteOrNewCombatPlan(BodyChanged)
```

若允许在局内现场变宽，变形提交前检查新碰撞形状能否合法放置；本候选默认拒绝无法放置的主动变形。强制换体需另有显式PlacementRequired/NoValidPlacement结果和恢复政策，不能先重叠墙体再假装路线仍可走。编辑器中变宽后再进入场景，也要按新尺寸查询合法落位。

## 7 攻击前停在哪：可行站位区域，不能只追目标中心

攻击站位是多个约束的交集：身体不重叠、执行肢体可达、技能范围/方向合法、目标可见或射线合法、可抵达、有稳定支撑，以及群体站位不冲突。

```text
GenerateAttackArrival(plan, body, target):
    candidateRootPoses = SampleTargetRingAndFacings(target, plan.mode)
    for pose in candidateRootPoses:
        if !LegalBodyPlacement(body, pose): reject Collision
        if !AuthoritativeReachRule(plan, pose, target): reject OutOfReach
        if !RequiredSightOrShotPath(plan, pose, target): reject Occluded
        route = FindRoute(body.navigationMode, pose)
        if route.failed: reject NoRoute
        if !CanReserveNeededCombatSlot(pose, plan): reject Occupied
        score = travelTime + exposureCost + turningCost + crowdCost
        emit {pose, hardValidRegion, settleRegion, score}
    return lowestCostFeasiblePose or Unavailable(reasonCounts)
```

简单圆形算例：己方碰撞半径0.7 m、目标0.5 m、身体安全余量0.15 m，中心距至少1.35 m。假设该动作的肢体根位于身体中心、最大物理触达1.4 m、目标受击球0.5 m，则最远中心距1.9 m。暂不计关节方向和其他障碍，合法站位带为`[1.35,1.9]`，选1.7 m作期望位置。法术、冲刺、不同手臂各有自己的区域，不能共用这一带。

本候选进入停靠状态需：中心距在`[1.6,1.8]`、实际平面速度≤0.1 m/s、朝向及支撑满足要求并持续0.15 s。进入后，只要仍在更宽的硬合法带内就保持；走出硬合法带或目标/部件失效才重新接近。这样不会因为测量在边界附近抖动而走一步、停一步。

保持的是停靠意图；是否允许发动技能仍持续检查低速度、朝向与支撑。已经到达后被推得移动或丢失支撑，应返回Settling/中断结果，不把旧Arrived标志当永久攻击资格。

这是**自己的到达容差与滞回政策**，不把SDK的两个StopDistance强行解释为同样含义。攻击启动与25的有效点重查仍分开；“刚刚到达”不保证前摇后仍命中。

### 7.1 减速应看剩余路径与制动能力

连续一维、固定制动能力的教学下界为`d_brake=v²/(2a)`；加上控制响应延迟τ，预留`vτ`。这里v取朝停点的有效接近速度，a是正的制动能力，不是某个原作配置名。

```text
s = remainingDistanceAlongFeasibleRouteToPreferredPose
v_stop_limit = max(0, sqrt((a*τ)^2 + 2*a*max(0,s)) - a*τ)
v_preferred = min(body.maxSpeed, routeSpeedLimit, v_stop_limit)
```

例：a=2 m/s²、τ=0.1 s、距离期望点剩0.3 m，速度上限约0.914 m/s；剩0.1 m时约0.463 m/s。以2 m/s接近时需预留约1.2 m，而不是冲到1.7 m才瞬间清零。实际控制还受转弯、碰撞、坡度和离散步进限制，路径弧长与目标中心欧氏距离不能随意互换。

## 8 局部避让：先预测碰撞，再决定绕行或等待

独立候选使用有限速度采样，便于先做可诊断实现；**不称原作使用它，也不声称等价于ORCA**。

对圆形教学代理，p为“邻居位置−己方位置”，相对速度u为“邻居速度−候选己方速度”，预测窗口T内最近时刻：

```text
tClosest = clamp(-dot(p,u)/dot(u,u), 0, T)  # u≈0时取0
closestDistance = length(p + u*tClosest)
reject if closestDistance < selfRadius + otherRadius + pairClearance
```

非圆形身体还需姿态与扫掠碰撞查询；加速度/转向受限时，预测只作候选预筛，最终碰撞控制器检查实际本步运动。邻居检索应覆盖预测窗口内双方扫掠范围，身体变宽后也要更新；不能沿用过小缓存而漏掉大身体。

```text
ChooseLocalVelocity(request, body, route, neighbors, dt):
    preferred = RouteVelocityWithStoppingLimit(request, body, route)
    candidates = AllowedVelocityAndTurnSamples(body, preferred, dt)
    for v in candidates:                 # 包括减速/等待候选
        if !AccelerationAndTurnFeasible(v): reject Dynamics
        if !SweptBodyPlacementLegal(v): reject StaticObstacle
        if PredictedNeighborOverlap(v): reject PredictedCollision
        if !KeepsWithinRequiredRouteOrArrivalRegion(v): reject InvalidRegion
        score = distanceToPreferredVelocity + goalDelay + sideSwitchPenalty
        emit v, score
    if no feasible candidate: return Blocked(NoSafeLocalMotion)
    return lowestScoreCandidate
```

相向算例：初始相距4 m，双方半径0.6 m，余量0.1 m，双方以1 m/s迎面走。相对速度大小2 m/s，在2 s预测窗内最近距离为0，拒绝继续迎头走；首次进入1.3 m安全间距约在1.35 s。不能只因现在相距4 m就判断安全。

宽道可选侧向速度，是否能侧移由肉体运动模式决定；不能给只会向前走的身体瞬间横移。窄道若容不下两者，局部绕行无解：使用通道预约、稳定让路侧或退到等待点。优先权可结合等待时长和稳定身份，预约带到期与退出释放；等待时间过长返回Stalled并触发重规划/灵魂改策。单纯给两者同一排斥力容易永久僵住，或每帧反复换边。

宽1.8 m的替代通道能容一个宽1.4 m生物加余量，容不下两个并排；因此本例按单通道预约运行。群体共享任务只提出目标，21中的每个成员仍要自己评估路线、占地和技能站位。

## 9 实际移动速度怎样接多足步态

本候选中导航/碰撞控制器负责身体根运动，步态跟随已经实现的运动。输入不是“想跑多快”：被墙挡住时DesiredSpeed仍可能很大，但实际自推进速度为零。

```text
TickCreature(dt):
    request = SoulAndActionOwner.CurrentMoveRequest()
    profile = CurrentBodyMotionProfile()
    route = CurrentOrReplannedRoute(request, profile)
    choice = ChooseLocalVelocity(request, profile, route, QueryNeighbors(), dt)
    motion = IntegrateAndCollideRoot(choice, profile, dt)
    sample = MeasureAchievedSelfMotionRelativeToSupportingGround(motion)
    gaitTargets = AdvanceGaitUsingAchievedMotion(sample, profile.supportFeet, dt)
    pose = SolvePose(gaitTargets, CurrentBoundActionTargets())
    RenderOwnSkinAndParts(pose)
    UpdateArrivalAndBlockedState(request, sample, pose)
```

平台运动、被击退或脚离地应记录运动原因与支撑状态，切换相应表现；不能把外力搬运速度当成主动奔跑速度。平地刚体近似下，髋i的速度为`v_i=v_root+ω×r_i`，原地转弯也产生髋运动。身体变宽使r_i变化，因此同样角速度下外侧脚所需位移变大，即使中心线速度为零。

本示例把s定义为**一整周期的根位移距离**，平移时频率`f=|v|/s`，组间仍使用04的共享时钟与频率比；每脚落点另看其髋速度和可达限制。它不是恢复的Spore步频公式。

```text
group.phaseCycles += chosenBaseFrequency(achievedMotion, yaw, stride) * dt
for foot in group:
    process all crossed lift/touch boundaries in time order
    if Stance: keep world contact anchor; derive local target from new root
    if Swing: predict root and rotation at touchdown; plan reachable ground point
```

构造例：六足、s=0.6 m/cycle。实际速度1.2 m/s时f=2 Hz；避让后降至0.6 m/s时f=1 Hz；撞墙使实际速度0且无转向时，不应继续以2 Hz原地跑。若参考着地比例β=0.65，则1.2 m/s时支撑期0.325 s，身体前进0.39 m，支撑脚相对身体相应后移；不能让脚随根一起平移导致滑步。

原地转弯ω=1 rad/s、髋偏移0.4 m时，该髋速度0.4 m/s；若变宽后偏移0.7 m，则为0.7 m/s。这里只说明局部目标需要变化，不意味着所有脚必须用各自独立时钟。长短腿组仍需协调，组内短脚可达失败时记录NoReachableFootPlant，不能无限拉长腿。

### 停步和速度切换

减速时保持连续相位、对步长/姿态参数平滑过渡；循环偏移用圆周插值或保持配置身份，不能把0.95到0.05按普通浮点中点插成0.5。停步进入Settling，已腾空的脚用独立的收脚时间完成合法接地，不把共享时钟立即置零然后冻结半空。全脚接地/合法支撑后进入Standing；必要的调整步仍可显式启动。

若前方堵住，只停平移而仍在转向，应继续为转向规划足部；若速度超出脚的可达步长/频率范围，则显式降低可实现移动速度或返回MobilityLimited。脚数变化需要重新协调分组、相位与接地锚点，不能把数组旧下标当稳定脚身份。

## 10 贯通例子与失效处理

1. 原宽0.8 m的六足肉体选择1.2 m窄道。变宽到1.4 m后，旧路线与通道预约失效，改走1.8 m替代通道；无法找到替代路线则向灵魂返回NoRouteForBody。
2. 替代通道里发现迎面同伴。预测拒绝对撞，单通道预约安排一个等待，实际速度从1.2降到0.6再到0；六足节奏对应2 Hz、1 Hz、Settling，原地转弯仍另处理。
3. 接近敌人时，用已选手臂的可达域与双方不重叠条件生成合法中心距带`[1.35,1.9]`，目标为1.7 m；按剩余路径与制动能力减速。
4. 位置、速度、朝向与支撑连续满足到达条件才发起手击。敌人前摇中移出范围，25的有效点重查判Miss，随后重新选站位或换技能。
5. 断腿会改变支撑与移动能力，断攻击手会改变合法站位带；两者都使相关旧计划失效，但不应重置灵魂人格或其他未依赖部件的技能。

每步分别保存RouteBlocked、Yielding、Braking、Settling、Arrived、Miss或BodyChanged等原因。不要把所有“没前进”都当AI没选目标，也不要让导航失败静默变成无限原地步态。

## 11 验证与尚未回答的原作问题

后续[31](31-terrain-contact-foot-locking-and-support.md)补实际根运动之后的地形查询、锁脚、台阶净空与停步落脚；[33](33-shape-revisions-collision-hit-and-ai-sync.md)补造型后的占地/命中版本同步。原作具体函数链仍未知，新增数学与状态规则属于自研。

| 最小原作验证场景，尚未执行 | 需要记录 | 能区分的候选 |
| --- | --- | --- |
| 同技能形态逐步加宽，经过同一通道 | 实测碰撞/占地、目标轨迹、方向与失败点 | 固定导航半径、随形态代理、碰撞后绕行等；视觉宽度不是测量结果 |
| 同目标改变双方体型与手长 | 启动移动、停点、能力启动、有效命中位置 | 中心停距、表面停距、部件可达与固定技能范围 |
| 两个同伴相向进窄道 | 邻居集合、期望/实际速度、优先权、等待和恢复 | 预测避让、碰撞推开、预约/让路等 |
| 加速、减速、撞墙及原地转弯 | 根位移、角速度、足部相位/接触、参数键 | 请求速度与实际速度驱动、停步相位政策 |

本轮读取[22条选定资源](evidence/local-selected-movement-resources.json)；[读取器6项检查](checks/verify_movement_reader.py)验证格式边界、未知槽保留和本机差异；[独立运动算例检查](checks/verify_land_motion_examples.py)核对通行、制动、碰撞预测、停靠滞回与步态连接。检查详情见[本轮验证](evidence/land-motion-verification.json)，不代表原作行为或用户游戏上线验证。

未做：原生调用链恢复、启动/附加游戏、真实通道/停距/脚滑测量、其他阶段调查、用户产品实现和仓库生产构建。保持静态调查，游戏不用开着。

风险：原作导航半径、停距函数、避让算法和速度到步态的传递点仍未知；社区ABI与当前EXE未对齐，GAIT有不解释字段。自研的圆形预测与有限采样只是可诊断起点，复杂地形、拥堵和可折叠肢体需要产品实现与场景验证。
