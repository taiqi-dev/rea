# 挖掘值场与局部重建：静态证据

## 范围与证据级别

目标是 `C:\Software\Steam\steamapps\common\A Game About Digging A Hole` 中的 `DiggingGame/Binaries/Win64/DiggingGame-Win64-Shipping.exe`（145,180,160 字节）及同目录 PDB（1,659,662,336 字节）。本文把这一安装版本里**已编入的 Voxel Pro 原生编辑路径**与已恢复的游戏 Blueprint 字节码连接起来。`Manifest_UFSFiles_Win64.txt:4464-4465` 列有 `CubicDestruction_FirstPersonCharacter`，`:4479-4484` 列有炸药和爆炸 Blueprint，`:4580` 列有 `MainLevel`。已解包资源，并用仓库 `tools/zen_probe.py` 索引对象、用 `tools/blueprint_probe.py` 解析有关函数；**没有运行游戏**。字节码能证明分支和调用参数来源，不能证明一次实际操作必定满足条件、真实参数值、网格算法或帧耗。

地址均为该 EXE 的首选映像基址下的 VA，函数大小来自同目录 PDB，经仓库 `tools/pdb_probe.py` 用本地 DbgHelp 查询；相关字节由 Visual Studio `dumpbin /DISASM /RANGE` 有界读取。原始符号与指令保存在 `.cache/procedural-modeling/digging-a-hole/digging/` 的 `symbols-sphere.json`、`symbols-chunks.json`、`symbols-tasks.json`、`symbols-mesher.json` 及对应 `*-disasm.txt`。PDB 名称负责定位，下面的数值和调用关系均以 EXE 指令复核。静态路径证明代码能力和分支，不证明这些分支在游玩时发生。

## 球形挖除的原生路径

**观察**：`UVoxelSphereTools::RemoveSphere`（`0x1441AC070`，1238 字节）先检查世界对象可用性，调用 `FVoxelToolHelpers::GetRealPosition`（`0x1441AC1F7`）和 `GetRealDistance`（`0x1441AC20C`）把输入位置、半径转换到体素坐标。它用 `center ± (radius + 3)` 构造 `FVoxelIntBox`，检查三轴边界非空，给 `FVoxelData::Lock` 写锁（`0x1441AC33C`），再调用 `FVoxelSphereToolsImpl::RemoveSphere<TVoxelDataImpl<FModifiedVoxelValue,FModifiedValueDummy>>`（`0x1441AC3A4`；被调函数 `0x143FAB280`，314 字节）。写入结束后 `Unlock`（`0x1441AC415`）；只有对应的 `bUpdateRender` 布尔参数为真时才调用 `FVoxelToolHelpers::UpdateWorld`（`0x1441AC45F`）。包装器还保留被修改值的输出路径，不能把“无可见更新”误当成“无数据修改”。依据：`remove-sphere-api-disasm.txt`。

**观察**：内部 `RemoveSphere` 又构造 `center ± (radius + 3)` 的写入盒，并把 `(radius + 2)^2` 与 `max(radius - 2, 0)^2` 传给 `TVoxelDataImpl::Set`（`0x143FAB38A`）。它将点位 `(x,y,z)` 送入 `SphereEdit<0>` 的逐点回调（`0x144159060`，242 字节）。该回调计算三轴平方距离 `d²`：

- `d² > (r+2)²`：保持旧值；
- `d² ≤ max(r-2,0)²`：写入有符号 16 位最大值 `32767`；
- 过渡层：先算 `0.5 × clamp(r - sqrt(d²), -2, 2)`，乘以 `32767` 并量化到短整数，再与旧值取较大者。量化指令涉及加 `0.5`、截断与负数修正，整数临界值应以原指令为准。

这是从 `remove-sphere-disasm.txt` 与 `remove-sphere-lambda-disasm.txt` 推导出的原生数值语义。`max(old, new)` 表明该过渡层只向“挖空”的符号方向推进；反向填充须走另一编辑操作。这里的距离和 `±2/±3` 均是**体素空间**数值，不是已经证实的世界厘米或玩家铲子尺寸。体素值符号与最终材质、表面位置的关系还要结合世界生成器和实际配置核对。

角色资源 `CubicDestruction_FirstPersonCharacter.uasset` 同时导入 `VoxelSphereTools.RemoveSphereAsync`（package index `-316`）与 `VoxelSurfaceEditTools.EditVoxelValuesAsync`（`-318`），以及 `FindSurfaceVoxels`、`ApplyConstantStrength`、`ApplyFalloff`、`ApplyStack` 等表面编辑函数（`-320` 至 `-324`）。这些导入曾只是调用候选；下文另以完整字节码确认具体位置，避免把不同挖掘分支强行归为同一个公式。

