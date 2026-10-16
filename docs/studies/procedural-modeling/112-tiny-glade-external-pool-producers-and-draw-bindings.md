# Tiny Glade：屋瓦外部池容量生产者与绘制绑定

接续 [110](110-tiny-glade-roof-atlas-budget-and-graph-views.md)。本轮把外部对象 `+0x50` 接到 **SparseInstanceBuffer<RoofTileSsbo> 的构造及 gpu_flush 成功写端**：初始 65,536 项，8 页，每页 8,192 项、每项 64 B；所见 writer 按页数翻倍并以 128 页表为上界。另接通 kind6 的外部 raw getter、屋瓦材质数据、管线名称及 coarse/fine 回调选择。这里的容量是可容纳项数；分配请求、图资源版本和实际绘制数分别记录。

## 身份、方法与覆盖

输入仍为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B）和 `tiny_glade.pdb`（310,513,664 B），沿用 [70](70-tiny-glade-update-and-render-costs.md) 的 PE/PDB 配对，首选基址 `0x140000000`。本轮未新算摘要，未启动目标。新原文在 ignored `.cache/procedural-modeling/static-producer-followup/tiny-glade/`；普通 PDB、PE 和 dumpbin 输出不是 REA Evidence。

`sparse-roof-symbols.json` 的 `*SparseInstanceBuffer*RoofTile*` 枚举 20 个候选、去重后19条；`roof-buffer-symbols.json` 在 `*ssbo*` 3563 个候选中接受3条；`nani-draw-symbols.json` 在1968个候选中接受65条、去重64条，以上查询均 exhausted。这只是指定掩码与过滤器覆盖。[RIP LEA 探针](tiny-glade/tools/pe_rip_lea_probe.py)及既有 E8 探针分别扫描唯一文件支持的 `.text` 48,438,230 B，只给出候选，本文引用站点另以 dumpbin 指令边界核对。[生产者探针](tiny-glade/tools/external_pool_probe.py)检查27组指令锚点并读取容量、键字面量与分发表；不模拟函数，不读取活动进程。

## 容量从 CPU 页数到 GPU 请求

PDB 定位的屋瓦 `new_storage_buffer` 为 `0x141A78470`、2101 B，空输入路径先为128项页表准备存储 (`0x141A784D4`)，并初始化前8个页记录（24 B stride、到 `0xC0` 结束，每页独立分配 `0x80000` B）。`0x141A78824` 明确写外部对象 `+0x50=0x10000`，`0x141A78878` 写 `+0x78=8`；`+0x28/+0x30` 保留页表指针和长度。原始 GPU 请求独立核对：构造在 `0x141A78789` 调 `TypedStorageBuffer::new` (`0x141B0E540`)，空数据路径 `0x141B0E5AF–0x141B0E5F4` 以 **4,194,304 B**、alignment4 建 buffer，成功 handle 在 `0x141A78821` 写对象首 qword。这与 `8×8192×64` 相符，不能由容量字段本身代替该字节描述符证明。

页数后写端有具体别名链。`assemble_roof_tiles` (`0x141F46490`) 取得 typed 屋瓦池后，在 `0x141F46A2E` 取 `&pool[0x78]`，`0x141F46A54` 写到 writer 的 `+0x38`（writer基址为此函数 `rbp-0x10`）；同一 writer 从 `pool+0x28/+0x30` 取得页表指针及长度。`SparseInstanceBufferWriter::push<RoofTileSsbo>` (`0x141F49FD0`) 在 `0x141F4A11D–0x141F4A13A` 沿此别名读旧已分配页数 `p`，候选为 **min(2p, 页表长度)**。若没有新增页则返回该分支，不突破固定表；新增页逐份分配/清零 524,288 B、初始化 OnceLock 后，`0x141F4A32C` 经原指针写新 `p`。这既不是 `+0x50` 的直接写，也不是每新增一片瓦就重新分配 GPU。装饰屋瓦另一个 push 特化 `0x1414A9F00` 有相同字段/翻倍机制；本文未穷尽所有构造和任意别名写端。

