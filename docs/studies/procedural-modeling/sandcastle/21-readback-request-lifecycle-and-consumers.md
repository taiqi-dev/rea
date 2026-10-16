# 读回请求的重建生命周期与碰撞消费者

本篇沿 [20](20-readback-snapshot-and-collision-age.md) 的快照年龄结论，追 `Clear/Setup`、请求回调和同步加载之间的边。目标仍是 `C:\Software\Steam\steamapps\common\Sandcastle Demo\GameAssembly.dll`，身份与 `0x180…` 原生 VA 坐标沿用 [01](01-artifact-and-method-map.md)、[07](07-local-updates-readback-and-costs.md)。这是对该制品的有界静态指令分析；没有运行或附加游戏、Unity、目标函数和 GPU。普通 PE/IL2CPP 读取及 `dumpbin` 截取不是 REA Evidence；上轮 Ghidra 超时的条件未改变，因此没有重试。

## 重建先清理，再建立新的读回目标

`Game.Load` 在 `0x18048AEDA` 先调用 `Game.Clear`，在 `0x18048B2D1` 调 `Game.Prepare`。`Game.Clear` 取仍存于 Game `+0x48` 的 Beach 对象，调用 `Beach.Clear` (`0x18048A515–0x18048A536`)；本路径未将这个 Beach 字段置空。`Beach.Clear` 依次清理其层对象，`+0x40` 的 Readback 对象在 `0x180427373–0x18042738A` 走其 Clear 虚方法。`Readback.Clear` 释放当前 GPU ComputeBuffer `+0x90` 和当前 `NativeArray` `+0x78`；所检查路径里没有可辨识的 `AsyncGPUReadback.WaitAllRequests`、按请求取消或等待回调的调用。这里的否定只覆盖所列游戏层调用路径；ComputeBuffer.Release、NativeArray.Dispose 及 Unity 内部是否等待或取消，仍是 **Unknown**。来源：新增 `Game_Load_full.txt`、`Game_Clear_full.txt`、`Beach_Clear_full.txt`，以及 [20] 已列的 `Readback_Clear_24e.txt`。

随后 `Game.Prepare` 对同一个 Game `+0x48` Beach 对象调用 `Beach.Setup` (`0x18048C1E4–0x18048C1EF`)，紧接着调用 `Beach.Init` (`0x18048C1F4–0x18048C1FF`)。`Beach.Setup` 在各层 Setup 的尾段对 `+0x40` Readback 调用 Setup (`0x1804282BD–0x1804282D4`)；`Readback.Setup` 以本次分辨率计算 `C`，新建 GPU ComputeBuffer 和持久 `NativeArray`，将其地址放回同一 Readback 实例的 `+0x78/+0x98` (`0x18046511F–0x180465343`)。`Beach.Init` 同样经 `+0x40` 调 Readback.Init (`0x180427E35–0x180427E4E`)。因此加载重建的代码次序是 **Clear → Setup → Init**，而不是把新读回对象交给每个新请求。来源：新增 `Game_Prepare_full.txt`、`Beach_Setup_full.txt`、`Beach_Init_full.txt` 和既有 `Readback_Setup_full.txt`。

`Game.Load` 继续执行其他层的 Load 虚调用，之后在 `0x18048B4F3–0x18048B537` 依次调用 `Readback.UpdateCellsImmediate`、`Readback.SetWaterSpawnPoints`、`Ground.UpdateColliders`。同步读回先从当前 ComputeBuffer 取长度为 `C` 的临时数组并复制到当前持久数组 (`0x18046551D–0x1804655C0`)，再刷新四块碰撞；这能解释加载路径为何立即有一轮 CPU 高度和碰撞输入。它不能自行证明异步旧请求已被清空，也不能把这次同步结果赋予版本标识。来源：新增 `Game_Load_full.txt`、`Readback_UpdateCellsImmediate_full.txt`，以及 [07] 的 `Ground_UpdateColliders_15c.txt`。

## 委托属于请求，接收者仍是可重建的 Readback

`Readback.Draw` 每次节流通过时读取**当时**的 `+0x90` ComputeBuffer，构造以当前 `Readback` 实例为目标的委托 (`0x180464AC0–0x180464AF9`)；委托构造函数把接收者引用写在自身 `+0x20` (`0x18080C244–0x18080C261`)。随后请求包装层 `0x181C5EA90–0x181C5EB45` 先调 `Request_Internal_ComputeBuffer_1_Injected`，再调 `AsyncGPUReadbackRequest::SetScriptingCallback`。这两个名字是从本 DLL 对应的内部调用名字符串读取，并由包装层使用位置交叉核对；名称本身不证明 Unity native 侧如何排队。`Readback.Draw` 没把请求、委托、发起时 NativeArray 指针或序号写入 Readback 字段，回调从其接收者对象实时读取 `+0x78` 和 `+0x48`。来源：既有 `Readback_Draw_full.txt`、`Readback__Draw_b__11_0_255.txt`；新增 `Delegate_ctor.txt`、`AsyncRequest_wrapper_neighborhood.txt`、`AsyncRequest_icall_strings.txt`。

