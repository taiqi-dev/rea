# 保存、恢复与逻辑时钟的边界

预告技能的增量生产与落点事件见 [15 生产与结算链](15-telegraph-production-chain.md)，提交、取消与 AI 门禁见 [16 技能提交](16-skill-commit-and-ai-gates.md)。本文的保存边界不能替代这些运行阶段的静态证据。

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [地牢生成](02-dungeon-generation.md) · [NPC 作息](06-npc-schedule-sleep.md) · [NPC 持久化](07-npc-persistence-following.md) · [预告攻击](13-telegraphed-attacks.md)

这轮静态续查确认了三个局部事实：角色保存器包含 `state` 和部分技能/Buff 数据；公共回合入口在时间未冻结时调用游戏时间更新；地牢楼层 seed 有明确的 `random_set_seed` 调用。它们仍不足以证明预告攻击在读档后完整继续、NPC 离屏逐回合行动，或者同一 seed 在所有返回与读档场景都恢复完全相同的房间。

本文关注前述模块之间的边界，不重新描述整个游戏。伪代码由我们编写，是已确认局部关系的行为规格，不收录原始专有代码、台词或资产。

## 1. 证据身份、方法与覆盖

结论绑定本机安装制品，而非未经运行核实的显示版本号：

| 制品 | 字节数 | SHA256 |
| --- | ---: | --- |
| `StoneShard.exe` | 166577664 | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| `data.win` | 109736736 | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

安装路径为 `E:\Steam\steamapps\common\Stoneshard`。沿用前轮的[制品复核](../../../_reference/stoneshard-study/third-target-hash-verification.json)、函数登记、对象元数据和已保存的精简存档观察。本轮没有读取新存档，没有启动游戏、附加进程、修改游戏或存档，也没有观察网络。

本轮使用本机 Python 3.12 与 Capstone 5.0.9 读取 PE 指令，不存在配置好的 REA 原生深度分析提供者会话。输出是本机静态研究记录，不冒充 REA Evidence 对象，也不虚构 session ID。首选映像基址为 `0x140000000`；文中 VA 为静态地址，ASLR 后可能改变。

检索限于已有 25,272 条函数登记的名称筛选，以及被选入口的直接调用和元数据引用。候选包括 time controller、time/minute/hour/day、敌人保存加载、房间动态实体保存加载、地牢 seed/graph 和主保存加载入口。没有重新全游戏扫描指令、字符串或全部对象。新增解码 26 个登记入口，共 153,642 字节，给定范围全部可解码；其中部分与前轮重叠。**指令全部解码不等于所有分支语义、运行时辅助函数、异常片段或调用时序已经恢复。**

| 证据层级 | 本文怎样使用 |
| --- | --- |
| 指令与实参确认 | 读取字段、保存调用、冻结分支、PRNG 设定参数；只解释指定入口 |
| 静态调用确认 | 建立保存→自身数据、加载→创建/恢复、回合→时间更新等局部关系；不声称实际运行频率 |
| 资源确认 | 沿用预告技能、提示范围、表现对象的继承关系；不把对象存在当成持久化注册 |
| 既有快照确认 | 只引用前轮精简 `osbrook_smith` 字段；单个快照不能推出离屏算法 |
| 推断/未知 | 对象是否纳入具体保存集合、恢复时是否重建预告、所有返回路径的 seed 稳定性均保留未知 |

名称指针按缓存 ID 字段地址前 8 字节读取，避免把相邻登记误认作当前变量。运行时未初始化槽保持未解析，不把文件内初始零当成实际常量。布尔 false、undefined、对象哨兵与数值零依照[证据范围](00-evidence-and-scope.md)区分。

本机可选证据：[候选索引](../../../_reference/stoneshard-study/fourth-persistence-candidate-index.json)、[26 个入口的指令索引](../../../_reference/stoneshard-study/fourth-persistence-native.json)、[反汇编目录](../../../_reference/stoneshard-study/fourth-persistence-disassembly/)。这些不是克隆仓库必带的文件；下文保留必要地址、规则、例子和限制。

## 2. 预告攻击：保存角色状态不等于保存独立技能对象

### 已确认的保存与恢复入口

房间动态实体存在类型分派。`scr_locationRoomEntityScriptGetSaveDataGet` 的已编译分派包含 Mobs、Insects、Doors、Triggers、Corpses、Loot、Containers、Npc、Transitions、Stuff、Sights、Marks 等保存处理器。不能因列表中出现 `Marks` 就将所有范围提示归入该类型：类型登记、父对象和保存选择条件需要分别核对。

