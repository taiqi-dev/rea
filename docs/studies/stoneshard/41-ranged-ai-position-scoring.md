# 41. 远程 AI 选位：格门禁、危险标记与候选消费

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [弩手动作选择](33-arbalester-skill-scoring-and-action-choice.md) · [怪物预告攻击](13-telegraphed-attacks.md) · [视觉听觉](03-enemy-perception.md)

后续真实候选比较、因子初始化、九格数值、周边特殊实体单结果与最终返回，见 [48 选位竞争与无路处理](48-ranged-position-selection-and-path-failure.md)。本篇保留格门禁阶段；不能再把所有后续选择都概括为尚未恢复。

**本轮已建立选位入口的空间检查、危险标记转换、候选门禁和主动作选择器消费；完整“哪一个格最终最好”的评分和所有无路回退仍只恢复了部分。** 可以具体解释一个陷阱相关负值怎样使候选跳过一段普通处理，也能确认射击范围、FOV、AOE、占格和临时寻路数据参与这条链；不能据此编出“距离×权重＋安全分”的完整效用公式。

目标沿用 00 固定的 Stoneshard GameMaker YYC x64 EXE/data.win，本轮完整摘要一致。REA 工具/提供者不可用，复用已有本地索引，以 Capstone 5.0.7 解码14个选定入口，再用5.0.9补注释和核对小助手。证据文件分别标明生成范围；它们不是 REA Evidence。没有运行、附加或修改游戏，没有读取新存档。

## 1. 选位不是技能评分回调本身

33 已闭合当前主选择器 `o_enemy.Other12@0x143644cd0`。它调用 `scr_enemy_find_target_tile_new(false)`（`0x1436450af`）取得工作值 targetTile，随后把它传给消耗品评分 `scr_enemy_consum_get_priority(item,targetTile)`（`0x1436457a3`）并参与后续动作路径。

因此空间查询确实进入当前动作选择，而不是仅仅一个未使用的旧脚本。与此同时，Taking Aim/Headshot 基础分、技能使用许可和最后平分规则仍属于 33；“存在可射击格”和“某技能赢得当前动作”是两层判断。

```text
当前敌人回合入口 → 当前 FSM → Other12 主选择器
    targetTile = 新版目标格查询(false)
    普通攻击建立基线
    消耗品评分消费 targetTile
    技能候选另做评分、许可、状态保存/恢复
    根据胜出候选进入相应执行路径
```

此图是已见局部调用关系，不保证每个状态每回合都到达同一分支。

## 2. 空间流水线的真实入口

| 入口 | VA | 已确认职责与边界 |
| --- | --- | --- |
| `scr_enemy_find_target_tile_new` | `0x14063cb30` | 当前目标格查询，选定首段69526字节；包含多种空间路径 |
| `scr_enemy_range_tile_can_search` | `0x1408c52f0` | 判断是否进入远程位置搜索，读取射击、技能可用、目标、距离、VSN和视线 |
| `scr_enemy_range_tile_find` | `0x1401bdd80` | 远程格查询，调用射线碰撞与path_to_point；全部返回选择未闭合 |
| `scr_enemy_can_attack_from_FOV` | `0x142028df0` | 查询攻击空间关系，使用格数据和距离；名字不能替代完整LOS规则 |
| `scr_enemy_tile_priority` | `0x14012b600` | 按网格/标记实例和单位条件返回类型/代价值 |
| `scr_enemy_next_tile_mark_get` | `0x141ee5950` | 将上述值经单位路径类型验证，转换为负值条件布尔 |
| `scr_grid_next_validate` | `0x140a7c6a0` | 读取grid/newgrid，经cell_validate等检查候选门禁 |
| `scr_enemy_AOE_escape_scan` | `0x14065b850` | 当前查询调用的AOE逃离扫描，含距离与投射物障碍检查；完整最佳格未知 |
| `scr_aoe_escape_mark_check` | `0x141c3ee50` | AOE相关格标记检查，也使用格值/路径类型验证 |
| `astar_grid_path` | `0x1403f7470` | 将参数与缓冲交给DLL寻路，处理错误入口；DLL完整算法未恢复 |

