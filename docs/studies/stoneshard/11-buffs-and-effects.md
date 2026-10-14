# Buff、临时效果与生命周期

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [战斗技能执行](10-combat-skill-execution.md)

属性消费者和临时状态的增量见 [45 装备与Buff属性流水线](45-equipment-buff-attribute-pipeline.md)，补组合查询、命中钳制和即时重算门禁；本篇保留状态创建与持续生命周期的证据范围。

本文使用 Taking Aim 的实际 Buff 对象解释状态创建、属性数据、汇总、回合更新和过期清理。召唤的持续状态是同一共享机制的另一种消费者，见 [召唤单位](12-summoned-units.md)；公共回合入口见 [战斗回合与伤害](14-combat-turns-and-damage.md)。

所有结论来自本机 EXE 和 `data.win` 的静态读出。没有运行游戏、修改游戏或存档。行为伪代码为我们独立整理的说明，不能用于复制或出售原游戏代码。

## 1. 数值状态、界面状态与视觉表现

本制品的状态系统使用实际实例，实例带 `target`、`owner`、`duration`、`have_duration`、`stack`、`stage`、`data` 等字段。目标单位有 `buffs` 列表、`buffer_buff_data` 汇总地图以及 `stats_is_change`、`buffs_is_change` 标记。

Taking Aim 的状态继承路径为：

```text
o_b_taking_aim (6091)
  → o_buff_maneuver (9092)
  → o_physical_buff (6051)
  → o_buff (6050)
  → c_buff (5900)
  → o_modificators (5899)
  → c_abstract_states (5897)
  → o_guiInteractive (2679)
  → c_GUI (4018)
```

数字是 `data.win` 对象资源索引。该链说明状态包含界面表现的共同基类，不表示数值效果仅存在于 UI。真正的数值证据是属性地图写入、汇总加法和持续递减。

| 名称/入口 | 已确认职责 | 不能仅凭名称得出的结论 |
| --- | --- | --- |
| `scr_effect_create` | 可创建 Buff，绑定 target/owner/duration，加入 target.buffs | 不是所有 effect 都只是视觉特效 |
| `scr_buff_buffer_add` | 把状态 data 的键值加入提供的汇总地图 | 不能据此证明最终伤害公式全部使用加法 |
| `scr_temp_effect_update` | 本次 Taking Aim 明确传入抗性字段与数值参数 | 不是因为 temp/effect 就能叫粒子效果；更新内部语义未全部恢复 |
| `scr_skill_call_buff` | 给选定状态实例写上下文并分派 Other14 | 不能当作“添加 Buff”的同义函数 |
| GUI 动画、音效调用 | Taking Aim Alarm2 存在 GUI 动画与音效调用 | 动画帧、alarm tick 和游戏回合不是同一单位 |

## 2. 创建时绑定什么

共享 `scr_effect_create` 入口 `0x1411b6b00` 包含多种对象和免疫分支。这里的字段绑定发生在已经进入创建路径后：

| 创建参数位置（从 0 开始） | 写入字段 | 指令位置 |
| --- | --- | --- |
| 0 | 待创建对象/状态类型 | 调用方和资源处理决定 |
| 1 | `duration` | `0x1411b9743` |
| 2 | `target` | `0x1411b968b` |
| 3 | `owner` | `0x1411b96e7` |
| 4 | `stage` | `0x1411b979f` |
| 6 | `is_crit` | 字段选择 `0x1411ba096`，读取参数 `+0x30` |

参数 5、7、8 的完整业务含义尚未恢复，不根据真值或空值补上名称。普通玩家控制器有实际九参数调用：`(buff_name,buff_duration,owner,owner,1,true,is_crit,undefined,undefined)`，见 10。

基础 `c_abstract_states.Create` 写 `have_duration=true`，地址 `0x1443533ce`，其值是 type `0xD`、数值 1。共享创建检测 `duration == -1` 时写 `have_duration=false`，地址 `0x1411b985a`。因此无持续时间状态与“剩余时间为零”是不同状态。

创建期间还会改变持续值：

