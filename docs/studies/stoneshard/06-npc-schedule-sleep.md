# NPC 作息、工作与睡眠

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [NPC 持久化与跟随](07-npc-persistence-following.md)

这份文档解释当前安装制品中已经确认的时间分类、NPC 行为配置、睡眠进入与清理子过程。它不是游戏完整 AI 的恢复源码。伪代码由我们按证据重新组织，只表达已经确认的步骤；省略的条件会明确列出。调查没有启动游戏，也没有修改安装目录。

## 1. 模块负责什么

已确认的设计可以分为三个环节：时间控制器把游戏内小时分成四段；NPC 用当前时间段选择活动目标和行为回调；状态机负责处理移动、目标变化、工作与表现。时间分类回答“现在是哪一段”，目标数组回答“这一段对应哪个目标”，回调回答“到达相关行为分支后做什么”。不能把“当前应该睡觉”直接等同于“实体已经成功躺在床上”。

实际字段包括 `time_period`、`target_array`、`target`、`sleep_target`、`is_sleeping`，以及 `time_period_morning/day/evening/night` 四个方法槽。状态机还读取 `state`、`move_target`、`previous_target`、`is_rest`、`is_transit`、`new_room_turns` 等上下文，但这些字段的所有组合尚未恢复。

| 输入或状态 | 确认的作用 | 尚不能断言的内容 |
|---|---|---|
| `timeDataMap["hours"]` | 时间分类处理器的小时输入 | 此处不负责定义时间加速和时间冻结 |
| `time_period` | 0–3 的时间类别，供活动选择使用 | NPC 每次一定立即执行新活动 |
| `target_array` | 按时间类别索引活动目标；睡眠可取索引 3 | Osbrook 铁匠具体四个实例目标、房间及坐标 |
| 四个时间段回调 | 允许父对象默认配置与子对象覆写 | 任何回调都没有中断或前置约束 |
| `sleep_target` | 睡眠目的地的优先来源 | 该目标由哪些剧情或地图配置赋值 |
| `is_sleeping` | 睡眠初始化门控与清理路径的判断值 | 始终是严格的二值布尔状态 |

## 2. 小时分类算法

`gml_Object_o_time_controller_Other_14` 从 `timeDataMap` 查询 `hours`，按顺序比较下界和上界，写入 `time_period` 及调试标签。已确认的普通数值分支如下：

```text
分类小时(h):
    如果 6 <= h < 12：返回 (0, "morning")
    否则如果 12 <= h < 19：返回 (1, "day")
    否则如果 19 <= h < 23：返回 (2, "evening")
    否则：返回 (3, "night")

更新类别(h):
    old = time_period
    (time_period, time_period_text_debug) = 分类小时(h)
    如果 time_period 与 old 不同：
        调用当前时间控制器的事件处理 helper，参数为 5
```

“其余”是实际最后分支，不应改写成仅匹配 `h >= 23`。在合法的 0–23 小时域中，night 为 23:00 到次日 06:00；输入异常值、缺失键、非数值或比较错误的处理没有被这份规格覆盖。

| 小时范围 | 类别 | 标签 | 类别写入的 VA |
|---|---:|---|---|
| `[6,12)` | 0 | morning | `0x1438d9ca4` |
| `[12,19)` | 1 | day | `0x1438d9e58` |
| `[19,23)` | 2 | evening | `0x1438da008` |
| 普通小时域的 `[23,24)`、`[0,6)` | 3 | night | `0x1438da071` |

小时键和标签不是由命名推测：初始化器 `0x1438da554` 将字符串 `hours` 绑定到常量值，`0x1438da573`、`0x1438da592`、`0x1438da5b1`、`0x1438da5d0` 分别绑定四个标签。上界比较 helper `0x140089b20` 接收整数 12、19 或 23，转成 double 后调用比较器，返回“结果为负且不是 −2”。这个排除项意味着不能将错误比较结果直接当作普通“小于”。

事件参数 5 的调用证据在 `0x1438da0dd`；没有据此证明它向所有 NPC 广播唤醒。

## 3. 用继承和覆写配置一个真实 NPC

### 对象身份与继承

| 对象 | OBJT 索引 | 父索引 | 相关职责 |
|---|---:|---:|---|
| `o_time_controller` | 4032 | 无父对象（记录值 −100） | 时间类别 |
| `o_npc_smith_osbrook` | 4627 | 4567 | Osbrook 铁匠具体配置 |
| `o_village_standing` | 4567 | 4563 | 村镇 NPC 通用活动回调 |
| `o_NPC` | 4563 | 3805 | NPC 基础行为 |
| `o_enemy` | 3805 | 本文未追踪 | 共享实体基础设施 |
| `o_NPC_target` | 4565 | 本文未追踪 | 活动目标对象 |
| `o_db_sleep` | 5925 | 本文未追踪 | 清理路径查找的睡眠效果对象 |

