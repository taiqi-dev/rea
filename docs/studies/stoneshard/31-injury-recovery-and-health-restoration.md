# 伤势恢复、生命恢复与状态降级

[总目录](README.md) · [部位命中与状态损失](25-body-part-hit-selection-and-injuries.md) · [各部位减益](27-body-part-injury-debuffs.md) · [流血](28-bleeding-and-blood-loss.md) · [夹板稳定](30-splints-and-injury-stabilization.md)

本篇补三条已确认的局部恢复路径：单位恢复条请求治疗、治疗入口向部位 Condition 分配恢复、特定状态直接增加部位 Condition。还解释为什么“Condition 增加”“伤势降级”“减益解除”不是同一个提交点。不是整个游戏的完整医疗或睡眠模拟；所有例子均为构造演算，未运行游戏。

## 1. 范围和状态所有权

同一安装制品 `StoneShard.exe` 的 SHA256 为 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，`data.win` 为 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。本轮开始为 2026-10-12 20:41:27 PDT（2026-10-13 03:41:27 UTC）。继续使用本地 PE、资源索引和 Capstone 5.0.9 静态分析；未产生 REA Evidence 会话。

| 状态 | 所有者与用途 | 不能混同的含义 |
| --- | --- | --- |
| HP / max_hp | 单位生命及最大生命字段 | 不是某个部位的 Condition |
| Health_Threshold | 治疗入口计算生命上限时读取的比例字段 | 不是本文已经恢复全部生产公式的固定100 |
| Health_Restoration_Bar / Health_Restoration | 单位的恢复条及本次累加量 | 不等于每次必定恢复同样的HP |
| Healing_Received | 治疗请求的比例修正 | 表中的−10贡献不等于直接扣10HP |
| Body_Parts_map | 单位按部位键存储的 Condition | 不等于对应伤势对象的存在状态 |
| injury_point | 治疗更新部位状态时的上界 | 基础初始化100，后续运行状态可能不同 |
| 普通/稳定伤势对象 | 单位 buffs 内的实际实例 | 可以有自己的降级、销毁和属性清理事件 |

上一轮确认 `scr_bodyPartsConditionChange(target, undefined)` 会把增量转成0，主要用于刷新；本轮又发现这个入口有明确的正增量调用。因此不能只看调用名称就把它命名为持续恢复或持续伤害。`scr_turn` 中另一条腿部更新反而传入−4，其完整动作门禁不属于本篇恢复链。

## 2. 单位恢复条怎样请求治疗

`scr_unit_regen@0x140237d90` 已接入回合处理：既有指令记录确认 `scr_unitTurnEvents` 在 `0x1416a1600`、`scr_global_turn` 在 `0x1416c422c` 调用它。两处调用不能相加宣称一个角色每回合必定恢复两次；分支、单位集合和调度资格仍需要分别解释。

已核对的正常生命恢复分支要求 HP 小于 max_hp，并检查 `lock_regen` 列表为空。前面还读取 `in_battle`、`ai_is_on` 和 `entrance_rewind` 状态，决定是否绕过生命恢复段；没有恢复所有调用方参数与组合，不宣称战斗内外一律按同一频率恢复。

通过该段资格后：

```text
Health_Restoration_Bar += Health_Restoration
如果 Bar 与100的比较通过：
    request = ceil(0.05 × max_hp) × 参数0
    scr_restore_hp(unit.id, request, undefined)
    Bar -= 100

HP_turn > 0 时，另有 scr_restore_hp(unit.id, HP_turn, undefined)
HP_turn < 0 时，另有负生命效果的损伤路径
```

参数0在 undefined 分支被设为数值1（`0x14023814b`）。恢复条累加在 `0x1402385c2`；与100比较在 `0x14023860b`；0.05标量在 `0x14023869e` 构造，乘 max_hp 在 `0x1402386b9`，ceil 调用在 `0x14023871a`；治疗调用在 `0x14023889e`，条减100在 `0x1402388db`。这里是一次 if 路径，没有看到用 while 连续消费多个100。

