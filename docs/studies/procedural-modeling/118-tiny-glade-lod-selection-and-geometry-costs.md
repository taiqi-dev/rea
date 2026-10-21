# Tiny Glade：屋瓦 LOD 选择与几何成本

本轮新增可量化事实：发行包的 `roof_tile_lod1.json` 有 **8 顶点、36 索引、12 三角形**；通常的 `roof_tile.json` 有 **20 顶点、90 索引、30 三角形**。LOD1 的三项源网格计数都是通常网格的 **40%**。`roof_tile_backface.json` 则有 **20 顶点、108 索引、36 三角形**，不能把 `m=2` 当成更省的第二级 LOD。数值是发行 JSON 的几何计数，不是一次实际帧的 GPU 工作量。

## 身份与静态证据

目标仅为 `C:/Software/Steam/steamapps/common/Tiny Glade`。本轮重读同目录 EXE **65,612,184 B**、PDB **310,513,664 B** 的长度；首选映像基址沿用同版 PE 的 `0x140000000`。[106](106-tiny-glade-distance-detail-and-budgets.md)记录的既有 EXE/PDB SHA-256 身份分别为 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`、`ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2`；本轮没有重新计算它们，也没有重新打开 REA/Ghidra。以下新值来自发行普通文件与[只读探针](tiny-glade/tools/lod_geometry_probe.py)，不是 REA Evidence ID。

输入 `assets/nani_meshes.ron` 为 16,124 B，SHA-256 `fefe20932f8112d6b6628ff6a1f8e75836b07ef92e219ac93298c9c3a22cda16`。其中 **204–209 行**的 `RoofTile` 列表依次指定 `roof_tile`、`roof_tile_lod1`、`roof_tile_backface`。探针读取这三个 `assets/meshes/*.json`，检查唯一 `Vertex_Position` 属性为 float3、索引为 int、长度可组成三角形、每个索引在顶点范围内且所有顶点被引用。新元数据原始回执在 ignored `.cache/procedural-modeling/tiny-performance-batching-lod-shadows/lod/roof-tile-geometry.json`；没有导出原始顶点或索引到正式目录。

| RON 顺序/条件部件号 | 资源；JSON 字节；SHA-256                                                                             | 顶点 / 索引 / 三角形 | 索引范围；局部包络 X/Y/Z      |
| ------------------- | ---------------------------------------------------------------------------------------------------- | -------------------: | ----------------------------- |
| 0                   | `roof_tile.json`；1,453；`2090152d3a11f9928701a8f6e716f1404dfc89f3802aede71fbc705ffe9bec8c`          |         20 / 90 / 30 | 0–19；X 约 ±0.59403，Y/Z ±0.5 |
| 1                   | `roof_tile_lod1.json`；414；`0c8a3c5e2a9036c63e629b39d55ecf59d2eaed39341d9f3e548485b0fe46a017`       |          8 / 36 / 12 | 0–7；X/Y/Z ±0.5               |
| 2                   | `roof_tile_backface.json`；1,511；`240f8f5874250e34642c76994d8ba89acbb13a8dc7d418815a5df9c9c4a29dc3` |        20 / 108 / 36 | 0–19；X 约 ±0.59403，Y/Z ±0.5 |

三者的 `double_sided` 均为 false。LOD1 的包络保持近似单位盒，顶点从 20 减到 8、三角形从 30 减到 12；这是**资源几何简化**，不代表 GPU 在实际像素、顶点缓存或裁剪后的同比节省。JSON 索引宽度、atlas 转换后的实际 `index_count` 与 GPU 内存布局尚未逐字段实测。

## 从距离分类到几何选择的证据链

[106](106-tiny-glade-distance-detail-and-budgets.md)在主视图屋瓦 cull shader 的包内模块起点 **10981（十进制文件偏移）**，确认通常 raw 标志在 `-view_z>70` 时给 `m=1`，否则给 `m=0`；raw 为 **0 或 2** 的分支改写为 `m=2`。进入 filtered 列表还要通过候选范围、视锥、HZB 与 prev 可见位门。距离比较先决定 _meta 分类_，不是不经筛选就提交绘制。

[108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md)的 sorted fill 把分类放进排序值的低 10 位；`generate_draw_lists.precomp` 的 `0x1428–0x1478` 再以 `%1024` 还原 `mesh_index`，于 `0x1664–0x1698` 从 `atlas_part_info[world_subset, mesh_index]` 读取 `index_count/first_index`，写入 20 B 间接命令。[110](110-tiny-glade-roof-atlas-budget-and-graph-views.md)追到加载特化 `0x141826650` 顺序消费上述 RON 列表并交给 `MeshAtlasLibrary::add`；**fresh subset、空闲槽为空、三次添加成功、无覆盖**时，三份网格才条件对应部件 0/1/2。本轮的新资源计数接在该条件映射之后：通常 raw 且较近选择精细模板，较远选择较简单的 LOD1；覆盖分支选择 backface 模板。热重载和 mod overlay 可改变实际 atlas 部件身份，不能把发行文件顺序写成所有运行会话的绝对索引。

这里有三种不同的“细节/粗度”，不能混称。**几何 LOD** 是上述 `m=0/1` 对不同源网格与 atlas 部件的条件选择。**fine/coarse sorted 回调** 是 CPU 绘制提交路径：[112](112-tiny-glade-external-pool-producers-and-draw-bindings.md)在 `0x1409E5AA4–0x1409E5AD4` 确认 `FORCE_FINE!=0` 选 fine，否则 `RoofTile=6>1` 选 `coarse_sorted_draw_fn`；coarse 于 `0x1409E69C4–0x1409E69D3` 调 `draw_indirect`。`FORCE_FINE=0` 的 RoofTile 因此是 coarse **提交回调**，不表示它只选 LOD1，且实际开关值仍 **Unknown**。**HZB mip** 是遮挡查询采样层级：[106](106-tiny-glade-distance-detail-and-budgets.md)的投影范围计算在 `20113–22005` 按最大像素跨度取约 `max(0,ceil(log2(span)))`；例如跨度 13 像素会选择 mip 4 的尺度。这一步用于深度比较，不是每瓦的三角形数量，也不是 `70` 的距离门。

## 带输入的预算演算与独立 demo

以下是**构造输入**，不是 Tiny Glade 实测场景：假设同一视图中 10,000 条屋瓦记录最终通过各自筛选并进入对应列表；其中 4,000 条通常 raw、`-view_z=20`，5,000 条通常 raw、`-view_z=80`，另 1,000 条 raw=2（即使 `-view_z=80` 也被覆盖为部件 2）。再假设 fresh atlas 的条件顺序成立，并且 atlas 中每份资源的 `index_count` 等于发行 JSON 的索引数。

| 分类           | 条数 × 源索引 |  索引引用数 | 源三角形提交数 |
| -------------- | ------------: | ----------: | -------------: |
| `m=0` 通常近瓦 |    4,000 × 90 |     360,000 |        120,000 |
| `m=1` 通常远瓦 |    5,000 × 36 |     180,000 |         60,000 |
| `m=2` 覆盖瓦   |   1,000 × 108 |     108,000 |         36,000 |
| **合计**       |               | **648,000** |    **216,000** |

在保持 1,000 条覆盖瓦仍为 backface、只把 5,000 条通常远瓦改为通常精细模板的对照中，合计为 **918,000 索引引用、306,000 源三角形**。此构造的 LOD1 选择少 **270,000 索引引用、90,000 源三角形，约 29.4%**；节省完全来自 `5,000×(30−12)`。它不是 GPU 时间、FPS、显存、可见像素或实例池容量的测量。真实候选可能因视锥/HZB/prev 位而不在本入口追加，实际 count buffer、atlas 转换与不同 pass 都会改变结果。

独立 demo 可使用自制屋瓦模板：为同一逻辑实例准备高/低两张网格（例如 30 与 12 三角形），在视图输入与资格筛选后写明确的几何级别，再按级别聚合实例并用各级 `index_count` 提交。另把遮挡 mip 只用于可见性查询，把 fine/coarse 提交策略当作独立优化选择。先量测每级实例数、索引引用数、实际绘制条数和 CPU/GPU 帧时，再调整自己的距离阈值、滞回及预算；本研究的 `70` 是原版本的视图深度比较值，不是可直接移植的屏幕像素阈值。自研只采用行为规格与自制资源，不搬运发行网格。

**Answered（静态）**：三份发行屋瓦资源的源几何计数与简化幅度；结合已有 shader、sorted fill、atlas 顺序与 CPU 回调证据，可说明几何 LOD、排序提交粗细和 HZB mip 各自作用。**Partial**：发行资源到启动后的 atlas `index_count` 和物理 GPU backing；mod/重载后的部件编号。**Unknown**：开关实值、可见实例分布、实际抽取/提交数、GPU 时间和 FPS。**Not Run**：游戏、Unity、GPU、私人存档、运行探针、性能测试、Ghidra 重试；仅做本地 JSON 格式/索引检查与算术核对。
