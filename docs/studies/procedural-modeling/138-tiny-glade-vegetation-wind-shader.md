# Tiny Glade：树冠、草与水生植物的 shader 摆动

> 后续 [141](141-tiny-glade-wind-producers-and-frame-constants.md) 接通设置基线、Weather 到帧字段 308 的写入；[143](143-unity-urp-cozy-style-independent-rendering-plan.md) 另写 URP 统一变形与前后帧参数要求。下文保留此前的 shader 局部证据。

2026-10-22，Pacific Time。框架和光照见 [137](137-tiny-glade-renderer-language-lighting-and-demo-route.md)。以下来自新读取的 shader 指令；原作实现与独立 demo 建议分别说明。

**树冠的所选顶点入口已经接通“时间/风参数 → 正弦 → 位置与叶片局部旋转”，不是只发现了一个叫 wind 的字段。** 草、芦苇和灌木走不同入口；不能把它们、常春藤增长动画和落叶粒子合成一个统一风公式。

## 本轮输入与坐标

文件根为 `compiled-shaders/country-core/compiled/`。下面 `w` 均指**该模块内部的 word offset**，换算容器文件字节为 `module_offset + 4×w`，与旧研究使用的原文件十六进制偏移区分。

| 文件 / 模块0                   | 文件字节起点 / words | 已确认实际读取                                                                       |
| ------------------------------ | -------------------- | ------------------------------------------------------------------------------------ |
| `clearing/tree_canopy.precomp` | 159 / 5605           | `game_time_sec`、`game_time_frac`、`wind_strength`，还检查 `glade_theme_id`          |
| `reed.precomp`                 | 127 / 5104           | 游戏时间两部分，多处时间处理与正弦/余弦                                              |
| `nani_bush.precomp`            | 137 / 3694           | 游戏时间两部分及后续时间相关顶点计算                                                 |
| `grass2/lod0.precomp`          | 141 / 6689           | `time_since_startup_secs`；另有带 `wind_wave_scale` 的实例结构，完整参数生产链未追完 |

树冠 `w2576/2599/3448`、芦苇 `w2529/2542`、灌木 `w2232/2245`、草 `w4438` 的 AccessChain 和后续 Load 都实际存在。共享 FrameConstants 声明同一字段，并不证明每个 shader 都读取它。尤其不能把所有植物都说成读取 wind_strength；本轮所选草入口的直接时间输入是 startup time，暂停时实际怎样推进仍需追 CPU 时钟，当前不作保证。

## 树冠：整体位置摆动与局部叶片旋转分开

树冠模块0在 `w2493` 先得到一个混合后的三维位置中间量 `p`；其完整坐标系尚未命名，下面不把 `p.y` 当作地形以上的实际高度。令整数秒转成浮点后的值为 `S`，分数秒为 `F`，定义本段实际反复使用的时间相位：

```text
D(a) = rem(S*a, 2π) + F*a
A = 0.03*p.y
x1 = p.x + A*sin(D(0.823529)+0.2*p.x)*sin(D(0.893617)+0.2*p.z)
z1 = p.z + A*sin(D(0.792453)+0.2*x1)*sin(D(0.688525)+0.2*p.z)
```

证据为 `w2566–2783`：四次时间频率处理、Sin、两路乘积以及位置分量写回。小数按便于阅读的精度展示；这是**本段位置运算的重组解释**，不是完整树冠顶点 shader，也不是供直接移植的生产代码。它说明摆动可以由空间位置、时间和高度相关量共同变化，不需要 CPU 每帧重建整树网格。未由此证明原作所有树根严格不动。

更后面还有叶片展开/局部旋转链。`w3448–3471` 读取 `wind_strength`，所选 `glade_theme_id==4` 分支将该输入替换为 0.4；没有把 theme 4 命名为某季节。`w3503–3580` 用两路含风参数的时间相位求正弦乘积，得到小角度；`w3585–3623` 由 sin/cos 建二维旋转，随后经方向矩阵和 `billboard_expansion_scale` 加回位置（`w3655–3681`），继续进入后续顶点处理。

所以整体位置摆动与叶片局部旋转是不同层次；所选 wind_strength 不应被当作前面全部位移的唯一幅度。该模块还读 `bend_vector` 等实例字段，后续弯曲、朝向、可见/出现控制与最终投影并未在本篇全部化简。

`GLSL.std.450` 的扩展号 13/14 分别为 Sin/Cos，本地模块导入名及编号都已核对；这是数学指令集名称，不是原始 shader 语言。[Khronos GLSL.std.450 grammar，version100/revision2](https://raw.githubusercontent.com/KhronosGroup/SPIRV-Headers/main/include/spirv/unified1/extinst.glsl.std.450.grammar.json)。

## 为什么看起来不像所有树一起机械摇摆

已证的机制是多频率乘积、位置相关相位、两个方向的非相同频率，以及局部旋转叠加；这些机制能产生不同步的视觉变化。它们与每棵树的 seed、形状、叶片展开、朝向和材质一起影响画面。具体玩家看到的每种树/草是否选到此变体、阴影变体是否使用完全相同的形变、是否存在额外 LOD 简化仍 **Unknown**。

[23](23-tiny-glade-ivy-leaves-and-rendering.md) 的常春藤结论继续保留：已证明的叶片增长不能改名为风。该轮所选 ivy blob 没读 time/wind，不排除别的植物有风；本轮树冠的新证据正好说明应按物种与变体分别研究。

## 综合 demo 的独立做法

建议先做两层、参数少而一致的顶点风：整株缓慢弯曲，加少量叶片/草尖微动。自己的顶点权重固定根部，以实例稳定相位避免整片植物同步；时间和风向统一供给，外观实例化数据与正式树木状态分开。

构造例，**下面参数为独立设计**：对归一化高度 `h∈[0,1]`，令 `weight=h²`，最大位移 0.03 米。根 `h=0` 的位移上限为 0，半高 `h=0.5` 为 0.0075 米，顶端为 0.03 米。两个实例使用不同稳定相位；不因此改变碰撞、建造占用或存档几何。

具体实施应同时覆盖主颜色、阴影、深度和需要的运动矢量 pass，采用同一形变定义；否则会出现叶子动而影子不动、深度轮廓错位或拖影。这是自研一致性要求，未证明原作所有变体已经满足。

性能重点是共用网格/材质、批量实例数据、有上限的可见数量和阴影距离。shader 风减少 CPU 变形工作，但仍会消耗每顶点、每个相关 pass 的 GPU 成本；透明/裁剪叶片的覆盖、重复阴影和远处叶片数量也要管。不要为每片叶子加 Update、Animator 或独立材质，也不必为微风每帧重烘焙网格与碰撞。

## 复核和剩余问题

正式入口 [shader_effects_probe.py](tiny-glade/tools/shader_effects_probe.py) 检查实际字段所有者、成员名、Load、树冠正弦和选定位置运算；完整解码留在 `.cache/procedural-modeling/tiny-shader-followup/`。四份植物文件共 16 个模块、11,516 条结构指令，本轮解析通过；不是 shader 合法性或 GPU 性能验收。仍缺 CPU 风参数写端、全部物种与变体选择、最终像素对齐与实机风感。运行、画面与性能均 **Not Run**。
