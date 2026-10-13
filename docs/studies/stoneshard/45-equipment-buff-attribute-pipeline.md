# 45. 装备、Buff 与临时属性怎样汇总

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [Buff 生命周期](11-buffs-and-effects.md) · [肢体减益](27-body-part-injury-debuffs.md) · [格挡临时收益](38-block-reactions-and-counterattack.md)

**已经确认三种不同的属性查询，以及“清空、重新累加、计算角色字段”的局部流水线。不能把所有属性都写成基础值加装备再加 Buff：有的查询这样相加，有的角色字段读取已经形成的基础字段，再加入 Buff 并钳制；后续战斗计算还可能继续修正。** 本篇给出已恢复的加法、缺失值、临时状态写入与命中上限，保留装备到所有基础字段的缺口。

目标为 00 固定的本机 EXE/data.win，本轮摘要一致。主要新解码记录使用 Capstone 5.0.7，按登记入口读取选定第一段 `.pdata`；这属于本地静态后备分析，不是 REA Evidence。没有运行、附加或修改游戏，没有读取新存档。下文的规格伪代码重新组织了行为，不是原始源码。

## 1. 先分清各层数据

| 层 | 已找到的载体/入口 | 本篇能确定的职责 |
| --- | --- | --- |
| 物品配置 | 武器表、`scr_item_attributes_set`、`scr_inv_damage_parse` | 把选定配置项解析并写入物品 data |
| 装备查询 | `scr_inv_param`、`scr_inv_param_slot` | 根据键查询装备侧结果；不是本轮已恢复全部槽位规则 |
| 活动效果 | 单位 `buffs`，各状态的 `data` | 保存状态贡献和实例身份 |
| Buff 缓冲 | 单位 `buffer_buff_data` | 从合格状态重建逐键贡献 |
| 通用查询 | `scr_inv_buff_atr`、`scr_FullAtr` | 按已确认的顺序组合几个查询结果 |
| 角色属性字段 | `scr_atr_calc`、`bHit_Chance`、`Hit_Chance` 等 | 把基础/贡献投影为当前角色数值，部分属性有钳制 |
| 战斗计算 | `scr_atr_calc_combat`、攻击结果和伤害入口 | 继续形成战斗参数；全体字段的转换尚未逐项恢复 |

同名键在几个容器里出现，不代表它们都是最终面板值。例如 `data["Hit_Chance"]` 是一个状态贡献，而 `Hit_Chance` 是角色字段；二者还隔着活动资格、缓冲重建和字段计算。

主要入口地址为：`scr_inv_buff_atr@0x1416b1a20`、`scr_FullAtr@0x1416b0b00`、`scr_buff_param@0x140fc2fc0`、`scr_inv_param@0x140fc4080`、`scr_player_buff_buffer@0x140fe5310`、`scr_enemy_buff_buffer@0x140fe3cf0`、`scr_buff_buffer_add@0x140fe7cb0`、`scr_atr_calc@0x140b66380`、`scr_atr_calc_combat@0x141a243c0`。

## 2. Buff 缓冲是重建，不是无限叠加

玩家入口先清空 `buffer_buff_data`，已见调用 `0x140fe5575`；敌人入口清空调用为 `0x140fe3f09`。随后遍历活动状态/相关被动数据，在有效实例、地图及激活等分支条件成立时调用公共累加器。玩家示例调用 `0x140fe5af7`，敌人示例 `0x140fe4380`、`0x140fe48c0`。

两种入口有不同过滤，不能把它们合并成“所有已学习被动无条件加入”。玩家路径还出现 `is_activate`、`is_open`、`on_panel` 等字段，敌人路径出现 `pass_skill`。本轮没有把每一种状态、技能和面板组合的资格表全部恢复。

公共累加器按状态 `data` 的键迭代，读取当前贡献与目标缓冲已有值。已有值是 undefined 或空指针时走缺失路径；普通有效数值路径进行相加。主要加法调用 `0x140fe87d0`，随后选择 `ds_map_replace` 的元数据 ID（`0x140fe884e`）并以三个参数写回（`0x140fe8870`）。另有 source/duration 来源登记，不能把调试来源记录误当成第二次属性收益。

