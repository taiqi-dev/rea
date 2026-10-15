# 掘地求财：重复更新、任务寿命与长期增长边界

本篇续查[03 调度与预算](03-performance-and-independent-design.md)留下的两个问题：连续挖同一块会不会排出一串并行重建，旧网格/碰撞结果如何失效；长期挖掘的成本更接近编辑次数，还是已修改叶块及当前活跃任务数。答案只对本版已编入的 Voxel 插件原生路径成立，**不是本作 VoxelWorld 运行配置或FPS观察**。游戏角色的`Dig → SurfaceEdit → EditVoxelValuesAsync`字节码连接、爆炸的`RemoveSphere`入口见[01](01-excavation-and-local-rebuild.md)；实际每铲覆盖哪些chunk、选择哪种mesh handler/碰撞设置仍未知。

## 身份和方法

目标仍是`C:\Software\Steam\steamapps\common\A Game About Digging A Hole\DiggingGame\Binaries\Win64\DiggingGame-Win64-Shipping.exe`（145,180,160B，SHA256 `8356c03affeaa4a08fc92e52fdac6feb3a69cbd7b90fe96d67c3db9e83e6200a`），同目录PDB为1,659,662,336B、SHA256 `4c224da4242d2ace8a88cf156fe136f358b6b44f12b941d35419dfc202ade7d5`；原EXE/PDB GUID+age核对及包身份见[00](00-evidence-and-reproduction.md)。本轮以`tools/pdb_probe.py`显式EXE路径和本地PDB掩码定位，再用现有VS2022 `dumpbin /DISASM /RANGE`读取原生指令，不执行或附加游戏。新增有界原文和符号结果在忽略目录`.cache/procedural-modeling/digging-a-hole/performance-followup/`，包括`symbols.json`、`cancel-symbols.json`及下述同名`.txt`。`*FVoxelDefaultRenderer*`返回79/79、`*FVoxelAsyncPhysicsCooker*`返回6/6，均为完整枚举；宽泛`*FVoxelDataOctree*`受800项上限截断，**不据它作全类否定断言**。

## 1. 同一chunk的通知会追加记录，但任务入口有占用门

`0x143EF53B0 FVoxelDefaultRenderer::UpdateChunks`对输入chunk key做`TSet<TTuple<uint64,FChunk>>`散列查找：`0x143EF54C3–0x143EF552F`使用64位键寻找对应`FChunk`，随后按每个命中的键构造`FPendingUpdate`。`0x143EF566A–0x143EF569E`给该chunk的pending数组长度加1，必要时调用`ResizeGrow`，以**32B步长**定位并构造新记录；`0x143EF56C3 / 0x143EF56CE`尝试两个`StartTask`入口。散列查找保留chunk身份，不等于每次通知都启动一份新任务。记录的时间值和委托业务含义尚未完整命名。

`0x143EC4F70 StartTask<1,0>`在`0x143EC4F78–0x143EC4F87`先检查`FChunk+0x30`任务指针；非零便跳到退出段，不再构造另一份同类`FVoxelMesherAsyncWork`。另一个`StartTask<0,0>`对应chunk内另一任务槽（见[01](01-excavation-and-local-rebuild.md)的定位），不应把两个槽混成单一任务。启动路径会分配`0xE0`字节任务对象（`0x143EC512A`），在`0x143EC515D`调用mesher构造，再把指针存入槽并排入后台工作；若需要替换旧指针，`0x143EC517E–0x143EC518F`有等待旧工作退出和析构路径。**已占槽时的直接返回并不删除刚追加的pending记录，也不表示正在运行的网格计算被即时取消。**

新查的`0x143ED3770 CheckPendingUpdates`给出排队记录的后续寿命：它逐条检查当前chunk的pending（`0x143ED3785 / 0x143ED38B3`），把chunk的`+0x40 / +0x48`两个double值与当前pending记录首字段比较，条件允许时再调用两类`StartTask`（`0x143ED37D3–0x143ED3802`）。当两值的较小值仍大于记录首字段时，进入其委托/回调循环（`0x143ED3816–0x143ED3878`），并在`0x143ED3892`调用`RemoveAtSwapImpl`、`0x143ED389A`调用`ResizeShrink`。`0x143EED4BF ProcessMeshUpdates`实际调用此函数。因此重复请求可能先在**每chunk的记录数组**中积累，后由完成消费路径删除；不能把它说成入队处“同key合并为一条”，也不能在未恢复这些数值的正式语义时声称固定几帧内删完。单位记录检查至少随该chunk当前pending数量增长。

