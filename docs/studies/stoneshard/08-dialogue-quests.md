# NPC 对话、状态副作用与任务推进

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [人质跟随与持久化](07-npc-persistence-following.md)

当前证据支持将对话条目与动作关联分开，也确认了人质跟随状态操作和葡萄园任务 `VineryThief` 的首次初始化条件。本文不恢复台词、选项文案或完整剧情图；行为伪代码由我们独立编写，只描述可确认的控制流，不是原始源码。

## 1. 模块职责与状态输入

对话入口需要决定如何开始一次交互；对话阶段处理器组织条目及动作关联；动作可能改变 NPC、任务或世界状态；任务管理器维护持久数据并连接日志、时间及完成处理。这些职责在现有制品中有不同入口，不能因为它们都由一次点击触发就当作同一个函数。

| 输入/状态 | 当前证据 | 未恢复部分 |
|---|---|---|
| NPC 交互上下文 | NPC 对话可用性、启动和角色内容入口 | 全部可用性条件与优先级 |
| 营地/事件上下文 | 交互启动读取事件存在、数据、参与者和延后事件等 | 具体选择哪一段剧情的全部规则 |
| `dialog_list` | 阶段处理器实际使用条目列表并添加条目 | 每个条目的完整字段、文本呈现与选项 ID |
| `dialog_actions_map` | 阶段处理器实际读取动作 map 并处理关联 | 所有 key/value 结构和确切触发时机 |
| `substate`、`hostage_substate` | 人质开始/停止跟随操作修改并持久写入 | 哪些具体按钮绑定这些操作 |
| `questsDataMap` | 任务启动、进度和下一目标处理器均读取 | 每个任务的完整 schema 与所有进度键 |
| 地图及日志状态 | VineryThief 入口调用地图处理器；任务启动有日志调用 | 精确地图坐标、完整失败/完成条件 |

## 2. 交互入口与阶段组织

`scr_npc_interact_start_dialogue` 是已编译的交互启动入口，原生路径包含营地事件存在检查、数据读取、活动角色、附加角色及延后事件处理入口，且在三个地址调用 `scr_dialogue_start`。这说明不同事件上下文可以引出对话；它不等于已经恢复完整的分支优先级。

`scr_dialogue_set_phase` 读取 `dialog_list` 和 `dialog_actions_map`。已确认有 `ds_list_add` 分派、列表长度处理及动作关联操作，也有格式和资源索引相关调用。可以确认该路径将“对话条目列表”和“动作关联数据”分开处理；不能据此命名某个商业对话树中间件，也不能补全未恢复的图节点 schema。

准确的局部步骤可以表述为：

```text
已恢复的阶段处理片段：
    使用 dialog_list 组织当前路径的条目
    通过列表添加分派写入条目
    查询列表长度等信息
    使用 dialog_actions_map 处理条目与动作的关联
```

这是结构规格，未指定动作是在生成条目、进入阶段、选中回答还是完成对话时执行。未恢复的触发时机必须保留，否则自研时很容易把“描述一个可执行动作”误写成“渲染时立即改变任务”。

### 真实对象与入口身份

| 条目 | SCPT/OBJT 索引 | data.win 记录偏移 | EXE VA |
|---|---:|---:|---|
| `scr_npc_interact_start_dialogue` | SCPT 1260 | 8991516 | `0x140460010` |
| `scr_dialogue_set_phase` | SCPT 4796 | 9019804 | `0x1413e0d20` |
| `o_dialogue` | OBJT 9661 | 12453664 | 本文不把对象登记等同于单个函数 |
| `o_NPC` | OBJT 4563 | 10767912 | 多个事件函数；父索引 3805 |

入口名称对应真实目录条目。只是目录存在的其他脚本，如回答构建、完成、可用性判断，不能自动作为“已经验证每条当前对话都会调用”的证据。

## 3. 具体对话动作例子：人质护送状态切换

`gml_GlobalScript_scr_npc_lines_generic_hostage` 把开始跟随和停止跟随函数注册为方法，函数引用地址分别为 `0x1400bc988` 与 `0x1400bc9e8`。实际开始函数将 `substate` 改为 `following`，停止函数改为 `waiting`，两者都调用 NPC 全局信息写入器，以 `hostage_substate` 为键保存状态。

```text
开始护送动作的已确认后果：
    现有选择上下文得到 NPC 实例
    instance.substate = "following"
    写入 NPC 全局信息("hostage_substate", instance.substate, 其余上下文)

停止护送动作的已确认后果：
    现有选择上下文得到 NPC 实例
    instance.substate = "waiting"
    写入 NPC 全局信息("hostage_substate", instance.substate, 其余上下文)
```

