# Tiny Glade：树实例到材质缓冲及绘制回调

2026-10-26，America/Los_Angeles。续 [61](61-tiny-glade-tree-mesh-processing-and-publication.md)、[72](72-tiny-glade-cpu-render-bindings-and-lifecycle.md)、[162](162-tiny-glade-tree-see-through-and-dof-composition.md)、[168](168-tiny-glade-tree-material-descriptor-producers.md)。

## 本轮结果与纠正

**已接通树自身的 CPU 更新、48 B 缓冲 flush、材质 buffer 取值和树专用绘制回调注册。** 两种树 subset 共用 `PlacementDataSsbo` 的构造和存储协议，各自有实例池与材质；本轮没有借用砖上传来填这条链。树冠和树干顶点入口都先读实例间接表，再读 `PlacementData_natural`。具体某棵树经过裁剪和排序后进入哪条间接命令，以及该间接表生产端到最终 vertex descriptor 的物理资源身份，仍未完全闭合。

对 168 有一项明确纠正：材质 CPU 参数块 **+0 是实例只读 buffer 的引用，不应称为 uniform 参数数据**。树冠 native binder `0x141571408` 实际调用 `RawBinder::read_buf`；顶点 SPIR-V 明确命名 `material_data.nani_instance_data`。SPIR-V 的变量使用数值为 2 的 `Uniform` storage class，但其结构带 `BufferBlock` 装饰，并且包含 stride=48 的 runtime array，这是该包采用的 storage-buffer 编码；不能只看 storage-class 名字把它解释成普通 uniform 常量块。材质纹理仍从参数块 +8 开始。

此编码语义另核 [Khronos VK_KHR_storage_buffer_storage_class](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_storage_buffer_storage_class.html)：Uniform storage class 的 BufferBlock 与后来的 StorageBuffer/Block 对应；本文实际类型仍由本地 native 与 shader 指令共同确定。

## 身份、范围与证据类型