```text
重建合格状态的贡献缓冲(unit):
    清空 unit.buffer_buff_data
    对每个通过本入口资格检查的状态:
        对状态 data 中每个被处理的键:
            old = 缓冲中的有效旧值，缺失时使用零
            缓冲[key] = old + 状态.data[key]
```

这份伪代码描述普通数值路径；原运行时仍保留动态值类型，不能据此承诺字符串、任意指针、NaN 等输入都可按数学数值相加。

**具体例子：**合格状态 A 为 `Hit_Chance` 贡献 +15，合格状态 B 贡献 −20，重建后这一键为 −5。再次重建仍为 −5，而不是 −10。B 被销毁并从活动列表解除后，下一次实际重建得到 +15。数字是构造输入，重建和逐键加法是指令确认；不是游戏实战记录，也不表示任意同类 Buff 都允许并存。

## 3. 查不到一个 Buff 键时返回什么

`scr_buff_param(key)` 从当前上下文的 `buffer_buff_data` 查询。已查路径对 undefined 和 `pointer_null` 做缺失判断；内部缺失标记真时，将调用者输出写为数值零（`0x140fc34d5–0x140fc34fa`），否则复制查询值（`0x140fc3513–0x140fc3521`）。

容易误读的是 `0x140fc3425` 写入的内部标记：它的常量为 1.0，用于决定缺失分支，不是“缺失属性返回 1”。返回零的实际指令是 `0x140fc34fa`。

因此，在本入口的已查普通路径中：

```text
BuffContribution(key):
    v = 查询缓冲[key]
    如果本入口认定 v 缺失: 返回 0
    否则返回 v
```

**具体例子：**缓冲中没有 `Hit_Chance`，本次 Buff 查询贡献为 0；缓冲有该键且值 −5，则返回 −5。不能把这条规则推广到 `ds_map_find_value_ext` 等其他查询，因为那些入口可能使用调用者提供的 fallback。

## 4. 两个通用组合助手的精确区别

### 4.1 装备加 Buff

`scr_inv_buff_atr(key)` 先调用 `scr_buff_param`（`0x1416b1b95`），再调用 `scr_inv_param`（`0x1416b1bb6`）；最终加法 `0x1416b1bed`，输出复制 `0x1416b1bf9`。

对普通有限数值可以表达为：

```text
InvBuff(key) = InventoryQuery(key) + BuffContribution(key)
```

本助手没有额外乘法，也没有加入角色基础地图。调用先后与数值加法顺序是两回事；最终结果仍依赖装备查询怎样选择槽位、物品和特殊条件。

**具体例子：**装备侧查询结果为 4，Buff 缓冲为 15，则此助手返回 19。这里“装备侧结果为 4”是明确输入前提，不是断言某把实际武器贡献 4。

### 4.2 角色地图加装备加 Buff

`scr_FullAtr` 分别保存 Buff 查询结果（调用 `0x1416b0d4a`，保存于本函数局部指针 `rbp+0x10`）与装备查询结果（`0x1416b0d6f`，保存于 `rbp+0x8`）。另调用 `ds_map_find_value_ext` 查询角色 `characterDataMap`（`0x1416b0ff6`），实参包含键和调用者的 fallback。

第一加法 `0x1416b113c` 接装备结果，第二加法 `0x1416b1195` 接 Buff 结果，最终复制到输出 `0x1416b11a4`：

```text
FullAtr(key, fallback) =
    (CharacterMapQuery(key, fallback) + InventoryQuery(key))
    + BuffContribution(key)
```

fallback 的全部默认值和键覆盖未恢复，不能自行写成 `characterMap.get(key, 0)`。上述表达也只是这个助手，不是“全游戏所有属性的最终公式”。

**具体例子：**键确实存在，角色地图值 20、装备查询值 4、两个合格状态贡献 +5/+10，缓冲为 15，结果 `(20+4)+15=39`。如果角色地图键缺失，必须先知道本次调用给的 fallback，不能继续沿用 20 或默认零。

## 5. 真实字段例子：命中属性有 5 到 150 的钳制

主属性重算读取 `bHit_Chance`（`0x140b6d3b3`），取得 `Hit_Chance` 写入槽（`0x140b6d3c9`），查询 Buff 的 `"Hit_Chance"`（`0x140b6d420`），做相加（`0x140b6d45d`），然后调用 clamp（`0x140b6d506`）并写回（`0x140b6d520`）。

