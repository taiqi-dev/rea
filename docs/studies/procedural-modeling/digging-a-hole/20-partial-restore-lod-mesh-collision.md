# 掘地求财：部分恢复后的 LOD、网格与碰撞刷新边界

接续[19：清旧后的失败来源与回滚边界](19-post-clear-failures-and-rollback-boundary.md)。本篇只问深度门已通过、旧数据根已被替换、chunk 或 placeable item 可能只恢复一部分时，传给 LOD 的盒从何而来，以及这些盒能否继续到网格和碰撞。前层的解包、失败字节和 bool 结论沿用 19，不在这里重判。下述均为**发行制品的静态控制流**，不是一次游戏运行的画面或物理观察。

## 身份、方法与证据边界

目标是 `C:\Software\Steam\steamapps\common\A Game About Digging A Hole\DiggingGame\Binaries\Win64\DiggingGame-Win64-Shipping.exe`（PE32+ x64，145,180,160 字节）及同目录匹配 PDB（1,659,662,336 字节）。RSDS 身份与先前匹配方式见[00](00-evidence-and-reproduction.md)；本次不重算摘要。地址是 EXE 首选基址 `0x140000000` 下的 VA，不是实时地址。

本次用[现有 PDB 探针](tools/pdb_probe.py)查询 `FVoxelDefaultRenderer`（79/79）、`FVoxelRenderOctree`（27/27）、`FVoxelDefaultLODManager`（43/43）、`FVoxelData::AddItem`（16/16）等精确范围，查询结果均 `exhausted=true`；用 VS 2022 `dumpbin 14.44.35222.0 /DISASM /RANGE:0x...` 与 `/RAWDATA:8 /RANGE:0x...` 读取局部指令和虚表。新原文位于忽略目录 [static-scheduler-followup/digging-a-hole/](../../../../.cache/procedural-modeling/static-scheduler-followup/digging-a-hole/)：`load-full.disasm.txt`、`load-chunk-visitor.disasm.txt`、`add-loaded-item.disasm.txt`、`scheduler-symbols.json`、`load-symbols.json`、`renderer-vtables.raw.txt`、`renderer-update-chunks.disasm.txt`、`renderer-process-mesh.disasm.txt`、`renderer-tick.disasm.txt`、`octree-select.disasm.txt`。复用[19](19-post-clear-failures-and-rollback-boundary.md)的 `lod-update-bounds.txt` 与上层载入指令，以及[05](05-task-lifetimes-growth-and-performance.md)、[08](08-mixed-handler-submission-chain.md)、[09](09-collision-result-acceptance.md)的已核对静态函数。这些本地文本是普通 PE/PDB 读取结果，**不是 REA Evidence**。

## 变化盒来自旧树终端节点和成功匹配的新 chunk

`UVoxelDataTools::LoadFromSave` 于 `0x1441A4222–0x1441A4234` 把本地 `TArray<FVoxelIntBox>` 指针交给 `FVoxelData::LoadFromSave`。内层在 `0x143E8243A` 检查该可选输出指针；非空时先锁定**当前旧数据根**，读取 `data+0x1E0`，遍历其八叉树，并在 `0x143E82555–0x143E82590` 向该数组追加 24 字节盒。然后于 `0x143E8268E` 调 `ClearData` 换根。正常旧树中，节点没有子节点时会追加以节点位置和 `8 << 节点深度` 构成的盒；有子节点时递归八个子节点。这里没有按“叶子曾编辑”过滤，第一批输出是旧树**终端节点的空间覆盖**，不能缩写成旧挖掘点列表。依据：`load-full.disasm.txt` `0x143E824B2–0x143E8268E`。

清旧后，`0x143E82739–0x143E82750` 把原输出数组指针所在的栈槽纳入 lambda capture，再遍历保存 chunk。lambda `0x143E5A7C0` 先检查保存数组当前序号；只有新树叶节点位置与保存块位置三轴相等，才于 `0x143E5A906` 调 `ExtractChunk`，并在 `0x143E5AB2C` 增加序号。**在同一匹配分支**，`0x143E5AB31–0x143E5AB6A` 从 capture 取得上述输出数组指针，非空时追加该叶节点的 24 字节盒。这是第二批变化盒；未匹配、未提取的保存块不会由这条分支追加。`load-chunk-visitor.disasm.txt` 给出完整 `0x143E5A7C0–0x143E5ABDD`，不是仅凭函数名判断。它把[19](19-post-clear-failures-and-rollback-boundary.md)中“变化盒来自清旧前旧树遍历”的简述修正为**旧树终端盒 + 实际匹配提取的新 chunk 盒**；19 对失败 bool 和回滚的结论不依赖这个修正。

随后 `0x143E82863` 解 placeable items，`0x143E828BA` 用 `FVoxelData::AddItem<FVoxelAssetItem,1,...>` 加入新根。`AddItem` 的当前调用只接收数据对象、item 和返回包装指针，其已读实现 (`0x143E33E80–0x143E34172`) 会遍历新数据树写 item，但不接收上述 `TArray`、不直接调用这次 LOD `UpdateBounds`。因此**恢复的 placeable item 没有在这次路径中单独追加自身边界**。这不排除其他监听器或未来独立编辑事件；本篇没有把未追踪的后续事件归入此次调用。

