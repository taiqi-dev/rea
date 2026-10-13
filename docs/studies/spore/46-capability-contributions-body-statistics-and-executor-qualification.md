# 46 部件能力、身体统计与具体执行者资格

[目录](README.md) · [10聚合问题](10-capability-aggregation-and-ability-eligibility.md) · [25实际技能配置](25-body-reach-attack-ranges-and-hit-resolution.md) · [39选执行者](39-same-role-effectors-variant-binding-and-default-mixing.md) · [45动作条件](45-animation-predicates-conditional-binding-and-fallbacks.md) · [16灵魂评估](16-soul-ai-body-assessment.md)。只研究陆地Creature和其编辑器。本轮起点2026-10-12 23:19:24 PDT，America/Los_Angeles。

本轮取得四份具体手/嘴定义的能力原值，并将其与既有技能资格配置、固定SDK的整生物统计字段对照。**部件贡献、整生物统计、技能档位、当前执行部件是不同层。** 本机聚合消费者仍未恢复；下文的求和/最高值/供能和资格公式均明确标作自研。

## 本机新读：一只手同时提供多种能力

从固定文件名注册表选普通Creature手/嘴，在两包索引精确查`PROP:40626000:lowercase-FNV1(name)`。两只指定bird手、两只普通amphibian_omnivore嘴在Patch匹配并完整走过PROP边界；Game在同键范围未匹配，不推广为基础游戏没有这些部件。[本机贡献记录](evidence/local-selected-capability-contributions.json)

| 部件定义 | 直接写入的能力原值（部分字段） |
| --- | --- |
| ce_grasper_bird_01 | Grasper1、Strike1、Social3、Mean2、Posture1 |
| ce_grasper_bird_02 | Grasper1、Strike2、Social5、Mean3、Posture2、Health1 |
| ce_mouth_amphibian_omnivore_01 | Mouth1、Bite1、Vocalize2、Cuteness3、Carnivorous1、Herbivorous1 |
| ce_mouth_amphibian_omnivore_02 | Mouth2、Bite1、Vocalize3、Cuteness4、Carnivorous1、Herbivorous1 |

表中是字段整数，不是最终伤害、HP、技能刷新率或实例数量。本轮没有读取父链执行/代码默认值；字段未直接出现不填0。两包摘要与既有身份一致；没有读取新模型、贴图或私人身体配方。四定义键、偏移、存储/解压摘要和完整字段计数保留在记录中。

两个反例很重要：Grasper同为1的两个手，Strike分别1/2；Mouth分别1/2的两个嘴，Bite都为1。抓握/嘴部字段不能替代攻击字段，更不能仅按角色grsp/mout猜技能强度。**一个定义中的Mouth=2不等于创建了两条部件实例。** 它是否描述多个可视开口或某种等级/统计含义，仍需要实际消费者和模型证据。

### 读取踩坑与修复范围

既有25读取器不支持嘴定义中的type0x39，首次两条嘴读取有明确诊断。本轮固定FX源码确认PropertyBBox是0x39、24字节；PropertyTransform实际为0x38、56字节，不能猜着跨过字段。

新[有界研究读取器](checks/read_capability_contribution_records.py)按已知PROP类型走每项边界，BBox只保留24字节原值；其余字段形成内存格式投影后交给原读取器解码。旧读取器及原游戏文件保持原字节。没有解释BBox坐标顺序，也没有把BBox当动作/能力公式。未知类型、错误itemSize、越界、重复字段或尾字节均诊断失败。[固定格式来源](evidence/public-capability-aggregation-contracts.json)

## 原作资格配置：最高值范围与总量范围分开表示

复用25完整解析的四类攻击1–5级、四模板和共同模板，共两包50记录；本轮没有重新读这些技能payload。固定属性注册表再次核对显式ID，不能把任意名称FNV当属性ID。

| 表示 | 已读证据 | 不能推出 |
| --- | --- | --- |
| 部件能力 | modelCapabilityStrike/Bite/Mouth等int32 | 最终整只生物值或贡献资格 |
| 技能RequiredCAPs | 需求字段和最大/总量范围分别声明 | 多数组配对/比较端点/缺省继承规则 |
| 四类1–4级 | MaxValueRange原值分别[1,1]至[4,4] | 所有技能都只取最大值 |
| 四类5级 | MaxValueRange原值[5,1000] | 技能上限就是1000，或两个端点一定包含 |
| SumValueRange / StatSumRange | 固定字典同时存在这些字段 | 某技能必定采用总和或每种部件都线性增加伤害 |

Grade=5配置有开放到1000的原值，不意味着此资源一定在运行用相同范围，也不恢复最高攻击手的选择。25的直接Damage字段仍是独立配置，不能把手部Strike2直接称成伤害2。