clamp 下界来自 `0x1495406f8`，上界来自 `0x149540708`，本机数值分别为 5、150。已恢复的这一阶段是：

```text
Hit_Chance = clamp(bHit_Chance + BuffContribution("Hit_Chance"), 5, 150)
```

这里不能再无条件加一次装备：`bHit_Chance` 的全部生产者还没有闭合，可能已经含有上游处理。把前节 `FullAtr` 的演算直接塞入此式，再额外加装备，可能重复计入。

| 构造输入 | 缓冲贡献 | 此阶段输出 | 意义 |
| --- | ---: | ---: | --- |
| bHit=90，状态 +15 与 −20 | −5 | 85 | 状态负贡献正常参与相加 |
| bHit=145，状态 +20 | 20 | 150 | 上界钳制 |
| bHit=10，状态 −20 | −20 | 5 | 下界钳制 |
| bHit=90，该键缺失 | 0 | 90 | 缺失 Buff 不改变此阶段基础字段 |

这些是属性字段的条件演算，**不是最终打中概率或游戏面板的实测值**。35 的攻击入口仍有 EVS、机会助手、标志转换和技能参数；命中属性 85 不足以断言任意目标受到该攻击的命中率就是 85%。27 还显示 EVS 和伤势/疼痛存在不同消费者，不能把 Hit 的钳制复制到所有属性。

主重算有敌人 Buff 缓冲调用 `0x140b6774f` 和玩家 Buff 缓冲调用 `0x140b752dc`，它们属于不同条件路径。不能声称每个单位每次重算都会连续运行两种缓冲器。

## 6. 临时属性是状态数据，calculation 控制是否立即重算

真实对象 OBJT6171 为 `o_temp_incr_atr`。38 找到格挡响应通过公共助手发出 `Block_Recovery` 参数 10、持续请求 3；这些是请求值，不能只凭名称变成“立即恢复十点格挡”或“最终三回合”。

本轮新查其 Alarm2 `0x144516000`：

1. 读取 `atr`，与数值 −4 比较；只有不等于 −4 的已见路径继续（比较 `0x1445160db`，相等跳过 `0x1445160fa`）。
2. 清空本状态 data（`0x144516174`）。
3. 读取 `atr` 与 `param`（`0x144516184`、`0x144516197`），向 data 的地图写入运行时传参为 map、atr、param（`0x1445161c8`）。结合 11 同一地图写入运行时的证据，是直接保存这项贡献；没有先把 param 乘到角色当前值。
4. 进入 target 实例上下文，写 `stats_is_change=true`（字段选择 `0x14451624b`，写回 `0x144516268`）。
5. 读取 `calculation` 并转换真值（`0x1445162ac–0x1445162c2`）；真时调用 `scr_atr_calc(target, undefined)`（`0x14451635f`），假时跳过这次即时重算。

因此 `calculation` 在本事件是是否调用即时计算的门禁，不是“加法/百分比/乘法模式”的枚举。其其他写入者和调用时点仍需按具体状态追查。

`atr != -4` 只确认一个哨兵门禁，不验证任意键类型或 target 一定有效。状态 data 的写入先于进入 target 上下文；以下成功演算另要求目标有效。

```text
临时状态 Alarm2 的选定有效路径:
    如果 atr != -4:
        清空本状态 data
        data[atr] = param
        target.stats_is_change = true
        如果 calculation 的运行时真值为真:
            scr_atr_calc(target, undefined)
```

**具体例子：**已进入上述事件，atr=`Hit_Chance`、param=−10、目标有效，且该实例后来通过 Buff 缓冲资格。它产生 −10 贡献；构造 bHit=90、另一状态 +15，则本阶段命中为 `clamp(90+15−10,5,150)=95`。calculation=false 时，本事件仍保存贡献并标记属性变化，但不在这个分支立即调用重算，不能声称此刻字段已经变成 95。

Destroy `0x144515760` 在 target.buffs 中找自身 id（`ds_list_find_index` 选择 `0x144515a4e`），符合索引条件时删除（API 选择 `0x144515aa0`），并标记 `stats_is_change`（`0x144515ae4`）。本轮没有逐项恢复这个临时对象的持续递减、首次 Alarm 排程和 dirty 标记所有消费者。删除实例后再重建能去掉贡献，不等于已证明任何销毁瞬间都会同步修改每一个面板字段。

