# 25 体型、技能距离、肢体可达与实际命中

[目录](README.md) · [行动执行](11-action-plans-and-execution.md) · [灵魂联合决策](16-soul-ai-body-assessment.md) · [续查清单](24-next-land-mechanism-investigations.md)。范围仍是登陆后的 Creature Stage 和对应编辑器。研究锚点：2026-10-12 01:36:27 PDT。

**这次取得了实际技能配置，但没有恢复原作的命中公式。** 本机两份游戏包中的四类攻击模板和等级记录已局部解码；开发团队论文可以解释动作怎样适配身体。两者之间的距离修正、选哪只手、动画事件何时提交伤害，仍缺少本机调用证据。下面先列原作资料，再给适合肢体拼装与灵魂 AI 的独立规格。

## 1 本次读到什么

| 来源 | 实际覆盖 | 能说明什么 |
| --- | --- | --- |
| 本机 EXE | SHA 与 PE 节表复核；限定节区的完整 ASCII 字符串及小范围邻域 | 名称存在及其位置；不能当作执行链 |
| `Spore_Game.package` | DBPF 3.0 索引 11,529 项；所选 25 个 PROP 资源 | 基础包中记录的技能配置 |
| `PatchData.package` | DBPF 3.0 索引 25,535 项；同一组 25 个 PROP 资源 | 补丁包同名记录；不声称已确认包加载顺序 |
| 社区 ModAPI | 固定提交的能力、空间对象、战斗对象与动画声明 | 结构与函数入口线索；未和本机 ABI 对齐 |
| 开发团队论文 | 目标相对运动、身体尺度适配、拳击方向模式 | 公开的动画设计；不是伤害判定实现 |

25 个不同资源为 Bite/Strike/Charge/Spit 各 1–5 级、四个技能模板、共同模板；两包分别保留，共 50 条记录。所有选中资源完整解压并解析到末尾，没有略过未知类型后继续拼结果。没有提取模型、贴图、完整动画或存档。[本机配置与来源摘要](evidence/local-selected-attack-properties.json)

目标身份：EXE SHA256 `f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d`；基础包 `9d085118c649d211a86723d363592fd66ad655fd24497289b3eab96bb07db329`；补丁包 `cadbff237076b441e6981503f80538705aefa5863bb4c8d1b869f9db98d1adff`。这是本地读取记录，**不是 REA provider 返回的 Evidence**；没有捏造函数定位或证据 ID。

### 1.1 解码时必须保留的边界

DBPF 索引是小端，PROP 的数量、属性头和普通数值是大端，资源键和向量又使用小端。读取器检查索引跨度、资源跨度、压缩输出长度、反向引用、属性数量、类型、填充与末尾；未知格式显式失败。RefPack 允许重叠复制，不能用普通不重叠片段复制替代。格式依据固定到 SporeModder-FX 提交 `a482c51d8d37fc8cf416acecc3c00a5b0723f2e5`，不是调用最新版本猜格式。[格式来源记录](evidence/public-dbpf-prop-format-sources.json)、[注册表记录](evidence/public-ability-name-and-type-registry.json)

资源名采用小写 FNV-1；属性名有大量显式 ID，不能全部自行哈希。`creatureabilityTemplates~` 的注册 ID 是 `0xd2fcb262`，也不能用裸名称哈希替代。[哈希实现](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/HashManager.java)、[资源键格式](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/ResourceKey.java)

本机 `parent` 键中类型是 **0**，而匹配的包条目类型是 PROP `0x00b1b104`。报告保留原键，并单独记下“同组、同实例的 PROP 候选”。以下连接是研究查找推导，未确认游戏内部怎样处理省略类型。没有将原值偷偷改成 PROP，也没有称其为运行时继承结果。

```text
bite1..5   → BiteTemplate   ┐
strike1..5 → StrikeTemplate ├→ CreatureAbilityTemplate
charge1..5 → ChargeTemplate ┤
spit1..5   → SpitTemplate   ┘
```

共同模板的四个属性不包含距离/伤害；选取的字段中能识别出两个本地化引用。两包对应资源的**所选属性完全一致**，但解压后文件摘要不同；不能扩大为整个资源字节一致或所有配置一致。未建立加载顺序，本次只报告每包各自的值。

