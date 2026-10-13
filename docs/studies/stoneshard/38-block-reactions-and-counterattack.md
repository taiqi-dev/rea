# 38. 格挡响应、Riposte、Deflect 与真实反击执行

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [攻击结果与顺序](35-attack-results-and-event-order.md) · [伤害数值段](32-physical-attack-damage-resolution.md) · [Buff 生命周期](11-buffs-and-effects.md) · [动作锁与控制重叠](36-control-overlap-and-action-locks.md) · [反射与来源归属](39-reflection-redirection-and-source-ownership.md)

本轮回答：暴击被格挡后，哪些状态会收到响应，响应是否直接攻击，以及真正反击如何排程与执行。结论是：**Riposte 的本次受击响应负责冷却和临时格挡恢复属性；Deflect 的本次响应负责临时属性、格挡恢复和冷却。真正反击通过另一个公共判定、角色 Alarm6 和普通攻击入口实现。** `critBlock` 不是“无条件立即反击”的命令。

目标为同一 Windows x64 GameMaker YYC 制品。EXE SHA256 为 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win 为 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。沿用提供者不可用记录，以 Capstone 5.0.9 做局部静态核对；未启动游戏，未改目标或存档。本文的事件链是指令关系，不是实战录像或频率测量。

## 1. 真实对象与两个派发通道

| 对象 | OBJT 索引 / data.win 对象偏移 | 本轮职责 |
| --- | --- | --- |
| `o_b_riposte` | 6074 / 11,368,288 | 接收受击上下文的 Other13；另有属性重建和装备检查事件 |
| `o_b_deflect` | 6175 / 11,412,336 | Other14 接收选定状态响应 |
| `o_temp_incr_atr` | 6171 / 11,410,640 | 临时属性请求所创建的实际数值状态 |
| `o_skill_riposte_ico` | 6507 / 11,537,944 | 玩家 Riposte 冷却响应选择的图标对象，含 `child_skill` |
| `o_b_battle_thirst` | 6103 / 11,383,032 | 公共反击许可里的特殊一次执行分支 |
| `o_unit` | 3804 / 10,528,224 | Alarm6 执行登记的反击 |

Other13 与 Other14 是不同通道。GameMaker User3 对应 Other13，User4 对应 Other14。这里同时验证了调用方、事件编号和对象身份，没有把事件名称当作“反击已发生”的证明。

`scr_damage` 在进入目标的 Buff 列表派发时，逐项取 `target.buffs` 的实例，写入本次 `damage`、`attacker`、`attack_result`，再分派 User3。关键位置为列表读取 `0x1412a8dbe`，实例取值 `0x1412a8fb9`，三个上下文写入 `0x1412a9039 / 0x1412a909f / 0x1412a90f7`，User3 `0x1412a9124`。随后才到本路径的 `scr_physical_damage` 调用 `0x1412a9974`。因此此受击响应发生在该路径的实际 HP 应用之前；不能由此声称每一个零伤害调用都必经这段列表派发。

Deflect 的已闭合来源位于 `scr_attack_result_block`。它保存 `scr_damage_calculation` 的返回值 D，比较 D 与数值 0，比较结果为相等时调用 `scr_skill_call_buff(6175, defender, undefined, undefined, undefined)`，地址 `0x1405da226`。相等比较入口为 `0x1405da0c5`，非相等绕过该调用的分支为 `0x1405da0ea`。本机比较传入 `1e-5` 容差，因此这里应说“本机比较认定为零”，不是额外推导 IEEE 严格相等。

`scr_skill_call_buff` 给选中的状态写上下文，再以 User4 分派，位置 `0x140feb393`。此调用早于该 block 路径的 `scr_damage@0x1405da4d4`。只要进入这条来源路径，Deflect 的门槛是 D 比较为零；它不是检查 `critBlock` 名称来决定执行。

## 2. Riposte 的格挡响应算法

入口 `o_b_riposte.Other13@0x14445cd10` 显式读取 `attack_result` 并匹配三种字符串：

```text
block
fumbleBlock
critBlock
```

三者都不匹配时跳到尾部，关键拒绝跳转 `0x14445d076 → 0x14445d8f4`。因此一次有效的 `critBlock` 可进入同一恢复分支；本事件未为暴击另设更大的恢复参数。

通过匹配后，目标是不是玩家决定冷却处理方式：

