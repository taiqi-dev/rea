# 44. 混合类型伤害、暴击倍率与 fumble 输入修正

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [单类型物理伤害](32-physical-attack-damage-resolution.md) · [结果判定顺序](35-attack-results-and-event-order.md) · [吸取结算](43-life-and-energy-drain.md)

**这不是把所有类型相加后套一个统一护甲公式。** 本轮新闭合 Fire 的格挡和类型处理实参；它与 Slashing 共用前段总基数 T，但两处预算系数都是 **0.66**，Slashing 则为1。暴击在结果处理器中把修正后的 `CRTD/100` 作为伤害计算倍率；fumble 的实际倍率参数为 **0.5**。二者发生在分量防御与取整之前，不能等同于最终扣血值乘二或减半。

继续分析同一 x64 GameMaker YYC 制品，EXE SHA256 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。沿用 REA 提供者缺失记录，以 Capstone 5.0.9 做本机局部静态核对。未启动、附加、修改游戏或存档、未读取新存档。

## 1. 真正的倍率生产者

普通 hit 助手 `scr_attack_result_hit@0x14052d380` 先把本地倍率初始化为1，`0x14052d951–0x14052d95b`。暴击资格成立时：

1. 先调用 `scr_attack_result_crit_modifiers_apply`，`0x14052db68`。
2. 再读此时当前攻击上下文的 CRTD，`0x14052db7e / 0x14052db87`。
3. 除100，写倍率本地变量，`0x14052db9c / 0x14052dbaf`。
4. 将此变量作为 `damage_calculation` 第1参数，即第二实参，`0x14052dc99–0x14052dca0`，实际调用 `0x14052ddca`。

所以这里是 `m = CRTD_afterModifiers / 100`，不是 `1 + CRTD/100`。普通未暴击分支保留m=1；不能未经初始化就替它指定某个角色的 CRTD 基础值。

block 也存在相同的暴击修正调用与 CRTD/100：`0x1405d89da / 0x1405d89f0 / 0x1405d8a0e / 0x1405d8a21`，并把准备的倍率交给 `damage_calculation@0x1405d8c49`。此前 fumbleBlock 分支还存在0.5倍率常数；暴击与失误标志的选择顺序见35，不能假设所有标志同时成立时把所有倍率连续相乘。

`scr_attack_result_fumble@0x142005bb0` 则直接准备常数0.5，`0x142006223 / 0x14200622a`，作为第二实参排列 `0x142006236`，调用 `damage_calculation@0x142006379`。它也传入其他资格和分类参数，并可能产生 fumble、fumbleDodge、hitFumbled 等标签；**0.5是真实调用倍率，不代表任何标签下的最终掉血必减半**。

## 2. 暴击准备还会改其他字段

crit_modifiers_apply 不是单纯输出一个倍率。它按装备/武器类型及其他实参走分支，局部能直接增加当前上下文的机会或属性，例如：

| 明确局部分支的写入 | 真实位置 | 不能推广的内容 |
| --- | --- | --- |
| Daze_Chance 加25 | `0x141de44a1` | 没有在本轮绑定完整武器资格 |
| Bleeding_Chance 加25或50 | `0x141de4588 / 0x141de453b` | 不是所有暴击都触发或保证流血 |
| CRTD 加50 | `0x141de45d5` | 这不是每次普通暴击的固定总倍率 |
| Bodypart_Damage 加30或60 | `0x141de4670 / 0x141de4623` | 部位状态消费另有单位与资格 |
| Manasteal 加50 | `0x141de46bd` | 不等于最终 MP 恢复50 |

整数加法助手 `0x14000bd90` 已在前轮核对为数值加法。本轮验证的是这些字段、数值和调用关系，不把尚未绑定的分支武器名称填进表。还有负资源请求、被动分派、统计与心理处理，见43。因此计算暴击时应使用**这些修正执行后实际读取的 CRTD**，不能越过生产者拿未经修正的角色字段。

这些是攻击上下文写入；是否对每次攻击重新准备、全部字段如何在后续清理/重算，不能凭此断言永久加成。完整武器分支表和所有修正回滚不在本轮闭合范围。

## 3. 分量倍率与共用分母

`scr_damage_calculation@0x141250670` 有独立物理、非物理分组倍率，还受武器、技能与法术资格影响。初始物理倍率有 `Weapon_Damage/100` 读取，`0x1412519d1 / 0x1412519ef / 0x141251a02`；特殊分支可能改为1，不能把全体调用都固定成相同武器倍率。

对于本轮选定的 Slashing+Fire 输入，记前段防御前已准备好的有效分量为 S0、F0。它们已包含本次 m 以及相应分组修正。Slashing 保存位置沿32为 `0x1412544e9–0x1412544fc`，Fire 的原字段绑定为 `0x14125390f / 0x141253918`，倍率乘入并保存 Fire 局部 `rbp+0x3c8` 在 `0x141254782 / 0x141254795`。

