# Tiny Glade：实例合批与间接提交的计数边界

本次把普通 RoofTile coarse 回调的 **命令起始号、提交条数实参和 recorder 字段**接通。结论是：多个通过筛选的实例可以在 `fill → generate` 后落入同一网格部件的间接命令，coarse 路径再以一次 CPU 回调录制一段命令。它减少的是逐实例 CPU 绘制入口的需求；没有测得该场景的命令数、驱动调用数、GPU 时间或 FPS。

承接 [108：分类值到命令](108-tiny-glade-distance-meta-consumers-and-draw-budget.md)、[110：atlas 与参数表](110-tiny-glade-roof-atlas-budget-and-graph-views.md)、[112：屋瓦池及 coarse 注册](112-tiny-glade-external-pool-producers-and-draw-bindings.md)和 [115：稳态视图与 recorder](115-tiny-glade-steady-culling-and-submission.md)。本篇新增当前 PE/PDB 的局部读取；沿用前文的 shader 结构解码，不把两种证据混称。

## 身份、原文与方法

静态输入为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`，65,612,184 B，PE32+ x64、preferred image base `0x140000000`，相邻 `tiny_glade.pdb` 为 310,513,664 B；本次沿用已经确认的 EXE SHA-256 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` 和用户授予的摘要取用范围。这里没有再计算摘要，也没有启动或附加游戏。地址是 preferred VA，文件偏移由 PE section 实测映射，不能当作运行地址。

新增的普通静态原文在 ignored `.cache/procedural-modeling/tiny-performance-batching-lod-shadows/batching/`：`draw-indirect-symbols-current.json`（DbgHelp PDB 精确查询，4 个候选、2 个 recorder 符号、查询穷尽）、`draw-indirect-abi-current.txt`、`coarse-tail-current.txt`、`draw-list-params-current.txt`、`set-draw-list-params-current.txt`（当前 PE 的限定范围 `dumpbin /DISASM:BYTES`），以及 `coarse-submission-anchors-verified.json`。新增只读 [batching_submission_probe.py](tiny-glade/tools/batching_submission_probe.py) 用 14 处指令字节、2 个相对调用核对关键结论，并记录 PE 文件偏移；错误身份、指令或调用目标会失败。这些是**普通 PE/PDB 静态证据，不是 REA Evidence**。现有 Ghidra 300 s 超时条件未变化，未重试。

复现锚点读取（输出路径需为尚不存在的文件）：

```powershell
python docs/studies/procedural-modeling/tiny-glade/tools/batching_submission_probe.py 'C:\Software\Steam\steamapps\common\Tiny Glade\tiny-glade.exe' --output '.cache/procedural-modeling/tiny-performance-batching-lod-shadows/batching/coarse-submission-recheck.json'
```

PDB 定位使用现有 `digging-a-hole/tools/pdb_probe.py` 对同一绝对 EXE 输入执行 `--mask '*draw_indirect*' --regex 'RasterStreamRecorderWithPipeline' --limit 30`；`dumpbin` 的四段 `/RANGE:0x起点,0x终点` 分别覆盖 `0x140E24CB0–0x140E24DFE`、`0x1409E6780–0x1409E69E5`、`0x140948130–0x1409487BE`、`0x1409D3120–0x1409D35BD`。这限定了本次实际读取范围，不等于对所有调用者的穷举。

## 四个数量域怎样收敛

| 数量域             | 所见来源及消费                                                                                                                                                                                | 能否直接叫 draw 数                                     |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 候选范围 `C`       | [108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md) 的屋瓦 cull dispatch 范围；[112](112-tiny-glade-external-pool-producers-and-draw-bindings.md) 的池容量初始 65,536 是可容纳量 | 不能。容量与本次候选、通过数都不同。                   |
| 新追加实例 `F`     | cull 资格/HZB/前次可见位后写 filtered 与同槽 meta；两轮主视图和阴影视图分开                                                                                                                   | 不能。一个实例可能在不同视图产生工作。                 |
| 生成的非空命令 `K` | sorted fill 把 `source_instance*1024+mesh_index` 写列表；`generate_draw_lists` 对每个非空 mesh index 从 atlas 取 index 范围，写 20 B 命令及实例间接表                                         | `K` 是该列表的命令数，仍不是全帧实际执行量。           |
| CPU 录制调用 `R`   | RoofTile=6 且 `FORCE_FINE=0` 的注册路径选 coarse；一次 coarse 回调把一段命令交给 `draw_indirect`                                                                                              | 所见一次回调/recorder 入口可带多条命令，`R` 不是 `K`。 |

因此合批的具体机制是：**候选实例先筛选，再按网格索引归组，组内实例索引由 indirection 表保留，最后按命令段录制。** “按材质合批”只在已经选定的屋瓦管线/材质绑定作用域内成立；本轮没有证明不同材质、所有 29 个 subset 或不同 pass 可合为同一个物理批次。`RoofTile` fresh 默认 atlas 下 `0/1/2` 条件对应 `roof_tile`、`roof_tile_lod1`、`roof_tile_backface`，热重载及槽复用仍受 [110](110-tiny-glade-roof-atlas-budget-and-graph-views.md) 的边界约束。

## 新桥：coarse 从子列表号到 recorder

