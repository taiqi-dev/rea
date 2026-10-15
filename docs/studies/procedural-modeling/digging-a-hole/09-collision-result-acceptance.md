# 掘地求财：碰撞烹制结果的最终接受门

[07](07-material-slots-and-handler-selection.md)给出 `MainLevel` 的静态初始配置会选 Mixed；[08](08-mixed-handler-submission-chain.md)证明 Mixed 把碰撞标记交给 Basic，Basic section 可经 `FinishSectionsUpdates → UpdateCollision` 进入组件碰撞重建。本篇只追**已编入这批游戏 EXE 的异步 Chaos cooker** 从旧任务取消到结果提交的门。仍未启动或附加游戏；不能据此断言每次挖掘均启用异步 cook。

## 身份与原文

EXE/PDB、安装版本和匹配方式沿用[00](00-evidence-and-reproduction.md)，没有重算摘要。本轮以本地 PDB 精确掩码查询 `*VoxelAsyncPhysicsCooker*`（13/13）、`*FVoxelAsyncWork*`（15/15）、`*FinishCollisionUpdate*`（1/1）、`*PhysicsCallbackHandler*`（8/8），均 `exhausted=true`；再以 VS 2022 `dumpbin /DISASM /RANGE` 读取对应函数、以 `/RAWDATA:8 /RANGE` 读取 Chaos cooker 虚表。新原文在 ignored `.cache/procedural-modeling/static-resource-followup/digging-a-hole/` 的 `collision-symbols.json`、`callback-symbols.json`、`cooker-ctor.disasm.txt`、`cooker-post-v2.disasm.txt`、`callback-tick.disasm.txt`、`work-threaded.disasm.txt`、`work-abandon.disasm.txt`、`component-destroy.disasm.txt`、`cooker-vftable.raw.txt`；复用[05](05-task-lifetimes-growth-and-performance.md)的 `collision-update.txt`、`cancel-task.txt`、`cook-finalize.txt` 与[01](01-excavation-and-local-rebuild.md)的 `collision-finish-disasm.txt`。下述地址均为该 EXE 的 VA。

## 取消、入队与当前任务身份

**观察。** `UVoxelProceduralMeshComponent::UpdateCollision` 在 `0x143EF5AB9–0x143EF5AD2` 若 `component+0x580` 非空便对旧 cooker 调 `CancelAndAutodelete`，**不检查返回值**就将该字段清零。`CancelAndAutodelete` 在 `0x143E64157–0x143E641AC` 设置任务 `+0x5C=1`、递增 `+0x58`，读取 `+0x20`：旧值 `>0` 时调用虚表 `+0x28` 删除任务并返回 true；旧值 `<=0` 时返回 false。`FVoxelAsyncWork::DoThreadedWork` 在 `0x143E6BC96–0x143E6BCCF` 于工作前后检查 `+0x58`，后置临界区内若取消标记 `+0x5C` 非零则改走删除路径。因此取消可阻止尚未入队的完成回调，但返回值、调用时机和已入队记录不能混作“最终结果已拒绝”。组件销毁也在 `0x143EEBD3E–0x143EEBD4F` 取消并清空当前 cooker 字段。

**观察。** 新 `IVoxelAsyncPhysicsCooker` 构造于 `0x143EC8520–0x143EC856F` 将进程内计数器 `0x14859D3B8` 加一，写入 cooker `+0x68`（64 位唯一编号），把组件的 `FWeakObjectPtr` 放在 cooker `+0x70`，并保存组件 `+0x528/+0x530` 的弱 callback-handler 引用到 cooker `+0x78/+0x80`。`UpdateCollision` 在 `0x143EF5C31–0x143EF5C66` 构造本作的 `FVoxelAsyncPhysicsCooker_Chaos`，**先写** `component+0x580 = newCooker`，再调用优先级处理器虚表 `+0x08` 排入工作。`IVoxelAsyncPhysicsCooker::PostDoWork` 在 `0x143EEC346–0x143EEC3C4` 若 callback handler 的引用仍可提升，分配 24 字节队列节点，把 cooker `+0x68` 编号和 `+0x70` 弱组件引用复制到节点 `+0x08/+0x10`；节点不保存 cooker 指针。这说明任务完成事件与当前 cooker 必须在消费端重新关联。

## 队列消费的精确接受条件

**观察。** `FVoxelRendererMixedMeshHandler::Tick` 先于 Basic 提交调用两个 `PhysicsCallbackHandler::TickHandler`（`0x143EF3BBE`、`0x143EF3BCE`），又于 Clustered 提交前调用其 handler（`0x143EF3C0F`）；`Basic::Tick` 独立路径也在 `0x143EF3AF5` 调该消费者。`TickHandler` 于 `0x143EF40B0–0x143EF40E9` 出队并取节点中编号与弱组件。其后逐门检查：