**构造例子：**单位 max_hp=100，恢复条90，恢复量20，参数0=1，且全部门禁通过。本次条变110，产生 `ceil(5)×1=5` 的治疗请求，条剩10。5仍是提交给治疗入口的请求，会继续受 Healing_Received、生命上限和其他事件影响；不是无条件最终加5HP。若构造初始条250，本次这条 if 只减一次100，不能改写成一次连治三次。

## 3. 治疗请求怎样进入生命和部位恢复

核心入口 `scr_restore_hp@0x141885050` 选择目标上下文，读取 Healing_Received。对普通有效有限数值，本段把请求修正为：

```text
A = math_round(rawRequest × Healing_Received / 100)
如果 A 非正或目标HP小于1：离开本治疗路径
发送已经定位的技能/Buff回调（完整副作用尚未恢复）
cap = math_round(max_hp × Health_Threshold / 100)
H = A - (cap - 本段读取的原HP)
生命更新另走上下限、回调和日志分支
只有 H>0 且其他后段条件成立时，处理部位恢复
```

Healing_Received 读取在 `0x141885621`，乘法和除100在 `0x141885697/0x1418856a5`，取整在 `0x141885712`。生命上限读取和取整在 `0x14188591f..0x141885a02`；上限减旧HP在 `0x141885a7b`，A减该差额在 `0x141885ad0`，H 保存到局部 `rbp+0x90`。生命写入后，`0x141886af0/0x141886b0d` 检查H是否大于0；非正时绕过部位恢复。

H是超出生命上限缺口的剩余治疗量，不是 `min(A,缺口)`，也不是实际加到HP的量。在正常 A>0、HP不高于cap的构造条件下，本路径只有请求超过缺口才恢复部位：例如cap80、HP76、A5，H=1；HP60、A5则H=−15，跳过部位恢复。达到当前生命上限不等于所有部位已恢复；此时新请求仍可能全部进入部位恢复段。上游回调、生命实际写入、取整和日志分支是不同步骤，本文不承诺原HP高于cap或多目标调用的全部行为。

这里的 `math_round` 是已有研究确认的自定义取整，普通有限值为 `sign(x)×floor(abs(x)+0.5)`。例如请求10、Healing_Received=85，得到 A=9，而不是8.5。属性贡献表和当前聚合值怎样对应见 [27](27-body-part-injury-debuffs.md)。

## 4. 部位恢复量按低于100的数量归一化

治疗后段先遍历 Body_Parts_map，统计数值 C<100 的条目数量 N（读取 `0x141886f0a`、小于100判定 `0x141886f2e`、计数增加 `0x141886f71`）。N必须通过后段的正值检查才继续。

随后再次遍历部位，以当前条目 C 为基础计算：

```text
a = 0
如果当前目标是玩家，Study of Anatomy实例存在且is_open为真：a = 0.1

对每个部位键 part：
    q = 0.4
    按 level=1、2 查询 o_db_inj_ + part + level
    若查询到匹配伤势实例：q = 0.25
    gain = (100 × H / max_hp / N) × (q + a)
    Body_Parts_map[part] = min(injury_point, C + gain)
```

默认0.4在 `0x141887309`；等级循环的起点1在 `0x141887403`，与3作严格小于比较在 `0x1418874bc`；名称拼接和资源查找在 `0x1418875aa..0x1418876ee`，实例查找在 `0x1418877bb`；命中时写0.25在 `0x14188781c`。Anatomy对象6726的存在/is_open门禁在 `0x141886c27/0x141886c4c`，加成0.1在 `0x141886ca7`。

