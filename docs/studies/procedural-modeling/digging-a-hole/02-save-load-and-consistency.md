# 掘地求财：体素保存、载入与一致性边界

## 范围与证据身份

本页研究 `C:\Software\Steam\steamapps\common\A Game About Digging A Hole\DiggingGame\Binaries\Win64\DiggingGame-Win64-Shipping.exe`（PE32+ x64，145,180,160 字节，同目录同名 PDB 1,659,662,336 字节）及同一次安装所载 cooked Blueprint 的**静态路径**。使用仓库 `tools/pdb_probe.py` 将本地 PDB 符号定位到映像基址 `0x140000000`，再用 VS 2022 `dumpbin 14.44.35222.0 /DISASM /RANGE` 有界读取指令；符号查询的 `queries.exhausted` 均为 `true`。Blueprint 使用仓库 `tools/zen_probe.py` 和本研究的 [blueprint_probe.py](tools/blueprint_probe.py) 解析。下文 native 地址均为 EXE VA；Blueprint `文件偏移` 均从解出的 `.uasset` 文件起算，`逻辑偏移` 为 Unreal Kismet code offset。原始记录在本机忽略目录 [save/](../../../../.cache/procedural-modeling/digging-a-hole/save/)；不会随文档跨机器同步。没有启动或附加游戏，没有读取玩家存档，也没有实测保存文件。

角色 `ExecuteUbergraph` 的 167,815 个序列化字节、115,747 个逻辑代码字节，以及 `BP_OreSpawner` 事件图的 129,075 个序列化字节、88,931 个逻辑代码字节，均已逐表达式解析至 `EX_EndOfScript`，与导出记录一致；`VoxelComplexController_SaveExample` 的 `Save`、`Load` 同样完整覆盖。原始解析结果为 `character-ubergraph.json`、`ores-ubergraph.json`、`saveexample-save.json`、`saveexample-load.json`。以下区分蓝图实际调用、native 函数实现和仍需运行时证据的结果。

## 游戏实际蓝图：slot、快照与恢复

角色在逻辑偏移 `114812`、`114890`（文件偏移 `387754`、`387844`）分别执行 `RegisterSaveQueue("Main", SavegameCooldown, true)` 和 `RegisterSaveQueue("Achievements", SavegameCooldown, true)`。逻辑 `43421`/文件 `285707` 将角色函数 `SaveGame` 绑定为 delegate，逻辑 `43466`/文件 `285764` 将该 delegate 订阅到 `Main` 队列。`SaveGame` 的短函数代码把执行引入角色事件图逻辑 `114957`，该入口 `Jump` 到 `62120`。可见 `shouldSaveAsync` 是回调签名中的参数，但本次完整事件图未发现对同名变量的读取；主 slot 采取如下固定蓝图路径，不能只按队列布尔值推测压缩线程。

逻辑 `62201`/文件 `313663` 执行 `CreateSaveGameObject`，返回对象赋给 `RefMainSave`；`62239` 跳至 `61934`，先 `GetAllActorsOfClass(VoxelWorld)`，取第一个世界对象，逻辑 `62051`/文件 `313501` 调 `RefMainSave.Save(VoxelWorld)`，逻辑 `62096`/文件 `313558` 调 `RefOreSpawner.SaveOres(RefMainSave)`。这说明体素与矿物状态先进入同一 `USaveGame` 对象。类身份不是只凭函数同名猜测：`CreateSaveGameObject` 的类索引 `-23` 与两次从 `MainSave` slot 载入后的 DynamicCast 类索引相同；后者的变量名为 `AsVoxel_Complex_Controller_Save_Example`。Zen import `-23` 的 imported package index 50 指向 `/Voxel/Examples/ComplexController/VoxelComplexController_SaveExample`，public export hash index 20 的原包存储值 `0x969909e9b01f3f92` 又与该包 Class 导出的原包存储值完全相同（`save-class-link.json`）；这是包中标识的对照，没有重新计算内容摘要。

