# 一把剑的一次攻击：结果判定、扣血与受击事件

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [物理伤害演算](32-physical-attack-damage-resolution.md) · [部位命中](25-body-part-hit-selection-and-injuries.md)

本篇把“一把剑的一次攻击”拆成配置输入、随机标志、结果处理器、伤害计算、HP应用和受击事件。已恢复选定入口的真实判定顺序，以及一个带明确条件的数值例子。**真实武器表的18、护甲计算后的12、最终HP扣12，不是可以无条件画等号的三件事。**配置到角色属性的完整生产者、若干运行槽及全部特殊保护仍未闭合。

## 1. 制品、方法与这次选择的剑

目标仍是本机GameMaker YYC Windows x64制品。EXE SHA-256为 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win为 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。本轮开始核对时间为2026-10-12 22:20:57 PDT（2026-10-13 05:20:57 UTC）。

REA MCP/provider不可用沿用00的记录，使用本机静态索引与Capstone 5.0.9。没有启动、附加或修改游戏，没有读取新存档或做网络监测。本机记录不是REA Evidence会话。

Drifter Sword来自一张完整嵌入武器表，而非我们随意给剑起名。表头地址 `0x1463c0410`，行地址 `0x1463c0900`，均84列；静态字符串槽 `0x14981df20`，构造入口 `0x140c887e0`、构造调用 `0x140c887ee`。配置包含：

| 字段 | 实际表值 | 解释边界 |
|---|---:|---|
| id / Slot / Subtype | sword02 / sword / sword | 表行身份 |
| Tier / rarity | 2 / Common | 配置分类 |
| Slashing_Damage | 18 | 基础斩击配置，不保证实战分量仍是18 |
| Armor_Piercing | 5 | 穿甲配置，不是直接额外加5伤害 |
| Rng | 1 | 配置的攻击距离项 |
| CTA / PRR / Block_Power | 5 / 6 / 4 | 所属这把武器；不自动等于攻击者最终CRT或受击者格挡预算 |
| MaxDuration | 80 | 原始耐久配置 |

`scr_get_damage_of_weapon(0x1403a1dd0)`会读取武器数据的DMG以及角色相关状态。仅有表行和此入口，尚不足以证明“表18→最终Slashing属性18”的完整映射。人物、装备、Buff、技能倍率及耐久均应在生产者侧继续核对。因此下文演算另外明确构造本段斩击输入18，见32。

## 2. 攻击首先产生多个标志

入口 `scr_attack(0x14129bb90)`的这段不是一次随机抽出一个互斥结果。它先读取攻击者和目标属性，分别调用Chance，再用多个局部标志选择结果处理器。

以下F、B、M、S、T、Q是本文为局部变量重命名，**不是恢复出来的原始变量名**。名称以读写和消费者为依据；不能仅靠名为dodge/fumble的脚本推定前段全部语义。

| 本文符号 | 局部槽 | 已见作用 |
|---|---|---|
| F | rbp+0x170 | 初始来自攻击者FMB机会，后面还可被失败标志转换置真 |
| B | rbp+0x160 | 目标PRR机会成功，并且Block_Power达到门槛 |
| M | rbp+0x1d0 | 命中检查或后续EVS检查置位；可被后续标准化清除 |
| S | rbp+0x28 | 第二次EVS机会成功的分类标志 |
| T | rbp+0x58 | M转换成F路径时置位的分类标志 |
| Q | rbp+0xd8 | 允许暴击检查时产生的暴击标志 |

### 2.1 FMB与格挡

攻击者FMB字段读取 `0x14129d5c8`，Chance调用 `0x14129d67c`，结果进入F。之后目标PRR读取 `0x14129d70a`，Chance调用 `0x14129d7eb`。PRR机会成功还不够，目标Block_Power读取 `0x14129d7fc / 0x14129d84d`，比较位置 `0x14129d883`；普通有限数值分支要求Block_Power≥1，才将B置真。

这一次只是**格挡资格判定**。实际格挡扣减预算由结果处理器重新把目标Block_Power传进damage_calculation，见32；Chance的输入PRR不是格挡吸收的伤害点数。

### 2.2 Hit_Chance、负EVS与第二次检查

攻击者Hit_Chance读取 `0x14129d96f`，目标EVS读取 `0x14129d98a`。设原始命中属性为H0、目标属性为E。局部命中输入为：

