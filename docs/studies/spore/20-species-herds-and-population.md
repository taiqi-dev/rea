# 20 物种、巢穴族群与数量管理

[目录](README.md) · [配合AI](21-pack-coordination-and-shared-intents.md) · [社交关系](22-social-sessions-and-relationships.md)。范围仅登陆后、部落前的Creature Stage。结论：物种资料、局部族群、跟随小队和关系进度应分别理解；原作已有结构线索，下面的完整算法是独立设计。

## 1 原游戏证据能支持什么

社区声明固定为Spore-ModAPI提交 `2d71289adc71aa5c58f4516c6c835c99f5f9ca19`；路径、摘要和选取行保存在[公开声明记录](evidence/public-group-social-contracts.json)。这是社区直接维护的接口声明，不是Maxis原始源码，也没有验证本机ABI。

| 层 | 已有入口 | 能回答的内容 | 尚不能回答 |
| --- | --- | --- | --- |
| 物种资料 | `cSpeciesProfile`的作品键、幼体键、身体/能力数据 | 一个物种采用什么生物与能力资料 | 全球总数量、每个字段是否使用 |
| 局部族群 | `cHerd.mHerd`、`mEggs`、`mOwnerSpeciesKey` | 成员、蛋与所属物种有独立表示 | 列表包含哪些远处/未显示成员 |
| 巢穴 | `cHerd.mpNest`、`cNest.mpHerd` | 族群与巢穴有关联 | 同物种多个巢穴的更新传播 |
| 数量参数 | `mTargetHerdSize`、`mInitialShortfall`、`mRespawnRate`、`mScheduleIndex` | 有目标数量、初始缺口、补充及调度入口 | 默认值、单位、公式、计时起点 |
| 结束状态 | `cHerd.mbExtinction` | 族群结构有灭绝相关标记 | 标记写入条件、作用范围、存档语义 |
| 关系进度 | `numKilled`、`numBefriended`、`friendlyCount` | 击杀与结交次数分别记录 | 是否全地图共享、重复计数防护 |

来源：[cHerd](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cHerd.h)、[cNest](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cNest.h)、[cSpeciesProfile](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cSpeciesProfile.h)、[关系管理器](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/SubSystem/cSpeciesRelationshipManager.h)。其中 `mHuntingStyle` 注释为未初始化，不能仅凭Solo/Pack枚举断言实际狩猎策略。

本机EXE的完整字面量：`mTargetHerdSize`在文件偏移 `0x1071308`，`mRespawnRate`在 `0x10712d8`，`mNumToKillForExtinction`在 `0x106a9ec`，`mbExtinction`在 `0x1071100`。这加强了“数量参数与灭绝进度值得分别追查”的判断，**不证明这些字段之间的公式**。[本机记录](evidence/creature-group-social-string-survey.json)

记录还包含其他阶段及音频Packet等无关命中，118项不是118条陆地AI证据。扫描仅检查 `.rdata` 中限定长度的可打印ASCII；没有命中完整 `mHuntingStyle` 不能解释为游戏没有这个功能。偏移是字符串数据位置，不是函数。

官方手册说明玩家控制单个生物，同物种成员自行活动；智力成长增加跟随位置，最多三名同伴。因而“同物种成员数”和“小队容量”已有玩法上的区别。[官方手册，印刷页32–35](https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/17390/manuals/manual.pdf?t=1642702281)，[来源摘要与页码](evidence/official-manual-creature-pages.json)。

**当前推导：** 有充分理由把原作视作由族群对象、个体AI、关系进度共同组织的遭遇系统。证据尚不足以说明它模拟了整颗星球的出生、死亡和生态承载量，也不能证明“杀空当前巢穴”“达到击杀配额”“整个物种灭绝”三者始终等价。

## 2 自研结构：六种身份分别有主人

以下全部为用户拼装游戏的独立规格，参数不来自Spore。

```text
SpeciesDefinition { speciesId, bodyRecipePool, abilityPrior, encounterProfile }
FactionState      { factionId, relationshipLedger, groupPolicies }
HerdState         { herdId, speciesId, factionId, nestId, generation,
                    residentIds, awayIds, committedBirthIds,
                    spawnReservations, targetPopulation, nextRefillTime,
                    extinctionState }
SquadState        { squadId, leaderId, memberIds, capacity, sharedIntent }
CreatureInstance  { entityId, incarnation, homeHerdId, activeGroupId,
                    bodyId, soulId, alive, worldPresence }
SoulState         { soulId, beliefs, socialMemory, personality, ownSkills }
```