## 2. 完成结果必须匹配现存chunk与任务令牌

`0x143EED040 ProcessMeshUpdates`从完成队列取一项（`0x143EED0D0–0x143EED122`），减等待计数，随后用完成记录中的64位chunk key查同一个`TSet`（`0x143EED13F–0x143EED1B5`）。找不到该key便跳过本项。找到后根据完成记录的类别选择`FChunk+0x28`或`+0x30`任务槽（`0x143EED1CD–0x143EED1DF`）；槽为空亦跳过。`0x143EED1F0–0x143EED1F4`又把槽中任务对象的`+0x68` 64位令牌与完成记录另一64位值比较，不等便跳过。只有通过这些条件才在`0x143EED1FC`对任务状态做原子交换，随后进入旧任务回收、结果与mesh handler分支，选定路径于`0x143EED451`调用`RemoveChunk`或于`0x143EED462 → 0x143ECDA50`进入`UpdateChunk`委托；`0x143EED4BF`再处理pending。此处是**chunk key + 当下槽内任务令牌**的提交门，足以解释已移除chunk或槽被替换后的旧完成项为何不能直接按旧键提交；`+0x68`的正式类型、是否等于编辑版本号仍未证明。

`0x143EDA8D0 DestroyChunk`在移除chunk前分别检查`+0x28 / +0x30`，非空便调用`FVoxelAsyncWork::CancelAndAutodelete`并清槽（`0x143EDA8E3–0x143EDA92D`）；若返回false，还会相应减少内部任务计数。它继续遍历该chunk pending委托并广播清理，再于`0x143EDAA49`按chunk key调用`TSet.Remove`。`0x143EC8FF0 FChunk::~FChunk`实际析构pending记录/其堆数组及`FChunkBuiltData`，且剩余两个任务槽非空时调用`WaitForDoThreadedWorkToExit`和虚表析构（`0x143EC9042–0x143EC907D`）。这说明清理有所有权路径，也暴露**可能等待后台工作结束**的成本；取消请求不能被解释成硬中断，也不能保证每次移除都不阻塞。

`0x143E64140 CancelAndAutodelete`自身在临界区内设置取消/自删除相关状态（`0x143E64151–0x143E64176`），根据原子任务状态走不同返回分支：`0x143E6417A–0x143E64192`可经虚表`+0x28`回收并返回true，另一支`0x143E6419F–0x143E641AA`返回false。故上面`DestroyChunk`显式区分返回值合理；但该函数没有证明运行中的mesher立刻停算，真正等待要看生命周期和工作循环。

## 3. 碰撞烹制有另一套旧工作处理

`0x143EF5A40 UVoxelProceduralMeshComponent::UpdateCollision`先检查世界及全局冻结开关。冻结时`0x143EF5A80–0x143EF5AB4`把组件弱引用放进`PendingCollisions`集合并返回；这是延后入口，不是本作运行中冻结已开启。非冻结路径在`0x143EF5AB9–0x143EF5AD2`对`component+0x580`旧cook任务调用`CancelAndAutodelete`并清指针，随后取得/创建`BodySetup`、`0x143EF5B5C`清旧physics mesh。若所查section不要求碰撞，`0x143EF5BAF`直接`FinishCollisionUpdate`；另一支`0x143EF5C17–0x143EF5C66`分配`0x140`字节`FVoxelAsyncPhysicsCooker_Chaos`并排入工作，记录新指针。实际数据结构/配置决定选哪支，不能把“已编入的异步cook”写成每铲必用。

`0x143ED5AF0 CookMesh`先测试状态`[task+0x8C]==2`则返回；否则按输入section数组（每项16B指针/引用）线性累计两种计数（`0x143ED5B01–0x143ED5B55`），再按第二计数是否小于`0xFFFF`选16/32位索引的三角网格构建入口（`0x143ED5B84–0x143ED5B99`）。`0x143EDD7F0 Finalize`遍历生成的网格引用、清其状态位，把结果转移到BodySetup的数组，并在`0x143EDD86F`设置BodySetup状态字节；实际何时由组件接受及`RecreatePhysicsState`见[01](01-excavation-and-local-rebuild.md)。CPU成本至少与输入section及其顶点/三角形规模相关，不由一次体素编辑数直接决定；`CancelAndAutodelete`的false分支意味着旧工作仍可能占用CPU/内存直到自身退场，当前证据没有测到同时在飞数量或竞态完成顺序。

