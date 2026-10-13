# 30 夹板：即时部位恢复、伤势稳定与分阶段清理

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [29 绷带](29-bandages-and-wound-treatment.md) · [27 部位伤势减益](27-body-part-injury-debuffs.md) · [31 恢复与治疗](31-injury-recovery-and-health-restoration.md)

真实玩家夹板动作并非只写一个“稳定”标志：`o_inv_splint` 绑定 `o_skill_stabil_wound`，后者明确设置heal=35；提交进入 `scr_injury_stabil`，先对所选部位的Condition加35、上限100，再把匹配的普通伤势实例销旧建新为对应 `_stabil` 状态。**即时Condition恢复、稳定状态、恢复过程中的降级/移除，是三项不同的输出**。本轮没有在该即时助手中确认HP直接增加，也没有证明每种程度的伤势都当场消失。

## 1. 身份和覆盖

同一 Stoneshard 安装制品，2026-10-12 20:41:27 PDT开始。完整摘要与 [证据范围](00-evidence-and-scope.md) 一致：EXE `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`；data.win `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。本轮沿用资源索引和Capstone5.0.9静态fallback，没有完整REA provider Evidence会话，没有启动、修改或附加游戏，没有读新存档或监测网络。

新增覆盖物品Create、夹板医疗Create/Alarm/Other11/Other20、公共稳定助手、销旧建新助手、稳定父类Create和轻伤稳定更新。中/重稳定阈值与部位减益使用27的本轮局部证据；被动恢复公式使用31，避免在夹板章节重复全恢复系统。

## 2. 真实绑定和原作常数

| 对象 | ID | 父ID | data.win偏移 |
| --- | --- | --- | --- |
| `o_inv_splint` | 5178 | 5164 | 11003144 |
| `o_skill_stabil_wound` | 6405 | 6404 | 11501216 |
| `o_medical_tab_skill` | 6404 | 6394 | 11500720 |
| `o_stabil_wound` | 5994 | 5964 | 11337032 |
| `o_db_light_wound_stabil` | 5995 | 5994 | 11337384 |
| `o_db_wound_stabil` | 5996 | 5994 | 11337736 |
| `o_db_deep_wound_stabil` | 5997 | 5994 | 11338088 |

真实物品行文本 `0x146709430`，初始化槽 `0x14983c398`，含 `splint;;10;;;medicine;;cloth;Light;...35;...common;`。本篇没有以整张物品表列推断35的含义，而以执行对象写入证明：

- 库存 `o_inv_splint.Create0 @0x143d6e200` 写charge=1（`0x143d6e2a4..2ae`），调 `scr_consum_atr(4) @0x143d6e30f`，写skill=6405（`0x143d6e3c6..3d7`）。属性初始化参数4不是治疗四个部位。
- `o_skill_stabil_wound.Create0 @0x1446b2a00` 继承创建后写 **heal=35 @0x1446b2a7f..2a89**。
- 通用 `scr_injury_stabil` 第三参数默认30（`0x1408658b0..8c1`）；如果调用对象存在heal字段，再以self.heal覆盖（`0x1408659cd..5a62`）。因此此夹板实例采用35，不能用助手默认30替代真实动作参数。

## 3. 部位选择和失败门禁

打开医学动作的库存父类链与29相同。`o_skill_stabil_wound.Other11 @0x1446b3120` 读取interact_id；未选择时按GUI鼠标位置查部位对象。进入选中对象后检查disabled（`0x1446b3444..345a`）；disabled真则不设成功标记，也不进入本次稳定助手调用。

`Other20 @0x1446b3d60` 在准备阶段循环伤势等级1..3，组合 `"o_db_inj_"+keyMap+等级`，在player.buffs查询（命名构造 `0x1446b416b..4304`，列表调用 `0x1446b436e`）。没有匹配普通伤势时把对应部位disabled设为真（`0x1446b440b..443c`）。这个查询没有直接把 `_stabil` 后缀加入候选，不能说已稳定伤势必定还能再次使用夹板。

选中有效部位后，在 `0x1446b3728` 用四个undefined参数调用 `scr_injury_stabil @0x140865330`。默认值不是“什么也不做”：助手先根据调用上下文补齐宿主/交互对象/治疗值/部位键；若self有interact_id就读取它（`0x140865b4e..b7a`），若交互对象有keyMap就把它用作部位键（`0x140865c4c..ca5`）。头部UI真实keyMap为head（29给出Create证据）。

这个过程绑定的是用户选定部位，而不是随机受伤部位。UI准备与执行各有门禁；本轮没有穷尽退出界面、物品消失、交互对象刚销毁等竞态。

## 4. 即时恢复的精确局部公式

设C为调用宿主 `Body_Parts_map[部位键]` 的当前Condition，h为助手最终参数heal。

1. 在 `0x140865cf0..5d98` 读map和选定键，得到C。
2. `0x140865de4..5e22` 检查普通有限值 **C>=0且C<100**。比较助手带 `1e-5` 容差，本文的整数例子远离端点；异常类型/NaN未完整恢复。
3. 对符合条件的C，先加h（`0x140865f5f`），与原作常数100取min（`0x140865ff0` 调 `0x1451de510`），再 `ds_map_replace @0x14086603c`。

因此当前夹板实例的即时写入是 `C'=min(100,C+35)`。该写入没有除以回合数，也没有等待自然恢复tick，因此它是本次调用的即时部位Condition增量。C<0或C>=100时跳过该map写入；后续伤势实例处理仍有其他路径，不能将此局部分支概括为“整个使用失败”。

