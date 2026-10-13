# 10 部件能力聚合与技能资格

[目录](README.md) · [动作绑定](03-core-structures-and-frame-pipeline.md)。本轮新增证据集中在身体能力如何表示；本机实际聚合函数仍未知。后半是针对用户拼装游戏的独立规格。

后续25已取得实际技能等级/模板配置；[46](46-capability-contributions-body-statistics-and-executor-qualification.md)新增四份普通手/嘴贡献，对照最高值/总量/提供者与本地执行资格。本页末尾的未做与范围属于初版，不扩大为新篇结果；本机聚合消费者仍未恢复。

## Spore 新证据

官方论文说明每个 rigblock 赋予属性与等级，举有 bite +3、speed +2 等例子；没有说明同类部件合并公式。[Maxis，Spore API 论文 §3](https://thevioletpiece.com/spore/SIGGRAPH09_SporeAPI.pdf)。这里的加号不能直接解释成全部数值线性叠加。

社区原始属性字典同时声明最大值与总和值范围，以及动画资源等字段。[SporeModder-FX properties.txt，约 L884–928、L2262–2326](https://github.com/Spore-Community/SporeModder-FX/blob/master/Documentation/properties.txt)

```text
modelCapabilityBite                     int32
modelCapabilityStrike                   int32
creatureAbilityRequiredCAPs             uint32s
creatureAbilityExcludedCAPs             uint32s
creatureAbilityRequiredCAPsMaxValueRange vector2s
creatureAbilityRequiredCAPsSumValueRange vector2s
creatureAbilityAttackStatSumValueRange   vector2
creatureAbilitySocialStatSumValueRange   vector2
creatureAbilityLevelMultiplier          float
creatureAbilityAnimationIDs             uint32s
```

这些是社区格式声明，不能证明当前 Strike/Bite 资源怎样设置或解析者怎样执行范围比较。社区物种资料还同时保存 mAttackSum、mAttackMaxLevel、mBiteLevel、mStrikeLevel、主动/被动能力与嘴/手索引。[cSpeciesProfile.h，约 L68–175](https://github.com/Spore-Community/Spore-ModAPI/blob/master/Spore%20ModAPI/Spore/Simulator/cSpeciesProfile.h)

结论是**必须分开研究总量、最高等级、技能等级和参与部件**；不能声称所有能力求和、所有能力取最大，或最强部件一定是实际攻击部件。结构容量也不等于游戏等级上限。

## 独立规格：保留多个统计和贡献来源

```text
PartContribution { partId, capabilityId, level, capacity, functionState }
CapabilitySummary {
    capabilityId, providers[]
    providerCount, maxLevel, sumLevel, totalCapacity
}
AbilityRequirement {
    requiredCapabilities[], excludedCapabilities[]
    minimumProviderCount?, minimumMaxLevel?, minimumTotalCapacity?
    structuralRequirement?, executionModeRequirements[]
}
```

我们只统计仍连接在该身体上、功能正常的部件。损坏部件保留身份和诊断，但不继续贡献功能值。机械连接、肌肉/神经/能量通路是否也需要成立，由能力的 structuralRequirement 定义；不能只检查所有部件是否位于同一个数组。

```text
DeriveOwnCapabilitySummary(body):
    summaries = empty map
    for part in body.parts:
        ValidatePartContribution(part)
        if !part.attached or !part.functional:
            record ExcludedProvider(part.id, reason)
            continue
        for contribution in part.capabilities:
            group = summaries[contribution.capabilityId]
            group.providers.add(contribution with partId)
            group.providerCount += 1
            group.maxLevel = max(group.maxLevel, contribution.level)
            group.sumLevel += contribution.level
            group.totalCapacity += contribution.capacity
    return summaries and provenance
```

对同一部件重复登记同一贡献应校验失败或由明确合并规则处理，不默认算两次。等级/容量的单位、非负约束和空集合结果在能力定义中声明；未定义能力与已定义但当前没有提供者是不同诊断。

## 构造算例

三只攻击手的等级为 `{1,2,3}`：最高等级=3、总等级=6、提供者数=3。它们分别回答强度门槛、累计指标和可参与数量。定义技能 A 要求最高等级≥3，技能 B 要求至少两只健康手，则两者都可进入资格集合。

等级 3 的手断掉后，结果为最高等级=2、总等级=3、提供者数=2：A 不再满足资格，B 仍满足。该规则是自研演算；没有恢复 Spore 的断肢或聚合公式。

## 对拼装游戏的建议

每种数值使用自己的合并契约：尖牙品质可按最高提供者评估，发电器官可按容量和有效连接统计，多手连击可按执行部件数定义。不要用同一规则强行合并移动、感知、护甲、供能和技能等级。

额外手可以提供另一个攻击通道或减少占用冲突，不必总是提高技能等级。是否允许并行施法、是否共享冷却、是否提供多段命中，是三个独立玩法选择。基于你的拼装目标，建议最初保留“额外执行部件”的价值，同时显式限制行动并发；具体增益需要实际平衡测试。

技能资格只是第一关。技能可以已解锁但冷却中；具有爪击能力也不表示当前任何爪都能触及目标。执行计划仍需要选择实际部件，详见 11。

灵魂技能不应塞入肉体能力统计后丢失来源。保持灵魂 learnedAbilityIds，再由各执行模式要求身体贡献；二者的可用行动在 13 合并。

## 状态与验证边界

已答：官方确认部件赋予等级；社区格式同时表示最大值/总和值条件。部分回答：技能资格的表示入口。未答：本机各能力生产函数、范围端点、等级上限、某技能配置和最高部件与实际攻击者的关系。

未做：原生反编译、能力资源解码、原游戏组合对照。本机身份沿用 00，新增来源没有建立与其 ABI 的逐项对应。风险：把社区声明、玩家经验和自研演算误当成一套原游戏公式。
