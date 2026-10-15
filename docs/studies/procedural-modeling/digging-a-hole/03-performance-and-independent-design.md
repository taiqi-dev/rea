# 掘地求财：局部重建调度与自研性能预算

## 证据边界

本文延续[挖掘值场与局部重建](01-excavation-and-local-rebuild.md)，研究同一安装版本中**已编入的 Voxel 插件原生调度路径**，并以已恢复的完整 Blueprint 字节码区分 Dig 和爆炸的编辑入口。目标 `DiggingGame-Win64-Shipping.exe` 为 145,180,160 字节，同目录 PDB 为 1,659,662,336 字节；地址是首选映像基址下的 VA，函数边界由 PDB 定位，分支由 EXE 的有界反汇编复核。原始证据在本机忽略目录 `.cache/procedural-modeling/digging-a-hole/performance/` 的 `queue-one.txt`、`queue-pop.txt`、`priority-handler.txt`、`lod-invokers.txt`、`lod-distance.txt`、`renderer-tick.txt`、`process-mesh-updates.txt` 和相应符号 JSON。静态代码和字节码不证明运行时采用的线程池设置、每铲产生多少任务或达到多少 FPS。

## 从影响盒筛选到工作队列

**观察**：球形编辑的原生路径先写受影响体素，再按修改盒请求世界更新；完整的 `BP_Explosion` 与 `BP_Dynamite` 主图字节码均含同步 `RemoveSphere` 调用，半径来自各自的 `ExplosionRadius`。`FVoxelRenderOctree::GetChunksToUpdateForBounds`（`0x143E72DF0`，261 字节）用 AABB 相交剪枝，`FVoxelDefaultLODManager::UpdateBounds`（`0x143E97870`，554 字节）用它收集要更新的 chunk。`FVoxelDefaultRenderer::UpdateChunks`（`0x143EF53B0`，1666 字节）管理待更新项并通过 `StartTask` 发起重建；`FVoxelMesherAsyncWork::DoWork`（`0x143EDBEB0`，1374 字节）在任务中生成 mesh。详见 01 的逐点公式和 Blueprint 调用证据。同步编辑节点**可能**把数据锁与格点改写计入触发它的线程成本；一次爆炸在运行时到底产生多少 chunk、卡在哪一帧，仍需测量。

角色 `Dig` 字节码在 `DrillUnlocked?` 条件分支中进入 `SurfaceEdit`，后者把 `DrillStrengthAfterNerf × Delta Seconds × 60.0` 送到 `ApplyConstantStrength`，用 `DigRadius` 设 `ApplyFalloff` 和采样盒，再顺序调用 `FindSurfaceVoxels`、`ApplyStack`、`EditVoxelValuesAsync`。native `FindSurfaceVoxelsImpl<0>`（`0x1441C5A00`，668 字节）先批量读取候选盒的值并扫描六邻居符号交界；异步值编辑阶段持锁改写，按配置还可能逐候选读取材质硬度。详见 01。**推导**：候选盒体积决定采样/筛选的基础工作量，而筛中表面点数决定后续栈处理和材质相关工作量；两者不应只用“挖洞半径”一个指标替代。实际候选数、硬度分支和耗时尚未测量。

**观察**：`FVoxelQueuedThreadPool::AddQueuedWork`（`0x144175B60`，418 字节）持有临界区时，根据池对象的 `+0x2C` 字节走两条路径：

| 路径       | 入队及取任务的指令行为                                                                                                                                                                                    | 可确定的含义                                                         |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| 该字节非零 | 入队调用工作的虚表 `+0x30` 取优先级，加调用者偏移并钳到 `0..0xffffffff`，记录下一次刷新时间后压入 `std::priority_queue`（`0x144175BF5`—`0x144175C50`）；取任务从堆顶弹出（`0x1441ACF84`—`0x1441ACF9D`）。 | 这是按入队时算出的优先级排序的堆路径；在这次弹出指令中未见重新计算。 |
| 该字节为零 | 入队把 32 字节记录追加到数组（`0x144175C57`—`0x144175C89`）；取任务扫描数组，到刷新时间才调用同一虚函数重算并钳位（`0x1441ACE81`—`0x1441ACED2`），选最大复合键后移除（`0x1441ACEDF`—`0x1441ACF78`）。     | 这一路可随时间或观察点变化动态重排；一次选取是线性扫描。             |

数组记录中，`+0x10` 的 32 位输入值排在复合键高位，`+0x14` 是缓存的动态优先级，`+0x18` 是有符号偏移；比较相当于按 `uint64(group << 32 | priority)` 选最大。`+0x08` 是下一次重算时间，重算后增加工作对象 `+0x18` 的间隔。字段的**正式名称、配置字节语义、输入分组的业务含义、间隔单位及本游戏选择哪一路都未知**；不能把数组路径的动态重排说成所有任务必然具备。入队与取任务都在临界区内完成，扫描路径的队列长度会影响锁持有成本。依据：`queue-one.txt`、`queue-pop.txt`。

`FVoxelMesherAsyncWork::GetPriority`（`0x143EE53C0`，12 字节）转到 `FVoxelPriorityHandler::GetPriority`（`0x143EE53D0`，316 字节）。后者对每个 invoker 体素位置计算它到 chunk 轴对齐盒的三轴越界距离平方，取最小值，开平方转整数再逐位取反（`0x143EE5410`—`0x143EE5505`）。在有 invoker 且正常距离范围内，贴近盒子的工作得到更大的无符号优先级；落在盒内距离为零，得到 `0xffffffff`。没有 invoker、距离溢出及分组偏移的整体排序需按具体调用状态解释，不能只凭这个函数称“离玩家最近的任务一定最先完成”。依据：`mesher-priority.txt`、`priority-handler.txt`。