游戏层没有显式的请求集合、完成后移除集合或对委托的清理代码。包装层将委托传入 `SetScriptingCallback` 后，保活时长、回调调度、请求结果及 GPU buffer 的 native 资源回收由 Unity 内部决定，本次静态代码无法确认。尤其不能把 `ComputeBuffer.Release` 等同于“旧回调不会再到达”，也不能断言它必然到达或必然造成悬空访问。`Beach.OnDestroy` 仅跳向 `Beach.Clear` (`0x180427E90–0x180427E92`)；`Game.OnDestroy` 所见路径未额外等待 Readback 请求 (`0x18048BC90–0x18048BCCC`)。这仍不覆盖 Unity 的对象销毁和 native 请求清理实现。

## 同尺寸重建时的条件性旧结果写入

若旧请求在 `Clear` 前已提交、Unity 在重建之后仍回调其委托、旧请求成功且返回 `C_old` 个元素、并且新 Setup 恰好得到 `C_new=C_old`，旧回调会通过“当前指针非零、长度等于当前 C”的检查，把旧结果复制进**新** NativeArray。因为委托目标是同一 Readback 对象，回调并不持有旧数组作为唯一写入目标。尺寸不同会让它跳过复制；相同元素数也不保证格网语义相同，例如不同的 `Nx×Ny` 可以有相同乘积。来源：上节的对象/委托引用链、`Readback.Setup` 的 `C=Nx×Ny` (`0x18046511F–0x180465126`)，以及回调 `0x180465440–0x18046549D`。

构造时序例（**条件推演，不是运行观测**）：旧场景的 `R_old` 已提交，`C_old=65536`；随后 `Game.Load` 清理旧数组，Prepare 为新场景分配 `C_new=65536`，同步读回写入新数组并开始更新碰撞；若 Unity 之后交付成功的 `R_old`，回调把旧样本写入新数组。此后轮到的 chunk 会从这份被覆盖的数组取高度。若旧回调在 `Clear` 后、`Setup` 前到达，则目标指针已释放/置空的具体状态还要服从 NativeArray Dispose 和回调时序；本次没有证明这一区间的实际行为。若 Unity native 在 Release 时等待或取消旧请求，则上面的重建后到达前提不成立。**静态证据只证明游戏层缺少世代门，不能证明该演示在玩家机器上发生。**

碰撞消费者没有可用来辨识“这一块来自第几次请求”的字段。`PlaneChunk.UpdateMeshCollider` 每次从当前 Readback 数组按本块 `readbackIndices` 逐顶点取值，再提交 MeshCollider；`Ground.Run` 的四块轮转和加载时 `Ground.UpdateColliders` 的全块循环都未向 chunk 传入请求 ID、时间戳或快照世代。故可以在推演中称“某块在某次调用时读取当前可见数组”，不能从静态结构给每块标一个 CPU 快照版本，也不能仅凭碰撞网格内容倒推出请求完成顺序。若回调可能与同步遍历并发，块内一致性仍是 [20] 已记录的 Unknown。来源：既有 `PlaneChunk_UpdateMeshCollider_216.txt`、`Ground_Run_full.txt`、`Ground_UpdateColliders_15c.txt`。

## 其他写入边与范围

`Beach.Run` 的 `+0x40` 虚调用到 Readback 时，本次 metadata map 中没有 Readback 自己的 `Run` 覆写；它继承的 `Compute.Run` 指向共享空桩 `0x180441590`，指令为 `ret 0`。因此所见稳态 CPU NativeArray 写入边是成功的 Draw 异步回调，加载/初始化边是同步 `UpdateCellsImmediate`；未发现 `Readback.Run` 另写该数组。`Readback.Load` (`0x180464D60–0x180464D83`) 是按索引从 `+0x98` 读取单元，并非场景加载方法或写者。该结论限定于已映射 Readback 方法及这些调用边，不能替代全程序数据流证明。来源：`codegen-map-all.json` 的 Readback/Compute 条目；新增 `Compute_Run_stub.txt`、`Readback_Load_Run.txt`；既有 `Readback_Draw_full.txt` 和 `Readback_UpdateCellsImmediate_full.txt`。

新增可复核原文位于忽略目录 `.cache/procedural-modeling/static-lifecycle-followup/sandcastle/`。生成方式为已安装 `dumpbin.exe /DISASM:NOBYTES /RANGE:0x…,0x… /SECTION:il2cpp` 只读截取精确 GameAssembly.dll；内部调用名按 `.rdata` 节表把 VA 换成文件偏移读取，以调用位置验证。旧 Ghidra 超时未重试，未重算身份摘要。**已回答**：重建、同步替换、委托接收者与同尺寸风险的游戏层条件；**部分回答**：Unity native 如何保活/等待/取消及回调与碰撞遍历的线程关系；**Not Run**：目标运行、GPU/物理测量、场景默认尺寸和旧请求真实到达次序。