## 2 四类攻击的真实配置入口

下面均为读取到的 **PROP 原始数值**，不是 SDK 注释里的默认值。未确认长度单位、时长单位、是否按体型缩放或是否用于玩家与 NPC 的同一分支；不用“米”“秒”标注原作参数。

| 字段 | BiteTemplate | StrikeTemplate | ChargeTemplate | SpitTemplate |
| --- | ---: | ---: | ---: | ---: |
| `creatureAbilityType` | 30 | 33 | 31 | 32 |
| `creatureAbilityCategory` | 1 | 1 | 1 | 1 |
| `creatureAbilityRange` | 1 | 1 | 1 | 30 |
| `creatureAbilityRangeMin` | 0 | 0 | 5 | 0.5 |
| `creatureAbilityRefresh` | 1.5 | 4.5 | 6 | 3 |
| `creatureAbilityEffectDuration` | 1 | 1 | 5 | 6 |
| `creatureAbilityConeDist` | 未直接写入 | 1 | 未直接写入 | 未直接写入 |
| `creatureAbilityConeRadius` | 未直接写入 | 2 | 未直接写入 | 未直接写入 |
| `creatureAbilityConeDamageMultiplier` | 未直接写入 | 0.25 | 未直接写入 | 未直接写入 |
| `creatureAbilityRushingRange` | 未直接写入 | 未直接写入 | 20 | 未直接写入 |
| `creatureAbilityRushingSpeed` | 未直接写入 | 未直接写入 | 20 | 未直接写入 |
| `creatureAbilitySpeed` | 未直接写入 | 未直接写入 | 未直接写入 | 50 |

“未直接写入”不是 0，也不排除代码默认值。字段名提供语义线索，不能单凭名称认定 Strike 必然对扇形内所有敌人结算 25% 伤害。

### 2.1 等级记录怎样改变模板

| 级别 | Bite `Damage` | Strike `Damage` | Charge `Damage` | Spit `Damage` |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1 | 3 | 1 | 0.5 |
| 2 | 1.5 | 4.5 | 1.5 | 1 |
| 3 | 2 | 6 | 2 | 1.5 |
| 4 | 2.5 | 8 | 2.5 | 2 |
| 5 | 3 | 9 | 3 | 2.5 |

这是 `creatureAbilityDamage` 原值，不能直接称最终扣血量。实际可能有等级、身份、状态或其他处理，尚未追到读取者。

四族 1–4 级记录的 `RequiredCAPsMaxValueRange` 分别是 `[1,1]`、`[2,2]`、`[3,3]`、`[4,4]`；5 级为 `[5,1000]`。这为10中的资格分档提供了**配置层证据**，并不等于已恢复 CAP 聚合器或它的读取顺序。

Charge 各级另外直接写入 `RangeMin=[14,10,10,10,10]`、`RushingRange=20`、`Refresh=[10,12,10,8,6]`；模板中的最小距离 5 不是所有等级的原始配置值。二级 Refresh 比一级大也不是解析器主动“修正”成单调曲线。Spit 各级另有 `EffectDamage`，因此直击与附带效果不能只看一个 Damage 字段。

Bite/Strike 的等级记录有不同 `AnimationIDs`；例如 Strike 1–5 为 `0x044DDD75`–`0x044DDD79`，Bite 为 `0x044DDEA6`–`0x044DDEAA`。它们说明等级记录选择动作资源，**不说明具体左手或右手**；选择资源以后仍有动作通道对当前身体的绑定。SpitTemplate 有普通动作 ID；ChargeTemplate 同时有 RushingAnimationID 与普通 AnimationIDs，支持继续分别追接近段与攻击段，但未恢复真实阶段时序。

### 2.2 这对“长手能打更远”意味着什么

已确认的是：技能体系有独立的范围、最小范围、冲刺距离、速度、锥形与动画资源参数。**仍不能得出长手提升射程，也不能得出长手完全不影响射程。** 同为 Range=1 的 Bite 和 Strike，可能经过不同几何与体型修正；Charge 的 RangeMin 大于普通 Range，说明把这两项机械解释成同一个合法中心距离区间会产生矛盾，需要分支/阶段读取证据。

本次所选记录没有直接写入 `creatureExtentsContributionScale`；这只是受限资源覆盖内的否定结果，不证明发行版不按体型修正。

