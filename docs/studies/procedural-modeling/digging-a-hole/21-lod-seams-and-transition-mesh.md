# 掘地求财：LOD 相邻块、过渡网格与碰撞覆盖

后续[22：过渡三角形的碰撞归属](22-transition-triangles-and-collision-ownership.md)补出普通／过渡索引合并到同一主buffer并被cooker读取的条件链。本文当时未答的buffer归属已收窄，真实mesh模式与物理接缝仍未运行验证。

接续[20：LOD 到网格和碰撞的刷新边界](20-partial-restore-lod-mesh-collision.md)。本篇只追 **render octree 中相邻的两个不同层级**如何形成六方向接缝标志、该标志怎样进入单独的过渡网格任务，以及结果到 section 和碰撞时还需什么条件。以下都是发行制品的静态指令推导；未观察画面、GPU 或物理接触。

## 身份与可复核原文

目标为 `C:\Software\Steam\steamapps\common\A Game About Digging A Hole\DiggingGame\Binaries\Win64\DiggingGame-Win64-Shipping.exe`（PE32+ x64，145,180,160 字节，首选基址 `0x140000000`）及同目录 PDB（1,659,662,336 字节）。[00](00-evidence-and-reproduction.md)已用 RSDS GUID/age 核对两者；本轮重新只读核对字节长度及 GUID `b6f613a8-3359-3fae-499f-16304cd0e880`、age `1`，结果 `guid_and_age_match=true`（新 `pdb-identity.json`），但复用先前摘要记录，**没有新算内容摘要**。同一包中 `MainLevel` 的静态世界字段 `RenderOctreeDepth=6`、`MaxLOD=4`、`VoxelSize=9.0` 和 Mixed 初始处理器推导复用[07](07-material-slots-and-handler-selection.md)；实际游玩 chunk 布局、mesher 模式和开关状态未读到。

本轮以[现有 PDB 探针](tools/pdb_probe.py)只在本地 EXE 目录查询符号：`*FVoxelRenderOctree*` 为 27/27、`*FVoxelMesherAsyncWork*` 为 14/14、`*FVoxelDefaultRenderer*` 为 79/79、`*Transvoxel*` 为 7/7，均 `exhausted=true`。宽泛 `*Transition*` 为 1562/1562，但包括大量无关系统，**不将命中数当作体素机制数量**。新增局部指令由 VS 2022 `dumpbin 14.44.35222.0 /DISASM /RANGE` 读取，位于 ignored [static-art-followup/digging-a-hole/](../../../../.cache/procedural-modeling/static-art-followup/digging-a-hole/)：`lod-symbols.json`、`transition-symbols.json`、`octree-adjacent.disasm.txt`、`octree-updates.disasm.txt`、`renderer-lods.disasm.txt`、`renderer-starttask.disasm.txt`、`mesher-ctor.disasm.txt`、`mesher-work.disasm.txt`、`marching-transition-template.disasm.txt`、`marching-transition-dir1.disasm.txt`、`marching-transition-full.disasm.txt`、`transition-bounds.disasm.txt`、`translated-transvoxel.disasm.txt` 等。复用既有 `static-slot-followup/digging-a-hole/mesher-get.disasm.txt` 及[05](05-task-lifetimes-growth-and-performance.md)、[08](08-mixed-handler-submission-chain.md)、[09](09-collision-result-acceptance.md)的接收路径。它们是普通 PDB/PE 文件读取，**不是 REA Evidence**；下文地址均为 EXE 首选 VA，不能当实时地址。

## 可见邻块到六方向 mask

`FVoxelRenderOctree::GetVisibleAdjacentChunk`（`0x143E7F130–0x143E7F2FE`）从当前节点 `+0x0C` 的层级计算宽度 `S=32 << L` 和 `S/4`。六个方向各取一个相邻空间查询点；例如方向值 `2` 对应正 X，点是 `origin+(S+S/4, S/4, S/4)`（`0x143E7F1BE–0x143E7F1DA`）。函数先检验点落在根 AABB 内，再沿有子节点的八叉树向下，返回停止处的可见节点指针；越界返回空。这个单点查询找到的是**候选可见邻节点**，还需调用方的盒交集检查，不能仅由函数名断言完整面邻接。

