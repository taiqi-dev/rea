# 从程序生成研究到Unity最小demo

本文把上级case study接到[Unity实施入口](README.md)。研究文档继续描述原目标及其证据；demo文档描述我们选定的算法和验证。无需把历史证据全文改写成“原作已经使用了我们的实现”。

## 1. 三种来源分别使用

1. 原制品观察：固定EXE/PDB/资源身份、字段、调用和shader范围，保留原报告限制。
2. 自研规格：直墙分格、BoxCollider覆盖、火水数值、永久损坏格和支持移除，是本次独立选择。
3. Unity平台契约：参考版本化官方API；实际工程需固定编辑器/包版本并验证。

原研究未知的地方，用自己需求选择明确算法；不把教科书补全、Unity默认行为或AI输出写成原作事实。首次实现只依据这里的行为契约独立写代码，不把恢复指令转译成生产源码。

## 2. 每组研究对demo的用途

| 原研究 | 可以采用的设计原则 | 本demo的具体选择/阶段 | 保留的边界 |
| --- | --- | --- | --- |
| [00身份](../00-evidence-and-scope.md)、[01 Bad North](../01-bad-north.md)、[02总览](../02-tiny-glade.md) | 模块/参数与产物分开；来源固定 | 所有阶段以自己的资产/逻辑ID为准 | Bad North约束传播、公开原型与发行Tiny Glade不同 |
| [03屋顶](../03-tiny-glade-roof-shapes.md) | 屋顶形状参数化 | M1用自己的线性双坡，R/D决定坡度 | 不照搬20点剖面/逆截面常数 |
| [04相交](../04-tiny-glade-intersections.md)、[05显示](../05-tiny-glade-seams.md)、[06账本](../06-tiny-glade-evidence-ledger.md) | 关系生成额外构件；显示裁剪与实体几何不同 | M1矩形厚墙收口；任意房屋相交在后续 | 不把GPU片元取消当实体开洞/封口 |
| [07水域](../07-tiny-glade-water-shape-and-banks.md)至[10管线](../10-tiny-glade-water-render-pipeline-and-bank-transition.md) | 水形、地形、显示通道有不同职责 | M4仅AddWater状态作用；河流在后续 | 加水工具不等于流体/河岸/反射系统 |
| [11锚点](../11-tiny-glade-stair-anchors-and-paths.md)至[15楼梯账本](../15-tiny-glade-stair-evidence-ledger.md) | 附着端点、稳定身份及产物清理 | M3墙挂点；楼梯/平台在后续 | 不宣称已有完整承重或阶梯生成 |
| [16开口](../16-tiny-glade-window-placement-and-holes.md)至[20窗账本](../20-tiny-glade-window-evidence-ledger.md) | 窗对象发布切口与视觉，宿主分别消费 | M2矩形并集+真实厚度/碰撞；M3独立附件 | 首版无gothic形状SDF或屋顶窗 |
| [21起点](../21-tiny-glade-ivy-roots-and-state.md)至[25常春藤账本](../25-tiny-glade-ivy-evidence-ledger.md) | 附着、生长及剪除有独立owner | 后续可给墙上植被用 | 不进入M0–M7燃烧验收 |
| [26道路洞](../26-tiny-glade-road-openings-and-merge.md)至[30石拱账本](../30-tiny-glade-road-arches-evidence-ledger.md) | 开口范围合并、构件绕边布局 | M2先矩形；拱门/拱砖为后续类型 | 初始门洞不是已实现道路自动拱门 |
| [31地形](../31-tiny-glade-terrain-strokes-and-heightfield.md)至[35地形账本](../35-tiny-glade-terrain-evidence-ledger.md) | 连续表面与开口、读回/dirty分开 | M1平地、楼板及洞口侧壁 | 不需要GPU高度场或地形读回 |
| [36砖行](../36-tiny-glade-brick-row-layout.md)至[40墙布局账本](../40-tiny-glade-wall-layout-evidence-ledger.md) | 小件布局与避洞 | M6以后可加自己的砖/板铺排 | 不复用原随机、错缝、raw样式数值 |
| [41屋瓦](../41-tiny-glade-roof-tile-layout-and-clipping.md)、[42边平面](../42-tiny-glade-roof-edge-planes-and-seams.md)、[43木墙板](../43-tiny-glade-wooden-wall-board-layout.md) | 面域与小件协调 | M1连续屋面，M6可选瓦/板模板 | 本demo未实现圆环排瓦或曲板 |
| [44稳定随机](../44-tiny-glade-stable-randomness.md)、[45重建](../45-tiny-glade-shared-invalidation-and-rebuild.md)、[46植被](../46-tiny-glade-land-vegetation-and-exclusions.md)、[47账本](../47-tiny-glade-four-systems-evidence-ledger.md) | seed/逻辑ID/物理槽位分开；明确dirty | M5以损坏格ID保留破坏，不以实例下标保存 | 植被补种、完整调度不是首版前置 |
| [48屋顶表面](../48-tiny-glade-roof-trigger-mesh-and-attachments.md)至[52后续账本](../52-tiny-glade-roof-and-vegetation-followup-ledger.md) | 表面cache、RT/可见mesh和GPU处理不同 | M1/M3自己的墙面投影/碰撞 | 不采用未知完整renderer/植被发布 |
| [53墙输入](../53-tiny-glade-wall-footprint-input-and-curves.md)、[54放置](../54-tiny-glade-edit-picking-and-wall-placement.md)、[55阶段](../55-tiny-glade-edit-rebuild-stages-and-upload.md) | 编辑命令、投影和重建数据分工 | M0/M2参数编辑与固定墙平面拖动 | 自由绘墙/原45阶段图不必复制 |
| [56树](../56-tiny-glade-tree-resources-growth-and-canopy.md)、[57岩](../57-tiny-glade-rock-mesh-displacement-and-masks.md)、[58账本](../58-tiny-glade-input-edit-and-natural-shapes-ledger.md) | 原资源与运行变形不同 | 后续场景装饰，M6只做小件资源验收 | 不列为建筑最小闭环要求 |
| [59窗协调](../59-tiny-glade-decoration-snapping-and-merging.md)、[60墙厚](../60-tiny-glade-wall-thickness-and-contour-joints.md) | 类型尺寸与墙厚契约，邻居资格 | M2固定1.2m窗型与0.2m墙厚，显式拒绝重叠 | 首版不做窗等级自动合并或通用miter |
| [61树加工](../61-tiny-glade-tree-mesh-processing-and-publication.md)、[62历史](../62-tiny-glade-history-snapshots-and-regeneration.md)、[63账本](../63-tiny-glade-coordination-contours-trees-and-history-ledger.md) | 逻辑恢复与GPU槽位不同 | M5存定义/损坏并重新生成 | 不复制原历史文件schema或宣称像素级恢复 |
| [64小件](../64-tiny-glade-building-kit-and-asset-assembly.md)、[65窗灯](../65-tiny-glade-window-holes-and-lantern-components.md)、[66独立规格](../66-tiny-glade-seams-and-independent-building-kit-spec.md)、[67账本](../67-tiny-glade-building-assets-and-assembly-ledger.md) | 部件、切口、挂点、光源和接缝分别拥有 | 01资产库→M2窗洞→M3灯→M4破坏→M5保存 | 原mesh仅研究；新资产/原点/算法自己确定 |

