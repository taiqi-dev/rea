# Tiny Glade：快照后的 system 入口、运行门与消息可见性

续查 [101：seed 数组及快照候选](101-tiny-glade-seed-array-and-snapshot-scheduling.md)留下的调度缺口。本文只回答快照恢复怎样到达系统入口、两个包装器实际是什么、`OnWallChanged` 的读写何时**可能**相遇，以及哪一层 deferred 尚不能确认。阶段图骨架见 [55](55-tiny-glade-edit-rebuild-stages-and-upload.md)，快照/历史状态见 [62](62-tiny-glade-history-snapshots-and-regeneration.md)。

## 身份、方法和边界

目标为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B）与相邻 `tiny_glade.pdb`（310,513,664 B）；沿用已核 RSDS GUID `d8d61d04-9e31-5b47-4c4c-44205044422e`、age 1，没有重算摘要。本文十六进制地址均为 RVA，首选 VA 为 RVA + `0x140000000`。`dumpbin 14.44.35222.0` 只读反汇编和本仓 PDB 探针提供的是**普通 PE/PDB 静态证据**，不是 REA Evidence，也不是目标运行观察。新原始输出留在本机忽略目录 `.cache/procedural-modeling/static-scheduler-followup/tiny-glade/`；精确 RVA 符号查询工具为 [pdb_address_probe.py](tiny-glade/tools/pdb_address_probe.py)。先前 REA native Ghidra timeout 状态未变，本轮没有重试。

## 三个入口属于不同调用层

| 入口                | 已核实的调用                                                                                                   | 静态解释与限制                                                                                                                                                                                                                                      |
| ------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `19274FA`           | `load_game` (`1924120`) 直接调用 `init_game_state_from_snapshot` (`1BF3100`)                                   | `19272F6–1927300` 先检查一个局部 `+0x208` 值，零则跳到 `19274AE`；`192733A–192734A` 还遍历一组条目，未找到时同样跳过调用。条目和资格原名未恢复。`load_game` 自身另有 `run_without_applying_deferred` (`189B4A0`) 与 `run_unsafe` (`1A48860`) 包装。 |
| `1E440C` / `5C2B57` | `run_without_applying_deferred` (`1E3AE0`) / `run_unsafe` (`5C2260`) 各调用 `B9F450 publish_public_wall_state` | 同一业务函数有两个包装入口；静态调用位置不等于运行次数。类型参数包含 `ResMut<InnerWalls>`、`ResMut<PublicWalls>`、`MessageWriter<OnWallChanged>` 等，但没有 `Commands` 参数。                                                                       |
| `1C4830` / `67BDB9` | `run_without_applying_deferred` (`1C3900`) / `run_unsafe` (`67AEB0`) 各调用 `808800 construct_walls`           | 类型参数包含 `MessageReader<OnWallChanged>`、`Res<PublicWalls>` 和 `Commands`。这一层的 `Commands` 属于构造器的后续世界修改，不能代替其消息读取资格。                                                                                               |

PDB 地址查询对各 RVA 给出**落在符号 size 范围内**的结果；`dumpbin` 又复核了上述 `call` 指令边界。PDB 的很长泛型名在 DbgHelp 返回中含无效尾段，工具在首个 NUL 截断；这里只使用可读的类型前缀和独立指令，不从损坏尾段推断参数。旧 `pdb_probe.py` 对广泛 `publish_public_wall_state` 枚举因 surrogate UTF-8 写出失败，新精确地址探针避免了该输出；失败记录与首次 `SymFromAddrW` 未解析尝试保留在新 raw 目录，不算成功证据。

两个外层包装器的入口各先调用一段参数准备代码（Public `1E3AFC→1A4770`；砖 `1C391C→1AA460`），再比较返回槽与 `0x8000000000000001`（`1E3B13–1E3B1B`、`1C3933–1C393B`）。之后仍有 world 表索引、资源存在和状态字段检查，成功路径才组装业务函数参数。这里核实的是**系统参数可用/获取门**，不是 user-level `run_if` 的真假表；这些失败分支的所有含义也尚未逐一命名。快照所在 `load_game` 的包装参数可读出 `AppMode`、`LoadGameManager`、`ActiveSession`、`NextState<AppLoadingState>`、`Commands` 和 `SnapshotLoadResources`，只能说明可能读写的类型，不能由参数名断言“加载态每帧执行”。

## 资源写入、消息写入与 deferred 是三件事

快照函数经 `B0DA60 InnerWalls.load_state`，把恢复的 WallId 直接写进 `InnerWalls+0x30` 创建候选集合；Public 函数读取该集合和 `+0x60` dirty 集合，选中候选后才发消息，详见 [101](101-tiny-glade-seed-array-and-snapshot-scheduling.md)。这是普通资源内存路径；现有证据未见这条 `+0x30` 写入通过 `Commands` 延后。

