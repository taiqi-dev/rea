# Tiny Glade：渲染框架、shader 语言与光影实现

2026-10-22，Pacific Time。本篇回答“是否 Unity URP、为什么光影看起来柔和”，植物与水面分别见 [138](138-tiny-glade-vegetation-wind-shader.md)、[139](139-tiny-glade-water-shader-and-demo-budget.md)。同时完成的菜单/发布续查见 [135](135-tiny-glade-menu-tool-exit-and-timber-cleanup.md)、[136](136-tiny-glade-entity-upload-and-frame-publication.md)。没有运行游戏或读取用户工程。

**本机这份 Windows 发行版走 Rust、`rhapsody` 和 Vulkan/SPIR-V 的专用渲染路径，不是 Unity URP。选定 shader 模块还明确声明源语言 Slang。** Bevy 在这里提供 ECS/调度能力，不能由依赖 `bevy_ecs` 推断它使用 Bevy 的整套 renderer。

## 不是只靠文件名判断引擎

| 证据                                     | 可确认的事实                                                                                                   | 不应额外推断                                                                                                  |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 随包 `build-info/Cargo.lock`，626–629 行 | `bevy_ecs 0.17.3`                                                                                              | 不等于 Bevy renderer，更不是 Unity                                                                            |
| 同文件 6342–6344 行                      | `rhapsody 0.1.0`，来源固定为 PounceLight 的 `rhapsody2` 提交 `5b499c1333d2fd04c30578bca5273e124093685a`        | 未下载该源码，不宣称知道框架全部内部实现                                                                      |
| 同文件 267–269 行                        | `ash 0.38.0+1.3.281` 依赖                                                                                      | 版本串不是本机运行时协商出的 Vulkan 版本                                                                      |
| EXE/PDB 的实际调用                       | 主循环进 `tiny_glade::render_loop::render`，再经 `rhapsody::rg::executor::GraphExecutor` 执行/呈现图，见 136   | 没有用源文件标签代替真实调用                                                                                  |
| `.precomp` 内嵌模块                      | 本轮读取的 9 个选定模块均为 `OpSource [11,1]`；留存 Khronos core grammar 将 SourceLanguage 11 定义为 **Slang** | `1` 是这个源声明的版本字段，不能据此称为 Slang 编译器 1.0；`GLSL.std.450` 数学指令集也不表示源码一定写成 GLSL |

SPIR-V 是编译后表示，`.precomp` 还有容器内容与多变体。本研究解释选定入口及数据流，不把二进制反向翻译成可销售的生产 shader。

## 光影是多个层次协作的结果

| 画面层次       | 本机已有静态证据                                                                         | 对 demo 的影响                                           |
| -------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 砖面与倒角     | 程序化布局、顶点变形、法线与材质 ID，见 [39](39-tiny-glade-wall-and-timber-rendering.md) | 轮廓、倒角和法线先决定受光效果；只换后期无法补回几何轮廓 |
| 基色与变化     | 砖片元按颜色 ID、调色资源、纹理与实例 seed 取色                                          | 同一共享材质可让许多实例有细小变化，不必每块砖一个材质   |
| 统一光照       | 紧凑 G-buffer → `deferred/solid_light_sun_sky`，消费太阳、天空、雾和屏幕阴影等输入       | 风格化调色与整体光照需要统一，不能各物件随意叠亮度       |
| 遮挡与太阳阴影 | 独立级联、caster 列表、GPU 可见性筛选，见 119                                            | 阴影预算与主画面可见性分开管理                           |
| 柔焦与空间层次 | `dof/prepare` 从深度、焦点与分辨率准备模糊量，见 69                                      | 是景深准备证据，不是证明所有柔和效果都来自景深           |

### 基色/法线怎样接到光照

[69](69-tiny-glade-shading-lighting-and-contact.md) 的具体格式已用本轮重新解码的文件对齐：`wall/wall_brick_lod0.precomp` 片元模块 1 位于容器字节 33327，4639 words；`solid_light_sun_sky.precomp` 片元模块 1 位于字节 1243，20348 words。

