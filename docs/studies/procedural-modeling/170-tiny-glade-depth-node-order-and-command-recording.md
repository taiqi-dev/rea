# Tiny Glade：水／冰前后深度读取的节点次序与录制

2026-10-26，America/Los_Angeles。续 [165](165-tiny-glade-scene-depth-to-focus-and-coc.md)、[167](167-tiny-glade-water-ice-depth-access-and-epochs.md)。锁焦读回另见 [169](169-tiny-glade-focus-readback-validity-and-latency.md)，树实例另见 [171](171-tiny-glade-tree-instance-to-draw-binding.md)。

## 结论：已从调用顺序补到图节点、屏障和提交入口

**所追新建图的数据转交、串行录制路径保留节点顺序；自动焦点登记在本图水／冰之前，CoC prepare 登记在之后。** CPU 并行分块的结果顺序另有匹配版本公开库契约佐证，证据类型在第 3 节单列。深度访问还通过前序访问记录生成节点前屏障。这已强于只排列三个 CPU 函数名，但仍不是 GPU 抓帧或每帧实际像素证据。

这里“前后版本”指对同源图资源的不同访问阶段，不是发现了三张独立深度纹理或递增 version 字段。水／冰可能被跳过、像素可能不通过深度测试，中间还有其他深度使用者；不能由这一相对次序宣称“自动焦点的所有样本必定只含不透明地形”。

身份沿 [169](169-tiny-glade-focus-readback-validity-and-latency.md)：只读指定 Tiny Glade 安装目录中的 65,612,184 B EXE 与匹配 PDB，preferred VA base `0x140000000`，不计算新摘要。REA native 的既有 300 s 超时前提未变，继续普通文件 fallback，不虚构 Evidence。新记录在 ignored `.cache/procedural-modeling/tiny-depth-schedule/`，正式复核器是 [depth_schedule_probe.py](tiny-glade/tools/depth_schedule_probe.py)。

## 1. 节点在返回前登记，不是等待稍后的任意回调排序

`calculate_dof_autofocus` 在 `0x140B38BC9` 调 `ComputeNode::dispatch_impl`（`0x140E28810`，176 B）。其正常路径在 `0x140E288B2` 调专用 `NodeBuilder::set_render_callback`（`0x140E45650`，481 B）；`0x140E45782` 尾跳 `drop_in_place<NodeBuilder>`（`0x140E27ED0`，220 B），后者在 **`0x140E27F31` 直接调 `GraphApi::add_recorded_node`**。这个 drop 含实质登记，不能按“析构只是释放”跳过。

通用 `NodeBuilder::drop`（`0x140E41A20`，125 B）还有相同登记调用。缺 callback 或 panic/unwind 有各自路径；本篇说的是成功构造和正常返回的节点，不假设失败后仍完成绘制。

`GraphApi::create_node`（`0x140E29900`，119 B）从 builder 的 node length `+0x70` 取当前序号，检查其 u16 范围，写入 NodeBuilder `+0x38`。`add_recorded_node`（`0x140E29B40`，3057 B）正常追加处：

- `0x140E29B69` 取当前长度，`0x140E29BEB` 取 node array 指针。
- `0x140E29BEF–BF3` 计算 `48*index`，`0x140E29BFE–C13` 复制完整 48 B RecordedNode。
- `0x140E29C17–C1A` 增加长度并发布回 `+0x70`。

167 已核的实际 `render_world` 注册点是 autofocus `0x1400FBC1B`、水／冰 `0x1400FC52E`、CoC prepare `0x1400FC598`。结合同步登记，成功路径的相对 node index 为 `A<W<C`；具体数值取决于中间节点、条件分支和调试设置，本轮没有编造三个固定编号。

## 2. 从 RecordedNode 到 CompiledGraph 保留这份数组