Public 选中墙时，`BA090A` 先检查消息 Vec 容量，必要时增长；`BA0925–BA094E` 对 16 B 消息记录写两个 qword，增加该缓冲长度 `+0x30` 和总计数 `+0x40`。这是 `MessageWriter<OnWallChanged>` 对消息资源的实际写端，不能把它解释成 ECS `Commands` 队列。随后 Public 还会处理旧 Public 状态和新状态；消息存在本身不保证消费者查得到有效墙。

砖构造器 `808B4D–808C02` 从 `MessageReader<OnWallChanged>` 持有的游标和消息资源计算两段缓冲各自的未读起点/长度，再调用专门 `FC81A0` 收集 WallId。`808BB9` 和 `808C6C` 更新读游标；`808D05` 随后查当前 `PublicWalls.get`，缺失则跳过。故如果两个系统确实在同一消息维护周期内按 Public→砖的次序执行，且该读游标尚未越过新消息，**消息这一路**无需等待砖系统的 `Commands` flush 才有被读取的可能。这里未恢复消息缓冲轮换/清理相对两系统的实际位置，不承诺跨帧保留多久。

`run_without_applying_deferred` 是两个外层包装器的真实符号；这证明该入口本身不承诺应用各系统的 deferred。Public 包装没有 `Commands` 参数，砖包装有。前者向消息资源直接写入，与后者排队的实体/组件命令是不同可见性问题。现有静态范围**没有**把某个 `ApplyDeferred` 节点、executor flush 或 system buffer 参数连到这两个具体 system 之后；也未证明砖构造器输出的实体修改在下一系统前生效。

## 阶段图与条件演算

[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)已核 `93E620 add_stages → C97EF0 → 1A12250 → 1A0C5B0 process_configs → 17C65A0 add_edge`，从 raw 0..44 的相邻配置生成有向阶段约束。相关标签有 `WallGenerators=0x13`、`WallVisualGenerators=0x1C`、`ReplaySystems=0x28`、`ReplaySystemsCleanup=0x29`。本轮没有恢复 `load_game`、Public、砖三个**具体 system**各自的 `in_set`/`run_if` 注册记录，也没有恢复 executor 对条件、系统和 `ApplyDeferred` 的实际遍历。因此“标签顺序”不能升级成这三个 system 同帧执行顺序。

下面是**构造的条件演算**，不是游戏运行记录。设快照恢复 WallId 7 且 `+0x30={7}`，Public 主 map 最终允许其派生，新消息缓冲开始计数为 0，砖 reader 游标为 0。令 `L` 表示 `load_game` 内 `+0x208`/条目检查通过，`P`、`C` 表示尚未命名的 Public 与砖系统外部运行条件通过：

1. `L=0`：`1927300/192733D` 跳过快照调用，不能由本入口声称 WallId 7 已恢复。
2. `L=1,P=0`：快照可以写 `+0x30={7}`；Public 未执行，不会由本次 Public 调用写 `OnWallChanged`。若资源随后被其他路径重置，这个集合能保持多久仍未知。
3. `L=1,P=1,C=1`，再**额外假设**执行次序为快照→Public→砖、无消息轮换夹在 Public 和砖之间且 WallId 7 通过 Public 资格：Public 写一条 16 B 消息，长度和总计数由 0 变 1；砖读取器以游标 0 计算当前段未读长 1，`FC81A0` 可产生 ID 7，之后还必须通过 `PublicWalls.get` 和墙洞筛选。若次序改为砖先于 Public，本次砖读取看到的新增条数为 0；后一次是否读到取决于维护点和游标，现证据不能保证。

这个演算把实际分支与额外假设分开：`L` 有原始偏移证据；`P/C` 的具体谓词和三个 system 的相对 schedule 归属未命名，因此只是必要条件变量，不是已恢复的原游戏配置。

## 结论与可续入口

已答：快照调用属于 `load_game` 的条件分支；Public/砖的两级包装身份与参数门；`OnWallChanged` 的直接消息写端、双段 reader 读端；两个外层包装均不自行承诺应用 deferred。部分回答：有条件的消息可见性。未答：三系统的精确 `in_set` 与 `run_if`、初始化/Update 分界、executor 的 `ApplyDeferred` 插入与 flush 次序、同帧墙重建、GPU 完成。PDB/PE 静态检查通过；目标启动、附加、原函数/GPU执行、私人存档和项目构建均 `Not Run`。

下一步最有价值的两处静态入口：① 从 Public `1E3AE0`、砖 `1C3900` 和 load `189B4A0` 的 system 注册对象反查 `in_set`/`run_if` 及所属 schedule，给阶段图加**具体节点**；② 从该 schedule 的 executor 追 `ApplyDeferred`/消息维护调用到两个 system 节点之间，区分 `Commands` flush 与 `Messages<OnWallChanged>` 轮换。完成这两条之前不应写“同帧屏障已证实”。