`gpu_flush<RoofTileSsbo>` (`0x141F482C0`、7440 B) 才把 CPU 已分配范围变成 GPU 容量：

| 阶段       | 指令位置                  | 所见行为                                                                       |
| ---------- | ------------------------- | ------------------------------------------------------------------------------ |
| 候选项数   | `0x141F488E4–0x141F488F7` | 读 `pool+0x78`，左移13位为 `candidate=p×8192`；`candidate<=pool+0x50` 跳过新建 |
| 新字节请求 | `0x141F488FD–0x141F48942` | 另以 `p<<19` 为 BufferDesc 长度，alignment4，调用 create_buffer                |
| 成功门     | `0x141F48956–0x141F4895A` | 结果tag为 `0x0B` 才进入替换路径；失败进入日志/错误清理路径                     |
| 替换与发布 | `0x141F48A5E–0x141F48A79` | 释放本池旧 raw 引用，首 qword换新 handle，随后 `+0x50=candidate`               |
| 内容上传   | `0x141F49358–0x141F4947C` | 将脏区间按8192项页界切分，使用页基址与 `page_index<<19` 字节偏移调用范围上传   |

成功替换后 `0x141F48A7D–0x141F48EEF` 将分配区位图合入待写位图，所见路径会重新提交相应影子内容；没有静态证据证明 GPU 原内容会自动保留。失败路径绕过首 qword/容量两次 store，清理后回到 `0x141F48EF1`，后续仍以旧容量限制所处理范围。不能把 CPU 页数增长当作 GPU 扩容成功，也未证明显存失败时所有待上传内容的重试与可见恢复。

在本构造/本 writer 路径中，可构造 `8→16→32→64→128` 页，对应容量 `65,536→131,072→262,144→524,288→1,048,576` 项，成功 GPU 请求 `4→8→16→32→64 MiB`。128页时再次计算仍是128，不再新增页。它与 [110](110-tiny-glade-roof-atlas-budget-and-graph-views.md) 的1,048,576同步上限相符；这不是所有会话的最终占用，也没有排除未查路径改页表。

## 两个库入口确实取同一类型键

屋瓦生成/flush 的名称查找使用字面量地址 `0x143432200`；容量同步、cull、typed图读和外部描述符使用 `0x14331C898`。两处**已存16 B 字面量相同**：`9950700d5939d913e142ab0b2961163d`，这里只比较文件字节，没有计算内容指纹。生成入口 `0x141F467B8–0x141F467D9` 经同键及 vtable+18取得 pool，flush caller `0x141F350A4–0x141F350E0` 经同键、可变 vtable+20交给已命名的 RoofTile gpu_flush。因此不同常量地址或不同 FrozenMap 特化不能被误写成两个无关池。

[110](110-tiny-glade-roof-atlas-budget-and-graph-views.md) 已证的维护 scope 读 `pool+0x50`、同步 world容量表并置脏重算，因而现在可连接 **writer页数→flush成功换raw及+0x50→外部同步→GpuWorld draw-list参数**。外层 `nani_frame_boundary_maintenance` (`0x140962570`) 在 `0x140962969` 调该 scope。所见入口存在不证明某一帧 flush 与图导入之间的实际先后。

## kind6 到当前 raw、屋瓦材质与回调

启动分发表 `0x143032DC0` 的第6项是 `0x14095E130`。`startup_nani` 在 `0x1409E52B3–0x1409E52D5` 以 kind×8索引此表，返回的152 B子集描述符在 `0x1409E51D0–0x1409E51DE` 拷入 `world+0x40+160*kind`。屋瓦构造小函数写外部标记和 getter `0x14095DBE0`；getter (`0x14095DBE4–0x14095DC18`) 使用上述同键找到当前 typed对象，读其**当前首 qword**并增加raw引用。所以它在被调用时取池当时的 handle，并未永久捕获初始4 MiB handle。