## 原作编译/物种表示：统计与提供者分别存储

固定SDK的cSpeciesProfile声明mSocialSum、mAttackSum、mAttackMaxLevel、mSocialMaxLevel，以及mBiteLevel/mChargeLevel/mSpitLevel/mStrikeLevel等。mNumMouths在该声明中是float；字段类型和名称不足以恢复真实计数公式。

cCreatureAbility分别表示required/excluded CAP、Max/Sum范围、攻击/社交总量范围；EditorRigblock声明各能力属性ID；cCreatureDataResource另有部件能力起点、数量、capability IDs/levels和animation values/weights。这些不是一个共享下标空间。[九份固定源码/注册表摘要与行位置](evidence/public-capability-aggregation-contracts.json)

本轮读取的是声明、格式工具和注册表，没有取得原作贡献归约、范围比较或选执行者函数体。全局注册表包含跨编辑器字段名；正文只对所选四个陆地定义与既有攻击资源解释，不分析其他阶段玩法。缺native提供者的状态继续沿用00。

## 自研结构：规则、贡献、摘要、技能资格、执行计划

以下全部是针对用户拼装/灵魂游戏的独立设计，参数不来自上表。

```text
CapabilityDefinition {
    semanticId, qualityDomain, capacityUnit, providerUnit: Part|Feature|Chain,
    functionalRequirements, summaryFields, explicitModifierRules
}
Contribution {
    partInstanceId, definitionVersion, capabilityId,
    baseQuality, baseCapacity, sourceFeatureIds[], functionalState
}
BodyCapabilitySnapshot {
    bodyId, bodyRevision, catalogDigest, modifierRevision,
    providersByCapability, maxQuality, sumQuality,
    declaredProviderCount, qualifiedCountsByRule, effectiveCapacity, diagnostics
}
AbilityRequirement {
    bodyRequirements[], executorRequirements[], requiredDistinctProviders,
    profileAndSocketRequirements, supportAndReachRequirements, resourcePolicy
}
OwnedAbility { providerKind: Body|Soul, providerId, abilityId, definitionVersion }
```

同款部件复制三次产生三个不同实例；同一实例重复登记同一贡献拒绝DuplicatePartContribution。镜像是否创建两条实例由配方事务决定，不能按对称标记直接加倍。一个手内部有多个爪尖，也不自动满足“需要两只手”；资格必须声明统计Part、Feature还是Chain，并验证共享祖先/独立自由度。

摘要同时保存多个统计，技能选用自己声明的字段。额外肢体可以增加可参与者和并发余地，不必提高最高等级。供能器官可按有效容量求和，武器品质可用max，双手动作可要求两个合格提供者；不存在适用于所有属性的统一归约。

## 自研聚合：质量与功能容量分别更新

本例质量是非负整数，容量是自研连续单位。质量在疲劳时不自动降级；容量按`baseCapacity×healthFactor×(1−fatigue)`变化，healthFactor/fatigue均在[0,1]。断开、功能损坏、healthFactor=0的部件排除并保留原因。另一种游戏可以采用离散质量退化，但需要自己的能力规则，不默认为Spore做法。

```text
BuildOwnCapabilitySnapshot(body):
    validate immutable body/catalog/modifier identities
    reject duplicate part IDs, unknown capability or duplicate local contribution
    for part and each contribution:
        validate finite nonnegative capacity, integer quality and declared units
        retain contribution source even when nonfunctional
        if detached/disabled/healthFactor == 0:
            record exclusion; keep known capability with zero functional providers
        else:
            effectiveCapacity = baseCapacity * healthFactor * (1-fatigue)
            append exact provider identity, quality, capacity and features
            update maxQuality, sumQuality, declaredProviderCount and capacity
    derive qualified counts for each declared eligibility rule
    publish one snapshot with body identity/revision and diagnostic reasons
```

疲劳=1时，本政策可保留品质3但容量0。需要容量的动作必须检查LocalCapacityInsufficient，不把“品质没变”当成还能出手。能力存在但无功能提供者与能力根本未定义分别诊断，便于灵魂判断修复、换技能或换肉体。

## 自研：全局解锁不替代执行者自身资格

```text
QueryOwnExecutableAbilities(soul, bodySnapshot, world):
    collect Body and Soul owned abilities with their distinct source IDs
    for ability:
        check its body max/sum/count/capacity requirements
        enumerate current executor instances/features at declared provider unit
        check each local quality/capacity/profile/socket and connection rule
        form only distinct qualified participant groups
        validate shared joints, reach, support, cooldown and output occupancy
        emit executable plans plus qualification/rejection provenance

CommitOwnPlan(plan, body, soul):
    verify bodyId/revision/catalog/modifier and controlGeneration still match
    revalidate selected providers, requirements and resource reservations
    atomically reserve the complete plan inside the actor update
    return bound action or explicit failure; do not substitute an arbitrary weak hand
```

