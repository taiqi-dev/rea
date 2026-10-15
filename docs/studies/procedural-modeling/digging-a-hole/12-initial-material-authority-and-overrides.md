# 掘地求财：关卡地形材质模式的初始权威与覆盖边界

[11](11-chunk-material-mode-selection.md)把 `MaterialConfig=0` 连到 chunk 的单材质分支，但仍保留“是否另有 Blueprint/archetype 默认值或加载时覆盖”的问题。本篇核对 `MainLevel` 的实际 actor 模板身份，以及加载后首次建世界和重建 renderer 的取值入口。结论限定于**这份发行关卡实例和已读的本作原生函数**，不声称穷尽游玩期间的脚本写入。

## 关卡 actor 的模板是原生 VoxelWorld CDO

**观察：发行资源。** 沿用[07](07-material-slots-and-handler-selection.md)校验过的 `mainlevel-zen.json`，其中 export `1611`／package index `1612` 的 `VoxelWorld`（文件偏移 `621156`，大小 `448`）声明 class script `/Script/Voxel.VoxelWorld`；`outer=0x4c` 指向 export `76` 的 `PersistentLevel`。其 `template=0x722386205d2bf8f8` 在同包 import `532`／package index `-533` 精确匹配 `kind=1` 的 script object **`/Script/Voxel.Default__VoxelWorld`**。新筛选回执 `mainlevel-world-authority.json` 位于 ignored `.cache/procedural-modeling/static-owner-followup/digging-a-hole/`，保留完整 export、模板 import 和 outer 三者，未重解包或重新计算摘要。

这个模板引用直接指向原生 `AVoxelWorld` 类默认对象，当前 actor **没有指向游戏 Blueprint 子类 CDO**。这比只看 actor 名字更能约束默认值来源，但仍不等于已观察进程中 CDO 的最终内存：类默认对象构造之后的配置、通用对象初始化与其他加载钩子未被这份包元数据穷尽。关卡 unversioned 属性头在材质一段选中 `VoxelMaterial` 索引 `41` 和 `LODMaterials` 索引 `43`，跳过 `MaterialConfig` 索引 `40`，因此这份 actor export 没有给 `MaterialConfig` 提供逐实例序列化覆盖；`M_Landscape`、`M_Landscape1` 则是本关卡明确写入的实例资产引用。索引到字段名的对应来自本作 generated `PropPointers`，不是按字节位置猜测。

## 从加载对象到 renderer 的再次取值

**观察：有界加载钩子。** PDB 查询 `*AVoxelWorld*PostLoad*`、`*AVoxelWorld*BeginPlay*`、`*AVoxelWorld*Serialize*`、`*AVoxelWorld*CreateWorld*`、`*AVoxelWorld*RecreateRender*` 均完整返回；相应指令位于 `world-postload.disasm.txt`、`world-beginplay.disasm.txt`、`world-serialize.disasm.txt`、`world-create*.disasm.txt` 和 `world-recreate-render.disasm.txt`。`AVoxelWorld::Serialize`（`0x1441DD2E0–0x1441DD318`）调用 `AActor::Serialize`，非 template 对象再做 `FBodyInstance::FixupData`；`AVoxelWorld::PostLoad`（`0x1441DB0F0–0x1441DB1C7`）先调用 `AActor::PostLoad`，随后检查/回填 `ProcMeshClass`、修正任务优先级表、钳制 `world+0x448` 的整数参数。**这两个 VoxelWorld 自身的函数体没有直接写 `world+0x47D` 的材质模式或 `world+0x57C` 的 render type。** 它们调用的引擎基类逻辑仍在本篇未读范围内，不能据此宣称“加载绝不改材质模式”。

主关卡已解码 `bCreateWorldAutomatically=1`。实际 `AVoxelWorld::BeginPlay` 在 `0x1441CEFA5–0x1441CEFB9` 检查世界未创建字节 `+0x8B9` 与自动创建字节 `+0x440`，满足时在 `0x1441CEFFB` 绑定无参数 `CreateWorld` 并于 `0x1441CF13A` 排入下一 tick。无参数入口在 `0x1441D285C` 调 `CreateWorld(FVoxelWorldCreateInfo)`；该重载于 `0x1441D2665` 进入 `CreateWorldInternal`。内部在 `0x1441D2B4F` 调 `UpdateDynamicRendererSettings` 填 LOD 材质缓存，再于 `0x1441D33C1` 调 `CreateRenderer`。后者按[07](07-material-slots-and-handler-selection.md)和[11](11-chunk-material-mode-selection.md)的 settings 构造从**当时 world 字段**读取材质模式与渲染设置。因此它们并非仅在原生 ctor 时一次性冻结。

`AVoxelWorld::RecreateRender` 是一条已编入的**后续重采样入口**：`0x1441DB577–0x1441DB57F` 更新动态 LOD/renderer 缓存，`0x1441DB63B` 销毁旧 voxel components，`0x1441DB647` 再调用 `CreateRenderer`。若有更早的合法写入改变 `world+0x47D` 或材质引用，重建会按当时状态重新构造 settings；本篇没有发现游戏脚本实际调用这个入口或设置该字段的证据。不能把“存在重建入口”解释为运行中已发生材质切换。

**构造演算，非帧观察。** 从 `/Script/Voxel.Default__VoxelWorld` 取得原生 ctor 的 `world+0x47D=0`，本关卡 export 不覆盖索引 `40`；假定加载期间没有其他写入，首次 `CreateRenderer` 的 `settings+0x3D=0`，随后[11](11-chunk-material-mode-selection.md)已核对的正常 mesher 会写 mesh 首字节 `1`，可见 section 走单材质查询。若在一次另行触发的 `RecreateRender` **之前**该 world 字节被改为 `1`，新 settings 将读到 `1`，相同生产函数把 mesh 首字节写 `0`，进入按 `FVoxelMaterialIndices` 分组的插件分支；但是集合资产是否有效、是否实际生成 chunk、哪个游戏脚本能执行这种写入，均未证。这个条件例子展示的是权威取值时机，不是本作确实发生的切换。

**Answered（静态）：** 发行关卡 actor 的 class、PersistentLevel outer 和原生 CDO template 身份；该 actor 没有逐实例 `MaterialConfig` 值；本作 `BeginPlay → CreateWorldInternal → UpdateDynamicRendererSettings/CreateRenderer` 的采样路径；`RecreateRender` 的重新采样路径。**Partial（静态）：** `AVoxelWorld::Serialize/PostLoad` 自身不直接写模式字段，但引擎基类、CDO 初始化/配置以及其他脚本调用未穷尽。**Unknown／Not Run：** 关卡是否作为某次实际游玩的当前地图、运行中 CDO/实例值、任何动态字段写入和重建频率、可见帧/材质实例，均未运行或附加验证；未读取私人存档。发行代码与资源只作独立实现研究证据，不作为自研产品交付。
