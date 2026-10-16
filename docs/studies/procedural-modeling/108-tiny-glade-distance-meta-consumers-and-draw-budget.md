# Tiny Glade 屋瓦距离分类的消费者与绘制数量边界

后续[110](110-tiny-glade-roof-atlas-budget-and-graph-views.md)固定 RoofTile=6、初始容量表值65,536及一处变更写端，并连接 cull/fill 的共同逻辑图视图；三网格在 fresh 默认 atlas 下形成条件映射。最终物理 buffer 和运行帧预算仍未知。

承接[106：远处屋瓦、深度桶与数量边界](106-tiny-glade-distance-detail-and-budgets.md)。本轮追到一个明确的下游用途：屋瓦 cull 写出的 `filtered_instance_meta_buffer` 分类值在列表填充 shader 中**替代深度桶的低 10 位，成为网格索引**；排序列表的生成 shader 再按这个索引读取 atlas 部件的 `index_count / first_index`，为每个非空部件写一条 20B 间接命令和原实例索引间接表。CPU 的计数式绘制回调另有一个条件性 `1024` 最大命令条数实参。这个静态链支持“距离分类影响选择哪份网格部件”，但仍缺发行 CPU 的逐字段资源绑定与 atlas 顺序证明，不能把 `0/1/2` 无条件命名为主体／LOD1／背面，也不能给出实机绘制次数或瓦片总预算。

## 身份、方法与实际覆盖

目标为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184B）、同目录 `tiny_glade.pdb`（310,513,664B）、`compiled-shaders/country-core/compiled/` 内五个指定 precomp。EXE/PDB 使用[70](70-tiny-glade-update-and-render-costs.md)已匹配的同版身份；本轮只重读目标和 shader 文件长度，**未重新计算摘要**。CPU 地址均为 EXE preferred VA；shader 地址是各包原文件偏移，不能相加。这里是普通文件静态证据，不是 REA Evidence ID。

正式只读解析器 `tools/spirv_probe.py` 配合现有 `.cache/procedural-modeling/followup-art-updates/spirv.core.grammar.json`，新原始投影在 `.cache/procedural-modeling/static-consumer-followup/tiny-glade/`：`cull_and_bucket_roof_tile`（45,431B；3 模块／1,962 指令）、`fill_sorted_instance_list`（2,906B；1／133）、`fill_unsorted_instance_list`（3,680B；1／166）、`generate_draw_lists`（7,334B；1／357）、`nani-instanced-roof`（114,565B；4／5,481）的 JSON/TXT，均无 rejected 模块。另有 `cpu-symbol-*.json`、`nani-draw-symbols.json` 和四份限定函数的 `dumpbin` 文本。`*nani*draw*` 符号查询到 500 条即触发上限，**不是完整枚举**；三个更窄 CPU 符号查询分别 4/4、8/8、2/2 且 exhausted。结构解码不等于 SPIR-V 语义验证或实际 GPU 绑定。

## 分类值如何进入排序键

[106](106-tiny-glade-distance-detail-and-budgets.md) 已核屋瓦主视图模块起点 10981：候选先过实例范围、视锥、HZB 和前次可见位门；新增时写 `filtered_instance_buffer[slot] = instance_index*1024 + depth_bin`，并在**同一 slot**写 `filtered_instance_meta_buffer[slot] = m`。`m` 对通常 raw 标志取 `(-view_z > 70) ? 1 : 0`，raw 为 0 或 2 时覆盖为 2；本轮重解码中这两个资源是 set 0 / binding 2、4（包偏移 `0x3ACD–0x3B41`），写入指令见[106](106-tiny-glade-distance-detail-and-budgets.md)的十进制偏移 `22285–22401`。

`nani/fill_sorted_instance_list.precomp` 的唯一模块起点 `0x84`。它以 `thread_count_buffer[draw_list_index]` 为 invocation 上界（`0x774–0x804`），用 `list_instance_offset + invocation` 同时读取 filtered 值与 meta（`0x82C–0x8AC`）。二者在此模块是同为 u32、步长 4B 的 read-only storage 资源，分别为 set 0 / binding 2、3（`0x434–0x4B4`）。令 filtered 值为 `e`、meta 为 `m`，指令 `0x8BC–0x994` 给出：

```text
source_instance = e / 1024
depth_bin       = e % 1024
histogram[draw_list_index*1024 + depth_bin]++
sorted_instances[list_instance_offset + histogram旧值] = source_instance*1024 + m
```

