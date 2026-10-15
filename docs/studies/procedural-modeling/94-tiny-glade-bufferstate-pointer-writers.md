# Tiny Glade：BufferState 指针写端与槽 23 的剩余边界

承接 [87](87-tiny-glade-final-command-backing-and-writers.md)、[89](89-tiny-glade-other-command-writers.md)、[90](90-tiny-glade-command-capacity-and-lifetime.md) 与 [92](92-tiny-glade-typed-buffer-replacement-and-final-range.md)。本轮从 `BufferState` 首 16 B 的实际写入和状态分支复查同一 `DrawIndexedIndirectBuffer` 项。**已定位的本类型写入仍是创建时把新 typed 对象及 vtable 放入新项；图读写和完成只改状态/图句柄，`export_from_rg` 只清状态；具名 `HashMap::get_mut` 的两个直接调用是另一种名称键缓冲。**另一类型 `NaniDrawListSsbo` 确有旧项内指针/vtable 写回，但其键和 vtable 与本类型不同。未发现本类型图使用前取得新 raw handle 的连通路径，因此不能从这些入口推出 480 B 容量或槽 23 的四个非动态计数字段；这仍是限定静态结论，不是全程序无写者证明。

## 身份、方法和可复查原始记录

只读目标为 `C:\Software\Steam\steamapps\common\Tiny Glade\tiny-glade.exe`（65,612,184 B）和同目录 `tiny_glade.pdb`（310,513,664 B）；本轮复核路径及长度，未计算新摘要。下文地址均是 EXE preferred VA，非运行地址。使用已有 `docs/studies/procedural-modeling/digging-a-hole/tools/pdb_probe.py` 的 PDB 名称结果、VS2022 14.44.35207 `dumpbin /DISASM:NOBYTES /SECTION:.text /RANGE:0x...,0x...`、既有有界 `.text` RIP-relative `lea` / `E8 rel32` 候选扫描；跳表目标按实际 PE `.rdata` section 的 VA→文件偏移转换及有符号 32 位相对项解析。这里的静态文件不是 REA MCP Evidence。既有 Ghidra 超时状态没有变化，也没有重试。

新原始记录在本机忽略目录 `.cache/procedural-modeling/static-bufferstate-followup/tiny-glade/`，包括四份 `0x*.json` 候选引用、`export-jumptable.json`、`export-call-{a,b}.txt`、`get-mut-call-{a,b}.txt`、`typed-{add,read,write,write-tail,finish,finish-read}.txt`、`nani-replace-writer.txt`。`decode_jump.py` 仅为本轮原始表解码辅助；正式结论以下述指令边界为准。`.text` 候选扫描覆盖 RVA `0x1000`、48,438,272 原始字节，候选由定点反汇编核对；它不覆盖间接调用、其它模块或所有内联写入。

## 同一个项的字段、写入和状态

`BufferState::new` VA `0x14090E410` 在 `0x14090E418/41B` 写结构 `+0/+8` 两个 qword，并初始化锁及 `+0x28=0`。本类型 `add_new<DrawIndexedIndirectBuffer>` VA `0x141542760` 是更直接的同键实例：`0x141542780–782` 以空数据创建 typed storage buffer；`0x1415427AB` 把返回的 raw handle 装进新 typed 对象，`0x1415427C1–7CC` 准备其 boxed 数据指针及 vtable，`0x14154280C–828` 将这两个 qword 搬入新分配的 0x48 B `BufferState`，然后 `0x14154283B` 用键插入。初始底层描述符为 460 B 的链见 [90](90-tiny-glade-command-capacity-and-lifetime.md)。这是**构造新项**，不是已有项里把 460 B 换成 480 B。

对 `BufferState::new` 的七个 `.text` 直接调用候选，经 PDB 函数边界定位，分别在 `0x1421608F0–0x1421612B0` 的七个 `add_existing` 特化中（Gate/Halftimber/WoodenWall/SlotWallId/StoneFoundation/Wall/RoofColorId），无本类型调用。它们是其它 typed 项的构造路径；本类型的构造已在上述 `add_new` 内联完成。该直接调用清单仍不涵盖所有内联实例。

为核对“没有改外层Box、却由虚调用换内部raw handle”的具体疑点，本轮再从构造的 `0x1415427C5` 实际RIP-relative LEA 解出 vtable `0x14331C5E8`（`.rdata`，文件偏移 `0x331B5E8`）。表的 `+0x28` 实字为 `0x1406D0830`；定点反汇编只有 `mov rax,rcx; ret`。write入口 `0x14152B754–75F` 经该槽返回当前typed对象地址后，直接读取该地址的首qword作为raw handle，再交给import_mut。故在本构造vtable保持不变的条件下，**这一取句柄虚调用本身不分配、不改写typed对象，也不替换raw handle**。PDB在共享代码地址显示GardenRaster的Deref名称，不能用该名字改变由构造vtable和调用参数证实的接收者身份。表的 `+0x18/+0x20` 均指向 `0x141B18270`，现有 `as-any-typed.txt` 表明它返回对象地址与Any表；这不排除其它消费者之后通过可变别名写入。新原始投影为 `typed-vtable-slots.json`、`typed-buffer-getter.txt`，`decode-typed-vtable.py` 是本轮一次性解码记录。

