# Tiny Glade 远处屋瓦：深度分桶、可见性与数量边界

后续[108：分类消费者与绘制预算](108-tiny-glade-distance-meta-consumers-and-draw-budget.md)把meta接到网格索引／20 B命令，另补fine回调单次最大命令条数参数。具体atlas编号、物理绑定与实例容量仍未知；本文的70／1024不能直接当作瓦数上限。

本篇只追一条屋瓦路径：屋顶编辑后的 64B 实例如何成为 GPU 筛选候选，以及主视图 compute 怎样按距离写元数据、按可见性追加列表。结论是：选定 shader 确有 **70 视图空间深度门槛**与 **1024 个深度桶**；前者给实例写一种分类值，后者给索引/直方图定位。两者都不是已确认的瓦片容量、全局绘制预算或 LOD 网格切换阈值。实际进入 filtered list 的数目还受实例范围、视锥/HZB、前次可见位和缓冲状态制约。

屋瓦 CPU 布局与重建见[41](41-tiny-glade-roof-tile-layout-and-clipping.md)、[50](50-tiny-glade-roof-edit-messages-and-regeneration.md)；已有 GPU 主视图 HZB 推导见[49](49-tiny-glade-roof-gpu-visibility-and-depth.md)。[51](51-tiny-glade-vegetation-counts-and-active-list-rebuild.md)的草活动前缀属于另一类植被列表，不能挪作屋瓦的活动数量。[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)的阶段图给静态依赖骨架，但不能据此补写每帧执行次数。

## 身份、证据与读取范围

当前输入为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184B）、同目录 `tiny_glade.pdb`（310,513,664B）及 `compiled-shaders/country-core/compiled/nani/cull_and_bucket_roof_tile.precomp`（45,431B）。本次重读两个本地文件长度；EXE/PDB 的摘要沿用先前已匹配身份记录（EXE `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`，PDB `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2`），**本次未重新计算摘要**。新 shader 结论来自原文件偏移与 SPIR-V 指令，不是 REA Evidence ID。

复用正式只读解析器 `docs/studies/procedural-modeling/tools/spirv_probe.py` 和既有 `.cache/procedural-modeling/followup-art-updates/spirv.core.grammar.json`，新原始记录在 `.cache/procedural-modeling/static-art-followup/tiny-glade/roof-tile-cull.json` 与同名 `.txt`。解析器找到 3 个内嵌模块，起点 208、10981、24642，结构指令数分别 454、594、914，零个被拒候选。本篇新增数值链只取**主视图 HZB 模块**（起点 10981）；原文件偏移是十进制，CPU 地址另标 RVA。SPIR-V 结构遍历不等于 shader 语义验证或运行观测。

## 实例生产与筛选入口

CPU 侧，`1F46490 assemble_roof_tiles`按有效 `RecalculateRoofCmd` 选择屋顶；`1F46A65 → 1F4A6C0`先回收该屋顶旧稀疏索引，非 flat 合格路径调用矩形/圆形布局，`1F49FD0 RoofTileSsbo.push`写 64B 瓦实例。这里的数量是**当前合格屋顶重建所产生的记录数**，不是 shader 中的 draw 数。复用[50](50-tiny-glade-roof-edit-messages-and-regeneration.md)与[41](41-tiny-glade-roof-tile-layout-and-clipping.md)的已核 CPU RVA 和原始记录；本次没有再反汇编这些函数，也没有补出 RoofTileSsbo 上传完成、实例池总容量或 CPU 对该 precomp 的逐项绑定。

选定 compute 的 `PushConstants` 四成员依次为 `world_subset / first_instance / instance_count / draw_list_index_base`（原文件 10981 模块的 `OpMemberName`，结构 member 0..3）。`16877–16981`从 `instance_count` 与 invocation ID 比较，`i >= instance_count` 直接退；通过者把 `first_instance+i` 作为实例索引，在 `17077–17237`读取 64B RoofTile 数据中的 base_position、current_height、打包 scale 与 raw 标志。它是**候选边界**，未见这里从屋顶编辑 dirty 集合直接生成 invocation。CPU 怎样设置四个 push 值、dispatch 的次数和真实候选规模仍未知。

## 深度与桶：两个不同用途

`17253–17557`把 `base_position + (0,current_height,0)`送入 `current_view.world_to_view`；其 z 分量记为 `z_v`。同段从压缩尺寸构造一个包围半径 `r`（包含 shader 常数 `0.5940300226`），用于后面的球形视锥/HZB 检查。本篇不把 `r`误作屋瓦世界宽度或像素面积。

`17593–17701`计算 `far = (-z_v > 70.0)`，再以 `is_main_roof_body` raw 值选择元数据。选定指令等价于：

```text
m = far ? 1 : 0
if rawFlag == 2: m = 2
if rawFlag == 0: m = 2
```

也就是 raw 标志 0/2 覆盖远近结果；对其他 raw 值才留下 0/1 远近分流。`m`在`22373–22401`写入 `filtered_instance_meta_buffer`，而该写入仍位于下文的“新追加”条件内。raw 字段名称和已知额外产物的值 2 来自[41](41-tiny-glade-roof-tile-layout-and-clipping.md)；这里只把 0/1/2 当字节分类，不将它擅自翻译成高低模、主体、阴影或网格切换。70 是对当前视图变换后 **负 z** 的比较，不是世界坐标中的 70 米，也没有证明来自 CPU 可调设置。