物种描述肉体来源；阵营负责关系政策；族群负责巢穴人口预算；小队负责活动协作；个体负责实际生死与位置；灵魂负责意愿和策略。换肉体可改变物种外观，阵营/信任归属依产品规则处理，不能自动重置成该外观物种的全部朋友。具体身份识别规则见22。

`homeHerdId`是来源，`activeGroupId`是当前行动组织，二者不冲突。离巢加入小队的成员进入 `awayIds`，依然占来源族群的预算；避免每招走一个就免费补一个。离开渲染范围时 `worldPresence` 可改变，`alive` 不随之改变。

## 3 自研数量算法：预算、预约、提交

本规格计入有明确人口承诺的出生事件；仅装饰蛋不计入。选择单位：`targetPopulation`为个体数，`refillInterval`为秒，每次调度还受本区生成预算限制。

```text
Allocated(H) = |alive residentIds| + |alive awayIds|
             + |committedBirthIds| + sum(spawnReservations.count)

RefillTick(H, now):
    atomic within herd owner:
        if H.extinctionState != Active: return ExplicitlyDisabled
        if now < H.nextRefillTime: return NotDue
        missing = max(0, H.targetPopulation - Allocated(H))
        count = min(missing, regionalSpawnBudget.available)
        H.nextRefillTime = now + H.refillInterval
        if count == 0: return AtTargetOrBudgetLimited
        reservation = reserve(H.herdId, H.generation, count, regionalBudget)
    start independent creation job(reservation, species recipe selection)

CompleteSpawn(jobResult):
    atomic within herd owner:
        lookup owned reservation; duplicate completion cannot install twice
        if result failed:
            release reservation and budget; record failure/retry reason
        else if herd inactive or reservation.generation != H.generation:
            discard created instances; release reservation and budget
        else:
            install instances and consume reservation in same transaction
            partial success installs actual count; release unused slots
```

生成工作会延迟；若只看可见动物数量，没有预约，就可能连续派出多个任务超量。处理所有权必须覆盖族群关闭、灭绝、存档加载或世代更新后返回的旧结果。原作是否如此执行仍未知。

### 数量算例

自研族群目标6，巢边活着3，随玩家离巢1，已承诺出生1，已有生成预约1。分配总数 `3+1+1+1=6`，即使镜头只有3只，也不补。巢边一只死亡后总数5；下一次允许补充时只预约1，总数恢复6。

这1个任务尚未完成时，任务进度触发区域灭绝：族群世代增加并停止补充，旧结果不能入群。另一个巢穴是否一起停由**明确配置的灭绝范围**决定；本算例选择区域内该物种，不自动扩展到整个世界。

## 4 自研击杀与灭绝：进度不是当前人口

```text
OnConfirmedDeath(event):
    atomic within death/progress owner:
        key = (event.entityId, event.incarnation)
        if key already processed: return Duplicate
        mark processed; update actual life and herd allocation
        if attribution qualifies for this objective:
            progress[(objectiveScopeId, victim.speciesId)].kills += 1
            relationship owner receives attributed hostility event
        if kills >= configuredKillQuota:
            mark objective complete
            apply explicitly configured extinction scope
            disable affected refill and invalidate reservations
```

例：区域任务要求7个合格击杀。第7个目标的死亡动画回调重复两次，仍只加1。地图卸载、切换LOD和入队不产生击杀。复活若允许，`incarnation`是否产生新任务资格需要规则明确，本规格每个实体生命版本独立计数，但仍由目标资格过滤。

任务完成不直接销毁世界全部同物种生物；本规格停止所选区域的族群补充，并对仍活着的成员采用明确的逃散/保留策略。若要真实生态灭绝，需另建全区域种群账本、繁殖与迁入模型；不能拿任务配额冒充生态人口。

## 5 验证与下一步

自研应验证：重复死亡、成员离巢、地图卸载、并发补充、灭绝后旧生成完成，以及同物种多巢穴的作用范围。算例核对见[可执行检查](checks/verify_group_social_examples.py)，它验证独立示例，不运行原游戏。

原作下一步：定位 `mTargetHerdSize`、`mRespawnRate` 与 `mNumToKillForExtinction` 的读取/写入者，核对单位、默认值、任务归属与标记传播，再做同场景离开/返回的运行观察。当前没有可用原生provider，未反编译、解码相关herdtypes资源、启动游戏、读取私人存档或运行仓库构建。风险：社区结构可能对应其他版本；本机字符串只给调查入口，所有数量公式仍为自研。
