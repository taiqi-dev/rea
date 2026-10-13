# 28 流血：部位状态、持续延长与回合损伤

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [身体部位与伤势](25-body-part-hit-selection-and-injuries.md) · [Buff生命周期](11-buffs-and-effects.md) · [战斗回合与伤害](14-combat-turns-and-damage.md)

本轮把流血入口接到了部位流血对象、初始化、重复施加、状态回合事件、生命伤害与清理。**同一部位重施走延长持续的路径；不同部位使用不同状态类型。流血的生命损伤取自状态缓存，再按`o_b_spidervine`是否存在修正；回合事件还对相应部位传入固定Condition变化−1。**这不是从现实失血或常见游戏机制推导出来的规则。

上一轮的随机整数5～7，现在可以命名为**基础持续请求**：它会先按部位Condition放大，新建状态还经过公共持续处理。最终存储值、有效递减次数与玩家可见回合跨度是不同层。

## 1. 制品与证据边界

本篇使用同一份`E:/Steam/steamapps/common/Stoneshard/StoneShard.exe`与`data.win`，Windows x64 GameMaker YYC。总调查在本轮复核目标摘要：

| 制品 | SHA-256 |
|---|---|
| EXE | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| data.win | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

REA provider的既有不可用状态沿用，采用PE映射、YYC登记、OBJT对象/事件表和Capstone静态fallback。没有REA Evidence ID，也没有启动游戏、修改安装文件或读写新的存档。

本轮从`bleed`相关登记和既有25/11/14的调用边开始，选择19个状态、公共助手和继承初始化入口；逐一核对所选登记范围的解码覆盖。完整指令解码不保证所有可达冷分支都在该`.pdata`范围内，也不表示全游戏所有流血来源已恢复。字段名称按`refVA−8`的名称指针绑定；BSS运行值没有用文件零值替代。

本机可选证据：[候选索引](../../../_reference/stoneshard-study/eighth-bleed-candidates.json)、[原生入口/字段/调用](../../../_reference/stoneshard-study/eighth-bleed-native.json)、[对象](../../../_reference/stoneshard-study/eighth-bleed-objects.json)、[部位事件表](../../../_reference/stoneshard-study/eighth-bleed-event-metadata.json)、[字符串初始化](../../../_reference/stoneshard-study/eighth-bleed-constant-initializers.json)、[构造演算](../../../_reference/stoneshard-study/eighth-bleed-derived-example.json)。正文保存足够的地址、实参和限制，这些本机未版本化产物不是唯一解释来源。

下文“确认”指静态控制流和数据读写；算例是人工输入；自研建议另行标注。没有用对象名证明执行频率或最终实战结果。

## 2. 身体部位不是一个共享流血层数

实际OBJT身份如下：

| ID | 对象 | 父ID | record文件偏移 |
|---:|---|---:|---:|
| 6043 | `o_db_bleed_parent` | 1845 | 11355360 |
| 6044 | `o_db_bleed_head` | 6043 | 11355928 |
| 6045 | `o_db_bleed_rhand` | 6043 | 11356136 |
| 6046 | `o_db_bleed_lhand` | 6043 | 11356344 |
| 6047 | `o_db_bleed_tors` | 6043 | 11356552 |
| 6048 | `o_db_bleed_legs` | 6043 | 11356760 |
| 6049 | `o_db_bleed_rlegs` | 6043 | 11356968 |

6044～6049没有自己的事件覆盖。6043登记Create、Alarm2、Alarm3、Other10和Other15，部位子对象继承这些处理。

头部的继承链为：`6044 → 6043 → 1845 o_influence_debuff → 5902 o_debuff → 5900 c_buff → 5899 o_modificators → 5897 c_abstract_states → 2679 o_guiInteractive → 4018 c_GUI`。对应[本机继承记录](../../../_reference/stoneshard-study/eighth-bleed-head-ancestry.json)。这确认了公共状态持续、单位活动列表和清理机制的来源。

