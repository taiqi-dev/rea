# 46 符文巨石作为战斗实体：占格、参数转移和主动消费

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [22 候选阶段](22-special-skill-candidates.md) · [19 公共位移](19-kick-pull-and-knockback.md)

本篇围绕 Runic Boulder、Boulder Toss、Runic Explosion，解释一个世界实体如何被两个后续技能取值并消费。**本轮已闭合巨石创建／占格、主动抛投与爆破的参数转移、原实体销毁和 aura／占格清理。尚未闭合巨石自动到期的触发器，也未证明字段 `duration` 是一个按回合递减的寿命。**不能把本机 Create 中的20、后续抛投的0.1系数直接拼成“巨石存活二十回合、每剩一回合增加10%伤害”。

目标仍为 `E:/Steam/steamapps/common/Stoneshard` 的 Windows x64 GameMaker YYC 制品。EXE SHA256 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win SHA256 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。沿用已记录的 REA 工具／提供者缺失，使用本机 Capstone 5.0.9 静态 fallback；没有启动、附加、改游戏或存档、读取新存档或联网。原始记录不是 REA Evidence；字段按 refVA−8 复核，BSS未知值不当常量，首 `.pdata` 范围不等于完整函数语义。

## 1. 配置与对象不是同一个层

| 技能配置 | 原表文本 VA | 执行代理 | 实际实体 |
| --- | --- | --- | --- |
| Runic_Boulder | `0x145e4f140` | `o_runic_boulder_birth` | 5473 `o_runic_boulder` |
| Boulder_Toss | `0x145e4f430` | 5459 `o_boulder_toss_birth` | 5457 `o_boulder_toss`，父5296 `o_shell_damage` |
| Runic_Explosion | `0x145e4f4d0` | 5468 `o_runic_explosion_birth` | 5467 `o_runic_explosion_impact`，父5446 `o_spellimpact_damage` |

巨石 OBJT 记录偏移11126568，直接父5470 `o_totem`；o_totem 再继承5469 `c_broken`，向上是 `o_abstract_stuff → o_stuff → o_barrier`。这提供实体与场景物件关系的实际资源证据，不证明父类名称本身就是可破坏、可阻挡或自动过期算法。

创建 birth.Other10 读取实际生成类型，在 `0x143f9c8b5` 选择 `instance_create_depth` 的API ID并于 `0x143f9c8e3` 调用分派器；其类型实参绑定5473。随后在新实例上下文复制 owner 和 damage 等字段（例如owner引用 `0x143f9c927`、damage复制 `0x143f9c97b`），并通过 `scr_setside`（`0x143f9cf08`）处理来源。创建目标位置、音效与方向各自还有参数，本篇不把这些字段混成寿命。

证据：[配置行](../../../_reference/stoneshard-study/sixth-terrain-config-rows.json)、[对象及父链复核](../../../_reference/stoneshard-study/eleventh-ally-and-terrain-objects.json)、[实体出生](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_runic_boulder_birth_Other_10.txt)。

## 2. Create 的生产：duration=20、独立 aura 列表与占格登记

巨石 Create 入口 `0x143f8a290` 调用继承行为后，初始化材质、伤害、光照和本体状态。以下为本轮直接恢复的部分：

| 字段／操作 | 原作值或规则 | 证据 VA |
| --- | --- | --- |
| duration | 写 double 20 | 选择字段 `0x143f8ab6a`，载荷／写入 `0x143f8ab95–0x143f8ab9f` |
| alarm[1] | 写10 | `0x143f8ab3d / 0x143f8ab54` |
| alarm[2] | 写40 | `0x143f8a494 / 0x143f8a4ab` |
| aura | 保存新建列表句柄 | `0x143f8a882 / 0x143f8a8b2` |
| is_created | 写false | `0x143f8ac16 / 0x143f8ac41` |
| wallgrid登记 | 坐标转格后请求添加标记1 | `0x143f8b1f1` |

`duration` 是一个独立字段；Alarm 是另一种计时表示。两个 Alarm 常数不能解释成10／40回合，也不能据此决定 duration 的单位。

