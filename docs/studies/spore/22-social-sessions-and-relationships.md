# 22 社交：动作挑战、会话结算与长期关系

[目录](README.md) · [数量与灭绝](20-species-herds-and-population.md) · [群体协作](21-pack-coordination-and-shared-intents.md)。只看登陆后的陆地生物阶段。原作可确认玩法和关系字段；具体计分、轮次、跟随者加成及传播公式尚未知。

## 1 原作事实与调查入口

手册的社交动作包括唱歌、跳舞、魅惑与摆姿态；互动中需要模仿对方动作，匹配能力等级。成功改善关系；已被打动的个体不能重复开始同类社交。友好/盟友关系允许在对方巢穴恢复，盟友可加入有空位的小队。战斗击败个体会降低整个物种的关系。[官方手册，印刷页33–35](https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/17390/manuals/manual.pdf?t=1642702281)。完整相关页面已读取，页码和摘要见[出处记录](evidence/official-manual-creature-pages.json)。

这说明即时动作挑战与长期关系变化存在不同职责。手册没有给出社交条公式、每场轮次数或“固定打动多少只就结盟”的普遍数值，也没有证明同伴贡献是简单相加。

社区 `cSpeciesRelationshipManager` 的记录包含 `relationship`、`friendlyCount`、`numBefriended`、`numKilled`、`lastAbilityMode`，并有两个以ResourceKey为键的关系表。两张表各自用途及是否覆盖任意NPC物种对尚未验证。[固定版本声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/SubSystem/cSpeciesRelationshipManager.h)

本机完整字面量及文件偏移：

| 入口 | 偏移 | 可以怎样继续追 |
| --- | --- | --- |
| `numBefriended` | `0x1065200` | 成功结交后的计数提交 |
| `numKilled` | `0x10651f4` | 战斗事件与关系变化 |
| `mNumToImpressForCurious` | `0x106a9d4` | 好奇关系的门槛读取 |
| `mNumToImpressForFriendly` | `0x106a9b8` | 友好关系的门槛读取 |
| `mNumToImpressForBestFriends` | `0x106a99c` | 更高关系的门槛读取 |

见[本机ASCII记录](evidence/creature-group-social-string-survey.json)。名称说明有可调查的关系门槛词汇；当前没有实际门槛值和写入函数。不能把它们自动等同于UI状态、全局关系传播或某个固定次数。

## 2 自研会话结构与状态机

下面是独立设计。先选择有限的动作响应机制，比把所有社交都交给自由对话更容易调试，也能直接使用已有身体能力和动作系统。

```text
SocialSession { sessionId, generation, initiatorId, responderId,
                participantIds, state, roundId, requestedAction,
                deadline, accumulatedProgress, requiredProgress,
                contributionLedger, outcomeCommitted }
Contribution  { sessionId, generation, roundId, actorId,
                planId, bodyVersion, controllerEpoch, action, strength }

States: Proposed -> Accepted -> Prompt -> Response -> RoundResult
                          ^                         |
                          +------- next round ------+
          -> Succeeded / Failed / Cancelled -> relationship commit
```

`SocialSession`负责短期计分；个体记忆负责是否已被打动；关系账本负责长期阵营/物种态度；小队负责入队名额。关系变好不直接将所有成员加入小队，当前会话也不负责刷新巢穴人口。

新会话验证：双方存活、距离与视线合法、没有冲突的战斗/交互预约、目标允许社交且未被该规则重复奖励。失败保留拒绝原因。社交策略也由灵魂决定：和平灵魂更倾向回应，捕食灵魂可能拒绝；这些人格规则是自研扩展。

## 3 自研参与者与具体肢体：每个行动仍需合法方案

```text
BuildSocialResponse(actor, requestedAction, opponent):
    capability = AssessBodyAndSoul(actor)
    candidates = legal body skills + legal soul skills
                 whose declared response type matches requestedAction
    plans = bind each candidate to its required limbs / channels
    reject unreachable contact, missing support, insufficient resource,
           blocked animation channels, stale body/controller versions
    choose by expected response benefit and soul's willingness
```

例如“摆姿态”需要合法支撑与指定可动部件；“唱歌”可要求发声器官；灵魂法术是否能代替唱歌由技能响应标签明确声明，不能因为数值高就无条件匹配。一个生物装四个嘴，也不会默认变成四名参与者；身体能力聚合与多角色贡献是不同层。

跟随者可以提供响应，但它们各自选择和预约行动，并须保持在会话范围。这里自主采用有限人数与可配置贡献权重；Spore的参与者上限、实际组合规则未知。

## 4 自研计分与完整算例

