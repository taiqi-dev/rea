# Tiny Glade：菜单背景快照与悬停分类

2026-10-24，America/Los_Angeles。承接用户在「Supervisor｜小屋美化与未完事项」的界面反馈，仅调查发行制品和用户指定参考图。实施需求来自协调根 `Docs/Planning/Records/UserFeedback20261024Evening/Plan.md` 的 REA/UF01 节；本会话没有读取或修改 Unity 源码。

## 参考图能说明什么

已读取该记录 `References/reference-3.png`、`reference-4.png`、`reference-6.png`。图 3/4 显示场景视角上叠加主菜单或设置，图 6 显示常驻分类上方的工具/参数排。图中版本标签为 v1.16.5a；截图是用户提供的视觉资料，不是本轮运行记录，不能仅凭雪点、模糊或两张图的位置变化认定冻结方式或动画时长。

本机制分析对应本机 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B）及已匹配 PDB（310,513,664 B，GUID `d8d61d04-9e31-5b47-4c4c-44205044422e`、age 1）。本轮没有通过画面版号建立截图与二进制逐构建等同关系。

## 菜单背景：事件截图请求与缓存纹理

**静态证据支持菜单背景快照路径；不能把它等同于“只固定相机但每帧重新渲染同一场景”。** 新接通了两个端点：

1. `tiny_glade::screenshot::gather_screenshot_requests`（preferred VA `0x1400B1F70`）实际持有 `MenuBackgroundResources`、`FrameRenderConfig`，以及 `MessageReader<EscapeMenuJustOpened>`。其 wrapper `0x14048C9E0` 在 `0x14048D390` 调到该入口，完整泛型参数列表确认资源和消息身份。
2. `0x1400B280F–0x1400B285C` 检查所选 reader 的未读记录并推进游标，形成布尔值；`0x1400B2D61` 为假则跳过该背景请求，为真时从传入的 MenuBackgroundResources 取得共享 Arc、增加引用，把该目的地和原始目的 tag 2 放进本轮截图请求列表（`0x1400B2D6A–0x1400B2DF6`）。不能把这个分支说成“只要菜单开着，每次调用都必定再截”。
3. `render_menu_bg`（`0x1409EBB90`）取同一类型资源，`0x1409EBDE9–0x1409EBDF5` 取走 pending texture 并把槽清空；有新图则替换资源 `+8` 的旧纹理，无新图时 `0x1409EBE57` 继续读取旧纹理。存在纹理时导入 render graph，并构建 `Menu bg` raster node（`0x1409EBE60–0x1409EBEA2`）。

这证明了“开菜单事件相关请求 → 共享结果目的地”和“新结果接管 → 缓存复用”的选定结构。截图队列中目的 tag 2 的所有 dispatcher 分支、GPU 完成回调和究竟取世界帧的哪个后处理阶段尚未全部展开，不能宣称已恢复完整截图提交协议。

**构造例，非运行观察。** 第一次收到新的开菜单事件时进入该背景请求分支；下一次调用若没有新事件，则不从该分支追加。背景消费者得到纹理 T 后保存在缓存，后续 pending 为空仍用 T。即便世界内部仍在更新，这一背景消费者也不会凭空把 T 变成新的世界帧。此例不证明整个世界或渲染器被暂停。

仍需区分：背景图静止、相机输入阻断、世界模拟推进、世界是否继续绘制、加载/特殊菜单是否走另一模式。快照路径不能单独回答后四项，图 3/4 的蓝紫色覆盖也尚未接到唯一的最终合成算法。

`do_gui_escape_menu_settings` 的选定代码另外包含 settings background 与主题背景资源引用，其完整选择条件未恢复；因此不能把暂停菜单的这条缓存路径推广为冷启动、特殊背景和所有设置页都只使用当前世界截图。

## 分类悬停与动效：复用已证链

直接证据沿 [144](144-tiny-glade-ui-motion-static-chains.md)、[147](147-tiny-glade-click-completion-and-row-timing.md)、[149](149-tiny-glade-ui-hit-gates-and-next-research.md)、[150](150-tiny-glade-ui-capture-release-and-overlap-arbitration.md)、[151](151-tiny-glade-selection-focus-grace-and-ui-sound-events.md)：

- 工具栏父子显示会消费交互聚焦状态，appear/focus 有各自更新；逻辑显示与命中注册另有门控，画面残留不授予输入。
- `toolbar_button_keep_focus`（`0x1429853C0`）所选分支刷新约 0.3 秒计时器，失去当次焦点时扣 dt，正值可补写焦点。它提供跨按钮/子排间隙宽限的实际机制，不是所有菜单统一的 300 ms 退场时间。
- 持久工具与类别选中另来自正式 AppMode/Toolbar；点击脉冲和聚焦不会自动授予业务工具。整排统一 reveal 已有证据，逐个按钮错峰出现仍未证实。
- 页面隐藏/换页应显式取消旧按压或拖动；旧控件停止登记本身不保证捕获立即终止。焦点声由进入边沿触发，持续悬停不逐帧重复发开始事件。

**构造例。** 分类 A 聚焦后显示其子排；指针短暂跨过间隙，冷却仍大于零，可继续维持该展示状态。若显式关闭页面，自己的实现应使旧冷却与回调失效，而不能等待宽限再清输入。原作完整系统相对顺序和实际可见延迟仍未运行验证。

## UF01 可独立实现的行为

按用户已经明确的产品需求实施即可，不必等待所有原作分支恢复：

1. 开菜单时在自己的世界画面与 HUD/UI 之间取得一次背景图，同一菜单事务内换页复用；关闭释放，尺寸变化和无世界相机有明确处理。不要每帧截图、存盘或暂停全局时钟来伪造静帧。
2. 分类常驻，悬停展示相应工具候选；点击/键盘路径仍可用，展示状态与当前正式编辑工具分开。移向工具区域不闪退，显式关闭绕过普通 pointer-leave 宽限。
3. 动效复用正式生命周期，旧代次回调失效，透明度/缩放与命中分开；背景和所有按钮按同一输入所有者阻断场景穿透。

实现和共享 UI 写入仍归既有 UF01 owner，本研究不新建另一 UI 系统。运行、画面、确切帧序和手感均 **Not Run**。

## 工具记录

本轮 REA MCP 已重新可用，`open_binary` 成功绑定所选 Ghidra 12.1.4；对 `fill_weather_slots` 的首次函数分析仍在 300 秒后发生客户端 tools/call 超时。之后 Evidence summary 的该 operation 保留记录数为 0，未冒称 native 分析成功；已通过 `close_binary` 关闭本轮会话。继续使用本地 DbgHelp、dumpbin 的有界静态证据，原始文件在 ignored `.cache/procedural-modeling/tiny-menu-environment/`。

本轮 [menu_environment_probe.py](tiny-glade/tools/menu_environment_probe.py) 另外校验选定菜单事件 gate、雾保存字段、序列化键与画质/橡皮查表。它不会替代上下文中的手工数据流分析，也不证明 GPU 截图完成或真实 UI 手感。