`GraphApi::export_temporal_and_finish`（`0x140E2D320`）正常路径在 `0x140E2D4A4–D4B8` 按 **0x1A0 B** 复制记录区，其中包含 `+0x60` 的 node Vec。它还处理 temporal 导出，不能把这个 memcpy 本身说成 GPU 同步或图像快照。

主图编译专门化 `0x140585C80`（19890 B）在 `0x140588DE7` 调 finish，返回区起点是 `[rbp+0x6F0]`。node Vec 因此在 `+0x750/+0x760`：

| 转交                     | 实际位置                                                                         |
| ------------------------ | -------------------------------------------------------------------------------- |
| 导出结果的 node Vec 保存 | `0x140588DED–0x140588E02`：`[750..767] → [CF0..D07]`                             |
| 转为构造参数             | `0x1405892AF–2C4`：`[CF0..D07] → [B80..B97]`                                     |
| CompiledGraph 构造       | `0x1405893BA/3C4` 将 `&[B80]` 传给 `CompiledGraph::new`（`0x140E8A580`，1644 B） |
| 构造中接收               | 保存该参数到 r15；`0x140E8A8D7–8E3` 将同一 Vec 写到输出对象 `+0x60/+0x70`        |

中间确实有 ResourceInfo/ResourceRegistry 和调试信息构造；本篇没有把函数名字“compile”当成必定重新拓扑排序。所追正常数据转交与节点消费者使用的是原序列。缓存复用、所有调试重写路径和跨视图图的等价性没有逐一覆盖。

## 3. 分批与 CPU 并行录制怎样区分

`CompiledGraph::compute_batches`（`0x140E892B0`，532 B）从 node count 循环构造**连续索引区间**，没有在这里按 shader 名称、耗时或材质优先级换序。所读布尔参数为 0 时形成一个 `[0,N)`；为 1 时形成逐节点区间。本轮未把该参数擅自命名成一个已找到的用户菜单项。

`GraphExecutionRecorder::execute`（`0x1403574C0`，3271 B）在 `0x14035767C` 生成这些批次，再由 `0x140357915` 调 `record_batch`（`0x1401028B0`，3648 B），按区间迭代；批次间存在 `submit_pending_cbs` 调用路径。

`record_batch` 可以在 `0x140102EF6` 调 `GraphExecutorBevy::run_in_parallel`（`0x1403A8110`，325 B），PDB 的完整泛型明确为对可变 RecordedNode slice 的 `ParallelSliceMut::par_chunk_map_mut`。CPU 工作者并行录制，不等于水／冰和 autofocus 可以任意改变资源访问顺序。

