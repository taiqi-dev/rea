# Tiny Glade：砖面着色、光照连接与景深准备

本篇回答一个有限的问题：程序化砖的可见颜色和法线怎样进入后续光照，以及画面柔焦怎样从深度生成。对象是本机 `C:\Software\Steam\steamapps\common\Tiny Glade` 的 Windows 发行版。EXE/PDB 与[本机身份记录](68-local-targets-and-three-game-comparison.md#tiny-glade-可以接着用哪些旧资料)一致；本篇新读取了以下实际包内文件，而没有运行游戏、附加进程或读取存档。此前砖的几何/实例生产见[39](39-tiny-glade-wall-and-timber-rendering.md)。

| 静态输入                                                                      | 本篇实际范围                                                     |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `compiled-shaders/country-core/compiled/wall/wall_brick_lod0.precomp`         | 4 个内嵌模块，重点 fragment 模块 1（文件偏移 33327，4639 words） |
| `compiled-shaders/country-core/compiled/deferred/solid_light_sun_sky.precomp` | 2 个模块，重点 fragment 模块 1（偏移 1243，20348 words）         |
| `compiled-shaders/country-core/compiled/dof/prepare.precomp`                  | compute 模块 0（偏移 94，2529 words）                            |
| `assets/colors.json`、`assets/tod/default.json`                               | 调色项及 15 个时间关键帧的配置读取                               |

这些 SPIR-V 由仓库的 `tools/spirv_probe.py` 按 Khronos grammar 结构解码；本机可选逐指令账本在 `.cache/procedural-modeling/followup-art-updates/tiny-{brick,solid-light,dof}.json/.txt`。引用中的 `w` 是**所在模块的 word offset**；路径和模块偏移共同定位指令。解码确认字数和语法结构，未用 `spirv-val` 证明语义合法，也没有 GPU 抓帧。

## 1. 砖片元把颜色与法线写为紧凑的 G-buffer

**观察。** 砖 vertex 模块包含实例数据 `InstancedWallData`、`Vertex_Normal`、`is_bevel` 和 `color_id`。其空间变形已在[39](39-tiny-glade-wall-and-timber-rendering.md#2-普通砖cpu-保存布局和四角变形gpu-继续加工)解释。所选 fragment 模块先按 `color_id` 选择颜色路径：`w2279–2450` 读取 `color_library.data` 的 `wall_1`、`wall_2` 等成员；`w2767–2996` 的若干分支从 `wall_color_data.brick_colors` 采样不同第三坐标；另有 `w3387–3465` 从 `roof_colors.tex` 采样并乘 `0.7` 的分支。实例 seed 还经整数混合构成 `[0,1)` 采样量（`w3103–3176`、`w3266–3339`）。这说明同一几何可以由材质 ID、纹理和实例种子产生不同颜色。具体哪个 `color_id` 对应哪种玩家所见的砖、颜色资源如何上传到各 shader binding，本篇没有证实。

**观察。** 片元结尾将法线 `%666` 乘 `0.5` 再加 `0.5`，逐通道 clamp 到 `[0,1]`，以 `round(255x)` 量化到 8 位（`w3476`、`w4361–4472`）。第一 32 位值是三个量化通道加 `0xCC000000`。颜色 `%2026` 经过 clamp 及同样的量化（`w4477–4592`），第二 32 位值低 24 位放 RGB，高 8 位组合常数 `7`、条件位和 `128`（`w4597–4628`）；`w4634` 将这两个 uint 组成的值写入 `gbuffer` 输出。这里的“颜色”是当前片元分支合流值，不等同于 `colors.json` 中某个原始 RGB。

**观察。** `solid_light_sun_sky` fragment 从 `gbuffer_tex` 进行 `OpImageFetch`（`w4166–4170`），把第一个 uint 的 0、8、16、24 位字节各除以 255（`w4189–4265`），并将前三个归一化通道做 `2x-1` 后 normalize（`w4336–4354`）。它同样从第二个 uint 的低三字节取出 RGB（`w4272–4336`），高字节继续按位拆出控制位（`w4373–4473`）。这些指令与砖片元的两个 uint 格式直接相容，是“砖片元输出 → deferred 光照输入”的**数据格式连接**。尚未核对 CPU render graph 的 attachment 实际绑定和 pass 顺序，所以不能把格式相容提升为每个运行帧都经过此确切 pass 的观察。

该光照片元还从 `depth_tex` 读取深度（`w4175–4184`），声明并读取 `FrameConstants` 中太阳色、天空色、雾、方向等字段，另有 `screen_shadows_tex`（`w6457–6466`）、间接辐射、光网格和灯笼数据的路径。最终颜色在 `w20338–20343` 写出；`w20259–20331` 的控制位分支可以选择不同合流颜色。因此，不能把整段 20348-word shader 简化成“漫反射 RGB×太阳色”的一个公式。本篇只证实上述输入格式和选定消费，不声称恢复完整 GI、阴影、曝光或最终屏幕色。

**构造演算 1（指令公式，不是游戏采样）。** 给 fragment 末端一个已经合流的单位法线 `(0,0,1)` 和颜色 `(0.2,0.4,0.6)`。法线映射成 `(0.5,0.5,1)`，量化成 `(128,128,255)`，第一字为 `0xCCFF8080`；RGB 量化成 `(51,102,153)`，第二字低 24 位为 `0x00996633`，高字节再由该片元的控制条件填写。光照端反读得法线前三通道 `(128/255,128/255,1)`，经 `2x-1` 与 normalize 后接近 `(0.00392,0.00392,0.99998)`；颜色反读为 `(0.2,0.4,0.6)`。这个算例证明打包/解包的量化误差与方向关系，不证明这些输入来自真实砖或输出最终色。

## 2. 配置中的色彩与时间关键帧

**观察。** `assets/colors.json` 含 `wall_1=(0.59,0.46515602,0.31859997)`、`wall_2=(0.49,0.37240008,0.196)` 和 `indirect_light_tint=(1,0.79600006,0.49)` 等具名项；砖 fragment 的 `ColorLibraryData` 成员有对应 `wall_1`、`wall_2`。这是名称及数据结构呼应，**配置文件 → GPU uniform 的加载/变换链尚未确认**，不能直接把配置数值代进前述像素演算。

**观察。** `assets/tod/default.json` 有 15 个 `time_of_day` 关键帧，分别保存 `sun_tint_color`、天空上下色、`base_fog_thickness`、地面雾与 `fog_tint` 等。例：`t=0.043` 的太阳色 `(0.5872374,0.50836915,0.3395426)`、base fog `0.01`；`t=0.513` 的太阳色 `(0,0,0)`、base fog `0.09`。`solid_light_sun_sky` 的 `FrameConstants` 确有 `sun_color`、`sky_low_color`、`sky_high_color`、`fog_tint_thickness` 字段。PDB 符号 `SunSkyColors::lerp` RVA `0xBB22F0` 是插值入口线索，但本篇未恢复其函数体及 `tod` 关键帧到逐帧常量的调用链；也不能假定关键帧之间必为线性 RGB 插值。配置值是原始资源，不是测得的实际帧光照。

## 3. 景深 prepare：深度、焦点和分辨率进入模糊半径

**观察。** `dof/prepare.precomp` 是 `8×8×1` compute（`w20–32`），每线程按像素坐标从 `depth_tex` 取深度（`w1883–1908`），经 `sample_to_view`、`view_to_world` 矩阵构造世界位置（`w1956–2009`）。从 `DofAutofocus` 当前 camera 索引读取 `focus0`、`focus1`、`use_tilt_shift`、`focus_scale`（`w2014–2063`）。所选路径将两个焦点值取倒数，再以 `0.001` 下限及 `±0.00001` 修正形成两个阈值（`w2067–2110`）。`use_tilt_shift` 控制投影距离计算分支（`w2115–2378`），所以焦点并非一个无条件的单标量距离。

后续以 `r = 1/max(1e-10, projected_distance)` 同两个阈值比较，分三段计算带符号响应（`w2204–2333`）；窄的过渡项至少为 `0.01`（`w2216–2226`）。结果还乘 `focus_scale`、视图投影矩阵的 `[1][1]` 值和 `depth_tex_dims.y/720`（`w2385–2418`）。这里 `depth_tex_dims.y/720` 是确切的**垂直分辨率缩放**，并不证明整条画质或帧成本在各分辨率上线性变化。

每线程把绝对模糊半径限制为不超过 `depth_tex_dims.y/24`，再在 8×8 workgroup 内做原子 min/max；第一个线程把该 tile 的 min/max 写入 `tile_output_tex`（`w2423–2504`）。各线程也把自身带符号半径写进 `coc_out_tex`（`w2512–2523`）。写入前的 `abs` 只用于 tile 范围，像素 CoC 保留正负号。两张输出纹理的后续 gather/composite、tile 跳过规则和实际总成本未在本模块确认。

**构造演算 2（中间值已给定）。** 设 `depth_tex_dims.y=1440`，则分辨率系数 `1440/720=2`、绝对半径上限 `1440/24=60`。设某片元经焦点分段所得带符号响应为 `-0.06`，`focus_scale=1`，投影矩阵 `[1][1]=2`；写入的 CoC 为 `-0.06×1×2×2=-0.24`。tile 聚合用 `min(60,abs(-0.24))=0.24`，而 `coc_out_tex` 仍写 `-0.24`。同 tile 其它 63 个线程决定最终 min/max；不能由这一像素推出完整 tile 或实际模糊画面。

## 独立设计的可用分工与边界

对自研画面，可独立设计“构件的材质/法线 → 明确格式的 G-buffer → 由时间和天气状态生成的光照常量 → 独立的景深准备与合成”。砖颜色与 bevel 细节的资源契约、GBUFFER 格式和每个后期 pass 应由自己的产品要求与性能目标制定；上文的常数、配置色和恢复的指令不是可移植的生产代码或素材。

**已回答：** 选定砖片元与 solid-light shader 的两字格式相容；选定景深 prepare 的深度/焦点输入、半径缩放和 8×8 tile 输出。**部分回答：** 色彩配置与 shader 同名字段、时间关键帧同逐帧光照字段的联系；CPU 上传链、实际绑定和插值公式未知。**未回答：** 运行时画面、全局光照/阴影/接触暗部完整算法、DoF 合成质量与帧时间。静态指令不能测得 GPU 成本，也不能替代玩家视角截图和 GPU 抓帧。