占格请求读本体 x/y，转换为整数后通过常数除法得到格坐标。这里的除数为26，编译为乘法倒数 `0x4ec4ec4ec4ec4ec5`、移位与符号修正（x处理 `0x143f8b100–0x143f8b145`，y处理 `0x143f8b155–0x143f8b192`）。正常正整数输入的局部演算为：

```text
x=130，y=208 → gx=5，gy=8
wallgrid_add(5, 8, 1, undefined)
```

130／208是构造像素输入，不是读出的实际地图坐标；1是本入口实际标记实参。不能未经检查把负数处理改写为数学floor，或把 wallgrid 与所有其他碰撞网格视作同一结构。调用还受所查场景控制器实例存在性门禁约束（`0x143f8b039 / 0x143f8b040`）；没有该上下文时，不保证仍登记。

同一 Create 还通知一组场景对象 Other12（`0x143f8b28e`），并有噪声请求。这说明地形出生除生成图片外还有系统副作用，但本轮未恢复每个被通知对象的完整消费者。

**aura 的所有权可确认到列表层：**列表句柄存于巨石，Destroy 使用该列表索引到关联实例，CleanUp 最后释放列表。本轮没有闭合全部关联实例如何加入这个列表，因此不能把“新建空列表”写成“此时所有附近单位已经获得 aura”。

证据：[巨石 Create](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_runic_boulder_Create_0.txt)。

## 3. 抛投：在原实体销毁前复制一项参数

birth.Other10 入口 `0x143f69850` 创建新的抛投实体，并在其上下文读取原被选物体。明确的局部数据转移是：

```text
projectile.add_damage = 0.1 * selectedBoulder.duration
```

add_damage 写字段引用 `0x143f6a3fd`、原物体 duration 读取 `0x143f6a40c`，乘法请求 `0x143f6a458`、写回 `0x143f6a46f`。注意新投射物与旧巨石是两实例，位置／owner／point来源分别处理，不能把投射物的 add_damage 当成旧实体留在地图上继续计时。

之后对原目标执行精确 `object_index == 5473` 检查（`0x143f6a68a` 后的比较），通过才写 `last_attacker=-4`（`0x143f6a729–0x143f6a733`），再在 `0x143f6a754` 请求销毁原巨石。因此是 **先复制数据、再消费实体**；并没有把原巨石对象变型后保留其原 ID。

投射物 Other10 有自身伤害字段准备和击退请求（`0x143f62d67`），随后可走父 `o_shell_damage.Other10` 的真实技能伤害消费入口 `0x143e14a86`。然而在本轮覆盖的投射物／父事件及公共计算首段中，尚未闭合 `projectile.add_damage` 如何参与最终伤害倍率。因此**不能把0.1×duration补成百分比加成或额外固定伤害**。这个参数转移已证明，最终战斗公式仍部分回答。

**直接参数演算：**采用巨石 Create 的实际默认值20，新实体 add_damage=2；若以显式构造输入指定实际存储 duration=8，则 add_damage=0.8。第二个输入不代表已观察到20递减至8的时序。两者只说明局部乘法结果。

证据：[抛投出生及消费](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_boulder_toss_birth_Other_10.txt)、[抛投事件](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_boulder_toss_Other_10.txt)、[父伤害事件](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_shell_damage_Other_10.txt)。

## 4. 爆破：duration复制与独立伤害实体

`o_runic_explosion_birth.Other10@0x143f82e90` 创建impact，并检查被选 point。巨石分支把原巨石 duration 复制给impact（`0x143f83204–0x143f8332e`）；非巨石分支把3写给impact.duration（`0x143f83c9b–0x143f83cbd`）。impact 自身Create原先初始化 duration=0（`0x143f7c011–0x143f7c03f`），出生代理的后续写入不能被这个默认值覆盖解释掉。

最后，原 point 精确类型是5473时，也写 `last_attacker=-4` 并销毁（调用 `0x143f8427d`）。这与抛投共享“参数取走后，旧世界实体退出”的结构；不是先销毁再读取一个仍有效的对象。

