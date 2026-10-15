# Tiny Glade：可变别名与 typed raw handle 的静态边界

承接 [89](89-tiny-glade-other-command-writers.md)、[90](90-tiny-glade-command-capacity-and-lifetime.md)、[92](92-tiny-glade-typed-buffer-replacement-and-final-range.md) 和 [94](94-tiny-glade-bufferstate-pointer-writers.md)。本轮优先追 `DrawIndexedIndirectBuffer` 的 `as_any_mut`、`TypeId` 和对象内部首 qword。**实际定位到的首 qword 写入仍是新 typed 对象的构造写入；没有找到可变别名消费者把另一 raw handle 写回该对象。**因此 460 B 是已证的初始底层请求长度；图使用前是否另有更大 raw backing、槽 23 的四个非动态计数字段，仍为 **Unknown**。这是有界静态结果，不是全程序无写者证明。

## 目标、方法和原始记录

只读发行文件 `C:\Software\Steam\steamapps\common\Tiny Glade\tiny-glade.exe`（65,612,184 B）及同目录 `tiny_glade.pdb`（310,513,664 B），本轮复核路径及长度，未计算新摘要。下文为 EXE preferred VA。PDB 名称用既有 `digging-a-hole/tools/pdb_probe.py` 查询；指令用 VS 14.44.35207 的 `dumpbin /DISASM:NOBYTES /SECTION:.text /RANGE` 核对；`.rdata` 表项按 PE section 映射读取。既有 Ghidra 超时状态无变化，未重试。这些本地文件不是 REA MCP Evidence。

新原始记录在本机忽略目录 `.cache/procedural-modeling/static-alias-followup/tiny-glade/`：`draw-indexed-symbols.json`、`typed-as-any.txt`、`typed-buffer-mut.txt`、`typed-write-get-handle.txt`、`any-type-id.txt`、`any-table.json`、`rip-candidates.json`、`typeid-immediate-candidates.json`、`as-any-call-refs.json`、`type-id-call-refs.json`、`any-vtable-lea-refs.json`、`tuple-fetch.txt`、`take-rg-sample.txt`、`rg-state-closure.txt`。其中三个 `*.py` 是本轮一次性原始记录辅助，不是正式工具。扫描 `.text` 原始区间 RVA `0x1000`、48,438,272 B，按 RIP 相对 32 位位移匹配三个精确目标，再用反汇编确认候选；另对 TypeId 两个 64 位小端常量分别找精确原始字节。直接 `E8` 和 `lea` 清单使用既有扫描器。这些扫描不覆盖其它模块、运行生成代码、间接调用或由传入指针形成的普通内存 store。

## 可变 Any 别名：表与类型标识已定位，写者未连通

由 [94](94-tiny-glade-bufferstate-pointer-writers.md) 的本类型构造指令 `0x1415427C5` 解出的 `StorageBufferDyn` vtable 为 `0x14331C5E8`。其 `+0x18` 与 `+0x20` 都指向 `0x141B18270`；本轮 `typed-as-any.txt` 确认该函数只做 `mov rax,rcx; lea rdx,[0x14338E838]; ret`。所以 `as_any` 和 `as_any_mut` 都能把**同一 typed 对象地址**交给后续消费者，返回的 Any 表为 `0x14338E838`；函数自己没有分配或写首 qword。

`any-table.json` 从 `.rdata` 文件偏移 `0x338D838` 读出此 Any 表：`+0` 为目标 typed 析构 `0x14096A3C0`，`+8/+0x10` 各为 `8`，`+0x18` 为 `0x141B1DA70`。`any-type-id.txt` 在 `0x141B1DA70–7D` 明确标为 `TypedStorageBuffer<DrawIndexedIndirectBuffer>` 的 `core::any::type_id`，并从 VA `0x14338EC38` 装入 16 B TypeId 字面量。这比单凭 `as_any_mut` 的 PDB 名称更具体：若有调用者经该 Any 表下转型，它具有识别这一类型的表项；**仍须找到调用者和其后续 store** 才能认定对象被改写。

本轮对上述 Any 表、TypeId 字面量和 `StorageBufferDyn` vtable 的 `.text` RIP 位移候选各找到一处：`0x141B18273` 加载 Any 表，`0x141B1DA73` 加载 TypeId 字面量，`0x1415427C5` 加载 typed vtable。16 B TypeId 字面量在整个 EXE 原始字节中只出现于 `.rdata` 文件偏移 `0x338DC38`。再以该 128 位 TypeId 的两个 64 位小端值 `282c06ad2f2710a0`、`7d6946dca37e6926` 搜索整个 `.text`，各为 **0 个精确字节候选**；因此没有可进一步定点核对的 `movabs`/64 位立即数配对。对 `0x141B18270` 和 `0x141B1DA70` 的精确 `.text` 直接 `E8` 调用候选均为零。它们正常也可通过 vtable **间接**调用；编译器还可能拆成 32 位或计算生成比较值。这些阴性清单仅说明本轮没有找到静态直连下转型/改写边，不证明绝无可变别名消费者。