另一路 `17757–17917`建立深度桶：

```text
u = clamp((32.0 - z_v) * 0.003472222248, 0.0, 1.0)
bin = clamp_u32(uint(u * 1024.0), 0, 1023)
instanceBin = (first_instance+i) * 1024 + bin
```

`0.003472222248`是存储的 float32，约为 `1/288`；`OpConvertFToU` 的极端非有限/越界输入行为本篇未验证。shader 随后在 `22337–22361`把 `instanceBin`写到 `filtered_instance_buffer`；`22413–22477`则用 `draw_list_index_base*1024+bin` 定位并 atomicAdd 对应直方图格。**1024 是每个实例/列表基址后的桶宽**，不是最多只能有 1024 片瓦。`filtered_instance_allocator_buffer` 的原子返回值另外决定紧凑列表的写 slot（`22285–22361`），与桶编号、实例物理索引分属不同计数域。

同一模块确实计算了**投影后的包围范围**：既有[49](49-tiny-glade-roof-gpu-visibility-and-depth.md)核对 `20113–22005`将范围转换到 HZB 像素坐标，取最大像素跨度，按 `max(0,ceil(log2(max(极小正数,跨度))))`选 mip，再取四角深度。这里投影大小决定**遮挡测试采样层级**；已核路径没有把它直接作为“保留多少瓦”或“换 LOD1 网格”的预算值。是否有其他 CPU/shader 阶段依据屏幕尺寸另作细节选择仍未知。

## 从候选到本次追加

前述数值并不让每个候选都进入列表。已有[49](49-tiny-glade-roof-gpu-visibility-and-depth.md)核对主视图模块先作球形视锥与 HZB 筛选；`21677`等四次 `OpImageFetch` 合并深度，`21941`进行严格大于比较。通过后 `22033–22125`对 `next_visibility_bitmask` 原子置位；`22153–22261`读取 **prev** 位，仅在该位原先未可见时走 `filtered_instance_allocator_buffer` 的 atomicAdd 与上述 instance/meta/histogram 三项写入。于是“本次通过 HZB”与“本入口本次新追加”不同；本篇没有把这条追加数宣称为最终 draw instanceCount。其他 pass 是否早已加过同实例、bitmask 的清旧/交换和最终间接 draw 提交仍缺完整链路。

## 条件演算与预算含义

这是按指令构造的输入，不是实机画面。假设两个 rawFlag=1 的候选均通过视锥和 HZB、prev 位为 0，分别有 `z_v=-20`、`z_v=-80`；`first_instance=100`，它们是本次 invocation `i=0,1`，`draw_list_index_base=4`。前者 `-z_v=20≤70` 得 `m=0`，`u=52/288≈0.180556`，桶 `floor(1024u)=184`；后者 `80>70` 得 `m=1`，`u=112/288≈0.388889`，桶 `398`。于是 filtered 值分别为 `100*1024+184=102584`、`101*1024+398=103822`；直方图分别加在 `4*1024+184=4280`、`4*1024+398=4494`。两片使新追加 allocator 计数增加 2，但 slot 的并发顺序不保证固定。

若第二片改为 rawFlag=2，它的 `m`变 2，桶仍由 `z_v` 算为 398；若它的 prev 位原先为 1，当前位仍可被置位，但本入口不为它再分配 filtered slot。若 HZB 不通过，连本入口的当前位也不会在这条路径置上。若深度 `z_v≤-256`，上述 `u`达到或超过 1，桶夹到 1023；**桶饱和并不是远瓦被删除**。这些条件严格分开 producer 的瓦数、候选数、当前可见位、追加数和可能的最终 draw 数。

自研预算可以据此独立设计：生成侧按屋顶对象拥有实例 allocation；绘制侧用明确的视图输入控制筛选与分桶；分别给实例池容量、filtered 列表容量和每帧 GPU 成本设可量测上限。目标程序的真实容量检查、超限处理、近远网格选择、投影像素面积阈值、实际帧耗时与最终画面，在本证据中均没有闭合，不能把 70、1024 或屋瓦 JSON 的 LOD1 资源当作这些预算的现成答案。

## 答案边界与检查

**Answered：** 选定主视图 shader 的候选上界、70 远近分类的 raw 覆盖、深度桶公式、filtered/meta/直方图写址，以及 visible 与新追加分支的区别。**Partial：** CPU 屋瓦重建到选定 shader 的生命周期，只复用各端已核证据，缺上传、具体绑定和同帧依赖。**Unknown：** 容量、实际活动屋瓦数、LOD 网格切换、最终 draw 数、运行频率、GPU 时间及真实远处视觉。**Not Run：** 游戏/Unity/GPU 运行、附加、私存档、函数执行、shader 语义验证器和性能测试；既有 Ghidra 超时环境未变，本次未重试。

静态复读的检查范围为：原 precomp 三模块结构边界、主视图模块上述具体操作和写入条件；算例用独立算术复核。文档相对链接逐一检查。该范围不能证明整个渲染器所有变体、GPU 屏障或 CPU 最终提交行为。
