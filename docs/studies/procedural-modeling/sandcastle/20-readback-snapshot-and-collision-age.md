# 读回快照到碰撞的时效边界

后续[21](21-readback-request-lifecycle-and-consumers.md)补上Clear→Setup／Init→同步读回→碰撞的加载次序、委托接收者和同尺寸重建条件；Unity native的等待／取消及真实回调时序仍未知。

本篇续查 [07](07-local-updates-readback-and-costs.md) 留下的快照年龄问题。对象仍是 `C:\Software\Steam\steamapps\common\Sandcastle Demo\GameAssembly.dll`，身份与地址坐标沿用 [01](01-artifact-and-method-map.md) 和 [07](07-local-updates-readback-and-costs.md)。这是该制品的有界静态指令推导，未运行、附加游戏或测 GPU/物理耗时。普通 `dumpbin` 文本不是 REA Evidence；先前 Ghidra native timeout 没有状态变化，本轮未重试。

## 两条调度链相遇于持久 CPU 数组

`Game.FixedUpdate` (`0x18048A930–0x18048A97C`) 在 phase 允许时取 fixed delta、传入当前 step 调 `Beach.Run`，返回后 step 加一；`Beach.Run` (`0x180428010–0x18042817F`) 先调用 `+0x20` 的 Ground.Run，后调用 `+0x40` 的 Readback.Run。`Ground.Run` 的碰撞刷新在其 GPU 子步循环之后，以 `step & 1 == 0` 选一块并把下标模 4 递增 (`0x1804506AF–0x1804506F6`)。因而稳定连续步中每块每 8 个 FixedUpdate step 获得一次**尝试刷新**，并非每次读回完成立即刷新。

另一条链是 `Game.Update`（本体起点`0x18048EB10`，选定尾段`0x18048ED30–0x18048ED4F`）调 `Beach.Draw`（起点`0x180427420`）；后者在 `0x180427509–0x180427526` 的 `+0x40` 虚调用到 Readback.Draw。Readback.Draw在Active时先Dispatch Readback kernel (`0x180464A49–0x180464A75`)，再用 `Time.deltaTime` 和 `0.2f` 调 `Compute.Step`，每次true向同一个 `+0x90` ComputeBuffer提交一个带对象回调的异步请求 (`0x180464A7B–0x180464B21`)。该循环没有pending数或上一请求完成判定。这里能证明各链**内部**次序；不同Unity回调阶段、GPU完成时间及本机实际fixed/render频率未被本轮静态指令测出，不能把一次Update与某个FixedUpdate强配对。

`Compute.Step` 本次调用的是 `0x180474E30–0x180474F8F` 版本：从对象 `+0x30` 的字典取累加时间、间隔、追赶计数；间隔改变则重置，计数为零时才加入本次 delta，达到间隔后减去一次间隔并把计数加一，返回 true。因 `Readback.Draw` 循环重复调用时计数非零，同一次 Draw 不会反复加入同一个 delta。若累积时间足够大，计数从零最多可连续增至 **1001**；随后 `count > 1000` 分支直接返回 false，且该分支自身未重置字典记录。这个异常阈值并不是正常运行每帧 1001 个请求的预测，也不是在途请求上限；别处是否复位该状态尚未查证。正常 0.2 秒节流只是提交节奏，不能限定完成时间或 CPU 快照年龄。来源：既有 `disasm/Compute_Step_39f.txt` `0x180474ED6–0x180474F86` 与 `update-followup/Readback_Draw_full.txt`。

## 回调接受条件与版本空缺

`Readback.<Draw>b__11_0` (`0x1804653E0–0x1804654AC`) 依次要求请求完成标志为真、错误标志为假、对象 `+0x78` 的持久 NativeArray 数据指针非零，取回的数组长度等于当前 `+0x48` 的 `C`，然后复制 `C` 个单元到这份持久数组 (`0x180465424–0x18046549D`)。任一检查不通过就直接退出，保留上次成功内容；它未比较请求序号、发起时的分辨率版本或最新已接受请求，也未显示显式的对象销毁/取消世代判断。指针存在与长度相等只能证明当前目标可按这一尺寸复制，不能证明它属于发起请求时同一场景或更新世代。`Readback.Clear` 会释放 GPU buffer 与该数组 (`0x180464955–0x1804649C6`)；清理与仍在途回调的相对次序、Unity API 对释放后请求的行为、以及回调是否会遇到同尺寸重建，均需生命周期证据，不能从指针检查推成完整安全保证。来源：既有 `disasm/Readback__Draw_b__11_0_255.txt`、`disasm/Readback_Clear_24e.txt`、`update-followup/Readback_Setup_full.txt`。

