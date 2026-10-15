# 掘地求财：矿物组件的销毁分支与渲染连接边界

> 后续 [07：材质槽与处理器选择](07-material-slots-and-handler-selection.md)已确认煤网格默认 slot 0，并从 MainLevel 配置与构造默认值推导 Mixed handler。下文 Basic 路径是已编入的实现分支，不能当成本关卡默认执行路径；运行加载/覆盖仍未验证。

接续[矿物网格与表现](04-mesh-materials-and-ore-presentation.md)和[重建任务寿命](05-task-lifetimes-growth-and-performance.md)，本篇解开先前未解释的 `DestroyOre` 条件，并沿本作 EXE 中的 Voxel 插件代码，追到 chunk 完成数据被组件作为网格 section 与材质接收的实际调用链。结论限于发行制品静态语义：`DestroyOre` 的传入组件显示名**包含** `Voxel` 时跳过紧邻销毁，**不包含**时调用销毁；Voxel Basic handler 则把构建所得 section 交给 `UVoxelProceduralMeshComponent`，由组件的 `GetMaterial(index)` 读取对应材质。游戏是否实际选择 Basic handler、矿物网格材质槽和画面仍未实测。

## 输入与方法

目标、只读授权与文件身份沿用[00 证据入口](00-evidence-and-reproduction.md)。使用仓库的[蓝图探针](tools/blueprint_probe.py)从已提取的实际 `BP_OreSpawner.uasset` 和 Zen export 信息重新解码 `ExecuteUbergraph_BP_OreSpawner`，结果保存在 ignored 原文 `.cache/procedural-modeling/render-chain-followup/digging-a-hole/ores-executeubergraph.json`。本次结果由导出 size field 确定边界，逻辑脚本 `88931/88931` 字节、`complete=true`、无解码错误。以下蓝图偏移均为 Kismet **逻辑偏移**，另给关键指令的包内文件偏移。该探针解码语法和引用，不模拟蓝图 VM 或组件生命周期。

原生侧以 [PDB 探针](tools/pdb_probe.py)对同一 EXE 的本地 PDB 作精确掩码查询，`*MeshHandler*` 完整返回 111 个唯一符号，`*UVoxelProceduralMeshComponent*` 完整返回 94 个；用本机 VS2022 `dumpbin /DISASM /RANGE` 只读必要函数。忽略目录 `.cache/procedural-modeling/render-chain-followup/digging-a-hole/` 保存 `handler-symbols.json`、`component-symbols.json`、`merge-symbols.json`、`mesh-handler-vftables.json` 及各函数 `.disasm.txt`。虚表取本作 EXE `.rdata` 的实际 8 字节指针，按 PE section RVA 映射到文件偏移，未按类名猜虚调用目标。下述原生地址都是该 EXE 的静态 VA；未启动或附加游戏。

操作码对照取自 Epic 的 [EExprToken API](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/CoreUObject/EExprToken)：`0x07=EX_JumpIfNot`，`0x06=EX_Jump`，`0x4C=EX_PushExecutionFlow`，`0x4D=EX_PopExecutionFlow`。Epic 的 [FFrame API](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/CoreUObject/FFrame)把 `FlowStack` 定义为编译后 Kismet 的执行流栈。这些文档用于解释格式；下面的偏移、条件和对象引用仍来自本作包，不由公开示例替代。

## 新闭合的 `DestroyOre` 条件链

[04](04-mesh-materials-and-ore-presentation.md)已把角色主图的 `BreakHitResult.HitComponent` 接到 spawner `DestroyOre`。该函数的 18 字节逻辑体调用 `ExecuteUbergraph_BP_OreSpawner(82400)`。重新解析的主图给出下列连续指令：

| 逻辑偏移 / 文件偏移 | 实际指令和数据                                                                                  | 对当前分支的意义                                                               |
| ------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `82400` / `216447`  | `GetDisplayName(K2Node_CustomEvent_OreToDestroy)`，保存到 `CallFunc_GetDisplayName_ReturnValue` | 检查的是传入组件的显示名，不是 StaticMesh 资产名或体素数据值。                 |
| `82437` / `216504`  | `KismetStringLibrary.Contains(displayName, "Voxel", false, false)`                              | 返回值进入紧随的条件跳转；两个布尔常量可见，当前没有把它们外推成稳定命名契约。 |
| `82475` / `216554`  | `EX_JumpIfNot(82490, ContainsResult)`                                                           | **Contains 为 false** 时跳到销毁语句。                                         |
| `82489` / `216576`  | `EX_PopExecutionFlow`                                                                           | **Contains 为 true** 时顺序来到执行流弹栈，不顺序落入 `82490` 的销毁调用。     |
| `82490` / `216577`  | 以 `OreToDestroy` 为 context；内层 `82512` / `216607` 为 `ActorComponent.K2_DestroyComponent()` | 这是 false 分支的实际组件销毁调用。                                            |
| `82523` / `216614`  | `EX_Jump(79483)`                                                                                | 销毁调用后转向主图的后续位置；不能把此跳转解释成材质或碰撞网格更新。           |

