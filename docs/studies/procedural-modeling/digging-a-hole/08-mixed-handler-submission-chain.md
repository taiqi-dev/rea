# 掘地求财：Mixed 处理器的渲染、碰撞与完成提交

[07](07-material-slots-and-handler-selection.md)从 `MainLevel` 的 `VoxelWorld` 属性与本作原生构造代码推导出静态初始设置会选 `FVoxelRendererMixedMeshHandler`。本篇沿**这个条件下已编入 EXE 的 Mixed 分支**继续追踪：Mixed 将可见网格送入 Clustered 合并支路，将碰撞和导航网格送入 Basic 支路；两侧各自完成、接收和清理。它补充了[06](06-mesh-material-binding-and-edit-lifecycle.md)只追 Basic 可用能力的边界。未启动或附加游戏，不能把静态路由写成运行时每次挖掘均已观察到。

## 输入与核对方式

发行 EXE/PDB、只读范围和身份沿用[00](00-evidence-and-reproduction.md)。复用[05](05-task-lifetimes-growth-and-performance.md)的 `FVoxelDefaultRenderer::ProcessMeshUpdates` 上游 chunk key／任务槽令牌门、[06](06-mesh-material-binding-and-edit-lifecycle.md)的组件 section 接收指令，以及[07](07-material-slots-and-handler-selection.md)的实例配置。新原文位于 ignored `.cache/procedural-modeling/static-submission-followup/digging-a-hole/`：匹配 PDB 精确掩码 `*FVoxelRendererMixedMeshHandler*` 返回 `15/15`、`*FVoxelRendererClusteredMeshHandler*` 返回 `34/34`、`*FVoxelClusteredMeshMergeWork*` 返回 `8/8`，均 `exhausted=true`；`dumpbin /DISASM /RANGE` 只读取下述函数范围。`mixed-*.disasm.txt`、`clustered-*.disasm.txt`、`sceneproxy-*.disasm.txt`、`component-nav-export.disasm.txt` 与相应 `*-symbols.json` 保存可逐条核对的静态指令。下列地址是该 EXE 的 VA；没有将 PDB 名称单独当作行为证据。

## Mixed 分派：三个标记位到两个子处理器

**观察。** `FVoxelDefaultRenderer` 构造代码 `0x143EC649A` 选 Mixed 时，`NewIntrusiveReferenceController<FVoxelRendererMixedMeshHandler>` 在 `0x143EC3218–0x143EC3234` 创建 Basic 并保存到 Mixed 对象 `+0xB0`，在 `0x143EC3271–0x143EC328D` 创建 Clustered 并保存到 `+0xC0`。`FVoxelRendererMixedMeshHandler::ApplyAction`（`0x143ED1CC0`）对更新动作的 settings 低位进行两次分派：`0x143ED1E00` 测试 `flags & 0x06`，非零就把**清掉 bit 0** 的动作经 Basic 虚表 `+0x38` 送入 Basic；`0x143ED1EF7` 测试 `flags & 0x01`，非零就把**清掉 bits 1–2** 的动作经 `0x143ED1F6E UpdateChunk` 送入 Clustered。首次需要时，`0x143ED1E29` / `0x143ED1F26` 分别走各子处理器虚表 `+0x30` 的 `AddChunk`，两个子 chunk ID 存在 Mixed chunk 项 `+0x10` / `+0x14`；无相应标记且已有子 chunk 时，分别在 `0x143ED1EEA` / `0x143ED1F80` 调 `RemoveChunk` 并清 ID。

标记语义由**同一数据在消费端的行为**核对，而非凭 `bDoNotMergeCollisionsAndNavmesh` 命名猜测。`FVoxelRenderUtilities::GetMeshesToBuild` 于 `0x143EE3D56–0x143EE3D98` 将 settings 的 bit 1、bit 2、bit 0 依次写到 section settings 的字节 `+0x10`、`+0x11`、`+0x13`。`UVoxelProceduralMeshComponent::SetProcMeshSection` 于 `0x143EF1151–0x143EF1172` 将这几个字节写进组件 section。随后，`UpdateCollision` 于 `0x143EF5BA0` 用 section `+0x10` 决定是否进入碰撞重建；`DoCustomNavigableGeometryExport` 于 `0x143EDB0D0` 用 `+0x11` 决定是否输出导航几何；场景代理构造于 `0x143EC7C7A` 把 `+0x13` 复制到代理项 `+0x30`，`GetDynamicMeshElements` 于 `0x143EE2010` 用该值决定是否走后续材质/绘制分支。因此 bit 1 是碰撞、bit 2 是导航、bit 0 是可见绘制的本作实际路径。

