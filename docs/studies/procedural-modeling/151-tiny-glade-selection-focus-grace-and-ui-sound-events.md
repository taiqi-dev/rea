# Tiny Glade：正式选中、聚焦宽限与声音事件

2026-10-23，Pacific Time。续接 [149](149-tiny-glade-ui-hit-gates-and-next-research.md)，补两级工具选中态的来源、聚焦保留和声音触发。捕获与命中仲裁见 [150](150-tiny-glade-ui-capture-release-and-overlap-arbitration.md)。本会话只查 Tiny Glade 制品，不读取用户工程或运行验证。

**选中态来自正式模式/分类，聚焦来自交互并带短暂宽限；声音另消费事件。** 它们不是同一个 clicked 布尔，也不应随每一帧的缩放重复执行。

## 制品和复核

沿用 150 的 EXE/PDB 身份与静态工具边界。新增完整系统签名在本机 `pdb-tool-focus-sound-signatures.json` 和 `pdb-focus-event-edge.json`；[ui_capture_focus_probe.py](tiny-glade/tools/ui_capture_focus_probe.py) 回读对应指令、常数、调用，并核对五个 typed signature。原始结果均在 ignored `.cache/procedural-modeling/tiny-ui-motion/`，没有把名字命中当成行为证明。

## 两级选中各有正式来源

`switch_app_mode_button`（`0x142984C50`）的系统签名包含 `SwitchAppModeButton`、可写 `UiInteractionState`、`Res<AppMode>`、点击 reader、`RequestAppModeChange` writer 及 `ModeJustChanged` reader。实际选中写端为：

- `0x1429850C8` 调 `0x142986F30`，PDB 命中 `country_core::systems::mode_manager::impl$58::eq`；输入来自按钮所带模式和当前模式资源。
- 返回值在 `0x1429850DF` 写入该按钮的 `UiInteractionState+2`，另一个查询遍历分支也有对应写端 `0x1429852FE`。

这将 149 尚未赋名的第三字节接到了正式模式比较。所选路径不是鼠标移到哪里就把哪里写成当前工具，也不是 pulse 播完才授予工具选中。

`switch_toolbar_category_button`（`0x142985EF0`）另持有 `Res<Toolbar>`、`SwitchToolbarCategoryButton` 和 `RequestToolbarCategoryChange` writer。`0x142986262–0x142986272` 读取当前 Toolbar 的 `+0x18` 类别字节，与按钮类别比较，把结果写入 `UiInteractionState+2`；稀疏遍历分支在 `0x142986420–0x142986430` 做相同用途的写回。

因此主分类与具体模式可以分别投影选中，点击只提出各自的请求。请求何时接受仍沿已有模式管理研究 [135](135-tiny-glade-menu-tool-exit-and-timber-cleanup.md) 的条件；不能由按钮发出请求就宣布正式状态已改变。

**构造例。** 当前类别 C、当前模式 M。类别 C 的按钮因类别匹配选中，模式 M 的按钮因模式匹配选中。把指针移到另一按钮 N，可以改变 N 的聚焦反馈，但上述正式状态仍是 C/M。请求 N 被拒绝时，也不能仅因已经播了点击脉冲就把持久选中留在 N。

## 聚焦宽限：并非普通缓动时间

`toolbar_button_keep_focus`（`0x1429853C0`）的签名明确持有 `ToolbarButtonCooldown`、可写 `UiInteractionState`、`UiToolbarButtonResetAllCooldowns` reader 及 Bevy `Time`。所选遍历逻辑为：

- `0x142985596` 读取 float 0.3；`0x142985658–0x142985675` 按当前聚焦位选择更新该计时器，未聚焦时扣除 `Time+0x58` 的 dt 并限制下界为 0。
- 另一遍历在 `0x142985B51–0x142985B68` 检查剩余值大于 0 时，重新把交互 `+1` 设为 1；另有同用途的存储分支 `0x142985C70`。

149 已证明渲染到 widget 的路径也会清零再重算 `+1`，144 已证明该位会影响聚焦动画和父子展开。因此保留计时器、当次输入聚焦、最终焦点表现要分开理解；完整系统相对顺序仍未全部展开，不把这段命名为主菜单的统一 0.3 秒退出动画。

从这些消费者推断，短暂保留可用于跨越按钮间隙时减少子排立即收起；这是一种机制用途判断，不是原作者的设计意图声明。显式关闭/换页能否绕过所有宽限，本轮仍不替原作作保证。

**构造例。** 自行取当前剩余宽限 0.3 秒，后续未获得新聚焦且每次有效 dt=0.125，扣减序列约为 0.175、0.05、0。正值期间后续补写路径可以维持焦点位，归零后不再由它强制保持。实际系统顺序和可见时长没有运行观察。

