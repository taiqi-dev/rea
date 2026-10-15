# Tiny Glade 局部更新与绘制列表成本

本篇回答一个范围明确的问题：一次或多次建筑编辑改变了哪些CPU对象与GPU实例；已有实例又怎样进入可见性筛选和绘制列表。静态证据支持**按语义对象重建产物**与**按当前候选集合生成绘制列表**两种不同粒度，不能把后者缩成“只检查刚编辑的砖”，也不能据函数存在声称每个游戏帧必然执行。本篇成本是由循环、记录宽度和着色器工作组推出的规模关系，**不是FPS或实测耗时**。

既有[共享失效](45-tiny-glade-shared-invalidation-and-rebuild.md)、[屋顶消息](50-tiny-glade-roof-edit-messages-and-regeneration.md)、[编辑到实例上传](55-tiny-glade-edit-rebuild-stages-and-upload.md)、[屋瓦GPU可见性](49-tiny-glade-roof-gpu-visibility-and-depth.md)、[植被active-list](51-tiny-glade-vegetation-counts-and-active-list-rebuild.md)及[历史回放](62-tiny-glade-history-snapshots-and-regeneration.md)给出各生产者边界。本篇新增CPU绘制编排、派生buffer初始化和选定墙/通用实例compute指令。资产身份与独立建筑资产边界见[67](67-tiny-glade-building-assets-and-assembly-ledger.md)。

## 身份与证据边界

