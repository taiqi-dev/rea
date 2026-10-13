# 47 盟友人数收益与猎犬标记：Protect the Hive、Sic Em

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [05 协作与技能集合](05-enemy-skills-cooperation.md) · [33 当前行动选择](33-arbalester-skill-scoring-and-action-choice.md)

本篇把两个配置候选推进到真实对象、参数、过滤和消费者。**Protect the Hive 在已查成功攻击分支统计附近盟友，以人数给施法者自己申请冷却和暴击属性变化；Sic Em 给选定目标挂状态，猎犬在状态事件中取得士气响应，符合类别及阵营的攻击者又通过受击事件增加伤害中间值。**这不是本轮已证明的编队、包抄或统一命令所有盟友立即行动。

沿用相同 Stoneshard Windows x64 YYC 制品和既有 REA provider 不可用记录，采用 Capstone 5.0.9 静态读取。EXE SHA256 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`；data.win SHA256 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。路径是 `E:/Steam/steamapps/common/Stoneshard`。字段名按 refVA−8 核对，数字和布尔类型分开；未初始化 BSS 值不作为常数。正文解释正常有限数值的局部规则，动态比较保留本机 `1e-5` 容差和异常类型边界。

## 1. 配置、真实注册和执行对象

| 技能 | 配置文本 VA | 执行对象 | 真实敌人注册 |
| --- | --- | --- | --- |
| Protect_the_Hive | `0x145e53180` | 2736 `o_protect_the_hive`，父 5531 `o_target_spell` | `o_rockeater_soldier.Create` 在 `0x143467be0` 读已构造技能名，`0x143467c1c` 调用 `scr_create_skill_map` |
| Sic_Em | `0x145e525b0` | 5603 `o_sic_em`，同一直接父类 | `o_bandit_huntmaster.Create` 在 `0x14378e276` 读技能名，`0x14378e2b2` 调用同一注册助手 |

这些注册不是“全体敌人都会用”。技能对象可用性、目标评估、活动集合和最终竞争仍由 33 所说明的当前选择器决定。本轮确认两种实际敌人的注册，不声称恢复了这两技能全部评分权重或每次战斗使用时点。

配置与实例是不同层：两行都标为 `skill`，虽然执行对象继承名含 `spell`，不能仅凭父对象英文名改称法术。Sic Em 的执行 Alarm 0 入口为 `0x1440dfef0`；Protect 的为 `0x14328ee00`。

本机记录：[配置清单](../../../_reference/stoneshard-study/sixth-skill-config-inventory.json)、[对象与继承](../../../_reference/stoneshard-study/eleventh-ally-and-terrain-objects.json)、[猎手注册](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Object_o_bandit_huntmaster_Create_0.txt)、[士兵注册](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Object_o_rockeater_soldier_Create_0.txt)。

## 2. Protect the Hive：先攻击，成功路径再统计人数

Alarm 0 先检查 owner、target 实例存在（`0x14328f005 / 0x14328f04f`）。自身 `turn_count` 为真时排 `alarm[0]=15` 并递减此字段，之后进入 owner 上下文；为假或实例门禁不满足则走所查继承路径。**15 是 Alarm 排程值，不是十五个逻辑回合。**

在 owner 上下文调用 `scr_skill_attack()`（`0x14328f471`）。返回真值门禁 `0x14328f49d` 为假时跳过本段群体收益主体。随后真正调用：

```text
A = find_ally_target(true, false, owner.VSN,
                     undefined, undefined, undefined)