## LOD、异步计算与提交边界

**观察**：`FVoxelDefaultLODManager::UpdateInvokers`（`0x143E97DB0`，2875 字节）收集 invoker 和设置，取其体素位置并请求 LOD 更新。`FVoxelRenderOctree::UpdateSubdividedByDistance`（`0x143E9A3E0`，381 字节）先检查节点层级和设置阈值，再以节点盒与外层及各档盒的 AABB 相交测试决定是否继续细分；需要时创建八个子节点并递归。该函数使用已有空间盒筛选，不是对每个体素计算到玩家的欧氏距离。实际 invoker 来源、距离档位和运行时 LOD 值未从游戏世界资产证实。依据：`lod-invokers.txt`、`lod-distance.txt`。

**观察**：`FVoxelDefaultRenderer::Tick`（`0x143EF3890`，588 字节）把一个浮点字段乘 `0.001` 后加到当前性能计数器时间，作为截止时间传入回调并传给 `ProcessMeshUpdates`（`0x143EF391A`），之后调用 `FlushQueuedTasks`（`0x143EF3926`）。`ProcessMeshUpdates`（`0x143EED040`，1398 字节）在进入和循环尾部比较时钟与截止时间（`0x143EED089`、`0x143EED558`），处理完成任务、移除或更新 chunk、过渡显示和待更新项；其中可见 `WaitForDoThreadedWorkToExit`（`0x143EED3A0`）调用，但当前分支上下文不足以断言它每次会阻塞。浮点字段的名称、游戏实际设置值和一次工作单元耗时未知。截止时间比较发生在工作单元之间，**它不是每帧绝不会超预算的证明**。Tick 后半还更新 Voxel 渲染器内存计数和任务/回调队列计数。依据：`renderer-tick.txt`、`process-mesh-updates.txt`。

网格计算与可见提交是不同阶段：`FVoxelMesherAsyncWork::DoWork` 在异步工作对象中执行，完成结果随后由渲染器 Tick 路径消费，并可经 `IVoxelRendererMeshHandler::UpdateChunk`（`0x143EF5300`，166 字节）提交。组件层 `UVoxelProceduralMeshComponent::SetProcMeshSection`（`0x143EF1090`，550 字节）可接到 `FinishSectionsUpdates`（`0x143EDDF20`，1864 字节）和 `UpdateCollision`（`0x143EF5A40`，637 字节）；后者有旧工作取消及 `FVoxelAsyncPhysicsCooker_Chaos` 异步分支，`FinishCollisionUpdate`（`0x143EDDE80`，148 字节）调用 `RecreatePhysicsState`。这些指令证明插件**具备**后台生成 mesh、组件级碰撞烹制和后续物理状态提交；尚未证明本作每次铲击采用的 mesh handler、碰撞分支、碰撞比画面滞后多久，也未证明所有提交都在某一个固定帧完成。详细函数证据见 01 的 `mesher-dowork-disasm.txt`、`set-section-disasm.txt`、`finish-sections-disasm.txt`、`collision-update-disasm.txt` 与 `collision-finish-disasm.txt`。

保存链路另见[保存、载入与一致性](02-save-load-and-consistency.md)：插件全域快照锁与序列化、压缩可能和挖掘写入争用，不能用“mesh 异步”推断保存无主线程压力；本文不重复保存实现。

## 构造算例与独立设计建议

**构造算例，所有数值均为自研假设而非原作测量**：沿用 01 的体素半径 `r=6`，自研实现若将 `center ± (r+3)` 的整数候选盒两端均计入，则上界是 `19³=6,859` 个格点；原生 `FVoxelIntBox` 的遍历边界和球外早退可能改变实际访问数，实际改写数还会更少。若洞中心同时靠近三个 chunk 分界，则受影响盒在一个自研世界里可能碰到 `2³=8` 个 chunk。假设在自研目标机器实测每次主线程 mesh 提交平均 `0.4 ms`，自定每帧提交预算 `1.5 ms`，单帧最多安排 `floor(1.5/0.4)=3` 个同成本提交；无新任务、无其他提交成本时，8 个需至少 `ceil(8/3)=3` 帧才能安排完。碰撞重建、LOD 改变、锁争用、长尾任务和渲染线程成本需另计。`0.4 ms`、`1.5 ms`、8 个 chunk 都是**设计演示输入**；本次没有运行游戏，不能据此报本作 FPS、帧耗或延迟。

**自研建议**：以实际修改盒而非球体理论半径作为脏区；合并同一 chunk 连续编辑，给网格与碰撞任务保留世界/块版本，在提交前核对版本并舍弃过期结果。后台队列可按玩家相关距离和可见性优先，但要给久候任务设老化或公平性约束；主线程分别给 mesh、碰撞提交和显示切换设可测预算。至少记录每铲采样格点、筛出的表面点与实际写入格点、受影响 chunk、队列长度与等待时间、后台 CPU 时间、主线程提交与碰撞时间、快照锁等待和峰值内存，并在真实目标硬件上比较冷启动、连续挖掘及保存同时发生时的分布。这些是从机制推导的**独立实现和测量方案**，不归属目标游戏。

关键未决证据是编辑参数的运行时数值、世界资产的 voxel/chunk/LOD/碰撞配置，以及获准运行后的任务队列与逐帧测量。在这些证据出现前，本文只界定本版本原生插件的调度能力与可能的性能边界，不能把队列分支、预算字段或假设成本认定为本作实际性能。