`FrozenMap::insert` 的已证重复键分支销毁新传入 box、返回旧项；本类型 `add_new` 的 `0x141542840–846 → 0x141542875` 对这一结果走 panic，见 [92](92-tiny-glade-typed-buffer-replacement-and-final-range.md)。作为真正旧项写回的对照，`replace_with_data<NaniDrawListSsbo>` VA `0x141533320` 的已有键分支在 `0x141533589–5BC` 析构旧对象，随后 `0x1415335C1–5D7` 将新指针和 `0x14331B820` vtable 写回原项 `+0/+8`，`0x141533617` 清状态。此函数的输入类型、vtable 和键都不能自动转借给 `DrawIndexedIndirectBuffer`。

本类型 `0x14331C938` 的 `.text` RIP-relative `lea` 候选为六处：`0x1415281B4/8218`（read）、`0x14152B6E2/B73B`（write）、`0x141535A9A`（finish read）、`0x141539C98`（finish write）。实际 read 在 `0x141528231–259` 经现有项的虚方法取 raw handle 并导入图，`0x141528269–285` 写项 `+0x28=1` 及图句柄/读者数；write 在 `0x14152B754–777` 同样读既有项并 `import_mut`，`0x14152B786–79E` 写 `+0x28=2` 及图句柄。`finish_read` 的 `0x141535AE3–B27` 将读者数减至零时 export，再于 `0x141535B27` 清状态；`finish_write` 的 `0x141539CDE–D0F` export 并清状态。这四个同键函数所见的指针/vtable `+0/+8` 是**读取**，可写字段位于 `+0x28` 以后。图导入 tag3 保留原 raw handle 的条件链仍见 [87](87-tiny-glade-final-command-backing-and-writers.md)。

`AssetSsboLibrary::export_from_rg` VA `0x14090E440` 遍历容器项，`0x14090E4CC` 得到 boxed `BufferState`，`0x14090E4FB–515` 读取旧状态、写 `+0x28=0` 并以 `0x14301F868` 跳表分支。按四个索引实际表项：状态 0、3 到 `0x14090E517` 释放锁并继续；状态 1 到 `0x14090E5A7`、状态 2 到 `0x14090E5DD`，均是 panic 路径。函数的直接调用候选 `0x140588AC7`、`0x14058B9D6` 位于图完成链；两个调用点都向该库传图上下文，没有向该函数传新 typed 对象或新 raw handle。在这个函数的可达正常分支没有 `+0/+8` 写入、BufferDesc 构造或槽 23 命令字段写入。这个遍历会检查容器项，但不能仅凭它证明目标项在某帧存在或具体状态为何。

PDB 的具名 `hashbrown::HashMap::get_mut` VA `0x141F12E60` 容易被误接成 `SsboId → BufferState` 写者。其函数体 `0x141F12EF6` 实际调用 `NameHash::eq`，两个已定位直接调用 `0x140FE09BB`、`0x141F350AB` 都传同一个 `anon.ce0c...` 名称键；命中后经值的虚方法，再调用 `SparseInstanceBuffer::gpu_flush`（`0x140FE09F0`、`0x141F350E0`）。两处附近没有 `0x14331C938` 的加载，也没有 `BufferState +0/+8` 写回。这个具名泛型/合并代码地址不能替代同键数据流证明。

## 容量和四字段的条件算例

沿用 [89](89-tiny-glade-other-command-writers.md) 的模板：槽 22 的 20 B 区间 `[440,460)` 可得到 `[count=18, instanceCount=0, firstIndex=0, vertexOffset=0, firstInstance=0]`；墙 compute 若随后对其计数加一，条件结果为 `[18,1,0,0,0]`。槽 23 位于 `[460,480)`，在这份 23×20 B 模板和已定位的 460 B 初始描述符之外。仅有图句柄状态更新、原 raw handle 的 tag3 导入、或 `update_buffer_bytes` 的暂存 buffer 创建，均不产生槽 23 的 `count/firstIndex/vertexOffset/firstInstance`。`update_buffer_bytes` 还按目标 raw 记录 `+0x320` 的原大小限制写入，见 [92](92-tiny-glade-typed-buffer-replacement-and-final-range.md)。

假设将来证实另一入口在图导入**之前**把本项换成新 raw handle，则还需逐跳证明新 `BufferDesc` 的低 32 位请求长度至少 480、对应资源记录 `+0x320` 至少 480、图记录绑定这个新 handle，并找到槽 23 四字段的写者及顺序。本轮所查入口没有产生这样的新 handle，因此没有可追踪到新描述符的事实边；不能把“未见替换”写成“最终必为 460 B”。同理，槽 23 shadow draw 的结构条件见 [87](87-tiny-glade-final-command-backing-and-writers.md)，本轮没有证明实际执行、有效绘制或运行越界。

**状态。** 已定位 `BufferState` 构造写端、其它类型的实际旧项替换写端、目标 typed key 的四组读写/完成、`export_from_rg` 状态跳表以及两个误导性的 `get_mut` 调用，为 **Answered（静态、限定范围）**。目标项所有潜在间接/内联替换、最终 raw backing 容量、槽 23 四字段和具体帧顺序为 **Partial/未知**。目标启动/附加、GPU、私人存档及运行观察均 **Not Run**。