流血Create入口`0x14442bf40`调用继承初始化，写`stack=1`（`0x14442c09c`）、`draw_duration=false`（`0x14442c0bf`起），以及`bleeding_damage=0`（`0x14442c366`）。它从实际对象名称和分隔符提取`id_name`，用于后面的部位Condition更新。例如头部实例采用`head`键。这里的`stack=1`不意味着之后每次命中都会增加层数。

`scr_bleed_count@0x14205c870`遍历单位`buffs`并对6043流血父类型做实例类别匹配，成功时递增计数。这是活动流血实例的计数，不是把每个状态的`stack`相加。计数入口没有证明所有单位只可能拥有六种身体结构。

## 3. 施加入门：抗性、免疫和部位键

### 3.1 与BodyPartHit的连接

[25](25-body-part-hit-selection-and-injuries.md)已恢复：一次BodyPartHit更新所选部位Condition后，如果`C<50`且本次伤害`D`为真值，构造：

```text
chanceInput = power((50-C) * D / target.max_hp, 1.8) - R
如果 Chance(chanceInput) 成功：
    bleedChange(target, part, integerRandomInclusive(5,7), R, sourceId)
```

调用`bleedChange`的地址是`0x1412b396e`。玩家的`R`可按受击部位读取；其他路径使用通用流血抗性。此Chance与下游创建是两次不同的门槛，Chance成功不保证出现新实例。

### 3.2 BleedChange的实际参数与拒绝

`scr_bleedChange@0x1412b5260`使用：

| 参数（0起） | 此入口中的用途 |
|---:|---|
| 0 | 目标单位/实例选择值 |
| 1 | 部位键 |
| 2 | 基础持续请求，随后会被改写 |
| 3 | 流血抗性；undefined时从目标`Bleeding_Resistance`取默认值 |
| 4 | 来源参数；undefined时使用当前执行上下文ID，进入后续被动通知等路径 |

正常有限抗性路径先检查目标存在；抗性不小于100，或目标`Bleeding_Immunity`为真，都返回false，不创建/延长流血。抗性与100的比较在`0x1412b590d`，免疫读取在`0x1412b5934`，拒绝路径从`0x1412b5980`开始。浮点比较带公共容差，NaN/非法输入不由这个普通数值规格覆盖。

部位键还与明确初始化的空串比较；空串返回false。对象类型通过`"o_db_bleed_" + part`取得资源索引：前缀初始化`0x1412b7ca3`，拼接`0x1412b5edd`，资源查找`0x1412b5f53`。因此`head`接到6044，`tors`接到6047。未知键、缺失资源或缺失Condition map项的全部错误契约尚未恢复，不宣称传任意字符串都安全。

这里对抗性R的直接使用是拒绝门槛；**没有在BleedChange这段普通路径把持续请求乘`1-R/100`**。发生概率处已经减R，新建持续和每次损伤又分别使用Fortitude，三者不能混成一个抗性公式。

## 4. 持续请求的放大、新建与重施

### 4.1 按部位Condition放大

读取`target.Body_Parts_map[part]`后，在正常有限Condition、有效map项的路径：

```text
CappedC = min(100, Condition)
durationRequest = baseDuration * (1 + power(1 - CappedC/100, 1.65))
```

取部位值的调用`0x1412b60b4`；min助手`0x1412b60e3`；除100、从1减去结果分别`0x1412b614f/0x1412b617d`；指数1.65与power调用`0x1412b61d3/0x1412b621f`；加1、乘基础请求分别`0x1412b623f/0x1412b62a3`，改写第三实参`0x1412b62cc`。

只看到上界min，没有在这里恢复下界clamp。Condition处于正常0～100时，因子从2下降到1：较差的部位状态令持续请求更长。这个参数不是本次HP伤害，也不是新状态的伤害层数。

### 4.2 新建路径与真实单位

用目标`buffs`查找此部位的状态类型（`0x1412b6407`）。未找到则传入公共创建入口（`0x1412b6795`）：

