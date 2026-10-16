# 局部编辑、读回与碰撞更新成本

后续[20](20-readback-snapshot-and-collision-age.md)补上具体Update／FixedUpdate调度者、Compute.Step追赶计数、回调版本空缺和碰撞消费时差；严格区分fixed step数量与墙钟上界。下文保留原有范围和当轮算例。

本篇只研究 Sandcastle Demo 已发售制品中的更新范围和成本结构。制品身份沿用 [01](01-artifact-and-method-map.md)：`GameAssembly.dll` SHA-256 `147030ECF9527A25250238120364EB761390B99688B1812C4EA555B3B04E56A0`，`sharedassets0.assets` SHA-256 `6dd7bb6bc7d926fd43c08d22c9c767b7edf531cf11a4a555fcd41830f2f9c721`；摘要只作本次获授权的身份核对。下文 `0x180…` 是该 DLL 的原生虚拟地址，DXBC 位置是 `sharedassets0.assets` 文件偏移。原始截取位于忽略目录 `.cache/procedural-modeling/sandcastle/`，尤其 `disasm/`、`dxbc/` 与 `update-followup/`。未运行游戏、Profiler 或玩家存档。

## 调度覆盖整张格网，刷子只改变局部值

`Compute.Dispatch` (`0x180474D70–0x180474E15`) 取三个虚方法返回值后调用 Unity `ComputeShader.Dispatch`。`Ground`、`Water`、`Readback` 的二维层使用 `Layer.get_DispatchX/Y` (`0x180458290–0x18045834F`)：分别读取层的 `resolution.x/y` (`+0x40/+0x44`)，乘 DLL 常量 `0.03125 = 1/32`，向上取整。`Compute.get_DispatchZ` 共用的 `0x18044E6A0` 返回 1。对应 DXBC 的 `dcl_thread_group 32,32,1` 可见 `Ground-01.asm.txt:22`、`Water-01.asm.txt` 和 `Readback-01.asm.txt`。因此每次调用这一通用 Dispatch 都发出 `ceil(Nx/32) × ceil(Ny/32)` 组、每组 1024 条线程；若边长不是 32 的倍数，边缘还会发出落在有效网格之外的线程。**这不是 CPU 只为笔刷矩形调用一个子网格。**

`Ground.Run` (`0x18044FF60–0x1804506A9`) 和 `Water.Run` (`0x1804832D0–0x180483B00`) 经通用调度执行多个 kernel。后者包含随时间累加器循环的调度 (`0x180483919–0x1804839DF` 等)，故不能由一个 FixedUpdate 推断固定 GPU Dispatch 次数。`Ground.UpdateTangent` (`0x180451650–0x1804516BA`) 即使由一次局部刷子触发，仍取 `Ground.kernelUpdateTangent` 后调用同一个虚调度接口。`Ground/Paint` 计算着色器（原文件偏移 `0x311f69c`，详见 [04](04-gpu-simulation-and-brush.md)）对每格中心做 `brushWorldToObject` 变换，再判断形状距离和覆盖，只有满足刷子条件的格子才产生目标权重和状态改写。这里的“局部”是**状态写入范围**，不是线程发射范围；边界外线程仍可能执行变换、比较或输入读取，实际分支代价需 GPU 计时才能判定。水、地面以及 Readback kernel 的工作域分别跟随各自 `Layer.resolution`，不能把三者默认视为同一个尺寸。

`Ground.Setup` (`0x1804509A9–0x180450A36`) 由上游尺寸与位移量构造分辨率，并在 `+0x40/+0x44` 保存；`Ground.Setup` 的 `0x180450D15–0x180450DBA` 再据此分块生成 4 个可见平面。尺寸是运行配置与序列化输入的结果，不是 `32×32` 的固定常量。本次没有从缺失 type tree 的场景资源可靠还原默认 `Nx/Ny`、`Water` 分辨率或场景分块倍率，所以不填写某一关卡的实际线程总数。

## 读回的完整路径与门禁