新版查询中有直接调用：技能范围 `0x14063f367`，FOV `0x14063fcc3`，AOE标记检查 `0x1406406b4 / 0x140640b02`，AOE扫描 `0x1406419ba` 等，远程搜索门禁 `0x1406428e5`，远程格查询 `0x140642bea`。它们属于不同条件路径，不能排列成每次查询都必走一遍的固定流程。

远程搜索门禁内部见 `is_shoot`、技能可用查询 `0x1408c57e8`、`is_player`、VSN、`scr_tile_distance_math@0x1408c599f` 和 `scr_enemy_vision_check@0x1408c5ac2`。本轮没有把全部默认参数、早退和“搜索倍率”生产者合成完整布尔式。视线是实际调用证据，但不能声称任意分支都要求同一种墙角遮挡检查。

## 3. 格的 priority 值不能当作整个 AI 的效用分

格助手读取 `markgrid`（`0x14012be87`）和 `newgrid`（`0x14012bf69`），查询标记实例（`0x14012c559`）。它还读取单位/标记的对象身份、阵营、子阵营、飞行/不死状态、`tile_grid_weight`、陷阱列表和保持距离能力。

存在输出负 `tile_grid_weight` 的普通数值分支：读取 `0x14012ca36`，数值符号翻转 `0x14012ca7d` 后写输出；另外有返回0与固定−100的分支。不是每个标记都直接取负权值，也不是最终空间选择全部由这个值排序。

例如明确到达该取负分支，标记权值为7，则局部输出−7。7是构造输入；这只能说明该分支怎样编码值，不能推定某个真实火焰/盟友格默认权值就是7。后续单位路径类型验证还可能替换这个值。

格坐标与像素坐标也分开处理，助手有参数决定是否需要坐标转换。已见像素到格的26除数，不据此推定任意传入位置都应再除26。未恢复所有格类型常量的业务身份时，保留类型值与分支，不把它们猜成“墙、友军、火焰”完整表。

## 4. 一个具体陷阱相关分支：保持距离产生−100

已到达陷阱相关处理段后，查询单位的 `trap_found_list`（`0x14012cf5e`），用标记实例做 `ds_list_find_index`（`0x14012cfae`），结果存为局部值；再读取 faction_key，形成同阵营比较。随后对列表查询结果直接做运行时真值转换（`0x14012d042`）。

这里没有在这处把索引改为 `index>=0`。按已核 GameMaker 数值真值规则，0与−1均不为真，2为真。**不能把这个局部条件翻译成常见集合API的“找得到即真”。** 本轮不把这种差别宣称为实战bug，因为全部上游列表内容和实际触发未运行验证。

若这个查询真值为真，读取标记 `is_disarm`（`0x14012d04b`）；未解除的已见分支进入保持距离检查。若单位 `is_keep_distance` 为真（`0x14012d109–0x14012d11f`），输出−100（`0x14012d1f8–0x14012d202`）。其他路径还可由阵营/canDisarm条件返回0或−100，完整门禁不能压缩为“所有敌人避开所有陷阱”。

```text
已进入本助手的选定陷阱处理段:
    index = ds_list_find_index(unit.trap_found_list, markInstance)
    如果该index的运行时真值为真，且mark.is_disarm为假:
        如果unit.is_keep_distance为真:
            本段返回数值 -100
```

这份伪代码只截取明确路径，其余资格由调用者/前段负责。−100是实际返回代值，**还不是“无路可走”、不可进入或完整最终危险评分的证明**。

## 5. 值怎样变成候选的危险门禁

`scr_enemy_next_tile_mark_get` 调格助手（`0x141ee601a`），保存结果，再根据当前 `pathfind_unit_data` 调 `astar_type_get`（`0x141ee613d`）。随后调用：

```text
validated = astar_type_unit_data_validate(unitData, astarType, tileValue)
return orderedLess(validated, 0)
```

