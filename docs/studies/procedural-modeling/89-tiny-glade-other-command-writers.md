# Tiny Glade：同一间接命令缓冲的完整模板写端

承接 [79](79-tiny-glade-draw-command-slot-provenance.md)、[81](81-tiny-glade-command-initialization-and-slot23.md)、[83](83-tiny-glade-slot23-write-growth-and-submission.md)、[85](85-tiny-glade-wall-bucket-and-command-writes.md) 与 [87](87-tiny-glade-final-command-backing-and-writers.md)。本轮从**同一 typed `DrawIndexedIndirectBuffer` 写句柄**反查，找到了此前缺失的另一条四字段生产路径：`reset_indirect_args` 将一张 23×20 B 的静态完整命令表复制进暂存区，建立带两个 buffer 资源访问的图节点；其录制回调对第二个资源发起设备操作，第二个资源索引逐跳来自该 typed 写句柄。静态表的槽 0…22 均为 `[count, 0, 0, 0, 0]`：相对于动态 `instanceCount`，它**提供非零或零的 `count`，并提供值为零的 `firstIndex`、`vertexOffset`、`firstInstance`**。表不含槽 23；其 `[460,480)` 四字段来源及实际可用 backing 长度依旧未知。图节点是否在某帧执行、设备虚调用的具体底层实现与 GPU 完成均未观测。

## 输入、坐标和证据边界

复用 [81](81-tiny-glade-command-initialization-and-slot23.md) 已核对的发行 `C:\Software\Steam\steamapps\common\Tiny Glade\tiny-glade.exe`（65,612,184 B）及同目录 `tiny_glade.pdb`，没有重算摘要。EXE 地址均是 preferred VA；静态表另给 PE 原始文件偏移。只用本地 PDB、PE 字节和 VS2022 `dumpbin /DISASM /RANGE`，没有运行或附加游戏、执行目标函数/GPU、读取私人存档、安装工具或控制鼠标。REA native Ghidra 既有超时阻塞未变，本轮未重试；以下是**普通静态原始文件**，没有新 REA MCP Evidence ID。

新增原始证据位于 `.cache/procedural-modeling/static-other-writers/tiny-glade-fields/`：`reset-symbols.json`、`reset-callers.json`、`reset-compile-caller.txt`、`write-1409ea9d5-head.txt` / `write-1409ea9d5.txt` / `write-1409ea9d5-tail.txt`、`reset-set-callback.txt`、`reset-callback.txt`、`reset-static-table.json`，以及 typed key / read / write / finish-write、通用更新函数的限定直接引用清单 `*-refs.json` 和 11 个写租约调用点的 `write-*.txt`。PDB 精确掩码 `*reset_indirect_args*` 为 6/6、已枚举完毕。三个小脚本 `scan_refs.py`、`decode_command_table.py`、`resolve_addrs.py` 仅在这个 ignored 原始证据目录内；最后一个 DbgHelp `SymFromAddrW` 返回 error 126，**未**用于得出函数所有权结论。`scan_refs.py` 在 PE `.text` 原始区间 RVA `0x1000`、48,438,272 B 搜索精确 RIP-relative `lea` 和 `E8 rel32` 候选；每项仍由限定反汇编核对指令边界。该扫描不覆盖间接调用、别名、JIT、其它模块或所有未具名 shader，阴性结论不可扩成全程序穷尽。

## 同一 typed 资源如何收到这张表