```text
effectCreate(partSpecificObject, durationRequest,
             target, target,
             undefined, undefined, undefined, undefined, undefined)
```

九个实参在该调用前逐项构造。公共创建的第三/第四参数绑定`target/owner`，因此**此处两者初始都取目标**；不能把它改写成“owner必定是攻击者”。来源参数仍用于另一层被动通知，来源归属与状态owner应分别追踪。

公共`effect_create`在相关创建分支把请求写`duration`，加入`target.buffs`。对非`o_condition_debuff`（5908）、`max_duration!=1`的正常持续分支，明确经过：

```text
duration = ceil(durationRequest * (1 - target.Fortitude/100))
如果 target.buffs_is_change 为false、duration非负、have_duration为真：
    duration += 1
```

Fortitude读取`0x1411b9e36`；乘法`0x1411bace2`；ceil调用`0x1411bad7d`；进入后续阶段补偿检查`0x1411b9c31`起，加1的普通数值分支`0x1411b9ef8`。这与[11](11-buffs-and-effects.md)的公共创建边界一致，不能忘掉对象类型、`max_duration`、阶段标记和创建失败门槛。

这条创建路径还在`0x1411bb258`直接分派事件类型2、编号2，即Alarm2；`0x1451ef5a0`直接跳到事件分派器。**事件名Alarm2在这里不表示等待两个回合或两秒。**它是被公共创建显式执行的初始化阶段。

基础`c_abstract_states.Create`有`have_duration=true`，`max_duration`初始化为1000000（`0x14435341e`）。这只是基类初值；活动状态的上限应读取实际字段，不当成任何情形下不可变的游戏常量。

所以5～7属于持续计数器的输入单位，之后由状态逻辑阶段递减，不能直接叫现实秒或固定可见回合。异常Fortitude、其他来源、读档恢复以及共享创建所有拒绝分支仍未全覆盖。

### 4.3 同部位重复：加时，不是重新建一份伤害

已找到相同部位类型的状态时，BleedChange进入其上下文，调用：

```text
modifierDurationChange(durationRequest, undefined)
```

调用点`0x1412b655d`。助手`0x141f6e790`把undefined第二参数改为false；普通路径执行：

```text
existing.duration = min(existing.duration + durationRequest,
                        existing.max_duration)
```

加法`0x141f6eb3b`，min`0x141f6eb89`，写回`0x141f6eb9f`。第二参数为真时有检查目标、阶段补偿+1的另一个分支；**本次重施传undefined，默认false，不走那个补偿分支**。

该重复路径没有再次调用effect_create、Alarm2或写`stack`，也没有重复把Fortitude套到新增请求上。它把已经按当前Condition放大的请求加给现有持续值，并保留原来缓存的`bleeding_damage`。不能将它命名为“刷新到新持续”，也不能说“每次命中伤害翻倍”。

头部和躯干用不同类型查找，因而可以拥有不同实例、不同duration和部位键。这是部位独立性的静态依据；通过外部异常方式造出同部位多个实例时如何规范化，不由这条正常入口完全保证。

## 5. 初始化损伤：缓存数值与spidervine状态修正

### 5.1 Alarm2写基础损伤

`o_db_bleed_parent.Alarm2@0x14442ccd0`在已进入目标上下文的普通分支中清空状态`data`，写若干属性贡献：

| data键 | 初始化值 | 写入VA |
|---|---:|---|
| `Healing_Received` | −10 | `0x14442f45d` |
| `MP_Restoration` | −2.5 | `0x14442f526` |
| `Cooldown_Reduction` | 10 | `0x14442f5f6` |

键由对应字符串初始化绑定确认，不能把它们直接当作最终治疗量、MP点数或固定冷却倍数；最终属性汇总属于公共状态系统。

基础损伤字段的普通数值公式是：

```text
M = target.max_hp
F = target.Fortitude
bleeding_damage = math_round(max(1, (3 + 0.01*M) * (1 - F/100)))
```