字符串 following/waiting/hostage_substate 有原生常量初始化证据。其完整空间消费者在 [NPC 持久化与跟随](07-npc-persistence-following.md) 说明：substate 比较后还要通过空间和 lock_turn 等条件，动作成功不保证同一时刻立刻移动。

`o_NPC Other23` 另有 `scr_dialogue_contract_hostage_check_rescued`、`scr_dialogue_start` 和 `scr_dialogue_contract_hostage_mark_rescued` 调用。它们说明互动路径连接人质救援状态，但本轮没有恢复这三次调用间全部条件，也没有把它们强行写成无条件固定顺序。

### 构造演算：一次动作如何留下持久后果

假设一个已满足前置条件的人质 substate 为 waiting，用户触发已绑定的开始操作。结果是实例值 following，并发起全局键写入 following。稍后触发停止操作则两处值写 waiting。操作无需复制整段剧情文本，也能成为可检验的状态转换规格。

这个构造并未指定按钮叫“跟我走”或“在这里等”；真实台词/按钮标签和选项 ID 未恢复。若界面只是显示候选条目、尚未执行动作，当前证据不能推导状态已经改变。动作注册、条目动作关联和实际执行应分别检查。

## 4. 具体任务例子：VineryThief 的首次初始化

`scr_npc_lines_vineyard_quest_start` 起点 `0x14006c530`，3179 字节完整指令解码。其任务标识 `VineryThief` 由初始化点 `0x14007b3bd` 绑定：字符串地址 `0x145aacc0e`，RValue 地址 `0x1497f3eb0`。所以此处的任务名来自真实常量，不能随意替换成另一个任务后仍声称是原行为。

### 已确认的条件与执行顺序

1. 调用 `scr_quest_get_started("VineryThief")`。
2. 将结果转换为真值并检查。
3. 为真时跳过首次启动和初始进度赋值。
4. 为假时先调用 `scr_quest_start`，随后调用 `scr_quest_set_progress`。
5. 两条路线重新汇合，继续执行地图位置查询和后续世界数据处理。

```text
葡萄园任务启动操作的已恢复片段：
    started = quest_get_started("VineryThief")
    如果 started 的真值为假：
        quest_start("VineryThief")
        quest_set_progress("VineryThief", 未恢复的初始键, 未恢复的初始值)
    继续已有地图查询与世界状态分支
```

“未恢复的初始键/值”是未知参数，不是要由读者填写的原源码，也不能被 `stage=1`、`accepted=true` 或其他常见命名替换。`quest_get_started` 的真值语义不等于全任务状态枚举：尚未恢复完成/失败/重启与这个查询的关系。

已启动路径跳过的是这两次初始化调用，不是整个操作。后面的地图相关路径仍可能执行，不能将此脚本写成已开始就直接 return。

### 地图分支确认到哪里

汇合后的路径有以下直接调用：`scr_glmap_getLocation`、`scr_glmap_getNearestLocationByCoord`、`assert`、`scr_globaltile_reset`、`scr_globaltile_location_replace`、`scr_globaltile_set`。它们说明任务入口可以改变世界数据，不能只把任务解释成日志里的一行文字。

调用的完整参数、条件与准确位置未恢复；尤其不能把 assert 的存在当作“绝不会失败”，也不能编造葡萄园坐标、替换的房间名称或任务目的地。这里的 map 是世界数据，不是前面 `dialog_actions_map` 的对话动作关联表。

### 构造演算：再次触发会跳过什么

构造 A：查询返回 false。入口依次执行 quest_start 和一次初始进度调用，再进入地图处理路线。其初始键和值仍保持未知符号 P/V。

构造 B：之后再次进入，查询返回 true。入口直接跳到汇合点，不再次执行这两个调用；地图路线仍保留。由此可确认局部重复初始化保护，不能扩大成“整个任务入口完全幂等”，因为地图副作用的重复执行语义没有恢复。

构造 C：任务已经完成。当前覆盖不足以确定 quest_get_started 会返回什么，因而不能给出该情况下的执行结果。把完成等同于 started=true 是可能的自研约定，但不是当前证据。

## 5. 通用任务层：数据、时间、日志和目标

`scr_quest_start`、`scr_quest_set_progress` 和 `scr_quest_next_target` 均读取 `questsDataMap`。进度路径使用 map 查询/存在/设置/删除与 list 查询/替换的分派；这支持任务在集中数据结构中管理，但每层字段和列表元素语义尚未完整恢复。

