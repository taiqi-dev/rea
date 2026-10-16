# 掘地求财：过渡三角形进入 section 与碰撞的条件

后续[23](23-mainlevel-mesher-lod-and-collision-config.md)补主关卡的模式、过渡开关与碰撞LOD配置，并把零play type的可见块碰撞上限固定为2；本文的索引合并结论仍须满足提交和cook条件。

接续[21：LOD 接缝和过渡网格](21-lod-seams-and-transition-mesh.md)留下的问题：**单独生成的过渡三角形，最终是否与普通网格一起交给碰撞构造？** 静态答案是：在相应任务结果被当前 renderer 接受、`GetMeshesToBuild` 找到有效过渡 buffer、section 带碰撞位并成功构建的条件下，过渡索引会进入与普通索引相同的输出 buffer，Chaos cooker 确实读取这个合并 buffer。它不是只凭 `visible` 或 `collision` 名称推断的。实际 MainLevel 是否选用产生该过渡网格的 mesher、某次是否有该 LOD 邻对，以及 cook 后物理表面是否连续，仍未实测。

## 身份、边界和原文

目标仍是 [00](00-evidence-and-reproduction.md)核过 RSDS GUID/age 的 `C:\Software\Steam\steamapps\common\A Game About Digging A Hole\DiggingGame\Binaries\Win64\DiggingGame-Win64-Shipping.exe` 与同目录 PDB；本次本地 PDB 探针记录 EXE 长度 `145180160`、首选基址 `0x140000000`，沿用[21](21-lod-seams-and-transition-mesh.md)的 PDB 匹配与先前摘要，**没有新算摘要**。本次没有重试先前未变的 Ghidra timeout。只用本地 `pdb_probe.py` 精确掩码和 VS 2022 `dumpbin 14.44.35222.0 /DISASM /RANGE` 定点读取 PE，原文放在 ignored [static-consumer-followup/digging-a-hole/](../../../../.cache/procedural-modeling/static-consumer-followup/digging-a-hole/)：`consumer-symbols.json`、`collision-path-symbols.json`、`merge-symbols.json`、`basic-merge-work.disasm.txt`、`basic-merge-helper.disasm.txt`、`merge-sections.disasm.txt`、`merge-lambda3.disasm.txt`、`merge-lambda5.disasm.txt`、`proc-buffers-ctor.disasm.txt`、`cooker-cookmesh.disasm.txt`、`create-trimesh-lambdas.disasm.txt`。其中 `*FVoxelBasicMeshMergeWork*` 7/7、`*FVoxelAsyncPhysicsCooker_Chaos*` 6/6、`*MergeSections_AnyThread*` 3/3，查询均 `exhausted=true`。这些是普通静态文件读取，**不是 REA Evidence**；下列地址为首选 VA，不是运行地址。

复用既有 [GetMeshesToBuild 原文](../../../../.cache/procedural-modeling/static-submission-followup/digging-a-hole/get-meshes.disasm.txt)、[Mixed/Clustered 原文](../../../../.cache/procedural-modeling/static-submission-followup/digging-a-hole/) 、[普通与过渡 mesher 原文](../../../../.cache/procedural-modeling/static-art-followup/digging-a-hole/)、[SetProcMeshSection 原文](../../../../.cache/procedural-modeling/digging-a-hole/digging/set-section-disasm.txt)、[cooker 构造原文](../../../../.cache/procedural-modeling/static-resource-followup/digging-a-hole/cooker-ctor.disasm.txt)。[08](08-mixed-handler-submission-chain.md)和[09](09-collision-result-acceptance.md)中的完成、组件和异步结果门保持适用；本篇只补三角形归属。

## 两个输入 mesh 到 section 的 buffer

[21](21-lod-seams-and-transition-mesh.md)已追到 chunk `+0x77` 的方向 mask 经 `StartTask<1,0> → FVoxelMesherAsyncWork::DoWork → GetMesher` 进入**过渡任务**；普通任务走另一槽。Marching Cube 与 Cubic 均有过渡 mesher 分支，Surface Net 另有 mask 路径。mesher 工作会构造 `FVoxelChunkMesh`；既有 `mesher-work.disasm.txt` 的 `0x143EDC1B4–0x143EDC281` 是单 buffer 输出实例。任务生成并不跳过 renderer 的当前 chunk/key、槽和令牌接受门（[20](20-partial-restore-lod-mesh-collision.md)）。