```text
H = H0
if E < 0:
    H += abs(E)
```

负值门槛、绝对值、加法分别位于 `0x14129da58 / 0x14129da8d / 0x14129da99`。第一轮Chance(H)在 `0x14129db6f`：失败将M置真，成功才可能走第二轮。

当第一次成功且E≥0，第二次机会输入是：

```text
evsInput = E - max(Kchance, H0 - 100)
```

H0重新读取 `0x14129dc63`，减100包装调用 `0x14129dca3`，max在 `0x14129dd17`，E减该max在 `0x14129ddcb`，Chance调用 `0x14129de6e`。成功将M和S均置真（`0x14129deb6 / 0x14129df07`）。E<0跳过这次额外检查。

这里确认的是 **H0−100**，不是100−H0：整数减法包装 `0x140005910`把源RValue复制到输出后减去第三参数；它的被调减法在本机已核对。把顺序颠倒会让高命中属性反而增大这项扣减的相反方向。

Kchance来自RValue槽 `0x149871d80`（引用位置 `0x14129dc72`），该槽没有PE文件原始字节，本轮未确认初始化与运行值。因此不能擅自写成max(0,H0−100)。例如**另构造Kchance=0**：H0=110、E=20时第二机会输入10；H0=90、E=20时输入20。这只是条件演算，不证明原作运行下限为0。

[19](19-kick-pull-and-knockback.md)已记录Chance的随机范围与仍未知的概率下限。上述数值是传给助手的输入，不能直接当成实测百分比，更不能把几次机会合并成一次相减后的命中率。

### 2.3 失败标志转换与暴击

在暴击检查之前，控制流先处理F与M：

```text
Q = false
if F:
    跳过这一段的失败转换和暴击检查
else if M:
    F = true
    M = false
    T = true
else:
    Q = Chance(CRT * (1 - target.Crit_Avoid/100))
```

F真值门禁 `0x14129df40`；转换写入F、M、T在 `0x14129df97 / 0x14129dfe5 / 0x14129e036`。CRT / Crit_Avoid读取 `0x14129e0a9 / 0x14129e0b8`，除100、1减、乘法在 `0x14129e125 / 0x14129e153 / 0x14129e19d`，Chance调用 `0x14129e277`。

暴击输入使用攻击者当时的CRT和目标Crit_Avoid。Crit_Avoid是倍率扣减项，不是这里再额外抽一轮“避免暴击”。非法数值、完整属性生产者和Chance下限仍有边界，不把公式扩成所有特殊单位的总规则。

## 3. 最终结果处理器的优先顺序

在上述转换**之后**，所查路径的选择顺序为：

```text
if M:
    attack_result_dodge(...)
else if B:
    attack_result_block(...)
else if F:
    attack_result_fumble(...)
else:
    attack_result_hit(...)
```

对应静态调用为 `0x14129e55a / 0x14129e714 / 0x14129e895 / 0x14129e9bd`。处理器还收到暴击与分类标志；“进入block”不代表Q被抹掉。block中可见critBlock、fumbleBlock结果标签，不能将格挡、失手、暴击强行做成一个互斥枚举。

| 具体构造路径 | 标志转换后 | 所选处理器 |
|---|---|---|
| F初始假；B假；Hit机会成功；额外EVS不成功；Q假 | M假、B假、F假 | hit |
| F初始假；B真；Hit成功；EVS不成功；Q真 | M假、B真、Q真 | block，携带暴击标志 |
| F初始假；B假；Hit机会失败 | M由真转换为假，F/T变真，Q保持假 | fumble |
| F初始真；B真；Hit机会失败 | F真使转换跳过，M仍真 | dodge先于block |

这是按真实分支构造的例子，不是四种情况的实战概率。还需区分处理器返回的局部结果、后续可继续伤害的资格和反射/二次处理。比如 `attack_result_dodge`内部也能到达scr_damage（`0x141d2d5bb`）；仅凭选择了dodge就宣布“整个攻击没有任何受击事件”不成立。

## 4. 从结果到伤害：暴击不是最后再随意乘二

普通hit处理器的选定调用顺序为：

