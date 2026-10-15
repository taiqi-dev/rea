# Tiny Glade：槽 23 命令的图导入、backing 与后续写端

承接 [81](81-tiny-glade-command-initialization-and-slot23.md)、[83](83-tiny-glade-slot23-write-growth-and-submission.md) 和 [85](85-tiny-glade-wall-bucket-and-command-writes.md)。本轮把同一 typed `DrawIndexedIndirectBuffer` 从写租约继续追到 raw buffer 的图导入登记和注册器分派。**新导入的tag3状态在注册器中保留原raw handle，不走通用池化/新分配分支；所查链没有生成命令模板或提供槽23四个非计数字段写者。**完整生命周期和其它写入仍未穷尽，因此最终 backing 是否覆盖 `[460,480)` 及槽 23 的有效命令仍是未知，不能据此宣称运行越界或有效绘制。

## 范围和原始证据

输入仍是 [81](81-tiny-glade-command-initialization-and-slot23.md) 已核对的 `C:\Software\Steam\steamapps\common\Tiny Glade\tiny-glade.exe`（65,612,184 B）及同目录 `tiny_glade.pdb`；不重算摘要。地址为 EXE preferred VA。继续使用仓库内 `digging-a-hole/tools/pdb_probe.py` 和本机 VS2022 `dumpbin /DISASM /RANGE` 只读定位。本轮 PDB 精确掩码 `*BufferDesc*` 18/18、`*GraphImportable*import_mut*` 2/2、`*compile_main_render_graph*` 10/10、`*rhapsody::rg::resource_registry*` 74/74、`*rhapsody::rg::resource::BufferDesc*` 1/1、`*rhapsody::rg::compile*buffer*` 2/2、`*GraphicsDevice*create_buffer*` 13/13、`*ResourceRegistry::new*` 1/1、`*GraphRecord::import_mut*` 2/2，均枚举完毕；掩码命中只作定位，不当作全程序写端穷尽证明。

新增原始输出在 `.cache/procedural-modeling/static-final-followup/tiny-glade/`：`graph-symbols.json`、`registry-symbols.json`、`allocation-symbols.json`、`import-mut.txt`、`graph-record-import-mut.txt`、`resource-registry-new.txt`、`create-buffer-typed.txt`、`create-buffer-impl.txt`、`compile-main.txt`。复用 [81](81-tiny-glade-command-initialization-and-slot23.md) 的 `new.txt` / `draw-write-typed.txt`、[79](79-tiny-glade-draw-command-slot-provenance.md) 的墙 shader 和 typed 同键证据、[85](85-tiny-glade-wall-bucket-and-command-writes.md) 的 `finish-write-drawindexed.txt` / `buffer-export.txt`。没有启动或附加游戏、执行图/GPU、读私人存档；共享 REA native Ghidra 的既有超时状态未变，未重复打开。这里是普通静态原始文件，不是 REA MCP Evidence。

## 同一 typed entry 到图导入记录

| 边                  | 新增指令事实                                                                                                                                                                                                                                                                       | 限度                                                                                                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| typed 写租约        | [81](81-tiny-glade-command-initialization-and-slot23.md) 已证 `write_rg_buffer<DrawIndexedIndirectBuffer>` VA `0x14152B6C0` 使用同一 `FrozenMap` 键；其 `0x14152B754–777` 从项内取 raw buffer handle，经虚方法后调用 `Buffer as GraphImportable::import_mut` VA `0x140E1E250`。    | 这是前轮墙 compute 使用的 typed entry，不是名字相似的 `NaniDrawListSsbo`。虚方法的内部意义仍须按此原始类型约束。                                           |
| raw buffer → 图记录 | `GraphImportable::import_mut` 在 `0x140E1E267–293` 从输入 raw handle 分解 registry 索引，读取原始 buffer 记录中的字段（含 `+0x310/+0x318` 两个 qword）；`0x140E1E2A0–2B2` 将这些值传给 `GraphRecord::import_mut` VA `0x140E7A300`，随后 `0x140E1E2B7–2C9` 组装返回的 20 B 图句柄。 | 此段没有 `GraphicsDevice::create_buffer`，没有 `BufferDesc::new`，也没有对命令 20 B 字段的 byte store。尚未把 `+0x310/+0x318` 解码为可独立证明的长度字段。 |
| 图记录复用或登记    | `GraphRecord::import_mut` 的 `0x140E7A33F–42E` 按 raw handle 查内部表；命中时 `0x140E7A425–42E` 取已有记录索引并标为 mutable。未命中分支在 `0x140E7A441–4F3` 追加 32 B 图资源记录及配套状态，`0x140E7A57A–5B9` 建立 raw handle 到图记录索引的映射。                                | 增长的是图记录容器，不是命令 buffer backing；登记分支不构造五字段模板。命中/未命中取决于当次图状态，不能替代后续资源注册和执行证据。                       |
| 完成写租约          | [85](85-tiny-glade-wall-bucket-and-command-writes.md) 已证 `finish_write_rg_buffer<DrawIndexedIndirectBuffer>` 的 `0x141539CDE–D09` 交给 `GraphImportable::export`；它将同一图句柄标记导出并登记。                                                                                 | export 不修改原始 buffer 的逻辑长度或命令模板；最终设备 backing 仍须另查。                                                                                 |