`FVoxelRenderUtilities::GetMeshesToBuild` 的参数依次包含普通 `FVoxelChunkMesh&` 和可空的过渡 `FVoxelChunkMesh*`。进入函数时，普通输入保存在本地 `rbp+0x40`，过渡输入保存在 `rbp+0x78`（`0x143EE3A84–0x143EE3ABF`）。当非单 buffer 路线被选中，`0x143EE3FF4` 对普通 mesh 调 `FVoxelChunkMesh::IterateMaterials`，`0x143EE3FF9–0x143EE4008` 在过渡指针非空时也对过渡 mesh 调同一迭代；材料集合随后分组。对所选材料索引，`0x143EE4BB3–0x143EE4BFA` 在普通 mesh 上 `FindBuffer` 并放入 `FVoxelChunkMeshSection+0x18`，`0x143EE4C42–0x143EE4C95` 在过渡 mesh 上 `FindBuffer` 并放入同一 section 的 `+0x28`。找不到对应材料 buffer 时该指针保持空；函数没有在这里把两个源的三角形预先拼成一份。

另一个单 buffer/材料分组支路也把普通 buffer 放入 section `+0x18`、可用的过渡 buffer 放入 `+0x28`（`0x143EE3EC2–0x143EE3F83`）。`GetMeshesToBuild` 在两处把传入 `FVoxelChunkSettings` 的 bit 1、bit 2、bit 0 拆给 `FVoxelProcMeshSectionSettings` 的 `+0x10` 碰撞、`+0x11` 导航、`+0x13` 可见位（`0x143EE3D56–0x143EE3D98`、`0x143EE4970–0x143EE49D6`）。这里须区分**两种不同结构的 `+0x10`**：上述是输出 section _settings_ 的碰撞位；`FVoxelChunkMeshSection+0x10` 是合并 helper 的另一个逐源标志，不能因为偏移相同就认作碰撞资格。后者在 `0x143EE4B9C` 的分组支路被明确置零。

## 合并输出与 Chaos 的实际取用

MainLevel 静态初始 Mixed 条件下，[08](08-mixed-handler-submission-chain.md)证明 `flags & 0x06` 送 Basic（可见 bit 0 清掉），`flags & 0x01` 送 Clustered（碰撞/导航 bits 1–2 清掉）。Basic 的 `ApplyAction` 于 `0x143ED11D2` 调 `GetMeshesToBuild`；`FVoxelBasicMeshMergeWork::DoWork` 于 `0x143EDB2E9` 调 `BuildMeshes_AnyThread`，该 helper 于 `0x143ED30BD` 对每组 section 调 `MergeSections_AnyThread`。Clustered 的可见分支也于 `0x143ED1936` 调同一个 `GetMeshesToBuild`，但其 section settings 没有碰撞位。两支路的 section 内容仍由各自收到的 flags、有效 buffer 和完成门决定。

`MergeSections_AnyThread` 第一遍读取每个 `FVoxelChunkMeshSection+0x18` 普通 buffer（`0x143EEAE33`）和 `+0x28` 过渡 buffer（`0x143EEAEC1`）。各 buffer 的 `+0x08` 是索引数，`+0x18` 是顶点数；非空且有顶点的输入把两项都加进同一输出容量（`0x143EEAE79–0x143EEAE88`、`0x143EEAF02–0x143EEAF11`）。普通输入还有 `0x143EEAE40–0x143EEAE43` 的本地状态门；过渡输入没有这个同型跳过门。随后输出 `FVoxelProcMeshBuffers+0x118` 的主索引缓冲区按两者合计索引数分配（`0x143EEB060–0x143EEB06B`）。第二遍分别从普通输入 `+0x18`（`0x143EEB158`）与过渡输入 `+0x28`（`0x143EEB4F4`）读取顶点和索引；普通索引在 `0x143EEB434–0x143EEB4B1`、过渡索引在 `0x143EEB6CF–0x143EEB731` 经过各自顶点基数修正后写入**同一个**输出 `+0x138` 的索引数据区。过渡顶点走同一输出顶点缓冲区，并以 `0x143EEB32D` 调用 `GetTranslatedTransvoxel` 做位置调整。这里可确认合并，而非只看到两个 buffer 指针存在。`FVoxelChunkMeshSection+0x10` 仅影响另一个 `+0x158` 索引缓冲区的容量统计（`0x143EEAE8A–0x143EEAF1D`）；本次碰撞取用的是主索引 `+0x118/+0x138`。

