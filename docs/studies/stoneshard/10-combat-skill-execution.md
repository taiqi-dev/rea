# 战斗技能执行：以 Taking Aim 为例

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [Buff 与效果生命周期](11-buffs-and-effects.md)

本文解释技能配置如何进入执行流程，以及一次使用怎样连接资源消耗、冷却、实体或 Buff。这里的 Taking Aim 是本机制品中的 `Taking_Aim`，不依赖其他版本的百科数值。技能选择与未装填弩的限制见 [敌人技能与协作](05-enemy-skills-cooperation.md)，公共回合和伤害结算见 [战斗回合与伤害](14-combat-turns-and-damage.md)。

调查只读取安装制品，没有启动游戏、修改存档或验证实战结果。下面的伪代码是重新组织的行为说明，不能作为原游戏源码使用。

## 1. 模块边界与已确认结果

技能不是一个函数包办所有事情。已确认的职责至少包括：

| 层次 | 真实入口或数据 | 职责与证据限制 |
| --- | --- | --- |
| 配置 | 分号分隔技能表、`scr_create_skill_map` | 指定目标方式、资源、冷却、执行对象等；表内值与最终运行时值要分别看 |
| 可用性 | `scr_unit_skill_can_use`、技能缓存 | 更新缓存，再返回指定技能缓存的索引 1；这里没有完整重算所有资源条件 |
| 玩家控制器 | `o_skill` 与 `o_skill_taking_aim` | 有 GUI 继承、描述与点击执行事件；不是每个控制器实例都等同于伤害实体 |
| 敌人执行 | `scr_enemy_cast_spell` | 读取当前 `skill`，计算部分资源/冷却参数，按目标和类型分派 |
| 瞬时技能实体 | `scr_cast_spell` | 可把字符串转换为资源索引，调用 `instance_create_depth`，再绑定 owner、target 等 |
| 状态效果 | `scr_effect_create` | 创建和登记数值状态/Buff；名字里的 effect 不意味着仅仅是粒子动画 |
| 回合与清理 | `scr_states_duration_dec`、Destroy/CleanUp | 按条件减持续值，过期销毁，解除单位 Buff 列表登记 |

已经恢复 Taking Aim 的实际配置行、实际 Buff 对象及部分效果公式，且共享创建、持续递减、销毁、列表清理链都有指令证据。尚未完整解释所有技能前置检查、被动修正、冷却修正和特殊目标分支，因此不能把局部流程写成所有技能统一的完整战斗规则。

## 2. Taking Aim 的真实配置

EXE 中存在同组初始化字符串：表头 VA `0x145e4bdc0`，Taking Aim 行 VA `0x145e4d610`。行被字符串构造调用 `0x140bd8e6a` 登记到槽 `0x14980d1b0`，构造地址 `0x140bd8e5c`。表头与行按分号位置对齐，得到：

| 字段 | 表内原值 | 当前可以解释到的层次 |
| --- | --- | --- |
| 首列技能键 | `Taking_Aim` | 技能身份 |
| `Object` | `o_b_taking_aim` | 执行对象是实际 Buff 对象 |
| `Target` | `No Target` | 无须指定外部目标；执行入口另有把目标设为施法者的分支 |
| `Range` | `0` | 配置值；不等于强化后武器射程 |
| `KD` | `1` | 基础冷却配置，尚不能替代最终冷却修正结果 |
| `MP` | `4` | 基础资源配置，存在消耗修正 |
| `Duration` | `1` | 传入持续值的配置基础，不等于最终计数器一定为 1 |
| `Class` | `skill` | 区分普通技能与法术的依据之一 |
| `Branch` | `ranged` | 技能分支 |
| `metacategory` | `weapon` | 元分类 |
| `Maneuver` | `1` | 机动类标记的表内值 |
| `Attack` / `Stance` / `Charge` / `Spell` | 空值 | 保留空值，不能自行改成数值零 |
| AOE、移动等字段 | `0` | 表内没有范围宽长或移动标记 |