- 存在对象祖先、免疫、Fortitude、舍入、持续补偿等分支，不能把传入值直接叫最终持续回合数。
- 一个已明确的局部分支在 `target.buffs_is_change` 为假、持续值为非负且 `have_duration` 真时，执行 `duration += 1`。检查位于 `0x1411b9c31–0x1411b9cf5`，普通数值加一位于 `0x1411b9ef8`；需要先到达该分支，其他类型分支可能转向不同处理。
- `max_duration == 1` 的比较位于 `0x1411b9da5`，等值分支转向舍入路径；不能把所有状态的时间补偿当成统一加一。
- `target.buff_end_turn` 为真时，还可能置 `is_next_turn=true`，但有对象例外。检查位于 `0x1411b9f1d–0x1411b9fde`，标记写入 `0x1411ba022`。

成功路径将状态实例 id 加入 `target.buffs`；实际 `ds_list_add` 调用在 `0x1411ba2f5`，API ID 加载在 `0x1411ba2cb`。这一登记才使单位侧的汇总和持续更新能找到状态。

## 3. Taking Aim 的状态数据和边界

实际对象 `o_b_taking_aim` 的 Create 入口 `0x144477c10` 经过继承初始化、调用 `scr_buff_atr`，然后写：

| 字段 | 值 | 证据 |
| --- | --- | --- |
| `stack` | 1 | 字段选择 `0x144477d36`，载荷 `0x144477d64` |
| `buff_snd` | -4 | 字段选择 `0x144477d78`，载荷 `0x144477da6` |
| `max_duration` | 2 | 字段选择 `0x144477dba`，载荷 `0x144477de8` |

`buff_snd=-4` 是这里的初始化哨兵，不把它解释成声音资源 4。技能配置的 `Duration=1` 与状态的 `max_duration=2` 属于不同层，不能任选其中一个写成“瞄准固定持续两回合”。

Other15 入口 `0x144479210` 会调用继承事件，再检查 target 是否玩家。若目标为玩家且射击武器检查为假，则调用销毁入口并结束；地址 `0x14447951b–0x1444795b5`，销毁 `0x14447b288`。非玩家绕过这一玩家武器检查，不能声称它证明敌人也会以同样方式检测武器。

进入效果计算后，从 **owner** 读取属性，不是自动从 target 取值：

```text
P = owner.PRC
R = owner.ranged_skill_learned
hitContribution = 59 + R
weaponDamageContribution = P
bonusRangeContribution = 10
```

Other15 清空状态的 `data` 地图，然后写入以下真实字符串键和值：

| 键 | 写入值 | 数据流与写入 VA |
| --- | --- | --- |
| `Hit_Chance` | `59 + ranged_skill_learned` | 乘 1 `0x14447966c`，加 59 `0x14447969a`，写 `0x144479a9c` |
| `Weapon_Damage` | `owner.PRC` | 读取 `0x1444795d8` 保存局部；写 `0x144479b3d` |
| `Bonus_Range` | 10 | 常量 `0x144479b72`，写 `0x144479c00` |

地图写入经过运行时 `0x1451e8870`。字符串键不是通过相邻内存猜出的：本轮定位了它们的初始化构造，槽分别为 `0x1498ec980`、`0x1498ec990`、`0x1498ec9a0`。

这三个数字是状态贡献数据，不能直接声称“最终命中率是 59+R%”“造成 P 点额外伤害”或“射程增加十格”。字段下游可能采用百分比、倍率、界限、武器基础属性或其他效果；最终单位与伤害管线没有在本文完整解出。

Other15 还会计算 `3×STR`、`3×AGL`、`3×PRC`，根据敌人计数写其他机会值，并有被动开启条件。一个被动分支写 `Armor_Piercing=5` 和 `Bodypart_Damage=5`，写入分别在 `0x14447a447`、`0x14447a538`；被动条件调用位于 `0x14447a37e`。本文没有把未核准的被动对象身份替换成技能名。

同一事件还向 `scr_temp_effect_update` 传入 `Physical_Resistance=-5`，以及条件分支中的 `Stun_Resistance=-5`、`Knockback_Resistance=-5`。调用为 `0x14447ae3c`、`0x14447afb8`、`0x14447b119`，另有数值参数 4 和 2。第10节续查已将本入口的4/2分别接到持续请求与同source+atr匹配数量限制；不能称为未经修正的可见四回合或主Taking Aim状态stack上限。