**观察**：异步 `UVoxelSphereTools::RemoveSphereAsync`（`0x1441AC550`，1230 字节）先换算坐标与半径。其工作 lambda（`0x144160250`，366 字节）在数据锁内于 `0x14416030F` 调用**与同步版相同的** `FVoxelSphereToolsImpl::RemoveSphere`（`0x143FAB280`），解锁后，latent action 的完成回调（`0x14416E510`，187 字节）在 `0x14416E5B6` 调用 `FVoxelToolHelpers::UpdateWorld`。这支持上述球形 SDF 公式也适用于该异步插件入口；仅凭此原生实现不能证明游戏调用；后文给出角色字节码的独立调用证据。工作与可见更新相隔几帧仍未知。依据：`remove-sphere-async-disasm.txt`、`remove-sphere-async-lambda-disasm.txt`、`remove-sphere-async-complete-disasm.txt`。

**构造演算**：假设输入已经转换为 `r=6` 个体素单位，中心附近一点 `d=3` 满足内核阈值 `d²≤16`，被写成 `32767`；`d=6` 位于过渡层中线，候选值约为 `0`，再与旧值取较大者；`d=7` 的候选约为 `-16383`，仍只在高于旧值时改写；`d>8` 的点完全不改。写入候选盒大约覆盖中心各轴 `±9`，比半径 `8` 的外边缘多留一个体素单位。此例展示指令公式，**不是游戏实际半径、每铲产量或实测画面**。

## 表面编辑的另一条原生能力

**观察**：`UVoxelSurfaceTools::FindSurfaceVoxels`（`0x1441D66D0`，787 字节）持读取锁，调用 `FindSurfaceVoxelsImpl<0>`（`0x1441C5A00`，668 字节）。它先从候选盒批量读取有符号 16 位体素值；内部扫描 lambda（`0x1441C08B0`，710 字节）跳过采样盒外层，在内层逐点比较中心与六个轴向邻居的符号：按 `value > 0` 分类，**任一邻居分类不同**才加入表面候选。存入的中心值乘 `1/32767` 归一化。依据：`find-surface-disasm.txt`、`find-surface-impl-disasm.txt`、`find-surface-lambda-a-disasm.txt`。这是一种局部符号交界筛选，并非先求精确几何表面的所有交点；传入盒子的运行时尺寸及完整边界补偿方式仍未确认。

`UVoxelSurfaceTools::ApplyConstantStrength`（`0x1441CC710`，295 字节）的逐候选 lambda（`0x1441C0110`，155 字节）把每项 `+0x48` 的浮点编辑权重乘输入强度（`0x1441C0180`—`0x1441C0188`）。`ApplyFalloff`（`0x1441CC840`，1135 字节）按输入模式派发多种距离权重处理；本作虽已读取原始枚举参数，尚未对齐其名称和对应曲线公式。`AddToStack`（`0x1441CC620`，227 字节）和 `ApplyStack`（`0x1441CD710`，293 字节）让 `FVoxelSurfaceEditsStack::Execute`（`0x1441D4CE0`，856 字节）顺序作用所加变换并产出 processed voxels；`ApplyStack` 还先检查错误。依据：`apply-strength-disasm.txt`、`strength-lambda-disasm.txt`、`apply-falloff-disasm.txt`、`apply-stack-disasm.txt`、`stack-execute-disasm.txt`。这些函数组成可用的数据变换链，**本作采用的顺序和实参由下节的真实蓝图调用单独确认**。

`UVoxelSurfaceEditTools::EditVoxelValuesAsync`（`0x144190970`，1214 字节）从世界构造 `FVoxelHardnessHandler`、校验非空盒，异步工作 lambda（`0x14415EDD0`，382 字节）在写锁内调用 `FVoxelSurfaceEditToolsImpl::EditVoxelValues`（`0x143F9F730`，201 字节）；完成回调与异步球形编辑共享 `0x14416E510` 的实现，在 `0x14416E5B6` 请求 `UpdateWorld`。逐点 lambda（`0x14414C5B0`，1492 字节）在普通有符号值分支取 `v=oldShort/32767` 和当前候选权重 `w`。若启用材质硬度，则读取对应材质、计算硬度 `h` 并以 `max(h, 0.0001)` 限住除数；随后按指令形成 `(v + w/h)/q`（未启用硬度时为 `(v+w)/q`），其中 `q` 是传入 `EditVoxelValues` 的另一个浮点参数。它把结果钳到 `[-10,10]`，乘 `32767`，量化并钳到有符号短整数范围。此处有替代旧值来源与不同材质模式分支，`q` 的 Blueprint 引脚语义和游戏硬度配置尚未确定，因此不能把简式用作所有输入的精确公式。依据：`edit-values-async-disasm.txt`、`edit-values-async-lambda-disasm.txt`、`edit-values-impl-disasm.txt`、`edit-values-lambda-disasm.txt`、`remove-sphere-async-complete-disasm.txt`。