| 局部顺序 | 调用点 | 含义与限制 |
|---|---|---|
| crit_modifiers_apply | `0x14052db68` | 条件成立时准备暴击相关修正 |
| damage_calculation | `0x14052ddca` | 计算类型分量、部位输入及相应副作用 |
| attack_result_crit | `0x14052e5fc` | 条件暴击表现/统计等，不等于整个伤害公式 |
| scr_damage | `0x14052e71f` | 伤害事件、控制机会与实际扣血链入口 |
| crit_post_damage | `0x14052e892` | 条件暴击后的处理 |

这些是有分支的调用点，**不是每次hit五项无条件全执行**。block的对应路径也存在暴击准备、伤害计算和暴击后处理：调用点分别为 `0x1405d89da / 0x1405d8c49 / 0x1405da39e / 0x1405da4d4 / 0x1405da8c3`。

block将目标Block_Power作为damage_calculation第三实参；hit传入的对应值却来自未知槽J=`0x1497fcc28`（引用 `0x14052dcab`）。32因此没有把普通hit里的J默认当0。想复现“普通命中不减格挡”必须继续闭合J的生产者，不能借处理器名字完成数值证明。

fumble同样能调用damage_calculation（`0x142006379`）和scr_damage（`0x142006ecf`），并按标志产生fumble、fumbleDodge、hitFumbled等结果。它具体改变哪些分量和机会，应在其修正生产者中另查；本文不擅自规定失手固定减半。

## 5. 伤害事件中，部分效果早于HP写入

`scr_damage(0x1412a4b70)`的所查首范围约22.8KB，包含Bleeding_Chance、部位、眩晕、踉跄、击退、定身机会及抵抗字段、owner/target、伤害结果和被动响应。它不能概括成“先扣血，再统一加所有状态”的短包装。

已见若干条件Chance、效果创建、cast_knockback与被动调用在physical_damage之前。随后调用：

```text
scr_damage
  → scr_physical_damage          调用点0x1412a9974
      → scr_simple_damage        调用点0x141292455
  → save_damage_received         调用点0x1412a9af0
  → 条件玩家 / 心理处理          is_player点0x1412a9b84，psy_change点0x1412a9e23
  → hit_deformation              调用点0x1412a9fa0
```

`scr_physical_damage(0x141291910)`也带HP、on_damage_method等读写，不能把它与simple_damage认作同一个函数。damage_calculation更早已可能调用BodyPartHit，见32/25。因而部位Condition与实际HP保护不必在同一写入点发生；不能看到HP最终回退就自动断言其他状态全部回滚。

本段证据证明有这些路径和局部先后，不证明每项始终执行、全回调顺序一致，或者当前装备的所有被动已被覆盖。要独立实现，可用明确的“准备→计算→应用→后续事件”阶段定义自己的契约，并明示中途状态变化怎样影响下一阶段。

## 6. HP到底怎样改，哪里可能回退

`scr_simple_damage(0x141227f30)`的选定普通数值路径先对准备的伤害量取整（`0x1412289be`），读取并保存旧HP（`0x1412289df / 0x1412289f5`），再做减法 `0x141228dec`，max与HP写入在 `0x141228e8e / 0x141228ea8`：

```text
HPintermediate = max(Lhp, HPold - math_round(Dprepared))
```

Lhp来自未知RValue槽 `0x149871410`（引用 `0x141228e44`），没有PE原始字节，本轮未核准运行初始化。**这里不能宣布已证明HP统一下限0**；普通有限值算例只要求Lhp不抬高本次正结果。

随后还会触及in_battle、last_attacker、is_damage_taken等状态。选定分支写in_battle=1、is_damage_taken=2，位置 `0x141228fcc / 0x14122911b`；这两个字段的数值不是一份最终伤害量。

### 保护与事件

- `is_player`检查调用 `0x141228c2a`的结果保存在局部。后段检查此结果（`0x141229132`）与先前读取的playerGodMode（字段引用 `0x1412282c0`，检查 `0x14122914c / 0x14122915a`）；两者满足时在 `0x14122918f`把备份HP复制回来。不是完全取消前段所有效果。
- 另一组合保护分支在 `0x141229653–0x141229664`可写HP=1，涉及特殊目标/状态资格；本轮未完整恢复该组合，不称它为所有敌人的保命规则。
- 后段还能调用enemyAI_damage_trigger（`0x14122a079`）和post_damage（`0x14122a1f0`）。事件实际是否可达取决于前段门槛；未核准全部早退、死亡及反射组合。