### 一个可核算的例子

假定状态 owner 的 `PRC=12`、`ranged_skill_learned=3`，已通过适用分支且忽略未解释的被动效果：基础地图贡献为 `Hit_Chance=62`、`Weapon_Damage=12`、`Bonus_Range=10`。这是实际指令的构造演算，输入属性不是实测强盗数据，结果也不是最终战斗属性。

## 4. 汇总：本段明确采用逐键加法

`scr_enemy_buff_buffer` 入口 `0x140fe3cf0` 首先清空单位 `buffer_buff_data`，调用位置 `0x140fe3f09`。随后遍历 `buffs`，在符合实例和分支条件时调用 `scr_buff_buffer_add`，位置包括 `0x140fe4380`、`0x140fe48c0`。这支持“从活动状态重建汇总”，而不是无限地每帧往旧值累加。

`scr_buff_buffer_add` 入口 `0x140fe7cb0`：

1. 通过 `ds_map_find_first`、`ds_map_size`、`ds_map_find_next` 遍历当前状态 `data`。
2. 读取该状态 `data[key]`，再从传入的目标地图读取同一 key。
3. 对目标值进行 undefined/空指针处理；缺失值采用本段的零替代路径。
4. 执行相加，再以 `ds_map_replace` 写回目标地图。
5. 另处理 source、duration 等来源记录，具体调试/来源登记结构未完全恢复。

主要相加在 `0x140fe87d0`，写回调用在 `0x140fe8870`，API ID 选择 `0x140fe884e`。可以重述为：

```text
rebuildBuffContributions(unit):
    clear(unit.buffer_buff_data)
    for eligibleBuff in unit.buffs:
        for key in eligibleBuff.data:
            old = missingAsZero(unit.buffer_buff_data[key])
            unit.buffer_buff_data[key] = old + eligibleBuff.data[key]
```

例如 Taking Aim 贡献命中 62，另一构造状态贡献 -10，单看这个已恢复汇总入口，结果为 52。不能进一步推出最终命中率一定为 52%，也没有证明所有数据键都以同一方式进入最终属性。值如何成为倍率、加法项或对基础属性的百分比，由后续属性计算拥有。

当前只确认 `stack`、`stage` 字段存在及相关条件，没有恢复“重复施放 Taking Aim 会无限叠加层数”的规则。`scr_buff_change` 有查同类状态、stack、duration/max_duration、stage_restore 分支，且调用 `scr_modifer_duration_change`，但各状态的完整合并策略未核准。自研规格应把叠层、刷新持续、替换与拒绝分别定义，不能从 `stack=1` 推导上限或叠加方式。

## 5. 持续值的两阶段更新

共享入口 `scr_states_duration_dec` 的真实 VA 是 **`0x141ae5c20`**。参数可恢复为：

```text
statesDurationDec(unitSelector, phaseFlag, decrement=1)
```

第一参数用于选择单位；第二参数保存到单位 `buff_end_turn`；第三参数未提供时初始化为 1，证据 `0x141ae5e4a–0x141ae5e54`，三参数路径可覆盖这一量。

入口读取单位 `buffs`；单位 `is_delete` 为真有提前返回假值的路径。遍历时跳过无效值/空指针，并使用实例选择机制处理有效状态。已确认的核心局部行为：

```text
for eligibleState in selectedUnit.buffs:
    if phaseFlag:
        if state.have_duration:
            if not unresolvedInstanceFilter or filterMatches(state.id):
                state.duration -= decrement
                if orderedLess(state.duration, 1):
                    destroyThisStateWithEvents()
        state.is_next_turn = true
    else:
        if state.is_next_turn:
            dispatchOther10(state)
            state.is_next_turn = false
```

减法 `0x141ae673e`；比较 `0x141ae675f`；销毁 `0x141ae6799`；设置下一阶段标记 `0x141ae67d8`；Other10 分派 `0x141ae6848`。filter 的完整产生条件仍未知，伪代码保留它，不能说每次 phase 真都减所有 Buff。

