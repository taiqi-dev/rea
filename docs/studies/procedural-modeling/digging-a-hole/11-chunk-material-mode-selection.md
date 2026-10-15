# 掘地求财：chunk 材质模式的生产与 section 分派

后续[12](12-initial-material-authority-and-overrides.md)已核对原生CDO模板及创建/重建renderer的取值时机；引擎基类、配置和其他脚本覆盖仍未穷尽，本篇默认值推导保持条件范围。

[10](10-terrain-material-to-sections.md)已追踪关卡材质引用进入可见 section 的过程，但当时没有约束 `FVoxelChunkMesh` 的单材质／索引材质分支。本篇从**网格首字节的生产者**反向核对关卡初始配置，再跟踪索引模式的生产和消费。结论是：在本关卡已解码的初始配置、原生构造默认值和正常 mesher 生产路径下，chunk mesh 首字节写为 `1`，`GetMeshesToBuild` 走单材质分支；按 `FVoxelMaterialIndices` 分组是插件已编入的另一条路径，不能据其存在断言本关卡实际使用了材质集合。

## 证据与实例边界

安装 EXE/PDB 身份沿用[00](00-evidence-and-reproduction.md)，没有重算摘要或运行游戏。新的本地原文位于 ignored `.cache/procedural-modeling/static-slot-followup/digging-a-hole/`：`chunk-mode-symbols.json`、`chunk-producer-symbols.json`、`mesher-impl-symbols.json`、`chunk-vertex-symbols.json` 及本篇提到的 `*.disasm.txt`。PDB 查询 `*FVoxelChunkMesh*` 58/58、`*FVoxelMesher*` 67/67、`*VoxelMaterialIndices*` 56/56、`*FinishCreatingChunk*` 6/6、`*CreateChunkFromVertices*` 4/4，均 `exhausted=true`；再用 VS2022 `dumpbin /DISASM /RANGE` 核对指定函数。实例属性头、原生属性指针顺序和 ctor 反汇编复用[07](07-material-slots-and-handler-selection.md)的 `slot-and-handler-properties-new.json`、`native-property-pointer-order.json`、`voxelworld-ctor.disasm.txt`，不重新解包。

**观察：初始 `MaterialConfig=0`。** `AVoxelWorld` 的 generated `PropPointers` 去掉 enum `Underlying` 和集合内部描述符后，`MaterialConfig` 是对象属性索引 `40`，紧随的 `VoxelMaterial`、`MaterialCollection`、`LODMaterials` 分别是 `41`、`42`、`43`。主关卡 `VoxelWorld` 的 unversioned 头在这一段选中 `41` 和 `43`，没有选中 `40`。匹配 EXE 的 `AVoxelWorld` 构造先在 `0x1441C88BD` 清零 `ebx`，再于 `0x1441C8AD1` 把零字写入 `world+0x47C`（覆盖 `+0x47D`）。`FVoxelRendererSettingsBase(AVoxelWorld const*)` 于 `0x143E4F43F–0x143E4F446` 把 `world+0x47D` 复制到 `settings+0x3D`。因此，在**原生默认 + 本关卡实例未覆盖**的静态初始条件下，设置中的材质模式字节为零。archetype、加载回调及后续运行时写入没有在这条静态证据中被穷尽。

同一关卡属性头还跳过了 `RenderType`（对象属性索引 `58`）；原生构造于 `0x1441C8BD2` 把 `world+0x57C` 写零，settings 构造于 `0x143E4F479–0x143E4F480` 复制到 `+0x4D`。`FVoxelMesherAsyncWork::GetMesher` 于 `0x143EE377A–0x143EE3786` 对零值跳到 Marching Cube 选择段，普通非 transition 支路于 `0x143EE3A1D` 构造 `FVoxelMarchingCubeMesher`。这仅约束同一静态初始条件下的正常网格生产者；是否启用 transition 和实际 chunk 数仍未知。

## 网格模式字节怎样决定分支

**观察：生产者。** `FVoxelMesher::CreateFullChunk`（`0x143ED8270`）的**空 chunk 路径**从 `mesher+0x20` 取得 settings，检查 `settings+0x3D`（`0x143ED8348`）。值为零时在新建的 `FVoxelChunkMesh` 首字节写 `1` 并调 `CreateSingleBuffers`（`0x143ED8351–0x143ED8355`）；非零时写 `0`（`0x143ED835C`）。正常 Marching Cube 的 `FVoxelMarchingCubeMesher::CreateFullChunkImpl` 于 `0x143ED90AF` 调 `FVoxelMesherUtilities::CreateChunkFromVertices`；后者独立检查同一 `settings+0x3D`（`0x143ED696E–0x143ED6979`），零值路径于 `0x143ED6E62–0x143ED6E68` 写 mesh 首字节 `1` 并建 single buffers，非零路径于 `0x143ED719D` 写 `0`。这两处生产逻辑互相核对了首字节语义；没有把 enum 名称或 PDB 符号名直接当作模式证据。

