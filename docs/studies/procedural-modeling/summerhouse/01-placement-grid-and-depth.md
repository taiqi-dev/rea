# 从建筑块预览到落地：格点、翻转和深度

本篇依据[固定程序集与工具边界](00-evidence-and-scope.md)。关键入口是 `BuildingBlockPlacer::PreviewPosition` (`0x06000093`)、`Click` (`0x0600009E`)、`PlaceBlock` (`0x060000A6`)，以及 `BuildingBlock::GetZPosition` (`0x0600005D`)。REA 选定成员 Evidence 分别为 `ev_dbf130a1797c92e37522986abf7c5c20d073a126086d567887d76411e92c7ddf` 和 `ev_54b382ffc96c6759d706f9d8a92e4a47dfef51824cb2864da333334241793076`；具体 `IL_xxxx` 以下述方法内部偏移为准。

## 构件和格点的分工

`BuildingBlock` (`0x0200000E`) 持有 `cells`、`visualOffset`、`saveID`、`mainRenderer`、`zOffset`、`raycastPositions` 和翻转父节点等字段。它以预制对象及其子节点为视觉载体。`BuildingBlock::Awake` (`0x06000056`, `IL_0000..003F`) 取第一个子 Transform 作为 pivot，计算根与 pivot 的位置差为 `visualOffset`，建立翻转父节点并记录原有材质。`GridManager` (`0x0200002B`) 则提供格点吸附、格子查询和 Z 步长函数；`CellTag` 枚举的 `Ground/Wall/Decoration/Roof/Window/Door` 等名称只是分类线索，当前证据没有把它们误读为连续墙面拓扑。

预览先取指针的世界 X/Y 和 `GridPositionZ`，加上块的 `visualOffset` 与手柄输入偏移，随后按 `SnapPositionToGrid` 取整，再调用块的 `GetZPosition` 决定前后深度，并更新网格高亮与位置变化事件。UI 菜单或指针位于 UI 时返回远离画面的哨兵 `(1000,1000,0)`。证据：`PreviewPosition` `IL_0000..0141`。`Click` 在建造模式排除菜单、UI 指针和已拖动相机输入，执行翻转检查、预览定位、落块与下一块预览；其它分支分别毁块、吸管和刷材质（`IL_0000..00BC`）。

`BuildingBlock::get_GridSubdivision` (`0x06000053`, `IL_0000..003F`) 的分支为：全局禁细分或 `cells.Count > 6` 用 1；5–6 个 cell 用 2；2–4 个用 4；单 cell 用 8。`GridManager::SnapPositionToGrid` (`0x06000138`, `IL_0000..0040`) 对每个坐标执行 `Round(coord × subdivision) / subdivision`。这里 X/Y/Z 都走取整函数；预览随后又覆写 Z。它是点位对齐，不等于编辑连续建筑轮廓。`GridManager::GetCell` (`0x06000137`) 对越界返回 null；当前方法并未见占用拒放检查，不能凭 `GridCell` 名称推断格子唯一占用。

## 前后层次与翻转

`GetZPosition` 可选地在块的 `raycastPositions` 发出向前的物理射线，暂时禁用该块子 Collider，从 `depthColliderLayer` 收集命中 Z；无命中时用网格基准 Z。它排序、去重命中深度；`depthSampleMode` 选择最大、最小或随机命中（由 `IL_008E..00DD` 的 switch 可见），然后以 **0.4 世界单位**为目标间距补足候选层，并向前、向后各追加 `5 + additionalDepthSteps` 个候选；低于 **0.02** 的近重复项会去掉。最终以选定基准项的索引加上手动 `currentDepthIndex`，夹入有效范围，返回对应 Z 加 `zOffset`。证据：`GetZPosition` `IL_0011..01FC`、`GetDepthRaycastHits` (`0x0600005F`) `IL_0006..014C`。`GridManager::RoundZDepth` 另有 `Round(z / depthIncrements) × depthIncrements`，构造器把 `depthIncrements` 设为 0.3；不能把该函数直接当成 `GetZPosition` 的 0.4 分层规则。

`CheckFlipping` (`0x06000060`, `IL_0000..005A`) 在启用深度射线时分别测未镜像与镜像命中。未镜像无命中、镜像有命中时得到自动翻转候选；它与 `ForceFlip` 做异或，结果为真则 `Flip`，否则 `UnFlip`。`Flip` 对翻转父节点做负 X 缩放，并设 `flipped` 字段（`0x06000061`）；这是预制件局部镜像，不等于重新生成屋顶或墙网格。[资源补证](04-packaged-blocks-and-combinations.md) 已解析目标文件中块的射线采样点字段，但未验证 collider 几何和实际命中，不能断言每个块都会自动翻转。

## 落地与贯通算例

`PlaceBlock` (`0x060000A6`, `IL_0000..017D`) 在预览开启时根据传入 XY 和 `GetZPosition` 构造实例位置，按块的视觉强度选择小/中/大声音、粒子和相机震动，再 `Instantiate` 构件、设父节点、调用 `OnPlace`、加入 `allPlacedBlocks`，通知 `CombinationManager::OnBlockPlaced`，登记撤销步骤并发出放置事件。`OnPlace` 当前调用的是放置动效 (`0x06000059`)，不是网格生成入口。代码没有在此处把相邻块布尔融合或重建接缝。

**构造演算，非运行观察。** 假定细分允许、当前块有 2 个 cell，`visualOffset` 和手柄偏移均为零；指针落在 `(2.21, 3.34)`。细分值为 4，预览 XY 变为 `(Round(8.84)/4, Round(13.36)/4) = (2.25, 3.25)`。再假定该块不使用深度射线、网格基准 Z 为 5、`zOffset=0`、手动深度索引为 +2：候选 Z 以 0.4 间隔排列，返回 5.8。点击后在 `(2.25,3.25,5.8)` 实例化一个构件并把二维放置坐标传给组合检测。实际场景的网格基准、块 cell 数、偏移和材质需解析场景与 prefab 才可代入；上述数值只是验证规则如何串接。