impact.Other11 的具体伤害准备可恢复两项正常数值规则：

```text
Blunt_Damage = 10 * (owner.Magic_Power + owner.Geomantic_Power) / 100
Arcane_Damage = 8 * (1 + owner.Geomantic_Power / 100)
```

第一项读取／加／乘／除／写入在 `0x143f7ec03–0x143f7ecfa`；第二项除100在 `0x143f7edf2`、加1在 `0x143f7ee16`、乘8在 `0x143f7ee44`、写回在 `0x143f7eeb3`。这些是所查局部算术，不宣称已覆盖所有加成。随后 `0x143f7f038` 调用 `scr_skill_damage`，另有带门禁的效果、击退（`0x143f7fa72`）和MP恢复请求（`0x143f7fd91`）。

例如构造 Magic_Power=80、Geomantic_Power=20，第一项为10，第二项为9.6；这只是初始化给计算器的分量，不是合计一定扣19.6HP。armor、抗性、命中／暴击和后处理仍由公共伤害路径决定。

MP恢复请求数量在 `0x143f7fcf7` 以 `0.05 * owner.max_mp` 生成，并把owner作为目标送入恢复助手；只有到达相应分支才有这个请求。不能写成每次爆破、每命中一目标或每一点duration都无条件恢复5%MP。

**duration消费者的缺口仍保留：**已经证明impact接到20／8／非巨石3等数值，但未闭合它是否作为持续时间、伤害修正或其他参数被之后的完整路径消费。本轮已读Other11不能直接提供这项答案；不能因为它拥有duration就推定爆破持续20回合。

证据：[爆破出生](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_runic_explosion_birth_Other_10.txt)、[impact Create](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_runic_explosion_impact_Create_0.txt)、[实际伤害与恢复请求](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_runic_explosion_impact_Other_11.txt)。

## 5. 所有到达 Destroy 的路径：aura、占格和容器分开清理

巨石 Destroy 入口 `0x143f8be90` 先继承分派（`0x143f8c096`），再清光照和其他表现；`0x143f8c3c9` 调用 `scr_destroy_aura`，`0x143f8c5ee` 调用 `wallgrid_remove`。之后还有场景对象Other12通知和有条件退出效果。

`scr_destroy_aura@0x14185b500` 实际算法：读取当前实体 aura 列表的大小，按下标取成员（`0x14185b761`），进入成员实例上下文，对仍能选中的实例调用销毁（`0x14185b795`）。这是销毁列表关联的实例，不等于释放这个列表句柄本身。

巨石 CleanUp 入口 `0x143f9a160` 再从本体 aura 取句柄（`0x143f9a208`），调用列表销毁包装（`0x143f9a246`）并写回其返回值（`0x143f9a25c`）。因此可区分：

```text
Destroy：结束关联实例 + 移除占格 + 条件退出副作用
CleanUp：释放实体持有的 aura 列表容器
```

例如构造 aura=[有效实例A,有效实例B]，当巨石进入此Destroy，两成员分别进入销毁请求；随后本体CleanUp释放列表容器。列表的实际登记来源、无效句柄失败处理和异常中途退出尚未完整验证；本轮不把这一正常清理链升级为所有错误路径都无泄漏。

wallgrid_remove使用实体坐标转格的清理请求；Create／Destroy分别对登记与解除有真实调用，建立了占格生命周期闭环。父 o_totem.Destroy 还有newgrid操作，但没有据此声称它能恢复所有旧网格数据、覆盖任何叠放物件或维护全体寻路缓存。

证据：[巨石 Destroy](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_runic_boulder_Destroy_0.txt)、[关联实例销毁](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Script_scr_destroy_aura.txt)、[CleanUp容器释放](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_runic_boulder_CleanUp_0.txt)、[父Destroy](../../../_reference/stoneshard-study/eleventh-terrain-disassembly/gml_Object_o_totem_Destroy_0.txt)。

## 6. 主动消费和普通销毁的退出副作用不同

清理完成后，Destroy 的额外伤害分支依次要求：

