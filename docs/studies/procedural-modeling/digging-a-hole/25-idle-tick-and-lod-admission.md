# 掘地求财：无新挖掘时的 Tick 与 LOD 工作准入

本篇回答稳态帧仍执行什么、何时重算 LOD、空完成队列如何退出。结论属于这份发行 EXE 中的 **Voxel 插件静态控制流**，不等于游戏运行时耗时或帧率；此前重复编辑、旧结果接受和任务寿命已在 [05](05-task-lifetimes-growth-and-performance.md)说明，本篇不重查 LOD 0 的碰撞资格。

## 制品与证据边界

沿用 [00](00-evidence-and-reproduction.md)已核对 RSDS GUID/age 的 `C:\Software\Steam\steamapps\common\A Game About Digging A Hole\DiggingGame\Binaries\Win64\DiggingGame-Win64-Shipping.exe`（PE32+ x64，145,180,160 B，首选基址 `0x140000000`）及同目录 PDB；本篇未重算摘要。复用 [03](03-performance-and-independent-design.md)的 renderer Tick 和完成队列原文、[24](24-collision-box-producers-and-invokers.md)的 invoker 原文，并新增两个函数的定点 `dumpbin 14.44.35222.0 /DISASM /RANGE` 输出。新增原文、完整 PDB 符号掩码结果和 [validation.json](../../../../.cache/procedural-modeling/steady-performance-followup/digging-a-hole/validation.json) 在 ignored [steady-performance-followup/digging-a-hole/](../../../../.cache/procedural-modeling/steady-performance-followup/digging-a-hole/)；普通 PDB、PE 和 dumpbin 读取**不是 REA Evidence**。REA 会话检查为未打开目标；原先 Ghidra 导入超时的环境没有变化，所以未重试，也没有生成新的 REA Evidence ID。

## 空闲帧不是零工作

`FVoxelDefaultRenderer::Tick` (`0x143EF3890`) 先读性能计数器，将配置浮点数乘 `0.001` 形成截止时间，然后依次调用虚表 `+0x10`、`ProcessChunksToRemoveOrShow`、`ProcessMeshUpdates`、`FlushQueuedTasks` (`0x143EF38BD–0x143EF3926`)。前三者中的虚调用业务目标仍未定名。即使没有新挖掘，Tick 后段仍计算内存与队列统计，并以原子操作更新计数、调用 `ReportMeshTaskCount` 和 `ReportMeshTasksCallbacksQueueNum` (`0x143EF39E8–0x143EF3AC7`)。因此只能说**重活有空队列门**，不能说 renderer 停 Tick、零 CPU 成本或没有其他引擎成本。旧原文见 [renderer-tick.txt](../../../../.cache/procedural-modeling/digging-a-hole/performance/renderer-tick.txt)。

新增两段空路径更具体：`ProcessChunksToRemoveOrShow` (`0x143EEC550`) 取一次计数器后，先查 `renderer+0x268` 的待显示项数；`<=0` 跳到第二个 `renderer+0x258` 待移除项数检查，后者也 `<=0` 直接返回 (`0x143EEC599–0x143EEC5A0`、`0x143EEC7B3–0x143EEC8D1`)。数组非空才进入按时间、chunk key 和状态处理的循环；“无新挖掘”本身不保证这些数组已经排空。[新增原文](../../../../.cache/procedural-modeling/steady-performance-followup/digging-a-hole/process-chunks-to-remove-or-show.disasm.txt)。

`ProcessMeshUpdates` (`0x143EED040`) **先**取计数器与 deadline 比较，超时直接退出 (`0x143EED064–0x143EED08D`)；未超时才看完成链表头 `renderer+0x2F8`，头节点为空则跳到收尾 (`0x143EED0D0–0x143EED0DD`、`0x143EED562`)。链表有项时才弹出，并检查当前 chunk、任务槽指针与令牌，随后可能进入 mesh/过渡提交和 `CheckPendingUpdates`；旧结果门及 pending 的具体解释见 [05](05-task-lifetimes-growth-and-performance.md)。循环尾部再次比较 deadline (`0x143EED538–0x143EED55C`)。空队列仍有一次时间读取和链表检查；deadline 是工作单元之间的停止门，并非严格单帧耗时上限。[旧原文](../../../../.cache/procedural-modeling/digging-a-hole/performance/process-mesh-updates.txt)。

`FlushQueuedTasks` (`0x143EDFED0`) 顺序看四组数组的长度字段 `+0x278/+0x288/+0x298/+0x2A8` (`0x143EDFEEA`、`0x143EDFF2F`、`0x143EDFF74`、`0x143EDFFB9`)；每组 `<=0` 直接跳过对应提交调用。非空时才对 `+0x2C0` 原子加待处理数量，调用 `renderer+0x170` 指向对象的虚表 `+0x10`，传对应数组及组号 `0..3`，并清数组计数。四组的正式业务类型及虚调用内部耗时未从本函数恢复。空时是固定四组检查，不能把四个数组误说成“每帧扫描所有 chunk”。[新增原文](../../../../.cache/procedural-modeling/steady-performance-followup/digging-a-hole/flush-queued-tasks.disasm.txt)。

