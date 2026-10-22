# Tiny Glade：确认、取消与建造画布输入映射

后续 [135](135-tiny-glade-menu-tool-exit-and-timber-cleanup.md) 已补工具点击到模式请求的实际消费者和阶段、菜单关闭状态提交、木框所属槽清理到木板池 flush；完整导航 Cancel 回调与历史忙碌后的最终接受仍未证明。下文保留本轮的输入调查范围。

2026-10-22，Pacific Time。续接 [131](131-tiny-glade-placement-lifecycle-and-animation-handoff.md)。本篇只分析发行 EXE、PDB 和随游戏提供的控制器配置；没有启动游戏、模拟输入、读取用户按键配置或检查用户项目。调度与发布另见 [134](134-tiny-glade-preview-handoff-schedule-and-publication.md)。

**新增接通了默认物理输入、动作状态、画布拖动、矩形创建，以及 Escape 发默认模式请求的路径。** 最重要的区别是：通用 `ui_confirm/ui_cancel`、画布 `left_click` 和 `main_menu` 是不同动作；拖动结束的两个原始值也不能分别命名为“取消”和“确认”。所有设备、重绑和打断组合仍未穷尽。

## 默认输入到动作状态

| 入口             | 本地证据与实际消费者                                                                                                                                                                                  | 结论边界                                                                                              |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 鼠标左键         | `translate_input` 在 `0x140B6B5A6–0x140B6B5BC` 检查 MouseButton 原始值 0，合入 `ActionSetValues+0x8C`；`calculate_input_delta` 转成第一份 DigitalActionState；`ui_update` 在 `0x140BF0814` 读取该状态 | 接通画布主交互；不是通过 `ui_confirm` 字段放置矩形                                                    |
| 鼠标右键默认绑定 | `KeyBindingsV2.default` 在 `0x140A1F76F–0x140A1F779` 构造 MouseButton 值 1；经 `+0x278` 指针 / `+0x280` 长度进入 `translate_input` 的 `0x140B6C194–0x140B6C264`，合入第二份动作状态的输入标记         | 这个消费者还有累积移动量与 3.0 的比较；不能把任意右键按下都写成候选取消。它到矩形退出的完整桥仍缺证据 |
| Enter 默认绑定   | V2 默认函数在 `0x140A1F893–0x140A1F897` 写 KeyCode `0x3A`，经默认向量 `+0x320/+0x328` 和 `translate_input` 的 `0x140B6D0BA–0x140B6D164` 合入 `+0xA1`；键名表实际返回 `Enter`                          | 对应通用 `ui_confirm`，未证实它直接写 `CreateRectangleCmd`                                            |
| Escape           | `translate_input` 在 `0x140B6B5F3` 和 `0x140B6CFD5` 使用 KeyCode `0x73`，键名表返回 `Escape`；按 EscMenuState 分支分别合入通用取消标记 `+0xA0` 或菜单标记 `+0xA9`                                     | 是有上下文的路由，不是统一投递“删除候选”                                                              |
| 控制器 A / B     | `assets/steam-controller/controller_neptune.vdf` 的 `controller_mappings/group id=1`，`button_a/Full_Press` → `GameControls ui_confirm`，`button_b/Full_Press` → `GameControls ui_cancel`             | 只确认随包默认配置；不代表玩家当前 Steam Input 配置，也未把 A/B 的所有导航分支等同于鼠标交互          |

动作名称也有二进制对应。`MainAction` 字符串反序列化器 `0x141C6F780` 将 `right_click` 映射到原始值 7、`ui_cancel` 到 `0x1A`、`ui_confirm` 到 `0x1B`、`main_menu` 到 `0x23`；例如 `0x141C6F9C1–0x141C6F9DA` 实际比较完整 `main_menu`，跳到 `0x141C6FF11` 写 `0x23`。这不是依据按钮标签猜语义。

`calculate_input_delta` (`0x1419ADF30`) 的带类型 wrapper 实际调用位于 `0x141A09A6F`。它从 ActionSetValues 的前一值与本次标记计算状态：第一份写到 ActionSetStates 的 `+0`；通用取消写 `+0xA0` (`0x1419AE9DD`)，通用确认写 `+0xA8` (`0x1419AEA64`)，菜单写 `+0xE8` (`0x1419AEF2C`)。**Values 的 `+0xA0` 是一个字节标记，States 的 `+0xA0` 是另一对象内的状态记录，不能混用偏移。**