该 SaveGame 类的 `Save` 导出完整代码在文件偏移 `8534` 直接调用 **同步** `UVoxelDataTools::GetCompressedSave(Voxel World, OutSave)`，随后把 `OutSave` 赋给成员 `VoxelWorldSave`（逻辑 `24`/文件 `8574`）；逻辑 `73`/文件 `8659` 又调用 `GetSpawnersSave`，把返回值赋给成员 `SpawnerSave`（逻辑 `88`/文件 `8682`）。因此游戏主存档确实保存**压缩的体素数据**和 spawner 数据，插件同步快照与 zlib 压缩位于 `RefMainSave.Save` 调用栈上。它们先于后续 slot API；即使后续写盘异步，也不能据此声称抓取/压缩已离开当前蓝图执行线程。具体帧阻塞时长未测量。

从 `RefOreSpawner.SaveOres(RefMainSave)` 到写盘的跨 Blueprint 边也已定位。`BP_OreSpawner.SaveOres` 小函数跳入自身事件图逻辑 `82528`/文件 `216619`，检查传入的 `RefMainSave`，清空并重新收集矿物、道具等位置数组；逻辑 `87421` 跳入逐类遍历链，最后一次数组遍历的逻辑 `74904` 走到 `75224`，逻辑 `75325`/文件 `206036` 调角色 `ContinuePlayerSave`，传入石、煤、铁、贵金属、宝石及道具的 23 类位置数组与 `MineSeed`。角色 `ContinuePlayerSave` 小函数跳到角色事件图逻辑 `76415`，把这些数组写入 `RefMainSave`，逻辑 `77542` 跳 `74469`，继续写入库存、金钱、升级和进度字段。逻辑 `74181` 后检查/创建 `ACHSave` 对象，逻辑 `74361`/文件 `330891` 执行 `Delay(0.1)`；该调用的 `LatentActionInfo` 中 `Linkage=26802`（文件 `330911`），将执行续接到角色图逻辑 `26802`。续接后复制成就字段，逻辑 `27329`/文件 `262139` **同步**调用 `SaveGameToSlot(Ref_SF_Achievements, "ACHSave", 0)`；逻辑 `27523`/文件 `262341` 更新主档时间戳，逻辑 `27582`/文件 `262448` 调 `AsyncSaveGameToSlot(RefMainSave, "MainSave", 0)`，随后绑定完成事件并 `Activate`（逻辑 `27656`—`27720`）。这证明两条 slot 调用确实处于同一次保存链中；0.1 秒 latent 续接与各 slot 返回/完成之间没有静态事务保证。本次没有观察到磁盘上最后的文件内容。

主 slot 的 `Completed` delegate 在逻辑 `27656`/文件 `262546` 绑定 `Completed_3B020A9D43A7982BB1F8C490C974BBDA`，其导出函数跳到事件图逻辑 `63313`。回调把 `bSuccess` 赋给临时布尔变量（逻辑 `63332`），随即**无条件**跳到逻辑 `62299`，取得 `CloudSaveSubsystem` 并调用 `WriteSaveToCloud`（逻辑 `62351`）。完整角色图中没有该 `bSuccess` 或临时布尔值的后续读取，也未见此回调中按失败重试或阻止云调用的分支。这是角色蓝图完成回调的静态事实，不能推断云子系统内部如何处理失败，也不能证明云副本确已存在。

角色载入主 slot 的逻辑 `16`/文件 `221350` 先查 `DoesSaveGameExist("MainSave", 0)`，逻辑 `65`/文件 `221411` 读 `LoadGameFromSlot`，并以同一类索引 `-23` 作类型转换；逻辑 `179` 检查 `DeletedForNewGame`。满足条件后再次 `LoadGameFromSlot`（逻辑 `244`），把转换结果赋给 `RefMainSave`，取第一个 `VoxelWorld`，逻辑 `468`/文件 `221962` 调 `RefMainSave.Load(VoxelWorld)`。该 `Load` 导出在文件偏移 `8141` 调 `LoadFromCompressedSave(Voxel World, VoxelWorldSave)`，根据其布尔返回值跳转；成功时文件 `8203` 调 `LoadFromSpawnersSave(Voxel World, SpawnerSave)`，失败时文件 `8248` 只调 `PrintString("Failed to load voxel world voxel data")`。这条外层分支没有显示回滚已经更动的体素数据；屏幕提示是否对玩家可见以及损坏存档时真实表现未经运行验证。

## 已定位的 native 路径

### 游戏自身：保存请求的时序

