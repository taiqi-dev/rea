# 一次攻击如何选择身体部位，以及肢体伤势怎样产生

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [相关系统](09-related-systems.md) · [猛踹与位移](19-kick-pull-and-knockback.md)

本轮已恢复真正的部位选择器，并将它接到部位护甲、伤害汇总、部位 Condition 更新和伤势对象创建。**默认攻击不是六个部位等概率抽选；技能也可以限制候选部位。部位选择先影响护甲数据，计算出的伤害再影响该部位的状态。HP 与肢体状态分别更新，但共享这次伤害的计算结果。**

这是当前本机制品的静态行为研究。以下伪代码由研究者重新组织，只用于解释控制流，不是恢复代码的生产实现。

## 1. 身份、方法和覆盖

| 项目 | 范围 |
|---|---|
| 制品 | `E:/Steam/steamapps/common/Stoneshard/StoneShard.exe`、同目录 `data.win` |
| 格式 | Windows x64、GameMaker YYC；本轮读取原生指令与既有资源元数据 |
| EXE SHA-256 | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| data.win SHA-256 | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |
| 本轮范围 | 部位抽选、猛踹指定候选、部位护甲接入、Condition 损失、伤势等级与流血入口 |
| 未做 | 未运行游戏、未修改游戏或存档；未恢复完整伤害系统、所有技能及全部伤势属性 |

REA MCP/provider 的既有不可用状态沿用，本轮没有重新安装或配置提供者。采用既有 PE 映射、符号索引、字符串槽和本机 Capstone 作有限静态解码。名称引用按 `refVA - 8` 绑定；`.pdata` 范围不自动证明所有后续分支都完整；`.bss` 文件初值不当成运行值。

主要本地证据位于 [seventh-body-disassembly](../../../_reference/stoneshard-study/seventh-body-disassembly)、[入口索引](../../../_reference/stoneshard-study/seventh-body-native.json)、[直接调用候选](../../../_reference/stoneshard-study/seventh-body-call-xrefs.json) 和 [构造演算](../../../_reference/stoneshard-study/seventh-body-derived-examples.json)。这些本机研究产物未版本化；本文保留必要规则、地址和限制，独立阅读不依赖这些文件。

## 2. 数据由谁持有

| 数据 | 持有者 / 用途 | 已确认边界 |
|---|---|---|
| `Body_Part_available` | 当前被选择的单位；可命中的部位数组 | 基础 `o_unit.Create` 写入顺序为 `head, tors, lhand, rhand, legs, rlegs` |
| `Body_Part_target` | 受击目标上暂存的指定部位 | 猛踹写入；特定伤害路径读取并消费后重置 |
| `Body_Part` | 伤害计算期间的目标字段 | 记录这次实际选择的部位；下游 `BodyPartHit` 读取同一个字段 |
| `body_parts` | 部位配置结构 | 数据助手通过上下文中的此字段获取结构；具体初始化生产者本轮未追 |
| `Body_Part_DEF`、`tmpDEF`、各 `tmp*_Resistance` | 伤害计算期间的字段 | 由所选部位配置接入护甲 / 抵抗数据 |
| `Body_Parts_map` | 被击中的单位 | 以部位键存储数值 Condition；不是六套独立 HP |
| `injury_point` | 被击中的单位 | Condition 更新的上界；基础单位初始化为 `100` |
| `Bodypart_Damage` | `BodyPartHit` 当前执行上下文 | 部位状态损失加成；基础单位初始化为 `0`，临时技能修正可能改变它 |
| `buffs` | 被击中的单位 | 查找已存在的伤势 / 稳定伤势对象，控制创建与替换 |

基础初始化地址：部位数组 `0x143607953–0x143607a3a`，`injury_point = 100` 在 `0x143606f18–0x143606f29`，`Bodypart_Damage = 0` 在 `0x1436064a2–0x1436064a9`。这些是基础初始化，不保证所有物种、技能、读档和后续运行状态都保持相同数组或数值。

`legs` 与 `rlegs` 在本文保留原键，不擅自解释为左腿 / 右腿。装备映射、显示名称与物种身体结构可能使用另外的约定。

## 3. 默认攻击：连续两次判定，再选四肢

入口 `scr_choose_body_part = 0x1412b9120`。它先检查当前对象是否属于 `o_unit`（OBJT `3804`）继承体系。未通过时返回空字符串；空字符串由构造器 `0x1412bd054–0x1412bd062` 明确初始化，不是从 `.bss` 零值猜测。

**没有提供候选实参**时，令 `N = len(Body_Part_available)`：

