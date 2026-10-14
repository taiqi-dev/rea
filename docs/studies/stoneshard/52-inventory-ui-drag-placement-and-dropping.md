# 52. 背包交互：选中拖拽、落点高亮、放置与点击空白丢弃

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [堆叠和拆分](53-item-stacking-split-and-transfer.md) · [自动整理](54-inventory-autosort-and-grid-packing.md)

**已找到“手持物品点击空白后丢弃”的实际分支，但空白必须区分背包空槽和没有完整落点的界面区域。空槽可进入放置；没有完整落点时，还要检查点击、Alarm、来源菜单和GUI重叠，才派发丢弃事件。** 不是只判断鼠标下没有物品就直接删除物品。

本篇针对00固定的Stoneshard Windows x64 YYC制品。第十二轮完整摘要与第十一轮一致，使用本地PE/OBJT解析与Capstone 5.0.7选定入口解码；REA工具/提供者不可用的阻塞沿用，不伪造Evidence。未启动、附加、修改游戏或读取新存档。伪代码重新组织行为，不是原始源码；算例均明确给定输入。

## 1. UI、格子与物品实例的分层

OBJT实际父链：

| 对象 | ID / 记录偏移 | 父链与职责边界 |
| --- | --- | --- |
| o_inventory | 4748 / 10843144 | o_menuParent→o_guiContainer→c_GUI；角色背包菜单 |
| o_inv_cell | 4767 / 10851488 | o_guiContainer→c_GUI；格子是独立GUI对象 |
| o_inv_slot | 4769 / 10852480 | o_inv_slot_parent→o_guiInteractive→c_GUI；物品槽实例 |
| o_inv_select_highlight | 2590 / 10154344 | 独立对象；选中落点高亮 |
| o_trade_inventory | 4749 / 10843856 | 本篇掉落分支明确排除的来源类型之一 |
| o_stash_inventory_right | 1970 / 9960120 | 同上；不是所有仓库菜单的泛称 |
| o_gui_no_click | 6850 / 11661128 | GUI碰撞列表中有特殊排除，不阻断本段掉落 |

同一物品有数据data、GUI父容器、逻辑占格和手持状态。可见图片坐标不是背包行列；世界掉落实例又是另一对象。对应关系来自资源父链和实际调用，不由英文名推定。

主要入口：物品Mouse4 `0x143c2caa0`，End Step/Step2 `0x143c289d0`，交互User11/Other21 `0x143c4ec40`，丢弃User15/Other25 `0x143c4bac0`；公共选中 `scr_item_select@0x1404b8890`、放置后处理 `scr_item_placed@0x14046f4d0`、绑定格子 `scr_item_attach_to_cell@0x141c85e80`、占格更新 `scr_item_cells_update@0x1420d4140`。

## 2. 点击选择产生哪些状态

Mouse4在动作/GUI许可、锁物品及对象条件通过后调用 `scr_item_select`（`0x143c2dfa1`）。同一事件还有交易、装备替换、堆叠和直接转移分支，不能把每次点物品都当作进入拖拽。

在公共助手的选中请求为真、当前物品尚未select的正常路径：

1. 设置物品 `select=true`（字段选择 `0x1404b8b25`，写回 `0x1404b8b56`）。
2. 把 `select_cell_id` 写为数值−4（`0x1404b8b88–0x1404b8bbd`）。
3. 将global.inv_select写为布尔真（`0x1404b8be5`）。global.inv_select是标量状态，不是持有物品ID的列表。
4. 处理can_pick/owner相关分支，将本实例加入Escape处理登记（`0x1404b8e37`），改变光标显示，并创建/更新2590高亮实例。
5. 调 `scr_item_cells_update(id,false)`（`0x1404b9399`），更新逻辑占格；选中不是只给图片一个跟随鼠标的标志。

取消选择的已查路径则设置select=false、select_cell_id=−4、global.inv_select=false，移除Escape登记（`0x1404b95a8`），恢复光标和清理高亮。是否任何对象都能在无效owner情况下完成这一流程，未覆盖全部异常路径。

这里只确认登记与清理，不把Escape登记本身宣称为全部键盘取消、菜单关闭、存档恢复和多实例并发的完整协议。

## 3. 拖动期间先更新预览，再处理提交

End Step首先读select；假时跳过本段。真时派User11（`0x143c28cc0`），进入本对象Other21，之后再检查slotDestroyed、Alarm和点击。

Other21调用 `scr_item_select_cell_find_nearest`（`0x143c4fafa`），写/检查select_cell_id，并根据cells_x/cells_y枚举覆盖格。实际调用包括：