`FVoxelRenderOctree::GetUpdates`（`0x143E7ABA0–0x143E7B23A`）先限于当前节点与请求盒相交；可见位与相关 settings 门通过后，分别以 `1,2,4,8,16,32` 六个值查询邻节点（`0x143E7AE90–0x143E7B0CA`）。对每个非空邻节点，代码再把邻节点 AABB 与这次 settings 的盒作三轴严格交集比较。例如正 X 分支 `0x143E7AF1A–0x143E7AF4D`；交集失败不置该方向位。其后 `settings+0x36` 控制深度比较方向：为零时用 `neighbor.L < current.L`，非零时用 `neighbor.L > current.L`（正 X 的 `0x143E7AF4F–0x143E7AF6B`），比较成立才把 bit `2` 或入新的方向 mask。六个方向使用同样形状的判断。代码没有在此要求深度差**恰好为 1**；相邻层级差上限如由其他构树规则保证，不能由这段独自保证。

节点旧可见/用途位 `+0x48` 与旧方向 mask `+0x49` 同新值比较（`0x143E7B142–0x143E7B169`）。任一相关位变化，且旧或新节点有用途位，便组装 `FVoxelChunkUpdate`，携节点 key、LOD、空间盒和旧/新两字节标记（`0x143E7B182–0x143E7B216`）。这说明**仅接缝 mask 改变也能形成 update**；并不证明每个 update 必新建网格。异步 builder `DoWork` 于 `0x143E6CD39` 调 `GetUpdates`，实际 manager/renderer 接收仍受[20](20-partial-restore-lod-mesh-collision.md)的类型、状态和任务门约束。

## update 到过渡几何

`FVoxelDefaultRenderer::UpdateLODs` 于 `0x143EF5E10–0x143EF5E4A` 读取 update 的旧/新两字节标记，把新值写入当前 chunk `+0x76/+0x77`；只有当前 chunk key 可解析且状态分支接受，后续才调 `StartTask`／`ApplyPendingSettings`（例如 `0x143EF61BB–0x143EF61F9`）。`StartTask<1,0>` 的构造支路把 chunk `+0x77` 的方向 mask 作为任务参数，并把布尔 `1` 交给 `FVoxelMesherAsyncWork`（`0x143EC5139–0x143EC515D`）；另一个 `StartTask<0,0>` 是普通网格槽。任务构造将这两个字节写在 `+0x89` mask、`+0x88` 种类（`0x143EC6FD9–0x143EC6FEC`）。`DoWork` 在 `0x143EDBF24–0x143EDBF52` 原样取出两个字节，传给 `GetMesher`。这一链证明方向选择进入过渡构网的**任务输入**，不是只设置材质或渲染器状态。

`FVoxelMesherAsyncWork::GetMesher`（复用既有 `mesher-get.disasm.txt`，`0x143EE3760–0x143EE3A44`）先按 renderer settings `+0x4D` 选择三种已编入分支：值 `0` 为 Marching Cube，`1` 为 Cubic，`2` 为 Surface Net。布尔参数为真时，前两种各构造对应 `TransitionsMesher`，并把方向 mask 写入 mesher `+0x40`（Marching Cube 的 `0x143EE39D6–0x143EE39FA`）；Surface Net 分支没有同型 transition mesher，而是另一条处理路径，`StartTask` 也能调用 `SetTransitionsMaskForSurfaceNets`（`0x143EC4F8D–0x143EC4FA6`）。因此不能把本作**实际所选**算法简写为 Marching Cube 或 Transvoxel；包字段尚未把本关卡的 `+0x4D` 动态值定下来。

在 Marching Cube 条件分支内，`FVoxelMarchingCubeTransitionsMesher::CreateGeometryTemplate`（`0x143EAEC50–0x143EAEE0A`）为体素数据建立覆盖边界的 accelerator，并调用六个按方向专门化的 `CreateGeometryForDirection<1/2/4/8/16/32>`；每个方向函数先测试自身 `mesher+0x40` 的对应位，例如方向 `1` 的 `0x143EA4C09`。该函数以 `2*i`、`2*i+1`、`2*i+2` 组装面内采样坐标（`0x143EA4C40–0x143EA4C68`），用 `TVoxelDataAccelerator::Get` 读取该版体素值，并建立顶点/索引；`CreateFullChunkImpl` 再做材质、法线/切线和 `CreateChunkFromVertices`（`0x143ED9158–0x143ED95BF`）。`GetBoundsToLock` 的边界从 `origin-S/32` 到 `origin+34*(S/32)`，即相对 32 单元 chunk 在各轴多一单元采样余量（`0x143EE1DD0–0x143EE1E6E`）。`GetTranslatedTransvoxel` 在 `0x143EE6F52–0x143EE702F` 以 `1<<LOD` 和 `32<<LOD` 检查顶点是否在边界、按六方向位分支；`0x143EE70FA–0x143EE71E8` 再以输入向量和这些边界差量计算新位置。故这条路径包含**边界采样、过渡拓扑和顶点位置调整**。这里尚未逐表验证它是否遵循某个标准 Transvoxel case table，也未证明屏幕上无裂缝；`GetTranslatedTransvoxel` 的名称不是标准算法符合性证据。