三参数验证调用 `0x141ee617d`，与0比较 `0x141ee619a`；真输出type13/value1，假输出type13/value0。比较助手 `0x140089b20` 接受有序负比较结果，排除unordered哨兵−2；它不是直接把任意非零数当真。

`astar_type_unit_data_validate@0x140aed2b0` 有一个可完整说明的路径：第二参数 astarType 与0比较相等（`0x140aed3e3 / 0x140aed402`）时，取第三参数并复制为输出（`0x140aed440–0x140aed450`，接 `0x140aed628–0x140aed62b`）。因此 **astarType=0的已见分支保留输入tileValue**。

非零type路径读取全局 `__astar_type_buffer_step`、`__astar_type_buffer_type`，按偏移 `buffer_peek`，非零查值可替换输入，零值则退回第三参数。类型缓冲的全部构建、数值编码和异常处理尚未恢复，不能将所有单位都视作astarType=0。

在新版目标格查询的一段候选处理里，先调用 `scr_grid_next_validate`（`0x140648e9b`）：返回假则跳 `0x140649140`（`0x140648eaa`）；通过后调用上述危险门禁（`0x140648f56`）：返回真也跳到该后续处理点（`0x140648f65`）。通过两个门禁才继续这里的正常路径，另查多格单位与当前格条件。

```text
如果gridNextValidate返回假:
    提前进入本段后续候选处理
否则如果nextTileMarkGet返回真:
    提前进入同一后续处理
否则:
    继续本段普通候选检查
```

**不能把这个跳转写成“一律删除候选”。** 同一后续点还处理实例、周边占格和视线，完整候选比较未闭合；门禁只证明路径改变与一段处理被跳过。

## 6. 贯通构造例：远程敌人面对一个未解除标记

假定当前弩手上下文调用新版查询，且已进入上述具体候选段；格G的标记实际符合前段陷阱分支，列表查询返回2，`is_disarm=false`、弩手 `is_keep_distance=true`。再明确给定本次 `astar_type_get` 返回0，以及gridNextValidate返回真。

1. 陷阱分支把格值设为−100。
2. 路径类型验证在type0分支保留−100。
3. `orderedLess(-100,0)` 为真，危险门禁输出布尔真。
4. 新版格查询在 `0x140648f65` 提前进入 `0x140649140` 后续处理。
5. 等整个查询完成才得到targetTile；33的主选择器再把这个真实返回值送给消耗品评分等消费者。

步骤1–4是条件完整的局部演算，步骤5是已见调用桥。**未确定的不是−100怎样判断，而是完整候选竞争以后G会被绕行、替换、留作后备还是导致无路返回。** 本轮不把最后的未知结论写成“弩手必走右边”。

若显式构造validated=0，负值比较为假，危险门禁本身不会提前跳；grid有效、多格单位、障碍和其他空间检查仍需通过。若gridNextValidate=false，则在危险门禁之前已经走后续分支。三个例子将格有效性与危险判断区分。

## 7. 盟友占位、AOE与临时寻路数据

### 7.1 占格读到了什么

新版查询读取 `posgrid`（`0x1406480c1`），以候选坐标和fallback −4调用 `ds_grid_get_ext`（`0x14064813f`）。后续有实例检查与周边查询 `scr_posgrid_around_search@0x140649a02`。gridNextValidate 又调用 `scr_cell_validate@0x140a7cef7`。

这证明当前位置实例、候选格和格有效性参加查询；尚未闭合友军/敌军、尺寸、临时占用、目标本身及共享格的全部区分。**目前不能给出“友军占位一律不能穿行”或固定占位罚分。**

具体例子只能写成：构造G的posgrid结果为某盟友实例F，查询确实拿到F；若随后实际cell/grid门禁拒绝，则按第5节转入后续处理。拒绝是否由F身份造成仍需补门禁生产者，不把“格上有F”和“因F被拒绝”混同。这是占位方向的明确剩余问题，而不是一个已复原的队形算法。