| 检查 | 地址 | 作用 |
| --- | --- | --- |
| 查格所属菜单与容器 | `0x143c4fdd1 / 0x143c4fe55` | 不把格子与菜单混同 |
| 按坐标取格 | `0x143c5035d` | 展开物品矩形覆盖 |
| 查格上的物品ID | `0x143c5075f` | 区分空槽和已有物品 |
| 检查能否替换 | `0x143c50876` | 与占格合法性分开 |
| 检查格类型与物品可放入容器 | `0x143c5095a / 0x143c509d2` | 容器类别限制 |
| 背包内部是否为空 | `0x143c50a80` | 嵌套容器的特殊门禁 |

还有堆叠、交换、装备、钱袋/弹药、交易和诅咒等分支。这里保存了入口与职责，没有把47055字节Other21的所有特殊物品规则称为已恢复。

最近格助手会检查容器可见状态/可见区域，以物品尺寸、GUI坐标和格子几何构造位置，再经过math_round与clamp。两个取整调用 `0x1404d1d7f / 0x1404d2002`，并有按坐标查格。UI格距来自该助手使用的几何输入，**不能把战斗地图的26像素格距直接用于背包**。全部缩放、裁剪、两侧容器和边缘偏移参数尚未恢复成一条可无条件复用的坐标公式。

高亮Step2根据owner.select和select_cell_id跟随候选格，视觉提示和最终放置许可是两个层次；出现高亮不等于覆盖格全部可以提交。

## 4. 放置提交怎样接到逻辑占格

End Step在select为真、slot未销毁、`alarm[1]==-1`且本次 `mouse_check_button_pressed(1)` 为真时继续。Alarm门禁 `0x143c28d64 / 0x143c28d89`，鼠标查询 `0x143c28e15`；不是mouse_button_released。按钮1常量的本机RValue位于 `0x14959f558`，值1。

select_cell_id不是−4时取得格所属菜单，并进入交易/普通放置/交换等路径。实际普通绑定调用包括 `0x143c29911`、`0x143c2a2e2`。公共attach助手连接：

```text
把物品加入目标GUI容器子节点
→ 重建目标容器
→ 更新容器布局
→ 按逻辑格刷新物品占用
```

对应调用 `0x141c8614e / 0x141c86202 / 0x141c86275 / 0x141c862f9`。占格更新读行、列与cells_x/cells_y，按坐标取格，再读写itemID；它不是只移动图片。

调用者还会取消select并调用item_placed，处理持有、装备灯具/面罩等后处理，部分路径请求allturn或属性重算。**不是所有背包拖拽都无条件花一个战斗回合**：不同来源、装备状态和分支的请求不一样，本篇未统一其时间成本。

## 5. 点击“空白”丢弃的真实门禁

当select_cell_id等于−4时，比较分支 `0x143c28e9c` 转到 `0x143c2aac4`。其他某些分支也能到达该后段，所以不能把整个后段定义为唯一的UI外点击。

已确认的关键条件：

1. `select_cells_count == cells` 时直接跳过后续掉落（比较 `0x143c2aafe / 0x143c2ab05`）。完整覆盖计数和物品格数不同才继续。
2. owner属于4749交易菜单或1970右侧仓库菜单时返回（`instance_is_array@0x143c2ac60`，真分支 `0x143c2ac6f`）。这次数组来自实测常量4749、1970；不推广为所有交易/所有仓库的统一行为。
3. 创建临时列表，以物品当前GUI x/y，对4018/c_GUI做 `instance_place_list(...,false)`（`0x143c2ae5f`）。是物品在当前GUI位置的碰撞查询，不只是一个鼠标点是否空的查询。
4. 默认allowDrop=true。若找到任何 `object_index !=6850/o_gui_no_click` 的GUI对象，则置false（类型比较 `0x143c2b068`；等于6850继续循环，不相等转禁止段）。
5. 销毁临时列表（`0x143c2b16c`），allowDrop仍真才派User15（`0x143c2b1af`），进入Other25。

```text
选中物品的End Step:
    先更新候选落点和完整覆盖计数
    若slot已销毁、Alarm未允许或没有本次点击：不进入本段提交
    若达到对应放置/交易路径：按该路径处理
    到达掉落后段时:
        完整覆盖计数等于物品格数 → 不由此段掉落
        属于两种指定来源菜单 → 不由此段掉落
        有会阻断的GUI重叠 → 不由此段掉落
        否则派发物品的丢弃事件
```

因此用户观察的操作有实际代码支持，但条件描述应是“手持物品在无完整落点、来源允许且GUI不阻挡的点击中申请掉落”。完整空槽正常是放置目标；放置无效或被GUI遮挡也可能继续保持选中，不能统一叫空白就掉。

## 6. 丢弃不是直接删掉数据：先生成世界物品

真实Other25有诅咒/装备和伤势阻挡等门禁。在普通允许路径，读5376/o_player的x/y准备掉落坐标（`0x143c4c0f9 / 0x143c4c123`），另有 `isNormalDropCoordinates` 与drop_x/drop_y覆写；不能说物品一定掉在鼠标点击的世界坐标。

主链包括：

