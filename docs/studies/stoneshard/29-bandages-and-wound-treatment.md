# 29 绷带：部位选择、流血清理与物品提交

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [28 流血](28-bleeding-and-blood-loss.md) · [30 夹板](30-splints-and-injury-stabilization.md)

本篇已确认一条真实玩家绷带链：库存对象 `o_inv_bandage` 绑定医疗动作 `o_skill_bleed_cure`，动作读取选定身体部位的 `keyMap`，从玩家 buffs 中查找该部位的流血实例，然后请求销毁。销毁助手在普通实例路径派发 Destroy 和 CleanUp。**这个效果提交是移除流血状态，不是在本入口把 HP 或部位 Condition 补满**。特定状态降低流血伤害和绷带清理状态是不同机制，见28。

物品创建默认 charge=2，公共提交父类含每次扣1与耗尽销毁分支。但整个医疗选择状态、运行时物品属性和父类扣除门禁尚未全部闭合，所以区分“真实默认容量”“真实扣除代码”与“所有使用场景都必定扣一份”的保证。

## 1. 输入身份与证据等级

调查同一 `E:\Steam\steamapps\common\Stoneshard` 制品，开始时间 2026-10-12 20:41:27 PDT。根调查复核 EXE SHA256 为 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win 为 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。方法仍为资源元数据和局部机器指令；REA provider 缺失沿用既有阻塞，新增记录不冒充 REA Evidence。

没有启动、附加或修改游戏，没有读取新存档或监测网络。查到的地址是静态 VA；字段名按 RIP 引用前8字节名称指针验证。本机可选证据是 [原生记录](../../../_reference/stoneshard-study/eighth-treatment-native.json) 和 [物品/对象资源](../../../_reference/stoneshard-study/eighth-treatment-resources.json)。正式文档保留关键输入、状态和位置，可独立阅读。

## 2. 物品到医疗对象的绑定

| 对象 | ID | 父ID | data.win记录偏移 |
| --- | --- | --- | --- |
| `o_inv_bandage` | 5182 | 5164 | 11004552 |
| `o_inv_consum_medicine_tab` | 5164 | 4801 | 10998144 |
| `o_skill_bleed_cure` | 6406 | 6404 | 11501712 |
| `o_medical_tab_skill` | 6404 | 6394 | 11500720 |
| `o_character_skeleton_progressbar` | 5887 | 2679 | 11289432 |

物品配置文本 VA `0x146709070`，字符串槽 `0x14983c338`，真实行以 `bandage;;10;;;medicine;;cloth;Light;;;30;...5;...common;` 开头。其30/5所在列未在本篇完整核对，因此不拿它们定义流血清理量、持续时间或行动成本。

更强的行为证据是 `o_inv_bandage.Create0 @0x143d6fb30`：

- `charge=2 @0x143d6fbd3..fbe4`；接着把当前charge复制到max_charge（字段读取/写入 `0x143d6fbee..fc1d`）。
- 调 `scr_consum_atr(1) @0x143d6fcff`；参数1是属性初始化调用输入，不是本次扣除数量。
- `can_merge=true @0x143d6fd1a..fd3b`。
- `skill=6406 @0x143d6fd7f..fd90`，对应 `o_skill_bleed_cure`。

初始化和执行间仍可能由读档、合并、属性设置覆盖charge。不能把新建物品默认2断言为所有背包绷带都一定有2次可用量。

## 3. 打开医疗选择与确定部位

库存医学父类 `Other24 @0x143d61f90` 先继承派发，然后调用 `scr_stop_player @0x143d6208a`。它的父类 `o_inv_consum_active.Other24 @0x143cc2020` 读取skill，符合所查 GUI 条件时调用 `scr_guiCreateInteractive @0x143cc2387`，并把新对象的parent设为调用物品ID（`0x143cc23e1..242a`）。另一路调用 `scr_use_consum_skill @0x143cc255b`。只恢复相关字段与分支，没有恢复整套鼠标、键盘和背包窗口系统。

