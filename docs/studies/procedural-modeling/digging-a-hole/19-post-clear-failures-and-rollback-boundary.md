# 掘地求财：清旧后的失败来源与回滚边界

后续[20：部分恢复后的LOD、网格与碰撞](20-partial-restore-lod-mesh-collision.md)补正变化盒来源：除清旧前旧树终端盒外，成功匹配并ExtractChunk的新叶节点也追加盒。本文对失败bool／旧根回滚的结论不变；变化盒与刷新范围以20的完整链为准。

## 范围与证据身份

接续 [18：加载失败与旧世界数据的保护边界](18-failed-load-and-old-world-protection.md) 和 [02：体素保存、载入与一致性边界](02-save-load-and-consistency.md)。本篇只分析 `C:\Software\Steam\steamapps\common\A Game About Digging A Hole\DiggingGame\Binaries\Win64\DiggingGame-Win64-Shipping.exe`（PE32+ x64，145,180,160 字节）及同目录匹配 PDB（1,659,662,336 字节）已经解出的静态控制流。地址为 EXE 首选基址 `0x140000000` 下的 VA，非运行地址；同一制品的 RSDS 身份见 [00](00-evidence-and-reproduction.md)。本轮未计算摘要。

沿用本地忽略目录 [save/](../../../../.cache/procedural-modeling/digging-a-hole/save/) 与 [static-state-followup/digging-a-hole/](../../../../.cache/procedural-modeling/static-state-followup/digging-a-hole/) 的完整函数反汇编和蓝图解析；新增有界输出在 [static-lifecycle-followup/digging-a-hole/](../../../../.cache/procedural-modeling/static-lifecycle-followup/digging-a-hole/)。PDB 由仓库 [pdb_probe.py](tools/pdb_probe.py) 查询；新增 LOD 查询 `exhausted=true`，`dumpbin 14.44.35222.0 /DISASM /RANGE` 读取精确 VA，`/RAWDATA:BYTES /RANGE` 读取虚表。这些是普通静态文件，**不是 REA Evidence**。没有启动或附加目标、执行目标函数、制作或读取玩家存档、做 GPU 取证、安装软件或操纵前台。

## 结论：可见的内层 bool 失败生产者为零

下文“深度有效”仅指通过已见`depth != -1`资格门，不代表保存内容已经过完整语义校验。

`UVoxelDataTools::LoadFromSave` 在通过世界/创建/深度门后，于 `0x1441A4234` 调 `FVoxelData::LoadFromSave`。内层于 `0x143E8268E` 调 `ClearData`；它在 `0x143E64BAB–0x143E64C48` 换入新根并销毁旧根及旧 placeable-item holder，还重置 undo/redo 和关联编辑状态。**该对象内没有保留旧根的回滚入口。** 清旧后才构造 `FVoxelSaveLoader`：`[rbp-70h]` 存保存对象指针，`[rbp-68h]` 的失败字节于 `0x143E82731` 置零；尾部 `0x143E82912–0x143E8291B` 检查它，零使返回 true。完整 `FVoxelData::LoadFromSave` 指令中没有第二处直接写这个字节。

对可能通过别名写该字节的已见调用逐一核对：树遍历包装 `0x143E42EA0` 调 lambda `0x143E5A7C0`，后者从 loader 只读保存对象指针，按 chunk 数与当前序号的**相等**关系停止，并调用 `ExtractChunk`；两个函数均未写 loader 的 `+8` 失败字节。`FVoxelSaveLoader::ExtractChunk` (`0x143E718B0–0x143E71E9F`) 返回类型为 `void`，只读 loader 的保存对象指针，没有对 `+8` 写入。`GetPlaceableItems` (`0x143E79410–0x143E7968B`) 同样只读 loader 的保存对象指针；它创建自己的内存 reader 和 object archive，调用 `SerializeItems` (`0x143E8F340`)，既不传 loader 的失败字节，也不在返回后检查 archive 错误。因此，**在所见完整调用链的正常返回路径，找不到能把这个 bool 变为 false 的生产者**。这一结论比“内层可在恢复失败后返回 false”更窄，也更贴近这份制品；不能把返回 true 当成所有保存内容已被语义验证。它不覆盖异常、内存错误、未识别的跨函数副作用或未观察到的运行时故障。

### chunk 和 placeable item 的实际约束