1. 记录playerDropItems行动日志。
2. `scr_item_select(false)`解除手持状态（`0x143c4c7d7`）。
3. 读取drop_script，通过script_execute派发（API选择 `0x143c4ca7e`）。物品Create把默认drop_script绑定到 `scr_loot_drop` 的登记ID（`0x143c16707 / 0x143c16719`），子类可以另行覆写。
4. 在产生的掉落实例上下文处理data地图，使用 `ds_map_clone`（`0x143c4cd2b`），并复制材料、表现索引、投掷/价格等选定字段；还处理赃物属性。
5. 请求 `scr_item_destroy`销毁旧背包物品（`0x143c4d347`），更新相关item/loot引用。
6. forced_drop参与是否请求allturn的后段（字段 `0x143c4d4d0`、调用 `0x143c4d58b`）。申请时间成本与真正全局时间推进见14，不能只凭这个字段名决定所有掉落时间。

`scr_loot_drop@0x141702050`还调用findFreeTile（`0x1417026e5`），再创建世界实例及位置/生成标记。坐标准备值不保证原点正好是最终落点。这里已恢复普通创建、数据转移和旧实例退出；世界实例创建失败、所有特种drop_script、退款和异常回滚未全面核准，不宣称它是原子事务。

## 7. 三个具体交互例子

共同构造：普通背包中一个2×1物品P，select=true、slotDestroyed=false、alarm[1]=−1，本次按钮1按下。P允许被移除，没有阻断的装备诅咒或伤势；这些是输入前提，不是所有实际物品默认属性。

| 场景 | 明确输入 | 已恢复的结果 |
| --- | --- | --- |
| A 放入空槽 | 合法select_cell_id，两个覆盖格允许放入，无交易/交换特例 | 实际普通绑定路径加入容器并更新两格itemID，解除选择及放置后处理；不因槽上没有物品而掉落 |
| B 点击UI外空白 | select_cell_id=−4，select_cells_count=0、cells=2，owner不是4749/1970，GUI碰撞列表空 | 到掉落后段，allowDrop真，派Other25；普通链解除手持，生成世界物品、复制data，再退出旧背包实例 |
| C 点击阻挡GUI | 与B相同，但碰撞列表有一个非6850的GUI实例 | allowDrop改为false；此后段不派掉落事件，不能据此声称物品已删除 |

若B的GUI碰撞列表只有6850实例，该过滤仍保留allowDrop真；这是明确类型例外，不是所有“不可点击UI”都默认不阻挡。

另一个差别：把B的owner换成4749或1970，来源门禁先返回，不会继续走本段GUI检查/掉落；它并不保证菜单外的所有其他脚本也永远不能丢弃这些来源物品。

## 8. 自研可以借鉴哪些契约

以下是独立设计建议：把手持、候选覆盖、可放置、交换、合并和掉落作为明确状态/动作；保留来源容器与取消落点，分清空槽和容器外区域。UI高亮先生成预览，点击提交时再次验证。逻辑itemID和GUI节点同时更新，不能只改变图标位置。

如果我们不希望误丢，可以要求明确的掉落区域或二次动作；是否这么设计由自己的产品决定，不能写成原作已有确认弹窗。堆叠部分提交、交换后手持另一物品、菜单关闭/失焦取消，以及世界掉落创建失败都应有可诊断结果和独立测试。

已回答：真实选择状态与高亮、预览到点击提交桥、空白掉落门禁、两个菜单排除、GUI重叠例外、普通掉落数据转移/清理。部分回答：最近格几何、交换/装备/交易、全部特殊物品与时间成本。未回答：运行中精确事件先后、所有分辨率/缩放、输入竞态和失败回滚。

可选本机证据：[本轮UI入口](../../../_reference/stoneshard-study/twelfth-ui-native.json)、[资源绑定](../../../_reference/stoneshard-study/twelfth-ui-object-bindings.json)、[按钮与来源常量](../../../_reference/stoneshard-study/twelfth-ui-selected-constants.json)、[End Step点击/掉落](../../../_reference/stoneshard-study/twelfth-ui-disassembly/gml_Object_o_inv_slot_Step_2.txt)、[拖动预览与特殊提交](../../../_reference/stoneshard-study/twelfth-ui-disassembly/gml_Object_o_inv_slot_Other_21.txt)、[实际掉落](../../../_reference/stoneshard-study/twelfth-ui-disassembly/gml_Object_o_inv_slot_Other_25.txt)、[公共选择](../../../_reference/stoneshard-study/twelfth-ui-disassembly/gml_Script_scr_item_select.txt)。这些是可再生成的本地静态记录，不随仓库分发。

未做：未运行游戏、拖动实际物品或改存档；当前没有可用的目标运行观察工具，单纯启动游戏不能核准UI时序。本篇验证依靠资源、指令和条件例子。风险：把“空槽”和“无完整落点”混同、把预览当提交、把世界实例当同一GUI实例，或漏掉子类drop脚本。正文已保留这些边界。
