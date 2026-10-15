# 掘地求财：矿物网格的生成、摆放与移除

后续 [06](06-mesh-material-binding-and-edit-lifecycle.md) 已解释 `0x4d` 执行流及 `DestroyOre` 局部销毁条件，并补 Voxel Basic 的 section/材质接收链；本篇矿物 StaticMesh 材质槽仍保留为未知。

本篇补齐[挖掘与局部重建](01-excavation-and-local-rebuild.md)、[保存](02-save-load-and-consistency.md)和[性能边界](03-performance-and-independent-design.md)之外的可见物体路径：矿物与石块并非由本次已证实的体素 mesher 直接合成。游戏自己的 cooked `BP_OreSpawner` 图会添加 `StaticMeshComponent`，给它选择包内静态网格，再对其设置可见距离；角色命中后可把组件交回 spawner 移除。这是**发行制品中的静态执行语义**，不是已观察的游戏画面。

目标仍是 `C:\Software\Steam\steamapps\common\A Game About Digging A Hole`，文件身份、工具和提取边界见[00](00-evidence-and-reproduction.md)。本篇新读 `BP_OreSpawner.uasset`（包名 `/Game/Blueprints/BP_OreSpawner`）、角色主图和 `SM_Ore_Coal.uasset`。蓝图字节码用[项目探针](tools/blueprint_probe.py)完整解码：spawner 主图序列化 `129075/129075` 字节、逻辑 `88931/88931` 字节。物体包按 Zen name/import/export 解析；忽略的本机原始记录在 `.cache/procedural-modeling/digging-a-hole/art-followup/`，不随文档迁移。本篇偏移是 Kismet **逻辑 code offset**，需要时另列 `.uasset` 文件偏移。没有启动或附加游戏，没有读取个人存档。

## 一条真实的矿物显示链：煤层候选可以选石、煤、铁网格

**观察：候选位置。** spawner 主图逻辑 `71–475` 以 `OreDistanceCoal` 分别对 `1000`、`1310`、`Layer2Depth` 作整数除法，并以对应的 `−1` 形成三层循环上界。这是选定图中的候选迭代结构；整数间距的运行时值和除零处置未从默认资产证实。逻辑 `536–1215` 将循环索引乘 `OreDistanceCoal`，在三轴各加一个 `RandomIntegerInRange(−floor(D/3), floor(D/3))` 的整数扰动，并让竖直轴随层索引下降。逻辑 `1270–1500` 再减去 `(500,650,Layer1Depth+LayerCoalDepth)`，生成 `MakeTransform(position,(0,0,0),(1,1,1))`。这里 `D=OreDistanceCoal`，`floor` 表示实际 `Divide_IntInt` 的整数商；对于负数或非法 `D`，还应依其运行时语义而非直接套普通数学 floor。

**观察：组件和网格。** 逻辑 `1579` 用上述 transform 调 `Actor.AddComponent("NODE_AddStaticMeshComponent-7", …)`，`1636` 对该 primitive 设置 cull distance `2000`。随后逻辑 `1669` 取 `RandomIntegerInRange(0,15)`；顺序的 `NotEqual_IntInt` 加 `JumpIfNot` 分派不同网格：`0–2` 跳至逻辑 `21730` 的 `SetStaticMesh`，`3–12` 跳至 `21786`，`13–15` 跳至 `2457`。这些分支的实际 `SetStaticMesh` 对象索引依次为 `-189`、`-180`、`-184`，不是从名字猜的枚举。Zen import 对应：

| 随机整数分支 | `SetStaticMesh` 逻辑/文件偏移 | Zen import | 精确外部包                                 |
| ------------ | ----------------------------- | ---------: | ------------------------------------------ |
| `0–2`        | `21762` / `128293`            |     `-189` | `/Game/Art/StaticMeshes/Ores/SM_Ore_Stone` |
| `3–12`       | `21818` / `128365`            |     `-180` | `/Game/Art/StaticMeshes/Ores/SM_Ore_Coal`  |
| `13–15`      | `2489` / `99720`              |     `-184` | `/Game/Art/StaticMeshes/Ores/SM_Ore_Iron`  |

这是同一**煤层候选路径**按随机分支挑网格；不能把所有煤层实例都叫煤矿，也不能据此推测拾取价值、稀有度或玩家看到的出现概率。蓝图传入的 transform 旋转为零、缩放为 `(1,1,1)`；网格自身顶点尺寸、组件模板默认属性和 Actor 父变换未完整恢复，所以“世界中物体绝不旋转或缩放”不成立。其它资源分支另有 `RandomRotator`（如逻辑 `31640`），不能推广这条煤层路径的朝向到所有道具。