这条链只证明**导入时仍以原 raw handle 为资源身份**。图句柄是记录/访问身份，不能把其 20 B 大小误认成 20 B 命令数据，也不能从图记录 Vec 增长推出原 buffer 扩容。

## 已见设备创建与图注册器的不同分支

[81](81-tiny-glade-command-initialization-and-slot23.md) 的 `new_storage_buffer<DrawIndexedIndirectBuffer>` 在空输入分支分配 `0x1CC=460` B 零 payload，并向 raw `GraphicsDevice::create_buffer` VA `0x1415D1D50` 传入 460 B `BufferDesc`。新增读取该 `create_buffer` 的 `0x1415D1DBD–1E36`：它先求 initial-data byte count，再把调用者描述符和数据交给 `create_buffer_impl` VA `0x140E547F0`；成功后 `0x1415D1E5C–1E82` 又将初值 byte count 与调用者描述符的打包字比较，超出时进入错误分支。此处未独立解码打包字的全部位语义，因此仍以构造处的 460 B 赋值为初始长度证据；这不是随后帧的最终长度或底层对齐后实际分配大小。

通用 `ResourceRegistry::new` VA `0x140E19CB0` 中另有可辨的 buffer 分配分支：`0x140E1ACE9–AD04` 用候选描述符调用 `ResourcePool::take_buffer`；复用失败则 `0x140E1AD06–AD3D` 把该描述符交给另一个 `GraphicsDevice::create_buffer` 特化，初始数据参数为零。该分支说明图系统**能**为其某类资源取池中 buffer 或新建 buffer，分配长度来自当时的候选描述符。当前证据没有把这段候选描述符、该分支条件和 `DrawIndexedIndirectBuffer` 的 raw handle/typed key 接成同一资源，也没有见到把 460 改为至少 480 的赋值边；不能把通用分支当成本槽已扩容的事实。`GraphRecord::import_mut` 的图记录容器增长同样不能替代 backing 长度证明。

## 四字段写端及槽 23 的精确边界

### 补查：导入变体如何越过通用分配分支

继续解开本作实际跳转表，而不是只按函数名推断分支。`GraphRecord::import_mut` 新记录在 `0x140E7A453` 写入头部 word **3**，在 `0x140E7A448` 写记录 `+8=1`，在 `0x140E7A441/44F` 将原 raw handle 放到记录 `+0x10`。注册器 `0x140E1A0D1–F7` 从32 B资源记录取 word，按 `tag<3 ? 0 : tag-2` 索引 VA `0x14320EF6C` 的相对跳转表。本作 PE 文件偏移 `0x320DF6C` 的四个有符号项解析后为 `0x140E1A0F9 / 0x140E1A4E1 / 0x140E1A4BB / 0x140E1BA78`；因此 tag3 选择第二项 `0x140E1A4E1`。

该分支从复制记录 `+8/+9/+0x10` 取标志和 raw handle；`+8=1` 时，经 `0x140E1A51A/520 → 0x140E1ACD1 → 0x140E1B2BC` 把 registry resource tag置3，保留同一个 raw handle，最后 `0x140E1A04B/4F` 写入注册器资源表。这条分支没有进入 `take_buffer/create_buffer`。所以**若同一导入记录保持 tag3 及该状态来到此分派，它复用原 raw buffer，不在此处扩容**；此前的通用池化分支不能再被当成这个导入状态下的扩容候选。