比较助手 `0x140089b20` 使用通用比较结果，只有结果不是 unordered 哨兵 -2 且为负才返回真。因此是有序 `<1`，不是 `<=1`。持续 1 减 1 得 0 后销毁；持续 2 减 1 得 1 时不在这一门槛销毁。非整数时间也要按该门槛处理，不能自行替换成“只在恰好等于零时结束”。

`c_buff.Other10` 又分派 Other16；运行时分派助手 `0x1451ef5b0` 直接将 User 索引加 10，事件类型设为 7，故传 0 是 Other10、传 6 是 Other16。这个链区分“持续递减阶段”和“状态回合事件阶段”。

Taking Aim 的 Other16 在继承事件之后再次检查 target 是玩家、当前武器是否射击类；若不满足则销毁，地址 `0x14447d1b7–0x14447d22b`。这证明 Buff 可因装备变化提前结束，而非只依靠持续耗尽。

### 时间演算的正确边界

如果一个状态**进入递减前的实际存储 duration 为 2**，have_duration=true、phaseFlag=true、filter 允许，且 decrement=1，则依次变成 1、0，并在第二次满足这些条件的调用销毁。

这不等于 Taking Aim 的“玩家可见持续时间固定两回合”。Taking Aim 表内 Duration=1，共享创建存在时间补偿和其他修正，而公共回合何时、对谁调用哪个 phase 要结合 14。本文只证明计数器在明确输入下的变化。

## 6. 过期销毁与解除登记

销毁不是把 duration 写成零后就停止分析。运行时 `0x1451f70d0` 零参数路径选择当前实例，并把“执行销毁事件”的默认值设为真，进入 `0x1451f0a90`。正常有效实例路径最终到 `0x1452fc370`：

1. 防重复销毁标记检查。
2. 分派事件类型 1、编号 0，即 Destroy，`0x1452fc3b6`。
3. 分派事件类型 12、编号 0，即 CleanUp，`0x1452fc3c8`。
4. 标记实例删除并更新运行时计数。

其中也存在延迟/已删除状态分支，本文不把一次调用承诺为任意场景立即释放全部内存。

Taking Aim 没有自己的 Destroy 覆盖，沿继承机制进入公共状态销毁。`c_abstract_states.Destroy` 入口 `0x144354ca0` 在 target 的 `buffs` 列表中找自身 id，只有索引为非负时才 `ds_list_delete`。查索引调用 `0x144354fac`，删除 `0x1443550a4`。随后写 `stats_is_change=true`，`0x1443550de`。

这一层支持的结论是：活动列表中解除状态，并请求属性重算。它没有证明对每个汇总键立刻逐项减去旧值。结合“汇总先清空再重建”的入口，重算可以避免把过期贡献继续留在缓冲里；实际哪个公共入口消费 dirty 标记、在哪一帧完成重算仍未完整闭合。

CleanUp 已证明会由销毁路径分派，但状态地图、GUI 辅助资源的逐项释放没有在本轮全部恢复。不能据此宣布没有内存泄漏，也不能将反汇编中的 RValue 临时析构误当作某个 Buff 游戏逻辑退出。

## 7. 伤害或技能通知不等于添加效果

`scr_skill_call_buff` 入口 `0x140feaa40` 遍历选定状态实例，写 `target`、`value`、`attacker`、`damage` 等上下文字段，再传 User 索引 4 给分派助手，调用 `0x140feb393`，即 Other14。

因此它是“把技能相关上下文送到状态事件”的明确连接。伤害入口也调用它，但静态调用本身不能证明它每次都会创建新 Buff，更不能把 Other14 的每一个处理器叫作伤害加成。实际被动状态可能决定后续效果，需要查相应 Other14。

## 8. 证据与未恢复部分

| 事实 | 位置 | 限制 |
| --- | --- | --- |
| Taking Aim Buff 身份/继承 | OBJT6091，偏移 11,376,216 | 资源存在不等于某次战斗实际运行 |
| stack/max_duration | `0x144477d36` / `0x144477dba` | 不证明重复施放策略 |
| 三个基础数值贡献 | `0x144479a9c` / `0x144479b3d` / `0x144479c00` | 不等于最终命中、伤害或格数 |
| 属性缓冲重建 | `0x140fe3f09`、`0x140fe4380` | 具体调用时机未动态确认 |
| 逐项加法 | `0x140fe87d0` | 下游倍率规则仍待恢复 |
| 有持续/无持续 | `0x1443533ce`、`0x1411b985a` | 创建期还有对象专属修正 |
| 回合减持续并过期 | `0x141ae673e`、`0x141ae675f`、`0x141ae6799` | phase/filter 门槛必须保留 |
| 分派 Destroy/CleanUp | `0x1452fc3b6`、`0x1452fc3c8` | 有运行时延迟删除分支 |
| 从单位列表清理 | `0x1443550a4` | 属性重算完成时间未恢复 |

