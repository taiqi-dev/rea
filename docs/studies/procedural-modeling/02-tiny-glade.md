# Tiny Glade 建筑模型生成

Tiny Glade 的本地发行包显示出多种建筑生成职责：墙与路径的分段、石拱轮廓、木墙与木板、屋顶、楼梯和装饰。GPU 则读取每个砖块或瓦片的实例数据，完成变形、裁剪、绘制组织和部分动画更新。要理解其复杂度，可以先用作者公开原型中完整可读的墙与拱门算法建立直观认识，再检查发行版已经确认的表示和公式。

## 证据层次

本文分别标注公开原型源码、发行版 SPIR-V 指令、发行版 PDB 符号和机制推断。原型中的参数不视为发行版参数，符号名不视为已恢复函数体。身份与工具范围见 [证据说明](00-evidence-and-scope.md)。

## 曲线怎样铺成砖墙

**公开原型源码。** [WallConstructor](https://github.com/anopara/country-slice/blob/3f6a459c0424ed9177a0dceec4d72a380cbd80c2/src/geometry/wall_constructor.rs#L23) 把墙表示为一条曲线和沿高度的分层。先在归一化曲线空间中划分砖块区间，扰动内部边界，再把砖块中心映射回曲线位置，并按曲线切线定向。端点保持固定，所以局部变化仍能覆盖原有长度。

原型主体分层数取 `floor(墙高/目标砖高)`，每行砖数取 `ceil(曲线长/目标砖宽)`；分层边界还包含最终端点，循环在顶部另外产生一排。它还随机拆分部分非顶部砖、改变深度，并省略部分顶部砖，形成细节和破损。随机数生成器在这个函数内以固定种子初始化；这不建立发行版的随机稳定性。

**构造演算。** 取原型的目标砖宽 0.2、墙高 1.4、目标砖高 0.2，给一条长 2.0 的曲线。主体分层数是 7，每行先划分 10 个水平区间。例如扰动后的相邻边界为 0.20 与 0.31，那么这一块的中心在 `u=0.255`，宽度为 `(0.31-0.20)×2=0.22`。随后从曲线取得该位置和切线，生成平移、旋转、缩放。示例边界是构造值，不是重放原型的随机序列。

这样能从少量可重复使用的砖模型产生自由曲线墙；砖块外形、排列边界和墙整体形状由不同层控制。

## 路径怎样形成拱门

**公开原型源码。** [路径笔刷](https://github.com/anopara/country-slice/blob/3f6a459c0424ed9177a0dceec4d72a380cbd80c2/shaders/compute_path_mask.comp) 把鼠标世界位置映射到二维掩码，添加或擦除区域；[模糊 pass](https://github.com/anopara/country-slice/blob/3f6a459c0424ed9177a0dceec4d72a380cbd80c2/shaders/blur.comp) 形成连续变化的采样值。它不是已经证实的严格有符号距离场，源码中的 SDF 注释不替代数学定义。

[墙片元程序](https://github.com/anopara/country-slice/blob/3f6a459c0424ed9177a0dceec4d72a380cbd80c2/shaders/instanced_wall.frag#L257) 在墙中面位置采样掩码值 `m`，用下式得到局部开口高度：

`h(m) = 1 - exp(-5m)`

当 `m > 0.01` 且片元在墙中面的高度低于 `h(m)` 时丢弃片元。路径穿过墙时，墙上出现开口；周围平滑变化的掩码控制轮廓。开口部分在这一实现中由着色器裁剪形成，不能据此说原型执行了完整网格布尔切割。

[拱段选择](https://github.com/anopara/country-slice/blob/3f6a459c0424ed9177a0dceec4d72a380cbd80c2/shaders/arch_curve_segments.comp#L60) 遍历墙曲线相邻点，只要任一端采到正掩码，就将该段加入输出 buffer，并原子增加间接调度计数。[拱线铺砖](https://github.com/anopara/country-slice/blob/3f6a459c0424ed9177a0dceec4d72a380cbd80c2/shaders/arch_layout_bricks.comp#L155) 裁去外侧平坦端，采样近似拱线弧长，以 `max(floor(弧长/0.2),1)` 选择砖数，再沿近似等弧长位置排列砖块。砖的长度由相邻采样点距离决定，方向由局部段切线决定，结果写入实例矩阵与间接绘制计数。

**构造演算。** 沿墙采到的掩码为 `0、0.2、0.5、1、0.5、0.2、0` 时，对应开口高度约为 `0、0.632、0.918、0.993、0.918、0.632、0`。若其中一段抬升后的近似弧长为 1.03，按原型公式得到 5 块拱砖，每块覆盖约 0.206 的弧长；最终直线弦长会随曲率变化，不能把 0.206 当成每块实际宽度。

原型的 [render_loop](https://github.com/anopara/country-slice/blob/3f6a459c0424ed9177a0dceec4d72a380cbd80c2/src/render_loop.rs#L42) 在更新当前路径和模糊之前就用已有模糊纹理计算拱段及拱砖，随后更新纹理再绘制。它体现跨 pass 数据依赖，不能把概念顺序写成同一帧内严格按笔刷、模糊、拱砖执行。

## 细节怎样保持手工感

**公开原型源码。** [墙顶点程序](https://github.com/anopara/country-slice/blob/3f6a459c0424ed9177a0dceec4d72a380cbd80c2/shaders/instanced_wall.vert#L67) 对主体按行关联扰动，对顶部按砖实例关联扰动。沿墙的波形改变顶点高度，同时按高度混合地形位移：下部跟随地面程度较大，上部较小。相邻砖使用关联规则，因而变化有连续性，而不是各顶点完全独立。

**发行版指令。** `wall/wall_brick_lod0.precomp` 中 vertex 模块位于文件偏移 `0x9f`，`InstancedWallData` 声明了压缩变换、平移、`sin_deform_y_packed`、`arch_and_wallspace_packed`、种子、来源与标志。`0x2a9b–0x2b1b` 从实例缓冲读取并解包变形参数，`0x2ce3–0x3137` 解包和构建变换，`0x3297–0x33e3` 在特定标志分支中按砖顶点位置混合参数，最终写出世界位置和法线。

发行版具有参数化实例变形是直接证据；目前未把其整个变形表达式还原为公开原型的正弦公式，也未证明逐帧随机种子如何保持稳定。

## 发行版怎样拆分建筑规则

后续已从发行版实际指令进一步恢复道路开口、石拱轮廓、分砖和按墙重建，见 [26–30道路石拱专题](30-tiny-glade-road-arches-evidence-ledger.md)。下面保留首轮符号定位时的候选与未决问题；其中已回答部分以新专题为准，公开原型仍单独标注。

**匹配 PDB 的符号线索。** 下列符号说明存在专门的结构入口，其函数体和完整调用顺序尚未恢复。

| 模块或入口 | 已见职责线索 | 尚需回答 |
| --- | --- | --- |
| `system_wall_constructor::segmentation::calc_path_wall_segmentation` | 路径与墙的分段 | 交点、容差和多路径重叠如何处理 |
| `construct_arches`、`profile::create_stone_arch_profile`、`arch_walker::ArchWalker` | 石拱轮廓与沿拱线布局 | 发行版拱形公式及失败边界 |
| `construct_wooden_walls` 中 `subtract_wall_cutouts`、`subdivide_region_into_planks`、`merge_narrow_planks_horizontal` | 墙面开口与木板细分、窄板合并 | 具体裁剪表示和合并条件 |
| `utils::half_timber::half_timbering` | 木骨架规则 | 支撑杆选择与交叠处理 |
| `system_roof`、`resources::roofs::roof_shape` | 屋顶几何与形状表示 | 屋脊、圆塔顶、相交屋顶的完整拓扑规则 |
| `system_decorator` 的楼梯结构图与 dirty 传播入口 | 结构关系与失效更新 | 哪些编辑触发哪些对象重建 |

这些入口比把所有内容称作一个随机生成器更有研究价值。它们支持“分工明确的构造规则”这一结构判断，不能单独证明采用某个完整几何算法，也不能证明没有局部 WFC。

可复查的核心入口如下。40 个选定入口都成功取得零位移编译器源行记录；记录中的私有源码路径只用于定位，不意味着取得了私有源码。大小来自 PDB 符号，不保证覆盖内联后的全部逻辑。

| 入口 | RVA | 字节数 |
| --- | --- | ---: |
| `calc_path_wall_segmentation` | `0x801390` | 3177 |
| `split_brick_by_holes` | `0x815BE0` | 622 |
| `create_stone_arch_profile` | `0x811D10` | 4190 |
| `split_into_random_rows` | `0x846C00` | 2401 |
| `sine_wave_deform` | `0x847B40` | 203 |
| `Roof::profile_curve_normalized` | `0xB772D0` | 842 |
| `assemble_roof_tiles` | `0x1F46490` | 2917 |
| `playermade_stairs_assembly_propagate_dirty_flags` | `0x8970C0` | 2211 |

PDB 的游戏 CPU 结构字段本轮未恢复，不能把着色器的存储结构直接当作 CPU 对象布局。

## 屋瓦怎样生成可动的细节

**发行版指令。** `nani_instanced_roof.precomp` 的 vertex 模块位于文件偏移 `0x9d`。其中 `RoofShingle` 包含基础位置、当前高度、裁剪面、缩放与参数、旋转、墙槽身份、压缩速度与转动、动画进度、种子，以及圆形和屋顶主体标志。屋瓦至少有独立实例状态，并非所有屋顶视觉只能由一个固定网格完成。

`roof_tiles_gravity.precomp` 的 compute 模块位于文件偏移 `0x6c`，以每个瓦片为对象更新实例缓冲。`0x18ac–0x1988` 的简化积分为：

`q = floor(50t) / 50`

`a = -98.100006 × mix(1, 0.4, q)`

`v_next = v + a × dt`

`y_integrated = y_effective + v_next × dt`

这里 `t` 来自缩放参数中的分量，`dt` 来自 frame constants。位置的前处理还受墙高变化影响；后处理在接触目标高度时限制位置和速度，随后使用 `1-exp(-dt×glue)` 向 `roof_pivot_y` 混合，某个 `q>0.9` 分支直接回到目标高度。最终把高度和压缩后的速度及转动写回 buffer，见 `0x1fa8–0x2020`。

**构造演算。** 取 `q=0.5`、`dt=0.016`、初始速度 0、有效高度 0.5。加速度约为 -68.670，下一步速度约为 -1.09872，积分高度约为 0.48242。这个值仍需经过接触和粘合处理，不能当成最终屏幕位置。原作单位、所有参数范围和调用频率尚未建立；也不能把这一个动画 pass 宣称为完整刚体模拟。

## 生成怎样与显示组织配合

**发行版指令。** 墙的 compute pass、砖块块级前缀和、实例间接索引、两种 LOD 顶点与片元程序均已解码。`wall/prefix_brick_chunks.precomp` 的 `0x148c–0x1768` 对共享整数计数做加法和屏障同步，并将前缀结果与组内总量写往可见砖块输出缓冲。这支持 GPU 上按块组织可见实例的判断。整条绘制管线的实际帧调度和性能收益尚未测量。

**发行版指令。** `paths/combine_path_exclusions.precomp` 的 `0x46e–0x5d6` 读取路径与三种石板路 mask 的首分量，将总和限制到 `[0,1]` 并写出共同排除掩码：

`E = clamp(path + cobble1 + cobble2 + cobble3, 0, 1)`

**构造演算。** 若四项为 0.2、0.4、0.7、0，则输出为 1。它把不同路径表示合为同一个占用信号。该 pass 自身不证明所有装饰或建筑最终怎样读取这张掩码。

## 首轮缺口与第二轮续查

第二轮已对同一 EXE/PDB 做只读 CPU 指令解码。屋顶幂剖面、水平截面、墙洞局部裁剪和接缝显示的具体公式见 [屋顶形状](03-tiny-glade-roof-shapes.md)、[建筑相交](04-tiny-glade-intersections.md)、[接缝显示](05-tiny-glade-seams.md)。首轮下面列出的入口已不再只有符号证据，但完整结构调度和所有生成分支仍有缺口。

1. 发行版石拱轮廓与 `ArchWalker`：怎样确定洞口边界、拱厚、砖数及相邻拱口合并。
2. `system_roof`：建筑轮廓和交叠输入怎样生成屋脊、斜坡面、裁剪面与瓦片布局。
3. `system_decorator` 的结构图和 dirty 更新：编辑一段墙后，哪些屋顶、窗口、木架、楼梯与装饰需要重新计算，旧结果怎样失效。

首轮未读 CPU 函数体；第二轮通过 Capstone 完成选定函数的静态指令解码，未取得原生反编译提供者或完整类型。续查应优先补齐屋顶瓦片生产者与裁剪平面消费者的关联，以及相交退化分支。运行观察若开展，应分别用单墙穿路径、两栋建筑相交和拖动楼梯端点三个最小场景检验。