这是配置本身的确认。数据加载时字段会转成地图键，执行代码又使用 `duration`、`main_spell`、`max_KD` 等键；不要把配置表的大小写、派生键与最终单位字段混为一物。`scr_skill_atr` 实际调用 `scr_create_skill_map`，随后读取 `MP` 设置 `MPcost`，读取 `max_KD` 设置 `maxKD`，证据分别在 `0x14172bcce`、`0x14172bdd9–0x14172be01`、`0x14172bd15–0x14172bd3d`。

数据证据为本地 [Taking Aim 配置与完整表头](../../../_reference/stoneshard-study/third-taking-aim-table.json)。该文件未版本化，本文已保留必要字段，不要求读者拥有本地调查缓存。

## 3. 执行前：技能缓存不是技能结果

`scr_unit_skill_can_use` 的局部算法可以按证据重述为：

```text
canUse(unit, skillKey):
    updateSkillCache(skillKey)
    entry = unit.unit_skill_cache[skillKey]
    return entry[1]
```

缓存更新调用位于 `0x1401b330d`，读 `unit_skill_cache` 位于 `0x1401b3358`，索引 1 的提取位于 `0x1401b33a2–0x1401b33f0`。四元组的评分、可用、额外量、目标结构见 05。

边界在于：缓存允许与真正执行成功是两个阶段。目标可能失效，单位资源可能变化，特殊技能对象还会再检查装备。例如 Taking Aim 的 Buff 更新事件会拒绝“目标为玩家且当前武器不是射击武器”的情况；这不能倒推出所有敌人使用它之前都执行了同一检查。

## 4. 敌人执行中的资源结算

`scr_enemy_cast_spell` 入口为 `0x14185e970`。它读取当前单位的 `skill` 地图，提取 `idName` 并转换资源索引，读取 `Target`、`Class`，并处理不同分类、被动和目标分支。

已恢复普通技能消耗的一段实际算式：

```text
localCost = gameRound(
    skillMap["MP"] * (
        unit.Skills_Energy_Cost / 100
        + unit.Abilities_Energy_Cost / 100
    )
)
```

证据是 `Skills_Energy_Cost` / `Abilities_Energy_Cost` 读取 `0x1418602f1` / `0x141860307`；除以 100 位于 `0x141860366` / `0x14186037d`；加法与乘法位于 `0x141860541` / `0x1418605b7`；`math_round` 位于 `0x14186066a`。`0x140016bc0` 已追到“复制输入再除以给定浮点数”的助手，不能误解为减法。

这里的两个字段是在本段直接相加的百分比量。不能依据名称把它们写成 `1 - reduction / 100`。法术分支另使用 `Spells_Energy_Cost`，本文不把它套入普通技能公式。

后续还有被动等分支，可以继续改变局部 `cost`。完成这一轮条件处理后，入口在 `0x141865863` 调用 `scr_set_kd`，再于 `0x141865922` 计算 `MP - cost`，于 `0x141865977` 调用 max，最后写回 MP：

```text
unit.MP = max(unresolvedFloorSlot, unit.MP - finalLocalCost)
```

下限参数来自运行时槽 `0x149881310`，静态初值没有完成绑定，本文保留未知。不能因此声称下限一定是 0，也不能从扣除后的下限保护推出“资源不足仍允许使用”；使用许可是在其他层判断的。

`gameRound(x)` 的普通有限数规则经本机助手核准为：

```text
sign(x) * floor(abs(x) + 0.5)
```

半值远离零，不能直接用某些语言默认的银行家舍入替代。

### 一个构造演算

只为演示已恢复的消耗片段，假设 Taking Aim 使用表内 MP=4，`Skills_Energy_Cost=100`、`Abilities_Energy_Cost=0`，且后续没有被动改变该量：

```text
localCost = gameRound(4 × (100/100 + 0/100)) = 4
若使用前 MP=12，则写回 max(F, 8)
```

若技能消耗字段为 80、通用能力字段为 10，同样前提下局部消耗为 `gameRound(3.6)=4`。这些单位属性是人为构造输入，不是已读取的强盗弩手当前状态；F 未恢复，最终值也要受其他真实分支约束。

## 5. 冷却写入与真正执行对象