| 入口标记            | Mixed 子处理器          | 传下的标记      | 后续 section 用途                               |
| ------------------- | ----------------------- | --------------- | ----------------------------------------------- |
| `flags & 0x06` 非零 | Basic，`Mixed+0xB0`     | `flags & ~0x01` | 碰撞 `+0x10` / 导航 `+0x11`，可见位 `+0x13=0`。 |
| `flags & 0x01` 非零 | Clustered，`Mixed+0xC0` | `flags & ~0x06` | 可见位 `+0x13=1`，碰撞／导航位为零。            |

**构造演算，非实测。** 若一个被[05](05-task-lifetimes-growth-and-performance.md)上游门接受的 chunk 更新携带 `flags=0b111`，Mixed 分派给 Basic 的副本是 `0b110`，给 Clustered 的副本是 `0b001`。在各自 `GetMeshesToBuild` 产生非空 section 的前提下，Basic section 的 `(collision,nav,visible)` 为 `(1,1,0)`；Clustered section 为 `(0,0,1)`。这说明两个组件支路为何分别触发物理/导航与可见绘制；`0b111` 是说明分支的自造输入，不是对主关卡实际每个 chunk 设置的读取。

## 可见合并支路：cluster 结果的二次门与组件接收

**观察。** `Clustered::ApplyAction` 于 `0x143ED16C7` 对 chunk 找或建 cluster，`0x143ED1936` 对其网格／材质／section 配置调用 `GetMeshesToBuild`，`0x143ED1AE2` 创建 `FVoxelClusteredMeshMergeWork` 并在 `0x143ED1AFA` 提交后台工作。该 work 的 `DoWork`（`0x143EDB4C0`）从 cluster 的活动 chunk 集合遍历数据，在 `0x143EDB94C` 以 `FVoxelMeshConfig` 查找分组，`0x143EDBBB9` 再按 `FVoxelProcMeshSectionSettings` 汇集 section；`0x143EDBC91` 把这些分组交给合并构建 helper。结果节点大小 `0x28`，在 `0x143EDBD26–0x143EDBD43` 携 cluster 引用字段、序号和 built-data 指针进入 Clustered 的完成队列 `+0xB20`。这证明本作确有**跨活动 chunk 按配置汇集后建网格**的实现路径；未恢复该 helper 内的逐顶点/索引合并公式或测量输出节数。

`Mixed::Tick` 于 `0x143EF3BD6–0x143EF3BE1` 调 Basic 的 `FlushBuiltDataQueue → FlushActionQueue`，于 `0x143EF3C17–0x143EF3C22` 调 Clustered 的同两步。Clustered `FlushBuiltDataQueue` 在 `0x143EDFCB0` 取完成节点，只有 cluster 索引在范围且活动 bit 仍在（`0x143EDFDA0–0x143EDFDD6`）、节点引用的 cluster 指针等于当前槽中的指针（`0x143EDFDE0–0x143EDFDF8`）、结果序号 `S_result` 不小于 `lock cmpxchg` 读出的当前序号 `S_atomic`（`cmp [rbp-30h], eax; jl`，即 `S_result < S_atomic` 时跳过，`0x143EDFE04–0x143EDFE20`），才把 built-data 移入 cluster `+0x60`；否则跳回消费循环并释放节点/结果。这里的序号是可见的**本地新旧门**，本轮未证明它与[05](05-task-lifetimes-growth-and-performance.md)上游 task `+0x68` 令牌是同一版本号。