H/max_hp 在 `0x1418878ab`，乘100和除N在 `0x1418878d5/0x141887928`，q+a在 `0x14188798f`，乘归一化量在 `0x1418879e4`。最后读取 injury_point，把 C+gain 与它取最小值，再写回 map（`0x141887b42/0x141887bc8/0x141887c17`）。该段没有再对每个写入条目重新加一次 `C<100` 门禁；已经满100的条目也可以走更新，但会受上界限制。

关键边界：

- N 使用100作为统计阈值，写入上界却读取 injury_point；不能无条件把二者统一成同一个运行变量。
- 本轮确实只见等级1、2查询，未见本段显式查询普通等级3。不要自行补一个第三次查询来“修正”原作。
- 这些查询用普通对象名，稳定对象的父链不含对应普通伤势对象，见27；稳定状态没有在本段被统一改成0.25。
- 所谓“0.4”和“0.25”是恢复系数，不是每回合直接增加0.4或0.25 Condition。
- 部位map在这里直接写回，未调用 injuryChange；状态对象何时随之降级，需要后续对象事件。

### 实例查询不是布尔字段

`scr_instance_exists_in_list@0x14179c350` 的第二参数 undefined 转成−4，再通过当前self.id和字符串 `buffs` 查询默认列表（`0x14179c872/0x14179c8fa`）。正常有效列表逐项调用 `instance_is(entry,asset)`；第三参数undefined走非计数模式，命中返回当前列表实例，未命中写 type0、数值−4（`0x14179ce4a..0x14179ce5b`）。

调用方再用 GameMaker 真值助手转换。其普通double分支是大于0.5（`0x145196dfb..0x145196e03`），所以这个−4哨兵是假，不采用C语言的“非零就为真”。无效列表和其他动态类型分支不能由这个正常例子推定。

## 5. 治疗与部位恢复的贯通演算

设目标 max_hp=100、HP=80、Health_Threshold=80、Healing_Received=100。恢复条90、Health_Restoration=20，其他门禁通过、参数0=1。本次请求5，故 A=5、cap=80、H=5−(80−80)=5。构造仅两部位低于100，N=2，其余四部位为100；injury_point=100，没有Anatomy加成：

| 部位状态 | 初值与匹配前提 | q | 本次gain | map写入结果 |
| --- | --- | ---: | ---: | ---: |
| head | C=24，buffs存在普通head2 | 0.25 | `(100×5/100/2)×0.25=0.625` | 24.625 |
| tors | C=60，存在稳定tors1，没有匹配普通tors1/2 | 0.4 | `(100×5/100/2)×0.4=1` | 61 |
| 其余四部位 | C=100 | 按各自匹配状态 | 仍可计算 | 被 min(100,100+gain) 限为100 |

若开通Anatomy，head gain变0.875、tors gain变1.25。在这些构造前提下可确定相应map值；尚不能保证界面在同一帧显示新的等级，也不能用这个例子证明恢复条每个玩家行动都被调用一次。

把同一例子的HP改为76，其余前提保持，则H=1，head/tors的增量分别降到0.125/0.2；HP改为60则H非正，不执行这段部位恢复。这个差异来自已恢复的“剩余治疗量”分支，不是人为假定治疗会按六个部位平均分摊。

## 6. Condition增加以后，伤势怎样降级

稳定伤势的独立 Other10 事件已恢复，详见27：

| 当前稳定等级 | Condition门槛 | 已确认动作 | 关键位置 |
| --- | --- | --- | --- |
| light / 1 | C≥90 | 销毁稳定伤势实例 | `0x144407937/0x14440796b` |
| mid / 2 | C>50 | 名称2换1，调用伤势实例替换 | `0x144408112/0x14440832c` |
| deep / 3 | C>25 | 名称3换2，调用伤势实例替换 | `0x144408e32/0x14440904c` |

这里的比较带已核对的浮点容差。**构造状态例：**稳定deep的Condition从24升到26，下一次执行相应Other10时可以转为mid；后续升到51且mid事件执行，转为light；达到90且light事件执行，走销毁。这是满足事件和门禁的状态序列，不是“一次治疗必定在同一回合连降三级”的实测结果。