## LOD 重算与 invoker 轮询是两道门

`FVoxelDefaultLODManager::Tick` (`0x143E94160`) 在全局停止门之后取时间，比较 `now - manager+0xC0` 与一个浮点间隔 (`rdi-0x14`)；未超过则不调用 `UpdateInvokers`，超过才记录时间并调用 (`0x143E94182–0x143E941CA`)。其后还查 `rdi+0xB0`、尝试原子取得共享状态，缺席/未获得时退出 (`0x143E941CF–0x143E941F5`)。该 Tick 还有后续回调、状态交换路径，不能由“invoker 没变”推论整函数完全不工作；字段的游戏实例值与真实调用节奏未实测。[LOD Tick 原文](../../../../.cache/procedural-modeling/static-producer-followup/digging-a-hole/lod-tick.disasm.txt)。

到了 `UpdateInvokers` (`0x143E97DB0`) 也不是无成本检查：它从本世界的注册表取 invoker 列表，复制并整理组件弱引用 (`0x143E97E1C–0x143E97E80`)，比较与缓存列表的数量/项目 (`0x143E97E85–0x143E97EAE`)；对每个组件读取 settings、local 标志和整数体素位置 (`0x143E98222–0x143E98261`)。设置标志/字段不等或位置三轴平方位移超过按 `VoxelSize` 缩放的阈值时才标记变化 (`0x143E98333–0x143E983B5`)。没有变化会从 `0x143E983CE` 跳到 `0x143E987EC`，绕过缓存替换等主体工作。此轮轮询的开销随已注册 invoker 数量增长，不能用“没有挖掘”代替“没有 invoker 轮询”。[UpdateInvokers 原文](../../../../.cache/procedural-modeling/static-producer-followup/digging-a-hole/update-invokers.disasm.txt)。

若变化符合 `manager+0x60` 分支，`0x143E983DE` 会设置 `manager+0x129` 待更新字节；收尾在该字节为真、共享状态门允许，且 `now - manager+0x130 > manager+0x64` 时才清字节并调用 `UpdateLODs` (`0x143E987FA–0x143E98868`)。因此一次位置/设置变化不等于同一 Tick 立刻重建 octree；可能受第二时间间隔和共享状态门延后。反过来，此前遗留的待更新字节即使本轮位置未变，时间门到达仍可能触发 `UpdateLODs`。`UpdateLODs` 才将已筛选的设置盒送入 `FVoxelRenderOctreeSettings` 并进入 octree 更新；它在稳定且无待更新状态时不由本轮轮询调用。两个间隔字段、阈值字段的正式名字和 MainLevel 实例值未在本篇恢复，不能推出“每 N 帧”或移动几厘米触发。[24](24-collision-box-producers-and-invokers.md)界定了 MainLevel 自动相机回退和已查实例的来源边界，这里不把回退存在当成已观察到的运行组件。

**构造分支例（不是游戏实测）。** 设某帧 Tick 进入时无待显示/移除项、完成链表空、四个提交数组均为零，invoker 集合及体素位置与缓存一致、LOD 待更新字节为零。renderer 仍取时间、调用上述函数并更新统计；两组可见性数组和完成链表各在空门返回，四组提交数组不触发虚调用。若 LOD 轮询间隔尚未到，`UpdateInvokers` 不执行；间隔到了则会读取/比较 invoker，却因未变化而不走缓存替换与 `UpdateLODs`。如果后台旧工作刚完成，或相机位置跨过阈值，这个例子的相应空条件就不成立，即使该帧没有新的挖掘输入。

**Answered（静态）**：空完成链表和四个提交数组的早退位置；待显示/移除列表的空门；LOD Tick 的轮询时间门、invoker 列表/设置/位移比较与 LOD 重算的变化标志和第二时间门。**Partial / Unknown**：renderer Tick 的首个虚调用、四组提交的完整业务类型、两套间隔与阈值的运行值、引擎实际 Tick 频率、别的插件或 UE 帧工作、运行时任务积压与性能。**Not Run**：游戏启动/附加、私有存档、运行时 FPS/CPU/GPU/物理测量、Ghidra 重试、安装。此调查只服务独立设计规格，不移植目标代码或资产。

**Focused 静态核对：Passed。** [探针](tools/idle_tick_probe.py)重新读取原 EXE 的 PE section 字节并核 16 个分支锚点、7 个 PDB 函数地址/边界、两个新增 dumpbin 函数标签及完整掩码查询；[回执](../../../../.cache/procedural-modeling/steady-performance-followup/digging-a-hole/validation.json)为 `Passed=27, Failed=0, Not Run=4`。检查只证明这些静态字节与符号身份，不证明某次游戏帧执行、任务队列已空或具体时间成本。
