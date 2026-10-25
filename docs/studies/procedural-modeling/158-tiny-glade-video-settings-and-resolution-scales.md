# Tiny Glade：画质面板、TGSR 档位与独立画质设计

2026-10-24，America/Los_Angeles。静态入口为 `ui_settings_video`（preferred VA `0x140370890`，12,121 B）；身份、reference-4 的版本限制和工具失败记录沿 [155](155-tiny-glade-menu-snapshot-and-hover-visibility.md)。本篇不读取玩家配置，不把截图中选中的值当默认值，也不测量 FPS。

## 超采样档位与图像质量是两个枚举

`UpscalingPreset::tgsr_resolution_scale`（`0x140A92210`）按输入字节读取 `0x1430456B0` 的 float 表；`UpscalingPreset::fmt`（`0x140A94560`）的实际跳表和带长度本地化键提供对应关系。五个已核记录如下：

| tag | 原始本地化键             | TGSR 内部线性比例 s | s²，仅像素数量演算 |
| --- | ------------------------ | ------------------- | ------------------ |
| 0   | Quality.UltraPerformance | 0.33333334          | 约 11.11%          |
| 1   | Quality.Performance      | 0.5                 | 25%                |
| 2   | Quality.Balanced         | 0.58139533          | 约 33.80%          |
| 3   | Quality.Quality          | 0.66666669          | 约 44.44%          |
| 4   | Quality.UltraQuality     | 0.76923078          | 约 59.17%          |

线性比例读取和显示名并非从常见 FSR/DLSS 档位猜出。`s²` 是两个维度都按 s 缩放时的理想像素数比例，**不是总 GPU 耗时、加速比或实际尺寸取整结果**。低分辨率几何/后处理、阴影、升频自身和 UI 的成本还需分别计算；这里没有证明 TGSR 的全部质量算法。

另一方面，`ImageQualityPreset::fmt`（`0x140A946D0`）对应：tag 0 Performance、1 Balanced、2 Quality、3 UltraQuality、4 Custom。这是另一张显示表，不能拿图像预设 tag 去索引超采样比例。截图的“关闭超采样”也不能命名为第五档：五个所选 UpscalingPreset 记录都有自己的比例，启用/关闭是另外需要追踪的选择。

复核器 [menu_environment_probe.py](tiny-glade/tools/menu_environment_probe.py) 校验本构建的指令形状、实际跳表、带长度字符串及尺度读取。它只读文件，不执行游戏或计算摘要；不适配的指令直接报错，不从附近字符串猜字段。

## 面板中确认的能力与仍未接通的部分

| 项目                | 证据与边界                                                                                                                            |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 超采样和档位        | native 实际引用 `Menu.Settings.Video.Upscaling` / `UpscalingPreset`；尺度映射见上表。完整启用与支持性分支未恢复                       |
| 亮度、Gamma、锐化   | `0x140371BCD/0x140371C65/0x140371CFD` 取各自本地化键，调用 float tweaker；存在实际状态绑定。最终色彩变换公式与单位未确认              |
| 分辨率/VSync/三缓冲 | 同一视频设置入口有实际控件路径；窗口模式、支持集合和逐项热应用行为尚不完整                                                            |
| 景深、渲染比例      | reference-4 显示用户提供的设置状态，是视觉需求线索；不能单凭该图报告默认值、内部缓冲尺寸或完整 GPU pass                               |
| 应用/重建           | `LastAppliedVideoSettings::needs_apply`（`0x140373E30`）比较旧/新配置，形成多种变化位；不能说所有选项都同成本、每帧重建或统一需要重启 |
| 设备切换            | 原入口引用 `RestartToChangeDevice`；该提示不能扩张为任何画质滑条都必须重启                                                            |

本轮特意排除两个误入口：`RenderConfig::impl$9::from`（`0x140A93B10`）所选函数实际格式化设备/driver UUID，不是图像预设转换；settings 的某个闭包实际是页签选择，也不能拿它补全 preset→低层选项表。

因此“每档阴影分辨率、阴影距离、植被量、反射、景深预算”的完整矩阵仍为 **Unknown**。不要从枚举名、同址泛型别名或邻近常量构造看似完整的原作表。

## 我方 QL01 可用的规格

先列自己的正式渲染器真正支持的项目、消费者和默认值，再设计界面：

1. 区分输出分辨率、内部 render scale、升频模式和锐化；升频关闭不能只是换了显示标签。检查文字/HUD 是否保持目标输出分辨率。
2. 画质预设是一组能力配置；手动改其中一项转为 Custom。亮度/Gamma/锐化属于显示调节，不承担偷偷降低阴影或实例预算的职责。
3. 把能热应用、需资源重建、需设备/程序重启的项明确区分；比较变化后只重建受影响资源，保持取消/恢复明确。
4. UI 只能承诺真实支持的选项和范围。降内部分辨率不等于 CPU 编辑/地形重建会变快；静止低 FPS 仍需项目实际采样定位。

用户要求“按硬件给推荐画质/可编辑范围”是我方新增设计。本轮没有证明原作采用某套硬件评分或基准测试。按协调范围可先做本地能力查询和保守、用户确认后应用的建议，不采集设备标识、不上传、不自行跑 benchmark。可编辑范围是世界/保存契约，不能由画质预设偷偷裁切存档，见 [157](157-tiny-glade-edit-bounds-camera-and-distant-horizon.md)。

## 记录与验收

ignored `tiny-menu-environment/` 中保留 `video-settings.asm.txt`、`video-needs-apply.asm.txt`、`upscaling-scale.asm.txt`、`upscale-display.asm.txt`、`quality-display.asm.txt`、`pdb-quality-enums.json`、`menu-environment-proof-v2.json`。

原作：文件读表和所选指令为静态证据；默认/当前用户值、整档画面与帧时均未验证。我方：后续 owner 必须按自己的真实 writer 和消费者实现，不能把这里的比例复制成“已证明适合 URP 的最优配置”。游戏、Unity、画面和性能验证均 **Not Run**。