这也不同于25中受伤时0/25/50的等级判定：受伤生产、恢复降级和轻伤解除有各自门槛。Condition刚越过50不表示所有轻伤减益立刻清空。替换/销毁后的属性重新汇总与锁列表清理见27；夹板即刻加35及普通→稳定替换见30。

## 7. 特定状态还有直接增加部位Condition的路径

`o_b_spleenwort.Other10@0x142d8b750` 进入状态target上下文，读取target.id，把数值0.1作为第二参数传给 `scr_bodyPartsConditionChange`（`0x142d8b8d0`）。0.1来自实际RValue `0x14956e198`，不是默认undefined的0增量刷新。

该助手遍历Body_Parts_map每个键，并调用 `injuryChange(target,part,delta,undefined)`，所以这是全体部位的正增量路径。该路径和治疗入口直接map写入不同；injuryChange沿用25确认的clamp上界、未知下界与对象处理门禁。

**构造例：**四部位均100，head=24、tors=60，delta=0.1，injury_point=100且未知clamp下界不高于这些值。一次该事件后head=24.1、tors=60.1，其余保持100。不能把这一次事件称为一小时或一回合，也不能把效果名存在推定为玩家已吃了药草：物品使用、时长与事件派发的完整链本篇未恢复。

恢复类药剂另有 `o_b_regen.Other10@0x1444b64e0` 调 `scr_restore_hp`，本轮已定位真实调用（`0x1444b68ad`），没有把它与Spleenwort的全体0.1直接增量混为一条公式。所有食物、药剂、睡眠和休息服务的参数表未全面恢复。

## 8. 可以独立借鉴的设计与后续问题

可借鉴的是三个状态层次：治疗事件产生量，生命/部位状态接收量，伤势对象响应阈值并清理贡献。恢复条把连续量变成离散请求；阶段阈值可以防止数值在边界附近来回切换。自研时应明确满生命是否继续恢复部位、按哪种数量归一化、普通和稳定状态的系数、事件顺序，以及状态重施/降级是否保留身份。这里提出的是我们的规格选择，不复制原作恢复代码。

已回答：一个恢复条提交例子、Healing_Received修正、部位恢复局部公式、Anatomy加成、稳定伤势降级/解除、一个直接正增量例子。

部分回答：普通伤势全部降级路径、恢复事件与属性缓冲更新的先后、休息/睡眠怎样改变恢复速度、生命上限的完整生产规则。

未回答：所有满血/越上限/特殊回调/多目标组合的恢复结果、全部物品与睡眠服务、精确实际回合和离屏更新频率，以及保存后所有医疗状态的恢复。没有游戏运行、存档往返或网络观察；本轮不需要改变REA生产代码，因此未执行REA构建和代码测试。

## 本机复核记录

- [本轮目标身份](../../../_reference/stoneshard-study/eighth-target-identity.json)、[恢复入口/字段/调用](../../../_reference/stoneshard-study/eighth-recovery-native.json)
- [恢复与助手指令目录](../../../_reference/stoneshard-study/eighth-recovery-disassembly)、[常量与默认列表助手检查](../../../_reference/stoneshard-study/eighth-recovery-helper-checks.json)
- [恢复构造演算与公式核对](../../../_reference/stoneshard-study/eighth-recovery-derived-examples.json)
- [既有回合调用](../../../_reference/stoneshard-study/third-turn-damage-native.json)、[min完整上下文](../../../_reference/stoneshard-study/fifth-displacement-disassembly/runtime-min-context.txt)
- [伤势对象与父链](../../../_reference/stoneshard-study/eighth-injury-objects.json)、[父对象记录](../../../_reference/stoneshard-study/eighth-injury-parent-objects.json)

本机产物被Git忽略，正文保留公式、入口和限制。剩余风险主要是把局部量当最终面板结果、把事件调用当固定时间频率，以及未知回调和动态类型分支。
