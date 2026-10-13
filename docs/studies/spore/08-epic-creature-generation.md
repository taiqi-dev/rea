# 08 陆地阶段的巨型生物：候选物种与实例生成

[目录](README.md)。将用户的“泰坦古生物”暂解释为 Epic Creature；范围是生物阶段自然遇到的巨大生物。部落 Epic 和 Galactic Adventures 的人为放大角色另属其他模式。

普通NPC作品来源、角色筛选与“预设还是随机”的区别，另见[18 敌人生物来源与生成](18-enemy-creature-sources-and-generation.md)；不要把本页Epic资格推广到全部敌人。

## 官方能回答的部分

官方 CRG 表的 `NPC_Epic_Predator` 候选条件如下。它定义可填 NPC 槽的作品资格，不保证符合条件就会出现。[Maxis Archetypes 教程](https://www.spore.com/comm/tutorials/archetypes)

| 列 | 官方条件 |
| --- | --- |
| Mouth Type | 肉食或杂食 |
| Cost | 200+ |
| Graspers | N/A，无手部门槛 |
| Feet | 1+ |
| Sing/Dance/Charm/Pose | 各 0–5，合计 0–20 |
| Bite/Strike/Charge/Spit | 各 0–5，合计 0–20 |
| Health | 0–5 |

不需要额外高等级攻击或社交能力。Feet 不能未经解释写成“至少一对腿”，Cost 也不能偷换成当前剩余货币。官方说明内容选择依据 archetype；订阅 Sporecast 有偏好，不足时可能回退到 Maxis 或其他 Sporepedia 作品。表格中的 TRG 行不用于此处。

因此更有依据的拆解是：**挑一份符合条件的生物作品，再产生具有巨型角色属性的局内实例**。没有依据说每次出现都重新随机长出一套完整身体，也没有依据说它仅缩放、绝不改变任何其他数据。

## 实例承载位置：社区声明与本机线索

社区 `cCreatureAnimal::Create` 接收位置和已有 species profile；`cHerd` 声明物种、位置、数量、调度和角色属性；枚举存在 `EpicPredator = 1`。它们没有证明自然 Epic 的调用者或本版本取值。[cCreatureAnimal](https://modapi-docs.sporecommunity.com/class_simulator_1_1c_creature_animal.html)、[cHerd](https://modapi-docs.sporecommunity.com/class_simulator_1_1c_herd.html)、[Simulator](https://modapi-docs.sporecommunity.com/namespace_simulator.html)

本机 EXE 摘要见 00；有界静态名称检查：

| 字符串 | 文件偏移 | 限度 |
| --- | ---: | --- |
| gait_epic | 0x1046650 | 特殊步态名称；路由未知 |
| epicfoottype | 0x1052964 | 足部效果线索 |
| epicfootsteps | 0x1052a34 | 邻近 footsteps；触发条件未知 |
| Simulator/cHerd | 0x105d660 | 类型名称 |
| mValidLocations | 0x1071280 | 位置字段名称 |
| mCreaturePersonality | 0x10712c0 | personality 承载线索 |
| mRespawnRate | 0x10712d8 | 重生字段，单位未知 |
| mTargetHerdSize | 0x1071308 | 数量字段，不证明 Epic 数量 |
| mDamageMultiplier | 0x1071318 | 伤害倍率字段 |
| mHitpointOverride | 0x107132c | 生命覆盖字段 |
| mScaleMultiplier | 0x1071340 | 缩放字段 |
| mOwnerSpeciesKey | 0x1071390 | 物种身份字段 |
| mArchetypeGroup | 0x10713b4 | 原型分组字段 |

全 EXE 有界 ASCII 表未找到 `NPC_Epic_Predator`；可能以资源名/ID 保存，不能推断不存在。`MinCreatureEpicScale` 0x108a228、`MaxCreatureEpicScale` 0x108a240 邻近 Scenario sculpt UI 与 captain adventure history，**不作为陆地自然生成大小规则**。

## 原游戏研究骨架：显式保留未知

下面只有资格条件来自官方规格。Unknown 是尚未恢复的接口标签，不是可执行实现，不能当成完整生成算法。

```text
OfficialEpicEligible(creation):
    return creation.mouthType in {Carnivore, Omnivore}
       and creation.partCost >= 200
       and creation.feetCriterion >= 1

InvestigateCreatureStageEpic(world):
    require world.stage == Creature
    request = Unknown(CRGSpawnTrigger)
    available = Unknown(AvailableCreationEnumeration)
    candidates = filter(available, OfficialEpicEligible)
    sourcePolicy = KnownPrinciple(SubscriptionBiasAndFallback)
    chosen = Unknown(ChoiceWithinEligibleSet, candidates, sourcePolicy)
    profile = Unknown(ProfileLoadPath, chosen)
    position = Unknown(CRGPlacementRule, request)
    parameters = Unknown(EpicScaleHealthDamageCountPersonality)
    instance = Unknown(ActualAnimalCreationCaller, profile, position, parameters)
    gait = Unknown(GaitEpicSelectionCondition, instance)
    return UnresolvedResearchGraph(instance, gait)
```

下一条有效追踪链是原型配置读取者 → herd/动物创建者 → 参数写入者 → gait_epic 引用者。没有这条链，不能用社区字段拼成“已恢复的 Epic 配置”。

## 独立生成系统：可讨论的完整规格

若我们做自己的巨型生物，建议把内容选择、地图放置、巨大化与战斗参数分开。以下固定种子、配置和值都是自研示例；不是 Spore 参数。

```text
OwnEpicConfig {
    maxAlive, minimumPlayerDistance, minimumSeparation
    permittedSlope, permittedBiomes
    scaleFactor, healthOverride, damageFactor, locomotionProfile
    weightedContentSources, spawnSeed
}
OwnEpicInstance {
    entityId, creationId, transform, role = GiantPredator
    health, damageFactor, locomotionProfile, spawnRecord
}

SpawnOwnGiant(world, creations, config):
    ValidateOwnConfig(config)
    if world.aliveGiants >= config.maxAlive:
        return Skipped(QuotaReached)
    pool = creations.filter(ourProductEligibility)
    if pool.empty: return Error(NoEligibleContent)
    rng = OwnSeededRng(config.spawnSeed, world.spawnSequence)
    chosen = WeightedChoice(pool, config.weightedContentSources, rng)
    sites = EnumerateOwnWalkableSites(world)
    sites = filter(sites, biome/slope/distance/separation rules)
    if sites.empty: return Skipped(NoValidSite, rejectedSiteCounts)
    site = StableSeededChoice(sites, rng)
    model = LoadOrBakeOwnCreation(chosen)
    if model.failed: return Error(CreationLoadFailed, chosen.id, model.reason)
    bounds = ScaleOwnBounds(model.bounds, config.scaleFactor)
    if !ValidatePlacement(bounds, site): return Error(PlacementInvalid)
    instance = CreateOwnEntity(model, site, bounds, config)
    PersistOwnSpawnIdentityAndParameters(instance)
    return Created(instance)
```

不为未知/无位置静默 return；配额阻止与加载失败是不同结果。实例身份和实际选择结果持久化，而不只保存种子，避免内容池变化使读档时变成另一个生物。

独立筛选算例：A 肉食、成本 240、Feet=2，可进入官方资格集；B 草食、成本 300、Feet=4，不符合该 Epic 捕食者条件；C 杂食、成本 190、Feet=2，也不符合。通过资格与地图最终选中是两件事。

自研尺度例：模型参考高度 1.2 m，配置尺度 3，实例高度 3.6 m。**这不是游戏巨大化倍率。** 生命/伤害使用独立参数；不能按体积 `3³=27` 自动推导 27 倍生命。动画目标、碰撞和转弯半径必须与实例尺度协同；只缩放渲染网格会产生脚滑、穿地或攻击范围不匹配。

## 未知与风险

未知：自然生成触发、概率、数量、地图分布、选择权重、下载/本地内容池、种子和读档策略、实际尺度/生命/伤害、人格写入与特殊步态路由。

未做：反编译、原型资源解码、地图采样与运行验证。风险：社区 SDK 版本未对齐；Scenario 同名字段可能误导；自研生成规格不能当作恢复的原作地图算法。