**观察：消费者。** `FVoxelRenderUtilities::GetMeshesToBuild` 的 PDB 签名明确包含 `FVoxelChunkMesh const&`，入口 `0x143EE3A98` 将其保存到 `r15`。`0x143EE3B84` 执行 `cmp byte ptr [r15],0`：**非零**继续于 `0x143EE3BE9–0x143EE3C0A` 用 chunk 单材质缓存，缓存空时调用 `GetVoxelMaterial(int LOD)` 并包装；**零**跳到 `0x143EE3FA6`，以 `FVoxelChunkMesh::IterateMaterials`（`0x143EE3FF4`）收集索引键，后续于 `0x143EE42C6` 调 `FVoxelChunkMaterials::FindOrAddMultiple`。该 helper 在 `0x143EBED06–0x143EBED24` 对未缓存键调用 `GetVoxelMaterial(LOD, FVoxelMaterialIndices)` 并包装；`GetMeshesToBuild` 之后按 `FVoxelMeshConfig` 与 `FVoxelProcMeshSectionSettings` 成组，索引分支还于 `0x143EE4BC2` 和 `0x143EE4C59` 按键查找 mesh buffer。两条分支都把结果交给[08](08-mixed-handler-submission-chain.md)已证实的 Mixed 可见 Clustered section 流程。

| 构造输入                                         |         生产的 mesh 首字节 | `GetMeshesToBuild` 消费                                    | 证据归属                                                  |
| ------------------------------------------------ | -------------------------: | ---------------------------------------------------------- | --------------------------------------------------------- |
| 主关卡初始 `settings+0x3D=0`，正常生成非空 chunk | `1`，并创建 single buffers | 单材质缓存；空时查该 LOD 的 `VoxelMaterial`/`LODMaterials` | 实例头 + ctor + 生产/消费指令的静态推导；没有观测游戏帧。 |
| 假设设置为 `1`，并有三个顶点索引字节 `5,7,9`     |                        `0` | 索引键进入多材质缓存，再走材质集合重载                     | 插件分支演算，不是本关卡值。                              |

## 索引模式中的键来自哪里

**观察，限插件非零模式。** Marching Cube 的 `CreateFullChunkImpl` 在 `0x143ED8B74` 调 `FMarchingCubeHelpers::ComputeMaterials`，该函数有把材质数据写到每个 `FVoxelMesherVertex` 的 `+0x60..+0x63` 的指令，包括 `+0x63` 于 `0x143EA3FEF`。随后 `CreateChunkFromVertices` 对 `MaterialConfig=1` 的支路，在 `0x143ED7210–0x143ED7280` 从一个三角形的三个顶点（步长 `0x68`）读取 `+0x63`，用两次 unsigned `cmovb` 取得三者**最小索引**；`0x143ED7280–0x143ED72BF` 把计数 `1` 和该索引组成 `FVoxelMaterialIndices` 键并做 `TSet` 查找，缺项于 `0x143ED740E` 新建组。于是自造输入 `5,7,9` 的该支路键索引为 `5`，而不是按最后一个顶点的 `9` 分组。其他非零材质模式在同函数另有分支；本篇不把此算例推广为所有多索引组合的规则。

`FVoxelChunkMesh::FindOrAddBuffer`（`0x143EDD940–0x143EDDA62`）也按 `FVoxelMaterialIndices` 哈希查找／创建共享 buffer；`FVoxelChunkMesh::IterateMaterials`（`0x143EC18C0`）遍历这些键，成为上述 `GetMeshesToBuild` 零字节分支的输入。这里的键是**由 mesher 的顶点材质数据在建网格时生产的 chunk 分组键**，不是关卡中 `M_Landscape`/`M_Landscape1` 的材质资产 package index。初始 `MaterialCollection` 及 `LODMaterialCollections` 没有实例值，[10](10-terrain-material-to-sections.md)已列出默认与有效引用边界；索引材质虚分派属于插件能力，不能反推这两个资产是集合成员。

**Answered（静态）：** 本关卡初始材质模式为零；两条 mesh 生产路径都将零模式编码为首字节 `1`；`GetMeshesToBuild` 对该字节的确切跳转方向，以及索引模式中的顶点字节 → 键 → buffer → 包装 → section 分组链。**Unresolved（静态）：** 后续配置覆盖、各运行 chunk 是否非空、每个 LOD 的具体 chunk 数与 section 数、实际加载后的弱引用、其他非零材质模式的逐顶点混合公式。**Not Run（运行）：** 游戏、附加、存档、运行帧或 GPU 证据均未执行。发行制品仅作独立实现研究，不作为自研产品代码或资产交付。