| 连接             | 原始指令事实                                                                                                                                                                                                                                                                                                                                                                                                                              | 解释限制                                                                                                                                                          |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 构图调用         | `rhapsody::rg::compile` 的 `0x14058752B–535` 传 `GraphApi` 与库参数，直接调用 `reset_indirect_args` VA `0x1409EA890`；`.text` 精确 `E8` 扫描仅找到此一直接调用。`reset_indirect_args` 在 `0x1409EA8B6–BE` 要求参数 `+0x88 != 0`，否则跳过。                                                                                                                                                                                               | 证明构图路径和门控，不证明每帧执行或某次图成功提交。                                                                                                              |
| typed 身份       | `0x1409EA9C3` 先取得另一 typed 写句柄，`0x1409EA9D5` 调用已由 [79](79-tiny-glade-draw-command-slot-provenance.md) 以同一 `FrozenMap` 键证明的 `write_rg_buffer<DrawIndexedIndirectBuffer>` VA `0x14152B6C0`；其 20 B 返回值被保存，`0x1409EAC12` 从此返回值末个 dword 取第二个图资源索引。                                                                                                                                                | 此处不是同样 20 B stride 的 `NaniDrawListSsbo`。图句柄的 20 B 与命令记录的 20 B 是两种对象。                                                                      |
| 460 B 表来源     | `0x1409EAAE4` 为第二次 `DynamicConstants::allocate` 提供 `r9d=0x1CC`；检查结果长度为 460 B 后，`0x1409EAB05–12` 从 `.rdata` VA `0x143032538` 向该暂存内存 `memcpy` 460 B。PE `.rdata` 映射的原始文件偏移是 `0x3031538`，`reset-static-table.json` 将该确切范围按 23×5 个小端 u32 解码。                                                                                                                                                   | 这是完整模板来源，不是创建时零 payload，也不是另一 Nani shader 模板。`memcpy` 本身写的是动态暂存内存，不能单独说已写入 GPU backing。                              |
| 图访问及回调     | `0x1409EAB80` 建图节点；`0x1409EAC0C`、`0x1409EAC64` 对两个图资源登记访问。`0x1409EACA2–DC` 将两份暂存描述符和两个资源索引放进回调闭包；`0x1409EAD02` 调 `NodeBuilder::set_render_callback`。该特化在 `0x14177B1A4–BE` 复制 48 B 闭包并将执行入口设为 VA `0x141A88AC0`。                                                                                                                                                                  | 两资源的顺序由闭包字段位置连接，不由 shader 名字猜测。图访问登记仍非执行观测。                                                                                    |
| 第二资源设备操作 | 回调 `0x141A88B0D–18`、`0x141A88B91–BC1` 先后对闭包 `+0x20/+0x24` 的索引调 `ResourceRegistry::buffer` 取得**目的** buffer；另对闭包里的暂存 `Buffer` 调 `Buffer::hot` 取得**源**句柄。第二次组装 `{srcOffset=闭包+0x2C, dstOffset=0, size=闭包+0x18}`，传 `rdx=源`、`r8=目的`、`r9d=1`、第五参数为该区域指针，调用命令接口虚槽 `+0x388`。上述闭包 `+0x24` 由 `0x1409EAC12/ACA9` 的第二图索引填入，`+0x18` 是第二次分配返回的 460 B 长度。 | 参数形状符合 Vulkan `cmd_copy_buffer` 的一段复制；虚槽目标尚未独立解析，故这是**静态可达的 460 B 复制录制路径**，不把设备实际完成、提交顺序或错误处理写成已观测。 |

这条连接修正了“同 buffer 已见 GPU 写入只有 `instanceCount`”可能造成的误读。[79](79-tiny-glade-draw-command-slot-provenance.md) 对墙目录七个 compute 的结论仍成立：那些 shader 的显式 `draw_commands` 写入只涉及槽 16…22 的 `instanceCount`。现在额外看到的 `reset_indirect_args` 是**CPU 静态模板经图回调/设备接口进入同一资源**，并非墙 compute 的新字段 store，也不证明 shader 自己写了 `count/firstIndex/vertexOffset/firstInstance`。

## 表的精确内容、有效范围和演算

`.rdata` 的 460 B 恰有 23 条 20 B 记录。逐条第一个 u32（`count`）为：

```text
slot       0   1  2  3 4  5 6  7   8 9 10   11   12 13  14 15  16 17  18 19 20 21 22
count    300  96 57 36 6 60 6 48 174 0  0 2817 4716 66 180 15 900 18 900 18 18 18 18
```

每条其余四个 u32 均为零，按已证布局分别是 `instanceCount`、`firstIndex`、`vertexOffset`、`firstInstance`。这里所追的“四个非动态计数字段”精确指 `count/firstIndex/vertexOffset/firstInstance`：**`count` 并非全零**。例如槽 16 的源表记录位于表内字节 `[320,340)`，五字段为 `[900,0,0,0,0]`；若该节点的第二设备操作确实先写入此表，然后 [79](79-tiny-glade-draw-command-slot-provenance.md) 的 pass2 在槽 16 对 `instanceCount` 原子加一且没有其它覆盖，它会变成 `[900,1,0,0,0]`。这只是带执行顺序和条件的演算，并非一帧观测。槽 22 在 `[440,460)`，其源值 `[18,0,0,0,0]`。槽 23 从 460 B 开始，需要 `[460,480)`；静态表和本次第二暂存操作的 460 B 长度均**不包含它**，不能推出 `[0,0,0,0,0]` 或任何有效命令。