医疗动作的提交事件 `o_skill_bleed_cure.Other11 @0x1446b5880` 先读interact_id。若为哨兵-4，则以guiMouseX/guiMouseY查询 ID5887 的部位界面对象（`instance_position @0x1446b5b19`），保存查询结果。若已经指定interact_id，则沿用它。

进入该部位对象后：disabled为真跳过本次处理（`0x1446b5c17..5c2d`）。读取其keyMap，拼接 `"o_db_bleed_"+keyMap`（前缀槽 `0x1498f2e18`，构造 `0x1446b5caf..5d83`）。从玩家5376的buffs调用 `scr_instance_exists_in_list @0x1446b5e64`。

一个有直接来源的部位是头部：`o_character_skeleton_progressbar_head.Create0 @0x14434a920` 写keyMap=`"head" @0x14434a9d0..9e9`。因此选头部会查询 `o_db_bleed_head`，并不是随机选择一个身体部位，也不是把所有流血实例一起清除。

## 4. 可用性门禁和成功写入

`o_skill_bleed_cure.Other20 @0x1446b6f90` 同样组合部位流血名并在player.buffs里查询（`0x1446b7322`）。查询结果为假时写 disabled=true（`0x1446b7331..736e`）。这是准备阶段对“该部位是否有流血”的门禁。

执行Other11仍检查部位disabled，避免仅凭上次UI可用性就当作当前有效。查到的流血实例被作为一个显式参数送到 `0x1451f70d0 @0x1446b5e9b`。本轮继续解码这个运行时助手，确认普通实例路径：

1. `0x1451f70d0..7140` 把参数0转换为实例/对象selector；未指定第二布尔参数时默认true（`0x1451f7101..710d`）。
2. 调 `0x1451f0a90 @0x1451f7127`，按selector遍历对象。普通有效对象在 `0x1451f0b99` 进入 `0x1452fc370`。
3. 后者先检查销毁重入标志，然后 `0x145300d10 @0x1452fc3b6` 派发类型1、编号0，即Destroy；再在 `0x1452fc3c8` 派发类型12、编号0，即CleanUp；最后设置销毁标志（`0x1452fc3cd`）。

相应诊断字符串 `0x147c68c70` 明确提到 managed object 的 destroy 限制，结合事件参数和状态位交叉确认该助手为实例销毁。特殊 managed/rollback 分支含延期标记，本篇不将普通即时事件次序推广到所有对象。

公共状态Destroy对target.buffs的解除和属性缓存失效见28以及 [11 状态系统](11-buffs-and-effects.md)。绷带不需要等待流血duration自然到期；已经被移除的实例不再负责之后的正常tick。不过没有运行证据确定当前事件周期内是否存在已排队的最后一次伤害，也不能说治疗会返还之前损失的HP。

## 5. 确认效果与表现/物品扣除分离

执行清理后，动作处理部位GUI事件，设置本地成功标记，再在player位置创建 `o_gui_animation`（5634，`0x1446b62b5`），给动画charges=1（`0x1446b6300..6308`）。这份charges不是绷带物品的charge，两者名称相近但对象所有者不同。

动作随后派发自身user0（`0x1446b6393`）。医疗父类 `o_medical_tab_skill.Other10 @0x1446b28e0` 写alarm[0]=1（`0x1446b2934..294f`），再派发user11（`0x1446b2967`），并非直接在此处扣背包数量。

绷带Alarm0 `@0x1446b5230` 播音/说话后在 `0x1446b54d5` 调继承事件。其祖先 `o_invisible_skill.Alarm0 @0x144699690` 有真实消耗链：检查delete_parent、parent_is_instance，选parent或查背包；根据duration/is_change_duration等分支处理持续物品；charge路径在 `0x14469a782..a78e` 对有限double执行charge−1，随后判断剩余charge是否小于1（`0x14469a7e9`），满足时 `scr_item_destroy @0x14469a8a4`。其他分支也有销毁调用。