动态保存入口获取实例并查询该类型的保存处理器；动态加载入口查询创建处理器和数据恢复处理器。这支持“按类型重建实体”的结构，但哪些类型在某次主保存时被调用、哪些对象实际进入列表，仍不能从处理器登记独立推出。

| 局部关系 | 指令位置 |
| --- | --- |
| DynamicSave 查询 InstanceGet、SaveDataGet | `0x140b15d19`、`0x140b15dbb`，入口 `0x140b157e0` |
| DynamicLoad 查询 InstanceCreate、SaveDataSet | `0x14070c91c`、`0x14070c9b1`，入口 `0x14070c3c0` |
| 保存处理器分派到 Mobs / Npc / Marks | `0x1413defd3` / `0x1413df107` / `0x1413df1a2` |
| MobsSaveDataGet 调用 saveSelfData 并形成子 map | `0x1409fd5ec`，随后 `ds_map_add_map` 调用配置 `0x1409fd605` |
| MobsSaveDataSet 调用 loadSelfData | `0x141e46316`，入口 `0x141e45dc0` |

`saveSelfData` 读取并写入角色 `state`，还处理技能数据和 Buff。该入口的重要位置为：

| 已确认操作 | VA |
| --- | --- |
| 读取角色 `state`，随后调用 `ds_map_set` | `0x1406ac48e`、`0x1406ac4ed` |
| 调用 `saveSelfBuffs` | `0x1406ae416` |
| 读取 `skill_id_name`，遍历并查询技能 `data` | `0x1406ae516`、`0x1406ae692`、`0x1406ae731` |
| `loadSelfData` 有多个 `state` 写入及状态分支 | `0x1406b4c2e`、`0x1406b509d`、`0x1406b510b`、`0x1406b5255` 等 |
| `loadSelfData` 处理技能 `data`，并调用创建技能 map / 冷却设置入口 | `0x1406b62c7`、`0x1406b687c`、`0x1406b6a28` |

因此不能写成“战斗状态完全不保存”。同样不能写成“读档将所有战斗状态原样恢复”：加载器有额外分支，保存字段不直接等于恢复后的最终状态。这轮没有恢复 `state` 各加载分支的完整条件。

### 冲击波的具体例子

前轮确认 `o_shockwave` / `o_rock_toss` 继承多回合技能父对象，Create 写入 `skill_duration=2`。公共 `scr_global_turn_end` 针对该类执行倒计时和释放/取消；巨魔冲击波还创建独立范围提示对象，以 `main_owner` 区分归属。详见[预告攻击](13-telegraphed-attacks.md)。

这些状态至少属于不同层：

| 层 | 例子 | 本轮保存证据 |
| --- | --- | --- |
| 施法角色 | `state`、Buff、技能 `data` | 通用角色保存器有明确读取与写入 |
| 独立多回合技能实例 | `o_shockwave`、`skill_duration`、owner 等 | 尚未确认该实例进入哪个保存类型/集合 |
| 独立范围提示 | 提示对象、`main_owner` | 尚未确认保存及加载注册 |
| 飞行/视觉表现 | 投石 visual、动画进度 | 尚未确认持久化，不从动画入口推断读档行为 |

`MarksSaveDataGet` 确实读取 `duration`、`is_execute`，并按对象条件处理 `activation_duration`、target/owner 与 restore 字段。具体入口为 `0x141c7e6c0`，读取 `duration` 位于 `0x141c7e901`。这是“某类空间标记有保存器”的正证据，**不是冲击波提示已经被保存的证据**。这轮未闭合预告提示对象与该处理器选择集合的对应关系。

构造演算：令一个巨魔角色正处于准备攻击状态，独立冲击波实例的剩余倒计时为 1，并存在若干提示格。即使角色通过 Mobs 保存路径成功写入 `state`，也只得到角色侧的保存证据。缺少技能实例及提示的入选证据时，读档结果至少有三种待区分的可能：继续剩余倒计时、取消准备状态、根据角色状态重新构建技能与提示。当前静态证据不能从中选择一种。

局部规格应写为：