**构造演算，非游戏实测**：取一个符号边界候选，旧值约为 `-0.25`，六邻居之一为正值，故它被筛入；若处理后的 `w=0.5`、硬度关闭、`q=1`，普通分支新值约为 `+0.25`，即量化后约 `+8192`。这与球形 `RemoveSphere` 的“以内核/过渡壳直接写候选 SDF”不同：表面路径先筛符号交界，再对候选权重作强度/衰减和可选硬度计算，最后编辑值场。实际的 `w`、旧值与材料配置尚未量到；下节能确认本次蓝图 `EditVoxelValuesAsync` 调用传入的浮点实参为 `1.0`。

## 游戏 Blueprint：Dig 的表面链与爆炸的球形链

**观察**：角色 `ExecuteUbergraph_CubicDestruction_FirstPersonCharacter` 的字节码解析**完整**：物理脚本 `167,815/167,815` 字节、逻辑脚本 `115,747/115,747` 字节；`Dig` 小函数也完整，直接跳到主图逻辑偏移 `68297`。该入口在 `68307` 对 `DrillUnlocked?` 作条件跳转，未跳走的分支在 `68321` 调 `SurfaceEdit`；后者小函数跳到 `85193`。因此可确认 **Dig 有条件地进入 SurfaceEdit**，不能把角色图中其他偏移的 `RemoveSphereAsync` 自动归给 Dig。依据：`digging/character-dig.json`、`digging/character-surfaceedit.json`、`digging/character-ubergraph.json`，均为本机忽略目录下可复核的结构化解码。

`SurfaceEdit` 入口区域里，字节码先用 `DrillStrengthAfterNerf × Delta Seconds × 60.0` 构造 `ApplyConstantStrength` 的输入（逻辑偏移 `85396`、`85442`、`85517`），并在 `85554` 加入栈。`DigRadius` 被转换为 `ApplyFalloff` 半径；后者调用在 `85671`，同时接收 `Ref_VoxelWorld`、`HitLocation`、原始枚举数 `1` 和浮点 `0.5`，随后在 `85734` 加入栈。`MakeIntBoxFromGlobalPositionAndRadius`（`86030`）也用 `HitLocation` 与 `DigRadius` 构造候选盒；`FindSurfaceVoxels`（`86067`）筛选候选，`ApplyStack`（`86123`）生成 processed voxels，`EditVoxelValuesAsync`（`86167`）在 `Ref_VoxelWorld` 上提交，传入另一个浮点实参 `1.0`。这里能证实**参数来源、函数顺序与一条实际蓝图执行链**；`DigRadius` 和 `DrillStrengthAfterNerf` 的运行时数值、衰减枚举 `1` 的准确名称、硬度配置、分支被触发的频率仍未知。前述构造演算的 `q=1` 与这个调用的浮点实参相同，但 `w`、旧值及硬度条件只是演示输入。

另两份爆炸资源的主图也完整解析。`BP_Explosion` 为物理 `2,852/2,852`、逻辑 `1,936/1,936` 字节：`Cylinder.K2_GetComponentLocation` 的结果送入 `VoxelSphereTools.RemoveSphere`（逻辑偏移 `1869`，包内文件偏移 `11442`），半径来自属性 `ExplosionRadius` 的数值转换（`1829`），世界来自 `Ref_VoxelWorld`，后四个布尔实参均为 `true`。`BP_Dynamite` 为物理 `6,488/6,488`、逻辑 `4,560/4,560` 字节：另一处 `RemoveSphere`（逻辑 `533`，文件 `14327`）同样接 `Cylinder` 位置、`ExplosionRadius`、`Ref_VoxelWorld` 与四个 `true`。依据：`.cache/procedural-modeling/digging-a-hole/explosion-blueprint.json`、`digging/dynamite-ubergraph.json`。这证实**爆炸蓝图的球形挖除调用**，但未证明两种爆炸对象在一次事件中都会出现，亦未读取属性实际默认半径或观察运行触发。

角色主图还确有 `RemoveSphereAsync` 调用（逻辑偏移 `8814`，文件 `234152`，传入 `Ref_VoxelWorld`、计算中心与半径引脚），其后邻近四次 `SmoothSphere` 调用（`9160`、`9468`、`9776`、`10107`）。这是**另一段角色字节码**；当前未把它的入口事件和 `Dig` 入口 `68297` 连成同一控制流，不能据此改写上述常规 Dig 的表面链。该异步调用的本地实现确实复用同步版球形内核，如前节所证。