1. 玩家：选择 OBJT6507，进行两次循环，每次请求 `scr_map_kd_decrease(undefined)`，再选择 `child_skill` 请求同一助手。调用地址 `0x14445d272 / 0x14445d334`；循环计数初始化为 2。这里只证明两轮请求，不把 undefined 的默认递减、缺失图标或 child_skill 的结果补成“所有冷却必减 2”。
2. 非玩家：调用 `scr_skill_change_KD_enemy("Riposte", -2, undefined)`，地址 `0x14445d4ea`。这是有来源的 −2 请求值；实际地图里的不存在键、下限和最终冷却差值仍取决于该助手。
3. 两条分支随后都申请临时属性：`scr_temp_incr_atr("Block_Recovery", 10, 3, target, target, undefined, …)`，十参数调用 `0x14445d6ce`。

临时助手确实创建 OBJT6171，并把第 0 参数写入 `atr`、第 1 参数写入 `param`：`0x14181f799 / 0x14181f7d0 / 0x14181f8a5`。第 2 参数在创建调用中成为 `duration` 输入，`0x14181f651–0x14181f676`。所以可以确认这是 `atr="Block_Recovery", param=10, requestedDuration=3` 的数值状态请求。**10 的最终单位、calculation 默认模式、叠加/刷新和创建后的实际持续值未在本轮完整恢复**；不能把它自动写成“格挡力量立即加 10”或“固定三个实际回合”。共享创建存在时间补偿，见 11。

本 Other13 的局部事件没有 `scr_attack`、`scr_contattack` 或造成伤害助手的直接调用。Riposte 的完整技能还涉及 Other15 属性贡献及武器检查，不能把这份受击响应规格当作它的全部技能描述。

自己整理的局部行为伪代码：

```text
onRiposteDamageContext(context):
    if context.attack_result not in {block, fumbleBlock, critBlock}:
        return
    if target is player:
        repeat 2 times:
            requestCooldownDecrease(selectedRiposteIcon, defaultArgument)
            requestCooldownDecrease(icon.child_skill, defaultArgument)
    else:
        requestEnemySkillCooldownChange("Riposte", -2)
    requestNumericTemporaryState("Block_Recovery", 10, 3, target, target)
```

## 3. Deflect 响应：临时属性、比例恢复与冷却

入口 `o_b_deflect.Other14@0x14451bf20` 本身没有三个攻击结果字符串的检查。通过别的来源派发到它的 User4 是否也有不同门槛，本轮未全局枚举。

| 分支 | 实际请求 | 调用位置 |
| --- | --- | --- |
| target 是玩家 | `Mainhand_Efficiency`, param=5, requestedDuration=3；target/owner 参数省略 | `0x14451c2b5` |
| target 是玩家 | `Offhand_Efficiency`, param=5, requestedDuration=3；target/owner 参数省略 | `0x14451c430` |
| 所有本段有效 target | `CTA`, param=10, requestedDuration=3，target 和 owner 都显式传 target | `0x14451c5b7` |
| target 作用域 | `scr_block_restore(0.25)` | `0x14451c69f` |

手持效率请求和 CTA 请求的实参不能混用：前两者省略 target/owner，由临时助手的默认路径决定；CTA 两者显式绑定。三个请求都是数值状态，不能解释成光效；也不能在尚未核准属性消费者前把 5、10 当成最终伤害倍率或准确反击概率增加值。

### 格挡恢复的实际比例算法

`scr_block_restore@0x140b317f0` 读写的是 `Block_RecoveryStatus`，随后重算 `Block_Power`：

```text
Snew = clamp(Sold + requestedFraction, L, 1)
Block_Power = math_round(Block_PowerMax * Snew)
```

其中 L 是 RValue 槽 `0x14980b768` 的运行值，不能因为没有 raw 字节就默认成 0。加法位于 `0x140b3194e`，clamp 调用 `0x140b319ce`，最大力量乘恢复状态 `0x140b31a83`，math_round `0x140b31acb`，最终写回 `0x140b31ae1`。加法助手普通 double 分支为 `addsd@0x140003974`；乘法助手已在前轮核对。普通有限数的 math_round 为 `sign(x)*floor(abs(x)+0.5)`，不是语言默认的银行家舍入。

因此它不是“把现有 Block_Power 加上 25%”。它先改变比例状态，再以 Max 生成当前预算；二者若此前不同步，也不能用当前预算反推 Sold。