## 一个相邻层级对的贯通演算

**构造演算，非本作运行实例。** 取一个 LOD 2 当前块，原点 `(0,0,0)`、边长 `S=32<<2=128`，其正 X 面外有 LOD 1 可见块，盒为 `[128,192)×[0,64)×[0,64)`；假设 settings 查询盒与两者有体积交集，相关可见/用途和过渡开关已开，`settings+0x36=0`，且当前 renderer 可接收更新。`GetVisibleAdjacentChunk(direction=2)` 的查询点为 `(160,32,32)`，落在该细层块中。`neighbor.L=1 < current.L=2`，所以 `GetUpdates` 的正 X 位 `0x02` 置入新 mask；若旧 mask 是 `0`，旧/新标记不同，可生成 chunk update。默认 renderer 接受该 update 后，把 `0x02` 写入 chunk `+0x77`；过渡任务构造保存至 `+0x89`。若本例再**假设** renderer mode 为 Marching Cube，`GetMesher` 把 `0x02` 写入过渡 mesher `+0x40`，仅对应正 X 的方向构网分支获得该标志，随后取边界体素值、建三角形并调整边界顶点。若 `settings+0x36=1`，同一 `1<2` 深度关系不会通过该方向门；若邻块缺失、盒不相交、chunk key 过期或任务/完成门失败，这条演算会在相应节点停止。这里的原点、可见块、settings 和 mode 都是**显式假设**；`MainLevel` 的 `MaxLOD=4` 只说明这个层级对在配置范围内，不说明游戏当时确有该相邻对。

## 视觉接缝与碰撞是不同资格

过渡顶点/三角形属于网格生成阶段；**视觉接缝可能有几何，却不能从 mask 推出物理覆盖**。已核对的后段是：[20](20-partial-restore-lod-mesh-collision.md)中 `ProcessMeshUpdates` 先核当前 chunk、任务槽和 `task+0x68` 完成令牌；[08](08-mixed-handler-submission-chain.md)中 Mixed 在 MainLevel 静态初始条件下把可见 bit `0` 送 Clustered，把碰撞 bit `1`／导航 bit `2` 送 Basic；`GetMeshesToBuild` 的 section settings、材质/缓冲区还须非空有效；section 碰撞资格最终由 `UVoxelProceduralMeshComponent::UpdateCollision` 读 section `+0x10`。若有碰撞 section 且进入异步 Chaos cooker，[09](09-collision-result-acceptance.md)的弱组件、当前 cooker 编号、任务状态与 BodySetup 门通过后才 `Finalize → FinishCollisionUpdate → RecreatePhysicsState`。这是一条**条件调用路径**，不是游戏内实际碰撞接缝连续性的测量。当前没有逐 section 证明“过渡三角形一定被收进碰撞网格”或“一定被排除”；这点保持 Unknown，而不拿可见/碰撞标志的名字替代 buffer 内容核验。

**Answered（静态）**：邻节点查询点、根界/子树选择、交盒和深度方向门、六方向 mask 与 update 变化门、update 到 chunk/过渡任务/mesher 的字节传播、Marching Cube 条件路径的边界数据采样和顶点调整，及碰撞独立资格链。**Partial**：过渡开关和 `settings+0x36` 在本关卡实例的最终值、当前 render octree 是否形成构造中的相邻对、实际 mesher mode、标准 Transvoxel 表符合性、section buffer 中过渡三角形的碰撞归属。**Unknown / Not Run**：真实画面是否无缝、物理表面是否连续、实际任务顺序/耗时/GPU 与碰撞结果；没有启动、附加、执行游戏或函数，没有读取私人存档，也未重试先前未变的 Ghidra timeout。下一次纯静态优先追 `GetMeshesToBuild` 的主/过渡 `FVoxelChunkMesh` 输入及其碰撞 buffer 取用，才能收窄最终碰撞接缝覆盖。