## 从脏区到局部网格

**观察**：`FVoxelToolHelpers::UpdateWorld`（`0x1441DFDA0`，79 字节）将编辑盒交给世界所持有的更新接口；直接调用是虚表槽，不能单凭此函数给实现类下结论。相邻的局部更新实现显示：`FVoxelDefaultLODManager::UpdateBounds`（`0x143E97870`，554 字节）对输入边界逐一调用 `FVoxelRenderOctree::GetChunksToUpdateForBounds`（`0x143E72DF0`，261 字节）。后者先做三轴 AABB 相交检查；非相交节点直接返回，满足节点标志条件时追加 chunk ID，并沿存在的子节点递归。它还在该标志分支广播边界事件；标志位的准确语义未还原。依据：`update-world-disasm.txt`、`lod-update-bounds-disasm.txt`、`octree-dirty-disasm.txt`。这说明插件有“按影响盒筛 chunk”的路径，不代表每次游戏挖掘都走它。

`FVoxelDefaultRenderer::UpdateChunks`（`0x143EF53B0`，1666 字节）管理 `FPendingUpdate`，调用 `StartTask`、`FlushQueuedTasks`，并处理待移除或显示的 chunk。`StartTask<1,0>`（`0x143EC4F70`，661 字节）与 `<0,0>`（`0x143EC5210`，267 字节）可构造 `FVoxelMesherAsyncWork`。其 `DoWork`（`0x143EDBEB0`，1374 字节）调用 `GetMesher`；后者（`0x143EE3760`，741 字节）含 Surface Net、Cubic、Marching Cube 等选择分支。任务生成的 mesh 可经 `IVoxelRendererMeshHandler::UpdateChunk`（`0x143EF5300`，166 字节）提交，空/无效 chunk 可走 `RemoveChunk`。依据：`update-chunks-disasm.txt`、`start-task-1-disasm.txt`、`start-task-0-disasm.txt`、`mesher-dowork-disasm.txt`、`get-mesher-disasm.txt`。尚未取得世界实例配置和 mesher 选择的实例证据，**不能指定本作采用哪一个 mesher，也不能把异步任务存在等同于稳定帧耗或全部碰撞已更新**。

**观察**：插件的 `UVoxelProceduralMeshComponent::SetProcMeshSection`（`0x143EF1090`，550 字节）可调用 `FinishSectionsUpdates`（`0x143EDDF20`，1864 字节）。后者更新局部边界、标记渲染状态，并在 `0x143EDE53D` 调用 `UpdateCollision`（`0x143EF5A40`，637 字节）。碰撞更新先检查全局冻结开关、将组件加入待处理集合、取消旧异步工作，再设置新的 `BodySetup`；其中有同步完成分支和构造 `FVoxelAsyncPhysicsCooker_Chaos` 的分支。`FinishCollisionUpdate`（`0x143EDDE80`，148 字节）调用 `RecreatePhysicsState`。依据：`set-section-disasm.txt`、`finish-sections-disasm.txt`、`collision-update-disasm.txt`、`collision-finish-disasm.txt`。这证明组件级网格提交**可以**串到碰撞重建；本次还没有把特定游戏挖掘输入、具体 handler、碰撞配置与每次任务完成一一连起，所以碰撞刷新时机、是否滞后于可见网格及旧任务失效条件仍未证实。

## 自研可用的独立规格与续查

若自研可挖地形，建议把一次操作定义为中心、半径、强度和世界版本号，先在体素数据所有者处原子提交受影响格点，再从实际变更盒筛与其相交的 chunk，按优先级派发可取消的网格与碰撞任务；提交结果时核对世界版本，避免旧任务覆盖新洞。这是**自研建议**，不是目标游戏已经证实的版本戳、取消或碰撞策略。性能预算应分别测量体素写入格点数、重建 chunk 数、任务排队时间、网格生成 CPU、碰撞准备时间及主线程提交；仅凭 PDB 和静态指令不能给出 FPS、毫秒或内存用量。

尚需的关键证据是：把角色图 `RemoveSphereAsync` 的入口归属与触发条件单独还原；读取角色与爆炸对象在实际存档/游戏状态中的半径、强度及硬度参数；取得世界属性 schema 后读取体素大小、mesher 与碰撞配置；必要时在独立获准的运行场景观察一次挖掘前后的数据及任务顺序。现有完整 Blueprint 字节码和 native 指令已经证明**Dig 条件进入表面编辑链、爆炸蓝图含球形挖除链**，但不足以报告每铲实际修改量、画面/碰撞刷新时机或运行性能。
