# NPC 持久化、离屏状态与人质跟随

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [作息与睡眠](06-npc-schedule-sleep.md) · [对话与任务](08-dialogue-quests.md)

当前证据确认 NPC 有房间实体数据和长期状态两层，也确认人质的 `following/waiting` 状态及一个实际消费者。它尚不能回答所有离屏更新、跨地图跟随和距离门槛。本文不把接口存在、保存字段或名称当作完整运行算法；伪代码是我们编写的局部行为规格，不收录原始专有代码。

## 1. 两种不同的问题

“玩家不在附近时 NPC 还存在吗”至少包含两个问题：当前房间里是否保留运行实例，以及长期状态是否仍被保存。卸载实例不等于删除 NPC 的长期身份。另一个独立问题是“离屏时如何更新”：可以逐回合模拟，可以按事件更新，也可以在回来时补算。这三种策略均能保留相似的存档字段；目前没有足够证据在本游戏中选定一种。

| 层 | 当前确认的内容 | 用途或边界 |
|---|---|---|
| 房间实体 | x/y、对象名、额外自身数据的保存/创建/恢复处理器 | 重建当前可见实例；生命周期调用全链未穷尽 |
| NPC 全局信息 | global data/info 的读取与写入；真实存档中的 NPC map | 保存跨房间的角色状态 |
| 空间行为 | following 的 FSM 分支、lock_turn 门禁和目标周围选格 | 已加载实例的行为条件；跨区延续未确认 |
| 离屏时间更新 | 若干时间/状态字段和读取入口 | 字段存在不能证明逐回合模拟或补算公式 |

## 2. 房间快照的保存子过程

`scr_locationRoomEntityNpcSaveDataGet` 创建一个 map，读取被选实例的位置和 `object_index`，将对象索引转换成对象名，再调用 `saveSelfData` 把额外自身状态写为子 map。

```text
形成房间实体快照(instance)：
    创建结果 map
    读取 instance.x、instance.y
    读取 instance.object_index
    通过对象名称查询取得 object_name
    extra = saveSelfData(instance)
    将位置、对象名称和 extra 子 map 写入结果
    返回结果
```

这里没有自行定义 extra 的所有字段。保存函数读取的属性，与后文创建函数实际查询的 `x/y/object_name` 键共同支持快照的这部分结构；不能凭此认为全局 NPC map 与房间快照是同一个数据结构。

## 3. 创建和恢复是两个子过程

### 先根据对象名创建实例

`scr_locationRoomEntityNpcInstanceCreate` 实际查询保存 map 的 `x`、`y`、`object_name`。前两项的默认值为 −1；对象名经过资源索引解析。结果初始为 −4，只有对象解析结果不等于 −1 才调用共享 `scr_enemy_create`。

```text
创建房间 NPC(saved)：
    x = 查询 saved["x"]，缺失默认 -1
    y = 查询 saved["y"]，缺失默认 -1
    object_name = 查询 saved["object_name"]，其全部默认语义未恢复
    object_index = 资源索引解析(object_name)
    result = -4
    如果 object_index != -1：
        result = 共享实体创建(x, y, object_index, 其他初始化参数)
    返回 result
```

共享创建器的名称带 enemy，不代表通过它创建的一定是敌方角色。当前 NPC 对象继承 `o_enemy` 的基础设施也支持它被多个实体类型复用。

这个子过程只在对象索引上有明确的失败门控。不能补写“x/y 为 −1 就拒绝创建”，也不能声称资源缺失时会自动替换成默认 NPC。

### 再向已有实例应用保存数据

`scr_locationRoomEntityNpcSaveDataSet` 向实例恢复数据时先清理碰撞，恢复位置，调用 `loadSelfData`，然后执行附加事件和 state/image_yscale 分支。

```text
应用 NPC 保存数据(instance, saved)：
    清理该实例的旧碰撞状态
    根据保存 map 查询并恢复 x/y
    loadSelfData(instance, 自身数据)
    执行已编译的附加事件与状态相关分支
```

最后一步未全部恢复，不把它简化成“所有字段原样赋值”。特别是加载代码引用 time_period 的事实，仅给出研究入口；本轮未恢复“当前时钟与保存时钟不同就补算多少次”的算法。

卸载处理器 `scr_locationRoomEntityNpcInstanceDestroy` 调用 `instance_destroy_enemy_not_execute`。这些处理器共同说明存在可分别保存、销毁、创建和恢复的路径；它们在每次房间切换中的调用顺序、哪些实例被纳入、失败时如何回滚仍未穷尽。

## 4. 一个真实存档例子：osbrook_smith