本地可选证据：[真实 Buff 事件](../../../_reference/stoneshard-study/third-skill-disassembly/gml_Object_o_b_taking_aim_Other_15.txt)、[共享创建](../../../_reference/stoneshard-study/third-skill-disassembly/gml_Script_scr_effect_create.txt)、[持续递减](../../../_reference/stoneshard-study/third-skill-disassembly/gml_Script_scr_states_duration_dec.txt)、[列表清理](../../../_reference/stoneshard-study/third-skill-disassembly/gml_Object_c_abstract_states_Destroy_0.txt)、[Buff 加法汇总](../../../_reference/stoneshard-study/third-skill-disassembly/gml_Script_scr_buff_buffer_add.txt)、[运行时销毁事件](../../../_reference/stoneshard-study/third-skill-disassembly/runtime-0x1452fc370.txt)。它们未版本化，正文已保存必要规则与地址。

确切未知包括：各 Buff 完整叠层/刷新规则；Taking Aim 特定被动身份与全部计数机会公式；数值贡献进入最终属性的单位/倍率；创建期间每个持续修正分支；filter 来源；dirty 标记被消费的完整链；所有数据容器释放行为；与实战动画完全一致的时序。临时效果参数4/2及特定刷新/新增语义见第10节新增覆盖，不能扩大为所有状态的规则。没有运行时验证，因此不报告观测帧率、实际回合长度或战斗数值实测结果。

## 9. 独立设计借鉴

可以借鉴“单位持有活动状态列表，状态保留来源与目标，属性缓冲按活动状态重建，持续推进与效果事件分阶段”的结构。它使叠层和过期有共同入口，来源记录也能解释某个数值从哪里来。

我们的实现应明确不同属性是加法、倍率还是覆盖，按属性定义决定汇总方式；持续时间宜使用明确的回合阶段与 tick 类型，避免界面帧和战斗回合混用。叠层规则、刷新规则、过期事件、清理所有权和失败结果应成为独立测试规格。

例如可以自行规定 Taking Aim 类能力“下一次远程攻击消耗状态”，或者“维持一完整行动窗口”，使用自己的数值和图标。这些都是独立产品规则，并未证明原游戏采用它们。本文提供机制和边界供学习，没有把恢复代码或原游戏资产作为自研实现。

## 10. 第十三轮收敛：重复施加的四种语义不能合并成一个 stack 规则

本节回答自研重构评审提出的窄问题：刷新持续、延长持续、叠强度和按来源并存，各自有什么真实入口。沿用 [第十三轮身份记录](../../../_reference/stoneshard-study/thirteenth-target-identity.json) 对应的 EXE/data.win，SHA256 与前述身份一致；仅做静态续查，不运行目标或读取新存档。第3、4、8节保留早期覆盖的未知，本节新增的是 `scr_temp_effect_update` 与创建助手的限定语义，不把整个游戏的 Buff 规则宣布已恢复。

| 所问策略 | 本轮已闭合实例 | 回答边界 |
| --- | --- | --- |
| 刷新持续 | Taking Aim 请求的临时抗性状态：按 `source + atr` 匹配已有实例，覆盖它的 duration | 是附属 `o_temp_incr_atr`，不是主 `o_b_taking_aim` 的重施规则；刷新可以缩短旧持续 |
| 延长持续 | 同部位流血：在已有实例上加请求，再取 max_duration 上界 | 不重写缓存流血损伤，不增加 stack；不同部位不是同一类型 |
| 叠强度 | 上述临时抗性入口在匹配数量不足时新增同类型实例，各实例各有一份 data 贡献 | 闭合“多实例贡献”，没有闭合任意主 Buff 的 `stack++ → 强度` 规则；最终战斗属性仍有下游处理 |
| 按来源并存 | 临时属性匹配同时比较 source 与 atr；不同 source 不计入同一个匹配数量 | 这里 source 是传入的来源值，未证明所有调用者都用施法者实例 ID；命名技能 A/B 在实战中必定并存未观察 |