### 冷却恢复的第二个输入来自缺失 HP

在同一 target 作用域，Deflect 调用 `scr_percent_hp(0.25, undefined)` 后 math_round：`0x14451c759 / 0x14451c793`。助手有效目标的普通数值路径计算：

```text
R = (max_hp - HP) / (0.25 * max_hp)
k = math_round(R)
```

乘法 `0x14096306b`，减法 `0x1409630a2`，除法 `0x1409630dc`。这表示“缺失生命相当于多少个最大生命的四分之一”，不是 `HP/max_hp`，也不是治疗 HP。分母为零、无效数值与异常目标的完整策略未恢复。

非玩家路径存在两种冷却请求：类别请求带 `"Attack"` 和 −1 等参数，`0x14451cb10`；命名技能请求向 `"Deflect"` 传 **−k**，`0x14451cc0f`。玩家路径另有对象/类别助手调用 `0x14451c88d / 0x14451c968` 及单技能调用 `0x14451cc98`。未恢复各类别选择器与排除项的全部语义，因此不宣称“所有攻击技能减同一数值”。

## 4. 真正反击：公共许可 → 登记 → Alarm6 → 普通攻击

普通 `scr_attack` 在结果处理之后还有独立分支。局部条件 `rbp+0x110` 已通过有界补查绑定为 **`object_is_ancestor(argument0.object_index, 3804)` 的返回值**，记为 `isUnitTargetObject`；它不是传入的“允许反击”开关。读取第 0 参数目标的 `object_index` 在 `0x14129cd29`，3804 常量在 `0x14129cd56`，两参数 API 调用在 `0x14129cda1`，返回值复制到本地变量在 `0x14129cdb0`。OBJT3804 为 `o_unit`。后续门禁检查该返回值的真值，`0x1412a0d0a`。本段没有恢复该 API 对“对象就是 o_unit 自身”的自匹配边界，不能额外宣称它包括所有自身对象或所有具备同名属性的实例。

通过这个单位对象关系门禁后，选中原 defender，必要时重算属性，调用 `scr_attack_counter_chance(defender, additionalContext)`，地址 `0x1412a0eee`。这一步还没有得到反击许可；真正许可仍由后面的状态与机会分支决定。

许可助手并不只读取 CTA。已确认条件包括 defender 的 `hasCTA`、`state != "flee"`、`counterattack_target` 与原 attacker.id 的不相等检查，以及敌对身份/owner 分支。关键地址 `0x141f620d9 / 0x141f621a5 / 0x141f621f5 / 0x141f625bb`。攻击源的 range 和 shooting 检查也影响前置门禁；本轮没有把 range 比较助手的所有类型分支恢复成全局武器规则。

普通许可路径将 defender.CTA 传入 `scr_chance_value`，地址 `0x141f627d9`。该助手概率的上下限、0..100 整数抽样和取模边界见 19；CTA 的输入值不能直接当百分比成功率。

另有 OBJT6103 `o_b_battle_thirst` 分支：实例 `is_execute=false` 时先写 true，然后返回真，`0x141f626e7 / 0x141f6282a / 0x141f62867`；若已经执行则走普通 CTA 随机路径。这是明确的一次状态消费，不能称 Riposte 自身的重入锁。

许可真还不够：`scr_attack` 再检查 `scr_tile_distance_min` 与 1 相等，通过后调用：

```text
scr_contattack(originalDefender, originalAttacker.id)
```

距离助手 `0x1412a11fd`、相等比较 `0x1412a1232`，登记调用 `0x1412a1346`。这里确实交换了攻击角色，反击目标是原 attacker，不是原 defender 自打自己。

`scr_contattack@0x1412efe20` 检查双方实例存在，选中 counterattacker 并比较其 `HP>0`：`0x1412f0078 / 0x1412f00bc / 0x1412f0177`。通过后写 `last_skill=-4`、`counterattack_target=originalAttacker.id`，设置 `alarm[6]`，置 `contrattack=true`，地址 `0x1412f01e8 / 0x1412f0238 / 0x1412f040a / 0x1412f043f`。可见角色使用 TurnDelay；不可见角色另用 unitTurnGetTime 和 max 计算排程值。本轮未动态量出延迟时间单位。

真正发起攻击的是 `o_unit.Alarm6@0x143611720`：