N = array_length(A)
申请修改 owner.id 的敌人技能冷却：变化请求为 -N
申请 owner.id 的 CRT 临时变化：数量请求为 3*N，持续请求为 5
```

取 VSN 在 `0x14328f4de`，六参数查询在 `0x14328f5a4`，数组长度在 `0x14328f623`。冷却调用 `0x14328f79f` 的第一个参数来自 **当前 owner 上下文的 id**（`0x14328f66b`），不是数组里每个盟友 ID；负号来自 `0x14328f6e4` 的符号位异或。临时属性调用 `0x14328f975` 的键是实际字符串 `CRT`，数量由常数 3 与 N 的乘法请求产生（`0x14328f85b`），持续参数是常数 5（`0x14328f894`），两个目标／来源位置均使用 owner.id。

这里没有逐盟友循环向盟友施加这个 CRT 收益。**盟友是人数输入，施法者是写入目标。**攻击返回真是所查门禁；它究竟涵盖普通命中、格挡或其他结果，不能仅从真值补齐完整结果分类。

## 3. 人数查询的实际过滤

`scr_enemy_find_ally_target@0x1411546b0` 用敌人父类 3805 的实例集合遍历，保存调用者 ID，再按当前参数分支过滤。Protect 使用 `argument0=true` 的数组返回路径；不是找一个最近目标的单目标模式。

本次参数组合恢复出的主要条件：

| 检查 | 地址与效果 |
| --- | --- |
| 排除调用者自己 | ID 比较 `0x141154ff0`；相等跳过 |
| 排除假单位 | `isFakeMob` `0x141155000`，真值路径跳过 |
| AI 必须启用 | `ai_is_on` `0x141155047`，假跳过 |
| 同 faction_key | 读取候选与调用者 `0x141155336 / 0x141155345`，比较 `0x141155379`，不相等跳过 |
| 距离不大于给定范围 | `scr_tile_distance` `0x141155481`；与 argument2 比较 `0x141155497`，大于范围跳过 |
| 排除指定对象家族 | `object_is_ancestor` 实参含 3987（`0x1411552cd`），真值跳过 |
| combat_array 约束 | 查调用者 combat_array 是否含候选 subfaction_key，`0x141155679`；返回不是 -1 时跳过 |
| 收集 ID | `array_push` `0x1411557bc` |

还有参数控制的特殊类别与视线分支：argument3 未提供时设置 false，argument4 未提供时设置 true，argument5 未提供时设置 false。实际视线检查 `scr_enemy_vision_check@0x1411555b1` 受 argument5 门禁，Protect 传 undefined 后走默认 false，**这一次查询没有要求通过该视线检查**。因此不要将 `VSN` 输入解释成已核准的墙体遮挡筛选；它在此提供距离阈值。

argument3 真时另有 3944 猎犬家族排除，argument4 假时另查 `typeID="Tech"`；这些不属于本次默认组合里必经的附加排除。3987 的名字不是理解本次算法所需前提，本篇保留实际类型常数，未将它泛化成“所有召唤物”。

**构造演算：**指定施法者 VSN=6；A 同阵营、距离 3、AI 开且通过其他门禁，B 同阵营距离 8，C 异阵营距离 2，D 距离 4 但 subfaction_key 已出现在施法者 combat_array。四者均不是自己／假单位／3987 家族。则 A 收集、B 因距离排除、C 因阵营排除、D 因数组约束排除；N=1，施法者得到 -1 冷却变化请求和 CRT+3、持续请求5，四个候选不因这段人数收益直接获得 CRT+3。如果再增加两个同样通过门禁的近处盟友，N=3，两个请求分别为 -3 和 +9。

距离使用实际助手和比较容差；这里的 3、8 等是构造输入，不冒充地图坐标或技能固定半径。

## 4. 冷却和 CRT 消费的边界

敌人冷却助手 `scr_skill_category_change_KD_enemy@0x141407110` 切入目标单位上下文，遍历其 `skill_id_name`，读配置键 `Branch`、`Category`、`Class` 与当前 `KD`，根据参数过滤；所查数值更新是旧 KD 加变化请求，再经过下限助手送 `scr_set_kd`（`0x141407db3 / 0x141407e13 / 0x141407e52`，另一类别路径在 `0x14140864a / 0x1414086aa / 0x1414086e9`）。

Protect 调用把 branch／排除名／category／class 四个后续位置都传 undefined；助手会转换部分默认值，其中 branch 与排除名可见 -4，另两个默认来自本轮尚未恢复的槽 `0x1498743f8`。**不能据此填成“所有类别的所有技能无条件减 N”，也不能把下限槽 `0x149874448` 当零。**

`scr_set_kd@0x141753040` 的所查实际写入接到单位 `map_skills` 的配置记录，最后 `ds_map_replace`（`0x14175389d`）；它还有条目存在、类型与 max_KD 分支，变化请求不一定等于最终可用的 KD。33 的实际技能许可随后读取自己的缓存／技能配置；本轮未恢复 Protect 在同一轮对选择缓存的完整失效时序，不能保证一减冷却就立刻追加行动。

CRT 使用 `scr_temp_incr_atr`，不是直接永久改基础属性。其临时实例、持续递减和统计汇总属于公共状态机制。这里明确的是输入数量／来源／目标；在未闭合全部修正前，不把 CRT+9 请求写成最终显示暴击率正好增加九个百分点。

本机证据：[Protect 执行](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Object_o_protect_the_hive_Alarm_0.txt)、[候选查询](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Script_scr_enemy_find_ally_target.txt)、[冷却过滤与修改](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Script_scr_skill_category_change_KD_enemy.txt)、[KD 写入](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Script_scr_set_kd.txt)。

## 5. Sic Em：标记敌方目标，而不是给每只狗发一个目标指令

`o_sic_em.Alarm0` 读取执行实例 target 与 owner，在 `0x1440e018f` 调用九参数 `scr_effect_create`：

```text
(状态对象5946，持续请求15，target，owner，
 undefined，undefined，undefined，undefined，undefined)