只读 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`，65,612,184 B；相邻 `tiny_glade.pdb`，310,513,664 B。沿用父调查已固定的 PDB GUID `d8d61d04-9e31-5b47-4c4c-44205044422e` / age 1；本轮重读路径和文件长度，不另算摘要。下列 native 地址均为 preferred VA，image base 为 `0x140000000`，不是实时进程地址。shader 的 word offset 从各 SPIR-V 模块起点计；file offset 属于对应 `.precomp`，不能与 native VA 混用。

既有 REA native Ghidra 300 秒超时且 session 已关闭的前提没有变化。本轮复用 blocked fallback，未重新打开或进行长分析，没有生成 REA Evidence ID。证据是 Windows DbgHelp/PDB、现有 VS2022 `dumpbin` 的精确函数范围、PE section 映射及发行 SPIR-V 的普通文件读取。PDB 同地址合并符号可能有多种类型名称，类型归属结合构造表和 vtable 的其他槽位核验，不能单用地址查询返回的第一个别名定类型。

新原始记录位于 ignored `.cache/procedural-modeling/tiny-tree-draw/`。正式验证器是 [tree_draw_binding_probe.py](tiny-glade/tools/tree_draw_binding_probe.py)。没有运行游戏代码、加载目标 DLL、附加、抓 GPU 帧、访问私人存档/配置、使用 Unity、安装软件或操作鼠标与前台。

## 1. 树冠／树干的 subset 身份与共同存储协议

三组真实索引表将类别值接到构造、shader 路径和材质更新分支：

| 内部 subset 字节 | shader 名称表                       | constructor 表 | 材质分支      |
| ---------------- | ----------------------------------- | -------------- | ------------- |
| 0                | `country_core/clearing/tree_canopy` | `0x140959DC0`  | `0x1409E6B69` |
| 1                | `country_core/clearing/tree_trunk`  | `0x140959DC0`  | `0x1409E7275` |

constructor 表从 `0x143032DC0` 开始，每项 8 B。`startup_nani` 的 `0x1409E52B6–52D5` 用 `subset*8` 调该表；`0x1409E52DC–52E7` 用 `subset*160` 选择世界内的记录。shader 名称地址表为 `0x143032F90`，长度表为 `0x143032EA8`；`nani_on_scene_load` 在 `0x1409E5917–5951` 以相同类别取名称和长度，调用 `get_world_raster_pipelines`。材质相对跳表为 `0x1430330A0`，索引 0/1 分别到上述树冠／树干分支。这不是把资源配置的排列顺序当运行编号。

`0x140959DC0` 的 PDB 完整类型是 `gpu_world_subset_desc::owned::closure_env$0<PlacementDataSsbo>` 的 `FnOnce::call_once`。它在 `0x14095A18C–A197` 把类型擦除数据指针写到 Owned subset 的 +0x70，将 vtable `0x143025A60` 写到 +0x78。此表具有：

| 表偏移 | 内容                                          | 核验作用                                                 |
| ------ | --------------------------------------------- | -------------------------------------------------------- |
| +0x18  | `0x140958F30`，`type_name<PlacementDataSsbo>` | 限定具体类型，避免混用相同实现地址的 Plant 等别名        |
| +0x30  | `0x140958E10`，`gpu_flush<PlacementDataSsbo>` | 实例参数 flush 入口                                      |
| +0x40  | `0x1408FFDC0`                                 | 指令只有 `lea rax,[rcx+18h]; ret`，取得该对象内的 buffer |

同一个 constructor 不表示两类共享同一个实例分配或同一个 buffer handle。它为各自的 subset 调用分配和构造。

## 2. 已变化的 Prefab 数据怎样进入实际 buffer 更新请求

[162](162-tiny-glade-tree-see-through-and-dof-composition.md) 已证手放树动画写 `PrefabInstanceData+0x20`。本轮接续 `update_prefabs`：`0x14090FC29–FC32` 从每条 prefab GPU 实例引用的 +8 取 subset 字节，取得 `owned_subset_mut`；`0x14090FC63` 将当前源记录指针作为实参，`0x14090FC72` 直接调用 `OwnedGpuWorldSubset::update_instance_data<PlacementDataSsbo>`（`0x140954F80`，1,032 B）。每条引用步长 12 B，并非一棵 prefab 只允许一条 GPU 实例。

该专门化在完成实例位置/尺度及类型检查后，`0x140955273–5296` 按 dense slot **乘 48**，从源指针 +0、+0x10、+0x20 复制三个 16 B 块，包含 +0x20 的 `anim_t_packed`；`0x1409552AA / 52CA` 原子维护参数数据的 dirty min/max。其类型不匹配和越界路径是显式 panic，不能当成静默跳过。此处同 [61](61-tiny-glade-tree-mesh-processing-and-publication.md) 的创建 staging 协议相容，但这里是变化后更新入口。

`nani_flush_instance_updates`（`0x14257D360`，1,005 B）以 160 B 步长遍历 subset。`0x14257D57F` 先 flush 每类的 16 B GPU 实例描述；`0x14257D585–D590` 再读取类型擦除数据指针和 vtable，调用 **+0x30**。这里循环中的指针指向 Owned 记录 +0x48，所以其 +0x28/+0x30 正好对应前述 Owned +0x70/+0x78，并非另一张对象表。

Placement 专门 thunk `0x140958E10` 给数据指针加 0x18，再尾跳 `ShadowedBuffer::gpu_flush<PlacementDataSsbo>`（`0x141A85660`，1,575 B）。后者：

1. 读取 dirty `[min,max]`；`min>max` 返回，`0x141A8588D` 将末尾转为 `max+1`。
2. `0x141A858B6–58BE` 按 `48*min` 找 CPU 源；`0x141A858E3–58EF` 求 `48*(max+1-min)` 长度和 `48*min` 目标偏移，检查 CPU 与目标容量。
3. `0x141A85925` 调 `GraphicsDevice::update_buffer_bytes`（`0x140E55470`）。成功状态才在 `0x141A85939–5941` 将 dirty 范围重置为 min=最大无符号值、max=0；失败进入显式错误/panic 路径。

`update_buffer_bytes` 的 `0x140E556D0–55714` 实际把所选源 slice 拷贝到更新暂存区；`0x140E55759` 交给专门 `with_setup_cb`。其 `update_buffer_bytes::closure$0`（`0x140E559A0`，817 B）在 `0x140E55A91–5A9C` 形成 **源偏移、目标偏移、长度**的三个 64 位字段，`0x140E55B56` 调设备对象 +0x388 的间接接口。至此树参数从 staging 到真实的 buffer 更新请求、暂存拷贝和后端记录入口已有树自身证据；**不是已观察到 GPU 执行或完成 transfer**。

对 +0x388 的命名仍保留一层边界：已找到 `DeviceFnV1_0::load_erased` 中 `vkCmdCopyBuffer` 名称加载写到函数表 +0x2F8，`vkUpdateDescriptorSets` 加载写到 +0x1F0；尚未完整证明该表嵌入上述设备对象的 +0x90 偏移。虽然数值对应 `0x2F8+0x90=0x388`、`0x1F0+0x90=0x280`，不能只凭这个加法给两个 native 虚槽宣布最终 API 身份。168 的设备 +0x280 命名断点因此继续保留。

## 3. 同一个实例 buffer 如何进入树材质与顶点索引

`update_world_subset_material_args` 在 `0x1409E6B33–6B3E` 从 Owned subset +0x70/+0x78 取指针与 vtable，经 **+0x40** 得到同一对象 +0x18 的 buffer，再读首 qword handle。其后对 handle 增加保留引用，将副本放到局部 +0x90；树冠参数块 +0 指向该局部 handle，`0x1409E6C44` 调专用 binder。**flush thunk 也是对象+0x18**，因此这里的 raw handle 与被 flush 的那个 ShadowedBuffer 有字段级同一性，强于字段名相似。

树冠 binder `0x1415713B7–3C1` 取参数块 +0，`0x141571408 → 0x140E27260 RawBinder::read_buf`；其后四个纹理走 `read_tex`。树干由同一材质函数开头取得 buffer，在 `0x1409E72D5–72E8` 组装实例 buffer 与三纹理参数块，`0x14154FB0C` 也直接调用同一 `read_buf`。168 所保留的 layout base B 尚未完整解析，本轮不据 shader 的 binding=0 直接给 native B 填值。

发行 shader 包各有四个 SPIR-V 模块；本轮逐指令追踪的是各包第一个 vertex 模块，其他变体未做同等语义覆盖：

| 顶点入口         | 模块原文件偏移 | 实例间接表                      | Placement 数据               | 精确指令链，模块内 word offset                                                    |
| ---------------- | -------------- | ------------------------------- | ---------------------------- | --------------------------------------------------------------------------------- |
| canopy 首 vertex | `0x9F`         | set 8 / binding 0，u32 stride 4 | set 0 / binding 0，stride 48 | 2342 读 InstanceIndex；2350/2356 读 indirection；2375/2382 读成员6；2386 解 half2 |
| trunk 首 vertex  | `0x9D`         | set 5 / binding 0，u32 stride 4 | set 0 / binding 0，stride 48 | 1878 读 InstanceIndex；1886/1892 读 indirection；1896/1903 读成员6；1907 解 half2 |

canopy 的关键装饰：word 964 将输入 ID49 标为 BuiltIn `InstanceIndex=43`；word 972 给间接表结构 ID54 `BufferBlock`；word 1040 给 Placement buffer 结构 ID62 `BufferBlock`；word 1036 给 runtime array ID63 `ArrayStride=48`。word 2189 的 `OpVariable [64,65,2]` 与 word 1727 的 `OpTypePointer [64,2,62]` 一起说明上述 Uniform-class/BufferBlock 编码。成员6的 Offset=32 在 word 1021。trunk 的对应 BufferBlock/stride 装饰在 word 906/902，成员布局由验证器完整核对。

两者共同的顶点读取规格是：

```text
draw_slot = InstanceIndex
dense_slot = instance_indirection[draw_slot]
packed_animation = PlacementData[dense_slot].anim_t_packed  // 48*dense_slot + 32
```

因此 **InstanceIndex 不能直接当 CPU dense slot**；中间表可改变顺序及子集。[108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md) 已追到通用 `generate_draw_lists` 写原实例索引到 indirection、并把间接表起点写入命令 `firstInstance`。本轮不把屋瓦类别的上游裁剪/meta 数值挪给树，也没有把 compute 输出 set0/binding8 与树 vertex 的 set8/binding0 或 set5/binding0 仅按同名连接成物理 backing 事实。

## 4. 树材质怎样和实际绘制回调一起注册

`nani_on_scene_load`（`0x1409E53F0`，2,985 B）的 `0x1409E5A37` 创建 material binding set，`0x1409E5A9E` 调上述材质更新函数。随后同一 subset 的临时 bundle 写入：material set 在 `0x1409E5B3C`、callback 在 `0x1409E5B40`、subset payload 在 `0x1409E5B4B`。`0x1409E5B79 → 0x141620010` 的 PDB 完整类型含 `GpuDrivenDrawable, CustomDrawFn, OcclusionCulled, NaniSubsetDrawable`。所以这里已将树的 shader/pipeline、material set、subset 与回调放到同一类实体构造中。

`0x1409E5AA4–5AD4` 的条件是：FORCE_FINE 非零选 `fine_sorted_draw_fn`；否则类别 0/1 且 FORCE_NO_FINE 为零也选该函数；其余选 `coarse_sorted_draw_fn`。这两项全局开关的运行时值没有观测，因此“树通常可走细排序”有条件，“某帧必走细排序”没有证据。

[77](77-tiny-glade-draw-callback-mapping.md) 已核通用的 `CustomDrawFn → DrawListItem(+0x20/+0x28) → render_bucket` 复制与间接调用。本轮树注册槽复用该消费者，选到细排序路径时 callback 为 `0x1409E5FA0`：

- `0x1409E6261–6289` 将 subset 与绘制阶段构成 sublist 索引，从 u32 表读 start-command；并非树实体 ID 直接乘 20。
- `0x1409E62A0 / 62B0` 读取命令/计数图 buffer；设置 atlas vertex/index buffer 后，`0x1409E6431–6439` 算 `20*start_command` 与 `4*sublist_index`。
- `0x1409E6454 → 0x140E24FA0 draw_indirect_count`。recorder 将视图偏移相加后的命令字节偏移、最大命令数、计数偏移写到 +0xDC/+0xE0/+0xEC，随后记录图访问与 draw stream。

这闭合了树类别注册到计数式 draw **录制入口**的静态链。它不证明一棵树恰好对应一条 draw；多个实例可以由同一 mesh 命令聚合，空/被裁剪实例不必贡献命令。实际 pipeline layout 的 B/set 解析、图资源物理 backing、GPU 执行和深度像素仍各有边界。

## 构造演算、验收与剩余入口

构造 dirty slots 为 10、12，即 min=10/max=12。flush 上传请求覆盖 `[10,13)`，目标字节偏移 `10*48=480`、字节数 `3*48=144`，包含中间 slot11。若构造 `InstanceIndex=23`、`indirection[23]=11`，shader 读的动画字节为 `11*48+32=560`，不是 `23*48+32=1136`；前者落在上述 `[480,624)` 更新范围。设 slot11 的 packed 值由我们构造为 half(0.5)/half(0.75)，高 half 可继续进入 162 已证的 see-through 消费。这个演算说明索引一致性的必要条件，不是原游戏分配、GPU 数据或实际画面验证。

| 问题                                                               | 本轮状态                                         |
| ------------------------------------------------------------------ | ------------------------------------------------ |
| Prefab 变化后更新 Placement staging                                | 已回答：专门化调用、48 B 拷贝与 dirty 范围       |
| Placement staging→buffer 更新请求→材质 buffer                      | 已回答静态 CPU 链：vtable/同对象+0x18/raw handle |
| 树冠/树干 subset→专用 shader、材质和 callback                      | 已回答有条件注册/录制链；运行开关未知            |
| vertex 的实例取数地址与 anim 成员                                  | 已回答首 vertex 变体：二级索引与48 B布局         |
| 某树→裁剪/排序输出→最终 draw slot/firstInstance                    | 未闭合；不是负面证明                             |
| native layout B、最终 descriptor backing 与 +0x280/+0x388 API 名称 | 部分回答；不可由表偏移加法补证                   |
| 游戏、GPU、Unity、画面、性能和 SPIR-V 语义验证器                   | **Not Run**                                      |

正式 probe 实际运行 **Passed**：31 个 native 字节锚点、11 个 direct-call 目标、两类 subset 的三组索引表、Placement vtable 和两份首 vertex 的 def-use/布局锚点均匹配；最终输出 `proof-final.json`。首次验证发现 shader 包实际为四模块，修正覆盖声明后通过；不能据首 vertex 的通过给其他变体或运行帧发通行证。PDB 的宽候选查询有达到上限的清单，最终类型/调用结论使用后续 exhausted 的窄查询及反汇编核对，不把宽列表称为完整枚举。未进行工程构建、安装和 Git 提交。

下一项最有价值的静态入口是：沿 `gpu_generate_draw_lists` 的通用 buffer owner，把生成阶段的 indirection 写句柄接到树 pipeline 的 `nani_instance_indirection` 绑定，同时核对树类别对应的 `firstInstance` 与命令子列表；再接 layout B 的反射/组解析。若未来授权运行，最小接受证据应是在自己构造的单棵手放树场景追同一 dense slot、两类 subset、两份 descriptor 与 indirect-command `firstInstance`，并观察参数改变如何影响最终颜色/深度。当前授权只有静态，不为补这个缺口启动或附加。

适合我方的独立设计规格是：保留唯一实例状态和稳定身份，将可见列表显式表示为 dense-slot 间接索引；材质绑定从实例池 owner 取得同一 buffer；局部 dirty 范围只负责更新请求，绘制与可见性单独验证。自研按自身产品需求独立实现，不带入原作资产、恢复代码或未核实的类别/容量常量。