## 4. 连续编辑的增长不是一个量

长期持久化基底来自[02](02-save-load-and-consistency.md)：`FVoxelData::GetSave`遍历数据树；`0x143E8B860 FVoxelSaveBuilder::Save`在`0x143E8B930–0x143E8B9A7`按叶子value/material修改状态计数，并于`0x143E8B9B0 / 0x143E8BA23`按每份**4,096个元素**分配保存数组，再复制被选叶块。相同叶块反复编辑，在一次快照中仍按当前修改叶块计，而不是把每铲写成一条永久mesh/编辑日志；新触及的不同叶块、材质块会增加该快照的遍历、复制、未压缩数据及后续压缩输入。完整保存还有全域读锁、未压缩对象、序列化缓冲和压缩输出，峰值内存不能只按压缩文件大小估算。4,096是数组元素数，不能未核元素宽度就直接报4,096B。

另一端，活跃渲染对象按`FChunk` key持有pending数组、最多两个已见任务槽、built-data引用及组件产物；本轮证明了移除时的清理/等待路径，但没有量出容器保留容量、全部mesh/碰撞组件池策略或加载几小时后的堆碎片。定义`C`为本次受影响chunk数、`R_c`为处理前某chunk累积pending通知数、`M_v/M_m`为存档中值/材质修改叶块数、`S`为某组件需要烹制的section数。当前静态路径给出：通知查找及构造随`C`增长；该chunk的pending扫描/委托可能随`R_c`增长；mesh生成取决于该chunk的采样/几何量；cook先随`S`汇总、再随实际几何量增长；快照会遍历数据树并至少处理`4096M_v + 4096M_m`个相应类型的叶块元素。这些不是统一的大O性能模型，且未含UE allocator、压缩比、工作并行及GPU提交成本。

**构造演算，非游戏运行**：连续10次编辑都影响同一有效chunk X，期间没有`ProcessMeshUpdates`消费，且X的两个任务槽已有工作。`UpdateChunks`的选定路径可追加10个32B pending记录，即至少320B记录体；`StartTask`看到非空槽不额外构造10份同类任务。之后若一次旧完成项的chunk key仍为X但任务令牌已不等于X当前槽，`ProcessMeshUpdates`跳过该项，不将它当当前mesh提交；pending记录是否在这次调用全部删除仍由时间/回调条件决定。另假设10次编辑只涉及两个不同value叶块和一个material叶块：一次保存的数组元素基数为`2×4096`个value加`1×4096`个material，而非10份相同叶块。若碰撞组件两次更新间旧cook返回false，后一次可排新cook，但旧CPU工作何时停止、两份瞬时内存是否重叠未知。

自研实现可独立设计更强的按chunk版本归并：请求只保留当前目标版本、完成提交核版本与chunk生命周期、碰撞也带版本，给pending长度及在飞任务设置可观察上界。为测长期增长，应同时记录唯一修改叶块数、每chunk pending峰值、在飞mesh/cook任务、丢弃旧结果数、等待耗时、mesh/碰撞容量和快照峰值，而非只看每铲FPS。此为设计建议，**不归属原游戏**。

## 验证与未决

本轮已按PDB精确地址/大小读取`UpdateChunks`、`CheckPendingUpdates`、`ProcessMeshUpdates`、`StartTask`、`DestroyChunk`、`FChunk`及built-data析构、`CancelAndAutodelete`、`UpdateCollision`、`CookMesh`、`Finalize`。原文保存在上述ignored缓存；函数名定位与条件/调用来自对应EXE指令。旧[02](02-save-load-and-consistency.md)的保存计数重新用`save-builder.disasm.txt`核对。**Not Run**：游戏运行/附加、VoxelWorld实际分支与配置、真实连续挖掘、线程/碰撞/内存/FPS分析、私人存档读取。仍未知：重复通知在所有上游是否已去重、具体时间阈值与回调语义、任务令牌的正式定义、跨世界重建时chunk key的作用域、旧cook结果最终接受检查，以及长期稳定内存曲线。故本文能给插件代码的寿命门与增长变量，不能声称本作默认设置或实测性能。
