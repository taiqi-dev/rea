# 读回请求的 Unity native 等待与取消边界

本篇接续 [20](20-readback-snapshot-and-collision-age.md)、[21](21-readback-request-lifecycle-and-consumers.md) 的异步读回与 `Game.Load → Clear → Setup/Init → 同步读回 → 碰撞`。静态输入为原安装 `C:\Software\Steam\steamapps\common\Sandcastle Demo\GameAssembly.dll`（47,654,400 字节）、`UnityPlayer.dll`（36,915,112 字节）和已授权的 `global-metadata.dat`；Unity `6000.4.10f1` 与 GameAssembly/metadata 身份摘要沿用 [01](01-artifact-and-method-map.md)，没有重算。下文地址是各 DLL 的 PE 首选映像 VA。新材料来自普通 PE/IL2CPP 读取和 `dumpbin` 静态反汇编，**不是 REA Evidence 或运行观察**。旧 Ghidra 超时条件未改变，未重试；没有启动、附加或执行目标、Unity、GPU。

## 包装调用接到 UnityPlayer 函数

GameAssembly 的请求包装层 `0x181C5EA90–0x181C5EB45` 在 `0x181C5EB16` 调 `Request_Internal_ComputeBuffer_1_Injected`，随后在 `0x181C5EB45` 调 `AsyncGPUReadbackRequest::SetScriptingCallback`；两者均由 `0x18036DD00` 按签名字符串懒解析为函数指针。[21](21-readback-request-lifecycle-and-consumers.md) 已证明调用者把以**同一 Readback 对象**为接收者的委托传入后者，而没有在 Readback 保存请求句柄或世代。

UnityPlayer `.rdata` 的文件 `0x1EB5D80–0x1EBDA60` 是 3996 个连续的名称指针，紧接着从 `0x1EBDA60` 起有同数可执行地址指针。以下按同一索引配对；本轮验证每个名称指向数据节、函数指向可执行节，五个函数体的参数和操作也与名称吻合。**尚未追到表的注册/查找消费者**，故把这种配对标为经交叉核对的静态映射，而非实际解析器返回值的运行测量。

| 内部调用名（省略 `UnityEngine.Rendering.` 前缀）              | 表索引 | UnityPlayer 函数 VA | 已核功能                               |
| ------------------------------------------------------------- | -----: | ------------------- | -------------------------------------- |
| `AsyncGPUReadbackRequest::SetScriptingCallback`               |   3356 | `0x180F84800`       | 转入 `0x180F00CA0` 保存回调            |
| `AsyncGPUReadback::WaitAllRequests`                           |   3358 | `0x180F848C0`       | 转入全局 `0x18156F760`                 |
| `AsyncGPUReadback::Request_Internal_ComputeBuffer_1_Injected` |   3359 | `0x180F848D0`       | 创建并连接请求节点，输出请求指针和世代 |
| `AsyncGPUReadbackRequest::WaitForCompletion`                  |   3346 | `0x180F84600`       | 核对请求后调用底层等待/完成路径        |
| `UnityEngine.ComputeBuffer::DestroyBuffer_Injected`           |   2647 | `0x180F6CF40`       | 资源对象回收入口                       |

名称直指针表的发现纠正了“完整字符串没有代码 RIP 引用就找不到 native 目标”的过窄搜索。单个字符串在可执行节中没有直接 RIP 引用，但完整字符串起点各有一个 `.rdata` 指针槽。探针对全文件 ASCII/UTF-16LE 精确 NUL 字面量、绝对指针、RVA 常量和 29,935,101 个可执行节四字节位移窗口做了有界扫描；结果和表索引在 `unityplayer-icall-map-final.json`。字符串和表配对仍须以函数体交叉验证，不能从名称独自推断行为。

## 请求队列、回调和保活

`0x180F848D0` 在输入 buffer 非空且大小计算非零时调用 `0x18156F870` 取得请求节点；用 `0x1815570D0`、`0x1815572F0` 配置/提交读回，把节点链入全局请求链表，并在输出结构中写入节点指针与 `node+0xDC` 的世代值 (`0x180F84A14–0x180F84AA1`)。失败分支输出零请求。此处 GameAssembly 包装传入的可选外部数组参数为零；结果不是直接写入 Readback 的持久 `NativeArray`。队列提交后 GPU 捕获时点、线程和完成顺序未由这些指令确立。

`SetScriptingCallback` 对有效请求检查 `request.pointer` 与 `request.generation == node+0xDC`。`0x180F00CD5–0x180F00D05` 经运行时函数指针把委托转换成一个不透明句柄，存入节点 `+0xD0`，同时设置 `+0xC0` 回调桥与 `+0xC8` 释放桥。若节点 `+0x20` 指向的状态 `+8 == 1`，该函数保留这些字段等待后续交付；否则它在所见分支内尝试立即调用桥并释放句柄 (`0x180F00D0C–0x180F00DA3`)。完成清理函数 `0x18156F460` 先按 `+0xC0` 调回调，再按 `+0xC8` 释放句柄，最后将 `+0xD0` 置为 `-1`、`+0xC0/+0xC8` 清零。桥函数 `0x18156F420` 取回托管目标并转入 `0x18156F4D0`。这证明 native 节点有**回调与句柄的保留/释放槽**；`0x1822AD9A0/0x1822AD978` 的运行时函数指针尚未解析为精确 GC API，不能指定 GC handle 类型或每条异常路径的保活保证。

## 等待确实存在，但本次 Clear 是否调用仍未知

