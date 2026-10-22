# Tiny Glade：实体生效、实例上传与最终帧提交

2026-10-22，Pacific Time。接续 [134](134-tiny-glade-preview-handoff-schedule-and-publication.md)，退出与木板池见 [135](135-tiny-glade-menu-tool-exit-and-timber-cleanup.md)。本篇补具体 executor 与外层渲染调用，仍不运行目标。

**已将“库默认”推进到本地程序的 executor 选择、末尾 deferred 应用开关，以及同一 App 从 update 到 render、维护和图执行的入口。** 对选定正常路径，可以解释 CPU 生成如何到达提交机会；不能保证每个新实体在同一次更新已通过所有 query、每份上传必被当次图采用或 GPU 已完成。

## Update 选择的 executor 与末尾应用

主程序配置 Update 时，`0x1405E9115` 调 `Schedule.set_executor_kind` (`0x140F255F0`)，传原始值 0。该 setter 在 `0x140F2562F` 调 `make_executor`。现在有二进制证据命名 0 的实际实现：

- `make_executor` 的零分支从 `0x140F23A9B` 开始，申请 0x50 B 对象，返回 vtable `0x14323ACF8`。
- 该表的 `+0x28` 是 `SingleThreadedExecutor.run` (`0x140ED6DE0`)，`+0x30` 是 `set_apply_final_deferred` (`0x140F0EC10`)。不是根据 enum 顺序猜它是单线程。
- 构造时 `0x140F23AD4` 写临时结构 `+0xC8=1`，经 `0x140F23AF8–AFF` 复制到新对象 `+0x48`。setter 的四字节函数正是将布尔参数写入 `+0x48`。

`run` 会检查条件和系统身份，普通系统在 `0x140ED71D3` 走 `run_without_applying_deferred`，执行后把相应位并入待应用集合。另一路 `0x140ED6ED1` 调内部 `apply_deferred`；迭代结束后，`0x140ED7293` 检查对象 `+0x48`，非零才在 `0x140ED72AB` 再应用 pending deferred。

这补上了一个明确边界：**所选构造的 executor 默认在正常结束时应用待处理系统的 deferred；不意味着每个业务系统之后都应用。** 条件未通过的系统、参数取得失败、错误退出以及开关后来被改写，均不能直接套这个结论。本轮没有穷尽 trait 间接 setter、内联字段写端，也没有获得最终构建的 ApplyDeferred 节点列表。

## 屋顶实体和实例仍有先后条件

[131](131-tiny-glade-placement-lifecycle-and-animation-handoff.md) 已核 `create_roof` 经 Commands 产生屋顶，动画两路初值为零；[134](134-tiny-glade-preview-handoff-schedule-and-publication.md) 已将它定位到 RoofSystems，后续是 Timberframe、WallVisualGenerators、RoofAssemble、PrepareRendering。

若屋顶的 deferred 直到整个 Update 末尾才应用，**在更早阶段已经执行过的 RoofAssemble query 不会因末尾应用而倒回重跑**。若依赖图在 RoofSystems 与 RoofAssemble 之间插入有效同步点，则同一次更新存在被 query 消费的条件。局部 chain_ignore_deferred 与全局普通 chain 需要结合最终图解释，不能用末尾 flush 替代中间屏障证据。

尖顶在 RoofAssemble 的选定路径读 RoofAnimation 第二路进度，收集记录后调用普通 SSBO update；屋瓦和木板走稀疏实例池，分别在 PrepareRendering 调对应 `gpu_flush`。动画进度已写入 CPU 记录、实体已可查询、GPU buffer 内容已提交是不同边界。

容量失败处理沿用 [112](112-tiny-glade-external-pool-producers-and-draw-bindings.md)：屋瓦新 GPU buffer 创建成功才替换 raw handle、发布容量，失败保留旧的发布字段；脏内容按页边界上传。这个成功门不能提升为全部失败情况下无损保留新几何的保证。

## 主循环确实先更新同一 App，再进入渲染

`GameLoop.main_loop` (`0x14035ABB0`) 的所选路径：

