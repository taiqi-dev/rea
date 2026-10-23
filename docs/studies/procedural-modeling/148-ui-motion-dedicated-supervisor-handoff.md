# UI Motion：给小屋 Supervisor 的独立事项交接

2026-10-23，Pacific Time。接收对话为 **Supervisor｜小屋美化与未完事项**，thread `01a16285-aea1-7602-828c-b5ef5426ada1`。本篇是研究到独立实现的交接规格；本会话没有读取或修改 3DSandboxTest 源码、项目规划或运行实例。

## 最新要求与状态

人类在本研究会话明确要求：补菜单进入/退出、按钮排是否错峰和点击动画触发/完成条件，然后发给上述 Supervisor，**将 UI 动效作为专门项专门做**。这次要求比此前只把取消/反向附带在其他 UI 工作里的安排更明确，不能继续以旧的“不独立派发”记录代替本次需求。

建议登记一个独立 UI Motion 事项，由 Supervisor 核对现有编号并确定 owner、独立分支和 worktree；不要只登记一个研究链接后停止。当前两级选中态修复继续由其原 owner 处理，动画项消费正式工具/页面状态，不重复维护点击即选中的第二份状态。

此处没有授予未知共享文件的写权限。Supervisor 需依据当前主干和既有共享修改清单，给实现 owner 精确范围，避开当前 UI 修复与性能线；私有动效逻辑和规格可以先推进，公共集成按真实消费者核对后授位。

## 研究结论怎样使用

| 可采用的独立行为               | 研究依据                                                        | 不得误读为                          |
| ------------------------------ | --------------------------------------------------------------- | ----------------------------------- |
| 出现、聚焦、激活脉冲分通道组合 | [144](144-tiny-glade-ui-motion-static-chains.md)                | 每个按钮都复制原作 1.5 倍或同一时长 |
| 逻辑状态和视觉进退分别结束     | [146](146-tiny-glade-menu-state-to-render-motion-boundaries.md) | 菜单状态提交就是最后一帧视觉完成    |
| 点击反馈不决定业务成功         | [147](147-tiny-glade-click-completion-and-row-timing.md)        | 按下回弹意味着建筑/物品命令成功     |
| 可反向、可打断，旧完成回调失效 | [145](145-independent-cozy-ui-motion-spec.md)                   | 原作已证明所有重触发交错都安全      |
| 工具排可选择短错峰             | 145 的独立规格                                                  | 已查实原作存在统一 i×delay 时间线   |
| 视觉层缩放与布局占位可分开     | 144 的尺寸链及 145 的独立取舍                                   | 为所有悬停反复触发布局重算          |

原作的菜单全屏淡入/平移生产端、完整按钮初值/时序、最终 deferred 顺序仍有缺口。这些未知不阻塞自己的有界实现，也不能当作已经恢复的原作算法写进项目验收。

## 第一批实现范围

第一批覆盖 **主工具按钮、其子工具排、一个真实页面的打开/关闭/切换**，必须接到当前玩家可用入口。需要独立事项和实际 PR，不新增一套演示 HUD 冒充正式接入。

- 主/子按钮的出现与收起、聚焦、按压、激活及失败短反馈，各自有明确来源；持久选中来自已有工具状态。
- 子工具排有整组显隐和可选短错峰，数量增加时延迟封顶；中途换类别能取消旧的未开始项。
- 页面从当前显示值进入/退出，覆盖快速开关与 A→B→C 切页；旧完成回调不能隐藏新页面。
- 退出/隐藏的命中和焦点资格按现有页面契约同步，不靠透明度为零假装不可点击。
- 一个视觉写入者从基准值组合各通道，不跨帧累乘；回收和重绑结束旧播放/监听。
- 仅调度活动动画；减少动态效果设置、UI 缩放和暂停世界时的表现时钟有明确处理。

参数起点沿用 [145](145-independent-cozy-ui-motion-spec.md)，属于我们的建议。实际 owner 应先用当前 UI 技术实现最小闭包，不因本报告安装新 tween 包或切换 UI 框架。

## 必须交付的证据