`USaveSubsystem::RegisterSaveQueue` (`0x1445EF6C0`) 接收 `queueName`、`cooldown` 和 `shouldSaveAsync`，为该队列准备 `OnSaveTimerFinished` 的定时回调。首次注册时，函数还把 `OnAppStatusChangeSaveRequested` 绑定到进入后台、失活和应用终止通知（`0x1445EF891`—`0x1445EF8C9`）。`ConfigureAutosave` (`0x1445EE970`) 配置一个自动保存计时器；`OnAutosaveTriggered` (`0x1445EEEC0`) 遍历已注册队列并调用 `QueueSaveRequest` (`0x1445EF08D`)。

角色蓝图配置自动保存时，逻辑 `43374`/文件 `285664` 传 `(true, 300.0)`，逻辑 `43586`/文件 `285916` 再按 `RefOptionsSave.AutosaveEnabled` 传 `(该布尔值, 300.0)`。native `ConfigureAutosave` 把这段间隔原值送进循环 `FTimerManager::InternalSetTimer`，而 [Epic `SetTimer` 文档](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/FTimerManager/SetTimer) 将 `InRate` 定义为秒。因此这条配置路径是 300 秒循环；它不证明实际运行每五分钟必成功写盘。

`QueueSaveRequest` (`0x1445EF3C0`) 先按名称查已注册队列，清除其当前请求标志并执行 `FSaveQueueRequestCallback::ExecuteIfBound` (`0x1445EF477`)，随后按 cooldown 重设队列定时器。若仍在 cooldown，指令在剩余时间大于零时设待处理标志 (`0x1445EF659`—`0x1445EF699`)；`OnSaveTimerFinished` (`0x1445EF0D0`) 执行该队列回调并重新安排计时。这里的 `shouldSaveAsync` 是传给回调的布尔值；角色蓝图的主 slot 路径已在上节实际确认。以上队列 native 函数本身不做体素序列化或文件写入。

应用状态通知路径在遍历队列时直接把各队列的 `shouldSaveAsync` 值传给回调 (`0x1445EEE5E`—`0x1445EEE66`)；所见指令没有等待异步写盘完成。因此“收到终止通知”本身不能作为崩溃或系统强制结束后存档已持久化的保证。

角色蓝图在逻辑 `62351`/文件 `313817` 也调用 `UCloudSaveSubsystem::WriteSaveToCloud("../../../DiggingGame/Saved/SaveGames/MainSave.sav", RefMainSave)`；此调用存在，但当前证据未追完该子系统的真实上传/复制、完成条件和冲突策略，不能把它视为可靠第二副本。`LoadSaveFromCloud` 的 native 包装很短 (`0x1445EC4B0`)，也不足以确立完整恢复路径。

### 引擎 slot：对象序列化与写盘

`UGameplayStatics::SaveGameToSlot` (`0x143621100`) 在 `0x143621126` 先调用 `SaveGameToMemory`，然后通过平台 `ISaveGameSystem` 虚表 `+0x28` 写入。`AsyncSaveGameToSlot` (`0x143600360`) 同样先在 `0x143600421` **同步**调用 `SaveGameToMemory`，在 `0x14360044F` 取已取得的保存系统虚表 `+0x48` 函数指针，并于 `0x1436004D2` 派发后续异步工作。因此主 slot 的异步 API 不能免去此前在蓝图中同步进行的体素快照/压缩，也不能免去 `USaveGame` 对象转内存字节的同步阶段。

引擎默认保存系统的静态对象 `0x148216520` 指向 vtable `0x14706CF18`，其中 `+0x28` 为 `FGenericSaveGameSystem::SaveGame` (`0x143A0F220`)，`+0x48` 为 `ISaveGameSystem::SaveGameAsync` (`0x143AF39E0`)。默认 `SaveGame` 在 `0x143A0F290` 调用 `FFileHelper::SaveArrayToFile`，`WriteFlags=0`；该 helper (`0x141122830`) 经 FileManager 虚表 `+0x20` 建 writer，写入数组、关闭并检查错误标志。本次所追默认路径没有发现“写临时文件并替换原文件”的事务步骤。Windows 平台的选择器 `0x143DBF0B0` 先检查 `[PlatformFeatures] SaveGameSystemModule` 并尝试自定义 provider；缺失或失败才回退默认系统。本次读到的 DefaultEngine/WindowsEngine 配置未含该键，但未覆盖所有配置层和运行时状态，所以**不能断言当前游戏一定选默认 writer**，更不能据此断言一次中断必然坏档。原始有界反汇编和 vtable 读取在 `.cache/procedural-modeling/digging-a-hole/disk/`。

