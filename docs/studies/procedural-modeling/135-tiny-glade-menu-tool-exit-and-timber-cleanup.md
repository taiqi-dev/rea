# Tiny Glade：菜单取消、工具切换与木框清理

2026-10-22，Pacific Time。续接 [133](133-tiny-glade-confirm-cancel-input-mapping.md)、[134](134-tiny-glade-preview-handoff-schedule-and-publication.md)。仅分析本机发行制品；运行、输入模拟、私人配置和用户工程检查均未做。

**工具按钮 → 模式请求 → 模式接受 → 候选退出 → 木框所属槽清理 → 木板池 flush，已补到具体消费者与阶段。** 菜单关闭另有自己的状态提交，不能把它等同于恢复先前建造候选。完整的控制器取消回调、历史忙碌后的最终处置仍保留缺口。

## 工具按钮和模式管理器在生成之前

`switch_app_mode_button` 的带类型 wrapper `0x142389890` 接收 `UiClickEvent`、含 `SwitchAppModeButton` 的 query、`MessageWriter<RequestAppModeChange>` 和当前 AppMode，在 `0x142389B2C` 调业务函数 `0x142984C50`。

函数读取未消费的点击记录，校验实体槽、generation 和组件可取得等条件。所选成功路径 `0x142984E0F–0x142984E5E` 从按钮组件取得 **24 B 目标模式**，`0x142984D2B–0x142984D54` 将模式与消息序号写为 32 B 队列记录并增长计数。它写请求，没有直接修改世界的 AppMode，也没有直接销毁木框。

本轮恢复了注册连接，而非只按名字推顺序：

| 处理         | 注册证据                                                                                                                            | GameSystemSet                            |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| 工具模式按钮 | `0x14238B4EC` → vtable `0x1434DED80` 的 `+0x48` → wrapper `0x142389890`；该配置经 `0x1411CE5A0`，由 Toolbar 插件 `0x140736033` 注册 | `0x140736038` 写 raw8，**UiClientLogic** |
| 模式管理器   | `0x14056A0A8` → vtable `0x142E41C00` → wrapper `0x1400F7640`；主程序 `0x14064FA45` 调该组配置，`0x14064FB6B–6E` 入组                | raw10，**MainPreUpdate**                 |
| 矩形候选     | 134 已核 UI 与创建消费者的注册                                                                                                      | raw17，**WallShapeUx**                   |
| 木框消费者   | 134 已核 `add_timberframe`                                                                                                          | raw27，**Timberframe**                   |
| 木板池 flush | `0x1400CFB33` → PrepareRendering tuple，`0x140170A85` → vtable `0x142F73C90` → wrapper `0x1405EC990`                                | raw44，**PrepareRendering**              |

这里的 enum 身份也核过：菜单/工具注册使用的 vtable `0x1432A7688` 与此前木框的 `0x14326E7E0` 是不同代码生成副本，但 type_id/Debug 指向同一 `GameSystemSet` 类型。不能因为两处 intern 特化地址不同，就把 raw8/raw10 套到未知的其他枚举。

**条件演算：** 当前矩形模式 `(1,2)`，工具点击的有效组件目标是另一模式 M；UiClientLogic 写请求，MainPreUpdate 接受并写 M，随后 WallShapeUx 的矩形模式检查不匹配，便在 `0x140ADCDCA` 清 Preview 并返回。本次该 UI 不产生新的矩形木框消息。这个“同一次 Update 中可见”的结论以这些系统实际运行、请求通过门禁为条件；资源写入本身不需要等待 ECS Commands 应用。

若切换仍落在匹配的矩形模式，不能据此演算成退出。切换圆形可能停止矩形供给、同时让圆形消费者生成新候选；不能把全局仍有木框解释成旧候选没释放。

## 菜单打开、关闭与建造取消是不同状态提交

133 已核 Escape 的选定菜单路径写默认模式请求，并另发 `EscapeMenuJustOpened`。本轮补上关闭与状态应用：

- `do_gui_escape_menu` 的关闭分支在 `0x14033E84E` 将 NextEscMenuState 的目标 tag 设为 **2**，`0x14033E862` 调 `NextEscMenuState.set`。该分支之前还发菜单音效。已打开菜单下的菜单动作和所选 UI 布尔槽可进入关闭分支；不把这等同于已还原所有 `ui_cancel` 导航回调。
- wrapper `0x1411D8C00` 实际持有可写 EscMenuState、NextEscMenuState、PrevEscMenuState 和 `EscapeMenuJustClosed` writer。它在 `0x1411D8DDB–E10` 取出待提交 tag，写回 **12** 作为空请求，并检查目标是否为 2；为 2 时 `0x1411D8E16–E4A` 发关闭通知。
- `0x1411D8E6D–E85` 把目标写入当前菜单状态；此前保留旧状态，随后经 `NextEscMenuState.set` 交给前态资源。该消费者的参数和所选写端没有 AppMode 或矩形 Preview，**没有在这里恢复先前候选的证据**。

