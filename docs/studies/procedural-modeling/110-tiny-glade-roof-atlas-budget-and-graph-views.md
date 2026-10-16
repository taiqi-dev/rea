# Tiny Glade：屋瓦 atlas 编号、容量表与图资源视图

后续补充见[112](112-tiny-glade-external-pool-producers-and-draw-bindings.md)：+0x50已接构造/flush写端及页数别名，kind6接屋瓦管线与材质。FORCE_FINE=0时实际注册coarse回调；本篇fine的1024仍只是假设进入fine后的条件演算。

接续[108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md)。本轮把 `RoofTile` 的子类编号固定为 **6**，找到绘制回调所读容量表的初始化及一处后写端：初始值 **65,536**，所读变更分支要求新值不大于 **1,048,576** 且为 **64** 的倍数。另把屋瓦 cull 与 sorted fill 的 filtered/meta 参数接到同一组逻辑图视图。发行 RON 的三网格在**新建空 atlas、按默认列表加载且无覆盖**的条件下可对应到部件 `0/1/2`；热重载、空槽复用、最终物理 buffer 和真实帧数量仍不能由此代替证明。

## 身份、工具与覆盖

输入为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B）、同目录 `tiny_glade.pdb`（310,513,664 B）及 `assets/nani_meshes.ron`（16,124 B）。沿用[70](70-tiny-glade-update-and-render-costs.md)的同版 PE/PDB 身份，本轮未新算目标摘要；所有地址为首选 VA。复用现有 VS `dumpbin 14.44.35222.0` 和正式只读 PDB/PE 读取器，未执行目标。新 raw 在 ignored `.cache/procedural-modeling/static-config-followup/tiny-glade/`，下文普通文件证据**不是 REA Evidence**。

新的[预算表探针](tiny-glade/tools/atlas_budget_probe.py)测量 PE 节映射，检查具体指令锚点，读取 29 项相对跳转表及第 30 项结束分支；它不模拟函数。`atlas-production-symbols.json` 对 `*mesh_atlas_library*`、`*nani*atlas*` 分别检查 372、272 个候选，以明确 namespace 过滤后接受 12、10 个，均 exhausted；`world-exact-symbols.json` 的两个窄查询也 exhausted。更早 `world-loading-symbols.json` 的宽查询到 100 条停止，不作为完整枚举。

原 PDB 输出遇到未配对 UTF-16 字符会在 UTF-8 保存处失败；本轮仅将[通用读取器](digging-a-hole/tools/pdb_probe.py)的 JSON 保存改为转义形式，保留字符码元后完成上述查询。另用[类型探针](tiny-glade/tools/pdb_type_probe.py)查 `WorldSubset`、`GpuWorldSubsetKind`、`GpuWorld` 均零命中，而 `*` sanity 查询能返回 3 个类型并显式截断。这是本接口/查询的覆盖限制，编号结论来自下面的真实解析指令，未靠类型查询缺席猜测。

## RoofTile 编号与 atlas 部件顺序

`GpuWorldSubsetKind` 的 serde 字符串 visitor 位于 `0x140958FF0`。`0x14095942A–0x140959439` 以 8 B 比较完整 `RoofTile`，成功写 `word [rcx]=0x0632`：低字节是此返回布局的成功标记，高字节是载荷 **6**。独立的 CPU 调用也吻合：`gpu_generate_draw_lists` 在 `0x1409B75B3` 置 `r9b=6`，`0x1409B75B6` 直接调用 [108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md)已由 PDB 定位的屋瓦 cull 特化 `0x1418C3650`。这比按配置列表位置猜枚举可靠。

默认 `assets/nani_meshes.ron:204–209` 在 `RoofTile` 内列 `roof_tile`、`roof_tile_lod1`、`roof_tile_backface`。加载特化 `0x141826650` 在 `0x14182688E–0x1418268E4` 取得该 mesh 向量，按 32 B 项逐项前进；每项先在 `0x141826954` 加载/准备网格，再在 `0x141826A1D–0x141826A3B` 将 subset 字节、名称及网格交给 `MeshAtlasLibrary::add`。这里既有配置又有顺序消费，并非只看 RON 名称。