```text
被纳入 Mobs 保存集合的角色：
    形成位置、对象名和自身数据快照
    自身保存器包含 state、部分技能数据、Buff 等处理

读入该类型快照：
    选择实体创建处理器
    选择数据恢复处理器
    恢复器执行自己的状态与附加分支

独立预告技能 / 提示 / 飞行对象：
    是否纳入保存集合：未知
    是否由恢复分支重建：未知
```

要进一步回答保存中途退出的行为，最小补查是恢复这几个具体对象的 `roomEntityType` 与 InstanceGet 入选条件，再追相关状态的加载分支；不需要扩大到所有技能。当前没有运行“准备攻击→保存→退出→读档”的实验。

## 3. NPC 作息、跟随与听觉使用不同的时间边界

### 回合会调用游戏时间更新，但有冻结门控

`scr_global_turn` 在 `0x1416c391f` 调用 `scr_timeIsFrozen`，通过真值助手检查返回值。返回真时 `0x1416c392e` 跳到 `0x1416c3afc`，跳过这一段 `scr_timeUpdate` 和 `scr_characterTimeUpdate` 调用。返回假时会执行：

```text
公共回合入口中已确认的一段：
    frozen = timeIsFrozen()
    如果 frozen 为假：
        timeUpdate(30, undefined, undefined, undefined, undefined)
        characterTimeUpdate(undefined)
    继续该公共回合入口的其他处理
```

常量 30 的实参构造位于 `0x1416c3995`；5 参数调用位于 `0x1416c3a4d`；角色时间更新调用位于 `0x1416c3af7`。本轮不将 30 写成现实秒、游戏分钟或固定“一次玩家输入”的长度。`timeUpdate` 同时读取 `timeDataMap` 和 `timeScale`，并有可选参数及运算；尚未恢复它们的完整单位契约和所有调用点。

`timeIsFrozen` 并非只按函数名作结论：其入口 `0x1415c71c0` 有任务状态、`time_frozen_until` 与时间戳比较等控制流。本文只使用公共回合中的真假门控，不把冻结规则泛化为“暂停时所有 AI 和所有倒计时均停止”。

`timeUpdate` 的这条可达路径调用 `timePartsUpdate`（`0x14199a8f9`）。后者存在分钟、小时、日、月更新及对应触发调用：

| 触发入口 | 调用 VA |
| --- | --- |
| `scr_timeEveryMinuteTrigger` | `0x14199bc9b` |
| `scr_timeEveryHourTrigger` | `0x14199c014` |
| `scr_timeEveryDayTrigger` | `0x14199c38d` |
| `scr_timeEveryMonthTrigger` | `0x14199c712` |

这些是游戏逻辑时间组成部分，不是 Windows 系统时钟的回调证明。触发次数、是否补发跳过的每个小时、睡眠快进是否另走入口，尚未完整恢复。

### 作息读取小时，跟随还需要实体行为机会

作息已确认读取 `timeDataMap["hours"]`，按 6、12、19、23 分成四段。`o_time_controller.Other14` 入口 `0x1438d9a20`；`hours` 常量初始化前轮已核对于 `0x1438da554`。铁匠对象继承通用 standing NPC 配置，但覆写晨间/日间工作回调，夜间选择睡眠行为；目标格和前置条件见[作息与睡眠](06-npc-schedule-sleep.md)。

构造演算：令游戏小时从 18 变为 19。在四段分类器里，结果由日间段变为晚间段。这个计算不依赖电脑实际时间是否 19 点，也不证明铁匠立刻完成移动或入睡。若公共回合的时间冻结门控返回真，上述 `timeUpdate` 路径被跳过；但不能据此推出所有其他更新时间入口也被跳过。

人质 `following/waiting` 是行为状态与持久信息，不是独立“每小时移动一次”的规则。前轮确认开始/停止对话将状态写入全局键 `hostage_substate`；FSM 读取 `substate` 并进入 following 分支，其中检查 `lock_turn`、周围目标格和其他条件。关键读取/消费位置为 `0x141786162`、`0x1417878a0`、`0x141787966`、`0x14178798b`。已确认 `scr_turn_npc` 处理已加载实例的移动/路径基础设施，但不能仅凭其名字宣称每个 NPC 在每次玩家输入都行动。

构造演算：人质状态保持 following，而该次 FSM 消费中门禁阻止继续选格。这与 following 被改成 waiting 是不同状态；持久状态保持 following 不保证已经移动。同样，保存中有 following 也不证明卸载房间后有实体逐格追随。