1. 当前 owner/root/branch/HEAD 与共享修改清单，以及正式按钮、子排、页面的实际消费者。
2. 已有实现与新增范围的对账，避免重复两级选中态修复或已交付项目；研究文档、合并和玩家验收分开记录。
3. 有意义的中断/取消/旧回调、单次业务激活、重绑和隐藏输入测试；适用编译检查与 PR。
4. 静止和集中展开的 UI 分配、布局/绘制工作量按项目已有性能线取证，不从参考游戏静态机制推算提帧。
5. 允许的运行/视觉验证与未做项分别记录。**本研究不新增运行授权**；后续只沿项目当前仍有效的人类授权，无法确认时标 Not Run。

本篇的实施、项目测试、视觉与性能验收全部 **Pending / Not Run**。Supervisor 接收消息不等于 owner 已开始；应回报独立事项编号、负责人/分支、首批范围和下一步真实动作。

## 供 Supervisor 自己核对落地的已有研究入口

以下是研究索引，不是当前项目“已落地/未落地”结论；本次遵从“先不查我的项目”，由 Supervisor 在项目侧核验实际代码和验证证据。

| 模块                      | 原始专题                                                                                                                                                                                                                                                                                                         | 项目对账时关注                                              |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 木杆框架预览与建造出现    | [129](129-tiny-glade-timberframe-placement-preview.md)、[130](130-tiny-glade-placement-animation-and-demo-priorities.md)、[131](131-tiny-glade-placement-lifecycle-and-animation-handoff.md)                                                                                                                     | 木杆框架与普通轮廓预览是否区分；真实候选到确认/取消的消费者 |
| 预览输入、清理和发布      | [132](132-demo-building-feedback-state-and-update-budget.md)、[133](133-tiny-glade-confirm-cancel-input-mapping.md)、[134](134-tiny-glade-preview-handoff-schedule-and-publication.md)、[135](135-tiny-glade-menu-tool-exit-and-timber-cleanup.md)、[136](136-tiny-glade-entity-upload-and-frame-publication.md) | 单一候选/命令、取消与业务成功、实例上传与最终可见性         |
| 渲染框架、受光和阴影      | [137](137-tiny-glade-renderer-language-lighting-and-demo-route.md)、[140](140-tiny-glade-lighting-brdf-and-soft-shadow-filter.md)                                                                                                                                                                                | 材质是否进入真实建筑消费者；静态算法不等于画面接受          |
| 植物风与参数生产          | [138](138-tiny-glade-vegetation-wind-shader.md)、[141](141-tiny-glade-wind-producers-and-frame-constants.md)                                                                                                                                                                                                     | 实际植物种类、根部约束、阴影/其他通道的一致性               |
| 水面与反射/折射预算       | [139](139-tiny-glade-water-shader-and-demo-budget.md)、[142](142-tiny-glade-water-reflection-refraction-and-fallback-gates.md)                                                                                                                                                                                   | 实际水面消费者、岸边表现和预算；不能仅凭参考材质宣称接入    |
| 独立 URP 取舍             | [143](143-unity-urp-cozy-style-independent-rendering-plan.md)                                                                                                                                                                                                                                                    | 独立风格实现的先后顺序，不要求复制原作管线                  |
| 实例、LOD、阴影和性能研究 | [117](117-tiny-glade-instance-batching-and-submission-costs.md)、[118](118-tiny-glade-lod-selection-and-geometry-costs.md)、[119](119-tiny-glade-shadow-cascades-and-work-budgets.md)、[120](120-tiny-glade-performance-patterns-for-composite-demo.md)、[121](121-performance-report-for-project-supervisor.md) | 复用现有性能线和实际采样归因，避免另开同一热点              |
| UI Motion                 | [144](144-tiny-glade-ui-motion-static-chains.md)、[145](145-independent-cozy-ui-motion-spec.md)、[146](146-tiny-glade-menu-state-to-render-motion-boundaries.md)、[147](147-tiny-glade-click-completion-and-row-timing.md)                                                                                       | 本次专门项的正式 UI 消费、状态所有权、中断和发布条件        |

更早的生成、地形、装饰、存档和局部更新研究沿用[现有总目录](README.md)。这份链接表覆盖当前交接所需的预览、渲染、性能与 UI 入口，不冒称已完成全项目的研究落地审计。