### 7.2 预告危险并非只看颜色

当前查询真实调用AOE标记和逃离扫描。AOE扫描还调用 `astar_get_cell@0x14065c66a`、标记实例查询 `0x14065c7c7`、Manhattan/Chebyshev距离（`0x14065cae0 / 0x14065ce67`）以及投射物障碍检查 `0x14065d13a`；存在live_call条件路径。

目前确认“逻辑格、距离和障碍参加扫描”，未恢复全部shape匹配、攻击者归属、预告剩余计数与最佳安全格排序。不能仅用一个地板颜色字段模拟怪物完整躲避策略，也不能保证任何预告都被所有敌人同等处理。

### 7.3 查询会准备并清理临时数据

选定路径调用 `scr_pathfind_enemy_begin@0x140642fcf`，后续见 `scr_pathfind_enemy_end@0x140646887`。begin/end按单位分支成对使用misc/enemy mark与unmark；还对NPC道路、畏火和多格单位做专门准备/归还。begin读取newgrid/temp_grid并清理临时网格；完整网格缓存所有权和各分支异常退出尚未逐一恢复。

目标格查询另外有陷阱/门/flee标记（例如 `0x14063e516 / 0x14063e57e / 0x14063e5f6`）以及对应解除（`0x14064a48f / 0x14064a8f2 / 0x14064a507`）、selfcell交换和多格填回，最后有临时spatial hash清理 `0x14064a9b0`。这说明调查空间机制必须追退出，而非只看候选生产。已见成对调用不证明所有失败、取消和动态分支都能恢复无副作用。

## 8. A*包装与完成边界

`astar_grid_path` 调 `astar_dll_buffers_set@0x1403f94c5`、`astar_dll_path_find@0x1403f95ac`，并调用 `astar_dll_error_get@0x1403f985c`。包内FastAstarClang.dll存在、包装入口可定位，但没有恢复DLL启发式、开放集合、对角穿越和完整无路协议。不能仅凭Astar名称补成某一种标准实现或认定原作每次都找最短安全路线。

已回答：新版查询被当前主选择器消费；远程/FOV/AOE/占格调用位置；部分格编码、陷阱保持距离−100路径；类型0保留值；负值布尔转换；候选早转分支；部分临时准备和清理。部分回答：实际空间流程与射击范围搜索。未回答：全候选最终比较、所有友军占格、格权值完整生产、全部路径失败返回、完整AOE逃离和DLL内部寻路。

自研建议是分别建模“格是否有效、危险原因、单位通行类型、射击许可、位置效用和路径失败”。要不要避开陷阱、是否跨越同伴、怎样比较距离与伤害风险，按我们自己的玩法写明确规则和测试；不要用未恢复的原作权重作为生产配置。

本机可选证据：[选定14入口](../../../_reference/stoneshard-study/eleventh-position-native.json)、[格分类](../../../_reference/stoneshard-study/eleventh-position-disassembly/annotated-scr_enemy_tile_priority.txt)、[负值门禁](../../../_reference/stoneshard-study/eleventh-position-disassembly/annotated-scr_enemy_next_tile_mark_get.txt)、[类型验证](../../../_reference/stoneshard-study/eleventh-position-disassembly/astar_type_unit_data_validate.txt)、[候选处理](../../../_reference/stoneshard-study/eleventh-position-disassembly/annotated-scr_enemy_find_target_tile_new.txt)、[格有效性](../../../_reference/stoneshard-study/eleventh-position-disassembly/scr_grid_next_validate.txt)、[有序小于](../../../_reference/stoneshard-study/eleventh-position-disassembly/runtime-less-than-int.txt)。正文自包含必要事实与未知，本地原始证据可再生成。

未运行游戏或做动态寻路验证，没有修改目标/存档、联网或setup；仅研究文档，不运行REA产品构建。剩余风险是把负格值叫完整评分、把跳转叫删除候选、把占位读取叫固定友军阻挡，以及把包装A*叫已经恢复寻路库。当前证据不保证任意战场的下一格都可预测。