| 绝对槽 | 此表 `count` | 此表另外四字段 | 已逐槽绑定的墙 compute `instanceCount` 写端 | [79](79-tiny-glade-draw-command-slot-provenance.md) 已见墙回调选择                                     |
| -----: | -----------: | -------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
|     16 |          900 | 全零           | prefix subtotal；pass2 reset/增量           | 阶段 0/1 可选                                                                                          |
|     17 |           18 | 全零           | pass2 reset/增量                            | 阶段 0/1 可选                                                                                          |
|     18 |          900 | 全零           | pass2 reset/增量                            | 阶段 0/1 可选                                                                                          |
|     19 |           18 | 全零           | pass2 reset/增量                            | 阶段 0/1 可选                                                                                          |
|     20 |           18 | 全零           | shadow 条件增量                             | 阶段 4、组号 2 可选                                                                                    |
|     21 |           18 | 全零           | shadow 条件增量                             | 所查墙回调未选择                                                                                       |
|     22 |           18 | 全零           | shadow 条件增量                             | 阶段 2、组号 0 可选                                                                                    |
|     23 |     **表外** | **表外**       | 所查墙 compute 无写者                       | 阶段 3、组号 1 可选；仍受 [85](85-tiny-glade-wall-bucket-and-command-writes.md) 的实体、首桶和绑定门控 |

表的 `count` 值是 `.rdata` 字节事实；右两列各沿用 [79](79-tiny-glade-draw-command-slot-provenance.md) 的独立绑定和回调证据，不把二者同时发生当作观测。尤其槽 23 的阶段 3 是结构上可达的**条件路径**，并非已证实际 draw 或运行越界。

[81](81-tiny-glade-command-initialization-and-slot23.md) 证明初始创建上传的 460 B 全零；那是**创建时间点**的槽 0…22。此处的表会在相关构图/执行条件成立时为同一范围提供非零 `count` 和四个零字段，所以初始零值不能当作之后的最终值，也不能扩展到未创建的槽 23。两份 460 B 的相等长度不构成 480 B 扩容证据。

## 其它候选与未闭合边界

对 typed key VA `0x14331C938` 的 `.text` RIP-relative `lea` 候选只有六处，分别落在 `read_rg_buffer`、`write_rg_buffer`、`finish_read_rg_buffer`、`finish_write_rg_buffer` 的已辨方法内；同一 `write_rg_buffer` VA `0x14152B6C0` 的 `E8` 候选有 11 处。定点反汇编确认其中一个是本轮完整模板节点，另有墙 pass2/shadow 调用 `0x1409BA1A2/0x1409BA735`、tuple `BufRef::fetch` 的 `0x140A92089`，其余是各自节点/资源绑定调用点，见 `write-*.txt`。这些 direct-call 清单帮助限定已查的 typed 入口，不排除句柄通过闭包、图资源表或间接调用传到其它写端。

通用 `GraphicsDevice::update_buffer_bytes` VA `0x140E55470` 的 `.text` 精确 `E8` 候选有 40 处（`update-buffer-bytes-refs.json`，与 [81](81-tiny-glade-command-initialization-and-slot23.md) 的旧清单一致）；这一数量不是 40 个同 buffer 写者。本轮没有把其中任何调用的输入 raw handle 与该 typed `FrozenMap` 项逐跳接通，故不能用名字或调用数量将其视作本表的替代写者，也不能用这份扫描排除其它 CPU 更新或 transfer。图资源别名、未具名 GPU binding、设备虚槽具体实现以及四字段后续覆盖未作全程序穷尽。

**状态。** 同一 typed 资源上的 `reset_indirect_args` 模板来源、23×20 B 表内容、第二暂存区与第二图资源的闭包配对、回调设备操作为 **Answered（静态、按门控）**。槽 0…22 的 `count/firstIndex/vertexOffset/firstInstance` 一条静态可达生产路径已找到；是否在具体帧执行、是否随后被覆盖、槽 23 的这四字段生产者、最终 backing `[460,480)` 是否有效为 **Partial/未知**。目标运行、GPU 抓帧、设备实现确认均 **Not Run**。