`scr_set_kd` 入口 `0x141753040` 读取单位 `map_skills` 查找相应技能地图；存在值检查后，最终通过 `ds_map_replace` 写入调用者选定的键和冷却量。替换调用 `0x1417538c3` 使用三个参数，键来自函数第二参数，值来自局部冷却量。敌人调用前的键绑定为 `KD`，位置 `0x141865786`。

因此已确认“使用会进入写冷却入口”，而非“只查询冷却”。`Cooldown_Reduction`、基础 `KD`、局部倍率都参与较早计算；完整被动与倍率链未恢复，本文只把 Taking Aim 的 `KD=1` 作为基础配置。冷却递减的公共调用见 14，不把写入与递减合成一个未经核准的公式。

执行对象分成两条重要路径：

1. `scr_cast_spell` 入口 `0x14185bce0` 可把字符串经 `__asset_get_index` 转为对象资源，调用 `instance_create_depth`，再写 `target`、`owner`、`point`、`target_x/y`、`is_crit`、`name`、`damage`，最后调用 `scr_set_startcast`。这里只确认字段绑定和创建过程；每个实体如何移动、命中和造成伤害要查相应对象事件。
2. 状态对象进入 `scr_effect_create`。敌人执行中，`No Target` 的局部分支明确读取施法者 `id` 并作为选定目标，地址 `0x141866e82–0x141866f07`，然后在 `0x141867237` 调用 `scr_effect_create`。外部目标分支与反射分支会改变目标，不能把这一次自我目标规则推广到所有技能。

Taking Aim 配置直接指向 `o_b_taking_aim`，所以它适合解释“一个技能使用产生状态效果”的案例，而不必假造箭矢、攻击伤害或命中判定。敌人执行的对应局部分支读取当前技能地图的 `duration`，调用 `0x14186656d`，把结果保存在局部 `rsi`；状态创建调用 `0x141867237` 的第二参数正是这个量。前置比较和特殊对象条件仍要成立，不能把调用存在当作每次选择成功的动态证据。

### 玩家控制器的另一条可见连接

`o_skill.Other13` 有计算持续值、写 `buff_name` 与 `buff_duration`、设置 `alarm[3]=1` 的分支，地址 `0x144564e04–0x144564ee3`。之后 `o_skill.Alarm3` 按以下已恢复参数调用：

```text
effectCreate(
    buff_name, buff_duration,
    owner, owner,
    1, true, is_crit,
    undefined, undefined
)
```

调用 VA `0x14454f9cc`。前两个 owner 分别进入 target 和 owner 参数。该分支连接“技能控制器暂存请求”与“延迟创建状态”。未完整追所有 Other13 分支，不能声称每次 Taking Aim 使用都必然经这一个玩家事件，也不能把 alarm 值 1 当成一个游戏回合。

## 6. Buff 生效与结束的连接

`data.win` 确认 `o_b_taking_aim` 为 OBJT 6091；对象的 Create、Alarm2、Other15、Other16、Other12 均存在。其继承链进入 `o_buff_maneuver → o_physical_buff → o_buff → c_buff → o_modificators → c_abstract_states`，不是靠前缀猜出的分类。

实际 Create 写 `stack=1` 和 `max_duration=2`；实际 Other15 写属性地图，包括命中、武器伤害和额外射程字段。共享创建函数绑定持续、目标、来源并将实例加入 target.buffs。共享回合函数按阶段递减持续，低于 1 触发实例销毁；Destroy 从单位列表移除并标记属性需要重算。详细公式、持续补偿分支、无射击武器时的主动结束、数值地图汇总与清理见 11。

这条连接已经达到“资源/冷却入口 → 配置状态对象 → 真实属性数据 → 有条件回合递减 → 销毁解除登记”。仍没有动态证据证明具体敌人在某一次战斗里选择并完整执行了它，也没有恢复全部特殊分支。该区别决定了本报告可以用来设计测试规格，但不能作为实测战斗日志。

## 7. 行为规格伪代码

下面保留未恢复参数，不把局部分支伪装成完整原代码：

