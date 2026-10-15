# 掘地求财：煤矿材质槽与主关卡体素处理器选择

接续[矿物网格与表现](04-mesh-materials-and-ore-presentation.md)和[网格组件接收路径](06-mesh-material-binding-and-edit-lifecycle.md)。本篇解决两处原先保留的静态缺口：发行包 `SM_Ore_Coal` 的 `StaticMaterials[0]` 实际引用 `/Game/Art/Materials/M_Ores_1-3`；`MainLevel` 的 `VoxelWorld` 在当前序列化配置和本作构造默认值下，进入 `FVoxelRendererMixedMeshHandler` 分支。后者是**静态初始选择的推导**，没有运行游戏来证明整个游玩期间一直保持此选择。

## 输入、格式与证据边界

目标身份与只读授权沿用[00 证据入口](00-evidence-and-reproduction.md)。从已提取的本作 `MainLevel.umap`、`SM_Ore_Coal.uasset`、对应 Zen name/import/export 表和同版本 EXE/PDB 出发；仅检查指定 export 及必要原生函数。新[窄范围探针](tools/voxel_render_config_probe.py)逐片段解析 unversioned property header、zero mask、已由 PDB 确认的字段和嵌套结构，并在 schema 或预期形状不符时失败。可复核的原始表、PDB 查询、`dumpbin` 反汇编、`native-property-pointer-order.json` 的实际 `.rdata` 指针顺序和探针 JSON 均保存在 ignored 目录 `.cache/procedural-modeling/static-chain-followup/digging-a-hole/`；不随文档提交。新探针输出为 `slot-and-handler-properties.json`。未启动或附加游戏，未读取玩家存档，也未重算目标内容摘要。

在仓库根运行以下已缓存输入的复核命令；`--output` 必须是尚不存在的新文件，探针用 CreateNew 写入，拒绝覆盖旧证据。

```powershell
python -X utf8 docs/studies/procedural-modeling/digging-a-hole/tools/voxel_render_config_probe.py --mainlevel .cache/procedural-modeling/digging-a-hole/packages/MainLevel.umap --mainlevel-zen .cache/procedural-modeling/static-chain-followup/digging-a-hole/mainlevel-zen.json --coal .cache/procedural-modeling/digging-a-hole/art-followup/packages/SM_Ore_Coal.uasset --coal-zen .cache/procedural-modeling/digging-a-hole/art-followup/coal-zen.json --output .cache/procedural-modeling/static-chain-followup/digging-a-hole/slot-and-handler-properties-verify.json
```