因此新物品默认charge2与公共扣1分支能构成 **条件明确的“2→1→0→物品销毁”**。尚未逐个闭合医疗实例运行时duration/parent类型及分支选择，不能保证取消、找不到物品、状态刚被其他操作删除等情况一定遵循同样的成功消耗。效果清理发生在Other11，而消耗是随后排程Alarm的一条祖先路径；未见把两者组成可回滚事务的证据。

`scr_allturn @0x14469aa02` 出现在祖先Alarm尾段，说明提交涉及公共行动推进，但调用存在不证明本动作精确消耗1个逻辑回合。详细逻辑时钟仍按14/17解释，本轮没有运行验证。

## 6. 具体构造例子

构造玩家buffs含实例B=`o_db_bleed_head`、另一实例L=`o_db_bleed_lhand`；头部UI的keyMap采用真实值head，disabled=false，其他提交条件成立。假设库存新绷带未被任何初始化覆盖，charge=2。

1. 选头部，动作形成 `o_db_bleed_head` 并查buffs，返回B。
2. 显式销毁参数是B，普通实例执行Destroy/CleanUp。L不是这次查询返回对象，本局部链没有同时销毁它的调用。
3. 创建charge为1的GUI动画；排程医疗Alarm。
4. **若随后进入已确认公共charge分支**，库存绷带charge由2到1，物品保留；再次成功使用并走同一分支时到0，进入销毁。

这不是实际存档或运行观测。这里刻意分开目标实例、动画charges和库存charge。若玩家没有头部流血，准备查询返回假会使头部disabled；执行事件检查disabled后跳过目标处理，不应解释为“绷带把正常头部也恢复健康”。如果准备与提交间状态变化，列表查询助手返回无实例时运行时销毁selector的准确处理仍需专门验证。

## 7. 自研可借鉴与未知

可借鉴的是按部位定位具体负面状态、用同一部位键构造UI与状态查询、让状态所有者负责清理、区分效果提交和物品数量。我们自己的实现可以把“确认目标仍有效→应用效果→扣可用次数→推进动作”定义为一个明确提交契约，给失败原因和取消补偿；这是自研建议，原作没有在本轮证实原子提交。

已回答：真实物品绑定、头部示例、部位门禁、流血实例销毁、默认容量、公共扣除代码与事件排程。部分回答：医疗输入、最终数量、状态清理。未回答：全UI派发、库存运行时所有覆盖、取消/并发状态变化、存档持久化、精确回合成本、是否有最后一次已排队tick。本入口没有证实HP/Condition恢复，不能称完整治疗。

可选证据：[绷带Create](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_inv_bandage_Create_0.txt)、[绷带提交](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_skill_bleed_cure_Other_11.txt)、[可用性](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_skill_bleed_cure_Other_20.txt)、[医疗排程](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_medical_tab_skill_Other_10.txt)、[公共消耗](../../../_reference/stoneshard-study/eighth-treatment-disassembly/gml_Object_o_invisible_skill_Alarm_0.txt)、[销毁入口](../../../_reference/stoneshard-study/eighth-treatment-disassembly/runtime_1451f70d0_context.txt)、[销毁遍历](../../../_reference/stoneshard-study/eighth-treatment-disassembly/runtime_1451f0a90_context.txt)、[Destroy/CleanUp派发](../../../_reference/stoneshard-study/eighth-treatment-disassembly/runtime_1452fc370_context.txt)。运行时context证据均裁到首个ret，不引用相邻函数。

验证为静态输入/读写/控制流核对和条件构造演算；未做运行测试。风险是局部提交与公共消费分支尚未全部贯通，不保证所有边界下成本和状态完全一致。交付为系统说明，不包含原作可发行代码或资产。
