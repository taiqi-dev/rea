# Tiny Glade：太阳级联阴影的图像预算与 caster 工作

本篇续查稳态渲染中的阴影成本。新接通的静态链为 `render_world → setup_directional_light_cascades → setup_shadows` 的级联视图生产，以及同一 `render_world → 阴影列表/HZB → shadow_pass` 的分层深度绘制。当前发行版在这条路径中给级联设置传入 **3 层、每层边长 1024**；这描述构图和资源请求，**不是实测每帧三次完整渲染或时间预算**。墙和通用实例有分别筛选、共享后续级联资源的路径，不能把主视图已剔除者直接当作不投阴影。

承接 [49：屋瓦太阳 shader](49-tiny-glade-roof-gpu-visibility-and-depth.md)、[70：更新与列表成本](70-tiny-glade-update-and-render-costs.md)、[72：CPU 绘制路径](72-tiny-glade-cpu-render-bindings-and-lifecycle.md)、[85：首桶与 `DontCastShadow`](85-tiny-glade-wall-bucket-and-command-writes.md)、[115：稳态两轮主视图](115-tiny-glade-steady-culling-and-submission.md)。以下地址均为 EXE preferred VA；函数名来自相邻 PDB，函数体和实参另用本地 PE 反汇编核对。

## 固定输入与方法

