# 沙堡：无刷子输入时的稳态模拟与 Step 成本门

## 结论与证据边界

对这份 Sandcastle Demo 制品，**不输入刷子不等于停止地面、水和读回工作**。在 `Game.FixedUpdate` 确实到达 `Beach.Run`、各层 `Active` 为真且资源有效的条件下，Ground 与 Water 的 `Run` 所见路径没有先测试刷子矩形、脏格或状态是否变化。Ground 的两个积分 kernel 由本层的 `Compute.Step` 控制；Water 有三个每次 `Run` 都提交的整层 kernel，并有另一套 Step 控制积分和出生处理。`Readback.Draw` 若被 `Game.Update → Beach.Draw` 调用且 `Active` 为真，每次先提交读回 kernel，之后才按 0.2 秒 Step 节流异步请求。这里的“提交”只指游戏层调用 Unity `ComputeShader.Dispatch`，不等于测得 GPU 真正执行时间或可见变化。

目标是 `C:\Software\Steam\steamapps\common\Sandcastle Demo\GameAssembly.dll`。本轮[静态回执](../../../../.cache/procedural-modeling/steady-performance-followup/sandcastle/static-receipt.json)重新读取它的 47,654,400 字节，SHA-256 为 `147030ecf9527a25250238120364eb761390b99688b1812c4ea555b3b04e56a0`，与 [01](01-artifact-and-method-map.md) 和 [26](26-startup-configuration-and-setup-colors.md) 记录的 DLL 相同。回执从已保留的 `dumpbin` 文本提取 41 个指定指令地址；探针在 [tools/steady_budget_probe.py](tools/steady_budget_probe.py)。这是**普通本地 PE/IL2CPP 静态读取，不是 REA Evidence**。本次查询 REA `binary_session` 显示未打开目标；既有 Ghidra 全局 procedure 搜索 300 秒超时的条件未改变，故未重试，也没有新的 REA 函数 Evidence。

## 三条路径的静态预算

下表只数所见 `Run/Draw` 方法内经 `Compute.Dispatch` 虚槽 `+0x218` 提交的主计算 kernel。单次 Dispatch 的格网线程预算沿 [07](07-local-updates-readback-and-costs.md)：对本层 `Nx×Ny` 为 `1024⌈Nx/32⌉⌈Ny/32⌉`。不同层可有不同分辨率。

| 条件成立的一次入口    |                                                                                                                                                                                                                           所见主 kernel 提交数 | 额外 CPU/请求动作                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: | ------------------------------------------------------------------------------------------------- |
| `Ground.Run(step,dt)` |                                                                                                                                                     `2n_G`：每个 Ground Step 命中依次为 `kernelVelocityIntegration`、`kernelHeightIntegration` | 偶数 `step` 还尝试刷新一个碰撞块；这不要求 `n_G>0`                                                |
| `Water.Run(step,dt)`  | `3+2n_W+a_W`：固定的 `kernelUpdateFloor`、`kernelUpdateAmount`、`kernelUpdateTangent`；每个 Water 主 Step 的 `kernelVelocityIntegration`、`kernelHeightIntegration`；其中 `a_W` 为满足分支条件时额外提交的 `kernelAdvection` 次数，`0≤a_W≤n_W` | 后面另有以不同 Step 键控制的 `Spawn`、`SpawnDirt` 方法调用；表内未给它们内部工作折算 GPU Dispatch |
| `Readback.Draw()`     |                                                                                                                                                                                              `1` 个 `kernelUpdate`，发生在读回请求节流检查之前 | 以 0.2 秒 Step 键循环提交 `q_R` 个异步请求；没有上一请求完成/在途数量门                           |

`n_G/n_W/q_R` 是**一次入口内对应 Step 返回 true 的次数**，不是固定 FPS 或实测平均值。每次 Dispatch 的核名由 [Ground.Setup](../../../../.cache/procedural-modeling/sandcastle/disasm/Ground_Setup_full.txt) `0x180450AF1–0x180450B8C` 和 [Water.Setup](../../../../.cache/procedural-modeling/sandcastle/disasm/Water_Setup_full.txt) `0x180483E75–0x180483FBF` 的顺序 `FindKernel → 字段`，与 metadata 字段顺序及 `Run` 的字段取值交叉对应；仅凭某个 kernel 名称本身不足以计数。

