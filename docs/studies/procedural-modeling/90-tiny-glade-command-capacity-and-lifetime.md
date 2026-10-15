# Tiny Glade：命令缓冲初始容量与最终容量的静态挑战

承接 [81](81-tiny-glade-command-initialization-and-slot23.md)、[83](83-tiny-glade-slot23-write-growth-and-submission.md)、[85](85-tiny-glade-wall-bucket-and-command-writes.md) 和 [87](87-tiny-glade-final-command-backing-and-writers.md)。本轮确认：**已定位的实际 `AssetSsboLibrary::add_new<DrawIndexedIndirectBuffer>` 调用会传空数据，创建的底层 buffer 请求长度确为 460 B；不能把这 460 B 仅解释为一个从未使用的默认分支。** 非空数据分支也固定构造 460 B 描述符，允许的完整 20 B 记录最多 23 条。图导入句柄的 20 B 宽度和设备内存分配对齐均不是命令 buffer 扩容证据。若该原始 raw handle 一直存活且没有被替换或改变底层资源，槽 23 要求的 `[460,480)` 不在这次创建的逻辑范围内；**完整后续生命周期、图执行和实际墙 draw 仍未穷尽，不能宣称最终必为 460 B、发生越界或有效绘制。**

## 身份、方法与原始记录

沿用 [81](81-tiny-glade-command-initialization-and-slot23.md) 已核对的 `C:\Software\Steam\steamapps\common\Tiny Glade\tiny-glade.exe`（65,612,184 B）和同目录 `tiny_glade.pdb`，本轮只核对路径与文件长度，未重算摘要。EXE 地址均为 preferred VA。用仓库 `docs/studies/procedural-modeling/digging-a-hole/tools/pdb_probe.py` 的 DbgHelp 本地 PDB 查询与 VS2022 `dumpbin /DISASM /RANGE:0x...,0x...` 读取现有发行文件；这是普通静态原始输出，不是 REA MCP Evidence。未启动、附加或执行目标，未读私人存档，未抓 GPU，也未重试此前无状态变化的 Ghidra 超时。

本轮原始目录为 `.cache/procedural-modeling/static-other-writers/tiny-glade-capacity/`：`capacity-symbols.json`、`graph-range-symbols.json`、`new-storage-buffer-full.txt`、`creator-call.txt`、`bufferdesc-new.txt`、`buffer-import-read.txt`、`rg-bufferdesc-new.txt`、`read-typed.txt`、`indexed-indirect-drawfn.txt`、`draw-indirect.txt`。复用 `.cache/procedural-modeling/static-tail-followup/tiny-glade/` 的 `creator-caller.txt`、`add.txt`、`update-byte-calls.json`，及 `.cache/procedural-modeling/static-final-followup/tiny-glade/` 的 `create-buffer-typed.txt`、`create-buffer-impl.txt`、`import-mut.txt`、`registry-import-dispatch.json`。PDB 查询 `*DrawIndexedIndirectBuffer*` 12/12、`*BufferDesc*` 18/18、`*GraphImportable*` 9/9、`*indexed_indirect*` 5/5、`*GraphApi*buffer*` 114/114 均穷尽；`*AssetSsboLibrary*` 扫过 3002 个名字并按本轮正则保留 106 个，查询也穷尽。名字枚举不能排除内联、类型擦除或动态分派。

## 实际调用确实选择空输入

| 边             | 指令事实                                                                                                                                                                                                                                     | 解释                                                                                    |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 创建调用点     | 资源建立函数的 `0x140B7F5CD–D7` 从设备结构取指针、加 `0x10`，然后调用 VA `0x141542760` 的 `add_new<DrawIndexedIndirectBuffer>`；这段连续建立不同 typed SSBO，见 `creator-call.txt` 与既有 `creator-caller.txt`。                             | 这是已定位的该 typed 特化直接调用点；函数是否在某次具体运行中成功走到这里仍属运行条件。 |
| `add_new` 传参 | `0x14154277D` 将设备指针给 `rcx`；`0x141542780` 执行 `xor edx,edx`；`0x141542782` 调 `new_storage_buffer<DrawIndexedIndirectBuffer>` VA `0x141B138C0`；成功返回的 raw buffer 在 `0x1415427AE–83B` 进入 typed `FrozenMap`。见既有 `add.txt`。 | `rdx=0`，因此实际这一创建调用必选被调函数的空输入分支，调用者并未递交另一个非空 `Vec`。 |
| 空输入创建     | `0x141B138E0–E3` 测 `rdx` 并跳至 `0x141B1393E`；`0x141B13943–55` 分配 0x1CC B 零数据，`0x141B13961` 设记录数 0x17；`0x141B1396E–7A` 构造 0x1CC B `BufferDesc`；`0x141B13996–C9` 传 23×20=460 B 初值。见 `new-storage-buffer-full.txt`。      | 初始 payload 全零，槽 0…22 各 20 B；槽 23 的首字节从偏移 460 开始。                     |

反例挑战：若某个其他调用以非零 `rdx` 进入同一 `new_storage_buffer`，`0x141B138E8–15` 要求 `r8` 长度为 20 的倍数；`0x141B1392C–33` 拒绝 `r8>0x1DF=479`。所以能通过的非空完整记录最长仍是 460 B。两支随后共同在 `0x141B1396E` **固定**以 460 B 建描述符；非空分支只改变初值指针和 `rdi=r8/20`，不令描述符变为 480 B。这排除“该函数的非空输入可以给第 24 条命令预留空间”的解释，不排除之后由别处创建或替换另一 buffer。

