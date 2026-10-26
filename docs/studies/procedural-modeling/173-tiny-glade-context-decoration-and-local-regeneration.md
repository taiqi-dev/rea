# Tiny Glade：建房、画水后的附带装饰与局部重建

配套 [172](172-tiny-glade-terrain-generation-and-randomness.md) 区分地形配方与噪声，[174](174-tiny-glade-scene-style-presets-and-demo-design.md) 接主题资源/颜色/环境及自研分层。

2026-10-26，America/Los_Angeles。本篇回答装饰来源、随机性、排除和清旧；地形及主题生产另属独立专题。

## 结论与本轮增量

**附带装饰由多套规则共同形成。** 建筑周边草花灌木有 GPU 候选域，窗台有模型 marker 请求，窗/门周有 CPU 区域采样与重叠筛选，藤蔓有自己的根点和枝叶生命周期，水生植物又有独立的水域资格。不能把这些解释成一次全场景随机撒物件。

本轮新增核对门两侧区域入口、特定灯笼周围的五次候选、选定 CPU 环境排除调用，以及 `render_world` 中水图/建筑图与植被生成的实际调用连接。CPU candidate→pending→entity 与稳定区域机制已在 [19：窗周自动装饰](19-tiny-glade-window-autoclutter.md) 详细恢复；本轮重新读取当前 PE 的关键字段和调用，将其用于建房/水域的综合解释，不将旧结论冒称首次发现。

主要边界：**GPU 植被的全域候选重筛、CPU autoclutter 的区域重采样、藤蔓的剪枝，是三种不同的更新粒度。** 当前没有运行证据证明每次笔画只重建附近所有装饰，也没有恢复所有环境过滤、运行顺序和最终可见数量。

## 身份、权限与实际验证