本轮输入为`C:\Software\Steam\steamapps\common\Tiny Glade\tiny-glade.exe`（65,612,184B，SHA256 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`）及同目录`tiny_glade.pdb`（310,513,664B，SHA256 `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2`）。摘要复用本轮已授权且确认一致的`.cache/procedural-modeling/followup-art-updates/identity.json`，未把旧机器缓存当成当前文件。地址是EXE的preferred VA；shader位置是各`.precomp`原文件偏移，二者不可互换。

用正式`digging-a-hole/tools/pdb_probe.py`的显式路径/掩码定位函数，再用现有VS2022 `dumpbin /DISASM /RANGE`读取下述七段原生指令。六份发行目录内precomp由本轮共用`tools/spirv_probe.py`和缓存的SPIR-V grammar做结构解码；6包、8内嵌模块均结构完整且无rejected模块。grammar来源与固定版本见`.cache/procedural-modeling/followup-art-updates/grammar-source.json`。分析没有运行目标、附加、GPU抓帧或读私人存档；这里没有REA MCP Evidence/session，也没有SPIR-V语义验证或驱动行为观察。

可复查的本机投影保留在`.cache/procedural-modeling/followup-art-updates/tiny-updates/`：`wall-symbols.json`的精确掩码返回17/17且枚举完毕，`upload-symbols.json`返回1/1；七份`params/upload/generate/wall/wall2/shadow/setparams.txt`是上述函数有界反汇编，六份`wall/wall2/wallprefix/nani/clear/allocate-spv.json`保留完整解码指令。它们是ignored研究缓存，不是可分发的原游戏代码。

## 1. 编辑侧：更新范围有对象身份

已核实的建筑编辑路径有三个不同边界：

| 输入与原生锚点                                                                                                                               | 状态变化                                                                                                 | 工作范围与输出                                                                                                                                             |
| -------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 墙组移动：`B47F40 WallGroupTransformCache.apply`至`B48246 → 92F410 InnerWalls._try_update_state`                                             | 有效WallID的新状态替换旧状态，`92F5CE–92F5DD`把ID插入`InnerWalls+60`集合                                 | 同一ID重复标记合并；不是所有墙都直接重写。见[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)。                                                        |
| 道路/高度等栅格影响：`B9F450 publish_public_wall_state`                                                                                      | dirty tile查空间bucket，相关WallID去重并检查资格；`BA0925–BA094E`写`OnWallChanged`，随后处理旧PublicWall | 成本取决于脏tile及其关联候选数，而非全场景墙数；消息入队不等于消费者已经完成。8×8 tile的内容过滤见[45](45-tiny-glade-shared-invalidation-and-rebuild.md)。 |
| 墙变化关联屋顶：`280E724–280E7C3 update_roof_spatial`，重算消息在`280E986–280E9E6`、`280EAF1–280EB69`；`1F469AF–1F46A7C assemble_roof_tiles` | 选定屋顶的`RoofTiles`旧稀疏索引由`1F4A6C0 clear`回收，再按当前屋顶生成                                   | 粒度是收到消息且通过条件的屋顶，不是逐瓦局部差量，也不是证明每条墙消息都重铺瓦。见[50](50-tiny-glade-roof-edit-messages-and-regeneration.md)。             |

普通墙显示在`BD7C70 gpu_flush_brick_buffers`为选定`InstancedWall`经`94C360 upload_to_storage_buffer`清旧allocation，按64B记录调用`1A77830 push<BrickTransformSsbo>`，随后走`1A76DD3 / 1A76E69 gpu_write_ranges_nonoverlapping<BrickTransformSsbo>`。因此选定对象的新砖数为`b`时，CPU记录消费至少随`b`增长，payload为`64b`字节；物理上传范围、分配碎片与GPU完成仍由下游决定。旧slot可回收并重新分配，不能用slot冒充WallID。屋瓦、植被各有不同owner和清零/生成过程；[51](51-tiny-glade-vegetation-counts-and-active-list-rebuild.md)的23条、460B indirect模板不能直接归到墙砖。

`93E620 add_stages`建出的GameSystemSet图把`WallGenerators=0x13`、`WallVisualGenerators=0x1C`、`RoofAssemble=0x1D`、`PrepareRendering=0x2C`置于静态依赖骨架中（见[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)）。未恢复各函数的完整`run_if`、deferred屏障或实际帧时间线；这些名称不提供“编辑后本帧完成”的证据。

## 2. 派生buffer与绘制参数有独立的规模成本

`0x1409620E0 nani_upload_derived_buffers`并不是上述单墙64B记录的上传函数。它读取输入`+0x64`的u32数量`D`（`0x14096210D`），在非零分支按`D×20`字节分配并清零20B记录（`0x14096211A–0x140962223`），`0x14096224D`传给`AssetSsboLibrary.replace_with_data`。随后从`+0x60`读另一个u32数量`I`（`0x140962279`），按`4I`字节清零并在`0x1409622FF`替换；`0x140962327`把该数右移5位，按`4⌊I/32⌋`字节建立两份零buffer（`0x140962378 / 0x140962392`）。最后`0x14096239F–0x1409623F5`清零并替换一份固定`0x220=544`字节表。字段的业务名与调用频率未独立证实；指令说明**调用此函数时**至少有这些随数量增长的CPU初始化和replace入口，不能称为每次编辑必然复制全部实例。

`0x1409D3120 GpuWorld::set_draw_list_params`在传入列表长度`P=[rdx+0x10]`非零时，`0x1409D3161–0x1409D3176`申请`4P`字节，`0x1409D31B0–0x1409D3225`复制P个u32，`0x1409D324C`与目标buffer容量比较，通过后`0x1409D3296`调用`GraphicsDevice.update_buffer_bytes`。越容量有独立失败分支。故一次有效调用的主机复制为`O(P)`、此块请求写入`4P`字节；调用者何时改变P、驱动何时完成写入尚未知。

`0x140948130 nani_calculate_draw_list_params`的PDB身份与1,678B范围已定位，函数内部有多个集合增长入口；本篇没有建立它的每个输入字段与`set_draw_list_params`的精确调用桥，因此不把二者说成单次编辑的一条已证链。

## 3. 绘制侧：编排、筛选、计数、间接列表

`0x1409B6690 gpu_generate_draw_lists`长9,096B，选定直接call显示它编排多段工作：`0x1409B6AF6 clear_draw_lists`、`0x1409B6BEE prepare_empty_unsorted_draw_lists`；之后`0x1409B75B6 / 0x1409B7613 / 0x1409B7991`三次调用同名的`cull_and_bucket_external`不同实例；`0x1409B81F9 fill_instance_lists`、`0x1409B820A clear_draw_lists`、`0x1409B84B1 prefix_sum_unsorted_instances_per_atlas_entry`、`0x1409B84F7 allocate_draw_lists`、`0x1409B8523 group_draw_cmd_prefix_sum`、`0x1409B856A generate_draw_lists`。这些是实际直接调用，不只函数名枚举；相关片段还在`0x1409B6F6D / 0x1409B6FC0`绑定compute/dispatch、`0x1409B744B`调`dispatch_indirect_with`。它说明一次进入该入口可能包含清零、筛选、统计、分配与写列表多个阶段；不说明入口每帧必运行，也不证明GPU已经执行完成。

墙列表另有`0x1409B91B0 generate_wall_draw_lists`（3,690B）、`0x1409BA020 generate_wall_draw_lists_pass2`（1,456B）、`0x1409BA5D0 generate_wall_draw_lists_shadow`（1,048B）。首函数`0x1409B937F / 0x1409B97E1`登记buffer clear，后段多次compute bind/dispatch；pass2入口的`[rdx+0x88]==0`可跳过主要路径（`0x1409BA04D–0x1409BA055`），并在`0x1409BA32E`清buffer，`0x1409BA2D7 / 0x1409BA314`及`0x1409BA414 / 0x1409BA42C`绑定/dispatch；shadow在`0x1409BA863 / 0x1409BA87B`绑定/dispatch。由此能说**条件满足且函数被调用时**存在另一个墙专用多pass成本，不能把这些call数乘作无条件每帧成本。`gpu_generate_draw_lists`的已检查直接调用列表没有通向上述三个墙函数的call；其共同上层调度与具体shader资源绑定尚未完整复原，以下同名precomp是一组有界的匹配证据，而非已证明的CPU→文件逐项绑定。

选定发行版shader结构提供下一级可观察操作：

| 原precomp（SPIR-V起始偏移；指令数；local size）                                                        | 可核指令与读写意义                                                                                                                                                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `wall/generate_draw_lists.precomp`（128；670；64）                                                     | 声明`brick_instance_data`、当前/前次visibility bitmask、chunk mask；原文件`11904 / 12720`有两次`OpAtomicOr`，并有barrier。这支持候选砖按位聚合/可见状态操作，不等于CPU逐砖循环。                                                                                                                                       |
| `wall/generate_draw_lists2.precomp`（130；846；64）                                                    | 四次`OpImageFetch`在`15394 / 15562 / 15730 / 15858`；`16242`取得`next_visibility_bitmask`目标、`16306 OpAtomicOr`写位；`16334–16374`读前次位并做AND；`17246 / 17274`对`draw_commands`中的计数做加1的`OpAtomicIAdd`，`17342 / 17366`向`brick_draw_list`写`instance_index`。分支条件存在，不能把所有候选都计成一个draw。 |
| `wall/prefix_brick_chunks.precomp`（120；340；512）                                                    | 名称和读写包含`all_lists_visible_brick_mask_in_chunk`、prefix和subtotals；这是按块统计/前缀，而不是局部几何重建的证据。                                                                                                                                                                                                |
| `nani/cull_and_bucket.precomp`（188/10786/24376；454/601/941；各64）                                   | 三模块分别有可见位及bucket atomic写、主视图四次HZB读取（`20958–21466`）与`21914 OpAtomicOr`、三层太阳视图共12次ImageFetch与六次AtomicIAdd。已核的屋瓦变体和深度公式见[49](49-tiny-glade-roof-gpu-visibility-and-depth.md)，不能把这些数直接外推到所有墙、屋顶和每次渲染。                                              |
| `nani/clear_draw_lists.precomp`（114；106；64）与`nani/allocate_draw_commands.precomp`（126；218；32） | 前者有3处Store清相关allocator/list长度；后者在`3182 / 3538`两次AtomicIAdd。与CPU的clear/allocate阶段功能一致，尚缺具体入口到文件的完整资源映射。                                                                                                                                                                       |

尤其`wall/generate_draw_lists2`的读写链显示：候选通过视图/HZB分支后，当前可见位可原子置位；部分条件分支再读取历史位、增加间接命令的instanceCount并写instance索引。前次可见位是筛选/避免重复的状态，**不是编辑dirty集合**。一面墙未编辑，若处于当前候选集，仍可参与视图筛选；一面墙刚编辑，若不在当前视图或对应dispatch覆盖范围，也不能保证实际进入draw list。所有模块的确切pass依赖、barrier与最终draw API提交尚未连通。

## 4. 小规模构造演算与成本变量

以下数值完全自造，只演示已证路径的规模，不是实机统计。一次批次内有效墙ID 7、8被修改，7又重复提交一次：`InnerWalls+60`的唯一键仍为`{7,8}`。假设两墙各自通过PublicWall资格，其中7关联屋顶A且形状差异满足重算分支：最多按这两个WallID通知选中消费者；A清旧索引后重铺瓦。假设墙7/8新的普通砖分别为3/2条，则这两个被选中的InstancedWall共消费`5×64=320B` CPU实例记录，并进入typed范围写入口；是否合并物理上传、还有多少屋瓦/窗口记录、GPU何时读到新内容都未知。

再**另设**一次render入口确实调用且墙shader候选量`A=130`：local size 64意味着覆盖这130个invocation至少需`⌈130/64⌉=3`个工作组，实际dispatch可能因padding、视图、LOD和分组多于此值；具体dispatch形状未由本篇确认。若这130个全部进入`generate_draw_lists2`的四角HZB分支，单模块对应最多`130×4=520`次所列`OpImageFetch`执行；实际会因前置分支而减少，也可能因多个pass/视图增加总量。5条新砖**不**把候选量自动缩成5。若在另一单独调用中`P=12`，`set_draw_list_params`该u32数组复制/请求写入为48B；这不把P解释成12次draw或12个砖。若`nani_upload_derived_buffers`的两个计数另取`D=10, I=64`，该函数的三类动态清零payload为`200+256+2×8=472B`，另有544B固定表；这是一次调用的CPU staging量，不是一个编辑的总GPU传输或显存占用。

用符号表达：语义dirty收集可受脏tile数`T`及其bucket关联总数`K`支配，去重后受影响墙数`W≤K`；被重建对象的新实例记录总数`B`使记录消费随`B`增长；进入某绘制调用的候选实例数`A`及列表/块数`L`决定GPU筛选、前缀和写列表规模。`W`可能远小于全世界墙数，但`A`不因此等于本次新增实例数。不同pass可以有各自的`A`与视图数。静态指令只能给出这些路径和上界形式，不能算出延迟、带宽、GPU占用或FPS。

## 5. 独立实现规格与未决

自研时可分别定义：稳定对象ID上的dirty归并；各产物owner按对象清旧重建、按类型上传；绘制入口依据当前视图对**当前活跃候选**独立筛选、计数、前缀与间接列表写入。需要自行设计buffer容量、帧资源与GPU同步、视图复用/失效规则和可量测指标，不应照搬目标的专有代码或shader。

已回答：选定墙/屋顶编辑的局部更新范围，选定实例上传记录宽度，选定绘制参数复制及多pass shader计数路径。部分回答：CPU墙pass与具体precomp逐项映射、GPU列表到最终draw提交。未知：各入口的实际帧频、run条件、所有建筑/植物统一调度、实际候选数量、buffer容量/同步、显存与GPU时长、FPS。没有运行目标或做性能测量；这些未知不能由静态复杂度替代。
