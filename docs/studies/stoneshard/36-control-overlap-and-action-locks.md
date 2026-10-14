# 36 静滞、眩晕重叠与动作锁的解除

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [状态生命周期](11-buffs-and-effects.md) · [格挡响应与反击](38-block-reactions-and-counterattack.md)

本篇研究同一个单位同时受两种控制时，限制如何加入、如何消费、状态结束后如何移除。对象是本机 Stoneshard GameMaker YYC 制品中的 `o_db_stasis` 与 `o_db_stun`，不把技能说明或对象名称当作算法证据。

**主要结果：两种状态的 Alarm 1 都向目标的五个动作锁列表各追加一个 `true`，Destroy 都向每个列表发起一次按位置删除。成员没有携带状态实例 ID，因此本轮没有找到“删除属于自己的唯一锁令牌”的机制。删除一个成员也不等于清空列表。**但删除位置来自尚未恢复初始化的运行时槽，不能确定写成位置 0；本篇的重叠解除演算明确保留这项条件。

静滞还单独处理 `can_speak` 和 `Knockback_Immunity`。前者保存旧值再恢复，后者结束时复制 `Move_Immunity`。它们不是这五个锁列表的派生值，也不能自动获得同样的重叠保证。

## 1. 输入身份与证据层级

输入为 `E:/Steam/steamapps/common/Stoneshard/StoneShard.exe` 与同目录 `data.win`。完整 SHA256：

| 输入 | SHA256 |
| --- | --- |
| EXE | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| data.win | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

延续已有 REA 工具／提供者不可用的限制，以本机 Python、Capstone 5.0.9 读取发行文件。这里的调查记录不是 REA 提供者返回的 Evidence。字段名来自 RIP 引用地址减 8 后的缓存变量记录；对象继承来自 OBJT 的实际记录。未读取运行中内存，不把 BSS 槽当成数值零；`.pdata` 首段可能只是函数片段，未覆盖的分支保持未知。

正文包含关键算法和地址，可以独立阅读。`../../../_reference/stoneshard-study/` 中的链接是本机可选原始证据，未随正式文档版本化。

## 2. 两个真实状态入口

| 对象 | OBJT ID | data.win 记录偏移 | 直接父类 |
| --- | --- | --- | --- |
| `o_db_stasis` | 361 | 9460000 | 5903 `o_physical_debuff` |
| `o_db_stun` | 5918 | 11303944 | 5903 `o_physical_debuff` |
| `o_physical_debuff` | 5903 | 11297512 | 5902 `o_debuff` |
| 静滞执行对象 `o_stasis` | 7154 | 11758408 | 5531 `o_target_spell` |

Stasis 的真实配置行在 EXE VA `0x145e4fc90`，文件偏移 98888848，执行对象字段为 `o_stasis`、类别字段为 `spell`。其 Alarm 0 根据 `is_crit` 在 `0x144c83622 / 0x144c8362c` 产生持续时间修正器的输入 3 或 6；`0x144c837ca` 调用 `scr_skill_get_duration`，`0x144c838a2` 调用共享 `scr_effect_create` 创建对象 361。因此 **3/6 是持续修正器的请求值，不是本轮已确认的最终可见回合数**。

眩晕状态的 Create 入口是 `0x14437fe80`，其中 `0x1443800a2` 选择 `max_duration`、`0x1443800d0–0x1443800da` 写入 double 2。这个初始化常数不证明所有眩晕来源都持续两回合：共享创建会绑定 duration、处理时间补偿，来源还可以传入不同持续请求。本轮选状态本身作对照，没有完整追溯一种特定攻击如何施加眩晕及其成功概率。

本机证据：[配置与对象](../../../_reference/stoneshard-study/sixth-arcane-config-and-objects.json)、[本轮对象复核](../../../_reference/stoneshard-study/tenth-control-objects.json)、[静滞执行 Alarm 0](../../../_reference/stoneshard-study/sixth-arcane-disassembly/gml_Object_o_stasis_Alarm_0.txt)、[眩晕 Create](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Object_o_db_stun_Create_0.txt)。

## 3. 加锁：目标持有列表，状态只追加相同布尔成员

输入是状态实例的 `target`。两个 Alarm 1 先切换到目标实例上下文，再取目标字段并调用 `ds_list_add(list, true)`。`true` 的实际常量在 `0x149536010`：数值 1、类型 `0xD`；不是状态 ID 或状态类型编号。