- lambda `0x143E5A7E0–0x143E5A906` 以当前序号和保存对象的 chunk 数 `+0x78` **相等**作为停止门；没看到 `序号 < count` 的独立边界检查。它只在叶块空间位置与保存块匹配时调用 `ExtractChunk`，然后在 `0x143E5AB2C` 增加当前序号。块的位置不匹配时，本次遍历可能不消费该块；没有因此置失败位的可见写入。索引被破坏成越界值时，不能从这些指令推定可控地返回 false；后续解引用、内存错误或其他结果仍属未知。
- `ExtractChunk` 在 `0x143E718DC–0x143E718E7` 先清当前新叶的 value/material。value 块索引 `+0x0C` 非负时，单值分支从保存的 value 数组 `+0x30` 取一值 (`0x143E7191C–0x143E71931`)，普通分支从 `+0x20` 复制 `0x2000` 字节 (`0x143E719D2–0x143E719E4`)；material 索引 `+0x10` 非负时，从 `+0x40` 的八个 32 位通道偏移，经 `+0x50` 数据数组或 `+0x60` 单值数组恢复 `0x1000` 个材质 (`0x143E71AA5–0x143E71E7D`)。所见直接读/复制分支没有按保存数组长度核对索引、字节区间或八个材料偏移，也没有以材料值非法为条件设置 loader 失败位。能否在这些指令之前由序列化器或数组 API 阻断特定畸形输入，不能由这里一概否定；若坏索引走到这里，不能承诺获得失败 bool 或安全恢复。
- `GetPlaceableItems` 用独立 reader 解出 placeable items 后，内层 `SerializeItems` 对未能同步解析的 transformable generator 走 `0x143E8F759–0x143E8F969` 的跳过路径，继续下一个对象；可见路径未把该情况传回 loader 失败位。之后 `FVoxelData::LoadFromSave` 于 `0x143E828B0` 逐项 `AddItem` 到**新**数据树。该流程可能产生只恢复部分 placeable items 的成功返回；具体资源可用性和可见结果未运行验证。reader 自身的 archive 错误不会从这个函数被转换成 `FVoxelData::LoadFromSave` 的 false。

这些约束发生在不同阶段：`FVoxelUncompressedWorldSaveImpl::Serialize` 的 archive 读取错误分支于 `0x143E8EF4B–0x143E8F02E` 重置未压缩对象深度为 `-1`，因此下一层在清旧**之前**挡住；但“可解包且形成非 `-1` 深度”不是 chunk 索引、数组区间、资源引用全部正确的证明。序列化器的异常数组数量还可走 `OnInvalidArrayNum` (`0x143E8F169` 等)，不能把它归类为正常 false 返回。

## 分支与后态

| 输入/控制流分支                                                               | 清旧前后                             | 内层及外层可见结果                                  | 旧体素根、刷新与蓝图后态                                                                                                                                  |
| ----------------------------------------------------------------------------- | ------------------------------------ | --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 世界无效、未创建、保存深度 `-1`；空压缩字节、解包明确失败或序列化错误重置深度 | `ClearData` 前停止                   | `LoadFromCompressedSave` 返回 false                 | 旧 `FVoxelData` 根仍在；`VoxelComplexController_SaveExample.Load` 只 `PrintString`，不载 spawner。详见 [18](18-failed-load-and-old-world-protection.md)。 |
| 深度有效，合法空 chunk/无 placeable                                           | `ClearData` 换根，随后零块遍历       | 所见失败位保持零，正常返回 true                     | 旧编辑树已销毁；变化盒来自清旧前旧树遍历，随后交给 LOD 更新。蓝图继续 `LoadFromSpawnersSave`。                                                            |
| 深度有效，块可读取，但块位置与遍历节点不匹配、资源引用不能解析等语义缺口      | 先换根，再局部写入或跳过             | 已见代码没有置失败位；正常完成时仍可返回 true       | 可能得到只恢复部分内容的新树；随后仍发出变化盒更新，蓝图仍可继续 spawner。实际输入是否能达到该路径需独立验证。                                            |
| 深度有效，chunk 索引/数组区间畸形且进入 `ExtractChunk` 的直接读/复制          | 旧根已毁，随后进入未证安全的内存访问 | 没有可见的对应 false 分支；崩溃、异常或其他结果未知 | 不能保证旧树、恢复后的新树、通知或蓝图提示的最终状态；静态读取不足以给出运行结果。                                                                        |
| **条件性**：假设内层失败位被未见机制置为 1 且函数正常返回                     | 清旧已发生                           | 内层及外层 false                                    | 上层仍在 `0x1441A4239–0x1441A4263` 调 LOD 更新虚函数；蓝图只提示失败，不回滚体素树。此行只说明控制流后果，不宣称该输入已可构造。                          |