只读目标是 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B，PE x64，preferred base `0x140000000`）及相邻 `tiny_glade.pdb`（310,513,664 B）。沿用同版既有 SHA-256 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`；本轮未重算。PDB `*shadow*` 有 171 个候选，限定本题后 13 项；`*cascade*` 2/2、`*sun_view*` 0/0、`*SunView*` 4/4，均枚举完毕。名称只用于定位，结论以以下指令与资源读写为准。

VS `dumpbin 14.44.35222.0` 对 `render_world` 阴影段、`setup_directional_light_cascades` 和 `shadow_pass` 定点反汇编；现有 [SPIR-V 读取器](tools/spirv_probe.py)完整结构解码 `rhapsody-shadow/compiled/setup_shadows.precomp`（1 模块，677 指令，0 rejected）及 `country-core/compiled/shadow_receiver_frustum.precomp`（1 模块，430 指令，0 rejected）。沿用先前完整解码的 `wall/generate_draw_lists_shadow.precomp`（1 模块，823 指令，0 rejected）。原文与定点核对结果保存在 ignored `.cache/procedural-modeling/tiny-performance-batching-lod-shadows/shadows/`。新 [shadow_budget_probe.py](tiny-glade/tools/shadow_budget_probe.py) 校验 14 个指令字节锚点、6 个 direct call 目标和 2 个 shader 的结构/读取数，结果 Passed（`shadow-budget-anchors-v2.json`）。它们都是**普通本地 PE/PDB/SPIR-V 证据，非 REA Evidence**。父调查已有匹配目标 open 身份；旧 Ghidra 深度分析超时条件未变，本篇未再次 open 或重试。

## 级联数、分辨率和视图生产

`render_world` 在 `0x1400FB110` 把浮点位型 `0x44FA0000`（2000.0）放到调用点 `[rsp+0x28]`，即 Win64 的**第六实参**；在 `0x1400FB11F` 置 `r8d=3`、`0x1400FB128` 置 `r9w=0x400`，`0x1400FB12D` 直接调用 `setup_directional_light_cascades` VA `0x140CAD8C0`。第五实参 `[rsp+0x20]` 是 `[rbp+0x8E0]` 的地址，第七实参 `[rsp+0x30]` 是 `[rbp+0x860]` 的地址；被调函数保存寄存器并减栈后，分别从 `[rsp+0x260]`、`[rsp+0x268]`、`[rsp+0x270]` 读取，`0x140CAD8F1` 明确将中间的浮点数读入 `xmm6`。这个 2000.0 是该调用的深度上限输入；没有恢复游戏距离单位，也没有证明最终每层覆盖距离等于 2000。

`setup_directional_light_cascades` 的 `0x140CAD94A–951` 将级联数左移 10 位送入 `BufferDesc::new`，即为级联相关记录请求 `3×1024` 字节；`0x140CAD9B9` 另请求 32 B buffer。它在 `0x140CADADA–B3E` 将层数、图尺寸、光向和深度输入传给 compute binder，并登记一次 dispatch。`0x140CADB43` 只在层数非零时进入逐层 binding-set 循环，`0x140CADB7D` 每次将偏移增加 `0x400`，`0x140CADBA3/BAA` 给这一层指定偏移和 1024 B 跨度；这里的 **1024 B 是视图记录区段，不是深度图的一行像素**。返回记录中，`0x140CADCF8` 将级联数写入 `+0x28`，`0x140CADCFF` 将另一个 binding-set handle 写入 `+0x34`，`0x140CADD03` 才将原 `r9w=0x400` 写入 `+0x36`。三字段互不混同。这补上了[115](115-tiny-glade-steady-culling-and-submission.md)之前没有的级联资源生产边。

发行 shader `setup_shadows.precomp` 在 `0x1B4C–0x1B90` 按 invocation 索引检查 `cascade_count`；之后从 `depth_min_max_tex` 的 `0x1BC8` `OpImageFetch` 取最近/最远深度，结合当前视图投影与 `max_depth` 计算并写 `cascade_splits_buf`（`0x1F48`）及 `shadow_rendering_views`（`0x2FF0–0x32E8`）。这表明层间范围与视图从当前深度/相机几何推导，不是单凭 PDB 名字猜的固定三等分。所选公式包含深度变换、`Pow`、上下界和 8 个 frustum corner 的投影；这里未逐字段复原深度单位、非空深度条件与最终切分数值。`0x2918–0x2950` 读取 `shadow_map_dims` 后形成 `(dims+64)/dims`，用于随后 XY 范围扩张；对本调用的 1024，**该局部比例**为 `1.0625`，不是一个已测得的整幅阴影图空闲率。

所选 `setup_shadows` 模块没有 `OpFloor`、`OpRound` 或浮点转整数量化投影中心的指令；该有界检查**没有证明像素网格稳定投影**。视图随主深度和相机输入变化，其他 CPU/shader 阶段是否做抖动抑制仍 Unknown。图被命名为 temporal 或复用图像资源，也不能据此声称太阳阴影有静态缓存或相机静止时自动免重绘。

## 深度图、caster 筛选与层间复用边界

`shadow_pass` VA `0x140B00540` 从级联返回记录的 `+0x36` 读**同一边长**（`0x140B00837`），从 `+0x28` 读层数（`0x140B00A48`）。`0x140B008C8–8DD` 将这个 u16 边长零扩展后复制到两个 16 位半字（`ecx=(edge<<16)|edge`），作为纹理描述的宽高字段，因此此路径请求正方形尺寸；这并非在返回记录中分别读取 width/height。它在 `0x140B00865–8C2` 依次探测候选深度格式能力后，于 `0x140B00912` 请求图纹理资源。可确认的是图请求、格式条件和层迭代，未解完整纹理描述布局、实际物理格式/显存字节或重用策略。`0x140B00B77` 以级联列表长度为门，`0x140B00BA8–BC1` 迭代各项，`0x140B00D07–D10` 以循环索引取 `TexView::with_layer`，`0x140B00DAB` 为该层建立 raster；另一路 `0x140B00E08/ED9` 加入草地 splat/caster 相关节点。第 `i` 项的 raster closure 在[83](83-tiny-glade-slot23-write-growth-and-submission.md)已证只在 `i<3` 时取同一 `DrawLists` 首桶并以阶段 `i+2` 进入 `render_bucket`。因此存在**逐层提交候选**，但每层是否非空、实际 draw 和 GPU 时间未知。

`render_world` 在 `0x1400FB483–562` 对 0、1、2 三层分别 `TexView::with_layer` 并登记接收者相关 raster，接着 `0x1400FB585` 生成阴影 HZB；`0x1400FB5F3` 进入墙专用 `generate_wall_draw_lists_shadow`，`0x1400FB67E` 取得 `RenderSublist::iter_shadow`，`0x1400FB6A1` 向通用 `gpu_generate_draw_lists` 传第五参数 1；`0x1400FBAE3` 才调用上述 `shadow_pass`。这说明阴影有独立于主视图两轮的 HZB/列表与绘制路径。墙 shader 的三个段分别有四次 `OpImageFetch`，共 12 个静态读取点，并分别追加列表计数（`0x2BDE`、`0x364A`、`0x40D2`）；[49](49-tiny-glade-roof-gpu-visibility-and-depth.md)的屋瓦太阳模块同样按三层各四次读取。**每个候选至多进入所走层的这些分支**，不能把 12 乘以全部实体当作实际 fetch 数。

CPU `DrawLists` 一侧，[85](85-tiny-glade-wall-bucket-and-command-writes.md)已将 `DontCastShadow` 的可选 ECS 列接到首桶分类：缺少该组件的实体才有进入首桶的路径；墙循环组的初始 bundle 与此相容，但运行时组件变更未知。首桶是一份供逐层 raster 读取的 CPU 候选列表，不等于所有层共享一次最终可见性判断。墙与通用实例的 GPU 阴影视图检测仍按层执行；究竟是否跨层复用更深的空间筛选、多少 caster 同时落入多个级联、不同材质/草地的完整排除条件，仍未闭合。

## 工作量模型与自研 demo 选择

定义 `C=3`、`R=1024`，`A_w/A_n` 为进入墙/通用阴影 compute 的候选数，`V_i` 为第 `i` 层通过其视图测试并形成列表的实例数，`P_i` 为该层实际覆盖的深度像素，`D_i` 为 draw/批次条目。静态路径可概括为：

`W ≈ W_setup(depth/HZB, C) + W_list(A_w, A_n, C) + Σ(i=0..C−1)[W_raster(D_i, V_i, P_i) + W_other_i] + W_screen_shadow`。

这里 `W` 是待测工作项的结构式，**不是毫秒或一个可校准常数**。若每层图均为 `1024²`，三层名义深度像素容量是 `3×1024²=3,145,728`；实际格式、mip、attachment、清除/读取量及分配复用未知，不能换算为显存字节或帧带宽。墙/屋瓦各自的 12 个取样指令是最多三个分支、每层四个角的**指令位置数**，不是固定每帧调用次数。编辑的局部重建数也不能代替 `A_w/A_n`，静止画面仍可能构造这些视图与筛选节点。

**独立自研建议，非原作参数**：小规模建筑 demo 先把 caster 集按统一对象身份管理。近层保留墙、屋顶和有明显轮廓的道具；中层保留建筑主体及少量大树冠；远层只保留大体量建筑/地形，细砖、瓦和草叶只在近层投影。每层分别统计候选、通过数、draw、深度像素及 GPU 时长；移动镜头和静止镜头都测，只有捕获证明某一阶段贵时才引入更细的级联筛选或静态缓存。近/中/远边界、阴影图尺寸与质量要在自研产品的相机距离和可接受误差上测定，不能照搬本制品的 `3/1024/2000`。

## 结论边界与复现

**Answered（静态）**：本版的 3 层与 1024 边长实参、级联记录的分段资源请求、当前深度到 split/view 的 shader 生产、阴影图的逐层 raster 以及墙/通用独立阴影列表。**Partial**：纹理描述的完整字段和格式、每层真实列表/绘制数、跨层共享筛选及全部 caster 排除。**Unknown**：稳定投影的全链策略、静态阴影缓存、真实帧调度条件、GPU/CPU 时间、内存与 FPS。**Not Run**：游戏/Unity/GPU、目标进程附加、私人存档、Ghidra 重试与任何运行性能测量；没有读取或适配 `3DSandboxTest`。

复现时在相同 65,612,184 B EXE 和相邻 PDB 上，用 [PDB 查询器](digging-a-hole/tools/pdb_probe.py) 查询上述掩码，以本机 `dumpbin /DISASM:NOBYTES /SECTION:.text /RANGE:0x起点,0x终点` 读取 `0x1400FB0B0–0x1400FBAC0`、`0x140CAD8C0–0x140CADD24`、`0x140B00540–0x140B012DA`；用 [SPIR-V 读取器](tools/spirv_probe.py)和已缓存 Khronos grammar 解码上述两个 precomp，再运行本篇定点探针。原文 `render-world-shadow.txt` 的截取开头落在上一条指令中间，**从 `0x1400FB0BC` 起才按指令引用**。探针结果通过不代表语义验证、graph 执行或运行测量。
