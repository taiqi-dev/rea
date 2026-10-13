# 06 编辑交互：滚轮、附着、镜像与重建

[目录](README.md) · [已有附着研究](02-skill-selection-and-editor-attachments.md)。用户观察是：身体加宽时，两侧肢体也向外分开。这提示附着点依赖当前身体，但不能唯一确定实现。以下给出完整的独立编辑规格。

## 输入必须先确定操作对象

滚轮可能作用于身体半径、部件整体尺度、形变手柄或镜头；先命中并确定活动工具，才能解释同一种输入。社区字段包含连接、表面法线、用户方向和变形权重，提供研究入口，但没有恢复事件分发与滚轮公式。

```text
EditorOperation {
    targetPartId, handleId?, kind
    beforeRecipe, proposedRecipe, baseRevision
    status: Preview | Committed | Cancelled | Failed
}
HandleKind = SpineRadius | JointMove | PartScale | PartRotate | MorphWeight
```

我们规定一次拖动/滚动序列是一项可撤销事务。预览改变派生模型；提交记录配方差异；取消恢复 beforeRecipe，不从当前动画姿态倒推原编辑值。

## 表面附着的独立模型

为了明确公式，自研身体近似一组沿中心线 C(u) 的圆形截面。其局部框架为切线 t 和两个法向 n、b：

```text
radial = cos(theta)*n(u) + sin(theta)*b(u)
mountPosition = C(u) + (radius(u)+normalOffset)*radial
mountRotation = SurfaceFrame(u, theta) * userRotation
```

部件保存 u、theta 和偏移，而不是仅保存世界 xyz。加宽后重新计算截面半径和附着点。例：C 不变，左右 theta 分别 0/π，偏移为 0，半径 0.4→0.7 m，每侧外移 0.3 m，两侧距离 0.8→1.4 m。原游戏身体是更复杂的表面，这个圆截面公式只验证一种可行机制。

椭圆截面不能仍把“径向方向”当实际表面法线；法线应来自椭圆梯度或当前网格。整体非均匀缩放时，法线用逆转置更新。若宿主重拓扑导致原三角形消失，应使用稳定形态坐标或显式重投影；本机采用哪一种未知。

## 滚轮更新与镜像

自研半径映射使用指数增量，避免同样一格对粗/细身体的相对变化不同：

```text
newRadius = clamp(oldRadius * exp(k * wheelDelta), minRadius, maxRadius)
```

k、限值、delta 单位都是自研配置，没有恢复 Spore 数值。半径变化可按邻近控制点权重扩散，但影响曲线必须明确；存在同名调节字段不证明它采用高斯、线性或其他核。

镜像绕自研身体中轴平面处理位置；左右共享源操作语义，各自重新计算框架。镜像方向有反射，不能直接用负尺度代替全部旋转和法线处理。编辑一侧是否同时更新另一侧取决于显式镜像状态，不按位置“看起来对称”推断。

```text
PreviewWheel(input, editor):
    hit = ResolveSelectedHandleOrPick(input.pointer)
    if hit.none: return PassToConfiguredCameraTool
    operation = BeginOrContinueTransaction(hit, editor.recipe)
    proposed = ApplyOwnHandleRule(operation.beforeRecipe, input.accumulatedDelta)
    ValidateRecipe(proposed)
    UpdateOwnMirrorPartner(proposed, hit, editor.symmetryState)
    dirty = CompareSemanticChanges(operation.beforeRecipe, proposed)
    operation.proposedRecipe = proposed
    PublishPreviewRecipe(proposed)
    return RebuildAffectedDerivedData(proposed, dirty)
```

这里累计 delta 基于事务起点，不在每帧反复把总增量乘到上一次预览半径上，否则会放大输入。

## 哪些修改使哪些缓存失效

| 修改 | 自研失效项 | 可保留项 |
| --- | --- | --- |
| 增删/重连肢体 | 身体图、绑定、步态、网格、UV、绘制 | 仍有效部件的稳定 ID |
| 身体粗细与部件形变 | 表面、附着、参考姿态、相关目标尺度、UV/绘制 | 能力标签不变时的资格索引 |
| 只改变关节参考方向 | 参考框架、相关绑定派生尺度与姿态 | 结构与能力；表面未变时的贴图 |
| 只换颜色/花纹 | 材质结果与烘焙任务 | 身体图、足部相位与动作资格 |
| 动作播放产生的姿态 | 当前骨骼变换 | 配方、参考姿态与固定拓扑 UV |

这是我们的依赖契约，不能断言原游戏每次滚轮都重做整张贴图。刚体/蒙皮动作和编辑造成的结构变化必须区分，详见 07。

## 同步预览与异步结果

[30](30-part-shape-rest-pose-and-local-animation.md)补充Baked/LivePreview模式、造型后的内部绑定与动态profile适配；完成烘焙后不再执行同一组编辑造型轨道，动作结束回到当前参考而非源资产默认形状。

[29](29-creature-mesh-joins-and-automatic-skinning.md)补充网格、权重、inverseBind、骨骼索引和附件锚点的同版本重建。其加宽算例说明新参考顶点混用旧绑定会重复外移；这仍是自研依赖契约。

```text
RebuildAffectedDerivedData(recipe, dirty):
    revision = recipe.revision
    body = BuildOwnReferenceBody(recipe, dirty)
    preview = BuildOwnFastPreview(body)
    job = SubmitOwnBake(immutableCopy(recipe), revision)
    register job with materialOwner
    return {preview, jobId, revision}

OnBakeComplete(job, result):
    if result.failed:
        record BakeFailed(job.id, result.reason)
        releaseOwnedJobResources(job)
        return
    if job.revision != currentRecipe.revision:
        record BakeSuperseded(job.id, job.revision)
        releaseOwnedResult(result)
        return
    SwapInValidatedModelAndMaterial(result)
    releasePreviousOwnedResources()
```

版本失配要丢弃旧结果并保留原因，不能让慢任务覆盖玩家刚完成的新形体。资源释放失败仍保留所有权并报告，不能丢失引用后称清理成功。

未做：原游戏滚轮映射、事务边界、表面投影、邻点影响与实际缓存顺序。风险：圆截面演算不能代表融合身体全部局部法线和分叉区域；异步规格尚未实现或压测。

后续：[33](33-shape-revisions-collision-hit-and-ai-sync.md)补加宽/断肢/换体后几何、命中与灵魂评估同步；[34](34-editor-validity-complexity-and-runtime-cost.md)补合法性、成本和预览/编译事务。二者是独立规格，不扩大本页原作交互证据。