1. 确认 `counterattack_target` 实例存在，`0x143611920`。
2. 要求 `lock_attack` 列表为空，`0x1436119b9`。
3. 再查双方距离等于 1，`0x143611ab8 / 0x143611aed`。目标离开后，之前登记的反击可失效。
4. 非玩家成功路径置 `force_attack=true`，重算属性，再调用 `scr_attack(counterattack_target, 1, undefined)`，`0x143612409 / 0x14361247e / 0x14361254e`。
5. 返回后置 `force_attack=false`、`contrattack=false`，`0x14361257c / 0x1436125c6`。前置检查失败也清 contrattack，`0x143611b41`。

玩家正常持武器路径和双手处理路径分别存在同类 `scr_attack` 调用 `0x14361277a / 0x143612077`；双手路径还暂时切换装备槽，本轮未把它扩成完整装备策略。

因此已证明真正反击**复用普通攻击计算**。它仍可能命中、被闪避、被格挡或产生其他结果，不能把排程成功当作必然造成某个伤害。Alarm6 在上述局部前置段未重复证明 counterattacker.HP>0；存活检查确实在登记时存在，登记后死亡/销毁怎样取消 Alarm 还需要单位生命周期证据。

## 5. critBlock 的贯通构造执行例

以下是明确给定输入的演算，不是原游戏实测存档，也不把剑表 18 当自动最终伤害。

**例 A：暴击被格挡但仍有伤害。** 令普通攻击结果生产者已经得到 `critBlock`，D=6，defender 为存活敌人且 Buff 列表含 Riposte，相关外层门禁均通过。

1. D 与零不相等，因此本文这条 block 来源不会调用 Deflect。
2. 若 `scr_damage` 到达受击列表派发，Riposte 收到 `attack_result="critBlock", damage=6, attacker=原攻击者`。
3. Riposte 请求命名冷却 −2，并创建 Block_Recovery 的 param=10、duration 输入 3 的临时数值状态。没有立即反击调用。
4. 随后该伤害路径进入 physical_damage；最终 HP 仍受 35 的保护/修正分支影响，本文不把 6 无条件当最终 HP 差值。
5. 若公共反击许可真、双方相邻且登记时 defender.HP>0，记录原攻击者为反击目标并排 Alarm6。
6. Alarm6 到时若目标仍存在、攻击锁为空、仍相邻，非玩家角色执行 `scr_attack(原攻击者,1,undefined)`；此次是新的一次普通攻击计算，随后清除 force_attack 与 contrattack。

**例 B：同样 critBlock，本机 D 比较为零。** 另给 defender 的 `Block_RecoveryStatus=0.20`、`Block_PowerMax=20`、`max_hp=100`、`HP=50`，并假设未知 clamp 下限 L 不高于 0.45、对应 Deflect 实例能被选中。

Deflect 在前置 block 路径收到 User4。它申请 CTA 临时 param=10、duration 输入3；比例变为 `clamp(.20+.25,L,1)=.45`，重算 `Block_Power=round(20*.45)=9`。缺失 HP 指标为 `(100−50)/(100*.25)=2`，所以 k=2，敌人命名 Deflect 冷却请求为 −2。类别冷却的最终改动仍保留未知。这个例子证明零伤害分支会恢复格挡预算与请求冷却变化，**没有证明零伤害必然经过后续 Riposte 列表派发，也没有证明一定反击**。

## 6. 重入、顺序与尚未闭合的问题

已确认的顺序是：block 结果生成 → 零 D 时 Deflect User4 → 调用 scr_damage → 其已到达的列表阶段 Riposte User3 → physical_damage → 外层允许时公共反击判定 → 登记 → Alarm6 再检查 → 新普通攻击。不同响应实例的列表顺序、回调对 damage 的后续加值、死亡事件和所有提前返回不能用这条局部顺序覆盖。

已确认的保护包括目标对象与 o_unit 的关系门禁、`counterattack_target != 当前攻击源id`、Battle Thirst 的 is_execute 消费、登记时 HP>0、执行时目标/锁/距离复查、执行后状态清除。**尚未证明所有反击链都有限、相互反击的所有组合都终止，或 critBlock 对递归计数有统一上限。** Alarm6 传入普通攻击的第 2/3 参数、反击许可助手的 additionalContext 全部语义未闭合，不能把参数 1 擅自解释成“禁止再次反击”。