M/F读取`0x14442f6ac/0x14442f6c2`；除100与减法`0x14442f715/0x14442f743`；0.01乘M、加3、乘比例`0x14442f770/0x14442f79a/0x14442f7f4`；max调用`0x14442f8ad`；取整调用`0x14442f8f6`，写缓存`0x14442f910`。

通用助手语义已核对：min/max使用包含后续可达片段的上下文，不能只看首段几十字节；乘/减/除按普通double路径证实。`0x140016bc0`是把标量除数包装成RValue后调用除法助手`0x140016cc0`，本机证据保留到该包装器自身ret。math_round正常有限值为`sign(x)*floor(abs(x)+0.5)`。

**这是创建初始化时缓存的基础数值。**Other10并不重新读取max_hp和Fortitude做同一公式。目标属性后来变化是否另有外部入口重跑Alarm2，尚未查遍。

### 5.2 每次事件先重建Pure_Damage_Self

`Other10@0x144434c60`开头显式发送Other15（`0x144434e57`）。`Other15@0x1444361d0`先调用继承事件，再查目标`buffs`是否含3410=`o_b_spidervine`（查找`0x144436398`）：

```text
factor = 1
如果找到 spidervine 状态：factor = 0.7
data["Pure_Damage_Self"] = bleeding_damage * factor
```

命中倍率0.7构造`0x1444363cd`；乘法`0x144436483`；地图替换`0x1444364d1`。这个值不会直接改写缓存的`bleeding_damage`。每次重建data键使spidervine状态能在下一次事件影响损伤输入；它不是销毁流血，也不是减持续值。本篇只确认这个状态对象身份，没有恢复它的物品显示名称或所有施加来源。

Alarm2结尾同样发送Other15（`0x14442fc17`），因此初始化与回合消费之间有实际连接。

## 6. 回合消费：HP损伤与Condition −1分开执行

Other10读取`data["Pure_Damage_Self"]`（`0x144434f10`），传入：

```text
pureDamage(bleedInstance.id, target, storedDamage,
           false, undefined, undefined, undefined)
```

实际七参数调用`0x14443508c`。`scr_pure_damage@0x140194010`在正常目标路径将伤害取整（`0x140194a65`），再调用`scr_simple_damage`（`0x140194b66`）。后者普通路径从HP减取整伤害，[25](25-body-part-hit-selection-and-injuries.md)已有`0x141228dec`的实际减法证据；特殊恢复、死亡和其他覆盖不由普通路径统一保证。

PureDamage还有真实阻止分支：目标buffs含361=`o_db_stasis`时，查找`0x14019481b`后返回数值0（`0x140194861`起）。这是该调用入口的条件，不保证Stasis对全游戏所有伤害或所有状态推进都有同一规则。

随后Other10进入目标上下文。若状态owner与该目标ID不同，写`last_attacker=owner`；之后读取HP，与1比较，HP普通有序值不小于1才进入：

```text
injuryChange(target.id, bleedState.id_name, -1, undefined)
```

HP读取/比较`0x1444351fd/0x14443522f`，HP小于1分支跳过该段；固定−1载荷`0x144435318`，调用`0x14443535f`。所以Condition下降**不是刚才生命损伤的等额值**。它仍由injuryChange的clamp、伤势等级和对象处理约束。下界L的初始化沿25保留未知，不假设永远能无限减到负值。

这两个步骤也不具有“生命损伤必须大于0才扣Condition”的直接联动检查：本段的后续门槛读HP，而不是检查PureDamage返回伤害是否正数。若构造调用已到达Other10、PureDamage被Stasis门槛拒绝且HP仍≥1，局部控制流仍会尝试Condition −1；**不将这个局部演算推广为Stasis状态下实际一定还会调度流血事件**。

Other10还调用`scr_blood_emit`（`0x1444354b1`）、音效与显示更新。这里的血迹/粒子输出不能当作另一个“血量储备”数值。此闭合路径损伤的数值所有者是HP及部位Condition；本轮没有恢复独立血容量、失血百分比或失血休克模型。

