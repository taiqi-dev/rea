# 掘地求财：地形材质从关卡 LOD 配置到可见 section

[07](07-material-slots-and-handler-selection.md)已从发行关卡实例恢复 `VoxelMaterial=/Game/Art/Materials/M_Landscape`、唯一 `LODMaterials` 条目 `Material=/Game/Art/Materials/M_Landscape1, StartLOD=3, EndLOD=6`、`MaxLOD=4`，并推导初始 renderer 选 Mixed。[08](08-mixed-handler-submission-chain.md)已证明 Mixed 的可见 bit 进入 Clustered、结果最终成为组件 section。本篇补齐中间的**材质选择、包装及传递指令**；这仍是静态初始条件，不等于实际游戏帧中某个 chunk 的最终 shader 观测。

## 取证范围

EXE/PDB 的安装身份和原摘要沿用[00](00-evidence-and-reproduction.md)，未重算。新原文在 ignored `.cache/procedural-modeling/static-tail-followup/digging-a-hole/`。本地 PDB 查询 `*FVoxelRendererSettings*` 返回 10/10、`*GetMeshesToBuild*` 5/5、`*FVoxelMaterialInterface*` 46/46、`*FVoxelChunkMaterials*` 6/6，均 `exhausted=true`；较宽的 `*LODMaterial*` 161/161、`*MaterialCollection*` 463/463 也完整返回，但不据符号名本身认定场景调用。使用 VS2022 `dumpbin /DISASM /RANGE` 有界读取 `world-update-renderer.disasm.txt`、`settings-base-ctor-b.disasm.txt`、`settings-get-material-a.disasm.txt`、`settings-get-material-b.disasm.txt`、`render-get-meshes.disasm.txt`、`render-material-helper.disasm.txt`、`chunk-find-multiple.disasm.txt`、`material-create.disasm.txt` 与 `material-create-impl.disasm.txt`。实例资源字段复用[07](07-material-slots-and-handler-selection.md)的 `slot-and-handler-properties-new.json`，未重新解包。

## 实例材质在 32 级缓存中的选择

**观察。** `AVoxelWorld::UpdateDynamicRendererSettings` 在 `0x1441DF964–0x1441DFC71` 对 `LOD=0..31` 逐级填 `world+0x988` 指向的数组，每项步长 `0x14`。每项 `+0x00` 是单材质弱引用，`+0x08` 是材质集合弱引用。对单材质，函数扫描 `world+0x490` 的 16 字节 `LODMaterials` 项：`cmp [entry],LOD; jg skip` 与 `cmp LOD,[entry+4]; jg skip`（`0x1441DF9A7–0x1441DF9B2`）给出**闭区间** `StartLOD <= LOD <= EndLOD`。命中时取 `[entry+8]` 的材质，未命中或弱引用无效则取 `world+0x480` 的基础材质（`0x1441DFA56–0x1441DFA96`）。多条命中时后项可覆盖前项，本关卡只有一条。集合走独立的 `world+0x4A0` 区间数组与 `world+0x488` 默认引用（`0x1441DFAB6–0x1441DFBC5`）；这两个属性在关卡实例没有序列化，[07](07-material-slots-and-handler-selection.md)已核对的 `AVoxelWorld` 构造于 `0x1441C8ADF`、`0x1441C8B0C` 初始化为零，因此**初始**集合为空，仍保留 archetype/加载及后续覆盖边界。

`FVoxelRendererSettingsBase(AVoxelWorld const*)` 于 `0x143E4F68F–0x143E4F6B0` 保存 world `+0x988/+0x990` 的数组引用到 settings `+0x140/+0x148`。单材质查询 `GetVoxelMaterial(int LOD)` 于 `0x143E7F42F–0x143E7F449` 以 `settings+0x140 + 20×LOD` 读取弱引用并尝试 `Get`；弱引用无效时进入诊断/默认材质路径，因此不能只凭静态配置保证资源实际加载成功。

| 构造输入 LOD | `3 <= LOD <= 6` | 初始选择及导入身份                                           | 可见范围边界                                          |
| -----------: | :-------------: | ------------------------------------------------------------ | ----------------------------------------------------- |
|            2 |       否        | 基础 `world+0x480` → `M_Landscape`（关卡 import `-165`）     | 需该 LOD 的 chunk 实际生成且走单材质支路。            |
|            3 |       是        | `LODMaterials[0].Material` → `M_Landscape1`（import `-166`） | 区间起点包含 3。                                      |
|            4 |       是        | 同上 `M_Landscape1`                                          | `MaxLOD=4`；配置的终点 6 不说明本场景会生成 LOD 5/6。 |