1. owner实例存在（`0x143f8c733 / 0x143f8c73a`）。
2. last_attacker实例存在（`0x143f8c77d / 0x143f8c784`）。
3. 两者ID不相等（`0x143f8c800 / 0x143f8c807`）。
4. 后续对象类型、被动技能和距离等门禁也通过。

然后才有 `scr_damage_with_calc@0x143f8cd85` 及效果创建等调用。它不是所有销毁原因共有的无条件爆炸伤害。

主动抛投／爆破在销毁前写−4，改变的是这项来源记录，而不是跳过整个Destroy。−4作为所查消费路径的哨兵传给存在性门禁；在该哨兵不能指向有效实例的正常路径，额外报复伤害主体被绕过，前面的aura／占格清理仍已执行。本轮不把−4解释成一个实际攻击者ID，不补齐所有特殊运行时选择器的语义。

**普通被毁构造例子：**owner=M存在，last_attacker=N存在且N≠M，其余门禁允许，则可进入额外退出伤害申请。把last_attacker改为M，比较相等就绕过；把它设为主动消费的−4且存在性失败，也绕过。这里验证的是门禁差别，不是实测被任何敌人打碎都造成相同报复。

## 7. 同一巨石的三条比较路径

下表是分支构造；不会同时真的消费三次同一实例。共同起点是刚创建、duration=20、占格登记成功的一块巨石B。

| 路径 | 参数／动作 | 原实体退出与已证结果 | 尚未确认 |
| --- | --- | --- | --- |
| A 等待所谓“自动到期” | 没有主动技能消费 | 未找到B的真实duration递减→门槛→销毁入口，不能推定20→…→0 | 自动到期是否存在、真实时钟／门槛与到期时last_attacker |
| B 对B抛投 | 新投射物add_damage=2；B.last_attacker=−4后销毁 | Destroy清关联aura与占格，CleanUp释放容器；条件退出伤害还需存在性门禁 | add_damage最终伤害消费、投射物全过程 |
| C 对B爆破 | impact.duration=20；B.last_attacker=−4后销毁 | 同一原实体清理链；impact走自己的伤害、击退／恢复条件 | impact.duration完整消费者，最终HP与MP |

另可将A替换为“外部伤害导致普通销毁”，用第6节有效且不同的owner／last_attacker演算退出副作用。但这**不是**把外部伤害销毁当作已经找到到期触发器。

为到期问题，本轮读取了所选父事件、巨石 Create／Alarm／Step／Other、共享回合及若干候选持续助手，并以 `mov edx,[rip+disp32]` 模式定位duration字段引用。定位覆盖551处候选引用，最近的已登记函数名只作候选归属；没有把551处全作语义分析，也不声称涵盖其他寄存器编码、间接字段访问或所有动态回调。未闭合的自动到期应保持未回答，不能反向宣布巨石永久存在。

证据：[限定duration引用定位](../../../_reference/stoneshard-study/eleventh-terrain-duration-xrefs.json)、[本轮选定函数](../../../_reference/stoneshard-study/eleventh-terrain-native.json)。

## 8. 自研借鉴、覆盖与风险

可以独立设计“有位置的可消耗实体”，分别持有占格登记、关联效果容器和来源记录。主动技能先复制所需的独立参数，再提交实体消费；清理逻辑按生命周期集中，副作用用明确退出原因区分。若需要寿命，另定义LifetimeTicks、逻辑消费点和到期原因，不沿用一个尚未确认单位的duration字段。退款、重入、同格多个实体和清理失败也应明确建模。

已回答：真实实体关联、duration默认生产、抛投／爆破复制参数、主动消费原实体、占格与关联实例清理，以及有条件退出效果的门禁。部分回答：伤害参数最终消费、aura全部登记生产者、父类其他网格语义。未回答：巨石自动到期链；本篇不会因为已有数值20就填上二十回合寿命。

未做运行／附加／修改／联网验证，没有交付原作代码或资产。剩余风险主要是把字段名当单位、把参数复制当最终公式、把一般销毁当到期、把关联实例清理与列表释放混为一步，或把有限事件范围当全部异常路径。本地原始证据可选，正式正文保留了关键规则和边界。