父索引从 `data.win` OBJT 记录的 `+28` 读取。此处列出 `o_enemy` 仅说明继承身份，不表示村镇 NPC 的产品职责是敌人。

父对象 `o_village_standing` 的 Create 把 morning、day、evening 绑定到 `do_animation`，把 night 绑定到 `do_sleep`。铁匠的 Create 先执行继承初始化，再创建自身 `do_smith_work` 方法，只覆写 morning 和 day。

| 槽 | 父对象默认值 | Osbrook 铁匠最终配置 |
|---|---|---|
| morning | `do_animation` | `do_smith_work` |
| day | `do_animation` | `do_smith_work` |
| evening | `do_animation` | 继承默认值 |
| night | `do_sleep` | 继承默认值 |

配置过程的行为规格是：

```text
村镇 NPC 默认配置：
    morning = 默认动画方法
    day = 默认动画方法
    evening = 默认动画方法
    night = 睡眠方法

Osbrook 铁匠配置：
    执行父对象配置
    morning = 铁匠工作方法
    day = 铁匠工作方法
```

这是确切的实例类型配置例子。它支持“复用通用作息，只替换工作行为”的结构结论。`do_animation` 的具体动作序列没有在本轮完整恢复，不能把 evening 槽直接解释为“必定去酒馆喝酒”。

### 目标与方法不是同一层

`scr_npc_work` 读取 `target_array[time_period]`，处理目标变化及距离，再按当前类别读取对应方法。有效方法与 −4 哨兵比较后交给动态调用 helper。`scr_update_FSM_NPC` 也按 time_period 取目标，并存在检查目标 `is_teleport` 后调用 `scr_npc_teleport_to_move` 的分支。

只按已确认部分可写为：

```text
活动选择子过程：
    p = 当前 NPC 的 time_period
    活动目标候选 = target_array[p]
    由现有目标比较、距离和状态分支决定如何处理候选
    当控制流到达活动执行分支：
        method = 对应 p 的时间段方法槽
        如果 method 不等于 -4 哨兵：动态调用 method
```

中间一句是显式的未恢复部分，不是虚构的“任何距离都可执行”条件。两个目标机制也不能合并：`target_array[p]` 用于当前活动，而睡眠目的地允许 `sleep_target` 覆盖。

## 4. 睡眠进入子过程

默认睡眠方法的闭包起点是 `0x143a6d2e0`。其目的地选择、初始化门控和关键副作用如下：

1. 初始目的地为 −4。
2. 如果 `sleep_target != -4`，优先使用 `sleep_target`。
3. 否则，先检查数组长度是否大于 0；非空时尝试读取 `target_array[3]`，并有数组类型和至少 4 项的边界检查。空数组保留初始 −4；非空但少于 4 项跳到另一边界路径，本规格不补写其最终结果。
4. 检查 `is_sleeping`。已为真时跳过首次进入的初始化块。
5. 首次进入时，目标存在才读取目标 `start_x/start_y` 并调用坐标更新。
6. 选择睡眠 sprite/动画，写入 `is_sleeping=true`，并处理循环音效等表现。

```text
选择睡眠目的地：
    destination = -4
    如果 sleep_target != -4：
        destination = sleep_target
    否则如果 target_array 的长度大于 0：
        如果数组类型合法且至少有 4 项：
            destination = target_array[3]
        否则：进入原处理器的类型/索引边界路径（结果未恢复）
    返回 destination

首次进入睡眠块：
    destination = 选择睡眠目的地()
    如果 is_sleeping 的真值为假：
        如果 destination 实例存在：
            通过坐标更新处理器使用 destination.start_x / start_y
        执行睡眠动画和 sprite 选择
        is_sleeping = true
        执行本分支的音效处理
```

目标存在的判断约束坐标更新；不能补写成“目标不存在则整个函数立即退出”。`start_x/start_y` 是实际读取字段，也不能替换成 `destination.x/y` 后声称是原实现。数组为空与“数组非空但缺第 4 项”走不同路径，不能把两者统一写成安全地忽略目标。

## 5. 退出睡眠：假值清理和前置约束

`o_village_standing Other17` 有具体睡眠清理路径。进入此块需要 `is_sleeping` 为真，且 `scr_instance_exists_in_list` 返回的睡眠对象实例存在；对象选择值 5925 对应 `o_db_sleep`。

在确认的清理块中，`is_sleeping` 被写为 type `0xD`、数值 0 的 RValue，表达 **false**。第三轮复核了目标运行时的真值转换助手 `0x145196dc0`：类型 13 经数值比较分支，数值零转换为假；类型 5 是另一个分支，不能混同。早期版本将这个写入误称为 undefined，现已更正。之后销毁选中的睡眠效果实例，停止 `work_sound`；后续还涉及 idle sprite、空格选择、坐标与碰撞恢复。

```text
已确认的睡眠清理块：
    如果 is_sleeping 的真值为真：
        effect = 已有实例列表查询(o_db_sleep, 其他查询参数)
        如果 effect 实例存在：
            is_sleeping = false
            销毁选中的 effect
            停止 work_sound
            执行当前分支的表现、位置与占格恢复
```