通过完成门后，`Clustered::FlushActionQueue` 在 `0x143EDF677–0x143EDF69B` 对本支路作有符号 32 位比较：只有 cluster `+0x50` 的已接收序号 `<` 动作序号 `S_action`，且 `S_action <=` cluster `+0x58` 的结果序号，才取出 `+0x60` 的 built-data；若 `S_action >` 结果序号，则转入 `0x143EDF979` 的旧结果失效路径。取出的指针为空时也不会提交 section。`0x143EDF6EC` 可新建 `UVoxelProceduralMeshComponent`，已有组件则通过弱引用复用；对每个 24 字节 mesh-config 结果，`0x143EDF7DF–0x143EDF85E` 以 32 字节步长搬运 section settings、材质引用和 buffer，于 `0x143EDF852` 调 `AddProcMeshSection`，于 `0x143EDF868` 调 `FinishSectionsUpdates`。该组件的 `GetMaterial(index)` 与 section 的 `FVoxelMaterialInterface` 消费关系已由[06](06-mesh-material-binding-and-edit-lifecycle.md)证明；Mixed 的可见支路至此接上**实际 section 材质引用和渲染状态更新**。配置/section 数由生成数据决定，不可从 `LODMaterials` 仅有一个条目推断每个 cluster 只有一个 section。

## 独立碰撞支路与失效清理

Mixed 的 `flags & 0x06` 支路进入 Basic 的 `UpdateChunk`，所以[06](06-mesh-material-binding-and-edit-lifecycle.md)已读的 `Basic::ApplyAction → FVoxelBasicMeshMergeWork → built-data 队列 → AddProcMeshSection → FinishSectionsUpdates` 在这里有了主关卡 Mixed 条件下的实际调用来源。Basic 的完成队列只在 chunk 槽仍活着时写入结果（[06](06-mesh-material-binding-and-edit-lifecycle.md) `0x143EDFB90–0x143EDFBEF`）；section 碰撞标记写入组件后，`FinishSectionsUpdates` 于 `0x143EDE53D` 调 `UpdateCollision`。该函数先取消旧异步 cooker（`0x143EF5ACD`），仅发现 section `+0x10` 非零才继续生成新碰撞数据（`0x143EF5BA0–0x143EF5C66`）；旧 cook 的处理能力和 `FinishCollisionUpdate → RecreatePhysicsState` 见[05](05-task-lifetimes-growth-and-performance.md)与[01](01-excavation-and-local-rebuild.md)。本轮没有证明异步 cook 的最终完成回调会对每个旧结果再按 chunk 令牌核验，不能把 renderer 的完成门自动套到物理结果上。

**观察：清理。** Mixed 的 `ApplyAction` 在移除动作上分别检查两个子 chunk ID，于 `0x143ED1D0B` 和 `0x143ED1D1E` 调 Basic/Clustered `RemoveChunk`，并清空 Mixed 槽的活动 bit。Clustered 在最后一个成员离开 cluster 时，`FlushActionQueue` 于 `0x143EDF4EC–0x143EDF5CB` 清理弱引用组件、调用 `RemoveMesh`、析构 cluster 并释放稀疏槽；新结果包含的配置数变少时，`0x143EDF8A0–0x143EDF8F2` 清空多余组件的 distance-field/section 数组并调用 `FinishSectionsUpdates`，因而旧 section 不会仅因新结果较短就被保留。`Mixed::StartDestroying`（`0x143EF2680`）标记销毁并向两个子处理器虚表 `+0x28` 转发；这些是本作实现的失效/清理路径，不能证明运行中每个弱引用仍可解引用，也不能当作无泄漏实测。

**Answered（静态）：** MainLevel 初始 Mixed 条件下 `可见 bit0 → Clustered`、`碰撞 bit1/导航 bit2 → Basic`；Clustered 的分组构建、完成队列二次身份/序号门、section/材质/可见组件接收，以及移除与 section 缩短清理。**Unresolved（静态）：** 主关卡每个 chunk 实际标记、[07](07-material-slots-and-handler-selection.md)的 `M_Landscape`／`M_Landscape1` 最终落在哪些可见 section、cluster 合并 helper 的逐几何公式、序号与上游任务令牌是否同源、物理旧 cook 的最终接受条件、蓝图煤矿 `StaticMeshComponent` 与这两支路是否有联动。**Not Run（运行）：** 游戏加载/编辑、GPU/碰撞抓取、FPS 或内存测量；未读取个人存档。研究只为独立实现行为说明，目标代码和资产不作为自研产品交付。