### 听觉包含事件标记消费和接收器清理

前轮感知分析确认噪声事件能设置 `is_noise_hearing` 及相关来源/坐标信息；`scr_enemy_noise_hearing_check` 读取该标记并清除一次性标记，入口 `0x1405d3310`，字段访问 `0x1405d338a` / `0x1405d33bb`。其消费粒度取决于消费者被调用的时机，不按函数名转化成秒数。

本轮新增 `scr_global_turn` 末段调用 `scr_noise_receiver_global_clear`（`0x1416c56b8`）。清理器入口 `0x141ce3540` 的明确局部条件是：

```text
对被选噪声接收器：
    如果 owner 的直接存在检查为假：
        如果 instanceExistsCulled(owner) 也为假：
            销毁这个接收器
```

owner 读取位于 `0x141ce365b`；两次存在性检查位于 `0x141ce3691` / `0x141ce36f4`；两者均不满足后调用销毁助手 `0x1451f70d0`，调用点 `0x141ce371a`。这不是“每回合清空所有接收器”或“清空所有 NPC 听觉标记”。噪声选择器常量的具体父对象解释未在本轮闭合。

构造演算：接收器 A 的 owner 在直接存在检查中仍存在，控制流跳过销毁；接收器 B 的 owner 两次检查都为假，进入销毁。两者不涉及指定现实时间长度。接收器 owner 被裁剪时的全部身份规则，以及噪声 duration 的所有消费入口，尚不能由这个局部清理器推出。

### 既有铁匠快照只证明状态被持久保存

沿用前轮精简观察：`globalmapDataMap.locationsDataMap["32_10"].npc_data["osbrook_smith"]` 含 `state="idle"`、`current_day=0`、`sprite_name="s_blacksmith_01"`，并存在 `current_time`、`new_room_turns`、`restock_timestamp`、`gold_restock_timestamp` 等键。来源 SHA256 与精简范围见[NPC 持久化](07-npc-persistence-following.md)。本轮只读取该研究摘要，没有再次打开原存档。

这证明长期身份有时间相关数据，不证明离屏更新采用逐回合模拟、事件更新还是返回时补算。构造“玩家离开 8 小时后返回”，当前不能计算铁匠离屏走了几步、工作多久或补货几次；不同快照的进度差异也不能填补这个缺口。

## 4. 地牢 seed、房间图和动态快照是三层不同问题

### 楼层 seed 确实进入随机数发生器

`scr_dungeonFloorSeedSet` 入口 `0x140f2c9a0` 从当前实例读取 `floorSeed`（`0x140f2ca91`），将该值作为唯一实参送入 `random_set_seed`。内建函数登记读取位于 `0x140f2cab3`，实参调用位于 `0x140f2cad6`。之后还调用 `random_get_seed` 形成调试输出。

```text
楼层随机起点设定入口：
    seed = 当前上下文.floorSeed
    random_set_seed(seed)
    读取 random_get_seed() 并用于调试输出
```

这是明确的 PRNG 设定证据，强于只有 `seed` 函数名。它不包含 PRNG 算法、所有随机抽样顺序、平台间一致性或每个返回/读档场景一定经过该入口的证明。

`scr_dungeonFloorSeedGenerate` 读取当前楼层编号、全局地牢数据，操作 `floorSeed` / `floorSeedArray`，可调用写入全局地图入口，最终有 `FloorSeedSet` 调用。具体位置：

| 操作 | VA |
| --- | --- |
| 获取当前楼层编号 | `0x1400043bf` |
| 查询全局地牢数据 | `0x14000451c`、`0x140004b9f` |
| 读取/操作 floorSeed、floorSeedArray | `0x1400045d2`、`0x14000464e` 等 |
| 调用 WriteSeedInGlobalmap | `0x140004a54` |
| 调用 FloorSeedSet | `0x140004ca9` |
| WriteSeedInGlobalmap 调用 globaltile_dungeon_set | `0x141de297b`，入口 `0x141de21d0` |

该入口包含字符串拆分、数值转换和条件路径，但本轮不将这些未完整恢复的细节拼成 seed 派生公式，也不猜测 separator、hash 函数或新旧 seed 的全部优先级。

### 地牢房间图另有保存和加载处理器