状态应用系统由菜单插件 `0x140736B3C` 的 vtable 连接注册，`0x140736B64` 指定 MainPreUpdate。插件另一个内容组在 `0x140736AFA` 指定 **PostGeneratorGameplay raw36**。所以不能把整个“菜单”都放进一个早于建造的 UI 阶段，也不能凭用户按键发生顺序断言模式请求一定在同一次更新中被读到。菜单状态应用与模式管理器虽然同属 MainPreUpdate，本轮未证明二者组内的全部相对次序。

通用输入还有消费边界：`mei_pre_update` 在 `0x14072D685` 分解动作状态，`0x14072D71B` 交给 `process_input_action_handlers`，再在 `0x14072D812` 重组。handler 通过 trait 回调分发。此链说明菜单可能先处理输入；**每个导航节点的 Cancel 回调到关闭槽的完整对应仍 Unknown**，不能把 B 键必然取消矩形当作已有结论。

## 请求被读取，不代表模式最终接受

`mode_manager` 在 `0x140B42A47–AF7` 定位最后一个未读模式请求并更新 reader 游标，再在 `0x140B42B33` 进入 `check_if_can_switch` 的实际目标 `0x141B6B0B0`。接受分支 `0x141B6B13C–14A` 复制模式到 AppMode；另一分支先写 HistoryCmd 原始值 4，未在该分支直接复制请求。入口还有 UiState 相关早退。

因此，不能把请求队列写入、读游标推进、历史中断和模式提交当作同一个成功点。本轮没有找到覆盖所有历史忙碌情形的原请求重试保证，也没有以“最后一个请求”证明全局取消优先级。

## 木框 clear 的实际所有权与 GPU 边界

矩形木框消费者的 `0x141F4F284` 调 `SparseInstanceBufferWriter.clear<WoodenPlankSsbo>` (`0x14281A140`，801 B)。该 writer 遍历**自己持有的 ChunkId 列表**：

1. `0x14281A1A0–1AD` 取 ID、检查范围，把该 ID 对应的字节状态写 0。
2. `0x14281A1B2–1CC` 计算 `id>>6` 和位掩码，对对应 qword 做原子 AND，清该位。
3. 后续在锁保护下把所属 ID 交回相应空闲列表，并 drain 自己的列表（`0x14281A350–374`）。没有在这里逐字节擦除整个 GPU 实例缓冲。

之后正常消费者仍可根据未读木框消息重新 push。因此清 Preview、停止一个生产者、清 writer 和全局再无木框是四个不同条件。本轮仍未证明取消时清空所有已经排入的 `ConstructTimberframeCmd`；其他生产者也可能继续产生新候选。

显示端的桥也补上了：PrepareRendering 的 wrapper 在 `0x1405ECAA4` 调 `system_wall_constructor::gpu_flush_plank_buffers` (`0x14081DF30`)，后者在 `0x14081E064` 调 `gpu_flush<WoodenPlankSsbo>` (`0x1413F07A0`)。**clear 是 CPU 端所属槽的逻辑失效；flush 与后续可见性/绘制消费才继续传播变化。** 本轮没有把每个槽状态到 GPU cull 字段的所有写端恢复完，不能把 CPU 清理指令当作屏幕当场消失。

## 综合 demo 可采用的具体契约

以下是独立设计建议，不是原作新增事实：

- 工具切换与菜单取消统一提交给既有交互状态所有者，携带候选身份和意图；模式真正接受后才让对应候选失效。记录“菜单关闭”和“取消建造”为不同结果，关闭菜单不隐式复活旧候选。
- 输入先由当前菜单/捕获者处理，再交建造工具，明确是否已消费；不要让同一按键同时关闭菜单并确认房屋。
- 取消只释放该候选拥有的实例槽，并使其旧生成结果失效；共用池、其他候选和正式建筑不做全局清空。回收与上传走现有实例管理入口。
- 明确请求被历史阻挡时是拒绝、替换还是稍后处理；使用原请求身份回报最终结果，不能仅凭“消息已消费”关闭玩家反馈。

构造例：P7 正在预览，玩家切到钓鱼工具；切换结果被接受后，P7 代次失效、释放它的 12 个框架实例槽。另一个候选 P8 的槽不受影响，P7 的迟到构建结果不得发布。12 是独立示例数，不是原作框架预算。

## 证据与未做

输入身份沿用 133：`C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe` 与匹配 PDB；本轮未新算摘要。REA native provider 的既有失败条件未变，未重复整程序分析；新增为 DbgHelp、dumpbin、PE 的普通文件证据。原始输出在 `.cache/procedural-modeling/tiny-menu-publication/`，正式 reader 为 [menu_publication_probe.py](tiny-glade/tools/menu_publication_probe.py)：19 个 E8、11 个锚点、4 个系统 vtable、2 个阶段 vtable及 executor vtable复核通过。

**已补：** 工具点击到请求及接受分支、具体阶段、菜单关闭状态提交、所属槽清理到木板池 flush。**仍未知：** 全部菜单 Cancel 回调、历史忙碌后最终接受、消息失效全路径、GPU 可见性到首帧的完整桥。交互、视觉、帧时序及性能均 **Not Run**。