因此HPintermediate是中间状态。一个完整规格应区分准备伤害、已计算伤害、HP实际差值、部位变化、保护结果与后续通知，不把一个整数伤害值拿来代表所有结果。

## 7. 一条可复核的具体攻击例子

将32的局部数值例继续接到此处。共同构造前提：

1. 本段Slashing输入18、格挡前总基数18，其余类型明确为数值0；Armor_Piercing=5、Slashing抵抗0、聚合Damage_Received=100。
2. 32共享下限C≤0；第二列不进入格挡分支，第三列进入且目标Block_Power=4。
3. 后段没有特殊效果改写计算返回值；交给simple_damage的Dprepared正是18/12/10；已到达普通HP应用路径。
4. HPold=50，Lhp≤32；GodMode和其他保护不触发；后续回调没有再次改变HP。

| 阶段 | 无护甲 | 部位护甲6 | 部位护甲6 + 已成立格挡4 |
|---|---:|---:|---:|
| 格挡后Slashing | 18 | 18 | 14 |
| 护甲扣减 | 0 | 5.7 | 4.433333… |
| 抵抗/受伤倍率后取整 | 18 | 12 | 10 |
| 输入HP层的伤害 | 18 | 12 | 10 |
| 在本组条件下的HP | 32 | 38 | 40 |

这是**真实局部公式的构造演算**，不是在游戏里测得Drifter Sword对任何单位都打18/12/10。若C、J、Lhp、聚合属性或修正不满足前提，应回到含未知参数的公式，不能套表。

同一击的部位变化还可分别算。另构造max_hp=100、当前执行Bodypart_Damage=0，并满足BodyPartHit资格，三组Condition损失为 `(D)^1.05`，约20.7987 / 13.5875 / 11.2202。它作用于抽到或技能指定的一个部位；没有平分六肢。初始Condition、未知clamp下界、伤势与流血机会另见25–28，本文不随意从损失量推出某个最终伤势实例。

若同一普通HP路径通过上述玩家保护门槛并且playerGodMode为真，则备份50可恢复，**即HP结果50而不等于单纯50−D**。这说明演算为什么必须写保护前提，而不能只报告一个“最终伤害公式”。

## 8. 下一步最值得补什么

| 缺口 | 已有证据 | 下一步完成标准 |
|---|---|---|
| 表行到攻击属性 | 84列真实剑表、武器DMG入口、damage_calculation的倍率与分量读取 | 闭合装备解析/默认值→属性聚合→实际调用实参，不靠空列猜0 |
| Kchance、C、J、Lhp初始化 | 已绑定读取地址、部分有限xref | 找到有效初始化与写入生命周期，或运行观察其真实类型/数值 |
| 暴击和fumble修正 | 修正入口与不同结果调用者 | 逐字段倍率和消费，至少两组数值例及例外资格 |
| 特殊HP保护/回调 | 神模式回退、写HP1、受击响应入口 | 补全组合门禁、死亡先后、回调是否再改HP及状态 |
| 混合元素与联动状态 | 类型助手、分组取整、Arcane局部改写 | 至少一种双类型输入，从生成到HP和部位输出全链闭合 |

目前不宣称恢复了完整战斗引擎。已闭合的是所选攻击入口的多标志判定、结果优先顺序、若干真实伤害调用链、普通HP局部公式和保护分支；可以据此讨论架构与独立重写规格，无法直接替代全游戏数值模拟。

## 9. 证据和验证

本机可选记录：[选定攻击入口](../../../_reference/stoneshard-study/ninth-attack-native.json)、[攻击指令](../../../_reference/stoneshard-study/ninth-attack-disassembly)、[完整剑表行](../../../_reference/stoneshard-study/ninth-weapon-example-config.json)、[未初始化槽核对](../../../_reference/stoneshard-study/ninth-attack-helper-checks.json)、[算例](../../../_reference/stoneshard-study/ninth-attack-derived-examples.json)、[目标身份](../../../_reference/stoneshard-study/ninth-target-identity.json)。这些链接在克隆后的机器可能没有，关键输入、地址与限制已保留在正文。

验证包括静态名称/参数绑定、控制流与算术顺序核对、构造演算及文档链接。未执行游戏运行验证或REA产品测试，原因是本次继续回答系统问题且现有静态证据已能建立这些局部规则。剩余风险是未知运行槽、属性生产者、特殊保护和回调；未复制目标代码/资产到生产实现，未提交或推送。