## 3 原作表现层和效果层怎样分开看

开发团队的动画设计允许按整体包围范围或肢体路径长度缩放位移；外部目标模式将动作调整到另一只手或果实等位置。方向限定模式保留运动形状，只随目标转向，论文以拳击为例。因此一套动作可以适配短手、长手和不同站姿，无需为每种身体制作完整关键帧。[开发团队论文 §3.2.2](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

这解决的是“动作画面怎样看起来合理”，没有说明实际攻击阈值。论文 §5 提及当时动画系统不理解体积边界、忽略内部碰撞；它也不能证明玩法层没有碰撞判定。

固定社区提交 `2d71289adc71aa5c58f4516c6c835c99f5f9ca19` 提供下列入口：

| 层 | 入口 | 边界 |
| --- | --- | --- |
| 技能配置 | `cCreatureAbility` 的 `mRange/mRangeMin/mAvatarRangeMin/mConeRadius/mRushingRange` | 声明可和配置词汇对应；没有恢复构造/读取函数 |
| 对象几何 | `cSpatialObject` 位置、尺度、局部包围盒、包围半径、占地半径 | 尚不知陆地攻击使用哪一种，或尺寸是否已经乘过尺度 |
| 候选查询 | `cCreatureBase.funcB8h(target, abilityIndex, optional hitPosition)` | 未命名虚方法；不能直接把它重命名为命中函数 |
| 动画事件 | `AnimationMessage` 的消息、身体块索引与参数 | 能携带部件相关事件；尚未找到陆地战斗接收者 |
| 伤害提交 | `cCombatant.TakeDamage` | 声明存在；向量参数用途未确定，不称其为命中点 |

[能力声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCreatureAbility.h)、[空间对象](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cSpatialObject.h)、[生物声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCreatureBase.h)、[战斗对象](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCombatant.h)、[动画消息](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/AnimatedCreature.h)

新增头文件的摘要与读取范围见[公开入口记录](evidence/public-hit-entry-observations.json)，能力/移动入口沿用24的固定来源记录。

社区导出工具说明事件可标记命中时点，并按被选身体分别产生事件。它没有证明多只手的多个事件都扣血。事件数量、动画参与部件数量、伤害次数必须分别调查。[事件格式说明](https://github.com/Spore-Community/SporeModder-FX/wiki/Exporting-creature-animations-from-Blender)

### 3.1 排除的误导线索

- 本机 `biteCapRange/strikeCapRange/chargeCapRange/spitCapRange` 邻近 `species_query/numFeet/totalAttack` 等汇总查询词，不能拿来当空间射程。
- `cCombatant` 的武器距离接口注释限定 weapon tools，武器 getter 注释限定车辆；不能移植为 Creature 的能力范围算法。
- 本机与 SDK 的 `mHitSphereSize` 周围存在屏幕尺寸、城市或载具武器信息；名称不能证明是陆地近战碰撞体。
- 树木/果实邻域中的 `mRadius/mHeight`、屏幕尺寸邻域中的 `mMinDistance/mMaxDistance`，也不能拼成生物战斗公式。

这些排除与限定节区的完整字符串结果见[本机词汇记录](evidence/local-attack-entry-observations.json)。记录的是数据位置，不是函数地址或已验证调用者。

## 4 给用户游戏：五个不同的量

以下是**独立设计候选**，不是 Spore 恢复代码，也未在用户游戏中实施。身体加宽或换肉体时，至少区分这些职责：

| 量 | 谁提供 | 用途与变化 |
| --- | --- | --- |
| 移动占地 | 身体核心与可碰撞结构 | 通道是否容得下、避让与站位；装饰不必全计入 |
| 受击体积 | 核心和可受伤部件的碰撞形状 | 目标能被什么轨迹击中；不同于整体视觉包围盒 |
| 肢体可达域 | 附着点、骨链长度、关节限制、末端与姿态 | 哪只手能接近接触点；断肢后局部失效 |
| 技能规则范围 | 肉体/灵魂的技能描述 | 法术距离、喷射距离、冲刺条件等；不必全从肢体长度推出 |
| 动画目标与轨迹 | 已选方案、目标与动作模板 | 表现如何跟踪目标；不能随意改变已绑定执行肢体 |

灵魂法术可以采用规则范围；触碰型灵魂技能仍需手等部件满足传导/接触要求。技能来自灵魂，不自动意味着不依赖肉体。反之，长手提高几何可达性，不自动提高法力或技能伤害。

```text
AbilityMode {
    provider: Body | Soul
    partRequirements, resourceCosts, timing, effectPolicy
    reachPolicy: PhysicalContact | RuleRange | Projectile | Rush
    hitPolicy: SingleTargetRecheck | SweptVolume | ProjectileImpact
    requiredEffectRole, minRange, maxRange, maxTargetAngle
}
ReachProfile {
    stablePartId, bodyId, geometryVersion, functionVersion
    worldAnchor, chainSegments, jointLimits, preferredPose
    physicalEndShape, conservativeReachBounds
}
BoundAction {
    actionId, soulId, controlGeneration, targetId
    chosenMode, effectParts[], presentationParts[], dependencyVersions
    effectOrdinals, resourceReservation, channelClaims
}
```

`effectParts` 和 `presentationParts` 允许不同。例如双手一起摆拳，其中一手负责单次判定；多击技能才为每次有效击打分配不同 effectOrdinal。不能用“收到几个骨块事件”隐式定义伤害次数。

## 5 灵魂怎样联合评估技能、目标与肢体

先按资格筛选，再做几何与代价评估，最后做策略评分。原地够不到的长手仍可能在移动后成为合理候选，不能第一次可达检查失败就永久删除整个技能。

```text
BuildCandidatePlans(soul, body, perceivedTargets):
    assessment = CurrentBodyAssessment(body)
    for skill in BodyAbilities(assessment) + SoulAbilities(soul):
        for mode in skill.modes:
            providers = FunctionalProviderGroups(mode, assessment)
            for target in perceivedTargets:
                for parts in providers:
                    result = EvaluateReachAndApproach(mode, parts, target)
                    if result.impossible:
                        RecordReject(skill, target, parts, result.reason)
                        continue
                    plan = Bind(skill, mode, target.id, stableIds(parts))
                    plan.approach = result.approach
                    plan.reachPrediction = result
                    plan.cost = ResourceCost + TimeCost + ExposureCost
                    plan.utility = SoulScore(predictedEffects, plan.cost, confidence)
                    Emit(plan)
```

面对一个球形目标，简化两段手臂模型可以先做廉价可达界限：

```text
A = arm.worldAnchor
C, R = target.worldCenter, target.worldRadius
D = length(C - A)
distanceToSurface = max(0, D - R)
minReach = abs(L1 - L2)
maxReach = L1 + L2
feasibleContact = TargetSphereIntersectsReachShell(A, minReach, maxReach, C, R)
```

外边界不够时，要移动、转身或改用别的技能；目标太近时，还可能需退后。球与壳相交的完整条件是 `max(0,D-R) <= maxReach` **且** `D+R >= minReach`，不只是比较最近点。关节限制、攻击方向、障碍与占用再通过更精确的查询或短时姿态求解检查。两段自由关节壳只是预筛，不能当真实可达域；末端有尺寸时把它计入实际接触几何。一般分叉骨链可用保守界限加有限候选目标求解，避免每轮 AI 对所有方案做整套 IK。

规则范围型技能则使用自己声明的起点与距离定义，例如施法器官到目标表面的距离；投射型检查生成位置、方向、遮挡与飞行预测；冲刺型另检查可移动走廊和预计停靠位置。**所有政策必须由同一规则服务供 AI 预测和战斗执行调用。** 预测可以近似，但应记录置信度和误差，不另写一套互相矛盾的最终范围公式。

## 6 一个完整战斗例子：长手、逃离、断肢与法术

本节参数全为我们自己的算例，长度用本示例单位，时长用秒；和上面的 Spore 配置无对应关系。肉体有短左手和长右手；灵魂有远程法术。

| 输入 | 值 |
| --- | --- |
| 身体中心 | `(0,0,0)` |
| 左/右附着点 | `(0,-0.4,0)` / `(0,+0.4,0)` |
| 左手两段长度 | `1.2 + 1.0 = 2.2` |
| 右手两段长度 | `2.0 + 1.6 = 3.6` |
| 敌人中心/受击球半径 | `(4,0,0)` / `0.5` |
| 身体移动速度 | `2` 单位/秒 |
| 手部技能/法术 | 手击伤害8、前摇0.4；法术由身体核心发出、伤害5、规则范围6、消耗法力3 |

两只手到敌人中心都是 `sqrt(4²+0.4²)=4.01995`；最近球面距附着点 `3.51995`。右手预筛可达，左手超出最大长度约 `1.31995`。左手若先沿目标方向移动，忽略障碍的接近时间下界约 `0.66`；实际落点还需导航、朝向与关节约束检查。

假设风险与命中置信度检查通过，本算例定义评分 `预期伤害 - 4×预计时间 - 法力消耗`：

| 候选方案 | 简化评分 | 选择含义 |
| --- | ---: | --- |
| 原地右手攻击 | `8 - 4×0.4 = 6.4` | 锁定右手稳定 ID |
| 接近后左手攻击 | `8 - 4×(0.66+0.4) ≈ 3.76` | 可行候选，但行动更慢 |
| 灵魂远程法术 | `5 - 4×0.4 - 3 = 0.4` | 保留法力；当物理方案变差时可升高 |

这不是通用评分常量。不同灵魂可以提高近身风险权重、重视节省法力、改选更弱目标或优先保护同伴；几何事实不因性格改变。

行动在 `t=0` 绑定右手并预约通道。敌人前摇期间移动到 `(4.8,0,0)`。在 `t=0.4` 的有效击打时点，最近表面距离约 `sqrt(4.8²+0.4²)-0.5=4.31664`，右手已够不到。本示例的“单目标重查”政策返回 **Miss(OutOfReach)**；动画可以完成收招，但没有伤害提交。IK 不得为了看起来命中而拉长右手或推动目标。

随后右手被切断：先使依赖右手的未完成行动失效，释放通道/预约，再更新肉体评估。目标仍在4.8处时，左手几何接近时间下界约 `(4.31664-2.2)/2=1.06`，手击评分约 `2.56`。假设这段移动会增加4点暴露代价，左手方案降为 `-1.44`；法术仍在其规则距离内、评分 `0.4`，灵魂改选法术。若敌人已不可见，则根据感知置信度降低评分或追到最后位置，不能把世界真实位置直接当灵魂已知信息。

如果此时换成无手肉体，右手事件携带的旧 bodyId/controlGeneration 必须被拒绝；法术是否保留取决于它需要意识、嘴、手或其他传导部件。不能只因为“换肉体后还有同名技能”就沿用旧部件绑定。

## 7 有效时点怎样结算，怎样防止多手重复伤害

```text
OnEffectEvent(actionId, effectOrdinal, sourceBlockIndex, capturedGeneration):
    action = FindActiveAction(actionId)
    if action absent: return Ignored(StaleAction)
    if capturedGeneration != action.controlGeneration:
        return Ignored(StaleController)
    if effectOrdinal not declared by action.mode:
        return Rejected(UnexpectedEffectOrdinal)
    if !DependenciesStillValid(action):
        CancelAndRelease(action, BodyChanged)
        return Cancelled
    if !MessageSourceBelongsToBoundRole(sourceBlockIndex, action):
        return Ignored(UnboundPresentationPart)
    if EffectAlreadyResolved(actionId, effectOrdinal):
        return Ignored(DuplicateEffect)

    result = AuthoritativeHitQuery(action.mode.hitPolicy, action.boundParts,
                                   action.target, currentWorld)
    if result.error: FailAndReleaseWithDiagnostics(action, result.error)
    else:
        CommitEffectOnceAtomically(actionId, effectOrdinal, result)
        # 同一结算中记录已解析序号，并提交伤害/效果或 Miss 原因。
```

Miss 也消耗本次效果序号；否则右手落空后重复左手事件可能变成第二次“补考”。资源在发动、有效点或成功命中时消耗，必须是技能的显式政策，不能失败后随意退还。扫掠形状的多目标技能通常以 `(actionId,effectOrdinal,targetId)` 去重，并保留窗口关闭状态；多次预定打击才使用不同序号。11的执行状态机继续负责恢复段、中断和释放。

动画以固定行动和目标驱动，命中按游戏规则结算；两者共享几何描述，但不把视觉网格每帧相交作为默认玩法真相。若选择扫掠碰撞，就记录前后时点的碰撞形状并做连续查询，不能只检查当前一帧而漏过快速拳击。

## 8 加宽、拉长与换体后重新评估哪些东西

| 变化 | 最小失效范围 | 当前方案如何处理 |
| --- | --- | --- |
| 身体加宽 | 附着点世界变换、碰撞形状、相关肢体可达域、占地与站位 | 重新算方案；不只修改整体 radius |
| 一只手拉长/关节改形 | 该链的长度/约束、动作适配、几何缓存；需要时更新受击与占地 | 重评该手候选及依赖它的动作 |
| 断手 | 该部件功能/身份、相关能力贡献、通道占用和行动依赖 | 当前技能按中断政策取消或剩余参与者继续 |
| 换肉体 | bodyId、控制代次、身体能力与部件绑定 | 旧事件全部失效；灵魂人格与自带技能保留后重新查依赖 |
| 目标移动/变大 | 目标几何版本、预测位置和置信度 | 重查接近与命中，不必重建整个己方身体 |

```text
OnBodyChange(change):
    InvalidateAffectedGeometryAndCapabilities(change)
    for action depending on changedPartsOrController(change):
        ApplyExplicitInterruptPolicyAndRelease(action)
    assessment = RebuildAffectedBodyAssessment(change)
    soul.InvalidatePlansDependingOn(change)
    soul.RequestDecision(BodyChanged)
```

同一行动中临时从断掉的右手换成左手，会改变占用、轨迹、时长和代价。默认取消后产生新行动；若设计允许双手技能降级继续，需提前在 mode 中声明可失去的参与者和剩余效果，不能由动画器偷偷接管选择。

## 9 下一步怎样区分原作的候选算法

| 验证 | 必须控制 | 可以区分什么 |
| --- | --- | --- |
| 攻击前摇中目标退出范围 | 启动、接触、事件、HP变化时点 | 启动后锁定结算、有效点重查等候选；失败仍不证明网格碰撞 |
| 长手与短手比较 | 同能力、实测尺度/整体包围范围接近、只改变肢体路径 | 肢体长度与整体体型修正；只拉手会同时改变包围盒，无法归因 |
| 目标大小改变 | 技能配置、攻击者、站位、目标身份/状态 | 中心距、表面距、footprint 等候选；需实际量测目标几何 |
| 多手事件计数 | 同技能、同目标，记录选中块、事件和伤害次数 | 多部件表现与多次玩法效果是否分离 |
| 冲刺/喷吐分别测试 | 起始距离、路径障碍、命中位置和目标移动 | 多阶段范围、走廊/投射/直接目标结算的差别 |

当前原生 provider 不可用，没有恢复 `funcB8h` 调用者、技能属性读取者、事件接收者或 TakeDamage 前的计算。尚未启动/附加游戏；需要可控运行样本时才选定程序与场景，不要求用户现在保持游戏打开。

实际验证：[局部读取器](checks/read_selected_ability_properties.py)在两包完成索引检查与50条完整资源解析；[8项读取边界检查](checks/verify_selected_ability_reader.py)覆盖字节序、填充、三种压缩回溯、重叠复制、截断、非法计数和本机记录对比。独立战斗算例的数字与事件政策检查见[算例检查](checks/verify_reach_hit_example.py)。这些不是原作运行测试，也不是用户游戏已经可用的战斗代码。

未做：原生反编译、真实伤害/距离测量、其他阶段研究、模型/贴图/整段动画提取、用户产品实现、仓库生产构建。研究脚本与文档的验证记录见[本轮检查](evidence/attack-reach-verification.json)。

后续[33](33-shape-revisions-collision-hit-and-ai-sync.md)补同版本广相/狭相、权威姿态、扫掠命中、断肢与灵魂缓存失效；[32](32-body-volume-contacts-and-self-collision.md)补动作表面接触。表面接触求解成功不自动产生伤害。

风险：PROP 解析得到的是原值，解释仍依赖公开注册名称；父引用解析、包优先级与本机 ABI 尚未验证。完整命中链仍未知。独立规格中的关节壳、评分和击打政策仅是可讨论候选，应按用户玩法决定后实施。
