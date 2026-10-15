# 发行资源中的方块、组合与网格引用

本篇把[组合判定的 CIL 规则](02-picker-combinations.md)与发行资源中的一个真实配方接起来。资源只作静态证据，没有启动游戏、打开预制件编辑器或复制艺术资产。下述名称是 Unity 对象名，不保证等同玩家界面文字。

## 如何定位和核对数据

本机 `SUMMERHOUSE_Data/globalgamemanagers.assets`（934076 字节，SHA-256 `f44591c487ce6f63a70ffeb8f5b3530dfeaddecd800cdd96cd2f3629c7a45e31`）的 `MonoScript` 表把 `BuildingBlock`、`BlockCombination`、`BuildingBlockLibrary` 分别映到 pathID `1650`、`984`、`1107`，程序集名均为 `Assembly-CSharp`。`SUMMERHOUSE_Data/sharedassets0.assets`（5739864 字节，SHA-256 `6c82efff00e66f0655c17b4a7a79198116360c2cb02af0cf44b1a372539f4510`）使用 Unity `2023.2.22f1`、序列化格式 `22`，未携带 type tree。因此字段读取依据 DLL 的字段顺序、可序列化性、字段类型与对象字节长度共同判定，再核对本地 pathID 引用和 GameObject/Transform 组件关系；不能把无 type tree 的猜测当作 Unity 自报字段名。

`sharedassets0.assets` 的 class `114` 对象中，识别出 `455` 个 `BuildingBlock`、`123` 个 `BlockCombination` 和 `1` 个 `BuildingBlockLibrary`。这三个类型的目标对象均被字段解析器完整消耗到对象末尾；242 个需求 PPtr 与 123 个奖励 PPtr 都解析到同文件内的 `BuildingBlock`。私有但带 `[SerializeField]` 的 `BlockCombination.id` (`0x04000056`) 与 `BuildingBlock.saveID` (`0x0400007E`) 被纳入布局，未标序列化的运行时字段没有硬塞进去。`BuildingBlockLibrary.entries` (`0x04000096`) 的 213 项各含块 PPtr 和 ID；213 项都能找到对应块，且条目 ID 与该块 `saveID` 一致。`GetBlockByID` (`0x0600006A`, `IL_0000..0025`) 正是逐条比较 entry `id` (`0x04000361`) 并返回其 `block` (`0x04000360`)。库的 `maxID` 序列化值为 227，实际条目 ID 从 1 到 227 有空缺。包内 455 个块对象只对应 213 种 `saveID`，故**预制件实例数量不等于存档 ID 数量**；这也不证明每个对象都出现在每个可玩场景或候选袋中。

具体到占格，库条目 `id=6` 指向 `BuildingBlock` pathID `7432`，其 GameObject 名为 `Awning 04`、`cells=[(0,0),(1,0)]`，占连续两格；文件中另一对象 pathID `6857` 同名、同 `saveID`、同两格配置。以下窗户配方的三个块则都只有 `cells=[(0,0)]`。这是预制件的格点占用定义，不能直接当作美术网格的米制宽高。

## 一条真实配方的贯通算例

`BlockCombination` 对象 pathID `7705`、文件偏移 `5713736` 的 GameObject 名为 `Windows w man looking up 02`，序列化 `id=117`、`hasBeenUnlocked=false`。其两条需求和奖励如下；坐标为配方中的 `Vector2Int`，不是预制件的世界位置。

| 条目   | 方块 pathID / GameObject 名      | `saveID` | 相对格点 | `replaceThisOnSuccess` |
| ------ | -------------------------------- | -------: | -------- | ---------------------- |
| 需求 1 | `7196` / `Window 07`             |      109 | `(0,0)`  | true                   |
| 需求 2 | `7632` / `Window 07 (1)`         |      109 | `(1,0)`  | false                  |
| 奖励   | `7510` / `Window 07 w character` |      180 | —        | —                      |

若当前放置块在格点 `(10,4)`，另一个同 `saveID=109` 的块在 `(11,4)`，`CombinationSatisfied` (`0x060000F7`, `IL_0034..0215`) 以第一需求作锚，算出第二目标为 `(10,4)+(1,0)-(0,0)=(11,4)`，再逐项比较格点和 `saveID`。因两个需求的 ID 相同，算法可以从另一需求作为锚尝试；它比对的是 ID，不要求运行时实例恰好来自表中那两个特定 prefab。命中后 `OnCombinationSatisfied` (`0x060000F8`) 依据这条资源的 true 标记选择一件参与的原块，调用 `ReplaceBlock` (`0x060000A7`) 在原位放入奖励预制件，并走解锁/存档路径。**前述格点与玩家触发过程仍是演算**；资源证据只证明发行包里确有这条配方，未证明某次游玩实际解锁。