这里的 `histogram` atomic 决定同一桶中的输出位置，并行执行时同桶内顺序不固定。`nani/fill_unsorted_instance_list.precomp` 的 `0xAC0–0xC04` 对相同两个输入做同样的商／余数与 `source_instance*1024+m` 写入；它还在 `0xC10–0xC64` 对 `draw_list_buffer[list_draw_cmd_offset+m].instance_count` 加 1。其 set 0 / binding 2、3、4、6 分别对应 filtered、meta、sorted 和 20B draw-list 资源（`0x588–0x728`）。两个填充变体都有条件边界；本轮未证明它们在一个视图中同时执行，不能把两者计数相加。

这条连接不只靠相似名称：生产者与两个消费者都保存**同一 slot 的一对 u32**；消费者把生产者的 `instance_index*1024+bin` 精确拆回实例索引和低 10 位，又以独立 meta 替换低位。CPU 特化 `cull_and_bucket_external<RoofTileSsbo,NaniCullAndBucketRoofTile>` 的 PDB 地址为 `0x1418C3650`，在 `0x1418C36B5` 从该实例池取得 `ToMultiDraw` 候选，并于 `0x1418C382F/0x1418C386E` 绑定／登记 compute dispatch。通用 `fill_instance_lists<RenderSublistIter>` 地址 `0x1418C2960`，`0x1418C2B41/0x1418C2B81` 与 `0x1418C2C84/0x1418C2CBD` 建立两个绑定／间接 dispatch 节点。这证明 CPU 编排存在屋瓦 cull 和列表填充两端；**本轮尚未逐字段证明它们的临时 graph 句柄就是同一物理 filtered/meta backing**。因此跨节点衔接是结构与编排支持的推断，单个 shader 内的算术和读写则是直接指令事实。

## 排序结果怎样变成间接命令

`nani/generate_draw_lists.precomp` 的唯一模块起点 `0x78`，读取 `sorted_instances_buffer`（set 0 / binding 3，`0x9AC–0x9CC`）。`0x1428–0x1478` 对读取值 `s` 算 `mesh_index=s%1024` 并为它累计局部频数；`0x156C–0x16CC` 对频数非零的索引分配命令位置及实例间接表位置。`0x1664–0x1698` 用 `world_subset、mesh_index` 选 `atlas_part_info` 的 `index_count` 和 `first_index`；`0x16DC–0x1798` 写 20B `draw_list_buffer` 的五字段：

```text
[atlas.index_count, 该mesh的实例数, atlas.first_index, 0, 实例间接表起点]
```

随后 `0x18F0–0x199C` 对每条 sorted 值取 `s/1024`，写进 `instance_indirection_buffer`。所以 meta 到这里确实作为 **mesh_index** 被消费，原实例索引仍能由 indirection 表找回。`nani_instanced_roof.precomp` 两个 vertex 变体分别在 `0x1B79–0x1BDD` 和 `0x10F90–0x10FF4` 先读 `nani_instance_indirection.buffer` 再以所得索引读 `material_data.nani_instance_data`；第一个变体中间接资源为 set 7 / binding 0（`0x8B9–0x8C9`）。然而本轮没有把 `generate_draw_lists` 的 set 0 / binding 8 输出与该 vertex 的 set 7 / binding 0 沿 CPU graph 句柄逐项连通，**不能把同名资源当成已证最终 GPU backing**。

发行 `assets/nani_meshes.ron:204–209` 在 `RoofTile` subset 下按 `roof_tile`、`roof_tile_lod1`、`roof_tile_backface` 顺序列三项；这与 `m=0/1/2`、下游 `mesh_index` 相容。仍需核对 CPU atlas 构建和 subset/list 偏移保序，才能把每个数值对应到这三份具体网格。已有[64](64-tiny-glade-building-kit-and-asset-assembly.md)只能证明三份资源进入该 subset，不能单凭文件顺序完成运行绑定。定点读 `nani_calculate_draw_list_params`（`0x140948130–0x1409487BE`）只见按内部类别、计数增长并构造多段 u32 数组；没有在该函数内找到资源名到 `atlas_part_info[RoofTile][0..2]` 的赋值。针对 atlas 的 PDB 查询还在符号文本编码处失败，较窄的 `*MeshAtlas*` 查询 120 条达到上限；这些都不能当作“保序”的阴性证明。本轮在这个动态类型／atlas 建表断点停止。

## 实际预算与条件演算