`scr_dungeonSaveGraph` 入口 `0x140888a50` 查询可保存 graph，再遍历 `floorGraph` 并创建 map。已经核对的字段引用包括房间/节点的 `Name`、`X`、`Y`、`Id` 和 `ActiveConnector` 等。这里只报告被访问字段，尚未把整个图的序列化格式全部恢复。

`scr_dungeonLoadGraph` 入口 `0x141b418a0` 有清理 map、按房间名查资源、解析房间、解析连接、创建房间节点的直接调用：

| 局部关系 | VA |
| --- | --- |
| SaveGraph → GetSaveGraph | `0x140888fa6` |
| SaveGraph 读取 floorGraph | `0x14088906c` |
| SaveGraph 访问 Name / X / Y / Id / ActiveConnector | `0x1408899be` / `0x140889b41` / `0x140889cc2` / `0x140889e45` / `0x14088a0e5` |
| LoadGraph 清理 map | `0x141b42156` |
| LoadGraph → GetRoomStructByName / StartParsingRoom | `0x141b424fe` / `0x141b42991` |
| LoadGraph → ConnectsParser / CreateRoomNode | `0x141b4300d`、`0x141b4310d` / `0x141b43688` |

这些正证据支持“房间图有恢复处理器”。结合前文动态实体创建/恢复处理器，可以区分三个层：

| 层 | 已确认入口 | 不能直接推出 |
| --- | --- | --- |
| 随机起点 | floorSeed → random_set_seed | 所有随机对象/抽样顺序都相同 |
| 房间结构 | SaveGraph / LoadGraph、房间与连接解析 | 所有地牢返回都使用同一张图且永不重置 |
| 动态实体 | DynamicSave / DynamicLoad、类型处理器 | 所有实体和临时技能都进入保存集合 |

### 同一 seed 的构造演算与稳定性边界

构造当前楼层 `floorSeed=12345`，资源和其他输入保持一致。进入已确认 Set 入口时，会把 12345 送入 `random_set_seed`。这一步能重置随机起点。若后续算法和随机调用顺序也相同，则可作为可重复生成的设计条件；后半句是一般性的条件推断，不是本游戏全部场景已证实的行为。

再构造“第二次访问时先恢复保存的房间图和动态实体”。即使随机起点相同，房间状态仍可能包含已经死亡的敌人、已开门等快照差异；这些不能只用 seed 解释。反之，若进入的是地牢重置或另一张图的生成路径，同一入口存在也不能保证它一定采用上次 seed。

目前未闭合：主保存/读档与房间离开/返回的全部派发顺序；已保存 graph 与重新生成的选择条件；seed 清除/地牢重置条件；PRNG 内部状态是否另外持久化；全部随机调用顺序；版本变化后旧 graph/seed 的兼容规则。不能宣称“一旦生成，返回与读档永远稳定”或“每次进入都重新随机”。

## 5. 独立设计借鉴与未做的验证

以下是供我们自研产品采用的设计方案，不是已证实的 Stoneshard 原实现：

- 为预告攻击明确规定存档契约：保存可恢复的攻击描述（施法者稳定 ID、技能种类、剩余逻辑回合、目标规格），提示由描述重新构建；或者明确取消准备状态并恢复安全动作。两种方案都应避免保存悬空实例 ID。
- 将日程时钟、行动机会、动画 alarm 和噪声事件寿命分别命名并定义单位。冻结日程时间是否同时冻结行动/听觉需要产品决策，不能让一个模糊 timer 隐含决定。
- 离屏 NPC 可以采用返回时补算，但需保存最后更新时间、当前任务和稳定身份，并明确补算事件上限。这是可选自研方案，不是从 `current_time` 推出来的游戏事实。
- 分开保存生成版本与 seed、结构 graph 和动态变化；使用稳定 ID 恢复实体关联。为“读档前后预告一致”“同一生成输入结构一致”“快进跨时段”建立行为测试。

已做的是局部静态指令、参数、资源/既有摘要与文档链接核对。没有执行运行测试，也没有添加 REA 代码测试：本轮只写研究文档，未改工具或生产行为。

剩余风险是将“存在保存器”扩大为“所有对象必然保存”，将“时间字段”扩大为“完整离屏模拟”，以及将“设定 seed”扩大为“所有读档/返回结果完全一致”。本文保留这些未知。后续最小验证分别是针对巨魔准备中的读档、离屏铁匠跨时间段返回、同一地牢层的离开/返回与存档重载进行受控观察；本轮没有实施，也没有把构造演算当成运行结果。