格式规则取自固定提交 `7ecaebdf9365798a74ea4ba03af0ee66f56dbfde` 的 [UAssetAPI `FFragment`](https://github.com/atenfyr/UAssetAPI/blob/7ecaebdf9365798a74ea4ba03af0ee66f56dbfde/UAssetAPI/Unversioned/FFragment.cs)：16 位片段低 7 位表示跳过字段数，`0x80` 表示零值 mask，`0x100` 表示最后片段，高位表示选中值数。这仅是辅助格式说明，**字段顺序和实际值仍须由本作 PDB 与包字节验证**。该格式要求读写侧对属性定义一致；[Epic 的 unversioned 序列化文档](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Core/FArchiveState/UseUnversionedPropertySerializat-)也明确了这一前提。本次不把任意位置的字节猜作属性。

## `SM_Ore_Coal` 的实际材质槽

**观察。** `coal-zen.json` 的 export `2` 是 `/Script/Engine.StaticMesh` 的 `SM_Ore_Coal`，文件偏移 `12496`、大小 `8950`。匹配 EXE 的 `UStaticMesh` generated `PropPointers`（`0x1470CB330`）按指针顺序给出其自身属性：`MinQualityLevelLOD`、`MinLOD`、`ElementToIgnoreForTexFactor`、`StaticMaterials`；另一个 `StaticMaterials_Inner` 是数组内部描述符，不占对象属性索引。因此 `StaticMaterials` 是该类属性索引 `3`。原始 export 头四字节 `03 08 13 03` 解析为 `(skip=3,count=4)` 与 `(skip=19,count=1,last)`，正好选中属性 `3–6` 和 `26`。从头后偏移 `+4` 读出 `StaticMaterials` 数组元素数 `1`，而不是仅看到一个材质包依赖。

`FStaticMaterial` 的本作 generated `PropPointers`（`0x1470CCAD0`）把成员顺序固定为 `MaterialInterface`、`MaterialSlotName`、`ImportedMaterialSlotName`、`UVChannelData`。这个数组元素从 export `+8` 开始，结构头 `00 09` 选中四个成员；第一个成员在 `+10`，其有符号 package index 为 `-5`。同一个包的 Zen import `-5` 是 `/Game/Art/Materials/M_Ores_1-3`，保存的 public export hash 为 `0xe50c6e76ded8dd3a`。两个后续 `FName` 各为 `(nameIndex=3,number=0)`；该包 name map 的索引 `3` 是 `WorldGridMaterial`。

| 实际对象 / 字段                                 | export 相对偏移 | 读到的值                                  | 连接含义                                                                                            |
| ----------------------------------------------- | --------------: | ----------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `SM_Ore_Coal.StaticMaterials` 数量              |            `+4` | `1`                                       | 本包定义一个默认静态材质槽。                                                                        |
| `StaticMaterials[0].MaterialInterface`          |           `+10` | import `-5` → `M_Ores_1-3`                | **实际 slot 0 的默认材质引用**，超出了[04](04-mesh-materials-and-ore-presentation.md)仅有的包依赖。 |
| `MaterialSlotName` / `ImportedMaterialSlotName` |   `+14` / `+22` | `WorldGridMaterial` / `WorldGridMaterial` | 这是实际序列化槽名；不代表最终显示网格名。                                                          |

与[04](04-mesh-materials-and-ore-presentation.md)已确认的蓝图 `SetStaticMesh(-180)` 以及煤矿 mesh public export hash 对照后，可把“蓝图选煤矿网格”连到“该网格 slot 0 的默认材质引用”。**未知**：组件是否在游戏运行中覆盖 slot、材质包内具体参数/纹理、shader 最终路径和屏幕呈现；这些不能由默认槽反推。

## `MainLevel` 的 `VoxelWorld` 与处理器分支

**观察：关卡字段。** `mainlevel-zen.json` 的 export `1611`（package index `1612`）是 `/Script/Voxel.VoxelWorld` 的 `VoxelWorld`，文件偏移 `621156`、大小 `448`。本作 `AVoxelWorld` generated `PropPointers`（`0x14719F390`）中，索引 `74` 对应 `bMergeChunks`，索引 `75`、`76` 依次是 `ChunksClustersSize`、`bDoNotMergeCollisionsAndNavmesh`。export 开头的 17 个 unversioned fragments 在索引 `74` 选中 1 个值，却跳过 `75–76`；索引 `61` 的零值 mask 为 `01`，并不改变随后值的读取位置。探针从 export `+0x23` 的值区按 schema 读取，`bMergeChunks` 位于 `+0x66`，实际字节 `01`。

首三个字段还能交叉锚定属性顺序：`WorldRoot` 的值 `1613` 指向名为 `Root` 的 `VoxelWorldRootComponent` export；`LineBatchComponent` 的值 `1611` 指向名为 `LineBatchComponent` 的对应 export；随后 `SaveObject=-535`。继续解析得到 `VoxelSize=9.0`、`RenderOctreeDepth=6`、`WorldSizeInVoxel=2048`、`MaxLOD=4`、`VoxelMaterial=-165`（`/Game/Art/Materials/M_Landscape`）。`LODMaterials` 数量 `1`，唯一元素的材质 `-166` 指向 `/Game/Art/Materials/M_Landscape1`，`StartLOD=3`、`EndLOD=6`；`ProcMeshClass=-115` 对应 `/Script/Voxel.VoxelProceduralMeshComponent`。这些值来自本关卡实例，不等同于煤矿 StaticMesh 的材质槽。

**观察：默认值与选择代码。** 同版本 EXE 的 `AVoxelWorld::AVoxelWorld`（`0x1441C88A0`）在 `0x1441C8C2B` 把字 `1` 写到对象 `+0x5B0`，因此初始字节 `+0x5B1=0`；`0x1441C8C3E` 把 `1` 写到 `+0x5B8`。本作 generated setter 符号把 `+0x5B1` 对应到 `bMergeChunks`、`+0x5B8` 对应到 `bDoNotMergeCollisionsAndNavmesh`。关卡仅序列化前者为 `1`，后者按此原生构造默认值为 `1`。`FVoxelRendererSettingsBase(AVoxelWorld const*)`（`0x143E4F230`）在 `0x143E4F62B–0x143E4F637` 把 world `+0x5B1` 拷到 settings `+0x130`，在 `0x143E4F64F–0x143E4F667` 取 world `+0x5B1` 与 `+0x5B8` 的布尔合取，写入 settings `+0x138`。`AVoxelWorld::CreateRenderer` 于 `0x1441D13D2` 构造这些 settings，并于 `0x1441D13DE` 调 `FVoxelDefaultRenderer::Create`。

**推导：静态选择。** `FVoxelDefaultRenderer` 构造函数（`0x143EC6370`）首先在 `0x143EC647D` 检查 settings `+0x130`：零走 Basic（`0x143EC6721`）；非零继续在 `0x143EC648A` 检查 `+0x138`：零走 Clustered（`0x143EC659C`）；均非零走 Mixed（`0x143EC649A`）。对这个关卡实例的算例是 `bMergeChunks=1`、`bDoNotMergeCollisionsAndNavmesh=1`，所以 settings `(+0x130,+0x138)=(1,1)`，构造 **Mixed handler**。这也收窄了[06](06-mesh-material-binding-and-edit-lifecycle.md)的 Basic handler 证据：Basic 是本作已编入的能力，不应作为此关卡默认所选的处理器。

| 两个输入位                                            | settings `+0x130` / `+0x138` | 构造分支                  |
| ----------------------------------------------------- | ---------------------------- | ------------------------- |
| `bMergeChunks=0`，另一位任意                          | `0` / `0`                    | Basic                     |
| `bMergeChunks=1`、`bDoNotMergeCollisionsAndNavmesh=0` | `1` / `0`                    | Clustered                 |
| `bMergeChunks=1`、`bDoNotMergeCollisionsAndNavmesh=1` | `1` / `1`                    | Mixed：本实例静态初始配置 |

**仍未验证。** 本轮未运行游戏、未观察实际关卡加载、原生类默认对象是否受额外配置改写或执行时的字段修改，因此不能断言启动后一定加载 `MainLevel`、两位始终取上述值、每一帧均使用 Mixed、或当前画面/性能表现。探针只解析到 `bMergeChunks`，其后 export 字段及完整 `StaticMesh` 渲染数据未作泛化解码。材质槽默认引用、VoxelWorld 地形材质、处理器选择分别成立，不能把矿物静态网格与地形 chunk 的材质实例或 draw call 合并为同一条未证实路径。