```text
如果 N == 0：返回空字符串
T = min(100, 100 / N + 20)
如果 T == 100：返回 "tors"
H = min(100 - T, 100 / N)

choice = 0
如果 Chance(T) 成功：choice = 1
如果 Chance(H) 成功：choice = 2   // 会覆盖此前的 1
如果 choice == 1：返回 "tors"
如果 choice == 2：返回 "head"
返回限定候选选择("rlegs", "legs", "rhand", "lhand")
```

关键位置：`100/N` 在 `0x1412b9dae–0x1412b9db6`，`+20` 和第一次 `min` 在 `0x1412b9f3f–0x1412b9fab`；第二个阈值在 `0x1412ba069–0x1412ba11f`；两次 Chance 在 `0x1412ba21e`、`0x1412ba321`；四肢递归调用在 `0x1412ba50b`。

这里有两个容易误读的细节：

- 头部判定不是躯干失败后的 `else if`。两次都会执行，头部成功覆盖躯干成功，因此不能把 `T`、`H` 当成两个互斥区域的最终权重。
- 默认分支在部分情况下直接返回 `tors` / `head`，没有再次逐项检查这些键是否存在于数组中。`N=1` 会令 `T=100` 并直接返回 `tors`；不能据此宣称任何单部位物种都能正确匹配。有效物种配置如何约束这一点仍未知。

### 随机数边界与六部位构造

公共 `scr_chance_value = 0x1413e5360` 在输入接近 / 达到 `100` 时直接成功；普通有限数路径使用 `max(输入, 未核准运行下限 S)`，并与 `irandom(100)` 的结果比较。整数随机取值包含 `0` 和 `100`，共有 101 个可能输出；比较包含浮点容差。PRNG 取模有微小偏差，不能称严格均匀。

本次没有重新证明 S 的初始化或所有运行写入。以下只作**条件构造**：S 不抬高阈值、忽略取模偏差，将连续抽样按理想独立抽样计数。

基础六部位数组令 `T≈36.6667`、`H≈16.6667`。两次成功输出数分别为 `37`、`17`。最终头部为 `17/101≈16.83%`；最终躯干为 `(37/101)×(84/101)≈30.47%`；其余进入四肢分支。它们不是“躯干 36.67%、头部 16.67%”。此例说明控制流与随机离散边界的效果，不是实战采样统计。

## 4. 技能限定候选：按目标数组顺序试，不等概率抽样

**提供 M 个候选实参**时，选择器遍历目标的 `Body_Part_available`，再逐个匹配技能提供的候选。每次匹配先保存该候选，再以 `110/M` 调用 Chance，成功则停止；所有匹配的 Chance 都失败时，保留最后匹配的部位。没有任何匹配时，结果仍为空，最后退回目标可用数组的第一个元素。

```text
result = ""
chosen = false
for part in target.availableParts:       // 主顺序来自目标
    for candidate in providedArguments:
        if part != candidate: continue
        result = candidate
        if Chance(110 / argumentCount):
            chosen = true
            break
    if chosen: break
if result == "": result = target.availableParts[0]
return result
```

`110` 的原始常量在 `0x1412b9587`，除法在 `0x1412b98a2`；匹配 / 保存 / Chance 分别在 `0x1412b97b6`、`0x1412b97ed`、`0x1412b9916`；最后的首元素兜底在 `0x1412b9e86–0x1412b9eee`。分母是实参数量，不是实际匹配数，也没有先去重的证据。不存在的部位和重复实参都可能改变局部判定机会。

### 真实技能：Power Kick / 猛踹

`o_power_kick.Other25` 给出真实参数 `rlegs, legs, tors`，调用选择器 `0x14406baba`，把结果写进当前目标的 `Body_Part_target`（`0x14406bad4`）。这证明猛踹会限定部位候选，不能把它理解成所有部位的普通攻击。

对于保持基础数组顺序的目标，匹配顺序是 **`tors → legs → rlegs`**，而不是参数书写顺序。M=3，每次输入 `110/3≈36.6667`。沿上节相同随机假设，三者结果分别约为 `36.63%`、`23.21%`、`40.15%`；最后一个包含所有前面判定失败的兜底，因此不是各三分之一。

原指令位置保存于 [猛踹事件证据](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Object_o_power_kick_Other_25.txt)。它还包含别的技能临时属性修正，本例的抽选演算不等于完整猛踹伤害计算。

### 另一选择器会影响后续顺序