此处另有库来源证据：EXE 的已读源码路径字面量含 `bevy_tasks-0.17.3/src/slice.rs`。官方 v0.17.3 标签解析到提交 **`706fdd9800c4bf335d67f127ff6e5a93deadabb9`**，其 [slice.rs 第 110–153 行](https://github.com/bevyengine/bevy/blob/706fdd9800c4bf335d67f127ff6e5a93deadabb9/crates/bevy_tasks/src/slice.rs#L110-L153) 的契约是按输入顺序返回分块映射结果，实际源码按原 slice 的 chunks_mut 枚举并 spawn。此项是**匹配版本的公开库契约佐证**，不是给目标私有代码做全文件等同性证明。

本地继续可见 `record_batch` 将 RecordedNodeRange 结果按 IntoIter 交给 `0x140564220` 的 map/fold；`0x140564250–42A0` 顺着输入复制 0x68 B CommandBuffer 到输出、增加输出位置。没有按任务完成时刻临时排序的证据。公开源码只读取得并留本机缓存，没有安装依赖、运行 Bevy 或新算内容摘要。

## 4. 节点前有实际访问屏障，之后才录制 callback

`record_batch::closure$1`（`0x1401036F0`，4523 B）消费对应的 RecordedNode 区间：

1. `0x140103986–3989` 计算当前 node index。
2. `0x140103A00` 调 `CompiledGraph::add_pre_node_barriers`（`0x140E89AE0`，1748 B）。注意这是关联函数名，实际参数对象应按调用者追踪，不能只凭名字把其内部所有 `+0x68` 都解释为 CompiledGraph 的 node Vec。
3. 屏障列表非空时，`0x140103A2B` 调 `GraphicsDevice::issue_pipeline_barrier`；随后 `0x140103B20–3B48` 从该 RecordedNode 取 callback data/函数指针，`0x140103F53` 才调用它。
4. `0x140103AB4` 的下一节点地址按 0x30 B 步长形成。各区间顺着原节点序列消费。

屏障构造读取资源当前访问和前序访问：`0x140E89C4C–C8F` 沿前序索引取得另一访问记录，`0x140E89C93–CD4` 比较 stage、access、layout。其中 `0x140E89CAC` 检查合并 access 与掩码 `0x15540`，命中写访问等情形转入屏障构造；即使不命中，访问/layout 差异仍有其他分支。

167 已核 autofocus/CoC 的 compute read 与水／冰 attachment read/write。**构造演算：** `(0x20 | 0x600) & 0x15540 = 0x400`，所以这个读／写组合不会走“相同只读状态直接省略”的支路；布局 5/4 与 3 也不同。这是实际表值和分支的演算，不是证明每次 runtime 都产生完全相同的 barrier 包。

`submit_pending_cbs`（`0x1403561F0`，1074 B）在 `0x14035632B` 调 `GraphicsDevice::queue_submit`（`0x1400A5830`，12496 B）。由此静态链已到设备队列提交入口。具体当前队列、跨队列信号、驱动实际执行与像素结果没有运行观察；不把找到 queue_submit 名称升格成 fence 已等待。

[Vulkan 的屏障规范](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdPipelineBarrier.html)将屏障作用限定到提交顺序、阶段与访问范围；因此我方也应保留访问与屏障证据，而不是把 CPU 调用时间当作 GPU 完成时间。此规范解释不替代本目标的完整驱动验证。

## 5. 现在可以怎样称呼两个深度阶段

对成功构造且被执行的这份图，可称 autofocus 是**本图水／冰写入前的读取节点**，CoC 是**本图水／冰节点后的读取节点**。二者来自同一 D 记录家族，但使用阶段不同；不再只剩三个函数名之间的未核实先后关系。

**构造例，非运行。** 简化图只取 A/W/C 三节点，未拆批得到 `[0,3)`，拆批得到 `[0,1)、[1,2)、[2,3)`。相对读取阶段不变。若 W 的某像素通过深度测试并将 D 从 .2 写成 .4，则 A 所处阶段在该次写入前，C 所处阶段在后；若 W 被跳过或不写该像素，两次读取未必数值不同。不能把这一例子当成原作实际水下对焦效果或性能测量。

仍未知：所有缓存/调试变体，实际活跃节点与开关、具体队列与 barrier 包、每个深度像素的作者和历史残留、跨帧焦点读回完成与主机可见时点。169 的 response 模式匹配仍不因此变成严格新鲜度保证。

综合 demo 可直接采用的独立规格是：明确 A 和 C 的深度阶段，声明读写依赖，让框架据此产生屏障；CPU 可并行录制，但发布/合并保持节点序列；锁焦结果另带视图与请求代次。无需为复刻风格重新写一套渲染图，也不能仅因同名 CameraDepth 就假定它含水、树切口及最新帧。

## 验证

`depth_schedule_probe.py` 实读当前 PE，26 处指令锚点、8 个 direct call/jump 目标和三组深度访问表核验 **Passed**；独立演算复核连续批次与上述写掩码。完整反汇编、PDB 范围、官方源码 URL/tag 回执保存在本机 cache。Web reader 未能取得 Bevy 两页，随后直接 HTTPS 读取固定提交源码成功，未把失败页面当来源。

游戏、GPU、附加、Unity、私人存档/配置、画面、性能与 CPU/GPU 时间测量均 **Not Run**。没有运行目标或把字节锚点通过当作整图语义验证。
