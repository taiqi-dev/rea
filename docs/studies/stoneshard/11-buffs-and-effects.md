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

同一事件还向 `scr_temp_effect_update` 传入 `Physical_Resistance=-5`，以及条件分支中的 `Stun_Resistance=-5`、`Knockback_Resistance=-5`。调用为 `0x14447ae3c`、`0x14447afb8`、`0x14447b119`，另有数值参数 4 和 2。属性键与 -5 确定，但 4、2 的单位及完整临时更新结构尚未恢复，不能自行命名为持续回合数和叠层上限。

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

确切未知包括：各 Buff 完整叠层/刷新规则；Taking Aim 特定被动身份与全部计数机会公式；数值贡献进入最终属性的单位/倍率；临时效果参数 4/2 的含义；创建期间每个持续修正分支；filter 来源；dirty 标记被消费的完整链；所有数据容器释放行为；与实战动画完全一致的时序。没有运行时验证，因此不报告观测帧率、实际回合长度或战斗数值实测结果。

## 9. 独立设计借鉴

可以借鉴“单位持有活动状态列表，状态保留来源与目标，属性缓冲按活动状态重建，持续推进与效果事件分阶段”的结构。它使叠层和过期有共同入口，来源记录也能解释某个数值从哪里来。

我们的实现应明确不同属性是加法、倍率还是覆盖，按属性定义决定汇总方式；持续时间宜使用明确的回合阶段与 tick 类型，避免界面帧和战斗回合混用。叠层规则、刷新规则、过期事件、清理所有权和失败结果应成为独立测试规格。

例如可以自行规定 Taking Aim 类能力“下一次远程攻击消耗状态”，或者“维持一完整行动窗口”，使用自己的数值和图标。这些都是独立产品规则，并未证明原游戏采用它们。本文提供机制和边界供学习，没有把恢复代码或原游戏资产作为自研实现。
