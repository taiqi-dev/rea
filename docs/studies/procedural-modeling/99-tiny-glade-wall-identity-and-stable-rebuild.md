# Tiny Glade：单墙恢复后的砖 seed 与稳定重建边界

本篇只追一面普通砖墙：历史回放或快照恢复其逻辑身份后，什么条件把它送回普通砖生成，以及相同输入能保证哪一层重复。前置结论见[62：历史与快照](62-tiny-glade-history-snapshots-and-regeneration.md)、[44：稳定随机](44-tiny-glade-stable-randomness.md)、[36：砖行](36-tiny-glade-brick-row-layout.md)与[55：编辑重建和上传](55-tiny-glade-edit-rebuild-stages-and-upload.md)。本篇新增的关键边是：先前只称为 `PublicWallState+0x48` 的每墙 seed 加数，在所选发行版布局中是一个 12 字节元素数组的**长度**。它不是可据此命名的“重新随机计数”。

## 身份、证据范围与坐标

精确目标为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 字节）和同目录 `tiny_glade.pdb`（310,513,664 字节）。本轮只读 PE CodeView RSDS 和 PDB 信息流，两者 GUID 均为 `d8d61d04-9e31-5b47-4c4c-44205044422e`、age 1；与[前轮固定身份](63-tiny-glade-coordination-contours-trees-and-history-ledger.md)记录相符。本轮没有重算摘要。以下地址均是首选 image base `0x140000000` 下的 RVA，不是 live 地址；列出的反汇编来自本机 `dumpbin 14.44.35222.0`，PDB 用于函数边界与符号名。原始范围、身份与算例保存在本机忽略目录 `.cache/procedural-modeling/static-state-followup/tiny-glade/`，属于普通 PDB/PE 静态记录，**不是 REA Evidence**。先前 REA native Ghidra timeout 状态未变，本轮没有重试。

| 本轮重读 RVA                     | 新增或复核的事实                                                                                                                                                                                                      |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `B0DA60–B0DD2F`                  | `InnerWalls.load_state` 从 120B 记录取原 WallId，重建 ID 集合/map，并将 `+0xC0` counter 设为最大 ID；非空路径会创建新的 HashMap `RandomState`。                                                                       |
| `92F5CE–92F653`                  | 成功的 `_try_update_state` 先把 WallId 插入 `InnerWalls+0x60` dirty map，再释放旧数组并转移 112B 新状态。                                                                                                             |
| `808D95–808E73`、`8090C3–809190` | `construct_walls` 遍历当前候选 ID，取 Public 墙；所见墙洞 `finalize` 返回 false 时不加入这一轮候选。后续再按 ID 查 Public map，查找本身使用哈希。                                                                     |
| `8096B9–8096DA`、`80AC7A–80AD25` | 当前 WallId 经 getter 得整数，与 Public 记录 `+0x48` 相加形成 `S`；`S` 被作为普通 `WallConstructor.from_curve` 的参数。                                                                                               |
| `BA098C–BA09C3`、`BA0BF0–BA0C55` | 公共墙替换时，旧 map 记录的 ID 在头部，Public state 从其后 8B 开始；旧 state 的 `+0x38/+0x40/+0x48` 是三 qword 数组描述。清理路径用 `+0x38` 乘 12 作释放大小、用 `+0x40` 作指针；因此 `+0x48` 是该 12B 元素数组长度。 |
| `80A543–80A54A`、`94C46D–94C4C8` | 选定普通墙分支先清旧砖 writer，再调用构造器；上传时每个对象的旧 allocation 再清一次，随后以 64B 步长 push 本次记录。两处清理属于不同资源层。                                                                          |

`BA09C3` 的复制起点为旧 Public state `+8`，因此临时副本 `rbp+2A0/2A8/2B0` 分别对应原 state `+0x38/+0x40/+0x48`。`BA0C12–BA0C33` 对前两项的容量/指针按 12B 元素释放；第三项不参与释放大小。这个定位依赖实际旧状态拷贝及 Rust Vec 在此制品中的读写布局，不给这个数组擅自命名为具体曲线或屋顶采样。`8096D3` 读取的正是该长度，所以[44](44-tiny-glade-stable-randomness.md)原先保留的“每墙值来源未知”在这一字段类型层面收窄；数组的生产者和长度何时变化仍未完整恢复。

## 恢复、候选与两次清旧

沿[62](62-tiny-glade-history-snapshots-and-regeneration.md)的已核调用，编辑回放的选定墙命令可走 `C1C8B0` 消费者，再调用 `92E8E0` 曲线修改或 `92F410` 完整状态修改；其中 `_try_update_state` 成功时明确插入 dirty ID。公共墙生产者 `B9F450` 汇集候选、写 `OnWallChanged` 并派生 Public 状态，见[45：对象候选与发布](45-tiny-glade-shared-invalidation-and-rebuild.md)。普通砖构造器在 `808800` 从候选 ID 查 Public 状态，并不是从历史记录直接读砖。所见分支还要求 Public 墙存在以及相应墙洞 finalize 资格；这些步骤不能被写成“每次撤销都一定重建该墙”。