总基数 T 在前段把各分组组合并乘本次第二实参，保存 `0x141253e6f / 0x141253e82`。只含本例两分量、其他类型明确数值0且组修正一致时，T=S0+F0。若还有其他分量，分母包含它们；若分组倍率/修正不满足这里的构造条件，不能从两个字段自行重建完整T。

T 与零比较相等时存在把分母改为1的哨兵补偿，`0x14125438e / 0x1412543c0 / 0x1412543ca`。后续分母副本 `0x1412543ec`。格挡扣掉分量以后，**没有按新的剩余 Slashing+Fire 重新计算这个分母**。

## 4. 各类型的系数与独立抵抗

类型助手实参为：

```text
typeCalc(target, remainingComponent, tmpTypeResistance,
         Damage_Received/100, T, penetrationFactor, typeCoefficient)
```

本轮核对13个连续类型调用的临时抵抗字段和系数。它们分别消费对应 tmp 抵抗，不是把同一个 Slashing 抵抗用于所有元素：

| 类型 | 格挡/护甲系数 | typeCalc 调用 VA |
| --- | ---: | --- |
| Slashing | 1 | `0x141256229` |
| Piercing | 1 | `0x141256361` |
| Blunt | 1 | `0x141256499` |
| Rending | 1 | `0x1412565d1` |
| Fire | 0.66 | `0x141256745` |
| Frost | 0.66 | `0x14125687d` |
| Shock | 0.66 | `0x1412569b5` |
| Caustic | 0.66 | `0x141256aed` |
| Poison | 0.66 | `0x141256c25` |
| Unholy | 0.66 | `0x141256d5d` |
| Arcane | 0.66 | `0x141256e95` |
| Psionic | 0.66 | `0x141256fc6` |
| Sacred | 0.66 | `0x1412570f7` |

系数保存于 `rbp+0x890`，物理设1，随后设 double 常数 `0x3fe51eb851eb851f`，即0.66；Fire 类型段载入 `0x141256615 / 0x14125661f`。**这里是0.66，不是精确2/3。** 连续 blockCalc 调用也按前四项1、后九项0.66排列；Fire 调用 `0x1412551ee`，常数设置 `0x14125511a–0x141255124`，输入分量指针 `0x14125516d`。表只说明这段预算系数与抵抗消费者，不表示所有类型后续状态副作用相同。

P 是该攻击分支选择的 `1−Armor_Piercing/100` 或 `1−Spell_Armor_Piercing/100`，不是仅凭分量名字 Fire 就必用法术穿甲。部位 DEF 与抵抗的实际字段选择见25/32；本助手使用 tmp 字段值，不另把通用抵抗和部位抵抗无条件相加。

## 5. 两分量局部算法

令 cS=1、cF=.66，K 为已成立格挡路径传入的目标 Block_Power。共享下限 C 为未知运行槽 `0x1498722e0`，不能默认0。

```text
for each component i:
    if entersBlockPath:
        reduction_i = max(C, c_i * K * B0_i / T)
        B_i = max(C, B0_i - reduction_i)
        _tmpBlockReduction += min(B0_i, reduction_i)
    else:
        B_i = B0_i

    if B_i passes positive-value gate:
        armor_i = max(C, c_i * tmpDEF * (B_i/T) * P)
        resist_i = max(C, 1 - tmpResistance_i/100)
        out_i = max(C, math_round((B_i-armor_i)*resist_i*G))
    else:
        out_i = max(C, 0)
```

G=target.Damage_Received/100。block助手和type助手的算术主体已在32闭合；本轮新增 Fire 的实际分量/系数/抵抗参数，而非拿斩击公式直接推广给火焰。

关键边界：护甲扣减发生在类型抵抗前；扣甲后没有立刻再截断到零，最后才经取整与max；格挡并非每一类型都吃全部K；预算系数小于1时，两类型扣减合计也不必等于K。类型输出之后还有分组取整和最终取整，不能用“所有未取整分量一次相加后round”替代。

普通hit传给格挡实参的 J=`0x1497fcc28`、fumble对应槽 `0x1498939a8`仍未核准运行初值。故下面不进格挡路径是明确构造的**分支前提**，不是凭hit/fumble名字推定实参0。本轮有限初始化扫描未找到这些槽的 `lea rcx` 构造生产者，不能据此证明它们没有初始化。

## 6. Slashing + Fire 的完整条件演算

这是构造输入，不是某把真实剑默认带火焰。参考32真实 Drifter Sword 的斩击表值18，另构造本次普通前段有效 Slashing=18、Fire=6，其余11种类型数值0；组倍率满足这里的简化条件；目标 tmpDEF=6、Armor_Piercing=5，所以P=.95；tmpSlashing_Resistance=0、tmpFire_Resistance=20、Damage_Received=100，即G=1。

共同未知前提：C≤0；未格挡列确实绕过格挡分支；没有后续特殊类型改写本次伤害返回值。不是把 C 或 J 的运行值设为0。