PDB 对 `*DrawIndexedIndirectBuffer*` 枚举 12/12 名，包含目标 `add_new`、图读写/完成、tuple `fetch`、`new_storage_buffer`、Any/type-id 实现和一个报错闭包；没有具名的目标 `replace_with_data` 或 `take_rg_buffer` 特化。目标 typed key `0x14331C938` 的六处 `.text` `lea` 已由 [94](94-tiny-glade-bufferstate-pointer-writers.md) 定位在 read/write/finish 四类入口；它们取得外层项后所见是图句柄状态或 raw handle 的读取。额外核对 `fetch<ref_mut<DrawIndexedIndirectBuffer>,…>`：`0x140A92089` 调目标 `write_rg_buffer`，`0x140A9212A` 起复制返回的图句柄到 tuple 输出，而非传出 typed 对象的可变别名。抽查另一类型 `take_rg_buffer` 的 `0x1405E13AC–CF` 也走 vtable `+0x28` 取 raw handle 并导入图；它不是目标特化。PDB 枚举和这两个局部反汇编不能排除内联或类型擦除消费者。

## 首 qword 的真实写入和容量含义

目标构造 `add_new` 的 `0x1415427AB` 是已证的 `mov qword ptr [rax],rdi`：`rdi` 是前一步 `new_storage_buffer<DrawIndexedIndirectBuffer>` 返回的 raw handle，`rax` 是**新分配 typed 对象**。其后 `0x1415427C1–CC` 把该对象地址及 vtable 装箱，`0x14154280C–828` 再形成新 `BufferState` 项。此处不是旧项或旧 typed 对象的重写。[90](90-tiny-glade-command-capacity-and-lifetime.md) 已将这次 `new_storage_buffer` 的空数据分支和底层描述符接到 460 B 请求。

同一 vtable 的 `+0x28=0x1406D0830` 在 `typed-buffer-mut.txt` 中只有 `mov rax,rcx; ret`；它返回对象地址，**不是 setter**。目标图写入口的 `0x14152B754–75F` 先从旧项取对象及 vtable，经 `+0x28` 返回地址，再于 `0x14152B75F` 读 `qword ptr [rax]`，作为 raw handle 传 `import_mut`。这个读端意味着：若别处真的改了首 qword，后续图导入会读新值；本轮没有找到那条先行写入及其新描述符。`StorageBufferDyn` 这张表的两个 Any 槽与一个返回对象地址的 buffer 槽都不自行扩容。

条件演算：已证初始化请求 `23×20=460 B`；槽 22 占 `[440,460)`，静态模板为 `[count=18, instanceCount=0, firstIndex=0, vertexOffset=0, firstInstance=0]`，见 [89](89-tiny-glade-other-command-writers.md)。槽 23 占 `[460,480)`。若图导入仍读这次构造的 raw handle，且底层资源未变，槽 23 超出**已证请求长度** 20 B；若另有未定位的别名 store 换入至少 480 B 的资源，容量条件可能改变，但仍须逐跳确认新 `BufferDesc`、raw 资源记录 `+0x320`、图绑定时间，并另找槽 23 的 `count/firstIndex/vertexOffset/firstInstance` 写端。`update_buffer_bytes` 的目标范围由现有记录 `+0x320` 限制，[92](92-tiny-glade-typed-buffer-replacement-and-final-range.md) 的暂存区分支也不能自行扩容。此算例没有证明实际帧的替换、GPU 执行、有效绘制或越界。

## 后续入口与停止条件

1. **容量链的新入口：**从 `GraphicsDevice::create_buffer_impl` 写 raw 资源记录 `+0x320` 的路径和 raw handle 生命周期出发，核对这次 460 B 创建后是否有同一 handle 的记录替换或重绑定。价值是把“初始请求 460 B”与图导入时的资源记录大小联系起来；缺口是目前未追完 handle 身份与重建先后，不能只比较数值。
2. **槽 23 消费链的新入口：**从已定位的墙阶段 3 / 组号 1 draw 调用和 `draw_indirect` 的偏移传递继续到设备虚槽及边界检查，核对 `[460,480)` 在静态提交路径如何被解释。价值是明确条件可达路径的资源范围处理；缺口仍是帧门控、实际 GPU 提交和槽 23 四字段内容，纯静态调用链不能补成运行观察。

本轮 Any 表、TypeId 常量、目标具名特化与已定位 key 的直连静态入口已查到可复核边界。除非出现**新的具体调用者、首 qword store 地址或不同制品身份**，不应再对同一批地址反复做 PDB 名称与 `.text` 引用扫描；应保留 `Unknown`。目标启动/附加、目标函数或 GPU 执行、私人存档读取、安装及鼠标操作均 **Not Run**。
