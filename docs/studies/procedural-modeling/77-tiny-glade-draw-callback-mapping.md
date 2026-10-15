# Tiny Glade：墙绘制条目的回调映射

> 后续 [79：绘制命令槽来源](79-tiny-glade-draw-command-slot-provenance.md)接上同一 typed buffer、CPU 基址 16 和 shader 槽 16–22；回调槽 23 的生产者仍未闭合。

本篇回答 [72](72-tiny-glade-cpu-render-bindings-and-lifecycle.md) 留下的墙条目断点：**墙启动路径注册的是 `draw_bricks::indirect_draw_bricks`，而不是直接注册 `CustomDrawFn::indexed_indirect::draw_fn`。** 前者按绘制阶段与墙组 payload 选择间接命令索引，满足条件时再尾调用后者。`build_draw_lists` 将 ECS `CustomDrawFn` 的两个机器字复制到 64 B 的 `DrawListItem`，`render_bucket` 从条目 `+0x20` 读取函数指针并以 `+0x28` 的 payload 调用。这是静态的注册→条目→录制链，不代表任一墙在每一帧实际可见或 GPU 已执行。

## 输入与证据边界

沿用 [70](70-tiny-glade-update-and-render-costs.md) 核对的同版 `tiny-glade.exe`（65,612,184 B，SHA256 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`）及相邻 `tiny_glade.pdb`。地址均为 EXE preferred VA。用现有 `digging-a-hole/tools/pdb_probe.py` 限定符号掩码和 VS2022 `dumpbin /DISASM /RANGE` 读取；ignored 原始投影在 `.cache/procedural-modeling/static-submission-followup/tiny-glade/`。`*indirect_draw_bricks*` 得 1/1、`*draw_fn*` 得 12/12、`*Commands::spawn*` 加 `CustomDrawFn` 过滤得 6/6，均未截断。只读 PE `.text` 中目标函数的 RIP 相对地址构造，并回读 `.rdata` 分发表；没有运行、附加游戏或抓帧。

## 墙实体注册：两个显式组与一个三项循环

PDB 将 `0x140B967E0` 标为 `country_core::startup::startup_walls::glade_startup_walls`（9,614 B）。三个构造点都把 **同一函数 VA `0x1409640E0`** 写到 16 B `CustomDrawFn` 的第一个机器字，把分组 payload 写到第二个机器字，然后调用有 `CustomDrawFn` 的 `Commands::spawn` 专门化：

| 构造点 | 函数指针 / payload 写入                                                                                                     | spawn 与 bundle                                                                    | 静态含义                                                         |
| ------ | --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| 第一组 | `0x140B978C6–D4`：`[rbp+220h]=0x1409640E0`，`[rbp+228h]=b<<32`；`b` 在 `0x140B97618` 收窄为一字节                           | `0x140B978F7 → 0x14161FA40`：`(DrawableMeshBundle, CustomDrawFn, OcclusionCulled)` | payload 低 32 位为 0，bit 40 为 0                                |
| 第二组 | `0x140B97A38–4A`：先将上述 payload 低位 OR 1，再写同一指针与 payload                                                        | `0x140B97A6D → 0x14161FA40`：同一 bundle                                           | payload 低 32 位为 1，bit 40 为 0                                |
| 循环组 | `0x140B97ABF` 将循环变量清零，`0x140B97D1C–3E` 写 `((i<<48) \| 0x10000000001)` 与同一指针；`0x140B97D73–7A` 在 `i<3` 时继续 | `0x140B97D5D → 0x14161C000`：`(DrawableMeshBundle, CustomDrawFn)`                  | 三个构造迭代 `i=0,1,2`，bit 40 为 1；没有 `OcclusionCulled` 组件 |

这里的第一、第二组 `b` 是构造时参与 payload 编码的字节；仅凭此处不能给它命名为墙 ID、材质 ID 或 draw-list 索引。`spawn` 是 ECS 命令记录，不能据静态构造次数断言运行时恰有五个可绘制实体。与之相对，直接取得 `indexed_indirect::draw_fn` 地址 `0x140AF4A50` 的七处 `.text` RIP 相对 `lea` 位于 `startup_terrain`、`startup_water`、`startup_garden_brush`；整份 EXE 中无该 VA 的 8 B 绝对值。墙上述三个点指向的是 **`0x1409640E0`**。因此以通用 `indexed_indirect` 的符号名直接归类墙条目会跳过实际阶段筛选。

## ECS 回调如何成为 `render_bucket` 的条目

`draw_lists::build_draw_lists`（`0x140AF54F0`）的查询类型在 PDB 中包含 `Option<&CustomDrawFn>`。其 `0x140AF631B–33E` 用每实体 16 B 步长取得回调组件位置；当位置非空，`0x140AF6A67–6A8E` 从 `[rsi]` / `[rsi+8]` 读出函数指针与 payload，并放入本地条目 `+0x20` / `+0x28`。`0x140AF6934–6971` 把四个 16 B 块复制进目标 `Vec<DrawListItem>`，每条 64 B。空组件走 `0x140AF6B60`，使函数指针为零。这个字段级复制证明注册的墙回调可进入绘制列表，但条目仍受 ECS 查询、pass 分类和桶筛选条件限制。

`draw_lists::render_bucket`（`0x140AF4DC0`）在 `0x140AF5041–5051` 以 64 B 步长确定桶的条目范围；必要绑定处理之后，`0x140AF523F–5246` 检查条目 `+0x20`。非零时 `0x140AF5080–5098` 取 `r9=[item+0x28]`，以 `rcx=item`、`rdx=资源容器`、`r8b=阶段字节`、第五参数为绘制 recorder 调用该函数指针。零指针则转入普通 `draw` / 网格分支。因而对已纳入此桶且通过绑定查找的上述墙条目，目标正是 `indirect_draw_bricks`；这是回调槽的调用条件，不是无条件逐帧调用计数。

## 墙回调选择命令，再录入 indirect draw

PDB `draw_bricks::indirect_draw_bricks`（`0x1409640E0`，410 B）在 `0x1409640E8–0FA` 用 `r8b` 索引 VA `0x1430279F0` 的五项相对跳表。PE 回读得到阶段字节 `0/1 → 0x1409640FC`，`2 → 0x1409641A9`，`3 → 0x1409641AE`，`4 → 0x1409641A4`。这些是**内部字节值**；本轮没有将五值逐一命名为 G-buffer、shadow 等 pass。

- 第一、第二组在 `0/1` 分支先检查 payload bit 40（`0x1409640FC`），再经资源查询和条件判断：可提交时按 payload 低位选 `0x10/0x11` 或 `0x12/0x13`（`0x140964230–26C`）；失败/不合条件时返回或进入显式 `unwrap_failed`。不能把这两个构造点都计作必然 draw。
- 循环组在 `2/3/4` 分支把阶段映射为 `0/1/2`（`0x1409641A4–1AE`），要求 payload 高 16 位与该组序号相等、低 32 位为 1、bit 40 为 1（`0x1409641B1–1D5`）。通过后命令索引为 `0x14 \| (r8b & 3)`：阶段 `2/3/4` 分别产生 `0x16/0x17/0x14`。不匹配便返回。
- 所有实际提交分支在 `0x1409641E2–1ED` 把选出的索引放入 `r9`，**尾跳** `CustomDrawFn::indexed_indirect::draw_fn`（`0x140AF4A50`）。该函数在 `0x140AF4CF8` 读 graph buffer，`0x140AF4D03/4D12` 设 vertex/index buffer，`0x140AF4D64–7A` 以 `20 × r9` 字节偏移、命令数 1 调 `RasterStreamRecorderWithPipeline::draw_indirect`，随后 `0x140AF4D85` 配对结束 graph read。

**构造演算。** 假设循环组 `i=1` 的条目通过查询、桶绑定，阶段字节为 3。注册 payload 是 `0x1010000000001`；阶段 3 选组号 1，与 payload 高 16 位一致，低位和 bit 40 也满足；回调交给通用函数的命令索引是 `0x17=23`，字节偏移 `23×20=460`，记录一次命令数 1 的 indirect draw。若阶段字节改为 2，组号为 0 而该 payload 为 1，回调直接返回。这是指令分支的构造输入演算，不是观察到的帧数、可见墙数或 FPS。

**已答与未答。** 墙三类注册形式、`CustomDrawFn → DrawListItem(+0x20/+0x28) → render_bucket → indirect_draw_bricks → indexed_indirect::draw_fn → draw_indirect` 有地址与字段证据。GPU 的 `wall/generate_draw_lists*` 写入的每个 `draw_commands` 槽与这里 `0x10–0x17` 的**同一资源句柄及逐槽对应**仍未从本轮指令逐字段核实；[70](70-tiny-glade-update-and-render-costs.md) 的 shader 读写相容不能替代这一步。也未观察 graph 编译后的运行条件、驱动提交或耗时；运行验证 **Not Run**。
