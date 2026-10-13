# 05 姿态：参考形状、粒子约束与骨骼重建

[目录](README.md) · [足部目标](04-gait-synthesis-and-foot-targets.md)。姿态不是仅靠一个动作文件决定：编辑器参考姿态给出偏好，动作给出目标，骨长和连接关系约束可行解，最终再转换为骨骼变换。

公开设计采用粒子约束，并区分脊柱、肢体和附属运动；详见 00 的动画来源。**以下距离投影公式、迭代器、权重和双骨示例为独立实现规格，不声称是原作精确求解器。**

## 输入与求解状态

参考骨骼、动态局部增量和已经求解的绝对姿态怎样避免重复合成，见[30](30-part-shape-rest-pose-and-local-animation.md)。绝对PoseResult不能再无条件乘一遍参考弯曲矩阵。

输入：BodyGraph、参考姿态、当前目标、上一帧结果。状态：求解点的位置、约束列表、参考朝向、目标权重。输出：骨骼位姿、每类约束残差和不可达原因。

```text
Point { nodeId, position, referencePosition, inverseMobility }
DistanceConstraint { a, b, restLength, stiffness }
TargetConstraint { point, targetPosition, weight, sourceChannel }
BendPreference { chain, referenceBendPlane, weight }
SolveReport { iterations, maxLengthError, maxTargetError, reasons[] }
```

`inverseMobility` 控制调整分担，不表示游戏角色的真实质量。固定点为 0，可动点为正数；重建骨骼时另用旋转。参考姿态不能每帧被最终解覆盖，否则几帧后“玩家摆出的弯曲方向”就会漂移。

## 为什么脊柱可以少求解一些点