`scr_choose_body_part_min = 0x1412bbdb0` 通过 `array_sort` 和比较器 `0x1412bb6d0` 处理同一个可用部位数组。比较器读取两个键在 `Body_Parts_map` 中的值，返回差值的符号（减法 `0x1412bb99d`，sign `0x1412bb9c4`），无指定条件的分支返回排序后的第一个部位（`0x1412bc397–0x1412bc3b4`）。

这是“按状态排序”的直接证据，不能推广为所有攻击必定打最弱部位。具体调用技能、参数筛选、缺键默认值和数组共享 / 排序后的运行顺序没有全部恢复。它也意味着前面的猛踹概率构造必须明确采用尚未被重排的基础数组。

## 5. 选择结果如何进入护甲和生命伤害

已连通以下真实边：

```text
scr_damage_with_calc
  → 可选：对其指定部位实参调用 choose_body_part（argc=1）
  → scr_damage_calculation
      → scr_get_body_part_data
          → 选择 / 消费 Body_Part_target 或使用输入部位
          → 写 Body_Part
          → 按部位查配置、DEF 与 Resistance
      → 类型伤害、格挡 / 抵抗计算、汇总与取整
      → BodyPartHit(target, D, target.Body_Part, P3, P4)
  → 返回伤害为正时 scr_simple_damage(target, returnedDamage, ...)
```

`scr_damage_with_calc` 指定部位筛选在 `0x1412bfefa`，调用伤害计算在 `0x1412c0120`；结果为正的测试在 `0x1412c0160–0x1412c017f`，HP 应用助手调用在 `0x1412c045c`。

`scr_damage_calculation` 于 `0x14125429a` 调用 `scr_get_body_part_data`，其中两个标志来自之前的 `is_player` 等检查。数据助手只在相关标志成立、输入部位为 `NA` 的路径检查 `Body_Part_target`；有暂存指定部位时采用它并重置该字段，否则零实参调用默认选择器（`0x14127b1d5`）。**不能将此写成所有伤害路径无条件消费指定部位。**

选择结果写入 `Body_Part` 在 `0x14127b24d`。数据结构按部位查找；无效配置还有错误提示和 `tors` 回退分支（`0x14127b8de`、`0x14127b936`），不是随意静默接受任何字符串。通过 `def` 取得部位防御描述并写 `Body_Part_DEF`（`0x14127baa0–0x14127bab8`），再取得相应防御字段写 `tmpDEF`（`0x14127bb9a–0x14127bbb8`）；还构造不同伤害类型的临时抵抗字段。

因此，**部位抽选本身不读“这一击伤害有多大”来选部位，但所选部位会进入后续伤害计算的防御 / 抵抗数据**。之后 Condition 又依赖伤害汇总，所以护甲可间接影响肢体状态损失。本文没有恢复全部护甲吸收公式，不能给任意武器、任意装备的最终伤害计算器。

汇总中间值 D 在 `0x14125780d` 经过 `math_round` 写到局部 `rbp+0x600`；在 `0x14125b9d0` 作为 BodyPartHit 的第二实参。该调用的实际顺序为 **`target, D, target.Body_Part, P3, P4`**。它不是无条件发生：`0x14125787e` 检查局部标志，假值分支跳到 `0x14125b9ff`，绕过此处 BodyPartHit。P3/P4 控制额外分支，其中 P4 影响玩家装备耐久路径；没有为所有上游调用赋予统一 UI 名称。

`scr_simple_damage` 的普通路径读取 HP（`0x1412289df`），将伤害取整（`0x1412289be`），在 `0x141228dec` 从 HP 中减去它。后面存在恢复旧 HP 等特殊分支（如 `0x14122918f`），故本轮不把这一局部减法宣称为所有情形的最终可见生命变化。

## 6. Condition 损失：由相对伤害计算，不是另一次随机选部位

在 BodyPartHit 的有效目标、单位继承和有效部位门槛通过后：

```text
M = target.max_hp
B = currentExecutionContext.Bodypart_Damage
loss = power(100 * D / M, 1.05) * (1 + B / 100)
injuryChange(target, selectedPart, -loss, undefined)
```

`D/M` 在 `0x1412b28f4`，乘 100 在 `0x1412b290d`，幂指数 `1.05` 在 `0x1412b2962–0x1412b29b4`；`B/100`、`+1`、相乘在 `0x1412b29ce`、`0x1412b29fc`、`0x1412b2a50`。负号在 `0x1412b2b92`，送入 `scr_injuryChange` 在 `0x1412b2c2f`。

该链没有再次随机分配到另一个部位，也没有把 D 平分成六份。一次 BodyPartHit 使用一个所选部位键；多段攻击 / 范围攻击是否调用多次，需逐技能查调用者。B 的直接来源是当前执行上下文，而非受击目标；不能一律认定它永远等于某个武器面板属性。