`MeshAtlasLibrary::add` (`0x140A58820`) 先按 subset 查 atlas；新条目路径把部件数组与空闲槽数组初始化为空（`0x140A58A75–0x140A58ABD`），再于 `0x140A58AE0` 调 `MeshAtlas::add` (`0x140C51D90`)。后者有两个不能忽略的分支：空闲槽非空时 `0x140C52035–0x140C52047` 弹出旧槽号；否则 `0x140C52288` 取部件长度为候选槽号。追加路径 `0x140C529DD–0x140C52A18` 按 16 B stride 写部件记录并递增长度，最终 `0x140C52A3D` 返回槽号。已有槽的更新不等于新追加；mesh 内属性排序也不是重排 RON mesh 列表。

因此在**该 subset 新建、空闲槽为空、三次 add 成功且输入就是发行默认列表**时，可演算：

| 顺序 | 名称                 | 部件号 |
| ---- | -------------------- | ------ |
| 1    | `roof_tile`          | 0      |
| 2    | `roof_tile_lod1`     | 1      |
| 3    | `roof_tile_backface` | 2      |

这把 [108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md) 的 meta `0/1/2` 与三份资源接成**条件映射**。加载入口会经过 `tg_mods::overlay::resolve`，重载又可能复用槽；尚未穷尽所有清空、compact、同名替换与实际启动路径，不能将此表写成所有会话不变的运行编号。`nani_on_scene_load` 的 `0x1409E5C31–0x1409E5C52` 会将 atlas 部件 slice 交给 `update_mesh_atlas_slices`；该函数把 16 B 项写到 `subset<<14` 字节偏移，并检查目标容量。RoofTile=6 的偏移为 98,304 B。其资源对象到最终 shader backing 的完整绑定尚未闭合。

## 单次命令上限读的是哪一张表

`GpuWorld::new` (`0x1409D3960`) 的 `0x1409D39DF–0x1409D3A57` 使用 `0x14302DD0C` 的相对跳转表，给 29 类生成 u64 数组。第 6 项落到 `0x1409D3A02`，写 `0x10000=65,536`。数组先在 `0x1409D3A6E` 复制到栈 `+0x11C8`，交 `nani_calculate_draw_list_params`，最后 `0x1409D3D15–0x1409D3D29` 把 232 B 原容量表复制到 `GpuWorld+0x1258`。`GpuWorld::subset_capacity` (`0x1409D2D70`) 也直接返回 `world[0x1258+8*kind]`，所以它有明确的容量读取者。

对象身份另作核对：PDB 定位的 `World::resource_scope<GpuWorld>` (`0x141952EB0`) 在 `0x14195302E–0x141953037` 复制1358h字节的该资源。它在 `0x141952F2F` 使用的完整类型键与 fine 回调第三次资源查找 `0x1409E618E` 读到**同一常量地址 `0x142E34190`**；两处16 B原字节均为 `ff7563a7d8b43705b7bce22c6b36a310`，这里只比较已存常量，没有计算摘要。fine 在 `0x1409E6210–0x1409E6270` 沿此键的资源槽取出 rbp，随后读 `[rbp+0x1258+8*(kind&31)]`。因此 [108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md) 的 x 能与该 GpuWorld 容量表绑定，依据包含类型键、资源槽和字段链，不能只靠相同偏移。它并非 atlas 中有几份网格，也不是本帧通过裁剪的实例数。若该 fine 回调的条目确为 RoofTile=6，且 `FORCE_FINE=0`，既有 `kind>=2` 门使单次 `maxDrawCount=1024`；即使 x 初值是 65,536，也不因此提交 65,536 条命令。若强制 fine 分支生效，则初始 x 向上对齐 32 仍是 65,536。具体 RoofTile raster 回调注册和真实开关值尚未逐项绑定，故这里仍是条件实参演算。

`GpuWorld::apply_grown_capacity` (`0x1409D2E70`) 是明确后写端。`old==new` 时直接返回；若表内已等于 new，也跳过写表与脏标记。因此下述限制仅针对**所见 changed-value 路径**：`0x1409D2FAF–0x1409D2FCD` 的两级类别位图对 kind 6 选择 1,048,576 上限；超过它走 panic，`0x1409D2FE2` 检查低 6 位，非零也走 panic。通过后 `0x1409D2FEC` 写同一表项，`0x1409D2FF4` 置 `world+0x1350=1`，并将类别加入去重后的待处理列表。所读字节没有单独的 `new>old` 检查，不能从函数名断言它绝不接受缩小值。