| 目标列表 | Stasis Alarm 1 实际追加调用 | Stun Alarm 1 实际追加调用 |
| --- | --- | --- |
| `lock_turn` | `0x142a522c2` | `0x14438385d` |
| `lock_attack` | `0x142a52339` | `0x1443838ef` |
| `lock_skills` | `0x142a523b0` | `0x144383981` |
| `lock_spells` | `0x142a52427` | `0x144383a13` |
| `lock_items` | `0x142a5249e` | `0x144383aa5` |

可重新组织为局部行为规格：

```text
状态的 Alarm1 到达有效 target 上下文时：
    对五个 lock 列表，各追加 true 一次
```

这是本轮事件主体的规则，不是完整调度代码。Alarm 1 在生命周期中的首次触发时点、是否存在重复触发或重新加载后的特别路径，尚未闭合。不能根据 Alarm 编号写成“每回合重复加五把锁”。Stun 事件在五次追加之后才检查 `is_load`（`0x144383af1–0x144383b07`）；这个局部顺序证明锁的追加不受该处加载门禁控制，但不证明整个读档流程没有别的安排。

目标单位拥有五个列表；状态实例负责在所研究事件中追加／请求删除。**本轮未见成员级所有者信息。**把列表长度理解为“有效限制数量”是从相同成员、追加和空表消费规则作出的局部结构推导；完整生命周期是否保证每次追加恰好对应一次有效删除，仍待验证。

证据：[Stasis Alarm 1](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Object_o_db_stasis_Alarm_1.txt)、[Stun Alarm 1](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Object_o_db_stun_Alarm_1.txt)。

## 4. 移锁：每类删除一个位置，不按状态 ID 查找

两个 Destroy 在目标上下文逐项取列表，向 `ds_list_delete` 传递两个参数：列表、删除位置。

| 目标列表 | Stasis Destroy 实际删除调用 | Stun Destroy 实际删除调用 |
| --- | --- | --- |
| `lock_turn` | `0x142a4ed0c` | `0x144380538` |
| `lock_attack` | `0x142a4edcd` | `0x1443805c5` |
| `lock_skills` | `0x142a4ee8e` | `0x144380652` |
| `lock_items` | `0x142a4ef4f` | `0x1443806df` |
| `lock_spells` | `0x142a4f010` | `0x14438076c` |

Stasis 的删除位置从 `0x1498b0378` 复制，例 `0x142a4ed86`；Stun 从 **另一个槽** `0x1498e9d70` 复制，例 `0x144380502`。两者不是同一槽，也不是已经解码的 `true` 常量。本轮没有恢复它们的初始化和运行值，因此局部规格必须保留：

```text
Stasis Destroy：对五个列表执行 deleteAt(list, runtimeSlot_1498b0378)
Stun Destroy：对五个列表执行 deleteAt(list, runtimeSlot_1498e9d70)
```

在所读删除片段中，没有先按本状态 ID 查找列表位置，也没有 `ds_list_clear`。所以可确认“按位置请求删除一个成员”，不能写成“清空所有控制”“精确撤销自己的 ID”或“固定删第零项”。如果位置有效且列表有两个成员，正常单元素删除后的长度是 1；若位置无效，不能凭本轮静态证据保证删除成功及失败表现。

为核对 Stun 槽做了限定 PE 节范围的 RIP 引用定位，得到五处读取，没有定位到初始化写入。扫描选择节 RVA 不大于 `0x07000000` 的文件字节，再用局部指令解码核对候选 RIP 引用；这不是全程序可达控制流分析。结果不能排除指针表、间接写入或其他区域初始化。证据：[删除槽定位记录](../../../_reference/stoneshard-study/tenth-control-delete-slot-xrefs.json)、[Stasis Destroy](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Object_o_db_stasis_Destroy_0.txt)、[Stun Destroy](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Object_o_db_stun_Destroy_0.txt)。

## 5. 谁消费锁：限制是多个动作入口的门禁

### 5.1 已确认的攻击门禁

`scr_enemy_hit` 在 `0x14112bc16` 读 `lock_attack`，`0x14112bc64` 调用 `ds_list_empty`，对结果取真值。`0x14112bc73` 在结果为假时跳往 `0x14112cf98`，避开该攻击分支；列表为空后还要通过其他门禁。**空表是这段攻击分支的必要条件，不是发动攻击的充分条件。**