按请求的 `WaitForCompletion` 函数 `0x180F84600–0x180F8466E` 先要求请求指针非零、世代等于 `node+0xDC`；若 `node+0x20` 非空且其状态 `+8 == 1`，它经一个对象虚表 `+0x8C0` 传 `true` 进入底层等待点。返回后再看状态，已不为 1 才转入 `0x18156F460` 清理/交付回调。全局 `WaitAllRequests` 的 `0x18156F760–0x18156F7C5` 遍历全局 `0x1822AEA20` 的请求链表，对状态为 1 的节点也调用虚表 `+0x8C0`（参数 `true`）；状态不为 1 或没有状态对象时进入 `0x18156F460`。可见的队列是请求链表，**虚表目标、锁、GPU fence 的具体实现与等待唤醒条件尚未接通**；状态 `1` 可作为本函数中的“需要等待”判据，不据此为所有状态命名。

`Readback.Clear` 在 `0x1804649A3–0x1804649B1` 调 GameAssembly `0x181C42350`：它把 ComputeBuffer 包装对象 `+0x10` 的 native 指针交给 `DestroyBuffer_Injected`，返回后把该字段清零。对应 UnityPlayer `0x180F6CF40–0x180F6D13B` 遍历资源链并调用虚方法及资源回收辅助函数；完整已截函数体中**没有直接调用**上述 `WaitAllRequests`、`WaitForCompletion` 或 `0x18156F460`。其中的虚调用（例如 `0x180F6CFEA` 的 `+0x2E0`）和其它辅助函数未追到终点，故不能排除间接等待、延迟释放或取消，也不能说 Release 必取消。名称表里有等待方法仅证明接口存在；[21](21-readback-request-lifecycle-and-consumers.md) 所核的 `Game.Load/Readback.Clear` 没有显式走等待包装层。

当前 CPU 数组另由 `Readback.Clear → 0x1813B75B0` 处理。`Readback.Setup` 在 `0x18046531A–0x180465331` 以分配器值 `4` 创建持久 `NativeArray`；Dispose 对非空指针及 `1 < allocator < 64` 的分支调用 `UnsafeUtility::FreeTracked` 包装 `0x181C1DA80`，随后清零数组指针/分配器字段。这里释放的是数组内存，不带读回请求句柄，不能当成取消。FreeTracked 再往 native 的目标未解析。

## 同尺寸重建的条件演算

构造状态（**非运行观察**）：`R_old` 在旧 ComputeBuffer 上提交，世代记为 `g_old`。`Game.Load` 调 `Clear` 销毁旧 buffer、释放旧 CPU 数组，再在同一 Readback 实例上 `Setup/Init` 建 `C_new=C_old=65536` 的新数组，同步读回刷新碰撞。若 buffer 销毁的间接资源路径确实等待旧请求，并在新 Setup 前交付/清除它，则旧结果无法在新数组建立后覆盖它。若销毁仅解除 buffer 资源，而旧请求节点和委托仍可完成，且旧结果成功、长度为 65536，则旧回调按 [21](21-readback-request-lifecycle-and-consumers.md) 读取**当前** Readback 数组，可能写入新数组。请求节点有 `g_old` 并不能保护这个游戏层写入：回调只比较当前数组长度，没有把请求世代与 Readback 重建世代比较。native 实际走哪支、请求是否失败/丢弃、回调与碰撞遍历是否并发均未知。

## 原文、验证与可续查入口

本轮忽略目录 `.cache/procedural-modeling/static-scheduler-followup/sandcastle/` 保存 `unityplayer-icall-map-final.json`、`gameassembly-wrapper-names.json`，以及 `GameAssembly-Async-request-wrapper.txt`、`GameAssembly-ComputeBuffer-release-neighborhood.txt`、`GameAssembly-NativeArray-dispose-neighborhood.txt`、`GameAssembly-NativeArray-free-helper.txt`、`UnityPlayer-readback-icalls.txt`、`UnityPlayer-request-native.txt`、`UnityPlayer-callback-storage.txt`、`UnityPlayer-callback-trampoline.txt`、`UnityPlayer-callback-release.txt`、`UnityPlayer-waitone-icall.txt`、`UnityPlayer-wait-implementations.txt`、`UnityPlayer-destroybuffer-full.txt`。只读探针为 [`tools/native_readback_name_probe.py`](tools/native_readback_name_probe.py)；用本机 `dumpbin.exe /DISASM:NOBYTES /RANGE:0x…,0x… /SECTION:.text|il2cpp` 生成定点指令。探针执行成功、3996 对表槽均落在预期 PE 节、五个目标函数体与名称交叉核对、报告链接和 UTF-8 已检查；未做目标运行或全项目构建。

后续两个具体入口及价值：

- 从 `0x180F6CF40` 的资源虚调用 `+0x2E0` 与 `0x18156F760` 的请求链交叉追调用者和资源类型；可判定本次 buffer 销毁是否间接等待、取消或仅延迟释放。
- 从 `0x18156F760` 的等待虚调用 `+0x8C0` 解析虚表目标与其锁/fence 条件，再追 `0x1815572F0` 的入队和完成处理；可确认请求状态 `1` 如何转移、回调何时交付以及是否可与碰撞遍历并发。

**已回答**：包装层到 UnityPlayer 的静态函数映射、请求/回调句柄槽、可见等待判据与队列、Clear 的直接 native 销毁边。**部分回答**：资源回收与请求等待/取消的间接关联。**Unknown**：真实释放策略、虚表等待目标、锁与线程、回调到达顺序和 GC API 精确身份。**Not Run**：游戏/Unity/GPU/目标函数执行、Ghidra 重试、玩家存档或物理时序测量。