若历史文件名或目录发生变化，应更新本表并验证链接，而非让读者从本机产物路径猜实现。全部研究继续保留对应证据账本，当前规格不重新声称原范围全部已验证运行。

## 3. 实施后再研究的方向

| 后续方向 | 触发条件 | 先回答的问题 |
| --- | --- | --- |
| 自由曲墙 | M1–M5闭环通过，需要更自由形状 | 轮廓厚度、自交、弧长附件坐标怎样保持 |
| 建筑相交 | 需要多栋自动协调 | 暴露面保留、封口、接缝owner及删除一栋后的清理 |
| 拱窗/拱门 | 固定矩形窗已通过 | 弧线几何、真实碰撞侧壁与框净洞契约 |
| 结构坍塌 | 简单永久破坏已经稳定 | 承重关系、断连检测、刚体碎块与逻辑状态怎样交接 |
| 热/水传播 | 单对象火水规则通过 | 作用范围/遮挡、快照贡献、邻接改变及帧率无关性 |
| 树岩植被/河流 | 建筑demo可玩后要扩展场景 | 场景排除、dirty、生成规模与水状态的实际耦合 |
| 高质量渲染 | M6资源验证后需要提升 | 光照、材质、实例化与LOD是否已成为实际瓶颈 |

这些是后续研究入口，当前没有启动新游戏调查、改变原制品授权范围或移植其它游戏模块。

### 构造映射例

原窗研究确认“装饰对象产生切口，宿主重建”；我们在M2选择二维矩形分格并挤出真实墙洞。原灯研究确认“外壳、发光和实际光源分开”；我们在M3选择Prefab部件与Unity Point Light。M4的湿度、燃料、损坏网格完全是新增自研规则。三条来源不会因为同一个小屋验收流程而变成“原作已有燃烧沙盒”。

未做：没有实施这些扩展或运行Unity。风险：研究能减少试错，但不能替代自己产品的资产、性能和可玩性验证。