**构造演算（自造输入，非默认参数）。** 令 `D=150`、三个循环索引依次为 `2,3,1`、`Layer1Depth=1000`、`LayerCoalDepth=2000`，随机扰动取 `(20,−10,5)`，在 `±50` 范围内。该路径构造的候选位置为 `(300,450,−150)−(500,650,3000)+(20,−10,5)=(−180,−210,−3145)`；旋转零、缩放一。若随机整数为 `5`，按上述跳转会给组件设置 `/Game/Art/StaticMeshes/Ores/SM_Ore_Coal`。这只计算图中的位置与选择；没有证明此点在实际地表之下、与体素表面相交，或运行时一定成功显示。

## 网格包到材质：已连到真实资产，材质槽仍未知

**观察。** 容器索引确有 `../../../DiggingGame/Content/Art/StaticMeshes/Ores/SM_Ore_Coal.uasset`（entry `949`，解出 `21450` 字节）。新提取并解析的 Zen 包中，`StaticMesh` 类 export 名为 `SM_Ore_Coal`，其**存储的 public export hash** `0xb6d9282a66c9c007` 与 spawner 对 `-180` 所保存的 export hash 相同。这把游戏蓝图的包外网格引用精确连到实际包内 StaticMesh export；并非只按同名路径联想。未重算内容哈希。

该网格包的 import `-5` 指向 `/Game/Art/Materials/M_Ores_1-3`，名字表另含 `Ore`、`WorldGridMaterial`。这是网格包对材质包的**依赖线索**；当前 Zen 工具只解析元数据，未解出 StaticMesh 的 material slot 索引、实际实例化材质、纹理或 shader。因此不能把 `M_Ores_1-3` 直接当成已确认的最终像素着色器，也不能把矿物网格与体素地形材质说成共用一套材质。体素 mesher 的插件能力见[01](01-excavation-and-local-rebuild.md)；本篇确认的是游戏蓝图额外添加的独立静态网格表现层。

## 玩家命中后的组件移除，以及缓存的另一职责

**观察。** 角色主图在逻辑 `14858`（文件 `243188`）、`19870`、`35766` 等位置调用 spawner 的 `DestroyOre`，参数来自相应 `BreakHitResult.HitComponent`。该函数本身的完整 18-byte 逻辑体把执行跳到 spawner 主图 `82400`。那里对传入组件取 `GetDisplayName`，检查是否含 `Voxel`，随后存在以该组件为 context 的 `ActorComponent.K2_DestroyComponent` 调用（逻辑 `82512`，文件 `216607`）。`0x4d` 控制流标记夹在名称检查与销毁之间；现有窄探针未给出其执行流栈语义，故不能宣称所有命中组件都会销毁，或准确写出 `Voxel` 条件的成功分支。可确认的是：**实际角色命中组件 → spawner DestroyOre 入口 → 基于组件名的检查与组件销毁候选**。

另一个主图区域在逻辑 `76819–78259` 遍历 `StaticMeshComponent`，按显示名尾四字符区分 `Stone`、`Coal`、`Iron` 等类别，取组件相对 transform，加入 `CachedOreLocations`。逻辑 `78835–79403` 还对待移除组件的显示名与缓存项比较并执行 `Array_Remove`；这属于缓存/保存位置管理，不能仅凭相邻代码把它等同于上面 `DestroyOre` 每次调用都同步完成的事务。完整保存链见[02](02-save-load-and-consistency.md)。显示名用于分类/对照本身有脆弱性，但本篇没有修改原作，也不推断其所有命名冲突结果。

## 可借鉴的独立设计和未决项

独立产品可以把“体素地形表面”“矿物候选分布”“可见网格/材质”“挖掘命中与持久身份”分成明确的四种状态：候选位置不自动意味着露出；可见组件不自动意味着体素材料值；拾取或移除时要用稳定实例 ID 同步组件、库存和存档，而不依赖显示名尾缀。矿物形状、材质和参数均需自行设计与授权，不以本作恢复代码或资源作生产交付。

**已回答：** 选定候选的三轴/层深位置构造、单位 transform、静态网格组件、2000 cull distance、三个精确矿物网格分支；煤网格引用和包内 StaticMesh export 的身份连接；玩家命中向 `DestroyOre` 传组件的实际调用。**部分回答：** 组件销毁条件、缓存同步和材质依赖。**未回答：** 地表遮挡/露出判定、StaticMesh 材质槽与贴图、世界和材质运行状态、实际出现频率、FPS/帧耗与画面。此次只做静态读取；未运行游戏，也未进行 GPU 抓帧或实际采掘验证。