这与31按治疗量、max_hp、未满部位数量和伤势状态分配的恢复公式不同。35不是总HP治疗量，也不是每回合恢复35，更不是稳定状态默认寿命35。

## 5. 稳定伤势通过销旧建新产生

助手从等级1开始循环至3；根据部位键和等级生成普通伤势对象名，查找宿主buffs（`scr_instance_exists_in_list @0x1408664a7`）。找到实例后读取其object_index，取得对象名并加 `_stabil`（`0x140866842..6996`），把新对象索引传 `scr_inst_change_buffs @0x1408669d5`。

例如选定头部且存在 `o_db_inj_head2`，目标新类型是 `o_db_inj_head2_stabil`（ID6016，OBJT偏移11344560，父5996）。资源存在只是类型候选；实际进入这条调用才是稳定处理证据。

`scr_inst_change_buffs @0x1417aef00` 的次序也已局部解码：

1. 缓存旧状态target、owner（`0x1417af065..f0a6`）。
2. 以无参数形式调用实例销毁助手 `0x1451f70d0 @0x1417af0be`，即处理当前旧状态；普通路径派发Destroy/CleanUp，29给出完整运行时验证。
3. 在 `0x1417af1f8` 调 `scr_effect_create`，用新类型和缓存宿主/owner创建替代状态。

这是 **先销旧、后创建新状态**，不能仅凭函数名称为原地instance_change。没有发现新对象创建失败时自动恢复旧对象的补偿；不把它称为原子无失败事务。

`o_stabil_wound.Create0 @0x144406f70` 写stability=true（`0x144407029`）。普通伤势基础对象写false的证据见27。稳定状态仍有同等级属性助手，不能从stable名称推断“所有减益减半”或“减益清零”。

## 6. 清理以部位Condition为条件

本轮直接核对 `o_db_light_wound_stabil.Other10 @0x144407770` 读取target、Body_Part和宿主Body_Parts_map对应值，按90门槛处理；达到门槛的销毁在 `0x14440796b`。中等级稳定父类在 `0x144408112` 比较50，超过50后将对象名等级2替换为1并调用销旧建新助手 `0x14440832c`。重等级的25门槛及降为2见27。

这些更新是状态事件的消费者，不是即时map写入必然同步完成全部降级的证明。已经稳定的状态也会随着Condition恢复降级/移除；普通状态和稳定状态的具体属性、每个事件何时被公共更新派发，请结合27/31。没有把轻/中/重门槛一律写成“到90全部伤势都立即消失”。

已查稳定父类Create/轻伤Other10没有证明固定持续回合数。状态寿命取决于所查Condition门槛和事件调度；离图重建、读档、宿主死亡或重新受伤取消稳定的全部路径尚未穷尽。

## 7. 一次物品用量与提交次序

库存夹板默认charge=1。效果提交的Other11先调用稳定助手，然后派发自己的user0（`0x1446b3734..3745`）。医疗父类Other10排程alarm[0]=1，夹板Alarm0 `@0x1446b2b30` 播音/说话后进入继承事件。祖先 `o_invisible_skill.Alarm0` 含charge−1和耗尽 `scr_item_destroy`；详情与分支边界在29。