清旧后的上层虚调用现已定位：`AVoxelWorld::CreateWorldInternal` 于 `0x1441D34BB` 调 `CreateLODManager`，把返回的 `IVoxelLODManager` 指针保存到 `world+0x908` (`0x1441D34DC–0x1441D3500`)。`LoadFromSave` 读取这个指针，在内层 bool 存入 `ebx` 后，**不按 bool 分支**，经虚表 `+8` 调用并传入变化盒数组及空 delegate (`0x1441A4239–0x1441A4263`)。匹配制品的 `FVoxelDefaultLODManager` 虚表 `0x1471AA150` 中 `+8` 项为 `0x143E97870`，PDB 将其命名为 `UpdateBounds(TArray<FVoxelIntBox> const&, delegate const&)`；该实现对空变化盒早返回，对非空盒逐个调用 `FVoxelRenderOctree::GetChunksToUpdateForBounds`，再调用 renderer 的更新接口 (`0x143E9789D–0x143E97A5D`)。这证明**请求局部重建/刷新**，不证明 mesh/碰撞在本帧完成；运行实例是否实际采用默认 LOD manager 仍需实例证据。所谓失败通知是蓝图 `PrintString`，不是 LOD 更新调用的效果。

## 构造输入的控制流演算

构造一个**不制作、不运行**的逻辑输入：当前世界深度为 8，旧树含挖掘叶 A；压缩内容可解包并序列化成深度 8、一个位置匹配且数组索引有效的 chunk B、一个引用当前无法解析的 transformable generator 的 placeable item。先前压缩元数据和临时对象都通过深度门。`ClearData` 毁掉含 A 的旧根；遍历 B 时 `ExtractChunk` 向新树写入 B；placeable 解码走 `LoadSynchronous` 未得对象后的跳过分支，因而该 item 不加入新树；失败字节仍为零，于是内层正常返回 true。上层即使只有旧 A/B 的变化盒，也照常请求 LOD `UpdateBounds`；蓝图走成功分支并恢复 spawner。这里的 B、引用缺失和画面结果是为说明分支而设的条件，**不是游戏真实存档观察**。它说明 bool true 可与部分资源未恢复并存，且旧 A 没有回滚来源。

## 回滚边界、未决问题与验证

在内存数据层，`ClearData` 释放旧根并重置相关编辑状态；内层、`UVoxelDataTools` 及游戏 SaveExample 蓝图的所见后续路径均没有旧根备份、交换回旧根或逆向重放。磁盘 `MainSave.sav` 不是 `ClearData` 的操作对象，游戏角色其他字段、云副本与未来自动保存另有生命周期；不能由这里推断磁盘旧档已被覆盖，也不能把磁盘档存在说成这次内存载入具有自动回滚。蓝图 false 时只输出 `Failed to load voxel world voxel data`，不会载入 spawner，也没有体素恢复动作；false 绝不等价于“旧树仍在”。

本轮 **Passed（静态核对）**：EXE/PDB 文件长度与既有身份一致；完整 `LoadFromSave`、`ExtractChunk`、遍历 lambda、`GetPlaceableItems` 的失败字节写入点和调用参数；`world+0x908` 的构造来源、默认 LOD 虚表项与目标 `UpdateBounds` 签名；蓝图完整 `Load` 解析结果 `complete=true`。**Partial**：所有可能畸形输入如何通过 archive 与容器边界、非常规异常如何终止、默认 LOD manager 是否为实际实例。**Not Run**：游戏运行、任何存档制作/读取、资源缺失复现、画面/碰撞结果、磁盘与云回滚、后续自动保存。下一步若获准运行，需在隔离且可恢复的非私人样本上分别验证“合法深度+可读块+缺失资源”和畸形索引，记录崩溃/返回值、树状态、LOD/mesh/碰撞及 slot 后态；本篇不把静态构造演算当成目标实测。