## 7. 真实装备例子：Drifter Sword 的 18 到了哪里

32 已从真实武器表行确认 Drifter Sword 的 Slashing_Damage=18、Armor_Piercing=5。这是配置事实；要证明装备形成的角色总伤害，还需要从表到物品再到角色消费者逐层连接。

本轮补出第一段生产链：`scr_item_attributes_set@0x141f23c10` 对 `"Slashing_Damage"` 调用 `scr_inv_damage_parse`（`0x141f2431f`）。后者入口 `0x14101f3a0`，以键和 undefined 请求 `scr_weapon_array_get`（`0x14101f5be`），再调用 `string_to_real`（`0x14101f627`）。选定正值路径把 `ceil(value)` 和该键加入 `data["Main"]` 列表（`0x14101fc8c`），并把取整结果写入 `data[key]`（地图写入准备 `0x14101fd88`）。

另比较 `max_dmg`（`0x14101fa74`）：较大的候选更新 max_dmg 及 `data["DamageType"]`。这是物品主要伤害类型选择的局部证据；全部平分规则、非正值路径和多次初始化顺序没有闭合。

**具体例子：**若这一实际调用从武器行取出的字符串/值是 18，转换成功且通过正值分支，则 `ceil(18)=18`，物品的 `data["Slashing_Damage"]` 为 18。这与 Drifter Sword 表值吻合，但本轮尚未闭合该物品实例的所有默认参数与装备查询消费，**不能进一步把角色 Slashing_Damage、攻击总基数或最终扣血直接定成 18**。32/44 的下游计算必须继续使用各自已经确定的输入前提。

## 8. 可独立借鉴的结构和验证点

以下是自研建议，不是原开发者意图：

- 分开保存物品属性、活动状态贡献、汇总缓存和当前角色字段，让每个阶段有明确输入。
- 对重建使用清空后累加；状态删除只登记变化，消费者统一刷新。需要即时反馈的效果可明确请求立即刷新。
- 每个字段定义自己的公式和钳制，不用一条“基础+装备+Buff”覆盖伤害、命中、抗性和恢复全部属性。
- 来源记录保留贡献者身份，支持解释“为什么当前值变成这样”；同名键不替代类型和单位约定。
- 测试状态加入、删除、换装备、负贡献、缺失键与上下界，并分别检查贡献缓存和最终字段，防止重复计入。

可作为自研测试的条件用例是本篇的 39、85、150、5、95；它们验证明示局部规格，不证明游戏完整属性流水线已经模拟成功。

## 9. 范围、证据与剩余缺口

已确定：逐键重建加法、Buff 缺失输出零、两种组合查询的参数和顺序、命中属性 5/150 钳制、临时状态 data 写入与即时重算门禁，以及装备伤害字段的局部解析。

仍未知：全部装备槽/副手/切换武器规则，characterDataMap 缺失 fallback 的全部生产者，所有 b* 字段生产，全部百分比和乘法阶段，临时状态的精确寿命及自动刷新时序，最终面板/实际伤害的完整一致性。完整指令解码与地址定位通过不替代这些语义缺口。

本机可选证据：[属性入口与覆盖](../../../_reference/stoneshard-study/eleventh-attributes-native.json)、[Buff 查询](../../../_reference/stoneshard-study/eleventh-attributes-disassembly/gml_Script_scr_buff_param.txt)、[组合查询](../../../_reference/stoneshard-study/eleventh-attributes-disassembly/gml_Script_scr_FullAtr.txt)、[命中字段计算](../../../_reference/stoneshard-study/eleventh-attributes-disassembly/gml_Script_scr_atr_calc.txt)、[临时状态 Alarm2](../../../_reference/stoneshard-study/eleventh-attributes-disassembly/gml_Object_o_temp_incr_atr_Alarm_2.txt)、[临时状态退出](../../../_reference/stoneshard-study/eleventh-attributes-disassembly/gml_Object_o_temp_incr_atr_Destroy_0.txt)、[物品解析](../../../_reference/stoneshard-study/eleventh-mixed-disassembly/scr_inv_damage_parse.txt)。这些可再生成的证据不随仓库分发；正文保存了必要规则、地址、前提和未知项。