| 处理器 | 已确认连接 | 本文没有填补的内容 |
|---|---|---|
| `scr_quest_start` | 读取任务 map；时间戳；journalTaskAdd；日记更新 | 各副作用的全部前置条件与精确 schema |
| `scr_quest_set_progress` | map/list 操作；某分支可调用 quest_start；日记更新 | 进度值如何比较、何时自动开始 |
| `scr_quest_next_target` | 读取任务 map；某分支调用 quest_set_complete | 目标数量、最终目标判断和奖励公式 |

一个可确认的调用关系是“任务推进与日志/时间/完成处理相连”。不能据此宣称每次 set_progress 一定刷新每个日志组件，也不能把所有任务归为固定三阶段。`scr_contract_*` 是另一些真实目录入口；本轮 VineryThief 的分析没有恢复契约期限、奖励、失败和竞争佣兵的完整算法。

`scr_quest_start` 的日志相关调用让我们知道一次新任务操作可以进入 journal/diary 层。但是本轮未启动游戏观察 UI，也未比对执行前后的存档，所以不能给出用户看到的精确文字、排列或刷新时刻。

## 6. 证据地址表

| 事项 | 关键 VA / 数据身份 |
|---|---|
| 交互启动函数 | `0x140460010`，6406 字节 |
| 三处对话启动调用 | `0x1404613ce` / `0x1404616ef` / `0x14046183e` |
| 阶段处理函数 | `0x1413e0d20`，3782 字节 |
| 条目列表 / 动作 map | `0x1413e186a` / `0x1413e19ec` |
| ds_list_add 元数据 / 分派调用 | `0x1413e1898` / `0x1413e18be` |
| 人质动作注册 | `0x1400bc988` / `0x1400bc9e8` |
| 开始/停止动作函数 | `0x1400bbb80` / `0x1400bc070`，各 697 字节 |
| 人质全局状态写入 | `0x1400bbd6e` / `0x1400bc25e` |
| 人质获救检查/对话/标记调用 | `0x143a529a0` / `0x143a52a7f` / `0x143a52b51` |
| 葡萄园任务入口 | `0x14006c530`，3179 字节 |
| VineryThief 常量初始化 | `0x14007b3bd`；字符串 `0x145aacc0e` |
| get_started / 条件跳转 | `0x14006c78c` / `0x14006c799`–`0x14006c79b` |
| 首次任务启动 / 初始进度 | `0x14006c81c` / `0x14006c8cc` |
| 地图查询 | `0x14006c94c` / `0x14006caa9` |
| 断言 / 世界 tile 重置 / 位置替换 | `0x14006cb3f` / `0x14006cca3` / `0x14006cd7a` |
| 世界数据写入调用 | `0x14006ced4` / `0x14006cfbb` |
| quest_start | SCPT 3686，记录 9010924；VA `0x140ff2950` |
| quest_set_progress | SCPT 3697，记录 9011012；VA `0x140ff9a50` |
| quest_next_target | SCPT 3699，记录 9011028；VA `0x140ffd330` |
| 三个任务 map 读取 | `0x140ff2c5d` / `0x140ff9c14` / `0x140ffd6c7` |
| 时间戳 / 日志项 / 日记 | `0x140ff3adf` / `0x140ff3c62` / `0x140ff3d4a` |
| 进度处理中的启动分支 | `0x140ffae52` |
| 下一目标中的完成分支 | `0x140fff6da` |

本机证据：[第一轮 NPC 报告](../../../_reference/stoneshard-study/npc-findings.md)、[第二轮 NPC 报告](../../../_reference/stoneshard-study/second-npc-findings.md)、[第一轮原生分析](../../../_reference/stoneshard-study/selected-native-analysis.json)、[第二轮原生索引](../../../_reference/stoneshard-study/second-npc-native.json)、[常量初始化](../../../_reference/stoneshard-study/second-npc-constant-initializers.json)。第一轮报告中的“尚未确认”可能已由第二轮补充；本文采用两轮合并后的界限。

## 7. 未做、未知与独立设计建议

未运行对话或任务，未修改存档，未读取并发布台词、完整任务表或专有代码。未恢复 action map schema、动作触发时机、选项 ID、葡萄园初始进度键值、全部地图参数，以及完成/失败/重启条件。主要风险是将调用存在误当作每次必然执行，以及把局部首次初始化保护误称为整个入口幂等。

我们自己的游戏可以独立把对话动作设计为明确的领域事件，例如“开始护送”和“接受任务”，让 NPC、任务、地图和日志分别消费，并为多次执行定义去重身份与失败结果。这是建议，不能写成 Stoneshard 已经采用事件总线或事务框架。另一个可独立采用的规则是“呈现选项不修改状态，确认动作才执行副作用”；当前原游戏动作时机未完整恢复，不能把我们的规则归给它。