资源容器也有静态搬运连接：`GraphApi::new` 在 `0x140E2D267–26D` 把输入 GraphRecord 的前 `0x1A0` B 复制到自身起点，包含资源 Vec `+0x78`；`export_temporal_and_finish` 的 `0x140E2D4A4–4B8` 把同一区域复制到返回对象。`compile` 的返回对象位于 `[rbp+6F0h]`，其 `+0x78` 三元组在 `0x140588E09–1E` 移到 `[rbp+C50h]`，随后 `0x140589127–151` 经 `Vec::into_boxed_slice` 得到资源记录切片；`0x140589157/1AC/1AF` 把返回长度/指针交给同一 `ResourceRegistry::new`。这补上了资源容器到注册器的入口，不等于穷尽构图期间对每个记录的所有改变，也不证明特定墙条目本次实际执行。

新 raw 为 `finish-registry-symbols.json`、`graph-api-new.txt`、`export-temporal-finish.txt` 和 `registry-import-dispatch.json`；后者保留实际跳转表、四个目标和39条定点指令。这里仍没有 `count/firstIndex/vertexOffset/firstInstance` 写者，也没有把原 raw buffer 的完整后续生命周期证明为恒定460 B或最终至少480 B。新增结论只收窄**该导入分派不负责扩容**，不把剩余容量问题改写成已解决。

五个 32 位字段仍按 [79](79-tiny-glade-draw-command-slot-provenance.md) 的 `count, instanceCount, firstIndex, vertexOffset, firstInstance` 排列，stride 20 B。槽 23 从 `23×20=460` 开始；要读完整命令需要 `[460,480)`，即从初始 460 B 请求至少增加 20 B 逻辑可用范围。初始零 payload 只覆盖槽 0…22。若没有后续写入，槽 23 的任何字段均不能从初始零数组推值；若只发生已见的 `instanceCount` 原子增量，另外四字段仍没有模板来源。

具体排除范围保持分层：[79](79-tiny-glade-draw-command-slot-provenance.md) 已穷尽墙目录七个 compute 的显式 `draw_commands` 写入，已绑定到同 typed key 的绝对槽只到 16…22，写的是 `instanceCount`（含重置）。[81](81-tiny-glade-command-initialization-and-slot23.md) 的非墙候选 `draw_commands` 模块在其检查范围内也只见计数增量或读取，但各候选的 CPU typed key/绝对槽未逐一绑定。`nani/prepare_unsorted_draw_lists` 的五字段模板已证写入另一 `NaniDrawListSsbo`；`finish_write → export`、本轮 `import_mut` 以及主列表 `Vec` 增长只操作图记录或其他容器。PDB 的 `*replace_with_data*` 完整具名专门化没有此 typed 类型，但不能排除内联、通用 CPU 更新、没有 `draw_commands` 名称的 GPU 写入或后续重建。**这些有界阴性证据不能提升为全程序无写者。**

条件演算沿用 [85](85-tiny-glade-wall-bucket-and-command-writes.md)：若墙组 1 的实体仍带 `Transform` 且无 `DontCastShadow`，它可进第一桶；若 shadow 列表有第二项，`i=1` 使阶段 `i+2=3`；若该条目存活并通过绑定/回调门控，`indirect_draw_bricks` 选 `r9=23`，最终录制一次从字节偏移 460 读 20 B 的 indexed indirect 命令。该条件链没有提供 `count/firstIndex/vertexOffset/firstInstance` 值，也没有证明 `[460,480)` 在实际 graph 执行时有效。

**状态。** 同 typed 写租约到 raw handle 图导入、图记录复用/登记、资源容器到注册器，以及tag3状态的原handle保留分派为 **Answered（静态、按上述条件）**。该分派本身不提供扩容；完整构图/执行生命周期中其它位置是否替换或改变资源、最终 backing 逻辑长度、槽23四个非计数字段生产者仍为 **Partial/未知**。后续须核对记录在整个构图期间的其它写入，以及同 typed key 的 CPU 通用更新/未具名 GPU 写者；不能重复把已经区分的图记录增长或通用分配分支当成答案。游戏、GPU 与运行时验证均 **Not Run**。