### 10.1 真正的临时属性参数及来源归属

`scr_temp_effect_update @ 0x141cd9aa0` 的七参数位置可以沿读写桥恢复为：

```text
tempEffectUpdate(sourceKey, unitSelector, attributeKey,
                 contribution, durationRequest, matchingLimit,
                 calculationFlag)
```

它根据第二参数选择实例，要求选中对象属于 `o_unit`（3804；祖先检查调用 `0x141cda358`；常量槽 `0x149550978`），并要求其 buffs 列表有效（检查 `0x141cda4e5`）。目标不存在、非单位、列表无效等路径不能套用后面的正常算法。

Taking Aim 的一个真实七参数调用 `0x14447ae3c` 是：

```text
(6091, 当前受作用单位.id, "Physical_Resistance", -5, 4, 2, undefined)
```

6091 对应 `o_b_taking_aim` 的对象资源索引；此处 **sourceKey 不是 Taking Aim 状态实例 id，也不是自动等于弩手的 id**。当前受作用单位来自前面的敌人数组选择循环（选择数组项 `0x14447ac5c`，切换上下文 `0x14447acc6`，读取其 id `0x14447ad22`）。数组生成的全部资格不在本节重述；不能把该调用改写成对任意范围内单位无条件施加。

关键常量已按原文件槽核对：来源6091位于 `0x1495b1b68`；贡献−5位于 `0x1495b1b78`；持续请求4位于 `0x1495b1b48`；匹配数量限制2位于 `0x1495b1b88`。因此第3节原先未命名的4/2，在**这个助手入口**分别可以命名为持续请求与匹配数量限制；4仍不是未经修正的最终可见回合数，2也不是主 Taking Aim 的 stack 字段上限。

### 10.2 刷新已有实例，再决定是否额外建一份

助手遍历该单位 buffs，取得有效实例后，先比较 `state.source == sourceKey`，再比较 `state.atr == attributeKey`。这两个比较和跳过路径分别是 `0x141cda7cd / 0x141cda7d4`、`0x141cda826 / 0x141cda82d`。所读循环不是按 owner 查找，也没有在匹配处增加 `object_index == 6171` 判断；规格应保留它实际比较的字段。

正常有限数值路径对**每个**匹配实例执行：

```text
matched = 0
for validState in selectedUnit.buffs:
    if validState.source == sourceKey and validState.atr == attributeKey:
        validState.duration = durationRequest + (not selectedUnit.buffs_is_change)
        matched += 1
if orderedLess(matched, matchingLimit):
    createOneTemporaryAttributeState(...)
```

取得单位阶段标记 `0x141cda844`；取第五参数 `0x141cda871`；布尔反转 `0x141cda8b4`；数值加0或1 `0x141cda8c6`；duration写入 `0x141cda904`。加法助手 `0x14000bd90` 的普通double分支在 `0x14000bdbf..0x14000bdc7` 执行加实参；这是覆盖新计算值，不是加到状态原来的 duration。数量增加的double分支在 `0x141cda98c..0x141cda998`。循环结束后比较 `matched < matchingLimit`（有序条件）在 `0x141cda9e7..0x141cda9f7`，创建调用 `0x141cdac23`。

**刷新不同时覆盖强度。**匹配片段未写旧实例 param/data，也未重跑它的 Alarm2。因此新请求的 contribution 若发生变化，已有实例不会仅因这一段刷新自动采用新值；只有新建实例沿创建链取得本次 contribution。不能把 `tempEffectUpdate` 名称写成“完全更新整个状态”。

匹配限制只用于是否新增这一份：若初始已经有3个匹配实例而限制2，所查循环仍会刷新3个，随后不新增；未见在此清理超量实例。例B从0/1份逐次新增得出的两份边界不能升级为全生命周期最多两份的保证。