这个消费者检查空表，没有读取里面某个成员是不是 Stasis、Stun 或具体 ID，因此在这个入口中，剩余任意一个有效成员仍会使空表检查失败。

### 5.2 已确认的技能／法术预告取消门禁

`scr_global_turn_end`有多组执行对象遍历。这里与37选用同一组5513多回合范围技能，读取其owner锁列表并检查执行对象class；不把前一组循环的位置直接当成这两招的消费者：

- `lock_skills`读取 `0x1419c1a24`、空表调用 `0x1419c1a9b`；非空路径继续比较class与真实字符串skill，比较调用 `0x1419c1b13`。
- `lock_spells`读取 `0x1419c18d7`、空表调用 `0x1419c194e`；相应路径与spell比较 `0x1419c19c6`。
- `lock_turn`读取/空表调用 `0x1419c17f0 / 0x1419c1867`；还要求执行实例is_movement为真（字段读取 `0x1419c187f`）。本篇不把该字段名称概括成所有技能的取消规则。

本轮联查确认 Shockwave 与 Rock Toss 的 Create 实际把 class 设为 `skill`。它们满足技能类的锁检查条件，与玩家 Stasis 配置的 `spell` 类别不是同一个字段归属：前者是被取消的技能执行实例，后者是施加控制的技能配置。取消及预告清理的具体后续见 [37 预告攻击的打断与取消](37-telegraph-interruption-and-cancellation.md)。

### 5.3 尚未完整闭合的消费者

`lock_items` 的生产和删除已确认；本轮读取 `scr_can_use_items` 的 `.pdata` 首段未看到该字段，不能据此断言它不受控制，也不能把这个名字相近的函数冒充锁消费者。玩家道具输入派发、各类技能按钮以及其他攻击路径未全部恢复。

`scr_enemy_turn` 中存在 `lock_turn → ds_list_empty`，但当前 AI 有新版 FSM，旧／共享助手中的存在不自动证明每个敌人当前回合都会走这段。当前敌人选择路线见 [33 技能评分与行动选择](33-arbalester-skill-scoring-and-action-choice.md)。

证据：[攻击门禁](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Script_scr_enemy_hit.txt)、[公共回合末](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Script_scr_global_turn_end.txt)、[当前 AI 与旧助手的边界](../../../_reference/stoneshard-study/ninth-ai-disassembly/gml_Script_scr_enemy_turn.txt)。

## 6. `can_speak` 与击退免疫是独立标量

Stasis Alarm 2 在目标上下文读取 `target.can_speak`（`0x142a53201`），保存到状态自己的 `target_can_speak`（`0x142a53217 / 0x142a53238`），随后用 type `0xD`、值 0 写回此前取得的目标字段（`0x142a53251–0x142a5326c`）。这形成“保存旧权限 → 写 false”的局部链。

Destroy 读取自己的 `target_can_speak`（`0x142a4f07d`），选择目标 `can_speak` 写字段（`0x142a4f093`）并复制回旧值（`0x142a4f0b4`）。它没有在该恢复片段重新统计全部控制状态，也没有根据五个列表重算说话权限。

实际消费者 `o_enemy.Other16` 在 `0x14364e1af` 读取 `can_speak`，取真值后在 `0x14364e1c5` 为假时跳到 `0x14364e6ea`，跳过这个局部分支。它还有其他门禁，因此恢复为 true 不保证立即发出台词，更不证明玩家、所有 NPC 对话及所有 UI 共用这一个入口。

Stun 的本轮已解 Create、Alarm 1／2、Other 10 和 Destroy 没有本字段读写，不能因此排除父类、未覆盖片段或其他控制状态对它的影响。尤其不能宣布“任意两个禁言状态按任意结束顺序都安全”：保存旧值的办法需要考察其他写入者与恢复顺序。

另一个标量例子：Stasis Alarm 1 写 `Knockback_Immunity=true`（选择字段 `0x142a524ae`，复制 `0x142a524d6`）；Destroy 读取目标 **`Move_Immunity`**（`0x142a4f026`）并复制给 `Knockback_Immunity`（`0x142a4f03c / 0x142a4f05d`）。这是按另一个字段重设，不是恢复一个已保存的原击退免疫值。若别的效果也操作击退免疫，实际叠加是否正确尚未验证，不能把列表的保留行为套到这里。