`Readback.Setup` (`0x1804650B5–0x1804653B2`) 从 Ground 取得一个维度，再以本层第二维相乘，在 `+0x48` 保存 `C=Nx×Ny`。它以 `C` 创建 `ComputeBuffer` (`0x1804652DA–0x1804652F5`)，并创建同长度的持久 `NativeArray` (`0x18046530B–0x180465343`)；`+0x90` 是 GPU 缓冲，`+0x78/+0x98` 对应本机单元数组/指针。Readback DXBC 的结构化 UAV 跨距为 **32 字节/格**（`Readback-01.asm.txt` 的 `dcl_uav_structured` 与两处 16 字节写入），故最小有效载荷是 `32C` 字节，不含驱动暂存、对齐、回调或其他缓冲开销。`Readback.Init` (`0x180464BE0–0x180464D55`) 与 `UpdateCellsImmediate` (`0x1804654B0–0x1804655CF`) 先 Dispatch，再同步从缓冲取数据；`Game.Load` 在 `0x18048B4F5` 调后者，随后 `0x18048B537` 调 `Ground.UpdateColliders`，为加载后的采样和碰撞准备数据。这条同步路径不能当作稳态每帧读回。

稳态 `Readback.Draw` (`0x1804649E0–0x180464B3C`) 在 Active 时先 Dispatch 读回 kernel，再以 `Compute.Step` 时间累加器循环发起 GPU 缓冲读回请求。传入 Step 的常量 `0x182035B1C` 解码为 `0.2f` 秒，所以在持续运行、每次 Draw 被调用且 deltaTime 正常推进时，意图频率约 **5 次/秒**。真实请求次数受帧调用、暂停、时间累加和 Step 的防长时间追赶上限影响；首次调用也不能据此写死恰好一次。请求回调 `Readback.<Draw>b__11_0` (`0x1804653E0–0x1804654AC`) 检查请求完成状态、错误状态、本地数组存在，以及返回长度等于 `C`，才把数据复制到持久数组。回调失败或尺寸变化会跳过复制，因此 CPU 采样可能沿用旧快照。`Readback.Sampler` (`0x180426240`，见 `disasm/Readback_Sampler_253.txt`) 正是在这份 CPU 数组上做双线性采样。

`Draw` 的循环每次都建立回调并提交请求，**没有观察到对上一请求的 pending 标志或队列长度的判定**；回调自身只决定是否接收结果。故“最多一笔未完成读回”不能作为本制品保证。若单次请求完成时间超过 0.2 秒，多笔请求有重叠可能；实际驱动是否合并、排队或限制，静态证据无法确定。回调检查长度与错误，是结果有效性门禁，不是提交速率门禁。

## 碰撞几何的复用与可见变化时差

`Ground.Setup` 生成四个 `planeChunks`。`PlaneChunk.SetMeshCollider` (`0x18045ED00–0x18045F113`) 绑定预建碰撞网格，按网格顶点数创建并保存顶点与采样索引数组（字段 `verticesOS`、`readbackIndices`）；这是初始化阶段。`PlaneChunk.UpdateMeshCollider` (`0x18045F120–0x18045F363`) 读取已有 `meshC` (`+0x68`)，按 `readbackIndices` 循环取新的高度/法线并写入已有顶点数组，之后更新 Mesh 顶点并对 `MeshCollider.sharedMesh` 做先清空、再设回同一 `meshC` 的操作 (`0x18045F2F2–0x18045F325`)。这会要求 Unity 重新接受/烘焙碰撞形状，但**本方法的稳态路径没有再次调用 PlaneGenerator 或新建 Mesh**。是否在 Unity 内部生成临时物理数据、烘焙花费多少，未由原生游戏代码证明。