屋瓦外部池另有写端，不能由 `apply_grown_capacity` 仅两个直接call候选就判未同步。上述 typed resource scope 在 `0x14195312A–0x141953136` 以 kind6、局部GpuWorld指针和资源库调用 `sync_external_capacity<RoofTileSsbo>` (`0x1409D0DE0`，PDB386 B)。它用与屋瓦cull相同的FrozenMap键取 typed外部对象，成功后 `0x1409D0E19` 读其 `+0x50` 值；与容量表不同才进入同一上限/64对齐门，于 `0x1409D0E69` 写 `world+0x1258+8*kind`、置 `+0x1350` 脏并追加更新类别。缺失对象或值相同则返回。维护 scope 的 `0x1419531F3–0x14195321C` 检查/清脏后，把局部world容量数组交给 `nani_calculate_draw_list_params`，`0x1419532C9` 再调用 `set_draw_list_params`。因此“外部字段→容量表→重算”的条件静态链已回答；外部对象 `+0x50` 的全部生产端、实际执行频率、最终raw buffer容量、分配失败及GPU越界保护仍Unknown。该同步路径没有直接调用上述通用setter，而是内联同样的检查/写入职责。

## cull 到 fill 的同一逻辑视图

令 `C` 为 `gpu_generate_draw_lists` 栈帧的 rbp，不能与被调函数的 rbp 混用。`0x1409B6A81–0x1409B6AD4` 构造指针集合：`[C+0x1D8]=&[C+0x20]`，并保存后续其它图视图。屋瓦调用前 `0x1409B7511–0x1409B757A` 构造 cull 参数；fill 的第 9 实参在 `0x1409B81AB–0x1409B81B2` 为 `C+0x1C0`。沿 [108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md) 的两个 CPU 特化和本轮 binder，得到：

| 数据          | cull 参数                           | sorted fill 参数                                 | 共同的逻辑 RG 视图地址 |
| ------------- | ----------------------------------- | ------------------------------------------------ | ---------------------- |
| filtered 编码 | context `+8`，由 `[C+0x1D8]` 取得   | fill 集合 `+0x18` 读出，再放 shader 参数 `+0x10` | `C+0x20`               |
| meta 分类     | context `+0x18`，直接指向 `C+0x24C` | fill 集合基址 `+0x8C`，放 shader 参数 `+0x18`    | `C+0x24C`              |

屋瓦/填充的 ComputeNode wrapper 分别在 `0x14178DEA1–0x14178DF06`、`0x141791BD3–0x141791C10` 按字段复制参数后调用实际 shader binder；实际 binder 在 `0x14090CD93/0x14090CF63` 与 `0x140C3337F/0x140C33458` 读取上述字段，并从图视图 `+0x10` 取 resource access 身份。因而这一步已超出“名称相同”的推断：两个入口收到同一对视图对象。fill 新建的 20 B 视图又在 `0x1418C2CC3–0x1418C2CDA` 写回 caller 的 `C+0x280`，caller 于 `0x1409B854F–0x1409B856A` 将其作为第 5 实参交给 draw-list 生成入口。

逻辑 RG 视图、图访问版本、Vulkan buffer 和 raw handle 是不同层。这里没有恢复图分配器的全部重映射与复用、生成器到 vertex/最终 draw 的完整字段链，也没有观察 GPU backing。特别是 caller 的 `C+0xC0` 在 `0x1409B807F` 后被另一个资源覆盖，不能只因栈偏移相同就连成同一对象。

## 算例、验证和停止点

构造 fresh atlas 使 meta1 指向第二份 `roof_tile_lod1`；输入候选通过 [106](106-tiny-glade-distance-detail-and-budgets.md) 的距离/HZB 条件后，经共同视图交给 [108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md) 的填充公式，低位成为 mesh_index1。若 kind6 的表从 65,536 改为 65,600，所见 setter 因 `65600<=1048576` 且 `65600%64=0` 接受并置脏；65,537 不满足对齐，1,048,640 超过上限。若 fine 回调仍走普通 kind>=2 分支，其单次命令上限仍为 1024。这些是控制流/算术演算，不是运行扩容、实际 draw 或视觉收益。

**Answered（静态）**：RoofTile=6、容量表初始化、类型键绑定及通用/外部同步 writer、所见变更分支的限制、cull/fill 两资源的共同逻辑视图。**Partial**：默认 fresh atlas 的三资源条件映射、fill 输出向生成入口传递。**Unknown**：重载后的部件实际编号、外部池+0x50的完整生产者/最终容量、图到最终物理 buffer/vertex/draw 的完整绑定及实际帧预算。预算探针重读、原生锚点、参数地址链、错误 profile 拒绝与 UTF-16 JSON 码元保留以本轮 focused 回执为准。游戏/Unity/GPU/附加、目标函数执行、私人存档和旧 Ghidra 重试全部 **Not Run**。
