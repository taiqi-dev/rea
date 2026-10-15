# SUMMERHOUSE：证据身份与调查边界

调查时间：2026-10-14 22:18 PDT。本机目录 `C:\Software\Steam\steamapps\common\SUMMERHOUSE`，`version info.txt` 声明 `Version: 1.2.12`。该字符串是包内声明；下列摘要才固定本轮程序集字节。分析静态读取发行文件，没有启动或附加游戏。

| 制品                                           | 格式和字节数                                   | SHA-256 / 模块 MVID                                                                                         |
| ---------------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `SUMMERHOUSE_Data/Managed/Assembly-CSharp.dll` | PE32 CLI，186880 字节，Unity Mono CIL / AnyCPU | `f4e8bf23299a5e4a916d4bd955e108d2f3760117e5850adf10926ee6aa8379de` / `84569538-a19f-4c17-8ccf-f40b95e99253` |

REA `inspect_managed_artifact` 的完整父 Evidence 为 `ev_ff501d30ac54266f32022d519c34b5ab505213ac840d55d79e153ad1df6aa2cf`，摘要视图为 `ev_8551c8766a33f2f2133f3d948df2fb8cecd1a381ffde1ab83756afe1314114ed`。元数据解码状态 complete，含 173 个 TypeDef、1006 个 MethodDef、1075 个 Field；程序集内嵌 managed resource 计数为 0。这不代表 Unity 场景和 asset 文件没有资源。选定类型的 REA `inspect_managed_members` 均回报 complete：

| Evidence ID                                                           | 选定类型                                                                                          |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `ev_54b382ffc96c6759d706f9d8a92e4a47dfef51824cb2864da333334241793076` | `BuildingBlock`、`GridManager`、`CombinationManager`、`BlockCombination`、`Requirement`           |
| `ev_dbf130a1797c92e37522986abf7c5c20d073a126086d567887d76411e92c7ddf` | `BuildingBlockPlacer`、`BuildingBlockPicker`、`SaveGameManager`、`SavedBuildingBlock`、`SaveData` |
| `ev_f1ce68a56c8253ecef304bbb32c0ed4c255a54b6241698c5491eb722f51a1c7d` | `PaintBrush`、`ColorPalette`、`SetVertexColors`、`GridVisualizer`                                 |

REA 负责身份、元数据、选定方法 CIL 锚点、调用及字段访问。为了读完整分支和常数，本轮另用机器已安装的 .NET 9 SDK `System.Reflection.Metadata`/`PEReader` 离线逐条解码同一 DLL 的 IL，输出暂存于仓库忽略目录 `.cache/procedural-modeling/summerhouse/managed-il.txt`，类型清单为同目录 `managed-list.txt`。这个本地解码器没有加载/反射/执行目标程序集；正文标记 `IL_xxxx` 的位置属于方法内偏移，`0x06...` 是本次构建的 MethodDef token，不能跨版本复用。REA Evidence 和本地 IL 逐项交叉核对，但本地全文不冒称由 REA 返回。

**覆盖与未知。** 主要逻辑入口和数据流取自 `Assembly-CSharp.dll`。[资源补证](04-packaged-blocks-and-combinations.md) 另解析了 `globalgamemanagers.assets` 的相关 MonoScript 和 `sharedassets0.assets` 中的方块、配方、库条目及网格引用，明确列出资源身份和覆盖。没有解析全体 `level*`、`resources.assets`、`sharedassets*.assets`、`StreamingAssets/aa` 的 prefab/材质/场景配置；字段名和包内对象不能证明某资源在某场景实际启用。没有玩家视角、操作、时间、性能或网络观察。本文的「执行」均指 CIL 可达逻辑，不声称游戏现场发生。专有游戏的恢复代码和资产只作研究证据，自研应按自己的需求独立实现。