公开论文 §4.3 的一项具体设计是在脊柱 IK 分支处放粒子，用五次 Hermite 曲线重建中间身体，并以参考形状抑制折叠；肢体阶段使用朝目标调整参考骨链的预处理。它不是简单地对每根骨头分别做双骨 IK。[开发团队动画论文](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

独立重组结构如下；分支规则、拟合权重和方向估计仍是我们选定的实现政策，不是本机恢复代码。

```text
ReducedSpineSegment {
    endpointNodeA, endpointNodeB
    referenceSpline, referenceEndpointFrames
    interiors[]: { nodeId, parameterT, frameRelativeOffset, frameRelativeRotation }
}
BuildOwnReducedSpine(body, goalNodes):
    marks = root + spineEndpoints + attachmentsOfActiveGoalChains
    for adjacent marked endpoints:
        referenceSamples = interveningRestJointPositions
        curve = FitOwnQuintic(referenceSamples, ownFitPolicy)
        if curve.failed: return Error(SpineFitFailed, endpointIds)
        for interior body:
            t = OwnClosestCurveParameter(curve, body.restPosition)
            frame = OwnTransportedFrame(curve, t)
            save t, inverse(frame)*body.restPosition,
                    inverse(frame.rotation)*body.restRotation
    return segments
```

足部/手部目标先给脊柱一个简化的可达需求：连接身体附着点到末端目标，使用参考连接的长度范围；脊柱调整后再求完整骨链。自研规格以此避免“身体完全固定、每条腿只好硬拉伸”的失效状态。简化距离用参考端点弦长还是路径长度，必须作为策略分别记录；不能混为同一个数。

曲线重建可以用一般五次 Hermite 边界关系独立实现。以下 t∈[0,1]，P0/P1 是两端位置，V0/V1 是对归一化 t 的一阶导数，A0/A1 是二阶导数，不是角色速度/加速度：

```text
a0 = P0; a1 = V0; a2 = A0/2
D = P1 - a0 - a1 - a2
E = V1 - a1 - 2*a2
F = A1 - 2*a2
a3 = 10*D - 4*E + F/2
a4 = -15*D + 7*E - F
a5 = 6*D - 3*E + F/2
P(t) = a0 + a1*t + a2*t^2 + a3*t^3 + a4*t^4 + a5*t^5
```

给定端点位置后，独立拟合策略可把 V0/V1/A0/A1 作为未知量，以参考样本的平方误差建立线性最小二乘，使用 QR 解算并检查秩；参考样本不足时返回明确的降级报告并选择线性段。参数 t 的初值可由累计弦长归一化，再迭代更新。原游戏拟合参数化、权重和退化策略尚未恢复。

求解出新的端点状态后重建曲线、运输框架，再把保存的局部偏移和旋转放回去。内部骨头不是“沿曲线一律等距排列”。我们还要求重建后测量实际骨长误差，避免误以为端点约束满足就保证全部中间骨长不变。

## 一条距离约束怎样修正

令两点位置 xa、xb，期望骨长 L，`d = xb−xa`，`C = |d|−L`，`n=d/|d|`。自研投影：

```text
wa = point[a].inverseMobility
wb = point[b].inverseMobility
if wa + wb == 0:
    if abs(C) > tolerance: report FixedConstraintConflict
else:
    xa += stiffness * wa/(wa+wb) * C*n
    xb -= stiffness * wb/(wa+wb) * C*n
```

例：xa=0，xb=1.2，L=1，wa=wb=1，stiffness=1。修正后 xa=0.1、xb=1.1，距离变为 1。若 a 固定，只把 b 从 1.2 移到 1。长度接近零时不能直接除以零；自研规则优先用参考方向，否则报告 `DegenerateReference`。

目标投影与骨长投影会互相影响，通常需要迭代。目标可以不可达，不能无限迭代后假装精确命中。

```text
SolveOwnPose(body, goals, previousPose):
    points = InitializeFromPreviousPoseOrReference(body, previousPose)
    ValidateLengthsAndFiniteValues(points, body.constraints)
    spineDemand = BuildOwnSimplifiedLimbDemands(body, goals)

    for iteration in 1..ownMaxIterations:
        RestoreOwnSpineMobilityForSpinePass(points)
        ApplyOwnRootBoundary(points)
        ApplyTargets(points, goals.spineTargets, ownTargetGain)
        ProjectOwnSimplifiedLimbDemands(points, spineDemand)
        ProjectOwnSpineConstraints(points)
        ApplyOwnReferenceBendBias(points)
        FixChosenSpinePointsForLimbPass(points)
        ApplyTargets(points, goals.limbTargets, ownTargetGain)
        ProjectOwnLimbAndBranchConstraints(points)
        errors = MeasureAllResiduals(points, goals)
        if errors <= ownTolerances: break

    if anyNonFinite(points): return Error(NumericalFailure, affectedNodes)
    return PoseResult(RebuildOwnBones(points, referenceFrames),
                      residuals = errors,
                      diagnostics = DiagnoseUnmetGoals(errors))
```

这个迭代顺序是我们的简化选择。Spore 如何初始化、插值脊柱内部点、分配权重、处理分叉和最小扭转，仍需原生代码与资源；不可将本段当作论文算法逐句翻译。

## 双骨链为什么有两种弯法

两段长度 l1、l2，根点 R，目标 T，距离 D。骨链可达要求 `|l1−l2| <= D <= l1+l2`。在沿 RT 的局部二维框架中：

```text
x = (l1*l1 - l2*l2 + D*D) / (2*D)
h = sqrt(max(0, l1*l1 - x*x))
elbow = R + axis*x + bendDirection*h
```

两段各 0.5 m，目标距根 0.6 m，得到 x=0.3 m、h=0.4 m。肘/膝可以位于 `(0.3,+0.4)` 或 `(0.3,−0.4)`，两者都满足骨长。参考姿态提供弯曲方向偏好，因此“脚到了同一个点”仍可能有不同姿态。

自研规则用编辑时的弯曲平面作为 pole direction；接近伸直奇异点时保存上一有效方向，并明确报告方向约束弱化。目标过远可投到 `l1+l2−epsilon`，同时输出原目标误差；不得只钳制后宣称原目标可达。D≈0 需要单独折叠分支，不能沿用上式。

双骨公式只适用于单根两段链。分叉成两只手的共享上臂必须作为整体协调，否则分别求两链会把公共关节写成两个位置。

## 分叉、躯干与旋转

独立分叉例：根 A→共享节点 B→末端 C/D。求解器只存一个 B；两个目标以各自权重拉动 C/D，然后约束 AB、BC、BD。若动作要求两个末端过度张开，结果是目标残差增大，不是偷偷复制 B 或任意拉长骨头。

参考姿态偏好用于抑制不必要折叠：自研选择轻度拉回参考弯曲平面，每次随后重新投影骨长。硬锁全部参考角度会阻止动作适配；完全不保留偏好会在等价解间翻转。

只有点位置还不足以决定完整旋转。沿骨方向的扭转仍自由。自研骨骼重建以参考切向框架平行运输，再应用显式扭转通道；左右镜像要重新构造右手坐标系，不能把一个镜像矩阵直接当普通旋转。

附属尾、耳、装饰可独立使用阻尼摆动。是否存在碰撞、体积保持、关节角限位，必须分别声明；当前自研规格没有完整自碰撞，原游戏对应边界也未在本机验证。

## 算法成本与诊断

每次投影一条约束为常数成本，粗略 `O(iterations × (constraints + goals))`；这不是本机性能测量。保存每类最大误差比只报告“收敛失败”更有用：能区分固定点冲突、不可达目标、退化方向与迭代预算不足。

未做：原生求解器恢复、实际骨骼轨迹比较和奇异点运行测试。风险：上述几何算例不验证分叉收敛、扭转稳定性或任意体型的视觉质量。