### Voxel 插件：数据快照与压缩

`UVoxelDataTools::GetCompressedSave` (`0x1441951C0`) 在世界有效时调用 `FVoxelData::GetSave` (`0x143E79880`)，之后调用 `UVoxelSaveUtilities::CompressVoxelSave` (`0x143E659A0`)。`FVoxelData::GetSave` 先对 `FVoxelIntBox::Infinite` 调 `FVoxelData::Lock` (`0x143E798E7`)，遍历八叉树叶子及 placeable items，再交给 `FVoxelSaveBuilder::Save` (`0x143E79B07`)；尾部调用 `Unlock` (`0x143E79C97`)。因此插件快照对体素数据持有覆盖全域的锁，写入不能与这段读取任意交错；这只说明插件内部数据层的排他边界，不说明游戏文件写入已原子化。

插件也实现 `GetCompressedSaveAsync` (`0x1441953E0`)：它创建 Voxel latent action；其工作 lambda (`0x143EFBC90`) 依次调用 `FVoxelData::GetSave` (`0x143EFBD05`) 和 `CompressVoxelSave` (`0x143EFBD19`)。这证明若调用该异步入口，快照与压缩属于异步工作内容；全域锁仍在快照期存在。本次角色实际主存档链进入的是同步 `GetCompressedSave`，不是此异步入口。

`FVoxelSaveBuilder::Save` (`0x143E8B860`) 对叶子的 value/material 已修改状态分别计数、分配并复制。计数乘以 `0x1000`（4,096）形成单叶子值/材质数组容量 (`0x143E8B9B0`、`0x143E8BA23`)，同时保存块元数据和 placeable items (`0x143E8BF47`—`0x143E8C029`)。这更符合**稀疏保存被改动的叶块和额外对象**，不是把每次挖掘当操作日志顺序重放，也没有在这个保存对象中观察到三角形 mesh。它不意味着整个世界每次只增量写入磁盘：`GetSave` 每次会重新遍历数据树并构造新的世界保存对象。`FVoxelUncompressedWorldSaveImpl::Serialize` (`0x143E8E360`) 包含版本/Guid、values、materials、chunk 数组和旧格式分支；`FVoxelCompressedWorldSaveImpl::Serialize` (`0x143E8DF50`) 包含压缩字节数组。**逻辑数据与派生渲染网格分开**是该序列化路径的静态结论；完整的游戏 slot 字段还需蓝图/存档证据。

`CompressVoxelSave` 用 `FLargeMemoryWriter` 先序列化未压缩世界保存对象，再调用 `FVoxelSerializationUtilities::CompressData` (`0x143E659C7`—`0x143E659F4`)。后者在 `0x143ED4DAB` 实际调用 zlib `compress2`，压缩级别的默认值从 `UVoxelSettings` 读取并钳到 `-1..9` (`0x143ED4B9A`—`0x143ED4BD4`)。它按输入长度分段后压缩到一个带头部的字节数组，解压侧用 `0xDEADBEEF` 标识和大小、段数边界判断，调用 `uncompress` (`0x143EDA31D`、`0x143EDA35D`、`0x143EDA42C`)。分段是压缩传输边界，不能与体素叶块或逐块持久化混为一谈。静态路径未量到压缩比、保存耗时或峰值内存；同时存在未压缩对象、写入缓冲和压缩输出的阶段，适合实际压测。

### Voxel 插件：载入与重建

`UVoxelDataTools::LoadFromCompressedSave` (`0x1441A3D20`) 在世界有效、已创建且保存深度可用后，调用 `DecompressVoxelSave` (`0x1441A3F5B`) 和 `LoadFromSave` (`0x1441A3F6A`)。`DecompressVoxelSave` (`0x143E6A9A0`) 对压缩字节解包失败会记录 `DecompressVoxelSave failed: Corrupted data` 并返回 false (`0x143E6A9D8`—`0x143E6AA34`)。该函数在解包成功后调用 `FVoxelUncompressedWorldSaveImpl::Serialize`，但当前指令把返回值丢弃，然后设置成功返回 (`0x143E6AA6E`—`0x143E6AA85`)。调用它的 `LoadFromCompressedSave` 同样没有在进入 `LoadFromSave` 前检查解压返回值。这是**插件 API 的失败传播弱点**；它是否影响本游戏取决于蓝图实际调用与外层校验，不能据此断言玩家存档损坏时游戏一定丢档。