状态 helper 提供了命名锚点：`DigitalActionState.just_released` 在 `0x140938B90` 判断原始值 3；`pressed/released` 以 3 为界。`just_pressed` (`0x140938B60`) 对原始值 0 返回真，对重复状态 2 还检查计时，所以不能只把它概括成单一硬件按下沿。

## 从画布拖动到矩形创建

`ui_update` (`0x140BF00B0`) 的 wrapper `0x141A5C6B0` 在 `0x141A5CBC5` 实际调用它。已核参数包括 ActionSetStates、UiState、GameTime，以及 WindowFocusEvent、EscapeMenuJustOpened、ShutdownGameCmd 的 reader。所选画布路径读取第一份主动作状态，并把释放、失焦、菜单打开、退出消息作为结束交互的输入条件。

`DragState.is_started` (`0x140901020`) 判断原始值 3；`is_finished` (`0x140901030`) 判断值小于 2；进行中写值 4。`ui_update` 的 `0x140BF08F1–0x140BF0900` 根据命中类别和当前 WidgetId 是否一致计算结束载荷，`0x140BF095D–0x140BF0966` 写回它。**结束的原始值 0/1 带有命中结果，现有证据不支持把它们贴成 Cancel/Confirm 枚举。**

矩形 UI (`0x140ADC7A0`) 进一步使用独立资源 `ShapesDragMouseMoved`：

1. 开始拖动时，`0x140ADCA4B` 清 `+0x0C` 的 moved 标记，并保存起始屏幕光标位置、清累计量。
2. 进行中，`0x140ADCB0B–0x140ADCB3B` 读取动作中的二维 cursor delta，累计每次向量长度；`0x140ADCB40–0x140ADCB4C` 在累计值 **大于 4.0** 后置 moved。这里是输入移动累计量，不能移植成 4 米、4 厘米或直线净位移；其在所有输入后端下的单位未穷尽。
3. 所选匹配 WidgetId 的结束分支在 `0x140ADD3BE` 检查 moved。已移动则回到预览处理；未移动才继续候选边界检查。由此证实该分支区分点击确认与拖动改尺寸，**不是每次结束拖动都创建房子**。
4. `0x140ADD3FB` 的 `GladeBorder.is_shape_inside` 拒绝时发反馈并返回预览路径；通过才在 `0x140ADD67A` 写 `CreateRectangleCmd`。后续还有建造音效消息；不能把按键事件本身当作创建成功。

这四步是选定矩形分支的控制流，不是完整设备交互手册。连续预览、拖动尺寸和下一次点击的候选参数仍由同一矩形 UI 持有，没有发现这里按每次移动排一套独立施工动画的证据。

## Escape 到候选退出：接通请求，保留接受条件

`do_gui_escape_menu` (`0x14033DFA0`) 的实际 wrapper 调用是 `0x1401C185A`。在菜单动作的选定路径，`0x14033E1DA–0x14033E1EA` 对 `ActionSetStates+0xE8` 调 `just_pressed`；菜单关闭、非活动 timelapse 等条件通过后，进入打开菜单分支。timelapse 活动时走历史 interrupt 路径，不能归入普通取消。

打开分支中，当前 AppMode 的原始值 9 有专门历史处理，`0x10` 跳过默认模式请求；普通矩形模式首字节为 1，不走这两个特例。`0x14033E68E` 调 `AppMode.default`，后者在 `0x140B4B6AA` 写首字节 **0**。随后 `0x14033E6C9–0x14033E6EE` 向带类型 `RequestAppModeChange` writer 的队列追加 32 B 记录；`0x14033E6F5–0x14033E729` 另向 `EscapeMenuJustOpened` writer 追加通知。两个消息作用不同。

模式请求的消费者也已接到实际代码：wrapper `0x1400F7640` 在 `0x1400F7E28` 调 `mode_manager`。`0x140B42A47–0x140B42AF7` 读取该 reader，按 32 B 记录定位最后一个未读请求；`0x140B42B33` 的实际 E8 目标是 `0x141B6B0B0` 的 `check_if_can_switch` 特化。该 helper 的接受分支在 `0x141B6B13C–0x141B6B14A` 将请求中的 24 B 模式复制到 AppMode；另一分支先写 HistoryCmd 原始值 4。入口还存在 UiState 活动状态等早退。因此不能把“发出了默认模式请求”写成无条件立即接受，也不能声称已证明历史处理中该请求最终一定重试成功。