| 顺序 | EXE 指令                                                                         | 拒绝条件与效果                                                                                               |
| ---- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| 1    | `0x143EF40F3–0x143EF40FA` 的 `FWeakObjectPtr::IsValid`                           | 组件弱引用无效则跳回消费循环。                                                                               |
| 2    | `0x143EF4109–0x143EF4113` 读取 `component+0x580`                                 | 当前 cooker 指针为零则跳过。                                                                                 |
| 3    | `0x143EF4115–0x143EF411E`：`mov rax,[currentCooker+68h]; cmp [rsp+20h],rax; jne` | **队列节点编号 `ID_queued != ID_current` 则跳过**；不是比较 cooker 指针，也未见按 chunk 令牌或版本大小排序。 |
| 4    | `0x143EF4120–0x143EF4135` 读取当前 cooker `+0x20`，再检查 `component+0x578`      | `+0x20 <= 0` 或当前 BodySetup 为空则跳过。                                                                   |

只有上述门都过，`0x143EF413B` 才清当前 BodySetup 的 physics meshes；`0x143EF415A` 调 cooker 虚表 `+0x48` 并检查返回值。发行 EXE 的 `FVoxelAsyncPhysicsCooker_Chaos` 虚表 `0x1471B17B0 + 0x48` 实际指向 `0x143EDD7F0 Finalize`；此函数把 cooker 的网格结果转给 BodySetup，设置状态位，并在 `0x143EDD876` 返回 true。若虚调用返回 false，`0x143EF415F` 直接跳回循环，**不**走下面的完成交换；Chaos 这份实现的所读函数本身没有 false 返回分支。成功后 `0x143EF4165–0x143EF41E8` 更新内存统计，`0x143EF41EF–0x143EF4205` 对当前 cooker 调 `CancelAndAutodelete`、清 `component+0x580`，再调用 `FinishCollisionUpdate`。后者在 `0x143EDDE86–0x143EDDEA5` 交换 `component+0x570/+0x578` 两个 BodySetup 指针后调用 `RecreatePhysicsState`，并清被换出的旧 BodySetup 的 physics meshes。`Finalize` 前已经执行的 `ClearPhysicsMeshes` 是可见副作用；上述拒绝门之前不调用它。

**构造演算，非运行观测。** 假设组件 C 的旧 cooker A 编号 101 已经 `PostDoWork` 入队；随后 C 的新 section 触发 `UpdateCollision`，即使取消 A 返回 false，代码也清 `C+0x580` 并为新 cooker B 分配编号 102。轮到 A 的节点时，弱引用仍有效且 `C+0x580=B`，但 `ID_queued=101 != [B+0x68]=102`，在 `0x143EF411E` 被拒，尚未清 BodySetup。若 B 的节点后到且 C 仍有效，`102=102`，`B+0x20>0` 且 BodySetup 存在，则可进入 `Finalize → FinishCollisionUpdate → RecreatePhysicsState`。若新更新不再创建 cooker，`C+0x580=0` 于第二门拒绝 A；若 C 已销毁，第一门拒绝。该演算证明这条静态消费路径不会仅因**旧 cook 曾入队**而将其错当当前结果，不声称实时调度中一定发生该次序。

## 结论与边界

**Answered（静态）：** 在 MainLevel 初始 Mixed 条件下，碰撞支路进入 Basic 的组件更新；异步 Chaos 结果的最终门是“弱组件有效、当前 cooker 存在、`ID_queued == [currentCooker+0x68]`、当前任务 `+0x20>0`、当前 BodySetup 存在、`Finalize` 返回 true”。旧 cooker 的取消返回 false 不会使旧队列节点自动获准，旧节点仍受当前编号相等门；接受后才进入 BodySetup 交换和物理状态重建。

**Unresolved（静态）：** 这批场景每个 chunk 是否启用碰撞、是否进入异步分支，游戏线程的实际调度/竞态顺序、进程内 64 位编号极端回绕、引擎内部 `RecreatePhysicsState` 成功与否及物理可见时延。`Finalize` 失败分支在消费者中存在，但本作 Chaos `Finalize` 可见实现返回 true；本轮不把其他潜在 cooker 实现或异常情况概括为同一行为。**Not Run（运行）：** 游戏、附加、碰撞抓取和耗时/内存测量；未读取私人存档。目标代码与资产不作为自研产品交付。