自研可采用较短、可配置的 pointer-leave 宽限，方便指针进入子排；**关闭页面、禁用和工具失效应显式终止宽限**，不能让延迟回调把已隐藏的组重新打开。具体选中标记继续来自正式状态，聚焦宽限不得改变它。

## 声音是事件消费者，不是动画更新回调

`ui_sounds`（`0x142980440`）的完整签名包括：

| 输入/输出 | 已核类型                                                                                        |
| --------- | ----------------------------------------------------------------------------------------------- |
| 聚焦开始  | `MessageReader<UiJustBecameInFocusEvent>`                                                       |
| 点击      | `MessageReader<UiClickEvent>`                                                                   |
| 拖动      | `MessageReader<UiDragEvent>`                                                                    |
| 输出      | `MessageWriter<PlayUiSound>`                                                                    |
| 分类查询  | `UiLocked`、`SwitchAppModeButton`、`SwitchToolbarCategoryButton`、`UiSlider`、`PhotomodeButton` |

原始 body 在不同分支写入不同声音 tag，例如 `0x1429808CC` 写 `0x12`，`0x142980A14` 写 `0x0C`。这支持声音按交互事件和控件类别分派，而不是让 `ui_focus_animation` 每更新一次就播音。**本轮没有完整映射 tag 到音频素材，也没有证明下游会把跨输入来源的重复事件合并。** 不将 reader 正常消费游标说成一次业务激活在所有层级只响一次。

聚焦开始事件的生产端也已接通。`ui_send_focus_begin_events`（`0x14297DED0`）的完整签名含 `Query<(Entity, &UiInteractionState)>`、`MessageWriter<UiJustBecameInFocusEvent>` 与 `Local<HashSet<Entity>>`：

- `0x14297E28D` 检查交互 `+1` 聚焦位；为真时，`0x14297E29A` 将该实体插入本地集合。
- `0x14297E2A0–0x14297E2A2` 检查插入返回值，已经在集合中的实体跳回遍历；新加入的实体才在 `0x14297E2E0` 写出聚焦开始事件。
- 未聚焦分支在 `0x14297E319` 移除集合项，允许以后重新进入时再产生开始事件。

因此此处的边沿去重有实际静态依据：同一实体持续聚焦不每帧重复发开始事件。实体离开查询或销毁时是否另有集合修剪，本轮没有完整展开；不据此声称存在泄漏，也不把这份局部集合说成所有点击/音频的统一去重器。

Mei 菜单的激活位已在 [146](146-tiny-glade-menu-state-to-render-motion-boundaries.md) 接通：点击/导航与热键进入 `used()` 的共同判断，但不能因此假定所有 Mei 声音和工具栏完全共用相同生产端。

**构造场景。** 对一个最初不在集合中的实体，依次输入聚焦位 `0、1、1、1、0、1`，所选生产端只在第 2、6 次遍历发聚焦开始事件。此例是依据分支构造的状态推演，没有运行游戏。若鼠标与快捷键在同一动作上各产生一条重复点击事件，现有研究不能保证音频下游去重；自研需先合并到同一激活结果，再发视觉与声音反馈。

## 给 Supervisor 的相应制作范围

继续并入既有 NC11 与当前两级选中态修复的明确所有权，不新建重复 UI 系统。实际主干、共享文件和已有交付由 Supervisor 在项目侧核对，本会话没有代查。

1. 主分类与子工具都投影正式状态；聚焦/按压只是覆盖层，失败请求不改选中。
2. 把 [150](150-tiny-glade-ui-capture-release-and-overlap-arbitration.md) 的旧捕获取消和释放激活条件接到真实页面，不靠退场结束回调清理输入。按住时切页须避免原输入穿透给新页。
3. 页面或工具显式退出使焦点宽限、错峰任务和旧完成回调一起失效；pointer-leave 的短宽限可独立配置。
4. 聚焦开始反馈只在进入边沿触发，持续聚焦和逐帧缩放不重播；关闭或销毁时清理对应临时状态。视觉与声音消费一次正式激活结果，沿现有输入身份去重；选中成功、拒绝、取消和普通按压分别反馈。使用项目已有可用或原创/适当许可的声音，不带入原作素材。

建议验收：鼠标与导航互换、两级选中与工具拒绝、跨子排间隙、按住后隐藏/换页、旧回调到达、同次鼠标/快捷键激活，以及静止时不重复播音。这是独立实现规格，**不是用户项目已经具备或已经存在缺陷的判断**。

本轮跨两篇的 reader 检查通过 21 个选定原字节锚点、6 个直接调用、0.3 常数和 5 个系统签名匹配；公式/构造算例另检。游戏运行、项目测试、画面、真实取消延迟、声音去重和性能均 **Not Run**。后续项目实施按当前有效的人类授权推进，研究交接不新增运行授权。