```text
executeSelectedSkill(unit, selectedSkill):
    require callerHasEstablishedPermission       # 调用者前置条件，完整规则未恢复
    config = selectedSkill.runtimeMap
    asset = resolve(config.idName)
    category = config.Class
    targetMode = config.Target

    cost = calculateObservedCostBranch(category, unit, config)
    cost = applyUnresolvedPassiveBranches(cost)
    cooldown = calculateUnresolvedCooldown(config, unit)
    setCooldown(config, "KD", cooldown)
    unit.MP = max(unresolvedMPFloor, unit.MP - cost)

    if reachedStateCreationBranch:
        recipient = unit.id if targetMode == "No Target" else resolvedTarget
        recipient = applyReflectionOnlyWhenItsBranchIsReached(recipient)
        return effectCreate(asset, resolvedDuration, recipient, unit.id, ...)
    if reachedSkillEntityBranch:
        entity = createSkillEntity(asset, ...)
        bind(entity.owner, entity.target, entity.point, entity.is_crit, ...)
        return entity
    return resultOfOtherConfirmedOrUnresolvedBranch
```

这不是建议自研照搬“先扣资源再创建”的失败处理方式。自研可以先完成请求验证并提供明确失败结果，再原子提交资源和冷却，避免实体创建失败但扣费已完成；这是独立设计选择，尚未证明原游戏如何回滚失败。

## 8. 证据位置与确切未知

| 事实 | 静态位置 | 强度 |
| --- | --- | --- |
| Taking Aim 表头/配置行 | `0x145e4bdc0` / `0x145e4d610` | 原始字符串与列位置确认 |
| 技能缓存可用字段 | `0x1401b31e0`，提取 `0x1401b33f0` | 局部数据流确认 |
| 普通技能消耗片段 | `0x1418602f1–0x14186066f` | 字段、除法、相加、乘法、舍入确认 |
| MP 扣除与下限 | `0x1418658b1–0x141865991` | 运算确认，下限槽值未知 |
| 写入 KD | `0x141865863`、`0x1417538c3` | 调用与地图替换确认，完整值修正未知 |
| 创建技能实体 | `0x14185c6ea`、`0x14185c771–0x14185cb0b` | API 与字段绑定确认 |
| 自我目标状态创建 | `0x141866e82`、`0x141867237` | 局部目标分支和调用确认 |
| 玩家延迟 Buff 创建 | `0x144564e04`、`0x14454f9cc` | 条件分支与九参数确认 |
| Taking Aim 对象 | OBJT6091，记录偏移 11,376,216 | 对象身份、继承与事件确认 |

本地证据：[函数与调用索引](../../../_reference/stoneshard-study/third-skill-native.json)、[对象元数据](../../../_reference/stoneshard-study/third-skill-object-metadata.json)、[敌人执行解码](../../../_reference/stoneshard-study/third-skill-disassembly/gml_Script_scr_enemy_cast_spell.txt)、[玩家状态创建事件](../../../_reference/stoneshard-study/third-skill-disassembly/gml_Object_o_skill_Alarm_3.txt)。这些可再生成调查产物未版本化，正文独立保留结论与地址。

仍未知：全部资源不足门槛与错误结果；所有被动修正；最终冷却和下限槽初始化；执行中失败的回滚；每种技能伤害实体的完整算法；实际一次玩家/弩手使用的事件时序；UI 展示数值是否与每次实际效果一致。

## 9. 可借鉴的独立结构

可借鉴的是职责拆分：配置描述能力、选择层返回意图、执行层确认资源与目标、效果层管理独立状态、回合层推进持续和冷却。我们自己的实现宜用明确的 `SkillDefinition`、`ExecutionRequest`、`EffectInstance` 和可诊断的失败结果，保留目标与来源身份。

不需要复用 GameMaker 的 GUI 对象继承、数字对象索引、特殊哨兵或字符串字段名称。状态效果和可视动画可以是两个相互引用但独立清理的对象；技能公式、资源曲线、持续时机与资产应按自己的游戏需求重新设计。本文未复制游戏源码或资产，也未实现任何游戏运行修改。