证据：[静滞权限生产](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Object_o_db_stasis_Alarm_2.txt)、[权限恢复](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Object_o_db_stasis_Destroy_0.txt)、[敌人消费者](../../../_reference/stoneshard-study/tenth-control-disassembly/gml_Object_o_enemy_Other_16.txt)。

## 7. 持续与解除：回合递减和 Alarm 分开

共享 `scr_states_duration_dec` 入口 `0x141ae5c20` 已在 11 恢复：通过 phase/filter 门禁后，对 `have_duration` 真状态减去递减实参；剩余持续值小于 1 的有序比较路径销毁。减法 `0x141ae673e`、比较 `0x141ae675f`、销毁请求 `0x141ae6799`。另一阶段派发 Other10（`0x141ae6848`），不能把派发状态事件与递减当成同一件事。

正常销毁运行时会派发 Destroy，再清理实例，见 11 的运行时销毁链。因此本篇两种状态的解除事件确实存在于实际实例生命周期，不是只把 duration 写成零。是否每一种强制清理、离图、死亡、加载失败都保持同样事件顺序，未在本轮证明。

Stun Other10 入口 `0x144384400` 的所读主体写 `shine=200`（`0x14438447f`），随后继承分派；本轮不能把它描述成独立 `duration--`。Stasis Other10 的已读局部还有被动技能与 duration 门禁，不能概括为纯计时器。

**持续构造例子**：状态进入共享递减前的实际存储 duration=2，have_duration=true，phase/filter 允许，decrement=1。第一次变为 1，仍保留；第二次变为 0，走销毁请求，之后进入该状态 Destroy 的移锁与权限恢复。2 是本演算指定的实际存储输入，不冒充 Stasis 技能修正后必然得到的数值；这两次递减也不能未经时序核对改称两帧 Alarm 或恰好两次玩家按键。

## 8. 双状态重叠解除：可确认的部分与条件

以下是**构造演算，不是运行观测**。指定起始五个列表均为空、can_speak=true；两个状态各成功执行一次加锁 Alarm 1；Stasis 的保存／关闭说话权限分支已到达；两个 Destroy 都到达有效目标，并且运行时删除位置对当时列表有效。最后一项是本轮未恢复槽值所需的明确条件。

| 步骤 | 每个动作锁的长度 | can_speak | 能否通过已查攻击空表门禁 |
| --- | --- | --- | --- |
| 初始 | 0 | true | 此门禁通过，仍有其他条件 |
| Stasis 初始化／加锁 | 1 | false；状态缓存 true | 不通过 |
| Stun 加锁 | 2 | 在已读自身事件中未改写 | 不通过 |
| Stasis 先结束，单元素删除成功 | 1 | 还原缓存 true | 仍不通过 |
| Stun 后结束，单元素删除成功 | 0 | 该自身清理片段未改写 | 此门禁可通过 |

这里两条列表成员都是 `true`。即使删除位置恰好对应另一状态先加入的成员，所查空表消费者仍只看到剩下一个成员，不区分来源。**这是基于相同成员与空表检查的局部语义，不是成员有唯一所有权的证明。**

在 Stasis 先结束而 Stun 留存的构造中，可以同时出现“说话权限恢复为 true、攻击列表仍非空”。两者不矛盾：它们由不同表示和不同消费者管理。也不能据此说留存眩晕的单位一定会讲话，因为 Other16 还有别的门禁。

如这个单位有等待释放的 `class=skill` 预告对象，剩余 `lock_skills` 非空仍满足技能类取消门禁。该联系无需名单成员身份，但需预告对象真的到达公共回合末处理；本篇不补上创建与首个回合末之间尚未观测的时间顺序。

## 9. 独立游戏设计可以借鉴什么

以下是自研建议，不声称原作已经实现：