主调查只读解析了本机 `characters_v1/character_2/exitsave_1/data.sav`。来源 SHA-256 为 `0155bd9b288fe1e71813815a912bfc3f4cab765f3a2c89a080961cbac9487a95`。本文只展示精简字段；未包含完整存档、其他角色数据或商品内容。

实际记录位于：

```text
globalmapDataMap
  .locationsDataMap["32_10"]
  .npc_data["osbrook_smith"]
```

以下三个值在精简观察记录中明确保留：

```json
{
  "state": "idle",
  "current_day": 0.0,
  "sprite_name": "s_blacksmith_01"
}
```

同一 NPC 记录还存在下列键，但精简观察没有输出其全部值：

| 字段组 | 实际存在的键 | 可以证明什么 |
|---|---|---|
| 时间与状态 | `current_time`、`current_day`、`new_room_turns`、`state` | NPC 状态不只是一张 sprite |
| 层级/位置上下文 | `current_floor`、`next_floor` | 长期记录保存层级上下文；具体层含义未恢复 |
| 商业状态 | `trade_list`、`restock_timestamp`、`gold_restock_timestamp`、`is_restock` | 商人数据和补货相关状态有持久字段 |
| 角色及内容 | `name_index`、`sprite_name`、`is_quest`、`news_left` | 角色和任务/内容相关字段被保存 |

`current_day=0` 是这个保存记录中的值，不是“NPC 总是第一天”或“游戏刚启动”的结论。`state=idle` 也不能说明保存时本机时钟、游戏时钟或 NPC 是否离屏。sprite 名是证据中的身份标识，不是可复制到我们产品的资源。

### 构造演算：身份状态和房间实例分离

构造一份房间快照，令其对象名为真实类型 `o_npc_smith_osbrook`，x/y 为人为选择的 `(100,200)`，并假设本次资源解析成功。创建子过程会把三项传给共享创建器；之后恢复子过程可以处理自身数据。`(100,200)` 不是上面真实存档中的坐标，两份数据不能混写。

另构造资源解析返回 −1。结果保持 −4，创建器不被调用。这个失败与持久 map 中是否仍保留 `osbrook_smith` 是不同问题：创建一个房间实例失败，不等于已确认删除全局身份。

如果构造“玩家离开 8 小时后返回”，当前证据只允许说保存、创建、加载和时间字段都有入口。无法演算 NPC 离屏走了几格、补了几次货、是否醒来；给出任何具体次数都会加入尚未证实的规则。

## 5. 人质开始/停止跟随：状态操作与持久写入

一个真实的实体跟随例子是通用人质护送脚本。开始脚本把 `substate` 改为 `following`，停止脚本改为 `waiting`，两者均通过 `scr_npc_set_global_info` 保存到键 `hostage_substate`。

```text
人质开始跟随操作：
    对已有对象选择器产生的 NPC 实例：
        substate = "following"
        通过现有全局信息处理器写入 "hostage_substate" 和该状态

人质停止跟随操作：
    对已有对象选择器产生的 NPC 实例：
        substate = "waiting"
        通过现有全局信息处理器写入 "hostage_substate" 和该状态
```

选择器值 4563 对应 `o_NPC`；实际对话触发条件和前置过滤未全部核对。这里不写成“遍历世界上的所有 NPC 并使其跟随”，也不声称任意角色都能访问此操作。

常量有直接初始化证据，而不是仅依赖函数名：`following`、`hostage_substate`、`waiting` 分别由 `0x1400bcd60`、`0x1400bcd7f`、`0x1400bcd9e` 绑定。

## 6. FSM 如何消费 following

`scr_update_FSM_NPC` 读取 `substate` 并与实际常量 `following` 比较，相等时进入一个空间条件块。该块还检查 `lock_turn` 列表是否为空，然后才可能进入目标周围选格路径。

按当前恢复覆盖，可以准确表达这条局部路线：

```text
已恢复的 following 分支入口：
    如果 substate == "following"：
        进入空间条件比较
        如果该空间条件未通过：跳过这条选格路径
        如果 lock_turn 列表不为空：跳过这条选格路径
        继续检查已有目标相关条件
        满足当前分支的条件时，调用目标周围选格处理器
```

这是控制流片段，不是完整跟随函数。`following` 也不是进入空间块的唯一可能原因：原生邻近分支还有特殊对象的选择条件。我们未给空间比较中的两个量命名为“玩家距离”或填写具体阈值，因为尚未完整恢复其来源。`lock_turn` 非空分支有明确跳转，但列表每个元素的语义没有恢复。