**构造演算，非游戏运行。** 假定调用入口收到显示名 `VoxelTerrain` 的组件，`Contains` 为 true，`JumpIfNot` 不跳，接着执行 `EX_PopExecutionFlow`；这条局部路径不会执行 `82490` 的销毁。若显示名为 `CoalOre`，`Contains` 为 false，`JumpIfNot` 直达 `82490`，把该组件作为 context 调 `K2_DestroyComponent`，然后跳往 `79483`。名称仅为阐明布尔分支的自造输入，并非证明游戏实际生成这些名字。

**推导边界。** `EX_PopExecutionFlow` 的明确身份和主图布局足以排除“true 分支直接顺序执行紧邻销毁语句”。本次没有复原进入该事件时栈里保存的确切续点，也没有运行 VM；所以不主张 `Voxel` 分支的完整后继效果、最终调用帧如何退出，或组件销毁是否因运行时有效性而成功。显示名本身可变化，不能把此分支概括为按稳定组件类型 ID 排除体素组件。

## 新闭合的 Voxel section 与材质接收链

这条链是**本作内已编入的 Voxel 插件 Basic handler**，不等同于上面的矿物 `StaticMeshComponent`。其生产、队列和消费点由 PDB 符号、指令及虚表相互约束：

1. [05](05-task-lifetimes-growth-and-performance.md)已证 `FVoxelDefaultRenderer::ProcessMeshUpdates` 在验收完成结果后调用 `IVoxelRendererMeshHandler::UpdateChunk`。本次读取 `0x143EF5300 UpdateChunk`：它将 chunk ID、settings、mesh 指针及转换 mask 装入 action，并在 `0x143EF535B` 调用虚表 `+0x38`。实际 `.rdata` 虚表 `0x1471B1940+0x38` 保存 `0x143ED0F20`，即 **`FVoxelRendererBasicMeshHandler::ApplyAction`**；Clustered 和 Mixed 对应 `0x143ED14C0`、`0x143ED1CC0`。因此可将这条后续链精确限定在 Basic 分支，不能替游戏运行配置选分支。
2. `0x143ED0F20 Basic::ApplyAction` 在 `0x143ED11D2` 调 `FVoxelRenderUtilities::GetMeshesToBuild`，该调用的 PDB 签名同时包含 `FVoxelChunkMaterials`、`FVoxelChunkMesh`、`FVoxelProcMeshSectionSettings` 和 section mesh 数据。`0x143ED12B0` 构造 `FVoxelBasicMeshMergeWork`，`0x143ED13CC` 亦有 action 入队路径。`0x143EDB290 MergeWork::DoWork` 于 `0x143EDB2E9` 调合并函数，随后在 `0x143EDB396–0x143EDB3AE` 把含配置、section settings 与 buffer 数组的结果节点压进 built-data 队列。这里确认的是类型化结果流与队列写入，尚未把每个材质参数的创建公式还原。
3. `0x143EF3AE0 Basic::Tick` 顺序调用 `0x143EDFA20 FlushBuiltDataQueue` 与 `0x143EDE850 FlushActionQueue`。前者从队列取 `FChunkBuiltData`，经 `0x143EDFA83` 的移动赋值，在 `0x143EDFB90–0x143EDFBEF` 核对活着的 chunk 槽/对象后把 built-data 指针写入该 chunk info `+0x58`，旧指针按类型化 section 数组析构。后者在 `0x143EDEA7F–0x143EDEA92` 从同一 chunk info `+0x58` 取走数据并清空槽；若需要新组件，`0x143EDEADF` 调 `IVoxelRendererMeshHandler::GetNewMesh`。该函数在 `0x143EE4FEC` 创建 `UVoxelProceduralMeshComponent`，`0x143EE5064` 注册，`0x143EE5229` 初始化，`0x143EE52B0` 设置 chunk 范围。不能把每次更新都写成创建新组件，因为已有组件可复用。
4. 对取出的 built-data，`FlushActionQueue` 按 **24 字节 mesh-config 元素**遍历，其内部 section 数组按 **32 字节元素**遍历（`0x143EDEAA9–0x143EDEAB5`、`0x143EDEC58–0x143EDEC64`）。每个非空 buffer 的 section settings 前 16 字节从结果元素 `rdi` 复制到调用参数（`0x143EDEC85–0x143EDECB4`），于 `0x143EDECC7` 调 `UVoxelProceduralMeshComponent::AddProcMeshSection`，最终在 `0x143EDECD8` 调 `FinishSectionsUpdates`。`AddProcMeshSection` 自身于 `0x143ED0DDD` 调 `SetProcMeshSection`；`SetProcMeshSection` 先检查索引，再于 `0x143EF10D4–0x143EF1115` 把传入 settings 的首个共享引用和字段存入组件 `+0x590` 的 section 数组（**40 字节一项**），于 `0x143EF1176–0x143EF11E9` 转移 mesh buffer 所有权。这是完成产物到可见组件的读写桥，并非只凭函数名推断。
5. `0x143EE3100 UVoxelProceduralMeshComponent::GetMaterial(index)` 对 `index<0` 返回 null；有效索引 `index < [component+0x598]` 时，以 `[component+0x590] + 40×index` 找 section，其首引用非空便于 `0x143EE3137` 进入 `FVoxelMaterialInterface::GetMaterial`。`FinishSectionsUpdates` 在 `0x143EDE520` 更新 bounds、`0x143EDE528` 标脏渲染状态，并在 `0x143EDE53D` 调 `UpdateCollision`；[05](05-task-lifetimes-growth-and-performance.md)已追其旧 cook 取消与新 cook 分支。由此材质查询、渲染提交与碰撞更新有明确组件接收点，但实际 GPU shader、运行时材质值和最终碰撞结果仍须另证。