1. 按行动类别聚合限制，攻击、移动、道具、技能、法术和说话由各自明确消费者检查；避免某个 UI 按钮禁用而执行入口仍可绕过。
2. 用状态实例作为限制所有者，返回独立句柄；移除指定句柄后从仍存在的限制重算有效权限。原作本次看到的是相同布尔成员和位置删除，自研无需沿用其表示。
3. 对说话／击退免疫采用基础属性加仍存状态的合并规则，明确优先级；不要只靠“保存旧值再还原”保证多写入者任意退出顺序。
4. 明确一次初始化、持续刷新、加载重建与销毁是否配对，重复结束必须幂等。针对 A先结束/B先结束、同类刷新、目标死亡、重载和施法打断分别验证。

可把本篇作为独立行为规格的参考，自己编写实现和测试，不移植恢复指令或原作代码。

## 10. 回答状态、未做与风险

| 问题 | 状态 | 边界 |
| --- | --- | --- |
| Stasis／Stun 对五类锁的生产与清理 | 已确认局部指令 | 同值追加、按位置删除；初始化 Alarm 调度未完整恢复 |
| 单状态结束是否直接清空所有锁 | 已确认所查片段没有这样做 | 有效单元素删除保留其他成员；删除位置运行值未知 |
| 锁成员是否属于独立状态 ID | 未发现此机制 | 本次新增成员实际为 true，不宣称全游戏没有其他表示 |
| 攻击／预告技能与法术消费 | 已确认所列入口 | 不覆盖每种行动、全部玩家输入或全部敌人调度 |
| can_speak 保存、关闭、恢复与一处消费 | 已确认局部链 | 任意多禁言者的叠加未验证 |
| 实际回合持续与加载／死亡清理全路径 | 部分回答 | 共用递减规则已查，实例的完整运行时序未采集 |
| lock_items 的实际使用门禁 | 未回答 | 本轮名字相近的道具助手首段没有形成消费桥 |

未运行游戏、未附加进程、未读运行内存、未改游戏或存档。本轮只新增正式说明和可再生成的本机调查输出，没有做运行验证。主要剩余风险是删除槽值、重复初始化／清理配对、标量权限多写入者覆盖和未覆盖的输入入口；因此不能把构造演算当作任意游戏场景的行为保证。

本轮完整选定入口和引用记录：[tenth-control-native.json](../../../_reference/stoneshard-study/tenth-control-native.json)。其他依赖见 [11 状态生命周期](11-buffs-and-effects.md)、[22 特殊技能候选](22-special-skill-candidates.md) 与 [33 当前敌人行动选择](33-arbalester-skill-scoring-and-action-choice.md)。

## 11. 第十三轮收敛：移除一个来源后，剩余控制靠什么保持

本节为跨项目自研评审回答“按来源移除一个控制后是否会错误解锁”。沿用 [本轮输入身份](../../../_reference/stoneshard-study/thirteenth-target-identity.json)，复核第3～5节的实际生产、清理和消费；不声称这两个状态之外的所有控制都采用同一表示。

结论需要分开三种容器：

| 表示 | 已查实例及来源 | 移除一份的确切含义 |
| --- | --- | --- |
| 单位buffs列表 | 公共状态清理按自身id找索引再删；临时属性状态也有自身id退出 | 活动状态实例的登记身份，可只删除该实例；不等于自动按施法者批量移除 |
| 五个动作锁列表 | Stasis/Stun各向每表追加true一次，Destroy按位置删一次 | 所查成员没有状态id/sourceKey；有效删除一项后其他相同成员仍在 |
| can_speak/Knockback_Immunity标量 | Stasis存旧说话值再还原；击退免疫从Move_Immunity重设 | 不是活动锁列表派生值，不具备同样的成员数量保留推导 |

这里的“五个动作锁”是 `lock_turn/lock_attack/lock_skills/lock_spells/lock_items`。**不是一个全局 canAct 布尔，也不是每个来源自带贡献key/句柄的集合。**所查真实生产只是 `ds_list_add(list,true)`：Stasis五处 `0x142a522c2..0x142a5249e`，Stun五处 `0x14438385d..0x144383aa5`；布尔常量 `0x149536010` 明确为type13、值1。