两个请求可以在制品代码层重叠。如果运行环境允许乱序完成，较早请求可在较新请求成功后覆盖同一 CPU 数组：例如构造的 `R1` 于 0.20 秒提交、0.70 秒回调，`R2` 于 0.40 秒提交、0.50 秒回调；若两者长度都是 `C` 且无错误，0.50 秒写入较新样本，0.70 秒又写入较旧样本。此例仅说明**缺少世代门时的条件性风险**；本轮没有观测驱动是否会乱序，GPU buffer 在各请求时究竟捕获哪一代数据也没有时间戳证据。

## 碰撞消费与年龄公式

`PlaneChunk.UpdateMeshCollider` (`0x18045F15F–0x18045F325`) 经 Ground/Readback 引用取得当前 NativeArray 的指针与长度表示，遍历本块 `readbackIndices`，把逐索引读取的高度写入已有顶点数组，之后更新 Mesh 顶点并将 `MeshCollider.sharedMesh` 清空再设回。它没有保存回调序号，也没有为本块复制一份不可变快照。若回调不能在一次同步遍历内插入，则单次块更新使用调用时可见的同一数组版本；若回调能并发改写，静态指令不能排除块内混代或读取竞争。即使单块内稳定，不同块在相隔的偶数 fixed step 刷新，可处于不同快照世代；显式 `Ground.UpdateColliders` 的四块顺序循环也未作版本锁。来源：既有 `disasm/PlaneChunk_UpdateMeshCollider_216.txt`、`disasm/Ground_Run_full.txt`、`disasm/Ground_UpdateColliders_15c.txt`。

对一次地面变化，记变化时刻 `t_m`，**对应发出相应请求那次Draw**的读回 Dispatch 为 `t_d`，相应请求为 `t_r`，成功且最终仍为当前内容的回调为 `t_c`，目标块下一次消费为 `t_u`。Draw也会在尚未达到节流间隔时Dispatch，故这里不把`t_d`定义为变化后最早的任意Dispatch。在这一请求确实捕获变化、回调未被旧请求反向覆盖且无块内并发写入的**条件下**，从变化到碰撞提交的时差是

`t_u - t_m = (t_d - t_m) + (t_r - t_d) + (t_c - t_r) + (t_u - t_c)`。

第一项包括等到符合 0.2 秒节流的 Draw，并受 GPU 输入顺序影响；第二项是在**同一次 Draw**中Dispatch后提交请求的代码时差，不能再加一个0.2秒；第三项是未知的GPU/驱动/回调时延。第四项只有额外假定固定步按墙钟每`F`秒均匀推进时，才能以小于约`8F`演算；恰好错过本块轮次就接近`8F`。单独读取`Time.fixedDeltaTime`不能证明真实墙钟如此调度，追赶步、暂停与帧阻塞均可能改变对应关系。这是**条件性分解**，不是实测上界：失败、异常计数、乱序覆盖或没有后续调度时，静态证据不给有限年龄上界。可见渲染、CPU数组与MeshCollider还各有不同的更新点，不应当把请求间隔`0.2s`直接当作三者之间的最大延迟。

构造演算：仅假设 `F=0.02s`、正常 Draw、同一块在 `0.28s` 与 `0.44s` 更新。`t_m=0.001s` 的变化等到 `t_d=0.215s` 的读回 Dispatch 纳入，紧随其后的请求于 `t_r=0.216s` 提交，成功回调在 `t_c=0.286s`；它刚错过该块的 `0.28s` 更新，到 `t_u=0.44s` 才进入碰撞。此时变化到碰撞为 `0.439s`，分项为 `0.214+0.001+0.070+0.154s`。这些时刻、`F` 和回调延迟都是演示参数，**不是沙堡实测值**；同一期间其他块可能先轮到并使用新快照。

## 证据位置与剩余边界

本轮新增原始截取在 `.cache/procedural-modeling/static-state-followup/sandcastle/`：`Game_FixedUpdate_full.txt` (`0x18048A930–0x18048AA20`)、`Game_Update_full.txt` (`0x18048EB10–0x18048ED60`)、`Beach_Draw_full.txt` (`0x180427420–0x1804275A0`)。用已安装 `dumpbin.exe /DISASM:NOBYTES /RANGE:0x…,0x… /SECTION:il2cpp` 对原 DLL 只读生成。其余指令沿用 [07](07-local-updates-readback-and-costs.md) 列出的 `.cache/procedural-modeling/sandcastle/disasm/` 与 `update-followup/`；token 到地址以 `codegen-map-all.json` 为线索并用调用指令交叉核对。

已回答：固定步和 Draw 的调用方向、正常块轮换、回调接受条件、缺少可见世代门，以及条件性时差公式。仍未知：实际请求完成/回调顺序与延迟、Unity 回调和碰撞遍历是否可并发、GPU 请求的精确捕获时点、异常计数触发后的外部恢复、场景实际 `F` 与帧间隔、物理后端接受新 sharedMesh 到生效的耗时。它们需要单独授权的目标运行/Profiler/物理观察；本轮均 **Not Run**。