`scr_injuryChange = 0x1412ad550` 做实际状态写入：

```text
old = target.Body_Parts_map[part]
next = clamp(old + delta, L, target.injury_point)
target.Body_Parts_map[part] = next

form = 0
if next <= 0: form = 3
else if next <= 25: form = 2
else if next <= 50: form = 1
// 再根据 delta / override、既有伤势及稳定状态决定对象更新
```

旧值查找 `0x1412ae330`，`old+delta` 在 `0x1412ae42d`，clamp 在 `0x1412ae4cf`，写 map 在 `0x1412ae5ea`。上界取 `injury_point`，基础初始化 100。**下界 L 来自 `0x149871e60`，本轮未绑定它的可靠初始化值；本文不将它直接写成 0。**

三个阈值在 `0x1412ae602`、`0x1412ae658`、`0x1412ae6a7`。助手 `0x14007b750` 明确是容差比较后的“不大于”分支（`setle`），不是严格小于；整数 0、25、50 落在上面的较严重等级。邻近浮点边界还受 `1e-5` 比较容差影响。

## 7. 伤势对象与流血是额外状态

Condition 数值写回后，伤势流程还有多层门槛：delta / 可选 override 控制是否进入对象处理，form 必须大于 0，查找已存在的普通 / 稳定伤势对象，可能保留已有对象、销毁较轻旧对象或避免重复创建。局部 form 比较在 `0x1412af299`；存在性查找在 `0x1412af0bd`、`0x1412af1d6`、`0x1412af593`。

对象身份由 `o_db_inj_` 前缀、部位与等级等拼接并取得资源索引（例如 `0x1412aeb2e`），最后通过 `scr_effect_create` 创建（`0x1412af78f`）。本轮确认了创建与替换链，没有逐一恢复每种部位、每个等级的属性减益，也没有为 form1/2/3 杜撰具体骨折 / 撕裂名称。部位状态与伤势对象不能合并成一个无条件“低于50就新建伤势”的规则。

BodyPartHit 随后读取部位流血抵抗 R（`scr_get_body_resistance` 调用 `0x1412b2ce2`）。该助手对玩家按 head/tors/hand/legs 键读取相应 `Bleeding_Resistance_*`；其他路径取通用 `Bleeding_Resistance`，相关读取在 `0x1405d6447`、`0x1405d646e`、`0x1405d64b3`、`0x1405d63fc`。

若更新后的部位 Condition C **小于50**、D 为真值，则构造：

```text
bleedChanceInput = power((50 - C) * D / target.max_hp, 1.8) - R
如果 Chance(bleedChanceInput) 成功：
    bleedChange(target, part, integerRandomInclusive(5, 7), R, sourceId)
```

门槛在 `0x1412b3462`，助手 `0x140089b20` 已核准为严格小于分支；所以 C 恰为50可以是 form1，却不进入本处流血机会判定。公式在 `0x1412b356f–0x1412b3753`，Chance 在 `0x1412b37fa`，随机整数 5..7 在 `0x1412b38e6`，调用在 `0x1412b396e`。这里的 5..7 是传入参数；本文不把它直接叫作最终持续回合或流血层数。下游仍有 Bleeding_Immunity / Resistance 和已有状态处理，Chance 成功不等于最终效果必定新建。

最后 BodyPartHit 调用 `scr_bodyPartsConditionChange(target, undefined)`（`0x1412b3a4e`）。该助手在第二实参等于 undefined 的分支把它改成数值 `0`（`0x1400637d4–0x140063842`），再遍历 map 所有键并以这个 delta 调用 injuryChange（`0x140063afa`）。因此这条调用是全体部位的零增量刷新，不会将本次伤害等额再扣到所有部位；对象更新仍受 injuryChange 自己的门槛控制。

## 8. 两次击打的构造演算

这是人工输入演算，不是存档或运行观测。假设相同部位、每次送入 BodyPartHit 的 D=20，目标最大生命 M=100，B=0，初始 Condition=60；L 不高于演算结果、injury_point=100，并满足对象处理门槛。

| 步骤 | 结果 |
|---|---|
| 相对伤害 | `100×20/100 = 20` |
| 每击状态损失 | `20^1.05 × (1+0/100) ≈ 23.2317` |
| 第一击后 | `60−23.2317≈36.7683`，局部等级 form1 |
| 第二击后 | `36.7683−23.2317≈13.5365`，局部等级 form2 |
| 第一击本处流血输入，R=0 | `((50−36.7683)×20/100)^1.8≈5.7645` |