`UVoxelDataTools::LoadFromSave` (`0x1441A4020`) 对无世界、未创建世界和无效深度返回失败；对保存深度大于当前世界深度给出提示，随后调用 `FVoxelData::LoadFromSave` (`0x1441A4234`)。后者先清除现有体素数据 (`0x143E8268E`)，再以 `FVoxelIntBox::Infinite` 加锁，逐块由 `FVoxelSaveLoader::ExtractChunk` (`0x143E718B0`) 恢复 values/materials，载入 placeable items，并返回由内部错误标志产生的 bool (`0x143E82750`—`0x143E82963`)。`ExtractChunk` 会把恢复的叶子数据设脏 (`0x143E71E8A`)，这是后续派生结果更新的输入。上层 `LoadFromSave` 随后把变化盒传给世界中一个虚调用 (`0x1441A4239`—`0x1441A4263`)；因尚未确认该虚调用精确接口，暂不把它写成确定的 mesh 更新函数。载入是替换当前数据而非把存档追加为操作日志。

## 构造演算：两处挖掘后的保存与恢复

假设原程序生成的地下体素中，A 叶块有 4,096 个值，B 叶块也有 4,096 个值；玩家只在 A 修改一个密度值，在 B 修改一个材质值。插件构建保存对象时，按脏标志收集 A 的值块与 B 的材质块，另保存块位置/状态和可能的 placeable items；它无需把所有未修改叶块或三角面片写进这个对象。游戏角色的 `SaveGame` 入口创建 `RefMainSave`，其 `Save(VoxelWorld)` 把压缩结果放入 `VoxelWorldSave`，再由 `SaveOres` 收集位置并经 `ContinuePlayerSave` 写入库存/进度。0.1 秒 latent 续接后，成就对象进入 `ACHSave` 同步 slot，主对象进入 `MainSave` 异步 slot。重新进入时，`LoadFromSave` 清掉旧的编辑状态，用保存块覆盖新生成世界中的对应叶子，再将恢复叶子标脏，供派生网格更新。这是**依据上述指令组织的构造例子**；A/B 位置、压缩后字节数、总耗时和可见刷新延迟都不是实测。

## 一致性与性能含义，以及未决项

已证：主存档通过同步 `GetCompressedSave` 抓取带全域数据锁的快照，保存修改叶块的逻辑数据加对象，不存 mesh 或逐次挖掘日志；之后序列化、压缩并进入 `MainSave` 异步 slot API。载入 `MainSave` 后调用同步的 `LoadFromCompressedSave`，恢复块设置 dirty。游戏有队列、cooldown、自动保存及应用状态事件回调。`ACHSave` 走同步 slot API。异步 slot 仍在调用线程先做对象序列化，故不能推出不会有保存帧耗时；应用被强制结束时最后一次请求是否落盘也未证实。

未证：所有配置层在当前运行中最终选哪个 `ISaveGameSystem` provider、具体文件路径/写盘完成与失败反馈、临时文件或替换提交是否由自定义 provider 执行、旧存档版本迁移、云存档冲突处理、每次挖掘是否触发保存请求，以及实际保存/加载耗时和峰值内存。本次没有读取真实玩家存档，也没有运行时测量。`LoadFromCompressedSave` 的 native 解压错误传播弱点已位于游戏真实载入链上，但缺少损坏测试样本，不能据此推定会无提示清空玩家体素数据。

**自研规格建议（不是原作事实）**：将编辑块的不可变快照与渲染 mesh 生命周期分离；写盘在后台完成，写临时文件、校验、同步并原子替换保留上一份可用快照；保存队列记录请求版本号及完成版本，失败保持待保存状态并向用户给出明确诊断。按修改块数量与总压缩字节数分别设预算，实测锁持有时间、序列化/压缩时间、峰值内存和加载后重建帧耗时。不要仅凭异步回调名称认定磁盘写入安全或性能稳定。