快照路径是 `1BF3100 → B0DA60`。它保留每条墙记录的原 ID，并以最大 ID 设置后续普通新建的 counter。`load_state` 的选定指令没有直接插入上面的 `+0x60` dirty map，也没有在函数内调用砖构造器；加载完成到 Public 状态发布及本次构造候选的调度连接仍缺证据。因此，**恢复了同一个 WallId/WallState**和**已经重建到显示层**必须分开陈述。已有历史回放修改支的 dirty 写入比纯快照装载支更明确。

到达所选普通砖分支后，`80A54A` 对该墙使用的稀疏砖 writer 清旧，之后 `80AD25` 进入 `WallConstructor.from_curve`。本次 CPU 输出在 `94C360` 上传路径又先清该对象旧 allocation，后按 64B 记录 push，typed GPU range write 入口见[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)。清旧说明此路径替换对象产物，不保证物理 GPU 槽位沿用，也不证明该次运行已完成 GPU 提交或屏幕像素一致。

## 一个墙 ID 的条件演算

以下是构造输入，不是运行游戏或读取存档。假定快照含 WallId 7 和 12；`B0DA60` 装载后 counter 为 12，所以随后普通新建走[53](53-tiny-glade-wall-footprint-input-and-curves.md)的自增支时得 13。墙 7 的 Public state 中所选 12B 元素数组长度取 11；普通砖选定路径的底 seed 是按 u64 wrap 的：

```text
S = WallId × 0x4B28021 + PublicWallState.array_len_at_0x48
  = 7 × 0x4B28021 + 11
  = 551,649,522
```

若重放后仍是 ID 7、长度仍是 11，`8096CC–8096DA` 的 `S` 相同。再假定纵向边界数 `B=5`、裁后记录索引 `r=0`，则[36](36-tiny-glade-brick-row-layout.md)的横分 RNG 输入为 `S×0x154DF+B×0x159+r×0x96A3DD = 48,138,592,240,011`；`r=1` 为 `48,138,602,112,360`。同一 ID 若这条数组长度变成 12，`S` 变成 551,649,523，`r=0` 横分输入随之增加 87,263。若删除后普通新建成 ID 13、长度又取 11，则 `S=1,024,491,960`；它不能按原 ID 7 的随机身份处理。

这个演算给出严格的条件边界：同一制品、同一 ID、同一 `+0x48` 长度只保证 **底 seed** 相同；加上相同 `B` 和 `r` 才保证这一用途的行 seed 相同。要使该行随机输出和 CPU 砖记录相同，还需要相同的曲线/高度/墙洞/样式及相关浮点输入、相同分支与随机调用次序。砖行裁切、洞口、特殊样式和碎砖筛选可改 `B`、`r` 或输出数；`r` 只是本次裁后序号，不是永久砖 ID。即便 CPU 记录相同，allocation 清旧后物理槽位与最终 GPU/像素等价性仍未证明。

## 静态确定性与未答边

恢复原 WallId 是一条强身份事实；`B0DA60` 在非空墙输入时新建带随机状态的 HashMap，说明容器桶序不能当作持久顺序。所选底 seed 直接取墙 ID 和数组长度，不取 HashMap 哈希值；但本轮未证明所有产物的遍历顺序、实例索引或其它全局输入都独立于容器顺序。`B0E300` 带 ID 创建和 `B0EB60` 普通新建使用不同 ID 路径，见[62](62-tiny-glade-history-snapshots-and-regeneration.md)与[53](53-tiny-glade-wall-footprint-input-and-curves.md)。

已答：恢复原 ID/最大 counter，回放选定状态修改的 dirty 写入，普通砖底 seed 的 ID 与数组长度来源，普通砖生成/上传的清旧顺序，以及相同输入可保证到哪一级局部 seed。部分回答：快照直接装载后的 Public 重建与候选资格、该 12B 数组的生产者和长度稳定条件、不同撤销方向/反向回放。未答：快照到构造器的完整调度、同状态不同分配历史能否总得到相同数组长度、所有浮点/平台差异、排序和其它全局输入、GPU slot/最终像素一致性。没有启动或附加游戏、调用函数、读取私人存档、执行 GPU、安装软件或做运行/构建测试。

自研可独立采用“持久对象 ID → 显式稳定 seed 输入 → 对象级派生清旧重建”的分层规格；若需要撤销/读档后逐构件稳定，应把每个会参与 seed 的逻辑量与构件身份写成自己的持久契约，避免依赖临时容器顺序或数组容量。这是依据局部证据整理的设计建议，不是原作完整协议。