全局max3满足技能门槛时，若技能规定发力手必须自身grade≥3，品质1的手不能自动借到3。若产品允许把躯干/灵魂能量传到弱手，需要另行声明传输路径、局部承载上限与消耗；不能因有全局统计就隐式实现这种能力。

两手模式检查两个独立合格提供者，不能用某手grade3顶替三只手。已解锁但唯一合格手忙于盾牌时，当前可执行集合可以为空；灵魂得到EssentialOutputOccupied，而不是“没有这个技能”。改造型带来的可达变化由39/33处理，能力品质不从手长自动推导。

## 自研完整演算：三手、断手与灵魂技能

身体B1/revision42三只手的独立构造参数如下：

| 手 | Strike品质 | 基础容量 | 健康因子 | 疲劳 | 有效容量 |
| --- | ---: | ---: | ---: | ---: | ---: |
| H1 | 1 | 3 | 1 | 0.2 | 2.4 |
| H2 | 3 | 5 | 0.8 | 0.1 | 3.6 |
| H3 | 2 | 4 | 1 | 0.5 | 2.0 |

1. 摘要得到maxQuality3、sumQuality6、providerCount3、effectiveCapacity8。它们分别回答品质门槛、累计指标、参与者数量和可用容量，没有合并为一个“攻击力8”。
2. HeavySlash要求身体max≥3、执行手品质≥3及局部容量≥1。身体合格，只有H2通过本地品质；H1/H3分别返回LocalQualityInsufficient。H2自身容量3.6通过。
3. H2正维持盾牌时，摘要品质仍3，HeavySlash仍解锁，但当前没有合法执行手，返回EssentialOutputOccupied。灵魂可等盾结束、改用H3的较低档动作或自带SoulBolt，不把技能错误发给H1。
4. DoubleSlash要求两只品质≥2、profile/关节/目标均可用的不同手。正常时H2/H3是候选；只有H2时即使品质3，也无法满足两个提供者。它们若共享关节仍需42联合验收。
5. H2断开后bodyRevision43：max2、sum3、count2、容量2.4+2.0=4.4；HeavySlash变BodyQualityInsufficient，DoubleSlash只剩一个品质≥2的手，变InsufficientDistinctProviders。旧revision42方案拒绝提交，灵魂重新评价H1/H3或自己的技能。
6. 若只是H2疲劳达到1，品质3仍在但容量0，HeavySlash返回LocalCapacityInsufficient。若H2还在但缺Grip/Strike执行profile，返回RequiredProfileMissing；这两种失败与断手不同。
7. 灵魂学会SoulBolt不改变身体Strike max/count。它有自己的来源、成本和冷却；若声明纯意识模式，则使用自己的发射框架并按40结算，而不伪装成一只额外攻击手。换魂失效行动计划，但不重写同一肉体的内在部件贡献。

另一个自研M1提供mouth质量2，摘要providerCount仍1；想支持某部件具有两个独立嘴口，要在features和执行模式中显式定义，不能拿质量字段当实例数量。这里的“质量”是自研语义，上面的原作Mouth整数没有被确认等同它。

## 检查、未知与风险

[独立聚合/格式与证据检查](checks/verify_capability_aggregation_examples.py)25项通过，覆盖max/sum/count/容量、局部执行资格、不同身体/版本、双手、忙碌/疲劳/断开/缺profile、重复贡献、真实四定义原值，以及BBox走表、未知Transform拒绝、边界和旧读取器一致性。与45、47–49的整体检查见[本轮记录](evidence/land-behavior-five-topics-verification.json)，不合并到前一轮111项。

已回答：四个具体部件的直接能力值；共享字典和固定SDK确实区分统计/等级/需求。部分回答：技能资格范围的实际配置与提供者表示。未回答：本机贡献归约、数组配对/端点语义、最终属性公式、实际技能执行手与最高提供者关系。

未做：游戏运行/附加、原生聚合函数追踪、私人存档、用户游戏实施和生产压力测试。网络读取使用正式权限流程取得固定公开源；没有安装、改配置、改游戏或修改既有格式读取器。

风险：数据声明和选定PROP不能代替运行消费者；自研疲劳容量、品质门槛及灵魂来源分层需要游戏平衡与实际连接契约验证。下一处关键原作证据是cSpeciesProfile统计的生产者和cCreatureAbility资格消费者，字段名本身不能补出公式。
