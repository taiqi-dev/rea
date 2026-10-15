# Tiny Glade：typed 命令缓冲的替换入口与容量边界

承接 [81](81-tiny-glade-command-initialization-and-slot23.md)、[87](87-tiny-glade-final-command-backing-and-writers.md)、[89](89-tiny-glade-other-command-writers.md)、[90](90-tiny-glade-command-capacity-and-lifetime.md)。本轮找到可对照的 **同一个 `AssetSsboLibrary` 容器的替换机制**，但在这份发行制品的具名特化里，`DrawIndexedIndirectBuffer` 有 `add_new`、图读写/完成及 tuple fetch 等入口，**未找到该类型的 `replace_with_data`**。它的已定位 `add_new` 重复键分支报错；通用 `update_buffer_bytes` 按原 raw buffer 记录大小检查目标区间，不能靠这一接口把 460 B 的原 buffer 扩为覆盖槽 23 的 480 B。以上是有界静态结论；其它类型擦除写入、图记录重建或 GPU 路径尚未穷尽，最终逻辑容量和槽 23 四字段仍未知。

## 目标、方法与原始证据

目标是 `C:\Software\Steam\steamapps\common\Tiny Glade\tiny-glade.exe`（65,612,184 B）及同目录 `tiny_glade.pdb`（310,513,664 B）；本轮只复核路径和长度，未重算摘要。地址均为 PE preferred VA。使用仓库 `digging-a-hole/tools/pdb_probe.py` 本地查询 PDB、VS2022 `dumpbin /DISASM:NOBYTES /SECTION:.text /RANGE:0x...,0x...` 和已有的 `.text` 精确 `E8 rel32` 候选扫描。新原始文件在本机忽略目录 `.cache/procedural-modeling/static-replacement-followup/tiny-glade/`：`frozen-map-symbols.json`、`buffer-state-symbols.json`、`typed-storage-symbols.json`、`ssbo-library-symbols.json`、`frozen-insert-a.txt`、`frozen-insert-b.txt`、`frozen-insert-*-refs.json`、`replace-nani-list.txt`、`buffer-state-new.txt`、`buffer-state-drop.txt`、`hashmap-get-mut.txt`、`as-any-typed.txt`、`export-from-rg.txt`、`update-buffer-bytes.txt`。复用 [81](81-tiny-glade-command-initialization-and-slot23.md) 的 `add.txt`、[87](87-tiny-glade-final-command-backing-and-writers.md) 的 `import-mut.txt` 和 [89](89-tiny-glade-other-command-writers.md) 的同键写租约及模板回调原始记录。这些是普通静态输出，**不是 REA MCP Evidence**。先前 Ghidra 超时阻塞未变化，没有重试；未运行、附加或改动游戏，未读取私人存档、抓取 GPU、安装工具或操纵鼠标。

## 容器插入与真正替换是两条路径

PDB 完整列举 `*FrozenMap*` 19/19 个名字，过滤后有两个相同 `SsboId → Box<BufferState>` 具名 `insert` 实例（VA `0x140BF4E90`、`0x1421634E0`）。前者的 `.text` 精确直接调用候选集中包含 `DrawIndexedIndirectBuffer` 的 `add_new` 调用点 `0x14154283B`；由 [81](81-tiny-glade-command-initialization-and-slot23.md) 的指令边界确认。`insert` 在 `0x140BF4F7F–8A` 比较已有键，重复键分支 `0x140BF4FD2–505D` 销毁**新传入**的 boxed 值，返回 `eax=1` 且 `rdx=已有项`；新键分支 `0x140BF5143–5145` 返回 `eax=0`。`add_new<DrawIndexedIndirectBuffer>` 在 `0x141542840–846` 检查 `eax=1` 并跳入 `0x141542875–922` 的错误分支。因此，再调用这个已定位的 `add_new` 不能作为同键扩容的正常替换机制。这里的 `FrozenMap::insert` 返回旧项不意味着它自动写入新 raw handle。

实际可对照的替换函数是另一个类型的 `replace_with_data<NaniDrawListSsbo>`（VA `0x141533320`）。它在 `0x141533353–367` 先按输入数目乘 20 构造新 typed buffer；**已有键**由 `0x141533416–41E` 进入 `0x141533581`，`0x141533589–5BC` 调旧类型对象的析构及释放，`0x1415335C1–5D7` 将新 boxed 指针和 vtable 写回原 `BufferState`，`0x141533617` 重置项状态。**缺失键**才走 `0x14153345E–4F5` 的 `insert`；它的重复键竞态检查会走报错路径。这说明该库在其它 typed 资源上有真正的重建/写回机制，也说明仅枚举 `insert` 调用或 PDB 名称不足以证明某个类型被替换。它不是 `DrawIndexedIndirectBuffer` 的调用证据，不能借用该函数的动态长度给命令 buffer 推出 480 B。