| 步骤 | 普通 m=1 | 暴击，修正后 CRTD=150 | fumble 调用 m=.5 |
| --- | ---: | ---: | ---: |
| S0 / F0 / T | 18 / 6 / 24 | 27 / 9 / 36 | 9 / 3 / 12 |
| 斩击护甲扣减 `6*(S0/T)*.95` | 4.275 | 4.275 | 4.275 |
| 火焰护甲扣减 `.66*6*(F0/T)*.95` | .9405 | .9405 | .9405 |
| 斩击类型输出 | round(13.725)=14 | round(22.725)=23 | round(4.725)=5 |
| 火焰类型输出 | round(5.0595*.8)=4 | round(8.0595*.8)=6 | round(2.0595*.8)=2 |
| 两类型汇总的本段 D | 18 | 29 | 7 |

该例中所有其余输出0，分组和最终取整不再改变整数结果。暴击29不等于普通18×1.5=27；失误7也不等于18×.5=9，因为倍率在防御扣减之前，而不是最终D的末尾乘法。

再用普通输入进入已成立格挡，目标K=4：

```text
斩击格挡减量 = 1*4*(18/24) = 3       → B_S=15
火焰格挡减量 = .66*4*(6/24) = .66   → B_F=5.34
护甲斩击 = 1*6*(15/24)*.95 = 3.5625
护甲火焰 = .66*6*(5.34/24)*.95 = .837045
outS = round(15-3.5625) = 11
outF = round((5.34-.837045)*.8) = 4
D = 15
```

累计格挡扣减3.66，小于预算K=4；它由两种系数和各自比例产生，不代表“漏执行.34点”。剩余总量20.34没有替换分母24。若把分母改成剩余总量，会改变护甲扣减，这是一个实际可区分的算法选择。

## 7. 汇总、部位和实际 HP 的边界

Fire 的 typeCalc 返回值写到 `rbp+0x870`，对应调用后复制 `0x141256754`。Slashing 则写 `rbp+0x538@0x141256238`。本函数对组和最终值另取整，最终 D 写 `rbp+0x600@0x14125781c`；最终取整调用 `0x14125780d`。

符合资格时再调用 BodyPartHit，`0x14125b9d0`，其 D 实参排列 `0x14125b939–0x14125b940`。**它不是混合伤害的全部部位状态副作用**；汇总到此之间还有类型进度、状态与部位处理，Arcane 等特定分支能够再改 D。本文例子明确排除这些改写，不能把所有元素都概括成“只用合计D损伤一个部位”。

真正 HP 继续由结果处理器把计算返回值交给 scr_damage、physical_damage、simple_damage。即使本段算出18/29/7/15，最终掉血仍要满足35的下限、保护与回调前提。吸血/吸魔另在实际 HP 应用前用传入伤害参数计算，见43；不是拿最终实际 HP 差值反推本段所有类型。

## 8. 完成状态与证据

已回答：真实hit/block暴击倍率生产者；fumble实际0.5输入；13类型预算系数与各自tmp抵抗；Fire的具体格挡和护甲实参；两类型共享分母、分别防御/取整和汇总；普通/暴击/失误/格挡四组可核算构造例。

部分或未知：每种武器全部暴击附加修正及清理；完整前段属性聚合/技能倍率；C、J和fumble槽的生产者；所有类型状态、副作用、免疫与返回D改写；实战概率；复杂组合的最终HP。不能把表内13种系数核对说成13种完整技能机制已恢复。

可选本机证据：[本轮入口](../../../_reference/stoneshard-study/eleventh-mixed-native.json)、[实际hit生产者](../../../_reference/stoneshard-study/eleventh-mixed-disassembly/scr_attack_result_hit.txt)、[失误输入](../../../_reference/stoneshard-study/eleventh-mixed-disassembly/scr_attack_result_fumble.txt)、[暴击准备](../../../_reference/stoneshard-study/eleventh-mixed-disassembly/scr_attack_result_crit_modifiers_apply.txt)、[混合分量消费者](../../../_reference/stoneshard-study/eleventh-mixed-disassembly/scr_damage_calculation.txt)、[有限槽扫描](../../../_reference/stoneshard-study/eleventh-mixed-slot-init-xrefs.json)。本机证据未版本化；正文保存必要输入、算法和位置。首段pdata解码不保证全部碎片/全局可达性，名称引用与直接调用已区分。

## 9. 独立设计借鉴与验证

自研可以把每类型分量、抵抗、预算系数、穿甲选择和取整阶段做成显式契约，并保留攻击上下文中的暴击/失误倍率。是否以原始总量或剩余总量分配防御、是否逐类型取整、元素是否共用穿甲，均由自己的玩法决定；不要把本例当原开发者意图或直接复制恢复代码。

验证包括本轮参数/常量/字段绑定、新的Fire链、上游暴击/失误生产者、条件算术和文档链接。未运行或修改游戏，未做REA产品测试。本轮剩余风险为未知运行槽、完整武器资格及类型副作用；现有证据足以说明这些局部机制，不能替代全战斗模拟器。