```

对象5946实际为 `o_db_sic_em`，OBJT记录11318048，父 `o_physical_debuff`。这条状态挂在选定 target 上，owner 保留施法者来源；不是枚举每个盟友并把该状态挂给它们。15 是共享创建输入，创建补偿／修正和状态递减见 [11 状态生命周期](11-buffs-and-effects.md)，未将其直接宣称为玩家看到十五个回合。

在已查执行和状态事件中，没有把选定目标写成所有猎犬的 `target`／`skill_target`，也没有直接派发每只狗的攻击事件。施法实例、状态实例与攻击者的身份必须区分。

## 6. 猎犬的实际消费者：近目标、非正士气时重设为10

状态 Other10 入口 `0x1443ca910` 调用继承后，遍历对象3944 `o_bandit_dog_parent`（`0x1443ca9da / 0x1443ca9f8`）。它不是泛化的“所有盟友”，普通猎犬3945继承自该父类。

在每只候选犬上下文，从 outer 状态取得标记 target（`0x1443caa67`），读取犬自己的 VSN（`0x1443caa7a`），调用：

```text
distance = scr_tile_distance(dog.id, mark.target, undefined)
如果有序比较认为 distance <= dog.VSN，且 morale_value <= 0：
    dog.morale_value = 10
```

距离调用 `0x1443cab10`、范围比较 `0x1443cab26`；无序结果 -2 或正结果绕过写入。士气助手调用 `0x1443cab50`，其本体 `0x14007b750` 构造第二实参数值0，排除无序 -2 后接受比较结果≤0，见本轮局部助手解码；实际士气写入 `0x1443cab99`，载荷 double 10。这是**赋值10，不是加10**。

本事件自身没再读犬的 faction_key，也没按 mark.owner 归属筛选。它按对象家族、距标记目标的距离和士气门禁工作；其他生命周期或 AI 门禁有无收紧范围，未全覆盖。不能宣称任意阵营动物都受影响，也不能仅因一只实例改过阵营就假定这个局部会排除它。

**构造例子：**D1 属3944家族，VSN=6、距标记目标3、士气−2，则这一事件写为10；D2同家族距离8，保持原士气；D3距离3但士气4，也保持4；D4是另一种同阵营敌人而非3944家族，不进入此遍历。若把 D1 的 faction_key 改为不同值但仍保持对象家族和其他输入，这个已读事件没有阵营检查可据以排除；这是局部过滤边界的演算，不是修改或观察游戏。

是否士气10让犬下回合由 flee 切换为 attack，要继续接犬实际 FSM 与状态上下文。共用 AI 和士气存在并不替代这条特定消费者；本篇只保证字段写入，不保证立即转向、寻路或攻击。

## 7. 受击响应：犬类 Brigand 攻击者增加伤害中间值

同一状态 Other13 入口 `0x1443cafc0` 读取这次受击 `attacker`。它先以3944测试攻击者对象是否属于犬父类（`0x1443cb106`），再比较攻击者 `faction_key` 与实际字符串 `Brigand`（`0x1443cb198`）。两者通过才：

```text
mark.add_damage = 0.5 * mark.damage
```

字段取得 `0x1443cb23a / 0x1443cb24c`，乘法请求 `0x1443cb26d`，之后复制到状态字段。这是更新本次状态响应值；不是给攻击者永久增加50%属性。

公共 `scr_damage@0x1412a4b70` 已有实际消费桥：遍历受击 target.buffs，写 damage／attacker／attack_result 后派 User3=Other13（`0x1412a9124`）；随即读取该状态 `add_damage`（`0x1412a913a`），在 `0x1412a9160` 加到传入伤害实参，再继续后续状态和实际伤害路径。因而这个值有消费者，不只是一项从未使用的初始化字段。

**构造演算：**到达该状态派发时，伤害中间值 D=20、攻击者是3944后代且 faction_key="Brigand"，状态响应产生10，公共伤害实参变30。若相同攻击者的 faction_key不同，则本响应主体不写这次0.5D；若攻击者是人类 Brigand但不是犬家族，也不进入加成。最终HP变化还受后续状态回调、伤害应用和保护约束，不报告实战一定扣30；不在这里额外假定会再执行一次护甲计算。

失败门禁不写字段，不能仅凭它推断状态 add_damage 从未残留；公共派发与父初始化／其他写入者仍有生命周期要核对。本轮证明成功来源与即时消费者，不声称同类标记重复施加、过期和所有受击类型都已恢复。

证据：[Sic Em 执行](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Object_o_sic_em_Alarm_0.txt)、[犬士气响应](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Object_o_db_sic_em_Other_10.txt)、[士气门槛助手](../../../_reference/stoneshard-study/eleventh-ally-morale-helper.txt)、[受击响应](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Object_o_db_sic_em_Other_13.txt)、[公共即时消费](../../../_reference/stoneshard-study/eleventh-ally-disassembly/gml_Script_scr_damage.txt)。

## 8. 独立设计与未决问题

自研可以把这些机制分别建模为“附近合法同伴人数驱动施法者收益”和“目标标记吸引指定家族的响应”，不要共用一个含义模糊的群体命令。距离、视线、阵营、家族、排除子阵营、作用对象和消费相位各写成明确条件；命令式共享目标则应另外定义目标写入、确认与撤销。

实际已回答：两技能真实注册／配置／执行对象，Protect的候选过滤和施法者收益请求，Sic状态绑定、犬类士气赋值和受击加成消费。部分回答：冷却默认类别、最终CRT、犬下一次FSM，以及状态的过期／刷新／残留值防护。未回答：所有技能评分、行动频率、编队或包抄，不据名称补齐。

未运行／附加游戏、修改制品或存档、读取新存档或联网。没有运行时验证；主要风险是把收益接收者误写成盟友、把状态标记误写成共享攻击命令、把中间伤害误写成HP损失，以及把未恢复的冷却默认槽当成全类别。完整本轮入口清单在 [eleventh-ally-native.json](../../../_reference/stoneshard-study/eleventh-ally-native.json)。