本例参数均为我们选择：每场需2次成功响应；盟友阈值为累计打动4个不同合格个体；实际原作数值未知。为便于演算，动作等级作为强度，每个参与者最多贡献一次：

```text
RoundStrength = sum(actor.strength * actor.assistWeight)
                over accepted unique contributions for current round
EffectiveStrength = RoundStrength * matchFactor
matchFactor = 1.0 when response type matches, otherwise 0.0
round passes when EffectiveStrength >= opponentThreshold
```

这是自研简化值，不是还原社交条或证明原作等级可以直接加总。对不同部件/灵魂能力，可改为有上限的贡献或概率响应，但需重做平衡和可解释评分。

前置：甲与乙同阵营，甲等级3的唱歌动作、乙等级2唱歌支援；敌对族群的丙愿意交流，本次门槛4，两人的权重为1。

| 步骤 | 输入与计算 | 结果 |
| --- | --- | --- |
| 第一轮提示唱歌 | 甲3 + 乙2 = 5，匹配系数1 | 5 ≥ 4，进度1 |
| 乙动画重复触发 | 同session/round/actor已入账 | 不重复加到7 |
| 第二轮提示摆姿态 | 甲有等级3；乙不具备合法姿态支援；门槛3 | 3 ≥ 3，进度2，成功 |
| 成功提交 | 丙尚未被此关系目标打动，提交一次 | 新增1个结交进度，记录丙已被打动 |
| 同一成功回调重发 | outcome已提交 | 不再新增 |
| 累计达4个不同目标 | 应用本例关系阈值 | 阵营关系升为盟友；入队仍需空位与同意 |

若第一轮错误地回应跳舞，`5 × 0=0 < 4`，该轮失败；强度再高也不能代替所要求的动作类型。若乙在唱歌效果提交前失去发声部件，该贡献因bodyVersion失效被拒绝，只剩甲3，达不到4；已完成且已提交的上一轮结果不回滚。

```text
SubmitContribution(event):
    validate session/generation/round, deadline and active participant
    validate event.plan and body/controller stamp at actual effect commit
    key = (sessionId, generation, roundId, actorId)
    if key already accepted: return Duplicate
    commit contribution once using session owner

FinishRound(session):
    freeze contributions after deadline or declared completion
    score according to configured formula; update progress once per round
    if required progress reached: CommitOutcomeOnce(Succeeded)
    else if failure budget exhausted: CommitOutcomeOnce(Failed)
    else: advance roundId and publish next prompt

CommitOutcomeOnce(result):
    persistent relationship owner deduplicates outcome by session identity
    if new success and target qualifies as not-yet-impressed:
        update individual record and relationship progress atomically
    record failed/cancelled results according to configured policy
```

动画事件不是长期关系账本的主人；它只请求提交当轮贡献。若存档/联网支持重放，去重与关系提交应处于持久事务，而非只用内存布尔值。

## 5 灵魂、外观与族群关系：你的游戏需要另定政策

Spore手册将互动后果关联到物种；用户的灵魂可换肉体，身份维度更丰富。建议独立保留：

| 关系 | 主人 | 换体时的默认建议 |
| --- | --- | --- |
| 熟人信任 | 对方对SoulId或可识别身份的记忆 | 识别成功时保留；未识别时保持不确定 |
| 外观第一印象 | 对BodySpeciesId的先验态度 | 根据新外观重新估计 |
| 阵营声望 | `(observerFactionId, subjectFactionId)`账本 | 不因借用身体自动改变 |
| 当前同伴契约 | SquadId、成员同意与容量 | 保留成员身份，更新能力和角色 |

没有辨认灵魂的能力时，NPC可先按外观估计敌友；看到可信证据后更新身份信念。灵魂法术可以改变当下情绪，但是否永久修改信任要作为单独效果声明，有来源、时效和解除规则。

同物种不必自动同阵营，盟友不必都是熟人；否则偷到一具敌方肉体就会把历史仇恨和所有同伴关系一起抹掉。此处是面向用户设计的政策建议，没有声称Spore支持灵魂识别。

## 6 实际检查、未知与验证路径

检查见[自研算例](checks/verify_group_social_examples.py)：当轮去重、旧轮次/断肢后的贡献拒绝、关系结果去重与数值演算。它不是原作社交实现，也没有验证实际动画事件和存档事务。

原作值得继续追：社交会话的创建/销毁、出题动作选择、结束条件、同伴参与与加成、个体成功到关系管理器的提交，以及三种Impress门槛的实际数据。需要函数交叉引用、相关资源解码或陆地场景观察；本轮没有可用原生provider，因此未恢复计分函数、运行游戏或验证具体常数。风险：社区版本差异、公开规则与本机版本差异，以及将本页自研参数误当原作参数。