一旦模式实际变为默认值 0，矩形 UI 的模式门不再满足 `[0]=1 && [1]=2`，便在 `0x140ADCDCA` 清 Preview 判别后返回，绕过本函数的创建写端。至此接通的是：

**Escape 的菜单动作 → 默认模式请求与菜单通知 → 有条件写 AppMode → 矩形候选清零 → 停止本 UI 的木框供给。** 木框消费者何时清分配，以及此前消息是否已消费，见 [134](134-tiny-glade-preview-handoff-schedule-and-publication.md)。这条链没有“删除已确认的逻辑房屋”，也不替代撤销。

## 适合 demo 的独立契约

建议沿用 [132](132-demo-building-feedback-state-and-update-budget.md) 的单一候选和既有命令入口，把 `确认候选`、`结束改尺寸`、`退出当前工具`、`打开菜单` 明确区分。由输入适配层为鼠标、键盘、控制器产生这些意图；确认仍需正式命令成功，取消仍需使候选代次失效。输入层不另维护一份世界历史。

若选择“拖动定尺寸、点击确认”，将阈值定义为自己的屏幕输入规则并使提示与消费者一致。不要照抄本地常数，也不要用一个 finished 布尔同时表达松开、取消和提交。菜单打开若要取消候选，应明确调用同一取消入口，不能只期待 UI 失焦自然完成。

## 证据、复核和剩余缺口

输入为本机 `C:\Software\Steam\steamapps\common\Tiny Glade` 的 `tiny-glade.exe`（65,612,184 B）、匹配 `tiny_glade.pdb`（310,513,664 B）和上述随包 VDF；沿用 [131](131-tiny-glade-placement-lifecycle-and-animation-handoff.md) 的制品身份，本轮未新增计算摘要。PDB 仅由 DbgHelp 读取，native 范围由既有 dumpbin 离线反汇编。REA provider 的既有失败条件未变，没有重试整程序分析；本轮是普通文件证据，不是新建的 REA Evidence。

可复核入口：[placement_input_schedule_probe.py](tiny-glade/tools/placement_input_schedule_probe.py)。它只读目标文件，检查 **18 个直接调用、16 个原字节锚点、5 条注册 vtable 连接、45 个阶段名、两份 chain 元数据、拖动阈值、两个键名和 A/B 配置结构**；它不是游戏行为测试。完整本机输出在 `.cache/procedural-modeling/tiny-placement-input/verified-input-schedule.json`，原始反汇编、符号枚举与候选搜索保留在同目录，均不提交发行制品或反汇编正文。

从 REA 根目录复核时，为 `--output` 选尚不存在的路径；脚本拒绝覆盖已有回执：

```powershell
python -X utf8 docs/studies/procedural-modeling/tiny-glade/tools/placement_input_schedule_probe.py `
  'C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe' `
  --controller 'C:/Software/Steam/steamapps/common/Tiny Glade/assets/steam-controller/controller_neptune.vdf' `
  --output .cache/procedural-modeling/tiny-placement-input/recheck-input-schedule.json
```

本轮该 reader 复核 **Passed**；新增 Python 的 AST 解析，以及本轮 5 份 Markdown 的 UTF-8、围栏和 145 个本地链接目标检查 **Passed**。未运行游戏、Unity、交互或性能测试。

| 缺口                                          | 当前结论                                                        |
| --------------------------------------------- | --------------------------------------------------------------- |
| 右键是否在全部建造上下文取消                  | 仅接通默认绑定到 right_click 状态；到候选退出的桥仍 **Unknown** |
| A/B、Enter 与全部画布手势的桥                 | 通用动作和鼠标主动作分开；导航/光标适配未穷尽，**Unknown**      |
| 所有重绑、焦点恢复及退出组合                  | 未读取私人配置，未枚举全部分支，**Unknown**                     |
| Escape 与确认同一更新相撞、历史忙碌后最终接受 | 已找到请求与门禁，未证明全部竞合的最终结果，**Unknown**         |
| 点击、手感、帧时序和画面                      | **Not Run**                                                     |
