# Tiny Glade：锁焦读回的适用条件与时效边界

2026-10-26，America/Los_Angeles。续 [163：焦点参数来源](163-tiny-glade-autofocus-parameter-producers.md)与 [166：UI 写端](166-tiny-glade-focus-and-tree-fade-ui-writers.md)。

同轮 [170](170-tiny-glade-depth-node-order-and-command-recording.md) 补登记与图录制链；该链没有替这里补出 CPU 消费前的 fence/主机可见性或固定帧延迟。

## 本轮结论

**已接上读回对象的实际类型、初始化、GPU 写入和 CPU 接受分支；尚不能给出固定帧数或毫秒延迟。** CPU 判断的是响应是否非零、是否等于当前相机 mode，以及当前 focus selector 是否允许接受。所选 16 B 读回记录没有帧号、请求代次或时间戳，不能把 mode 相等直接解释成“这是最新操作的结果”。

本轮工作项目为 `C:/Data/WebProject/rea`，制品为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`，PE32+ x64，65,612,184 B，preferred image base `0x140000000`；同目录 `tiny_glade.pdb` 310,513,664 B，沿用已核匹配的 GUID `d8d61d04-9e31-5b47-4c4c-44205044422e`、age 1。以下地址均为 preferred VA，不是运行地址。本轮不新算摘要。

沿用 REA Ghidra `analyze_function` 300 s 超时且 session 已关闭的记录；没有相关前提变化，未重试长分析或安装工具。新证据来自本地 PDB、dumpbin、PE/SPIR-V 普通文件读取，**不是 REA Evidence**。原始记录在 ignored `.cache/procedural-modeling/tiny-focus-readback/`；正式复核器为 [focus_readback_probe.py](tiny-glade/tools/focus_readback_probe.py)。正文保留关键地址，不依赖本机缓存才能理解。

## 读的确实是 DofFocusReadbackSsbo

166 留下的 `do_photomode` 查询已经能和 typed 注册链对应，依据不只是名字相近：

| 环节             | 位置                                                           | 本轮实际读取                                                                                          |
| ---------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 初始化入口       | `init_populate_ssbo_library`，`0x140B7F3E0` / 2688 B           | `0x140B7F795` 直接调用下述 typed `add_new`                                                            |
| typed 注册       | `add_new<DofFocusReadbackSsbo>`，`0x141543B40` / 547 B         | 调 `MappedStorageBuffer<T>::new_storage_buffer`，以制品既有 `SsboId` 字面量 `0x29FAA4608BF58D67` 插入 |
| CPU 查询         | `do_photomode` 的 `0x14298F523`                                | 从 `0x1434D7798` 取同一既有 64 位键                                                                   |
| GPU 图写入查询   | typed `write_rg_buffer<DofFocusReadbackSsbo>` 的 `0x14152A902` | 从 `0x14331C8F0` 取同一键                                                                             |
| CPU 动态类型入口 | `0x14298F546` 调 vtable `+0x18`                                | 注册 vtable `0x14331C7E0` 的此槽为 `0x141B1D960`，PDB 命名为该 mapped 类型的 `as_any` / `as_any_mut`  |

PDB 进一步把两处 `FrozenMap::get` 的键/值命名为 `SsboId` / `Box<BufferState>`。CPU 侧 `get` 在 `0x1429932FC` 读取键的 8 B，未把紧邻键后的其他字节当作类型标识。这里比较的是制品原有 ID，不是新计算内容摘要。

注册 vtable 的对象尺寸为 24 B；`as_any` 返回对象指针和 `0x14338EA58` 的 Any vtable，后者类型槽指向 `type_id<MappedStorageBuffer<DofFocusReadbackSsbo>>`（`0x141B1DC80`）。这把 166 的未命名读回对象收窄到了实际 mapped SSBO，而不是泛称“某个 CPU 焦距缓存”。

## 缓冲创建、映射与图写入

`new_storage_buffer<DofFocusReadbackSsbo>` 位于 `0x141B1A550` / 965 B：

1. typed `add_new` 在 `0x141543B60` 将初始数据参数置空。创建函数的无数据支路分配 **16 B、4 B 对齐、全零**的初始数据。
2. `0x141B1A5E4–0x141B1A637` 用长度 16、raw 参数 `0x32` / `5` 构造 BufferDesc，设 alignment=4，标签为 `DofFocusReadbackSsbo`，调用 GraphicsDevice `create_buffer`。未将这些 raw 参数擅自补成内存属性名称。
3. 成功支路在 `0x141B1A675–0x141B1A68C` 检查 cold Buffer 的状态、取得 `+0x48` 的非空映射地址和 `+0x10` 的字节容量；之后核对容量、16 B 整除及地址对齐。
4. `0x141B1A6BE–0x141B1A6C5` 返回 `[Buffer handle, mapped pointer, element count]`，count 由容量右移 4 得到。CPU 后续从对象 `+8` 取映射指针，`+0x10` 查元素数。

`calculate_dof_autofocus`（`0x140B38410` / 2074 B）在 `0x140B38A9C` 调 typed `write_rg_buffer`（`0x14152A8E0` / 588 B），将现有 Buffer 导入 RenderGraph 的可写资源。binder 从参数块 `+0x10` 读取这份资源（`0x140BDCF2C`），在 `0x140BDCFE4` 生成 binding=3 的 buffer descriptor；对应 shader `focus_readback_buf` 为 set=0、binding=3。dispatch 后 `0x140B38BDF` 调 typed `finish_write_rg_buffer`（`0x141537200` / 308 B），它执行 graph export 并复位库中的图状态。

这些指令证明资源的创建、持有、图访问和直接映射读路径；**graph export 这个调用本身不证明 GPU 已执行完，也不证明 CPU 此刻读到哪一帧**。本轮未继续泛查队列、fence、映射可见性或整帧执行调度。

## GPU 写出的内容和条件

选定 shader 为 `compiled-shaders/country-core/compiled/dof/calc_autofocus.precomp` 的 SPIR-V 模块：文件 offset 108，4387 words。以下 word 是模块内 word offset；reader 同时保留实际文件 offset。

| 读回布局    | SPIR-V 证据                             | 含义                                       |
| ----------- | --------------------------------------- | ------------------------------------------ |
| `+0`，12 B  | type 859，word 1943；成员装饰 word 1529 | `lock_pos_ws`，float3                      |
| `+0xC`，4 B | 同一 struct；成员装饰 word 1534         | `lock_reponse`，uint32；保留制品中的原拼写 |

shader 中另有 `frame_counter`，但它没有写入这个读回 struct。不能因为 shader 读过帧计数，就把 CPU 的 response 字段解释为帧号。

实际锁点选择是：

- word 2072/2077 从 frame constants 的成员 18 取得 `camera_idx`。
- word 3592/3597 从 globalParams 的成员 3 取得 `focus_lock_request`。
- word 3601/3609 比较二者，仅相等时进入重建世界锁点的支路：用选定 UV、深度与 view transforms 生成世界点 `1338`。
- word 3805 的 Phi 在相等支路取新点 `1338`；另一支取现有 autofocus 的 `lock_pos_ws` `157`。word 4368 将选中的点写到读回 `+0`。
- word 4378 将 **原输入 `focus_lock_request`** 写到 `+0xC`。此末尾写入没有再以相等条件过滤 response。

因此 response 是请求值的回传，不能单独当作“GPU 已为该相机重新计算锁点”的成功凭证。要证明某次回传含新点，还需该 dispatch 的 request 与 shader `camera_idx` 相等，以及 GPU 写入与 CPU 读取的同步证据。本轮没有把 CPU `MainCamera.mode` 与 shader `camera_idx` 的全链关系补成一个保证。

## CPU 怎样接受、拒绝与重新发请求

这是 `do_photomode` 的所选读回支路，不是整个函数所有 UI 资格门的穷举：

1. `0x14298F50E` 取当前 MainCamera.mode；`0x14298F55D` 将其 byte 零扩展。
2. `0x14298F51C` 先将 `PhotomodeState+4` 设为 `0xFFFFFFFF`，作为本次默认 request。
3. `0x14298F552` 要求 mapped 元素数非零；从首个元素 `+0xC` 读取 uint32 response（`0x14298F564`）。查询缺失/动态入口为空走 `unwrap_failed`，元素数为零走 `panic_bounds_check`，并非安静地当作“尚未准备好”。
4. `0x14298F584–0x14298F597` 只在 focus selector `<2`、response `!=0`、response `==当前 mode` 时接受。
5. 接受时 `0x14298F5C3–0x14298F5DA` 将 selector 设为 1，把记录前 12 B 写到 focus `+4/+8/+0xC`。这里是世界锁点，不是 163 的屏幕点 UV 或 focus0/1 距离。
6. 不匹配/零 response 且 selector=0 时，`0x14298F5A4` 将当前 mode 写回 `PhotomodeState+4` 发请求；selector=1 时此读回支路不重新请求；selector>=2 时跳过这里的接受与请求。后续 UI 拖动仍可能在别处分支写 request，见 166。

上述局部分支没有比对 request generation、采样 UV、相机矩阵、模式切换次数或时间戳，也没有在接受后清零 mapped response。后一点只描述本范围内的指令，不排除下一次 GPU 写入覆写它。

**构造例，非运行。** 当前 mode=3、selector=0、mapped point=(10,2,-4)：

| 已有 response | 所选 CPU 分支结果                          |
| ------------- | ------------------------------------------ |
| 0             | 不接受，request=3                          |
| 2             | 不接受，request=3                          |
| 3             | 接受该点，selector→1；本支路不发新 request |

若第三行记录来自较早同 mode=3 的操作，期间 selector 又回到 0，而该记录仍未被 GPU 覆写，**这一局部判断仍会接受它**。这是缺少代次比对的条件演算，不是声称运行中已经发生陈旧读回；是否能形成该时序仍取决于外围调度和状态写端。反过来，selector=1、response=2 时，所选支路既不接受也不重新发请求，不能套用 selector=0 的行为。

## 已答、部分与未知

- 已答：读回类型与资源键；实际初始化调用；16 B 映射布局；shader 的锁点选择与响应写出；CPU 的模式匹配、零值拒绝和 selector 条件。
- 部分回答：旧相机模式的结果在此处被拒绝；同模式旧结果缺少本地代次检查。后者是适用性检查的能力边界，不是已证运行故障。
- 未回答：提交到执行、执行到主机可见、主机可见到 UI 消费各段时长；固定帧延迟；具体 fence/flush/invalidate；CPU mode 与本 dispatch `camera_idx` 的完整一致性；快速切模式后旧结果能否实际覆盖新操作。

自研建议：由一个焦点状态所有者持有 request generation、相机/视图身份和最终锁点；结果至少回传同一 generation、视图身份、有效标记，GPU 完成后再发布给 CPU。只有同时匹配 pending request 才接受；取消或拖动递增 generation。需要复制的行为是“异步求世界锁点，再切入锁定状态”，具体代次协议应按自研渲染框架独立实现。这不是对原作内部已有机制的补写。

## 验证

正式 probe 对当前制品 **23 个 PE 指令锚点、13 个 SPIR-V 锚点**核验 Passed，复核同一既有 SsboId、typed vtable、模块范围与上述构造分支。`pdb-focus-readback.json` 查询匹配 11 个符号、穷尽且未触顶；实际初始化 caller 经 PDB 精确包含关系和 dumpbin 直接调用复核。原始 `proof.json`、`proof-final.json` 保留开发中较早输出，交付范围以 `proof-delivery.json` 为准。probe 编写中发生的两次宿主读取器适配错误均已修正，没有把失败轮次当 Passed。

游戏运行、附加、GPU执行、私人配置/存档、Unity、画面、手感和性能均 **Not Run**。未尝试用 CPU 调用顺序推导“一帧/两帧延迟”，也未通过静态 probe 宣称完成并发或运行时验证。