Stasis Destroy的五处删除 `0x142a4ed0c..0x142a4f010`，Stun `0x144380538..0x14438076c`，没有先按状态id找锁成员，也没有清空整表。与此相对，临时属性状态的 **buffs登记列表** 在 `0x144515a81` 按自身id查索引，`0x144515ad1` 删除，这个新增限定证据见 [11第10节](11-buffs-and-effects.md#10-第十三轮收敛重复施加的四种语义不能合并成一个-stack-规则)。两种列表不同，不能从后者推导前者也有令牌所有权。

### 11.1 已闭合的保留机制：非空成员继续阻挡

攻击消费者 `scr_enemy_hit` 在 `0x14112bc64` 只问 `ds_list_empty(lock_attack)`；非空时跳过已查攻击分支（`0x14112bc73`）。它不查询剩余成员来自谁。预告技能处理也检查锁列表是否空，并配合执行对象class：技能锁检查 `0x1419c1a9b`，与skill比较 `0x1419c1b13`；法术锁检查 `0x1419c194e`，与spell比较 `0x1419c19c6`。因此只要剩余列表非空，这些所查门禁仍阻挡；其他未覆盖的动作消费者不能直接照搬。

**条件例A：Stasis先结束。**设五表初始空，Stasis与Stun各恰好执行一次加锁，两状态Destroy最终均到达同一有效目标，每次删除位置在当时列表有效。每表长度按 `0 → 1 → 2 → 1 → 0` 变化。Stasis结束后长度1，攻击空表门禁仍失败；已挂起的skill预告在到达对应回合末处理时仍满足非空技能锁取消条件。没有必要知道删掉的是第一个还是第二个true，所查消费者不区分成员身份。

**条件例B：Stun先结束。**前提同例A，但结束顺序相反。第一次成功删除后每表仍长1，第二次后为0；在已查空表消费层面结果相同。这是同值成员与有效单项删除的推导，不是运行中观察，也不是“任意结束路径都幂等”的证明。

删除位置仍分别来自运行时槽 `0x1498b0378` 与 `0x1498e9d70`，未恢复它们的初始化/运行值；例A/B明确依赖有效位置。不能把位置0、来源id或默认零写进自研规格当成原作事实。如果删除失败，或同一状态多次加锁却只删一次，就不能保证长度守恒。

### 11.2 重复施加控制是否重复加锁：尚未闭合

“两个不同控制各有一个实例”与“同类型控制再次施加”是两道问题。前者有本篇Stasis/Stun生产与清理；后者需要证明新请求最终复用旧状态、替换旧状态还是成功创建第二实例，以及Alarm1是否再次执行。本轮没有补全这条桥。

**条件例C：只刷新持续的自研选择，不是原作已确认规则。**自研若用状态实例锁句柄L，重施同状态只改变持续而不创建新实例，L应仍只有一份；状态结束删除L。若自研决定按来源并存L1、L2，则删除L1后保留L2并重算动作权限。原作此次看到true列表与按位置删除，不是这套有来源句柄的实现；该例只用于明确我们应测试的规格。

不能把 [11第10节](11-buffs-and-effects.md#10-第十三轮收敛重复施加的四种语义不能合并成一个-stack-规则) 的临时属性按source+atr刷新/新增机制直接用于Stasis/Stun：它创建6171临时数值状态，而本篇控制对象361/5918还有各自加锁事件。更不能因为公共助手存在stack字段，就宣称控制刷新必然不加锁或控制可无限叠强度。

### 11.3 标量权限的反例边界

**条件例D：攻击仍锁，但说话标量已恢复。**Stasis执行保存can_speak=true并置false的路径，随后Stun成功加锁；Stasis先结束且单项删除有效。动作表仍长1，但Stasis恢复缓存true（`0x142a4f07d..0x142a4f0b4`）。这不证明单位会立即讲话，敌人消费者 `0x14364e1af..0x14364e1c5` 还有其他条件；只证明该标量并不是“存在任意动作锁就必为false”。

**条件例E：多写入者的保存旧值风险，是结构推断。**自研若A、B都用“存旧值再设false”，起始true，A存true、B存false；A先退出还原true时B仍在，可提前放开；B最后退出还原false又可能留下禁用。这个例子没有证明Stoneshard存在两个这样的禁言状态，也没有证明Stasis正常入口允许两个同类实例；它解释为何本次看到的标量结构不足以保证任意多来源的安全恢复。

未做运行验证、读档/死亡/离图压力场景；未恢复动作锁删除槽与同类控制重施策略。自研可以借鉴按动作类别分别消费限制，但建议自行采用实例身份句柄与仍存限制重算，并分别测试刷新不重复登记、A/B两种退出顺序、重复销毁、目标退出。该建议不是原作代码还原。