**例A：纯刷新，可缩短。**指定有效单位已有两个匹配临时状态，source均6091、atr均Physical_Resistance，旧duration分别9和2，旧param均−5；单位 buffs_is_change=true，本次请求4、匹配限制2。两个duration都变4，matched=2，不新建，两个param仍−5。若同场景阶段标记为false，则刷新写5。这里只演算 stored duration；没有宣称状态还会恰好维持四次玩家行动。

**例B：刷新加一份贡献。**指定原来只有一个相同匹配状态，旧duration=1、param=−5；新请求仍−5、durationRequest=4、matchingLimit=2，阶段标记true。旧状态刷新为4；matched=1<2，申请创建第二个临时实例。只有创建成功、两个实例都进入本篇第4节的有效汇总时，同键贡献才合成−10。再次调用且这两实例仍在列表时，matched=2，不申请第三份。新建实例的实际duration仍经过公共创建修正，不从旧实例刷新公式反推。

**例C：强度参数变化不是统一替换。**指定已有两个匹配状态param均−5；第三次请求contribution=−7，其余条件同例A。匹配数已满，两个duration被刷新，但该片段不把两份旧param改−7；不能演算成−14。这个例子是从没有param写入的限定片段推导的条件行为，不是原作实战中确有−7版本 Taking Aim。

### 10.3 新实例为何成为属性贡献，以及不同来源如何分开

创建分支调用 `scr_temp_incr_atr @ 0x14181e8d0`，实参由上一助手逐项准备：

```text
(attributeKey, contribution, durationRequest,
 selectedUnit.id, selectedUnit.id, true,
 calculationFlag, sourceKey, undefined, undefined)
```

这是目标与 owner 均当前受作用单位的具体调用；来源仍单独保存在 source，不用 owner 替代来源匹配。创建助手将类型6171=`o_temp_incr_atr`送给公共effect_create（常量 `0x14954ca98`，调用 `0x14181f799`），创建成功后写：atr取参数0（`0x14181f885`）、param取参数1（`0x14181f8e3`）、calculation取参数6（`0x14181f941`）、source取参数7（`0x14181f99f`），然后显式派发Alarm2（`0x14181fc09`）。这里仍有目标/来源检查与失败路径，匹配数量不足不是创建必成功的保证。

OBJT6171直接父5949=`o_invisible_buff`，再到5897=`c_abstract_states`，不是主Taking Aim对象6091。`o_temp_incr_atr.Alarm2 @ 0x144516000` 在 atr!=−4 的路径清空自身data（`0x144516174`），写 `data[atr] = param`（`0x1445161c8`），并将目标stats_is_change置true（`0x144516268`）。calculation为真才进一步请求属性计算（`0x1445162c2 / 0x14451635f`）；Taking Aim本次传undefined，经创建助手默认false，不把此调用描述成必然立即完成最终属性重算。

这闭合了“一个新临时实例 → 一份属性地图贡献”。两个实例各一份−5，在有效逐键加法汇总中得到−10，是**多实例叠贡献**；没有任何必要把它改写成“单个对象stack从1加到2”。也不等于最终物理抗性直接下降十个百分点，最终基值、上下限和其他属性消费者另见 [45](45-equipment-buff-attribute-pipeline.md)。

**例D：按来源值分组的并存，条件演算。**指定有效单位列表只有一份source=S1、atr=Physical_Resistance、param=−5的临时状态；向该单位发同键来源S2、S2≠S1、限制2的请求，并指定创建检查通过。S1状态不匹配，不被此请求刷新；S2的匹配数为0，申请新增一份source=S2的6171实例。两者仍存在并通过汇总时，各自贡献相加。这个正常匹配/创建桥支持来源值分组的并存；**没有证明名为技能A/B的两个实际施法者必定传不同sourceKey**。尤其两个Taking Aim调用都传6091时，纵使施法者不同，也不能仅靠这段算法声称按施法者分组。

`o_temp_incr_atr.Destroy @ 0x144515760` 按目标buffs中该临时实例自身id查索引（`0x144515a81`），再请求ds_list_delete（`0x144515ad1`）并置目标属性dirty（`0x144515b0c`）。这是**活动状态列表的实例身份清理**，与 [36](36-control-overlap-and-action-locks.md) 中动作锁列表只存true、按位置删除的表示不同；不要把这里的id清理当成五个动作锁也具有相同来源令牌。