数量应分成不同域。`RoofTileSsbo` 是每条 64B 的 CPU/GPU 实例池，屋顶重建写入条数由合格屋顶决定；本轮没有恢复总容量或超限行为。cull 的 `instance_count` 是本 dispatch 的**候选范围**，HZB/prev 位决定本入口新追加量 `F`；filtered 缓冲所需 slot 数随追加量增长，当前容量及 atomic 后是否另有完整保护未知。填充 shader 的 `thread_count_buffer` 限制这次填充的 invocation 数，不能直接读成全场景瓦数。排序路径对每个有实例的网格编号产生一条 20B draw-list 命令，命令的 `instance_count` 是该路径聚合后的数；这既不是 CPU 池容量，也不是实际已经执行的 draw 数。`1024` 是编码的低位宽及直方图／网格索引空间，`70` 是分类比较；它们均不是瓦数容量。生成 shader 的局部 1024 项循环也不证明每帧绘制 1024 条命令。

静态 CPU 提交侧，PDB `fine_sorted_draw_fn`（`0x1409E5FA0`）经资源及入口参数判断后，在 `0x1409E62A0/0x1409E62B0` 取得两个只读图 buffer，`0x1409E6454` 调 `RasterStreamRecorderWithPipeline::draw_indirect_count`；`coarse_sorted_draw_fn`（`0x1409E64E0`）在 `0x1409E68AA` 取得图 buffer，`0x1409E69D3` 调 `draw_indirect`。前者有计数式提交，后者有直接间接提交；这两个入口与本屋瓦的具体图句柄、阶段门和最终 draw-list 命令尚未逐项绑定。

计数式回调的**最大命令条数实参**可以再收紧。`fine_sorted_draw_fn` 在 `0x1409E63F2–0x1409E643D` 计算第六实参 `M`：从渲染条目 `[rdx+0x10]` 取得的表基址 `p`，索引 `j=r9&31`，读取 `x=u64[p+0x1258+8j]`。若 `NANI_FORCE_FINE_GRAINED_SORTING` 为 0，且 `r9b>=2` 或 `NANI_FORCE_NO_FINE_GRAINED_SORTING` 非零，则 `M=1024`；否则 `M=(x+31)&~31`，即把 x 向上对齐到 32（按所见 64 位算术，极端溢出条件未核）。例如构造 `x=37`，此分支传 `M=64`，并不表示实际有 64 条非空命令。`0x1409E643D` 将 M 放入调用栈的第六实参位；被调函数 `0x140E24FA0 draw_indirect_count` 在 `0x140E25048` 读取该第六实参，并于 `0x140E2509B` 将其**低32位**存入 recorder 的 `+0xE0` 命令字段（`mov dword ptr [rsi+0E0h],eax`）；本篇不保证超大表值经此收窄仍保持原上限。第五实参在 `0x140E25101–0x140E2512A` 则与计数 buffer 视图偏移相加，存入 `+0xEC`。因此 1024 在此处是**某条件下单次录制的最大间接命令条数参数**，与 cull shader 的 1024 深度桶虽数值相同，作用域不同；x 的生产者和具体 RoofTile 入口参数尚未绑定。它也不限制每条命令的实例数。没有读取 GPU count buffer 的实值或观察一帧，**实际发出的命令数、每条实例数、裁剪收益、GPU 时长和 FPS 均 Unknown**。

构造演算沿用[106](106-tiny-glade-distance-detail-and-budgets.md)的两个候选：`first_instance=100`、`draw_list_index=4`、raw=1，视图 z 分别为 -20 与 -80，二者都通过 HZB 且 prev 位为 0。cull 对它们写 `e=102584,m=0` 和 `e=103822,m=1`，即深度桶 184/398。若列表偏移为 0、两桶原计数为 0 且没有别的并发候选，sorted 填充在直方图 4280、4494 各加 1，写 `s=102400`、`s=103425`。生成阶段拆回 `(source_instance,mesh_index)=(100,0),(101,1)`；若 atlas 两部件均有效且列表生成节点执行，将产生两个各 `instance_count=1` 的命令，indirection 表含 100、101。命令的 `index_count/first_index` 取 atlas 实值，本例没有编造这两个数；若其中一片已在 prev 位中可见而未由别的 pass 追加，本入口只贡献一片，不能再推出两条命令。这是指令条件演算，不是实机绘制观测。

**已答：** meta 的同槽读取、低位替换、网格编号消费、选定路径的实例／命令计数机制。**部分：** CPU 屋瓦 cull 与列表填充、vertex 与回调的编排及数据格式；跨节点物理资源身份、RoofTile 三网格顺序和实际分支选择未闭合。**Unknown：** 实例池/filtered/sorted/命令 buffer 容量与保护、具体画面的 draw 数、时长和视觉收益。**Not Run：** 游戏、Unity、GPU、附加、私人存档、函数执行、SPIR-V 语义验证；旧 Ghidra timeout 条件未变，本轮未重试。下一静态入口是 CPU binder 对 filtered/meta/sorted/indirection 的逐字段 graph 句柄传递，以及 atlas 构建时 RoofTile 三项的部件索引赋值。