砖片元先生成颜色和法线，再将法线映射到 `[0,1]`、逐通道量化到 8 位，与 RGB/控制位打包为两个 uint。光照片元从 `gbuffer_tex` 读回，解包 RGB、恢复并归一化法线，另读深度、太阳/天空颜色和 `screen_shadows_tex` 等输入。这里不是简单把整栋模型涂一个“卡通材质”，也不能缩成唯一的 `baseColor×sunColor` 公式。

构造例，沿已有指令解释：法线 `(0,0,1)` 映射、量化后得到 `(128,128,255)`；解包会接近原方向但有 8 位量化误差。颜色 `(0.2,0.4,0.6)` 对应低三通道 `(51,102,153)`，实际像素还要走光照与后续合成。这是格式演算，不是游戏截图采样。

`assets/colors.json` 和 `assets/tod/default.json` 分别有材质/间接光调色项和 15 个时间关键帧；光照片元存在太阳、天空、雾字段。配置到每个当前 uniform 的全部加载和变换仍未在本轮闭合，因此不能把配置中的 RGB 当作最终屏幕色，也没有恢复完整 GI 解法。

### 太阳阴影有明确成本边界

[119](119-tiny-glade-shadow-cascades-and-work-budgets.md) 已核选定 CPU 调用请求 **3 层、边长 1024** 的太阳级联；图像候选规模为 `3×1024²=3,145,728` 个深度 texel，不是测得显存字节。各层还要经过 caster、HZB、draw-list 和 raster 路径。

这能解释它怎样限制阴影工作，但不能据此宣称阴影使用某种 PCF/PCSS 核、全局静态缓存，或当前 GPU 正好渲染了三张满图。本轮也没有证明其所有细小接触阴影、间接光与历史滤波算法。`screen_shadows_tex` 的实际消费与“完整 SSAO/GI 已还原”之间仍有距离。

## 给综合 demo 的路线

**建议保留现有 Unity/URP 技术选择，先实现一致的光照、美术规则与少量定制效果。** 这是独立建议，没有检查你的项目，也不声称它已经使用某个 URP 版本。

Unity 6.0 的官方资料明确提供 Lit Graph 的顶点 Position/Normal 输入，以及通过 Renderer Feature 插入或改写部分绘制处理的入口。因此顶点风、风格化材质和少量屏幕效果不要求先重造整套 Vulkan renderer。[URP Lit Graph](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/prebuilt-shader-graphs-urp-lit.html)、[Renderer Feature](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/urp-renderer-feature.html)。具体接口需实施时匹配项目版本。

优先顺序是：统一太阳/天空与调色 → 正确几何法线与小倒角 → 共用材质的实例变化 → 有预算的阴影 → 植物顶点风与基础水面。景深、复杂屏幕反射和自定义 G-buffer 放后面；它们可能增加全屏带宽或重复绘制，当前没有证据能解决你的约 10 FPS。既有低帧率需要另做获准的项目采样，不能从参考游戏的 shader 数量推出原因。

## 本轮证据与边界

目标仍为 `C:/Software/Steam/steamapps/common/Tiny Glade` 的已匹配 EXE/PDB、随包 Cargo.lock、`compiled-shaders/country-core/compiled/`。原始新输出在 `.cache/procedural-modeling/tiny-shader-followup/`；8 个选定 `.precomp` 共 **27 个模块、26,188 条结构指令**解析成功，未见被拒候选。长期复核工具 [shader_effects_probe.py](tiny-glade/tools/shader_effects_probe.py) 另检查其中 9 个关键模块、6 处实际字段读取、7 处树冠正弦，以及水面高度/涟漪上限/LUT 样本数。

这些是普通文件证据，不是 REA native 成功 Evidence、`spirv-val` 合法性结果、完整反编译源码或 GPU 抓帧。没有新算摘要，没有启动目标。全部视觉、真实帧时和项目适配验证 **Not Run**。
