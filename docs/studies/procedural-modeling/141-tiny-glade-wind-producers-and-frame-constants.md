# Tiny Glade：风参数写入、天气资源与帧常量

2026-10-22，Pacific Time。续接 [138：植物顶点风](138-tiny-glade-vegetation-wind-shader.md)。目标仍是已匹配的 Tiny Glade Windows EXE/PDB、随包配置和 shader。没有运行游戏、读取私人存档或检查用户 Unity 工程。

**树冠消费的 `wind_strength` 有 CPU 来源：随主题加载的设置 → `Weather` → 帧常量准备 → shader 字段。这条已核风链由共享帧参数驱动，摆动在 shader 中计算。** 以下区分首次装载的基线、帧内复制和 shader 局部覆盖；并未枚举全部编辑器/历史恢复写端。

## 设置到 Weather 的装载链

`GladeSettings::load`（preferred VA `0x140C5D220`）将设置路径交给 `tg_mods::overlay::read_to_string`，随后调用 serde JSON 解析。选定的字段 visitor `0x141C6F698–6BE` 实际比较 `wind_strength` 的 13 字节内容并返回字段号 **7**，不是只搜到一个字符串。

`deserialize_struct<...GladeSettings...Visitor>` 在 `0x14167BCC7` 调 visitor，再经表 `0x14332458C` 分派；表的第 7 项指向 `0x14167BF5D`。该分支检查重复字段，转到 `0x14167C26F` 读取浮点值，成功后在 `0x14167C293` 放入 `xmm6`。省略字段的另一分支在 `0x14167C472` 取 1.0。结果打包与外层 `GladeSettings::load` 的移动链将其置于所选设置对象的 `+0x10`；装载失败/默认构造路径 `0x140C5D3EB` 也向该偏移写 1.0。本轮没有把读取失败等同于任意文件都可以安全忽略，其他错误路径不在这里概括。

`load_glade_tod_and_weather` 的 `0x1408F9D10–1C` 读取设置对象 `+0x10`，写入当前 `Weather+0x0C`。随包 `assets/glade/olden/settings.json` 明确给出 `wind_strength:0.2`；这是原作配置实例，不是本机已经运行到的值，也不能排除 overlay、存档恢复或 UI 后续覆盖。

## Weather 到 shader 不是靠偏移猜字段

| 环节        | 实际证据                                                                                                                                                                    |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 资源类型    | `0x14060313D` 的真实 E8 目标为 `prepare_frame_constants`（`0x1409252D0`）；包含此 call 的 PDB 专门化参数第二 tuple 第一项是 `Res<Weather>`，第二项才是 `Res<GladeSettings>` |
| 取资源指针  | `0x1409253F6–3F9` 从该 tuple 的第一资源引用取指针，留在栈 `rbp+0x1110`                                                                                                      |
| 取风值      | `0x140925D8B–97` 取这个资源的 `+0x0C`，经 `xmm1` 留到 `rbp+0x1138`                                                                                                          |
| 写帧常量    | `0x1409263BA–3C2` 从同一栈槽回读，写入目标 `+0x134`，即十进制 **308**                                                                                                       |
| shader 布局 | 树冠模块 `FrameConstants_natural` 的成员 38 名为 `wind_strength`，`OpMemberDecorate Offset` 明确为 **308**；`w3448–3453` 实际读取它                                         |

这避免把两个相邻 `Res` 的字段合并解释。DbgHelp 本轮没有返回这两个精确类型的子字段枚举，故字段意义以真实参数列表、复制路径和 SPIR-V 布局相互对应，而非捏造 PDB struct layout。

另有选定 `GraphApi::push_instant_binding_set<FrameConstants,...>`（`0x1405DA380`）在 `0x1405DA4E8–4F1` 复制 **0x160=352 B**，`0x1405DA51C` 进入 `FrameConstants::bind`，`0x1405DA5BA` 进入 `DynamicConstants::allocate`。其两个已核 caller 位于主图和加载图的 compile 专门化中。这里证明存在有类型的图常量绑定/分配路径；本轮没有逐跳证明每个 render 分支的资源槽都选中此次准备对象，或它已在某帧被 GPU 消费。

## 风强度到底控制什么

138 已恢复树冠两个层次，不能把“风强度为零”直接等同于整个世界静止：

- 大范围位置扰动使用 `game_time_sec`、`game_time_frac` 和位置分量的低频正弦组合；选定这段没有读取 `wind_strength`。
- 叶片/卡片旋转微动使用强度乘时间频率。主题号为 4 时，树冠局部把 `W` 选成 0.4，否则用帧字段；这个覆盖发生在 shader，不是把 `Weather` 改写成 0.4。
- 芦苇、灌木的选定入口读取游戏时钟，草的选定入口读取启动时钟并有 `wind_wave_scale`；不能宣称所有植物共用同一强度、速度与暂停规则。

**构造演算。** 假设 olden 设置的 0.2 未被覆盖、且主题号不为 4，那么这条装载/准备路径把 0.2 复制到帧偏移 308。树冠微动的两项时间系数约为 `3.529416*0.2=0.7058832`、`1.538462*0.2=0.3076924`；主题号 4 的局部覆盖则得到约 1.4117664 和 0.6153848。这里只演算选定频率项，不能据此说振幅同比翻倍或所有枝叶都有相同速度。

`weather_system`（`0x140B56280`）的所选主体写的是 `Weather+0x10` 等状态，而非上述风字段 `+0x0C`。不能看见天气系统里有正弦就把它当风强度生产者。此系统的主题门和渐变含义不扩展成已还原的完整天气模拟。

## URP 的独立规格

建议由一个环境参数所有者发布当前/上一帧的视觉时间、风向、速度、强度及阵风值，植物实例只携带稳定 seed、柔度和锚定权重。根部权重由自己的顶点色/网格数据明确提供；不要把原作未命名坐标的 `p.y` 直接当成自己的根部遮罩。

为叶片、灌木、草约定“振幅”和“频率”两个不同参数，暂停/读档/天气切换时如何连续推进也写进规格。主颜色、深度、阴影与必要的运动向量 pass 使用同一变形函数及对应时刻，实例 culling bounds 包含最大位移。这样 GPU 微动不要求每帧重建 mesh、碰撞或写存档。具体 URP 接口与分步范围见 [143](143-unity-urp-cozy-style-independent-rendering-plan.md)。

## 证据与未决项

正式回读工具 [lighting_wind_water_probe.py](tiny-glade/tools/lighting_wind_water_probe.py) 核对 8 处 native 锚点中的参数复制/字段识别部分、字段 308、字段分派表和有界调用；原始 PDB JSON、完整选定函数反汇编在 ignored `.cache/procedural-modeling/tiny-light-wind-water/`。这些不是 REA native 成功回执。

已回答：设置基线和默认值、首次加载到 Weather、帧字段写入、树冠读取与主题局部覆盖。部分回答：有类型的绑定/分配路径。未回答：风字段所有 UI/快照写端、每种植物全部变体、实际上传槽同一性和运行中的暂停/天气衔接。运行、画面和性能验收全部 **Not Run**。