其影响容易被误读：旧终端节点盒在正常八叉树布局下覆盖整个旧根区域。因此新位置 B 在旧根覆盖内，即使没有新盒，也可能因旧盒与 B 周围的现存渲染 chunk 相交而被刷新；成功匹配提取时，B 的叶盒还会明确加入数组。反之，保存块位置不匹配、被跳过时，不能把该未恢复块当作第二批盒的来源。静态指令没有给出所有畸形树、越界保存坐标和实际实例的保证。

## 从变化盒到任务与组件

外层在内层 bool 存到 `ebx` 后，`0x1441A4239–0x1441A4263` 不以 bool 作分支，读取 `world+0x908` 的 LOD manager，通过虚表 `+8` 传上述数组和空 delegate。`AVoxelWorld::CreateWorldInternal` 对该字段的来源及默认 LOD 虚表见[19](19-post-clear-failures-and-rollback-boundary.md)。若实际实例是 `FVoxelDefaultLODManager`，虚表 `0x1471AA150+8` 落到 `0x143E97870 UpdateBounds(TArray<...>)`：无 render octree 或数组长度为零时 `0x143E97889–0x143E978A3` 直接返回 0；否则逐盒向三轴扩展 2 个体素坐标单位，`0x143E97A10` 调 `GetChunksToUpdateForBounds`，并在 `0x143E97A5D` 调 renderer 虚表 `+0x10`。该 `+0x10` 槽在默认 renderer 虚表 `0x1471B18B0` 实测为 `0x143EF53B0 FVoxelDefaultRenderer::UpdateChunks`。**默认 manager 与 renderer 是否是这次游戏实例的动态类型，仍为条件。**

`GetChunksToUpdateForBounds` (`0x143E72DF0`) 先做三轴 AABB 相交，边界不相交就返回；相交节点的标记 `+0x48 & 7` 非零时将其 chunk key 加入列表，并继续遍历已有子节点 (`0x143E72E14–0x143E72ED8`)。这个筛选取的是**当前 render octree 中存在的 chunk**；旧数据树盒本身不创建 renderer chunk。若所得列表长度为零，默认 renderer `UpdateChunks` 在 `0x143EF5447–0x143EF545D` 返回 0；若 renderer 的 `+0x141` 静态状态门非零，则在 `0x143EF53D1–0x143EF5446` 记录不能更新并返回 0。非空正常分支对每个 key 查当前 chunk，追加 `FPendingUpdate`，调用两种 `StartTask`，最后 `FlushQueuedTasks` (`0x143EF54C3–0x143EF56EB`)。`StartTask` 的占槽门意味着收到通知不等于立即并行启动新 mesher，详见[05](05-task-lifetimes-growth-and-performance.md)。LOD 调用返回值没有在外层替代载入 bool。

任务完成并非本帧同步 mesh 提交：默认 renderer 的 `Tick` 于 `0x143EF391A` 调 `ProcessMeshUpdates`，后者在 `0x143EED0D0–0x143EED1FC` 对完成项查当前 chunk key、相应任务槽及槽中任务 `+0x68` 与完成令牌相等，再检查任务状态。通过后可能 `RemoveChunk` (`0x143EED451`)，或经 `0x143EED462 → 0x143ECDA50` 走 mesh handler `UpdateChunk`；`0x143EED4BF` 再调 `CheckPendingUpdates`。不存在的 chunk、空任务槽或令牌不符的旧结果不能由此路径提交。这是完成结果的**当前槽身份门**，尚不能把令牌称为存档版本号，也不能证明一次部分恢复必有新完成项。

在[07](07-material-slots-and-handler-selection.md)给出的 MainLevel 初始 Mixed 配置仍适用、且完成 mesh 的 settings 带相应位时，[08](08-mixed-handler-submission-chain.md)已追到 `Mixed::ApplyAction`：可见 bit 0 送 Clustered，碰撞 bit 1／导航 bit 2 送 Basic；相应异步合并结果还各有当前对象与序号门，最终通过 `AddProcMeshSection → FinishSectionsUpdates` 更新组件。`FinishSectionsUpdates` 于 `0x143EDE53D` 调 `UpdateCollision`。碰撞只有 section `+0x10` 要求时才走 cook 支路；关闭碰撞的 section 走直接完成，冻结状态会延后处理；已启用的旧 cooker 先被取消并清当前指针，然后才可建立新 Chaos cooker。新 cook 完成事件在主线程 `PhysicsCallbackHandler::TickHandler` 中必须匹配有效弱组件、当前 cooker、队列编号与 `currentCooker+0x68`、任务状态和 BodySetup，才可 `Finalize → FinishCollisionUpdate → RecreatePhysicsState`。精确接受门见[09](09-collision-result-acceptance.md)。这是**有条件的组件物理状态重建路径**，并不证明某个实际载入触发了碰撞，也不证明引擎最终碰撞形状或可见时延。

## 分支表：部分恢复输入与完成边界

