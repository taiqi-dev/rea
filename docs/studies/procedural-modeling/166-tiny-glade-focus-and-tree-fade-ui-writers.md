# Tiny Glade：焦点与树木渐隐的 UI 写端

2026-10-25，America/Los_Angeles。续 [163：焦点参数来源](163-tiny-glade-autofocus-parameter-producers.md)与 [164：树木设置和帧常量](164-tiny-glade-tree-settings-and-cone-producers.md)。本轮接上拍照工具栏到状态写入，未运行游戏或读取玩家配置。

## 结论与证据范围

**焦点框显示、固定焦点、树木渐隐是三个不同的按钮及写入动作。** 树木按钮并非只改当前 profile，而是逐个翻转两个非默认 profile；焦点框拖动直接写 MainCamera 的 focus 子对象，再由 163 的自动焦点逻辑转换为采样 UV。

仍使用 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B）和匹配 PDB，身份沿 163。地址均为 preferred VA。沿用已记录的 REA native 超时阻塞，没有重试相同长分析或伪造 Evidence。新 PDB/dumpbin 普通文件记录在 ignored `.cache/procedural-modeling/tiny-focus-ui-depth/`，不含目标运行或新摘要计算。

`setup_photomode_toolbar` 为 `0x142B57670`（8957 B），`photomode_buttons` 为 `0x14298FC30`（4996 B），`do_photomode` 为 `0x14298EB90`（4249 B）。PDB 的按钮系统签名还明确含 `UiClickEvent` reader、`PhotomodeButton` / `UiInteractionState` / 可选 `UiLocked` query，以及可变 MainCamera、PhotomodeState、ImageFormationConfigs。该类型证据不代替所有点击资格分支的恢复。

## 三个按钮的准确连接

工具栏按实际字符串长度引用资源，并构造按钮 raw tag；处理器从 `0x1436095D8` 的相对地址表分派。不是从图标外观推断功能：

| 资源标识                            | 构造 tag 的指令   | tag → handler | 实际写入                                                   |
| ----------------------------------- | ----------------- | ------------- | ---------------------------------------------------------- |
| `toolbar/photomode_tree_seethrough` | `0x142B58708`，14 | `0x14299064C` | 调 `iter_non_default_mut`，逐项 XOR profile +0x3D          |
| `toolbar/photomode_focus`           | `0x142B58106`，15 | `0x142990389` | `0x14299039C` XOR PhotomodeState +0x0D；下游用于焦点框显示 |
| `toolbar/photomode_pin`             | `0x142B58054`，16 | `0x1429903CA` | 调 MainCamera::focus，改 focus selector 与对应点数据       |

焦点图标翻转的是显示状态，不能解释成“开启/关闭整个景深”。固定焦点按钮也没有直接把 shader 的 `focus0/1` 距离改成一个 CPU 常量。

`iter_non_default_mut`（`0x1409AA280`，26 B）返回 `[root,root+0xC0)`、起始 ordinal=0。按钮循环 `0x142990690–0x1429906AE` 每步加 0x40，跳过 ordinal 0，在 +0x3D 执行 XOR。因此本选定布局是 **profile 1、2 各翻转一次，profile 0 保持**。这不是“把所有配置统一设置为某个目标值”。

**构造例。** 原 tree_see_thru 为 `[true,true,false]`，一次所选按钮动作后为 `[true,false,true]`；第二次恢复原值。当前 profile 是否被渲染采用，仍取决于 164 的 kind 与模式门。不得由按钮存在推成所有模式的总开关。

## 固定与拖动怎样接回 focus 字段

pin handler 在 `0x1429903DD` 调用已核身份的 MainCamera::focus。选定原 selector 0/1 时转到 selector 3，并把原 +0x10/+0x14 点带到 +4/+8；原 selector 3 时转到 selector 0，把原 +4/+8 点带到 +0x10/+0x14。另有 selector 2 的独立分支。本篇只解释这些 raw 分支，不补齐枚举名称、全部合法域或联合体其他字节的意义。

`do_photomode` 中 `camera_focus_canvas` 是实际交互入口，不只是装饰图资源：

1. `0x14298F4E3–0x14298F4FA` 创建该 widget context；`other/camera_focus` 与 `_pinned` 是其下游显示资源。
2. `0x14298F5DD–0x14298F60D` 取得所选屏幕点 p=(px,py)、WindowSize.as_vec2 和 aspect_ratio。p 来自输入块 +0x60 所指两项 float；本轮没有进一步把该整个输入块命名成所有原始设备/DPI 来源。
3. `0x14298F63F–0x14298F66A` 形成 `x=(2px/W-1)*(W/H)`、`y=1-2py/H`。
4. selector 3 分支调用 `UiWidgetContext::dragged`，返回 raw 值大于 2 才在 `0x14298F684/689` 写 focus +4/+8。其他选定的可拖动分支在 `0x14298F6D5/6DA/6E0` 写 +0x10/+0x14 并设置 selector=0。selector 2 另走不写点的分支。不猜 dragged 各 raw 值对应哪个鼠标阶段。

**构造例。** W=1920、H=1080、p=(1440,270) 得 focus 点 `(0.888889,0.5)`，再代入 163 的配置点公式得到 UV=(.75,.25)。这里 UI 写点与 shader UV 变换互为所选条件下的逆变换；163 的直接光标策略另有半像素项，不能混成同一公式。

## 锁定请求与生效边界

每次该更新在 `0x14298F51C` 先将 PhotomodeState +4 设为 `0xFFFFFFFF`。部分焦点/相机状态会写当前相机 mode 作为请求（如 `0x14298F5A4`、`0x14298F6D2`）；读取到的结果在另一分支写 selector=1 与点数据（`0x14298F5C3–5DA`）。163 已证同一资源 +4 进入 autofocus 的 focus_lock_request。

因此应区分 **UI 写入点、提交锁定请求、GPU 焦点状态、结果消费**。本轮未完成该读回对象的全部类型/延迟/有效版本证明，也未证明点击当帧就锁定成功。全部 UI 默认值、镜头滑块范围、快捷键、跨模式恢复和所有加载写端仍未穷尽。

综合 demo 可采用：保留一个相机/焦点所有者；焦点框显示开关与焦点策略分离；拖动点用统一坐标换算；请求携带视图与序号，旧读回不得覆盖新操作。若我方需要统一树木总开关，应设置明确目标值，不能照抄逐 profile XOR 后声称它们一定一致。这些是独立设计建议。

[focus_ui_depth_probe.py](tiny-glade/tools/focus_ui_depth_probe.py) 核验所选 tag、跳转表、字段写端及构造例；它没有点击界面。静态核验 **Passed**；游戏、GPU、Unity、存档、画面与性能验证均 **Not Run**。