## 7. 持续推进与结束清理

状态来自c_abstract_states继承体系，进入单位`buffs`列表，持续由[11](11-buffs-and-effects.md)中`scr_states_duration_dec@0x141ae5c20`处理：

- phase真、`have_duration`真且filter允许时，`duration -= decrement`，默认decrement=1；若有序`duration<1`，调用实例销毁。
- phase假且`is_next_turn`真时，发送Other10并清除该标记。

持续减法`0x141ae673e`、过期比较`0x141ae675f`、销毁`0x141ae6799`、回合事件分派`0x141ae6848`。因此数值输入属于状态逻辑阶段的计数，不是渲染帧。一个玩家动作怎样接到所有phase、创建当轮是否已消耗一次，仍需完整回合调度与运行观察；不能把输入或存储duration直接报成准确UI回合数。

流血部位对象和6043都没有自己的Destroy覆盖；`o_influence_debuff.Destroy@0x142fa3b00`调用继承Destroy（`0x142fa3b41`），最终公共状态清理从目标buffs中删除自身ID并置`stats_is_change=true`。公共列表删除`0x1443550a4`、dirty标记`0x1443550de`见11。默认实例销毁还分派Destroy和CleanUp，不只是让duration归零。

医疗交点也确认了同一身份：`o_skill_bleed_cure`对选定部位流血实例在`0x1446b5e9b`调用销毁助手，其正常默认路径分派Destroy/CleanUp。医疗UI、物品消耗与绷带自身其他状态由医疗模块单独解释，本篇不重复恢复。

结束流血与恢复损伤不是一回事。已核对清理是解除活动状态和请求属性重算；**没有在该清理链把此前扣掉的HP或Condition自动加回来**。被动恢复和治疗另有入口。

Alarm2还存在具体提前拒绝：目标属于3830=`o_skeleton`或3994=`o_Specter`的祖先检查成功时销毁（`0x14442d009/0x14442d0ea`→`0x14442d119`）；`playerGodMode`为真且目标为玩家时也进入该销毁分支。不要把“来源创建过对象”当成必然获得持续流血。

两个易错的相邻副作用单独保留：Alarm2中的同目标/同`id_name`销毁选择的是6138=`o_b_leech_parent`，不是另一流血实例；另一个`duration++`分支选择的是5935=`o_db_feast`，不是流血自身。不能从相邻字段名把它们错误合并到重复流血算法。

## 8. 头部流血的完整构造演算

**这是指令规则的人工输入，不是实战测量。**前提：目标是有效正常单位，有head键；Condition=20、max_hp=120、Fortitude=20、HP=60；免疫false，R<100且上游Chance已经成功；抽出的基础请求为6；目标当前没有head流血；公共创建进入上文普通分支，`buffs_is_change=false`，have_duration=true；相关上限不截短，其他状态不阻止伤害。为解释spidervine交点，假定spidervine持续在活动列表中。

1. **选择类型**：`"o_db_bleed_"+"head"`匹配6044。只创建头部实例，实例的`id_name=head`；躯干已有流血也不等于头部已存在。
2. **请求放大**：`T=6*(1+0.8^1.65)≈10.1519271899`。
3. **新建持续**：`ceil(T*0.8)=9`；在明确阶段补偿前提下加1，实际存储duration=10。它并非原始6。
4. **初始化基础损伤**：`(3+0.01*120)*0.8=3.36`；先max(1,3.36)，再round，缓存`bleeding_damage=3`。
5. **第一次有效Other10**：Other15写`Pure_Damage_Self=3*0.7=2.1`；PureDamage再round为2。正常HP路径`60→58`。若injuryChange下界L≤19、上界正常，head Condition`20→19`；其他部位不由本次−1实参一起下降。
6. **持续计数**：若随后发生一次满足phase真/filter的decrement=1，duration`10→9`。这一步与Other10的时间先后是本例指定的外部调度前提，不声称所有实战路径都固定如此。
7. **结束示例**：若此后外部调度每次先执行一轮有效Other10再递减1，spidervine与伤害门槛持续满足，且没有重施或其他中断，十次共向正常HP减20，`60→40`；在L≤10条件下head Condition`20→10`，duration最后`1→0`，由`<1`门槛销毁并解除列表登记。这是该构造调度的结果，不是UI保证十次伤害。