把最后一个 `5.7645` 直接称作“5.7645% 流血率”是错误的：公共 Chance 的未知下限、0..100 离散随机、容差和下游免疫 / 对象分支都还需要考虑。此例也没有声称第二击的武器 / 装备会保持 D=20；伤势及护甲变化可能反馈到后续攻击。

## 9. 证据位置与结论状态

| 结论 | 证据位置 | 状态 |
|---|---|---|
| 基础六部位数组、顺序 | `o_unit.Create 0x143607953–0x143607a3a` | 指令 + 字符串构造确认 |
| 默认阈值、头部覆盖躯干、四肢递归 | `0x1412b9db6 / 0x1412b9fab / 0x1412ba11f / 0x1412ba21e / 0x1412ba321 / 0x1412ba50b` | 指令确认 |
| 限定候选110/M、早停、最后匹配与首项兜底 | `0x1412b9587 / 0x1412b98a2 / 0x1412b9916 / 0x1412b9eee` | 指令确认 |
| 猛踹候选 rlegs/legs/tors | `0x14406ba5f–0x14406bad4` | 真实技能事件确认 |
| 状态排序的另一选择器 | `0x1412bc209 / 0x1412bb99d / 0x1412bb9c4` | 局部确认；调用场景部分 |
| 指定部位消费与护甲接入 | `0x14127b141 / 0x14127b16d / 0x14127b24d / 0x14127bab8 / 0x14127bbb8` | 指令确认；完整配置生产者未知 |
| 汇总伤害送BodyPartHit | `0x14125780d / 0x14125b9d0` | 指令确认；完整伤害公式未恢复 |
| HP局部减法 | `0x1412c045c / 0x141228dec` | 确认；特殊恢复分支仍存在 |
| 相对伤害损失公式与状态写回 | `0x1412b28f4–0x1412b2c2f / 0x1412ae4cf / 0x1412ae5ea` | 指令确认；clamp下界未知 |
| 0/25/50等级与伤势对象创建 | `0x1412ae602 / 0x1412ae658 / 0x1412ae6a7 / 0x1412af78f` | 局部确认；完整减益表未恢复 |
| 流血条件、公式、5..7参数 | `0x1412b3462 / 0x1412b370a / 0x1412b3753 / 0x1412b38e6 / 0x1412b396e` | 指令确认；最终效果与时间部分 |

**已回答：**一次攻击如何选择部位、默认与限定候选的差别、至少一个真实技能的部位限制、护甲数据接入、Condition 损失、伤势等级和流血局部入口。

**部分回答：**对象替换 / 稳定状态的具体门槛、完整HP终值、每种护甲与抵抗的完整公式、不同物种的实际数组及已排序数组的实战频率。

**未知：**Chance 运行下限 S、Condition clamp 下界 L、所有技能的指定部位覆盖、每个伤势对象的完整减益及持续 / 治疗机制、真实运行统计。没有运行验证，不能把上述构造概率当成实战测量。

第八轮增量已补 [27 各部位贡献表](27-body-part-injury-debuffs.md)、[28 流血持续/损伤](28-bleeding-and-blood-loss.md)、[29 绷带](29-bandages-and-wound-treatment.md)、[30 夹板](30-splints-and-injury-stabilization.md)、[31 恢复](31-injury-recovery-and-health-restoration.md)。上段保留本篇原始覆盖状态；现已能说明三级基础贡献与选定治疗链，但全部最终属性消费者、运行时下限、精确事件时序和所有医疗来源仍未恢复。

## 10. 自研可以借鉴什么

可借鉴的是职责划分：一次攻击产生可追踪的部位结果，部位结果连接装备防御，伤害同时驱动整体生命和局部状态，局部状态再驱动伤势对象及额外流血机会。这种分层能解释“生命还够，但手部状态已经影响战斗”的设计。

独立实现时应根据自己的需求明确候选抽样语义、数据顺序和边界。若希望稳定且直观的权重，可以自己设计一次累计权重抽样，避免无意引入本机观察到的早停、末项兜底和后一次覆盖。将这些修改标成自己的设计决定，不能称作 Stoneshard 原有算法。状态下界、最大生命为零、无匹配部位和失效装备也应在自己的契约中显式处理。

本轮没有复制专有代码或资产到生产实现，没有修改原游戏、提交或推送。剩余风险是静态覆盖和上下文缺口，尤其未知常数槽、特殊HP恢复分支与物种配置；实际时序和实战分布仍待针对性运行核对。