具体调用点见 [Ground.Run](../../../../.cache/procedural-modeling/sandcastle/disasm/Ground_Run_full.txt)：`0x1804500DE–0x1804500E2` 的 `Active` 失败直接返回；`0x18045060C` 首次 Step 判断，循环内 `0x18045063A` 取 `+0xAC`、`0x18045065A` 取 `+0xB0` 后两次虚 Dispatch，`0x1804506A2` 续查同一 Step；`0x1804506AF–0x1804506F6` 仅按 `step&1` 轮换碰撞块。没有输入变化测试插在上述门与 Dispatch/碰撞之间。这是该方法的有界否定，未覆盖所有可能的外部停用路径。

[Water.Run](../../../../.cache/procedural-modeling/sandcastle/disasm/Water_Run_full.txt) 在 `0x180483401–0x180483405` 检查 `Active`；`0x180483881` 先 Dispatch `+0xD4`，主 Step `0x180483919` 命中后 `0x18048394A/+0xDC`、`0x18048396A/+0xE0` 两次 Dispatch，`0x180483970–0x180483990` 满足正值分支再发 `+0xE4`，并于 `0x1804839D8` 续查。循环后 `0x180483A1F/+0xE8` 与 `0x180483A5B/+0xEC` 再各 Dispatch 一次。`0x180483A7C–0x180483AB1` 和 `0x180483AD1–0x180483B07` 是另外两个 Step 循环，分别调用 `Water.Spawn` 与 `Water.SpawnDirt`，所以主模拟子步数不能直接当作全部水处理次数。`Water.Spawn` 自身先查 `enableSpawn` 字节 `+0x88` 等条件；仅看到 `Run` 调它不证明已实际出生水量。

[Readback.Draw](../../../../.cache/procedural-modeling/sandcastle/update-followup/Readback_Draw_full.txt) 的 `0x180464A47–0x180464A4B` 是 `Active` 门，`0x180464A75` 先 Dispatch `+0x88`，`0x180464AA1` 才 Step；命中后 `0x180464AF9` 提交异步请求。其 [Readback.get_Active](../../../../.cache/procedural-modeling/sandcastle/disasm/Readback_get_Active_249.txt) 还要求基类 `Compute.get_Active` 为真且格数 `+0x48>0`。因此 5 Hz 只描述**正常时间推进时的请求意图**，不是读回 kernel 每秒只运行五次。每次 Draw 先发一个整层读回 kernel 是本篇相比 [07/20](20-readback-snapshot-and-collision-age.md) 最影响空闲成本的区分。

## Active、暂停与不同频率

`Game.FixedUpdate` 在 `Game+0x34 == 1` 时直接返回，否则取 `Time.fixedDeltaTime`、调用 `Beach.Run` 并把 `Game+0x20` 的 step 加一（[指令](../../../../.cache/procedural-modeling/static-state-followup/sandcastle/Game_FixedUpdate_full.txt) `0x18048A936–0x18048A96F`）。`Beach.Run` 先进入 Ground 后进入 Water，再走其他层。Ground 与 Water 在自身 `Run` 开头通过同一虚表位置 `+0x188` 的 `Active` 调用早退；`Compute.get_Active` 的现存[指令](../../../../.cache/procedural-modeling/sandcastle/disasm/Compute_get_Active_394.txt)继续查询 Unity 侧状态，但本次没有把那三个 CoreModule 函数进一步映成“暂停按钮”语义。故精确结论是**phase=1 阻止这条 FixedUpdate 链**，以及各层 `Active=false` 阻止各自这条 `Run`；不能把任意 UI 暂停状态或无变化状态自动等同于它们。