周围选格调用支持“跟随状态参与空间行动选择”的结论；不能据此推导出每回合恰走一格、保持两格距离、自动跨区或参与战斗。邻近处理器中存在走路/寻路基础设施，但没有把所有调用连成已验证的整段护送轨迹。

### 构造演算：状态变化不等于即时移动

构造某个已满足对话前置条件的人质，当前 substate 为 waiting。调用开始操作后，实例值变成 following，全局信息写入同一状态。下一次 FSM 到达已确认的比较分支时，会进入 following 路线。

若此时构造 `lock_turn=[L]`，列表非空，当前目标周围选格路线被门禁跳过。由此可以确认“开始操作成功”和“本次 FSM 立刻移动”不是同一个事实。再构造列表为空、空间及其他目标条件通过，才会到达已确认的选格调用；选出的具体格子与后续移动结果仍不能填值。

随后调用停止操作，substate 和全局键均写 waiting。这能说明下一次上述 following 相等判断不会因这一字段而通过，但不能声称 NPC 此后永远静止：它还有其他状态和行为分支。

## 7. 跟随与商队成员的职责区别

人质护送的依据是实例状态变化和 FSM 消费。商队成员的招募、忠诚、服务和营地活动是另一组模块；`caravanFollowerAdd` 不能作为“每一步物理跟随”的证据。警卫 `scr_stateMoveToPlayer` 也不能自动当作人质护送或商队移动，第一轮已确认每日触发中的一个对象选择值为 `o_npc_guard`（4612）。

这里只按已恢复证据区分职责。没有声称 Stoneshard 完全没有战斗同伴，也没有拿历史开发者说明替代当前安装包的运行验证。

## 8. 证据位置与身份表

| 事项 | VA / 身份 |
|---|---|
| 房间实体保存 | `scr_locationRoomEntityNpcSaveDataGet`：`0x141db1850`，1700 字节 |
| 读取 x/y/object_index | `0x141db1a47` / `0x141db1afd` / `0x141db1be2` |
| 对象名与自身数据 | `object_get_name` 调度 `0x141db1c1d`；saveSelfData `0x141db1d68` |
| 房间实体创建 | `scr_locationRoomEntityNpcInstanceCreate`：`0x140fedf70`，2039 字节 |
| x/y/object_name 三项查询 | `0x140fee232` / `0x140fee2e7` / `0x140fee39c` |
| 资源解析 / 创建 | `0x140fee3fe` / `0x140fee533` |
| 恢复保存数据 | `scr_locationRoomEntityNpcSaveDataSet`：`0x1401c2670`，1941 字节 |
| 碰撞清理 / 自身数据加载 | `0x1401c286d` / `0x1401c2bcc` |
| 实例卸载调用 | `0x1406e1c82` |
| 开始跟随脚本 | `0x1400bbb80`，写状态 `0x1400bbccd`，写全局 `0x1400bbd6e` |
| 停止跟随脚本 | `0x1400bc070`，写状态 `0x1400bc1bd`，写全局 `0x1400bc25e` |
| following 消费 | 读字段 `0x141786162`，相等分支 `0x1417878a0` |
| lock_turn / 列表门禁 | `0x141787966` / `0x14178798b` 及后续分派 |
| 目标周围选格 | `0x141787bf4` |
| o_NPC 与村镇/铁匠继承 | 4563 ← 4567 ← 4627；4563 父索引 3805 |

本机证据：[真实铁匠保存观察](../../../_reference/stoneshard-study/save-smith-observation.json)、[第二轮报告](../../../_reference/stoneshard-study/second-npc-findings.md)、[原生函数索引](../../../_reference/stoneshard-study/second-npc-native.json)、[常量初始化](../../../_reference/stoneshard-study/second-npc-constant-initializers.json)。

## 9. 未做、未知与自研借鉴

没有进行运行时跟随、换区或睡眠测试；本次只整理既有静态调查和只读存档观察。未知包括全部房间调用链、离屏更新粒度、时间差补算、跟随距离、跨区转移、目标失效与战斗中断。风险是将可重建的实体误解为逐回合存在，或者把持久状态写入误解为保存后必然正确继续行动。

独立设计建议：用稳定 NPC 身份保存长期事实，用房间快照保存当前表现，用明确的更新策略处理离屏时间。我们的游戏可以独立选择事件驱动补算，记录 `lastUpdatedGameTime`，并明确补算顺序与上限；这不是已确认的 Stoneshard 算法。跟随也可以独立设计为目标身份、移动意图、锁定原因和路径结果四部分，把“不能移动”的原因保留为可诊断状态。