PDB 对 `*ssbo_library*` 枚举 3362/3362 名，按库方法过滤有 19 个 `replace_with_data`、69 个 `add_new`、6 个 `add_new_with_data`、8 个 `add_existing`、11 个 `take_rg_buffer`，以及图读写/完成方法；其中具名 `replace_with_data`、`add_new_with_data`、`add_existing`、`take_rg_buffer` 均无 `DrawIndexedIndirectBuffer`。`*DrawIndexedIndirectBuffer*` 的既有 12/12 名称枚举与此一致。没有同名专门化只排除**本次 PDB 具名集合**，不排除内联、类型擦除或其它模块。`BufferState::new` 的 `0x14090E418–432` 设置 boxed 数据/vtable、锁和状态；`export_from_rg` 的 `0x14090E4FB–515` 重置状态并按状态跳转，本轮检查到的分支未显示新 buffer 描述符或同键 typed 指针写回，不能当成扩容证据。

## 原 raw buffer 的字节更新约束

`GraphicsDevice::update_buffer_bytes`（VA `0x140E55470`）可能因名称被误作扩容入口。它在 `0x140E554C8–4E0` 从传入 raw handle 找到资源记录；`0x140E554F0–5552A` 验证每段源区间并累计写入长度，要求 `目标偏移 + 累计长度 ≤ 记录 +0x320 的 dword 大小`，超出转入 `0x140E5552C–53F` 的 panic。大传输路径 `0x140E55600–673` 调 `create_buffer_impl` 建**暂存 buffer**，后续 `0x140E55752–759` 通过 setup callback 处理复制，不见此函数重写传入 raw handle 的库项。该 `+0x320` 字段也是 [87](87-tiny-glade-final-command-backing-and-writers.md) 的 `GraphImportable::import_mut` 在 `0x140E1E27A` 从 raw 记录读取的字段；两条路径面对的是 raw 记录的大小约束，而非 20 B 图句柄长度。

构造演算：若 [90](90-tiny-glade-command-capacity-and-lifetime.md) 创建的 460 B raw buffer 的记录大小仍为 460，则对槽 22 的 20 B 更新取 `offset=440`，`440+20=460` 通过这一比较；对槽 23 取 `offset=460`，`460+20=480>460`，走该函数的拒绝/报错分支。`0x140E55673` 即使创建更大的暂存区，也不会把目标 buffer 的逻辑大小改为 480。此演算是**同一记录大小保持 460** 的条件结论；本轮没有证明所有实际调用都以这条 raw handle 为目标，也没有把 40 个 `update_buffer_bytes` 直接调用候选逐一接到该 typed key。

## 与槽 23 的关系和下一入口

[89](89-tiny-glade-other-command-writers.md) 已把 `reset_indirect_args` 的第二图资源逐跳接到本 typed 写句柄，但静态模板只有 23×20 B，止于槽 22；它给槽 0…22 的 `count/firstIndex/vertexOffset/firstInstance` 一条有条件的写端。上述替换和更新检查没有提供槽 23 的这四字段，也未显示一个 480 B 新描述符。若同键 typed entry 在图使用前由未发现的另一入口换成至少 480 B 的 buffer，容量条件才可能改变；还需独立证明槽 23 内容、图资源实际指向新句柄、相关节点与 draw 的执行顺序。没有这些边时，既不能宣称最终必为 460 B，也不能宣称实际越界或有效绘制。

最有判别力的下一静态入口是：对 `BufferState` 中 boxed 指针/vtable 的其它**写入**做有界交叉引用，特别检查 `get_mut`/类型擦除及 graph 完成后是否重写 `DrawIndexedIndirectBuffer` 项；若找到新 raw handle，逐跳追到其 `BufferDesc` 低 32 位、资源记录 `+0x320` 和图导入时间。另一路是将 40 个通用 `update_buffer_bytes` 调用按调用者实际 raw handle 分类，查是否存在同资源且已先被更大描述符替换的情况。PDB 名称、直接 `E8` 与字面 key 清单均不能单独封闭间接调用、别名和 shader 写入。

**状态。** 本类型 `add_new` 的重复键行为、其它 typed 类型真实替换机制，以及 `update_buffer_bytes` 的目标容量检查为 **Answered（静态、限定入口）**。同键其它替换或 raw handle 重写、所有通用更新调用的身份、最终 `[460,480)` backing 与槽 23 四字段为 **Partial/Unknown**。游戏运行、GPU 和真实帧提交为 **Not Run**。