## 460 B 到底层创建，不是仅仅 CPU 零数组

`BufferDesc::new` VA `0x140E1D1F0` 在 `0x140E1D202–17` 把 `rcx` 的低 32 位放在返回打包字低位，另外组合 flags；该调用的 `rcx=0x1CC`。`GraphicsDevice::create_buffer` VA `0x1415D1D50` 在 `0x1415D1D9B–AF` 读取该打包描述符；`0x1415D1E24–36` 将它与初值指针、长度一同传给 `create_buffer_impl` VA `0x140E547F0`。`create_buffer_impl` 在 `0x140E5481F` 从第六栈实参取得打包字，`0x140E54855` 取其低 32 位为 `r8d`，并于 `0x140E54887/8B` 两次写入创建信息局部结构；随后 `0x140E548A9–BE` 把该结构交给底层 buffer 创建调用。因而这次底层 buffer **请求大小是 460 B**，不是只上传了 460 B、描述符却预留 480 B。证据见 `bufferdesc-new.txt` 及既有 `create-buffer-typed.txt`、`create-buffer-impl.txt`。

同一个 `create_buffer_impl` 后面还为设备内存计算和分配大小（如 `0x140E5499B–D7` 的最大值和 `0x140E54A13–49` 的分配调用）。那是物理内存需求/对齐的另一尺度，不能拿较大的内存块证明 buffer 的逻辑可读字节超过创建描述符。尤其 `r13` 在 `0x140E5497F` 已右移 56 位，不能把 `0x140E54C77/7F` 写入返回结构的 `r13` 误读为原始 460 B 大小。尚未把原 raw registry 记录所有字段和底层 API 的最终使用范围全部解码。

## 图句柄范围及后续生命周期边界

`write_rg_buffer<DrawIndexedIndirectBuffer>` 仍按 [81](81-tiny-glade-command-initialization-and-slot23.md) 的 typed 键在 `0x14152B754–777` 取得同一 raw handle 并调用 `GraphImportable::import_mut`。该函数 `0x140E1E267–293` 从 raw 记录取值传给 `GraphRecord::import_mut`；`0x140E1E2BF–C9` 给返回的 20 B **图句柄**的 `+8` 写 `0xFFFFFFFF00000000`。只读导入 `GraphImportable::import` 在 `0x140E1E517–579` 也写同一个值；typed `read_rg_buffer` 在 `0x141528259` 调它。这个 `+8` 低 32 位是 0、高 32 位全 1，至少不能解释为“图句柄为 20 B，所以命令多出 20 B”或直接作为 480 B 容量。通用 `RasterStreamRecorderWithPipeline::draw_indirect` 在 `0x140E24D41–5D` 从句柄 `+8` 取低 32 位并与调用者字节偏移相加；它使用的是视图偏移，不负责底层容量增长。此通用函数仅说明句柄布局的一种消费，墙专用槽 23 的 460 B draw 偏移仍以 [79](79-tiny-glade-draw-command-slot-provenance.md) 的绑定证据为准。

[87](87-tiny-glade-final-command-backing-and-writers.md) 已把同一 raw handle 的导入记录接到注册器 tag3，证明在该分派状态下保留原 handle、不走通用 pool 分配。本轮的 460 B 创建证据使其条件后果更明确：**若之后始终使用这次创建的 raw buffer，且没有其他接口改变其底层资源或注册表项，槽 23 的 20 B 区间 `[460,480)` 超过创建请求 20 B。** 但本轮没有穷尽构造后的所有 typed entry 改写、raw handle 替换、图资源变化或时间性更新，也没有证明具体 shadow 条目通过所有门控并执行该 draw。PDB 中未见具名 `replace_with_data<DrawIndexedIndirectBuffer>` 或 `add_new_with_data<DrawIndexedIndirectBuffer>`，其否定范围仅限具名特化；既有 `update-byte-calls.json` 的通用 byte-update 调用点尚未逐一关联到同一 handle。不能因此把“若保持原 handle”升级为“最终必保持 460 B”。

构造例子：在 `add_new` 成功且此 raw buffer 被图导入、tag3 保留的前提下，槽 22 占 `[440,460)`，槽 23 占 `[460,480)`。若图执行前确实发生一次同键替换，新 buffer 的描述符为 480 B，则槽 23 **容量条件**可满足，但四个非计数字段是否有有效值仍须另证；若没有替换，这次 460 B 创建本身不提供槽 23 的任何字节。这里的 480 B 替换是待验证的反事实输入，并非观察到的目标行为。

**状态。** 实际 `add_new` 进入空输入、非空分支上限、打包描述符低 32 位到 460 B 底层创建信息、图句柄 `+8` 不构成扩容，为 **Answered（静态）**。该 typed/raw buffer 的全生命周期、最终逻辑容量、槽 23 四字段生产者及运行时提交，为 **Partial/未知**。游戏、GPU 与实际运行结果 **Not Run**。下一条最有判别力的静态边是定位同一 typed entry 或 raw registry 记录在图编译/执行前的所有替换入口，追踪新描述符及 handle；若无该闭包，只能把最终容量保留为严格条件结论。