**结构演算，非运行次数测量。** 假设一个被接受的 Basic chunk built-data 含 1 个 mesh-config、2 个非空 section buffer：外层步长 24 字节遍历 1 项，内层步长 32 字节遍历 2 项，调用 `AddProcMeshSection` 两次，然后一次 `FinishSectionsUpdates`。若它们在空组件中成为 section `0`、`1`，`GetMaterial(1)` 会从 `component+0x590+40` 的第二项取得 `FVoxelMaterialInterface` 并调用其 `GetMaterial`。这个演算只说明已证代码在给定输入下如何落点；实际 chunk 的 config/section 数、材质对象是否非空、是否走复用组件路径均未观察。

## 矿物网格、材质和局部更新的边界

**实际游戏网格连接已证：** [04](04-mesh-materials-and-ore-presentation.md)的 `BP_OreSpawner` 煤层候选经 `Actor.AddComponent` 创建 `StaticMeshComponent`，其 `SetStaticMesh` 煤分支 import `-180` 与实际 `SM_Ore_Coal.uasset` 的 StaticMesh public export hash 相连；网格包 import `-5` 指向 `/Game/Art/Materials/M_Ores_1-3`。本次没有补出 `StaticMesh` 的 slot 数组、slot→材质 import 的索引或运行时材质覆盖，因此 **`M_Ores_1-3` 仍只是包依赖，不是已证的最终材质绑定**。`DestroyOre` 操作的是组件，不能从 `K2_DestroyComponent` 反推出该组件原先用了哪个材质实例。

**插件重建路径已接到组件，但未接到此矿物分支：** 上节已把通过完成门的 `UpdateChunk` 接到 Basic handler 的 built-data、section settings/buffer、组件材质查询与渲染/碰撞更新；这是**编入本作 EXE 的 Voxel 插件能力**。现有蓝图证据没有显示 `DestroyOre` 对该 renderer 发送 chunk 更新，也未证实煤矿 `StaticMeshComponent` 与 voxel `UVoxelProceduralMeshComponent` 共用材质、碰撞或生命周期。VoxelWorld 运行配置是否选择 Basic/Clustered/Mixed、具体材质设置及碰撞旧结果最终接受条件仍未证。

独立实现可把“命中对象是否矿物”的判定建立在显式组件类别或稳定实例 ID 上，并在实例移除时协调可见组件、存档身份与地形编辑。此为面向自研产品的设计建议，不是原作意图；矿物网格和材质仍须自行制作或获得许可。

**Answered（静态）：** `DestroyOre` 名称检查的 true/false 跳转、`0x4d` 的操作码身份、false 分支销毁调用；Voxel Basic handler `UpdateChunk → ApplyAction → MergeWork built-data → FlushActionQueue → AddProcMeshSection → GetMaterial/FinishSectionsUpdates` 的生产消费桥。**Unresolved（静态）：** true 分支确切执行流栈续点、矿物 StaticMesh 材质 slot/实例绑定、游戏选择的 Voxel mesh handler/材质配置、材质参数来源与着色公式、煤矿组件与 Voxel chunk 更新是否联动、碰撞旧结果最终接受检查。**Not Run（运行）：** 启动或附加游戏、命中/采掘验证、材质及 GPU 抓帧、碰撞或 FPS 实测；未读取个人存档。