另一条 `Game.Update` 尾段直接到 `Beach.Draw`，继而到 `Readback.Draw`（[指令](../../../../.cache/procedural-modeling/static-state-followup/sandcastle/Game_Update_full.txt) `0x18048ED30–0x18048ED4F`、[Beach.Draw](../../../../.cache/procedural-modeling/static-state-followup/sandcastle/Beach_Draw_full.txt) `0x180427509–0x180427526`）。该尾段没有 `Game+0x34 == 1` 的同一检查。`Game.Update` 同时在 `Game+0xE0` 非零时向 Unity 时间比例 setter 传 0 (`0x18048ECDC–0x18048ECF7`)；这说明固定链与 Draw 链有不同的门，但本次未测 Unity 对暂停、`Update`、`deltaTime` 和 GPU 命令的实际调度。即使 `deltaTime=0` 让请求 Step 暂无新预算，只要 Draw 与 Readback `Active` 仍成立，**先于 Step 的读回 Dispatch 仍是可达代码路径**。

`Compute.Step` ([原始指令](../../../../.cache/procedural-modeling/sandcastle/disasm/Compute_Step_39f.txt) `0x180474E30–0x180474F86`) 按对象字典的键保存剩余时间、间隔和本轮追赶计数。间隔变化重置记录；同间隔且计数为零时才把本次 `dt` 加一次，重复循环调用不会重复加同一 `dt`。达到间隔便扣一次并增加计数。一个入口的普通子步数因此近似由**该键累计的时间÷该次动态间隔**决定；Ground、Water 主循环、水出生循环和 Readback 请求使用各自的键/间隔，不能混作同一个节拍。`Ground.Run` 的间隔由本层尺寸/重力相关字段计算；`Water.Run` 的主间隔由水参数计算，出生使用 `Water+0x8C` 等另外的间隔；本轮没有可靠场景实际值，故不给数值 Hz。

`Compute.Step` 在计数大于 `1000` 时返回 false (`0x180474EDA–0x180474F36`)。这允许同一键在一次追赶过程中最多返回 true **1001 次**，但不是经济的常态预算，也不是 GPU 运行时间、墙钟时长或在途请求上限。达到 1001 后，若间隔保持相同，后续调用会在增加新 `dt` 之前再次走同一大于 1000 分支；这条代码本身没有复位计数，因而可能保持拒绝，直到间隔改变或别的未追踪写者重建状态。不能将它称为“超时后下帧自动恢复”。

构造算例（**非游戏测量**）：若某次有效 `FixedUpdate` 中 Ground 的对应累加器尚不足间隔，`n_G=0`，它不发那两个积分 kernel，但偶数 step 仍尝试更新一个碰撞块。若同次 Water 主 Step 也未命中，`n_W=0`，仍发上述三个固定 kernel；若主 Step 命中两次且只有一次进入 advection 分支，则主路径为 `3+2×2+1=8` 次 Water Dispatch。若同一时期连续发生十次有效 Draw 且请求时间尚未到 0.2 秒门槛，Readback 仍是十次 kernel Dispatch、零次新异步请求。这个算例只展示三个不同门的影响；尺寸、调用次数、间隔和 GPU 耗时没有从目标运行中测得。

## 对自研的适用边界与验证

可借鉴的机制是把物理子步、读回请求和碰撞块轮换分别预算，并将真正无需变化的全格网计算设置显式门；这属于自研设计选择，**不是声称原游戏已有无变化休眠**。对本制品，GPU 驱动是否消去空操作、Water 出生内部总成本、真实默认分辨率、FixedUpdate/Draw 墙钟频率、暂停后的 Unity 实际调用、CPU/GPU/物理耗时、功耗及玩家感受仍为 **Unknown**，不能用这里的指令计数冒充 Profiler。

**Passed（静态）**：重新核目标 DLL 字节数与授权摘要；从既存原 DLL 的精确 `dumpbin` 截取核 41 个关键站点、Setup 字段与 metadata 顺序、`Game.FixedUpdate/Update → Beach.Run/Draw` 链；探针运行成功并生成上述回执。**Partial**：`Compute.get_Active` 调用的 Unity 侧具体语义、`Water.Spawn/SpawnDirt` 内部全部成本及所有外部状态门未闭合。**Not Run**：游戏、进程附加、Unity、GPU/Profiler、私人存档、Ghidra 超时重试及全项目构建。若未来获运行许可，最小区分性观测是无输入稳定场景中同步记录 fixed/Draw 入口、每 kernel Dispatch 数、异步请求数、GPU 时长与时间比例；本轮不进行这些动作。