`SetProcMeshSection` 于 `0x143EF1151–0x143EF1172` 把 settings 的 `+0x10…+0x13` 写入组件 section，`0x143EF1176–0x143EF11DB` 把**合并后的** `FVoxelProcMeshBuffers` 存于组件 section `+0x18`。`UpdateCollision` 于 `0x143EF5BA0` 先要求至少一个组件 section 碰撞位非零；cooker 构造在 `0x143EC8660–0x143EC8694` 只把这类 section 的 `+0x18` buffer 收进 `cooker+0xC0`。`FVoxelAsyncPhysicsCooker_Chaos::CookMesh` 于 `0x143ED5B30–0x143ED5B55` 累加这些 buffer 的顶点数 `+0xCC`、主索引数 `+0x154`；再按累计顶点数是否达到 `0xffff` 选择 16 位或 32 位三角形构造分支（`0x143ED5B84–0x143ED5B94`）。这两个 `CreateTriMesh` lambda 都从同一 buffer `+0x138` 的主索引数据取三元组（16 位分支 `0x143E9EEDA–0x143E9EFA3`，32 位分支 `0x143E9F2D3` 起），按累计顶点基数调整后交给 Chaos；因此在上述条件成立时，过渡三角形确实成为碰撞构造的输入。最终旧 cook 仍必须通过[09](09-collision-result-acceptance.md)的弱组件、当前 cooker 编号、任务状态及 BodySetup 门才会提交；本次静态读取不能证明 Chaos 最终实际保留每个三角形，也不能测量接缝接触效果。

## LOD 2 / LOD 1 正 X 构造演算

继续[21](21-lod-seams-and-transition-mesh.md)的**构造样例，非存档或运行观测**：LOD 2 当前块原点 `(0,0,0)`、边长 `128`，LOD 1 正 X 邻块盒 `[128,192)×[0,64)×[0,64)`；假设可见、交盒、`settings+0x36=0` 等门通过，则查询点 `(160,32,32)` 找到该邻块并置方向 mask `0x02`。再假设本实例的 mesher mode 选择会生成 `FVoxelChunkMesh` 过渡结果，renderer 接受普通与过渡任务，且二者所选材料都有非空索引 buffer：`GetMeshesToBuild` 为该材料 section 挂 `普通+0x18` 与 `过渡+0x28`；Mixed 若收到碰撞 bit 1，把动作送 Basic；Basic 合并把两份索引（过渡索引加普通顶点数作为基数）写入输出主索引；组件 section 碰撞位为 1 时，cooker 从该输出主索引生成三角形。即使普通 buffer 缺失，只要同一分组中有效过渡 buffer 留下，合并函数也会计入其索引；是否会实际形成该分组取决于材料查找和前述门。若没有碰撞 bit 1，或 transition `FindBuffer` 为空，这个结论分别停在组件资格或过渡 buffer 入口。此样例不证明主关卡实际采用 Marching Cube，也不证明用户触碰该接缝时物理连续。

**Answered（静态）**：普通/过渡 `FVoxelChunkMesh` 在 `GetMeshesToBuild` 中分别取 buffer 并存入 section `+0x18/+0x28`；Basic 与 Clustered 的条件路由；两源索引进入同一输出主索引 buffer；组件碰撞位筛选后，Chaos cooker 实际读取该主 buffer 的顶点与三角形索引。

**Partial / Unknown**：MainLevel 实际 mesher 动态类型、当前 render octree 是否出现构造邻对、各 chunk flags/材料 buffer 是否满足门、主/过渡任务的运行时先后、Chaos 最终形状是否保留所有三角形及接缝物理连续性。`GetMeshesToBuild` 的一处材料/模式分组条件和合并函数的普通输入状态门有可见静态分支，不能外推每个普通网格必进入输出。

**Not Run**：游戏/Unity 启动或附加、目标函数执行、GPU 或物理接触观测、私人存档读写、制档测试、安装软件。报告只提供独立实现可参考的行为规格，不携带目标代码或资产。