`coarse_sorted_draw_fn` 是 PDB 地址 `0x1409E64E0`。[112](112-tiny-glade-external-pool-producers-and-draw-bindings.md) 已证正常 RoofTile 的注册条件及读 NaniDrawListSsbo 的入口。这次在所选非失败路径看到：

1. `0x1409E677C` 限制 kind 字节小于 29；`0x1409E6799–0x1409E67A7` 用 `kind&31` 计算 `160×kind`。`0x1409E67AB` 先读取该记录 `+0x38` 的**锁状态**，随后经共享锁与内联/外置数据选择；`0x1409E6826–0x1409E683C` 从所选数据 `+8` 取 qword 并保存为稍后第四实参。这个 qword 是传给 recorder 的**命令条数实参**，不是 cull 后实例数。其全部生产者和是否恰为非空 `K` 尚未证明。
2. `0x1409E686A–0x1409E6894` 把一处已取出的子列表索引与 `0x143033078` 的类别表值组合，在显式长度门后，从 u32 表中取**命令起始号**。这段有 `rsi < [rax+0x38]` 的边界检查；不能把表的槽号、类别号或长度直接读成命令数。`0x1409E6894` 的 `mov r12d,[rax+rsi*4]` 位于 PE 文件偏移 `0x9E5C94`。
3. `0x1409E69C4–0x1409E69C8` 算 `byteOffset = startCommand×4×5 = 20×startCommand`，作为第三实参；`0x1409E69C0` 把第 1 步的 qword 作为第四实参，`0x1409E69D3` 直接调用 PDB 确认的 `RasterStreamRecorderWithPipeline::draw_indirect` `0x140E24CB0`。调用后 `0x1409E69DE` 结束该资源的 graph read。这里证的是一次所见 CPU 录制路径，不能据此算 Vulkan 命令缓冲提交次数。
4. 被调 recorder 在 `0x140E24D41–0x140E24D45` 将资源视图 `+8` 偏移加到第三实参；`0x140E24D5D` 把结果的低 32 位写到 recorder `+0xDC`。`0x140E24D91` 将第四实参的低 32 位写到 `+0xE0`；两者先检查高 32 位是否为零，溢出走错误分支。该函数也登记 graph resource access（`0x140E24D3C`），故调用本身是 recorder 状态写入，不是观察到一次驱动 API 调用。两个最终 store 的 PE 文件偏移分别是 `0xE2415D`、`0xE24191`。

新增 PDB 查询把 `draw_indirect` 定到 `0x140E24CB0`、334 B，并将 `draw_indirect_count` 独立定到 `0x140E24FA0`、504 B；本篇 coarse 走前者。[108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md) 的 fine 最大命令条数与本次 coarse 共享锁读出的 qword 并非一个已证明相同的值。`nani_calculate_draw_list_params` 的新 PE 读取确认它生成多段 u32 向量，并在 `0x1409486AD–0x140948700` 发布结果；`GpuWorld::set_draw_list_params` 的 `0x1409D32C3–0x1409D33B0` 复制及替换一份结果。不过尚未把 coarse 内两次查表沿对象/别名闭合到这两个函数的具体向量字段，所以这里保留**参数生产者 Partial**，不按相似偏移强行接线。

## 贯通演算与自研取舍

构造一帧的单个屋瓦视图：假定候选 120，cull 后本轮需新增 100；其中 60、30、10 个实例分别归到三个有效 mesh index，sorted 路径得到 `F=100`、`K=3`，命令的 `instance_count` 分别为 60、30、10，实例间接表保留各自原索引。**再假定** coarse 表给 `startCommand=7`、`commandCount=3` 且所读图视图偏移为 40 B：回调传入 `20×7=140 B`，recorder 保存 `+0xDC=180 B`、`+0xE0=3`。这是对已见指令的条件演算；`7/3/40` 都是示例输入，不是游戏样本。该视图可以用一次 CPU 录制入口表示三条间接命令和 100 个实例，但不能推出一帧只有三次绘制或 100 个像素可见瓦片；其它视图、空命令、图执行门及 GPU 深度结果都未被实例化。

对综合 demo，可独立采用四个分开的计数器：持久实例池使用量、每视图筛选通过数、按网格/材质分组后的非空命令数、CPU recorder/实际图形 API 提交数。只有测得提交成本高时，才考虑间接多绘制；小场景先保证实例资料复用和按视图筛选即可。若实现多绘制，每个分组命令应保留可诊断的 `index_count/first_index/instance_count/first_instance`，并核实命令 buffer 容量、空槽初始化、视图偏移与 shader indirection 绑定。自研代码和资产应按自身需求独立设计，本篇没有移植原作源码。

**Answered（静态）**：普通屋瓦 coarse 选路前提、从子列表查出起始命令号、`20×` 偏移、第四实参进入 recorder 命令条数字段、候选/实例/命令/录制四域区别。**Partial**：命令条数记录与参数生成器的具体字段别名、生成输出到 coarse 读取的完整 graph backing 同一性、材质跨批边界。**Unknown**：实际开关值、逐帧 `C/F/K/R`、空命令和真实执行条数、API/CPU/GPU耗时与 FPS。目标运行、附加、GPU、Unity、私人存档、3DSandboxTest读取、模型代码复用、Ghidra 重试均 **Not Run**。