| 本次输入或状态                                                          | 变化盒和 LOD 选择                                                                                                              | 网格、碰撞后续                                                                                                |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| 输出数组为空（例如内层调用者传空指针，或未形成盒）；默认 LOD 实例       | 默认 `UpdateBounds` 长度零早退；当前上层实际传了非空数组指针，旧树通常会贡献终端盒，所以不能把“合法空保存”直接等同于“空变化盒” | 这次调用不送 renderer；不由此产生 mesh/cook。                                                                 |
| 旧位置 A 被清，新位置 B 的 chunk 位置匹配并已提取                       | 旧树终端盒与 B 的新叶盒都可进入数组；当前 render octree 中的相交 chunk 必须存在且带选择标记才列入更新 key                      | key、状态门、任务槽、完成令牌依次通过时，才可能提交新 mesh；碰撞再取决于 settings 和 section。                |
| 保存块 B 未匹配／未提取，或对应 render octree 没有 chunk／相交标记      | B 不贡献新叶盒，但旧树盒可能仍覆盖该位置；若筛选不出当前 key，数组可以非空而 key 仍为零                                        | 对未提取 B 不能推断有 B 的新网格；其他独立更新未在本链证明。                                                  |
| placeable item 被跳过，或新加入但其位置不在选中盒内                     | item 不为此次输出数组单独追加边界；旧树/新 chunk 的盒仍可能覆盖其位置                                                          | 即便载入 bool 正常为 true，这条路径对该 item 的画面与碰撞结果仍未知；不能由此次刷新断言它出现。               |
| 盒选中 chunk，但 renderer 为 static、任务槽占用、旧完成项 key／令牌不符 | static/空 key 早退；占槽可留下 pending；旧完成项在接受门被跳过                                                                 | 不能把“已调用 UpdateBounds”写成“已完成 mesh”。旧 cook 即使入队，编号不等于当前 cooker 也在最终门被拒绝。      |
| mesh 已获接受；section 无碰撞位、碰撞冻结、或有碰撞位且正常 cook        | Mixed 的具体路由和 section 才决定碰撞入口                                                                                      | 无碰撞位可直接 `FinishCollisionUpdate`；冻结延后；启用 Chaos cook 则等主线程编号门、Finalize 和物理状态重建。 |

**构造演算，非存档或运行观测。** 设旧数据根的终端盒覆盖坐标 `[0,512)`，旧编辑 A 在 `x=32`，新保存块 B 在 `x=320` 且与新树叶节点匹配；另有保存块 C 在 `x=448`，但未与遍历到的叶节点匹配；transformable placeable P 在 `x=400`，资源引用不能解析而被跳过。旧树盒在清旧前加入数组；`ClearData` 后 B 经 `ExtractChunk` 写入新根，随后 B 的新叶盒也加入数组，C 不写入且不贡献新叶盒，P 被跳过，内层仍可正常返回 true。若默认 LOD/renderer 是实例，B 的 render chunk 已存在且符合标记，则旧盒和 B 新叶盒经 ±2 扩展后可选中它，可能生成 pending 网格任务。旧盒也可能覆盖 C 的位置，但没有 C 的新数据可据此提交；P 没有因此恢复。B 虽与旧编辑 A 相隔 288 个坐标单位，仍可能更新，原因同时包括旧终端盒覆盖和 B 的明确新叶盒。即使 B 的网格任务完成，仍要通过当前 chunk/任务令牌；只有碰撞位存在且相应组件结果通过后，才到物理状态重建。坐标、根大小、匹配结果、chunk 是否存在和标记都为说明分支而设，未声称是本作实际参数。

## 已答、限制与下一入口

**Passed（静态）**：旧数据根终端盒在 `ClearData` 前生产，匹配并提取的新 chunk 在后续追加新叶盒，placeable 不单独追加本次数组；默认 LOD 虚表到 `UpdateBounds`、默认 renderer 虚表到 `UpdateChunks`；空数组／空 key／static 门；`Tick → ProcessMeshUpdates` 的当前 chunk 和令牌门；在 Mixed 与碰撞位条件下，既有网格提交和 Chaos cooker 接受门。新增原文和符号查询输出均可从上述本机目录逐条复核。

**Partial**：`world+0x908` 与 renderer 的实际运行动态类型、当前 render octree 的 chunk/标记分布、载入时是否有在飞旧任务及其先后顺序、placeable 内部或其他监听器是否触发独立更新。静态链不能断定某一次 B 必显示，亦不能把 `RecreatePhysicsState` 调用当作物理形状完成的实测。

**Not Run**：目标启动／附加、函数执行、GPU/物理观察、私人存档读取、资源缺失复现及构造存档。下一次若有**非私人、可恢复且明确授权的运行样本**，最有价值的是记录 A/B 分离时的旧树终端盒、B 的新叶盒、render chunk key、pending/完成令牌和最终组件，验证静态推导的实际动态类型和提交时序。另一个纯静态入口是追 `FVoxelData::AddItem` 的 `IterateTreeInBounds` 消费及其监听者，专门判定 placeable 加入是否会产生**本次 LOD 调用之外**的更新；它不改变本文对输出数组的结论。