对“实际进入公共charge分支、未被覆盖的新夹板”可演算 **1→0→库存物品销毁**。但本轮未完全闭合运行时duration/is_change_duration、parent表示及背包重查所有条件，不把这个条件结论推广到取消/无有效物品/所有库存实例。稳定效果与物品扣除并非同一个指令点；具体动作占用多少逻辑回合未运行验证。

## 8. 构造演算：恢复不等于当场无伤势

以下C、buff集合和消费分支是构造输入，非实际存档/运行值；h=35、上限100、普通/稳定对象类型来自本机制品。

**例A：中等头部伤势。** 假定选定头部，C=40，player.buffs存在 `o_db_inj_head2`，disabled=false，调用上下文完整。提交写 `min(100,40+35)=75`。查到head2后销毁旧状态，创建head2_stabil。随后该稳定状态的更新事件读取C=75，满足中等级大于50的降级门槛，可产生head1_stabil；后者只有在其相应事件达到轻伤清理条件时才移除。C75尚未达到90，不能因为用了夹板便说“头部伤势已经全部治愈”。若公共charge分支成立，库存夹板1→0并销毁。

**例B：上限裁剪。** 假定同样有效条件而C=80，局部写 `min(100,80+35)=100`，实际增加20，不是增加35后允许115。后续状态更新可按相应门槛清理或分阶段降级；精确发生在哪一个逻辑更新周期未采集。本文没有写HP同步增加20。

**例C：无普通伤势。** 当前部位不存在准备查询的普通inj1/2/3，则UI会设置disabled，Other11检查它后跳过本次稳定提交。仅有已经稳定后缀状态的场景不保证仍通过普通名查询，不能据此宣称可以无限重复夹板叠加。

## 9. 自研规格和证据表

独立设计可把三份状态明确分开：部位健康数值、伤势等级、是否已稳定。一次夹板可以定义即时增量、状态转换和后续恢复修正，而不让“稳定”名词隐含所有行为。物品提交应复查部位和库存，记录失败原因；替换状态需要明确失败补偿。数值35/90/50/25是原作局部证据，不是我们产品的平衡建议，也不交付恢复代码供生产复用。

| 已确认问题 | VA或资源位置 | 覆盖边界 |
| --- | --- | --- |
| 库存绑定、默认charge | `0x143d6e2a4..2ae`、`0x143d6e3cd..3d7` | Create默认值 |
| 真实治疗参数35 | `0x1446b2a7f..2a89` | 夹板医疗对象 |
| 选择部位、执行门禁 | `0x1446b3444..345a`、`0x1446b3728` | Other11局部提交 |
| 普通inj候选决定disabled | `0x1446b436e`、`0x1446b440b..443c` | Other20准备 |
| Condition即时增量 | `0x140865d98/5f5f/5ff0/6603c` | 正常有限值，C处于有效区间 |
| 稳定类型选择 | `0x140866842..6996`、`0x1408669d5` | 找到普通伤势的分支 |
| 旧状态销毁/新状态创建 | `0x1417af0be`、`0x1417af1f8` | 次序确认，失败回滚未知 |
| stability真值 | `0x144407029` | 稳定父Create |
| 轻伤清理 | `0x144407937/796b` | Condition90门槛事件 |
| 公共charge扣除 | `0x14469a782..a78e`、`0x14469a8a4` | 条件消费路径 |

本机可选来源：[夹板Create](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_inv_splint_Create_0.txt)、[heal35](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_skill_stabil_wound_Create_0.txt)、[实际提交](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_skill_stabil_wound_Other_11.txt)、[准备门禁](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_skill_stabil_wound_Other_20.txt)、[稳定助手](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Script_scr_injury_stabil.txt)、[销旧建新](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Script_scr_inst_change_buffs.txt)、[轻伤稳定事件](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_db_light_wound_stabil_Other_10.txt)、[资源索引](../../../_reference/stoneshard-study/eighth-treatment-resources.json)。本机证据是可选调查产物，缺失不改变本文列明的地址和边界。

已回答：真实夹板绑定、部位门禁、35即时Condition写入、普通伤势到stable的销旧建新、轻伤清理门槛和条件消费例子。部分回答：完整提交/扣除、稳定持续和降级周期。未回答：精确回合成本、所有取消补偿、特殊目标类型、库存属性覆盖、stable再受伤和存档完整生命周期。验证为静态核对与构造演算；未运行游戏。风险是事件相位/资源消耗尚有缺口，不能把局部状态变化解释成所有场景下一次使用即可完全治愈。