目标是 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`，65,612,184 B；相邻 `tiny_glade.pdb`，310,513,664 B。沿用既定 GUID `d8d61d04-9e31-5b47-4c4c-44205044422e` / age1；本轮重读文件及长度，不计算新摘要。native 地址一律为 preferred VA，image base=`0x140000000`；旧报告中的 RVA 须另加 base。SPIR-V 地址是指定包内文件偏移，word offset 另注明。

REA native 已记录的 Ghidra 300 秒超时及关闭 session 条件未变，继续 bounded static fallback，不重试长分析。不运行/附加游戏，不加载目标 DLL，不操作 Unity、鼠标或前台，不读私人存档/配置，不安装软件，不导出原作几何/纹理，不生成 REA Evidence ID。以下是普通文件/PDB/指令证据，不是运行观察。

新记录在 ignored `.cache/procedural-modeling/tiny-context-decoration/`；正式验证器 [context_decoration_probe.py](tiny-glade/tools/context_decoration_probe.py) 实际通过 **20 个 native 锚点、17 个 direct-call、4 个 command callback 地址、6 个字面量、4 个 shader 的7处 atomic 追加锚点及芦苇三项严格比较**。输出 `proof.json`。初次检查发现手填的 RNG callee 地址有一位错误，按 PE 相对位移修正后通过；未把失败忽略。没有工程构建、Git 写入、SPIR-V 语义验证器或 GPU 验证。

## 1. 先分清用户看到的装饰来源

| 表现                         | 已证生产方式                                                                        | 随机与更新的实际作用域                       |
| ---------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------- |
| 地面草                       | 固定逻辑 ID 可重算候选位置；removal.R 排除、G 缩高；活动 ID 前缀单独重建            | GPU 草体系；不是有持久实体身份的每株植物     |
| 建筑脚边灌木/花              | `spawn_bushes_buildings` / `spawn_flowers_buildings` 的候选网格、噪声与多 mask 资格 | GPU 输出实例及计数前缀；选定入口扫描全逻辑域 |
| 窗台花箱等                   | cottage mesh marker→80 B WindowAutoClutterCandidate→104 B请求                       | 资源/marker 生产，与窗周随机候选不同         |
| 门/窗周小摆件与部分 CPU 植物 | 稳定键区域→局部采样→环境过滤→有序重叠筛选→实体请求                                  | 区域候选与 entity owner；已存在对象按键协调  |
| 常春藤                       | 根点选择、同朝向根间距、生长点、叶片及独立修剪                                      | 有状态枝条，不是每次全量重新撒叶片           |
| 芦苇、睡莲、睡莲花           | 水域/路径/建筑或花园资格、空间噪声、独立 buffer/计数                                | 水域派生 GPU 实例；叶与花分开计数            |
| 手放装饰、预置森林           | 独立编辑/配置转换路径                                                               | 不因附近自动装饰失效便当然删除               |

草/灌木公式和计数读写见 [46](46-tiny-glade-land-vegetation-and-exclusions.md)、[51](51-tiny-glade-vegetation-counts-and-active-list-rebuild.md)，窗台见 [19](19-tiny-glade-window-autoclutter.md)，树实例见 [171](171-tiny-glade-tree-instance-to-draw-binding.md)。[59](59-tiny-glade-decoration-snapping-and-merging.md) 的窗户等级合并属于用户装饰编辑，不是随机散布或普遍的碰撞推挤。

## 2. 建筑附近：GPU 草花与 CPU 区域分别处理

### 建筑图驱动的 GPU 灌木和花

当前 `render_world` 的 `0x1400FA1A8` 直接调用 `rasterize_buildings`；`0x1400FA1BE` 调草 removal mask，随后 `0x1400FA24F → 0x140B32850 spawn_vegetation_around_buildings`。这个1090 B入口实际获取三个写 buffer，选择字面 shader `country_core/garden/spawn_bushes_buildings:main` 和 `...spawn_flowers_buildings:main`，在 `0x140B32B2E` 传灌木90×90，在 `0x140B32BF2` 传花150×150，分别绑定后登记 dispatch。

这建立同一渲染编排内的“当前建筑相关图→建筑周边专用候选管线”。完整建筑编辑消息到 mask writer、全部 descriptor 身份及图执行依赖仍未逐字段恢复，不能说已观察一次房屋修改的最终帧。

选定建筑灌木分支沿46的真实规则：拒绝道路、水域、foliage、部分岩坡条件、非零 `plant_sample`、花园过强与未模糊建筑内部；还要求模糊建筑 R>0、空间值噪声 V(p)>.5、size_test≥.3。building.G 参与尺寸 pulse，building.R 另参与资格/尺寸测试。两个通道的上游数值语义尚不完整，**不能把 .4 等值直接换算成离墙多少世界距离**。

其候选的随机扰动由 invocation 坐标参与的整数混合计算，空间噪声形成成片密度。相同网格与输入不要求重新取一套时钟随机数，但原子分配只保证输出 slot，不保证实例序列稳定。灌木 shader 在包偏移 `0x4DD6` atomic追加灌木，在 `0x522A` 可追加花；花 shader 的两候选追加点为 `0x4318 / 0x6FB0`。本轮重核这些写端，不据90×90/150×150直接给实例总数。

### 门两侧与窗周的 CPU 候选区域

`add_autoclutter_around_gates`（`0x1428E8400`，2894 B）读取门相关几何与端部位置，构造两条路径，字面标签精确为 `gate_right` / `gate_left`（`0x1435B22C0 / 22CA`）。`0x1428E88F6` 和 `0x1428E8B23` 都以2作为循环边界；`0x1428E89BA` 根据当前 owner 信息及标签取得区域键，`0x1428E8B17 → 0x1410CFF30 AutoClutterState::add_region`。只读取目标内的键计算调用，没有在分析器执行它或另算摘要。

因此门两侧可进入与窗周相同的区域 owner。这里的2是**两条区域构造尝试**，不是“两件可见装饰”；后续每区是否采样成功、被环境拒绝、被优先级排除及实体复用另算。窗周的方向矩形与身份键完整式已在19；本轮不把门与窗的尺寸常数混为通用参数。

### 区域有稳定位置和类型抽样，最后还要让位

19已核：位置 RNG 使用由量化区域 origin 生成的输入，类型 RNG 以区域身份组合生成；选定类型分支按各资源权重的累计区间选择。资源缺失可把对应权重变成零；不同 category 有不同权重。**这属于给定布局输入的确定性抽样，不能据此承诺跨版本、跨改动的最终画面完全不变。** 邻区域资格和冲突排序仍会改变哪件物体被接受。

本轮重新接通候选字段：

```text
AutoClutterState +0x20/+0x28 : 152 B candidate 数组 / 长度
candidate +0x68             : 32 B Rectangle3d
candidate +0x88/+0x90       : 区域身份 / u32 排序值
candidate +0x40             : 请求稳定键
AutoClutterState +0x50/+0x58 : 104 B pending request 数组 / 长度
```

`process_autoclutter_candidates`（`0x1428E9FF0`，2279 B）先构造16 B OrderedCandidate，+0/+8拷贝原候选+0x88/+0x90，+0xC存原候选u16索引；被输入键集合排除的条目不进入此序列。排序比较在 `0x14219EF25–EF39`，先比较u32、相同时比较u64，均降序；不能把它写成随机打乱或按离光标最近排序。

之后依次比较已接受的矩形，`0x1428EA33B → Rectangle3d::overlaps_rectangle3d`；发生重叠即跳过。raw candidate +0x30=6绕过本次碰撞检测，但其box仍加入后续已接受列表。可接受项在 `0x1428EA4B0` 按104 B步长追加，`0x1428EA504` 更新+0x58长度。故特殊类型和普通类型不能统一说成“全都互斥”。具体品种到所有raw tag的完整映射仍未知。

### 环境过滤仍有未命名输入

本轮在 `populate_autoclutter_regions` 的一个内联分支确认：`0x1428DEC61 / DEC8A` 双线性采两份输入栅格，样值>0转到共同退出路径；`0x1428DECAE → PlantSampleRaster::has_non_grass`，返回真也走该路径；`0x1428DECC6` 再采 TerrainRockMask，非零亦进入同一路径。附近还存在地形高度取样、墙空间查询及 `BushGrid::bushes_near_point`。

这比名称命中更强，但**两张 float-grid 的源身份尚未逐字段定位，不在本报告直接命名成水图/道路图**，也不能把上述分支阈值概括为全部CPU装饰规则。46的GPU植被有自己的已恢复mask门槛，不用于替代这里缺失的CPU参数来源。

## 3. 局部重采样、实体复用与删除是三个步骤

`add_region`（`0x1410CFF30`，2062 B）分别在 `0x1410D01F7 / D02D0` 对旧、新区域AABB访问dirty/world-space cells。已存在且几何参数未变时刷新epoch；变化时撤旧覆盖、加新覆盖，把旧candidate索引排入移除队列。原区域之外的候选不因此全部删除。19详细列出比较字段、NaN及索引哨兵；本轮重核两处空间单元调用。

订阅者构造 `autoclutter_subscribe_to_tabloids`（`0x1428E6360`）登记RaycastWorld、WorldRaster、PlantSampleRaster及其他publisher；`populate` 的 `0x1428DC0A7` 实际take DirtyTiles，`0x1428DC0DD` 合并，再 `0x1428DC169` 迭代tile。既有网格映射把涉及region置为待采样。**区域采样是局部的，后面的候选排序/冲突协调仍读取candidate集合，不能说所有工作量都只随dirty tile增长。** epoch推进和各ECS system执行时序仍未知。

移除候选由 `flush_candidates_pending_removal`（`0x1410D0740`，718 B）处理：152 B候选swap-remove，尾项搬到空位，len--，并用尾项区域身份修复region中的u16索引；最后清移除队列。这个索引是临时密集槽，不能当作持久装饰ID。

`manage_autoclutter_entities`（`0x1428EAD00`，9779 B）在 `0x1428EAF22–AF26` **读取同一状态+0x50/+0x58、104 B步长**，按稳定键协调现有实体。19已证：找不到请求键的旧对象，以及特定不允许继续复用的位置变化，排入 `ClutterMarkedForDeletion`；允许的分支保留或更新。当前PE的 `0x1428EB877` 装入该标记命令的真实callback `0x1428D9330`。

新对象在 `0x1428EC251` reserve entity，`0x1428EC283` 装入 `spawn<AutoClutter>` callback `0x1428D96C0`。资源分支还能排队 `NaniBundle<PlantInstanceData>`（`0x1428EC70A → 0x1428D9720`）或 Uber 等不同绘制数据；**自动装饰并不全是树的 PlacementData 协议**。这些是延迟ECS命令，最终apply、动画退场、despawn、GPU释放均未在本轮闭合。删除标记不能当作已经物理销毁。

## 4. 画水以后：软水域筛选，而非每个笔刷点种一株

[07](07-tiny-glade-water-shape-and-banks.md)/[160](160-tiny-glade-water-brush-and-layered-eraser.md) 已证输入笔画经平滑写共同512²水域层；旧新范围参与dirty，CPU staging与GPU上传分开。当前 `render_world` 的实际静态调用顺序是：

```text
0x1400FA145 → water_rasterize_from_cpu
0x1400FA1A8 → rasterize_buildings
0x1400FA244 → water_spawn_vegetation
0x1400FA24F → spawn_vegetation_around_buildings
0x1400FA25A → read_bush_positions_for_cpu
```

这是CPU构图/录制顺序，不是观察到GPU已按该顺序执行，也没有把建筑图与水图误并为一份资源。`water_spawn_vegetation`（`0x140B31710`，1378 B）实际选择睡莲和芦苇 shader，睡莲逻辑225×225（`0x140B31A5D`），芦苇150×150（`0x140B31B44`），绑定对应写buffer和draw索引后dispatch。生成域与最终数量不同；[08](08-tiny-glade-water-vegetation-and-surface.md) 还说明芦苇尾部invocation边界未完全核实。

芦苇首计算模块的真实资格可取08已恢复式：先算水/路相关pulse量 A，须 A>0；再要求空间噪声 N(p+20)>.6、水图G值 W>.55、建筑图R值 B<.1。三项最后比较在原包 `0x298A / 299E / 29C6`，本轮复核严格不等号。接纳后在 `0x327A` atomic追加并写48 B实例。W是软mask通道，**不是已恢复的厘米水深**；水域变化可使原候选失去资格，不能据候选网格算法认定是在岸线上等弧长撒点。

睡莲使用另一套水域pulse和花园重叠，叶片与花分别atomic追加（原包 `0x6EE0 / 7320`），其增长动画另读写texel。GPU旧产物清理采用51确认的计数重置/有效前缀机制；本轮没有找到“每个被擦水像素直接删除一个CPU植物实体”的链。未闭合reset、所有producer和最终draw的全部图依赖，保留该限制。

### 一个容易误认的“水边装饰”入口

`add_lantern_water_setdresssing`（`0x1428EFA80`，1932 B）确实存在，但当前指令说明它先迭代 terrain decorators，raw kind=4或5、另一个标志=0才进入选定路径。随后用 `CachedDecoratorTransforms::transform` 取得owner变换，创建半径.65的Circle2d，以owner整数ID调用 `init_rng`，最多尝试5次（`0x1428EFF13`），通过 `Circle2d::get_pos_at_u` 取圆环候选，再按给定随机偏移扰动。

`0x1428EFFE7` 对输入grid做双线性样本，`0x1428EFFF0` 的<=0分支跳过；通过者在 `0x1428EFEAA–EFEFF` 追加同一104 B pending数组，类型选择中使用字面量 `lantern`。部分y/尺寸选择还取决于DragState和键的低位。**它以已有装饰owner为中心，不能解释成每次画水无条件生成灯笼或岸边石块。**

该入口调用的栅格deref函数被编译器与Garden/其他WorldRaster wrapper合并，`dumpbin` 显示的Garden名字不能证明实参就是GardenRaster；同样不能凭函数标题证明它必定是WaterRaster。本轮不为这一输入grid定名，也不赋raw kind4/5全部UI名称。水笔刷派生芦苇/睡莲的证据来自上一条GPU链，独立成立。

## 5. 藤蔓与石块的边界

藤蔓沿 [21](21-tiny-glade-ivy-roots-and-state.md) 的实际根候选与同朝向间距门槛，沿 [24](24-tiny-glade-ivy-pruning-and-updates.md) 按无有效墙、洞口或区域请求修剪。窗口消息可以提出局部剪除请求；命中后删的是枝条后缀及关联叶片，旋转等分支可删除整Ivy。它不是上述104 B autoclutter候选或GPU花草实例，不能用计数清零说明藤蔓清旧。

道路碎石、岩层网格、CPU摆件中的石质资源也不是同一散布器。[154](154-tiny-glade-ground-materials-and-pack-decoration.md) 只证明 path_pebble 资源加载及另一条岩层位移。**本轮未接通“房屋脚边/岸边的所有石头”完整资源类别、密度和发布链**，不能因看到石块截图或候选名字就补出统一石头算法。

## 构造演算与自研规格

**建房候选。** 自造三个资源权重[1,2,1]、u=.6，累计比例.25/.75/1，首次严格>u的是第1号槽；这是目标已证累计选择方式的独立输入，不使用原资源。再给同区域两个候选A/B的排序值分别(40,100)/(39,200)，二者矩形相交；先处理A，B因重叠被拒。若A被环境mask拒绝而未进入candidate集合，B可以被接受。稳定位置/种子不代表最终存在性无条件稳定。

**擦水候选。** 构造芦苇 W=.65、P=0、B=0、N=.7，水pulse A=.5，通过资格；给水平尺度随机值.5，得到s=1.25、sy=.78125。只把建筑值改成.1，严格B<.1失败；或水被擦到W=.3，W>.55失败。若本次先正确重置计数再重新追加，旧payload可以残留但不在新有效前缀。这里没有执行目标shader，也未观察一次真实擦水事务。

**局部区域与实体。** 自造候选索引表A→0、B→1、C→2。区域A变化排除0，swap-remove把C从2搬到0并修正C索引；新A待采样。若A重采样失败，B/C可继续存在；manager再据稳定键判断旧A的实体进入删除标记，而不是把B/C也按临时候选index删掉。真正销毁仍要后续生命周期证据。

我方可独立采用：以建造/道路/水域的既有状态为唯一输入，资源包负责模型；固定空间候选与区域owner负责稳定布局，各类mask负责资格；GPU草/花的有效前缀和CPU摆件的稳定身份分别管理。脏范围要包含旧/新覆盖及规则邻域；物体消失需区分失去生成资格、延迟删除与最终资源回收。手放摆件应由独立编辑所有权保护，不能随自动区域整批清掉。参数、随机函数与实现按自身需求编写，不搬原作资产或恢复代码。

**已回答：** 多生成器分工、建筑和水的选定生成入口/资格、门区域入口、稳定区域与候选冲突协调、pending到实体命令，以及局部失效与全候选筛选的区别。**部分：** 完整建筑/水编辑→publisher→consumer时序、CPU全部环境mask、最后绘制和删除。**Not Run：** 游戏、GPU、Unity、存读档、画面、性能、真实随机稳定性与最终数量验证。后续只值得围绕缺失的具体grid实参、publisher写端或删除consumer继续定点追踪；不重复用名称列表补成算法。