**例E：只移除一份属性贡献。**指定单位有临时实例T1与T2，两者贡献均−5，且buffs索引查询/删除成功；销毁T1后，T2仍登记。下一次有效全量重建中，该键只从T2取得−5。这不保证销毁调用当帧UI立刻显示新数值，也不证明销毁S1的来源对象会自动销毁所有source=S1状态；此处清理单位是状态实例自身。

### 10.4 延长持续的命名实例：同一部位流血

完整来源见 [28 流血](28-bleeding-and-blood-loss.md) 第4节。`scr_bleedChange` 查该部位的状态类型，已找到就调用 `scr_modifer_duration_change(durationRequest, undefined)`（`0x1412b655d`）。默认第二参数false，执行：

```text
durationRequest = baseDuration * (1 + (1 - min(100, Condition)/100)^1.65)
existing.duration = min(existing.duration + durationRequest, existing.max_duration)
```

Condition放大链 `0x1412b60e3..0x1412b62cc`；持续加法 `0x141f6eb3b`、min `0x141f6eb89`、写回 `0x141f6eb9f`。已存在状态时不重走Alarm2缓存损伤，不写stack，不重新把Fortitude应用于新增请求。

**例F：同部位加时。**指定头部已有正常流血，stored duration=3、max_duration=10、bleeding_damage=4，目标存在、抗性与免疫门禁通过；Condition=100、本次baseDuration=5。放大因子=1，请求5，持续写min(3+5,10)=8；缓存损伤仍4。若重施前duration=8，则封顶10。不同攻击来源的参数没有被这个正常同部位类型查询用作区分实例的键，所以不能借此推出“流血按每个攻击者并存一份”。

### 10.5 不宜交给自研实现冒充事实的剩余项

本轮没有闭合主Taking Aim、Stasis、Stun对**同类型重复施加**的完整策略，也没有证明所有Buff采用上述任一种机制。`scr_buff_change @ 0x140fd24e0` 虽有stack比较、duration/max_duration、替换和stage_restore分支，尚缺每个命名状态的调用资格及完整分支契约；本节不把它们任意改名为“通用刷新”“通用强度叠层”。

来源对象退出是否带走其全部临时效果、离图/读档与异常删除能否保留各实例、所有门禁失败是否回滚、时间补偿对应哪个玩家可见窗口，仍未知。可以据本节独立设计四个明确策略，但自研应自行规定匹配键、贡献更新与时间补偿，并测试旧强度是否随刷新变化；不能将这些选择归因于原作全部状态。

本机可选证据：[Taking Aim调用](../../../_reference/stoneshard-study/third-skill-disassembly/gml_Object_o_b_taking_aim_Other_15.txt)、[刷新和计数入口](../../../_reference/stoneshard-study/third-skill-disassembly/gml_Script_scr_temp_effect_update.txt)、[加0/1助手](../../../_reference/stoneshard-study/thirteenth-buff-disassembly/helper-0x14000bd90.txt)、[新增临时状态助手](../../../_reference/stoneshard-study/thirteenth-buff-disassembly/gml_Script_scr_temp_incr_atr.txt)、[临时属性初始化](../../../_reference/stoneshard-study/thirteenth-buff-disassembly/gml_Object_o_temp_incr_atr_Alarm_2.txt)、[按自身id退出](../../../_reference/stoneshard-study/thirteenth-buff-disassembly/gml_Object_o_temp_incr_atr_Destroy_0.txt)、[本轮对象资源](../../../_reference/stoneshard-study/thirteenth-buff-objects.json)、[常量核对](../../../_reference/stoneshard-study/thirteenth-buff-selected-constants.json)、[原生覆盖记录](../../../_reference/stoneshard-study/thirteenth-buff-native.json)、[独立条件演算](../../../_reference/stoneshard-study/thirteenth-buff-derived-examples.json)、[本节核对记录](../../../_reference/stoneshard-study/thirteenth-buff-validation.json)。这些是普通本地调查产物，不是REA Evidence；未运行游戏。条件例子的核对不能代替实战生命周期验证。