这是按**已解码实例配置 + 发行 EXE 比较式**所作的演算，不是实测每级 section 数或运行中 LOD 分布。

## 从选中材质到 Clustered section

**观察。** `Clustered::ApplyAction` 在 `0x143ED1936` 调 `FVoxelRenderUtilities::GetMeshesToBuild`（同一入口也供 Basic 使用）。该函数在 `0x143EE3B84–0x143EE3BF7` 的一种分支中，若 `FVoxelChunkMaterials` 当前材质引用为空，便以本次整数 LOD 调上面的 `GetVoxelMaterial(int)`；返回的 `UMaterialInterface*` 在 `0x143EE3C0A` 交给 `GetMeshesToBuild` 内的 lambda。lambda 于 `0x143ECB877–0x143ECB8D5` 检查 settings `+0x54`：为零时调用 `FVoxelMaterialInterfaceManager::CreateMaterial`；该函数 `0x143E696F6–0x143E696FC` 将 `CreateMaterialImpl` 的动态实例标记参数置零。`CreateMaterialImpl` 于 `0x143E69779–0x143E698B0` 将原 `UMaterialInterface` 按引用放入管理器并返回 `FVoxelMaterialInterface` 共享包装。`GetMeshesToBuild` 于 `0x143EE3C3C–0x143EE3D9D` 把包装引用写回 `FVoxelChunkMaterials`，并放进以 `FVoxelMeshConfig` 和 `FVoxelProcMeshSectionSettings` 分组的结果；section settings 的首引用携带该包装，碰撞/导航/可见位另写到后续字节。

本关卡初始 `bMergeChunks=1` 已在[07](07-material-slots-and-handler-selection.md)确认。设置构造在 `0x143E4F492–0x143E4F4AC` 遇 `world+0x5B1` 非零时把 `settings+0x54` 写为零。因此，上述**单材质分支**针对这份初始设置使用 `CreateMaterial` 包装原材质，不走 lambda 另一侧的 `CreateMaterialInstance → InitializeMaterialInstance`（`0x143ECB8E8–0x143ECB9E8`）。这不排除其他材质集合、后续设置变更或别的调用路径创建动态材质实例。

Clustered 已在[08](08-mixed-handler-submission-chain.md)证明消费这份分组数据：`Clustered::ApplyAction → FVoxelClusteredMeshMergeWork → 完成队列/序号门 → Clustered::FlushActionQueue`，于 `0x143EDF7DF–0x143EDF85E` 将 section settings 的材质引用和 buffer 搬到组件，于 `0x143EDF852` 调 `AddProcMeshSection`。组件的 `GetMaterial(index)` 在[06](06-mesh-material-binding-and-edit-lifecycle.md)的 `0x143EE3100` 从对应 section 首引用调用 `FVoxelMaterialInterface::GetMaterial`。所以可验证的桥是 **LOD 缓存原材质 → `FVoxelMaterialInterface` 包装 → mesh/section settings → Mixed 可见 Clustered 组件 section → 材质查询**；它不是“每个 LOD 只对应一个 section”的证明。

**插件可用的另一支，非本关卡已证结果。** `GetMeshesToBuild` 还在 `0x143EE3FA6` 进入按 `FVoxelMaterialIndices` 分组的路径；`FVoxelChunkMaterials::FindOrAddMultiple` 于 `0x143EBED06–0x143EBED24` 调另一重载 `GetVoxelMaterial(LOD, indices)`，再经过同一个材质包装 lambda。该重载于 `0x143E800A9–0x143E800C1` 对选中的 `UVoxelMaterialCollectionBase` 虚表 `+0x2D0` 分派；集合弱引用无效时可走默认/诊断路径。MainLevel 初始集合为空，且这次未解出每个 chunk 的 `FVoxelChunkMesh` 模式、材质索引与有效弱引用，故不能把该能力写成此场景确实使用 `SingleIndex`/`MultiIndex` 集合材质，也不能断言 `M_Landscape1` 落在每一个可见 section。

**Answered（静态）：** 主关卡两项资源身份、区间闭合选择与 LOD2/3/4 演算；单材质分支从配置到 Clustered section 引用和组件材质查询的真实原生连接；初始合并设置下该分支的普通包装选择。**Unresolved（静态）：** 实际每个 chunk 的材质模式、索引/section 分组数、材质资源加载失败及动态覆盖、最终 shader 和 LOD 分布。**Not Run（运行）：** 游戏帧、材质实例或 GPU 抓取，未读取私人存档。发行代码与资产仅作独立实现研究证据，不作为自研产品交付。