查询的全部列表/参数语义与所有异常分支未恢复，伪代码没有把它替换成“任意睡眠对象都可删除”。`scr_timezone_behaviour_npc` 的一个状态转换分支调用参数 7 的事件 helper，再设置 state；这为时间转换与 Other17 清理路径的关联提供依据，但不证明每天 06:00 一定满足全部清理前置条件。

## 6. 构造演算：边界时刻和目标覆盖

下面使用真实的铁匠类型配置，但目标符号 A/B/C/D、坐标与效果实例是人为构造输入，不是游戏存档值。设 `target_array=[A,B,C,D]`，D 的 `start_x=100`、`start_y=200`，`sleep_target=-4`，初始 `is_sleeping` 为假，且活动执行前置条件满足。

| 输入小时 | 分类计算 | 被选方法 | 可确认的子过程结果 |
|---|---|---|---|
| 5 | 不满足前三段 → 3 | 睡眠 | 首次进入使用 D；存在时更新坐标为其 start 字段 |
| 6 | `6<=6<12` → 0 | 铁匠工作 | 到达工作分支时调用工作方法；不能仅凭时钟保证已起床 |
| 12 | 第一段上界排除，第二段包含 → 1 | 铁匠工作 | 保持工作类方法，目标槽由 A 切为 B |
| 19 | 第二段上界排除，第三段包含 → 2 | 默认动画 | evening 方法；具体动画未恢复 |
| 23 | 第三段上界排除 → 3 | 睡眠 | 回到夜间方法，睡眠目的地仍按独立规则选择 |

再构造 `sleep_target=E`，E 的 start 坐标为 `(300,400)`。即使 `target_array[3]=D`，睡眠目的地也选择 E。若 E 不存在，已确认的坐标更新不会执行；不能推断程序会自动回退到 D，因为回退发生在 `sleep_target==-4` 的分支。

最后构造一次清理事件：`is_sleeping=true`，查询返回一个存在的 `o_db_sleep`。清理后的值是假，效果被销毁，音效停止。若查询不返回实例，不能使用这条分支推导出同样结果。这说明“日程切换”“睡眠状态”“睡眠效果”必须分开描述。

## 7. 证据位置

| 事项 | VA / 数据位置 |
|---|---|
| 小时分类函数 | `0x1438d9a20`，1900 字节完整指令解码 |
| 比较上界 helper | `0x140089b20`，有限范围独立检查，未作为全程序语义证明 |
| 父对象 Create | `0x143a7adf0` |
| 父睡眠/动画方法绑定 | `0x143a7b677` / `0x143a7b737` |
| morning/day/evening/night 赋值 | `0x143a7b905` / `0x143a7b93b` / `0x143a7b971` / `0x143a7b9a7` |
| 铁匠 Create 与工作闭包 | `0x143b07100` / `0x143b05470` |
| 铁匠 morning/day 覆写 | `0x143b07f50` / `0x143b07f89` |
| 活动执行处理器 | `scr_npc_work`：`0x140027e30` |
| FSM 按类别读取目标 | `0x141787596`、`0x1417875ac` |
| 可选目标瞬移 | 检查 `0x14178754e`，调用 `0x14178768d` |
| 睡眠目标/数组 fallback | `0x143a6d7de`、`0x143a6d81a`、`0x143a6d9b2` |
| 首次睡眠检查与坐标更新 | `0x143a6d9ed` / `0x143a6dcd3` |
| 写入睡眠真值 | `0x143a6e4b1`–`0x143a6e4cc` |
| 清理事件与 false 赋值 | `0x143a8a400`；关键写入 `0x143a8a818`–`0x143a8a82e` |
| 时间转换中的事件调用 | `0x1413f171a`–`0x1413f1720` |

本机证据：[第二轮报告](../../../_reference/stoneshard-study/second-npc-findings.md)、[原生函数索引](../../../_reference/stoneshard-study/second-npc-native.json)、[常量初始化记录](../../../_reference/stoneshard-study/second-npc-constant-initializers.json)。证据文件可能是本机研究产物；其缺席不使本文的规格变成运行验证。

## 8. 未做、未知与独立设计借鉴

未做运行时验证，原因是当前结论来自静态证据。未知包括铁匠具体目标数组、床位、完整走路路线、清理条件全部组合，以及地图卸载期间如何结算作息。风险在于把配置方法误当作必然发生的动作，或没有核对 RValue 类型及消费者便解释状态语义。

用于我们自己游戏的独立设计建议：用日程数据定义“应做什么”，用动作状态机执行“如何抵达和完成”；角色只覆写差异行为。可以独立采用显式的睡眠枚举，例如 Awake/Preparing/Sleeping/Waking，并明确目标失效、中断和恢复规则。这个枚举不是已证实的 Stoneshard 实现。我们也可以独立规定目标失效时重新找床或回到安全点，但不能将该策略归因于本游戏。