另一条可交叉核对的不同 ID 配方是 pathID `7706`、`id=22`，GameObject 名 `Door w grandpa 03`：`Door 07`（块 pathID `7197`、`saveID=130`、相对 `(0,0)`、替换 true）与 `Door 08`（pathID `7633`、`saveID=131`、相对 `(2,0)`、替换 false），奖励为 `Door 07 w character`（pathID `7486`、`saveID=174`）。从第一门在 `(10,4)` 作锚时，第二门目标是 `(12,4)`；这是资源相对偏移经算法平移的演算，未观察游戏现场。

## 预制件层级与美术增量

这三个块的根 GameObject 均有 `BuildingBlock` 组件，根 Transform 下是 `Cursor Pivot`，其子对象带 MeshFilter/MeshRenderer。需求 1、2 各有 2 个 MeshFilter：一个 `Mask` 的 mesh 指向外部文件 ID `2`、pathID `10210`，一个 `Model 01` 指向本文件 mesh pathID `432`（对象名 `Window 07`）。奖励有 4 个 MeshFilter：除同类 `Mask` 和 `Window 07` 模型外，还引用本文件 mesh `584`（`Character Window Man Looking Up 01`）与 `586`（`Character Window Man Looking Up 01 Eyes`）。这使“人物窗”在资源层体现为预制件带额外角色网格，和代码的整块替换相吻合；这里只计引用，不复原网格几何、贴图或最终画面。

对 455 个已识别 `BuildingBlock` 根层级递归枚举，共有 673 个各不重复的 MeshFilter，恰好覆盖此文件的全部 class `33` 对象；其中 526 次引用落到本文件的 234 个不同 class `43` Mesh 对象，141 次指向外部文件 ID `2` 的两个 mesh 标识，另有 6 个 mesh 引用为空。单个块的 MeshFilter 数量分布为：1 个有 287 块，2 个有 142 块，3 个有 13 块，4 个有 7 块，5 个有 3 块，6 个有 1 块，7 个有 2 块。这是**引用和层级计数**，不是顶点/三角形数，也不说明所有对象同时渲染或显示。

**边界。** 解析覆盖 `sharedassets0.assets` 内与上述类型匹配的对象和该文件内的 MeshFilter 层级，没有把 `resources.assets`、`sharedassets1..4.assets`、各关卡、Addressables 包里的全部对象重新解释为同一配置全集。带外部 fileID 的 mesh 只记录引用，未按资源依赖表追到源文件。后处理启用状态、贴图颜色、场景实际候选袋、玩家操作与运行结果仍未验证。原始逐对象索引和解码记录保存在忽略目录 `.cache/procedural-modeling/summerhouse/resources/`，不随报告提交。

## 重现与工具边界

从仓库根目录在 PowerShell 中运行以下只读命令；`--sha256` 是本次游戏目录的身份记录授权，其他调查须重新判断是否获准使用摘要。正式脚本在本目录的 [tools/resource_objects.py](tools/resource_objects.py) 和 [tools/decode_blocks.py](tools/decode_blocks.py)，前者调用相邻的 [Unity format-22 索引器](../tools/unity22-compute-probe.py)。脚本只读游戏文件，解析 JSON 写入被忽略的 `.cache`：

```powershell
python docs/studies/procedural-modeling/summerhouse/tools/resource_objects.py --game-data 'C:\Software\Steam\steamapps\common\SUMMERHOUSE\SUMMERHOUSE_Data' --output .cache/procedural-modeling/summerhouse/formal --sha256
python docs/studies/procedural-modeling/summerhouse/tools/decode_blocks.py --game-data 'C:\Software\Steam\steamapps\common\SUMMERHOUSE\SUMMERHOUSE_Data' --input .cache/procedural-modeling/summerhouse/formal --output .cache/procedural-modeling/summerhouse/formal
```

本轮最终运行得到 `455/213/123/242/213/673`，依次为块对象数、不同 `saveID` 数、组合数、组合需求数、库条目数、MeshFilter 数；三类 mesh 引用为本地 `526`、外部 `141`、空 `6`。正式工具输出与先前一次性解析记录逐项核对，方块 ID/占格、组合引用/相对坐标及 MeshFilter 标识一致。`decode_blocks.py` 把本次 DLL 字段布局写死为窄格式；没有依赖缓存中的 `managed-list.txt`，但若版本/程序集身份变化，必须先重新用 REA `inspect_managed_artifact`、`inspect_managed_members` 核对字段及 `[SerializeField]`，再审查该解析器。它会对不支持的 Unity 版本、对象布局、未解析本地引用与计数不符显式失败，不自动解释其它游戏或 Unity 版本。