**同部位重施分支**：改成在第6步后再次以基础6施加头部流血。此时C=19，新的请求`T₂≈10.2379080691`；若实际max_duration不截短，旧duration变为`9+T₂≈19.2379080691`。没有再次创建头部对象，没有再将T₂乘Fortitude，也没有重算缓存基础损伤3。这个非整数持续仍按后续`duration<1`门槛消费，不能擅自改成整数round。

**另一部位分支**：若调用部位变成tors且未找到6047，进入另一实例的创建和初始化。它使用tors自身Condition计算请求，并持有自己的duration。HP仍属于同一个单位，多个部位事件最终可能共同损伤这一HP；实际调度和其他门禁必须逐事件满足，不能仅靠“有两实例”就给固定每回合总量。

## 9. 按证据重组的行为规格

```text
施加流血(target, part, baseDuration, resistance, source)：
    若目标不存在、普通抗性比较达到100、或免疫真：返回false
    若part是已确认的空串：返回false
    由前缀+part解析对应部位状态类型
    读Condition，计算按Condition放大的durationRequest
    在target.buffs查找该类型
    若找到：把request加给其duration并受max_duration上限约束
    否则：公共创建，绑定目标/owner和持续字段，执行Alarm2初始化
    后续通知/统计与创建失败分支保持入口自己的条件

初始化普通目标上的流血状态：
    经过种类、GodMode等拒绝分支
    写data贡献；计算并缓存bleeding_damage
    派Other15形成当前Pure_Damage_Self

有效Other10：
    派Other15：按spidervine是否存在选择1或0.7
    从data读当前Pure_Damage_Self，交给PureDamage及其门槛/取整
    若目标当前HP普通比较至少1：对id_name部位调用injuryChange(-1)
    处理血迹、声音和显示；不把它们当成额外血容量模型

状态持续阶段：
    在phase/have_duration/filter门槛通过时递减
    duration<1时销毁；Destroy/CleanUp解除登记并请求属性重算
```

规格没有补齐全部Chance分布、非法输入、共享创建失败、无限持续哨兵、属性重算时刻、死亡结算和读档恢复。它也不把每个Other10调用自动等同于玩家的一次完整行动。

## 10. 自研借鉴与验证

**以下是独立设计建议，不是原作事实。**可借鉴“部位键→各自状态实例→共享HP”的所有权关系，把基础损伤缓存和当前状态倍率分开，明确同部位重复是加时、刷新、叠强度还是拒绝。生命损失、部位Condition和表现血迹应是独立数据，避免从粒子数量反推健康状态。

我们的实现应自行规定持续时间的阶段起算、分数持续的结束条件、抗性和免疫适用在哪一层、药物是否只减伤或直接解除，以及解除后是否触发恢复。用自己实现的代码、数值与资产，不翻译或搬用目标的恢复代码。最值得独立测试的规则是：相同部位重施、不同行动阶段、spidervine状态生效/过期、目标死亡、阻止HP伤害但Condition仍更新的边界，以及多部位同时流血。

本轮实际验证了部位事件表与继承ID、19个所选登记范围的指令覆盖、键初始化、持续/损伤公式实参、spidervine与销毁交点、构造算术和文档链接/UTF-8。未做目标运行、存档往返、全游戏流血调用者扫描或医疗UI实测，因为范围是静态局部研究。

剩余风险：共享创建与回合调度仍有未恢复分支；原始duration不等于实际UI回合；Condition下界初始化未知；HP应用的特殊覆盖可能改变可见终值；未证明所有单位、物种和所有技能都走本链。本文明确列出普通数值、对象与阶段前提，避免把局部规则冒称整个战斗系统的无条件契约。