`nani_on_scene_load` 的两张 kind表在第6项给出长度32、名称 **`country_core/nani_instanced_roof`**，`0x1409E5951` 用它取管线。`update_world_subset_material_args` 在外部描述符分支 `0x1409E6B15–0x1409E6B1C` 调 getter，保留其raw引用到局部 `+0x90`；其相对跳转表 `0x1430330A0` 第6项落 `0x1409E7561`，取得 `roof/roof_tile_damage` 与 `roof/roof_tile_normal` 两纹理。`0x1409E75A0–0x1409E75F2` 把 **raw引用、damage、normal** 依次作为 `nani_instanced_roof::MaterialData` 交给 `update_binding_set`，调用中的binding set索引为1。PDB明确将 `0x141563930` 标为这个具体 MaterialData 特化；`0x141563B4D–0x141563BF2` 顺序调用 `RawBinder::read_buf`、两次 `read_tex`，buffer偏移参数为0。精确 shader binding编号与最终 descriptor/GPU记录仍未由这三次调用单独恢复。

扩容后的材质也有静态刷新入口：`refresh_material_args` 的 fold `0x1419B06D0` 遍历 `(Entity,kind,BindingSet)`，克隆 binding set 后，在 `0x1419B080E–0x1419B0842` 再调上述材质函数；frame维护的 `0x1409638A0` 创建这批结果，`0x140963A29–0x140963A96` 检查实体/组件、更新changed tick、释放旧引用并写回新binding set。这里已见当前raw重取和组件替换；**变更类别队列到每个待刷新实体的完整筛选、图访问版本及本帧可见性仍Partial**。

回调选择也有直接指令。场景加载遍历 kind0…28，成功找到atlas且描述符/管线满足门才创建drawable。`0x1409E5AA4–0x1409E5AD4` 的规则是：`FORCE_FINE!=0` 选 fine；否则 `kind>1` 选 coarse；其余类别再检查 `FORCE_NO_FINE`。因此 **RoofTile=6 且 FORCE_FINE=0 时选 coarse_sorted_draw_fn** (`0x1409E64E0`)，与 FORCE_NO_FINE 无关；强制fine才选 `0x1409E5FA0`。`0x1409E5B40/0x1409E5B56` 把函数指针和同kind写入即将spawn的drawable。两开关本轮定位到非文件支持地址，保留实际值Unknown。此前 [110](110-tiny-glade-roof-atlas-budget-and-graph-views.md) 的1024是**假设进入fine后的条件上限**，不能据此称普通屋瓦就是fine/count调用。

coarse回调 `0x1409E68AA` 从 NaniDrawListSsbo取得逻辑图视图，`0x1409E696B–0x1409E6987` 绑定对应atlas的vertex/index资源，`0x1409E69C4–0x1409E69D3` 按命令起始号×20 B偏移调用 `draw_indirect`，之后finish_read。这将已确认的屋瓦管线、材质raw与实际选定draw入口接近一层；[108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md) 的 generate→indirection→vertex **全套逻辑视图同一性、所有公共set与图分配器的物理重映射仍未闭合**，不能宣布最终GPU backing全部确认。

## 算例、复核和剩余缺口

条件演算：池在8页/65,536容量时，writer用尽已初始化范围且仍有页表空间，候选16页。若 flush 创建8 MiB成功，先替换首 qword再写131,072容量；维护同步看到变化后更新kind6并重算。随后材质getter若执行，会取新handle。若分配失败，所见路径保留旧handle和65,536容量；若强制fine为0，drawable仍选coarse，其命令数量需按对应子列表参数另算。以上没有执行目标函数。

**Answered（静态）**：外部容量构造/flush写端、页数别名及所见翻倍上界、真实字节请求、同键对象链、kind6的外部getter、管线与MaterialData、回调选择及coarse最终调用。**Partial**：刷新实体筛选和时序、generate到全部公共/vertex图视图、shader编号及最终descriptor。**Unknown**：实际开关/帧容量、所有其它写者、分配失败后的完整重试与GPU安全、真实绘制量和性能收益。新探针重读、错误输入拒绝和页数/字节演算见本轮 focused 回执。初次读取非文件支持开关地址失败，后将缺失明确保留为Unknown；未据此造初始化值。目标启动/附加/函数/GPU执行、私人存档、软件安装和不变条件Ghidra重试均 **Not Run**。