普通 `Ground.Run` 在 `0x1804506AF–0x1804506F6` 对 `step & 1` 做判断：偶数步更新当前一个 chunk，并让 `planeChunkUpdateIndex=(index+1)%4`；奇数步跳过。连续固定步正常前进时，同一个 chunk 每 **8 个 FixedUpdate step** 才轮到一次；全四块分散在 8 步里。它并没有把碰撞更新裁成笔刷附近的顶点范围：轮到的 chunk 逐顶点遍历。另有显式 `Ground.UpdateColliders` (`0x180451580–0x1804515CE`) 逐个更新全部 4 块，`Game.Load` 在同步读回后调用此路径。可见 GPU 位移可以先于对应的 CPU 读回和 MeshCollider 刷新；对“鼠标操作后碰撞立即精确贴合画面”不能做静态保证。

## 可计算成本与不能冒充的实测值

设 Ground 分辨率 `Gx×Gy`、Water `Wx×Wy`、Readback `Rx×Ry`，一个通用 Dispatch 的发射线程数分别是 `1024 ceil(Gx/32)ceil(Gy/32)` 等。Ground/Water 的一次 simulation step 会调多个完整格网 kernel，具体次数取决于 Step 累加与条件分支；刷子直径不直接改变这项 Dispatch 网格大小。Readback 每次复制 `32RxRy` 字节有效格数据；若按稳态目标 5 Hz，**名义有效载荷率**为 `160RxRy` 字节/秒。例：仅作容量演算，若 `Rx=Ry=256`，则请求为 `2,097,152` 字节，5 Hz 是 `10,485,760` 字节/秒；该 256 并非本游戏默认参数。一次碰撞块更新需要遍历该块顶点数，分块网格的拓扑成本可按 [03](03-excavation-and-mesh.md) 的 `(rx+1)(ry+1)` 顶点与 `6rxry` 索引估算，物理烘焙成本不能仅凭顶点计数换算成毫秒。

场景真实分辨率、FixedUpdate 步长、读回完成时延、GPU 占用、CPU stall、物理烘焙耗时和不同质量设置的变化均**未知**；当前资源索引记录 `sharedassets0.assets` 为 Unity SerializedFile v22 且 `typeTree=false`，未有受验证的 MonoBehaviour 序列化字段解析，故不从名字或任意字节猜数值。独立开发可沿用“规则格网状态 + GPU 可见位移 + 限速 CPU 快照 + 分块碰撞”的设计原则，但应按自有场景负载实测，并为读回设置显式在途上限、陈旧数据版本和碰撞延迟容忍范围；不要复制本游戏 shader、网格或素材。

## 复查入口

metadata token 到原生地址的映射为 `.cache/procedural-modeling/sandcastle/codegen-map-all.json`；核心原始截取为 `disasm/Compute_Dispatch_39e.txt`、`disasm/Ground_Run_full.txt`、`disasm/Water_Run_full.txt`、`disasm/Ground_UpdateColliders_15c.txt`、`disasm/PlaneChunk_UpdateMeshCollider_216.txt`、`disasm/Readback_Init_24b.txt`、`disasm/Readback_UpdateCellsImmediate_24c.txt`、`disasm/Readback__Draw_b__11_0_255.txt`，以及 `update-followup/Readback_Draw_full.txt`、`update-followup/Readback_Setup_full.txt`、`update-followup/PlaneChunk_SetMeshCollider_full.txt`。线程组与 32 字节跨距见 `dxbc/Ground-01.asm.txt`、`dxbc/Water-01.asm.txt`、`dxbc/Readback-01.asm.txt`。仓库 [`tools/disassemble_mapped.ps1`](tools/disassemble_mapped.ps1) 可从 map 复现 `.pdata` 给出的短范围；本篇新增的完整片段直接以本机 `dumpbin.exe /DISASM:NOBYTES /RANGE:<起点>,<终点> /SECTION:il2cpp` 对同一 DLL 截取，范围分别是 `0x1804649E0–0x180464B50`、`0x180465030–0x1804653D0`、`0x18045ED00–0x18045F113`。DLL 常量以 PE 节表将 VA 换算成 `.rdata` 文件偏移再按 little-endian float32 解码。以上缓存只用于证据追踪，不进入正式产品资产。
