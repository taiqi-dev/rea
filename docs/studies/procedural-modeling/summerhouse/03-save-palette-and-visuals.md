# 保存重建与美术变体的边界

后续[19](19-palette-propagation-and-shared-state.md)补上Lake三套真实调色资产、manager和共享写端：按分类曲线过渡，普通切换入口跳过地形直接应用。最终像素、曲线数据和真实成本仍未验证。

本篇依据[固定程序集与工具边界](00-evidence-and-scope.md)。REA 成员 Evidence 为 `ev_dbf130a1797c92e37522986abf7c5c20d073a126086d567887d76411e92c7ddf`（Save/Placer）与 `ev_f1ce68a56c8253ecef304bbb32c0ed4c255a54b6241698c5491eb722f51a1c7d`（Paint/Palette/Vertex）。保存结构说明这个系统把什么视为可重建的建筑状态，但不能替代未解析资源来证明最终画面。

## 保存的是构件身份和位置

`SaveData` (`0x02000042`) 的字段为 `buildingBlocks`、`mapName`、`saveGameVersion`、`savedPalette` 和 `cameraPos`。其构造器 (`0x06000224`, `IL_0011..00A7`) 遍历放置器的 `allPlacedBlocks`，逐个新建 `SavedBuildingBlock`，并读取当前场景名、相机位置、活动调色板和版本。`SavedBuildingBlock` (`0x02000043`) 只有 `position`、`flipped`、`blockID` 三个数据字段；构造器 (`0x06000225`, `IL_0006..002F`) 从实例的 Transform、翻转标志和 `saveID` 取值。这里没有保存每个块的连续墙轮廓、屋顶控制点或逐顶点网格；这直接支持“由预制件身份和变换重建”的解释。

`SaveGameManager::SaveGame` (`0x06000215`, `IL_000D..003B`) 把新建的 `SaveData` 转为 JSON 写入所选保存槽；这轮没有读取任何用户保存文件。`LoadGame` (`0x06000218`) 检查文件、读取保存数据并比较 `saveGameVersion`，随后在淡出回调中应用。实际重建在协程 `<ApplySaveData>d__47::MoveNext` (`0x06000393`, `IL_001E..0105`)：先加载存档声明的场景并等待加载结束，再恢复调色板和相机，清空原有块，依次调用 `BuildingBlockPlacer::RecreateSavedBlock`，重置撤销历史。`RecreateSavedBlock` (`0x060000AC`, `IL_0000..0062`) 按 `blockID` 经 `BuildingBlockLibrary::GetBlockByID` 找预制件，再实例化、设置位置、加入放置列表，必要时翻转。找不到 ID 时该方法跳过；未见在此路径内生成新几何补救缺失资产。

**构造演算，非实际玩家存档。** 假定场景 `Coast` 已有一件 `saveID=12`、位置 `(2.25,3.25,5.8)`、`flipped=true` 的构件。保存会形成该块的三元状态及场景/相机/调色板；载入时以 ID 找相应预制件，放回同一世界位置并镜像。若版本不等于当前 `saveGameVersion`，`LoadGame` 在进入重建回调前返回；若库中没有 ID 12，`RecreateSavedBlock` 不产生这一件。`Coast` 和 12 都是构造参数，不是发行资源或真实槽内容。

## 换色与像素风格

`PaintBrush` (`0x02000039`) 带 `materialReplacements`，其中每项把 `originalMaterial` 映到 `replacementMaterial`。`GetReplacement` (`0x060001D9`, `IL_0000..0049`) 按材质引用相等查表。实际放置器的 `PaintBlock` (`0x060000A1`, `IL_0000..0029`) 对当前射线命中块调用 `BuildingBlock::ReplaceMaterials(PaintBrush)` (`0x06000064`, `IL_0000..0064`)：遍历子 Renderer，对每个 `sharedMaterials` 槽查询该映射，只在至少一个槽被替换时写回，再刷新块的原材质记录。`PaintBrush::Paint` (`0x060001DA`) 也有类似遍历，但当前触发链使用的是块上的方法。因而“刷子”改变的是现有构件的材质绑定；这段没有生成新的窗洞或表面网格。

`ColorPalette::ApplyMaterialColors` (`0x060000DD`, `IL_0000..005B`) 对调色板中每对材质直接写 `_BaseColor` 与 `_EmissionColor`；同类还配置附加材质、环境光、雾、地形图层色等。`SetVertexColors::Start` (`0x06000262`, `IL_0000..00AB`) 遍历子网格现有顶点色数组，只按配置改 R/G/B 中一个通道，再写回 Mesh；它表明有运行时顶点色调整，不证明几何是运行时生成的。`PixelizeFeature/PixelizePass` 的类型与渲染方法说明程序集有像素化后处理路径；是否在每个场景启用取决于尚未解析的 URP 资源配置。

**构造演算，非实际美术资源。** 若某构件 Renderer 的材质槽为 `[砖A, 木A]`，刷子映射仅有 `砖A→砖B`，放置器调用 `PaintBlock` 后会得到 `[砖B, 木A]`；随后若活动调色板对 `砖B` 写入基础色和发光色，所有实际共享该材质引用的渲染器都可能受影响。真实材质名字、共享关系和画面颜色未读取，不能据此宣称某个场景一定出现特定外观。

**存档限制。** `SavedBuildingBlock` 没有逐块刷子/材质字段，已读 `ApplySaveData` 和 `RecreateSavedBlock` 也没有恢复每块刷色的分支。因此目前没有证据证明逐块刷色能跨完整保存/重新启动保留；也不能仅凭这些静态字段断言玩家实际刷色一定丢失，尚需资源配置和受控运行场景验证。[资源补证](04-packaged-blocks-and-combinations.md)已列出 `sharedassets0.assets` 内的 prefab 与网格引用数量；材质实际绑定、贴图和最终画面仍未分析。