| 位置                | 实际调用或数据                                                              |
| ------------------- | --------------------------------------------------------------------------- |
| `0x140360E51–E58`   | 对 `rsi+0xF0` 的 App 调 `App.update` (`0x140E02350`)                        |
| `0x140361076–1080`  | 同一 App 字段作为参数交给 `tiny_glade::render_loop::render` (`0x1400FD580`) |
| `0x1400FD8B3`       | render 正常资源路径调用 `nani_frame_boundary_maintenance` (`0x140962570`)   |
| `0x1400FDE06/16/26` | 创建 DrawLists、`build_draw_lists`、排序                                    |
| `0x1400FECA9`       | 一条分支调用 `GraphExecutor.execute` (`0x140355DF0`)                        |
| `0x1400FED6D`       | 另一条分支调用 `GraphExecutor.execute_and_present` (`0x140353810`)          |

维护调用前存在 world 资源槽、指针与可取得状态检查（例如 `0x1400FD85F–FD88F`）；没有资源并非照常执行完整维护。两条图执行分支还有各自参数和资源检查。本轮只确认调用、正常路径顺序与分支分离，没有将所有前置谓词命名，也没有以 execute 的名字保证实际 present 成功。

这使此前外层顺序的缺口缩小为：在所选正常主循环路径，Update 内 PrepareRendering 的 CPU 操作先发生，随后 render 做边界维护，再构造/提交绘制与图执行的工作。**它仍不是 GPU 完成顺序证明。** `gpu_flush` 的 CPU 返回、队列提交、依赖/屏障满足、swapchain present 和真正扫描到屏幕不能合并。

## 与最终屋瓦绘制的连接还差什么

已建立的连接可重用 [112](112-tiny-glade-external-pool-producers-and-draw-bindings.md)：屋瓦池的 raw/容量 → 边界维护的同类型键 → GpuWorld 容量表 → cull/draw-list 参数和外部资源绑定。现在又知道该维护位于 update 后的 render 中。

仍需区分三项限制：

1. 本轮没有把每个图 closure 的资源版本、外部导入与 descriptor 绑定逐条接回同一次 `GraphExecutor` 调用。已有绘制回调的静态连接不等于每个分支都执行。
2. 并非每个候选都会通过视锥、遮挡、LOD、容量与材质筛选；“GPU 已有实例”不等于产生可见像素。
3. 没有抓取实际 command buffer、GPU fence 或 present 结果，不能宣称零帧延迟、原子换显或木框必定无缝退出。

## 综合 demo 的可实现发布条件

以下为独立规格，需在后续实施时接项目既有权威：

| 事件               | 可以承诺的事                             | 候选/动画应怎样响应                |
| ------------------ | ---------------------------------------- | ---------------------------------- |
| 正式命令接受       | 逻辑建筑已提交，拥有稳定身份             | 进入等待显示，不能仅凭它清所有预览 |
| 几何结果准备       | 当前建筑代次的必要 mesh/实例数据已可发布 | 丢弃旧代次；记录失败与拒绝原因     |
| 当前显示资源已接管 | 有效几何与实例引用已交给既有渲染消费者   | 移除对应木框，开始或继续显示动画   |
| 取消/撤销/读档替换 | 旧候选或显示代次已失效                   | 旧任务和完成回调不得复活它         |

不建议为普通建造每次等待 GPU fence；通常由既有渲染资源生命周期和有序提交保证正确使用。若产品要求严格的首帧确认，应另定义必要的可观察回执，不能让一份全场 GPU 等待成为每次建造的常规成本。这是设计选择，当前没有用户项目的性能测量。

构造例：Update U1 接受 B3，屋顶到 U1 末尾才生效，U1 的组装已经错过该实体；U2 正常 query 后生成对应实例，才满足本产品定义的显示接管条件。若 U1 末尾已撤销 B3，则 U2 的旧结果不能发布。这个例子说明中间屏障与末尾应用的区别，不是测得 Tiny Glade 固定需要两个更新。

## 证据与收口

EXE/PDB 身份及工具沿用 135，原始范围、符号和候选枚举保存在 `.cache/procedural-modeling/tiny-menu-publication/`；[menu_publication_probe.py](tiny-glade/tools/menu_publication_probe.py) 的 19 个调用、11 个锚点、4 个系统注册及 executor 连接检查 **Passed**，不计算摘要、不执行目标。仍缺最终 schedule 图、所有 settings 写端、图资源版本到设备完成的全链；运行/画面/性能验证 **Not Run**。
