# 18 非本人设计的敌人生物：作品来源与生成层次

[目录](README.md) · [Epic专篇](08-epic-creature-generation.md) · [配方重建](12-body-recipes-and-runtime-reconstruction.md)。这里先回答**Spore陆地生物阶段**，最后给用户自研游戏建议。

## 已有作品库＋角色筛选，不是每次完全随机拼装

官方FAQ说明本人、Maxis和允许的社区作品可进入游戏；Archetypes说明部件条件决定作品可填哪些NPC角色槽、订阅内容有偏好、不足可回退。由此能确认NPC使用已创作内容；不能把作品选择随机性等同于现场随机组装身体。[官方FAQ](https://www.spore.com/comm/faq/)、[官方Archetypes](https://www.spore.com/comm/tutorials/archetypes)

官方FAQ描述离线可仅用本人和Maxis内容，Buddies Only限制社区作者；它是产品功能说明，**不是本机账号/服务器现状检测**。没有读取私人Sporepedia或确认本机允许哪些下载来源。

| 普通CRG角色 | 官方资格示例 |
| --- | --- |
| NPC_Level1_Combat | 肉食/杂食；攻击各0–3、合计2–12；社交各0–3、合计0–12；Health能力0–3 |
| NPC_Level3_Social | 草食/杂食；社交各0–5、合计11–20；攻击各0–5、合计0–20；Health能力0–5 |

这些行的成本、手、足条件为N/A，即任意值，不是0。Health是作品能力条件，不是局内HP。资格不能独自证明遇见时的敌对关系。Epic另有专门资格，不能套给所有敌人。以上均见官方Archetypes表。

该页表达“选择并非随机”时紧接着解释按角色资格；应理解为**不是对全部作品毫无条件地任意挑选**。它没有给出合格集合内部的随机权重、排序或种子。

## 三种不同的“生成”

| 层 | 输入→输出 | 当前能确认什么 |
| --- | --- | --- |
| 身体设计来源 | 作者拼装→保存的生物作品 | 可来自Maxis、本人或社区作者 |
| 内容选择 | 需要的NPC角色→符合资格的作品 | 官方确认按archetype与来源偏好；集合内部算法未知 |
| 局内实例 | 已选作品/物种→有位置、生命、目标与动作的动物 | 社区接口有独立物种/实例结构；本机生成调用链未恢复 |

因此“预设还是随机”的准确回答是：**身体可来自预先制作的作品；出现哪份作品由资格及来源选择决定；地图位置、数量、数值和行为另有实例规则。不能概括成完全随机，也不能说整场遭遇全部手工固定。**

社区 `cCreatureAnimal::Create` 接收已有species profile、位置、年龄和可选herd；`cHerd`分开声明物种、原型、数量、位置、调度/重生及倍率字段。这些是声明旁证，不是已经读到本机函数体。[cCreatureAnimal](https://modapi-docs.sporecommunity.com/class_simulator_1_1c_creature_animal.html)、[cHerd](https://modapi-docs.sporecommunity.com/class_simulator_1_1c_herd.html)

本机文件身份与旧有界字符串结果见00/08。此次没有新增反编译、资源解码或运行观察，也没有将已有字段名升级为已恢复参数。

## 原作研究伪代码：未知保持未知

```text
InvestigateOrdinaryCreatureNPC(request, permittedContent):
    require request.stage == Creature
    role = Unknown(ActualNPCSlotRequest)
    pool = Unknown(EnumerationOfPermittedAvailableCreations, permittedContent)
    eligible = filter(pool, PublishedCRGCriteria(role))
    preference = KnownPrinciple(SporecastBiasAndFallback)
    creation = Unknown(ChoiceWithinEligibleSet, eligible, preference)
    species = Unknown(ProfileLoadAndReusePath, creation)
    site = Unknown(CRGPlacementAndSpawnSchedule, request)
    parameters = Unknown(NumbersStatsRelationsAndBehaviorInitialization)
    return Unknown(ActualInstanceCreationCaller, species, site, parameters)
```

普通资格算例：作品P有肉食口，Bite2/Strike1/Charge0/Spit0，攻击合计3；社交各0、Health能力1，满足Level1_Combat这行。作品Q有草食口，即使攻击同样合计3，也不满足这一行。P符合不代表一定被选，更不证明会在指定位置/概率出现。这是对官方表的演算，不是运行生成观察。

未知：本机内容池、来源优先级/权重、合格集合选择算法、随机种子、NPC槽位布局与数量、放置和重生、关系初始化、具体实例HP/伤害、自然Epic与普通动物的完整调用差别。官方页面直接打开曾失败，本轮官方内容通过搜索服务返回；没有依赖论坛或百科作为算法证据。

## 对用户游戏：模板与约束随机可以一起用

下面是**自研建议**，不是Spore还原。若希望敌人也能拼装，可先做少量作者设计的角色模板，再允许有限的部件替换、数量变化、比例/皮肤变化与灵魂策略抽选。内容来源与AI灵魂分开，避免同一种外形永远只有一种性格。

```text
EnemyArchetype {
    role, bodyTemplateIds, permittedPartPools
    requiredCapabilities, forbiddenCombinations
    costBudget, sizeRange, locomotionRequirements
    permittedSoulProfiles, soulSkills, habitatRules
    maxAssemblyAttempts, authoredFallbackId
}
EnemySpawnRecord {
    generatorVersion, archetypeId, seed
    resolvedBodyRecipe, selectedSoulConfiguration
    instanceParameters, worldPosition
}
```

生成的是符合角色约束的身体，不是均匀抽任意部件ID。近战追击者必须有可执行近战与有效移动；纯意识法师可以无手，但不能抽到全依赖符印手的灵魂技能且没有任何攻击方案。大身体也需通路/碰撞可容纳。

```text
GenerateOwnEnemy(archetype, site, seed, catalog):
    ValidateConfigAndCatalogReferences(archetype, catalog)
    rng = DeterministicRng(seed, generatorVersion)
    for attempt in 0 .. archetype.maxAssemblyAttempts-1:
        recipe = ClonePermittedAuthoredTemplate(archetype, rng)
        MutateOnlyPermittedSlotsAndShapeRanges(recipe, archetype, rng)
        body = BuildTemporaryAssessmentModel(recipe)
        caps = AssessBody(body)  # 同玩家使用16的能力评估规则。
        soul = ChoosePermittedSoulAndSkills(archetype, rng)
        check = ValidateRoleBudgetLocomotionAndExecutableAbilities(caps, soul, site)
        if check.failed: record RejectedAttempt(attempt, check.reasons); continue
        return Generated(PersistResolvedRecipeAndSoul(recipe, soul, seed))
    fallback = LoadDeclaredAuthoredFallback(archetype.authoredFallbackId)
    check = ValidateWithSameRules(fallback, site)
    if check.failed: return Error(NoValidEnemy, attemptDiagnostics, check)
    return GeneratedFallback(fallback, attemptDiagnostics)
```

模板/随机/回退三种来源都受同一验证，不能把失败隐藏成一只无法行动的怪物。随机重试次数有上限；不要无限循环直到运气好。最终配方与灵魂配置应持久化，单存种子会在部件池或生成器更新后读出另一只怪物。

构造例：追击者模板预算10、至少一种有效地面移动、至少一个近战模式。第一次抽到长手但无可支撑身体的腿，拒绝并记录LocomotionUnavailable；第二次抽到有效腿与角击，预算9，和保护/好战两种允许灵魂之一匹配，可生成。若给无手身体抽到符印火球且没有其它攻击方式，拒绝或使用预先允许的意识法术模式；不能生成后偷偷补一只手。

未做：Spore私有作品库/地图/存档检查、游戏运行或敌人生成概率测量；没有实施用户游戏的敌人生成器。风险：原作精确分布未知；自研约束太松会出不可用怪物，太紧会让随机内容几乎全部回退，需要用实际目录与生成统计调试。