| 问题 | 状态 |
| --- | --- |
| Riposte 是否响应 critBlock/fumbleBlock？ | 已回答：与 block 一同通过字符串门禁 |
| Deflect 是否由 critBlock 字符串触发？ | 已回答本来源：由 D 比较为零触发；事件自身无结果字符串判断 |
| 两个响应事件是否直接造成反击伤害？ | 已回答本次事件：没有；真实攻击在公共 Alarm6 链 |
| 反击目标及实际攻击入口？ | 已回答：原 attacker；Alarm6 重新调用 scr_attack |
| 暴击被格挡后是否必反击、必减 HP？ | 否；许可、距离、存活、锁和新攻击结果仍有条件 |
| 冷却最终差值、临时属性完整叠加单位、死亡取消、完整重入策略？ | 部分或未知；请求值与确定门禁已保留 |

## 7. 证据位置与独立设计借鉴

| 结论 | 主要位置 |
| --- | --- |
| block/fumbleBlock/critBlock 结果来源 | block 助手 `0x1405d874d / 0x1405d87bb / 0x1405d8864` |
| Deflect 零 D 门禁与 User4 | `0x1405da0c5 / 0x1405da226 / 0x140feb393` |
| Riposte 结果门禁与两个输出请求 | `0x14445d076 / 0x14445d4ea / 0x14445d6ce` |
| 受击 Buff User3 早于 HP 应用 | `0x1412a9124 / 0x1412a9974` |
| 比例格挡恢复与缺失 HP 比值 | `0x140b319ce / 0x140b31ae1 / 0x1409630dc` |
| CTA 许可和一次状态消费 | `0x141f627d9 / 0x141f6282a` |
| 外层目标对象关系门禁的生产者 | `0x14129cd29 / 0x14129cd56 / 0x14129cda1 / 0x14129cdb0` |
| 换角色登记反击 | `0x1412a1346 / 0x1412f0238 / 0x1412f040a` |
| 延迟执行普通攻击与清标记 | `0x14361254e / 0x14361257c / 0x1436125c6` |

可选本机证据：[入口覆盖](../../../_reference/stoneshard-study/tenth-reaction-native.json)、[对象绑定](../../../_reference/stoneshard-study/tenth-reaction-objects.json)、[Riposte](../../../_reference/stoneshard-study/tenth-reaction-disassembly/gml_Object_o_b_riposte_Other_13.txt)、[Deflect](../../../_reference/stoneshard-study/tenth-reaction-disassembly/gml_Object_o_b_deflect_Other_14.txt)、[block 派发者](../../../_reference/stoneshard-study/tenth-reaction-disassembly/gml_Script_scr_attack_result_block.txt)、[damage 派发者](../../../_reference/stoneshard-study/tenth-reaction-disassembly/gml_Script_scr_damage.txt)、[反击许可](../../../_reference/stoneshard-study/tenth-reaction-disassembly/gml_Script_scr_attack_counter_chance.txt)、[登记](../../../_reference/stoneshard-study/tenth-reaction-disassembly/gml_Script_scr_contattack.txt)、[执行](../../../_reference/stoneshard-study/tenth-reaction-disassembly/gml_Object_o_unit_Alarm_6.txt)、[恢复比例](../../../_reference/stoneshard-study/tenth-reaction-disassembly/gml_Script_scr_block_restore.txt)、[缺失 HP 比值](../../../_reference/stoneshard-study/tenth-reaction-disassembly/gml_Script_scr_percent_hp.txt)。这些未版本化，正文已包含必要规则、地址、前提与未知；首段 pdata 解码不等于整个系统恢复完整。

自研可以借鉴“先产生结果事件、响应修改预算、反击独立登记、到时再验证”的结构。我们自己的实现应明确事件阶段、伤害上下文是否允许改写、临时效果的单位和持续策略、死亡取消，以及每次攻击的反击深度或不可重入令牌。上述是独立设计建议；不能声称原游戏已经采用了我们建议的统一深度上限、事务回滚或取消接口。生产代码应按自己的规格重新编写，不使用恢复代码或原游戏资源。

未做：运行时战斗、存档构造、网络监测和完整技能恢复；本轮的局部问题可由静态调用和参数得到明确结论。风险：静态首段与门禁覆盖不代表所有来源，不能对所有 Buff 组合、死亡时序或实际反击概率作保证。
