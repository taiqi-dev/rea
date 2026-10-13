# 42 分叉肢体、共享关节与目标冲突

[目录](README.md) · [粒子IK与参考姿态](05-particle-ik-and-rest-pose.md) · [并行动作](28-parallel-actions-channel-ownership-and-conflicts.md) · [接触约束](32-body-volume-contacts-and-self-collision.md) · [镜像与安装](41-mirroring-mount-frames-and-action-coordinates.md)。

限定陆地生物及编辑器。一条上臂分成两只手时，两只手不是两条完全独立的骨链：它们使用同一个分叉关节。第1节列原作证据；其余是自研规格、算法与构造例子，不声称恢复了 Spore 的求解器。

## 1 原作证据：拓扑、目标与求解是三个层次

开发团队论文§4.3.3明确：肢体阶段给各关节分配粒子；有多个带IK目标的直接孩子时加入交叉约束。分叉预处理使用子树目标的加权平均，并向外递归；位置求解后再重建方向。论文同时承认目标可冲突、不可达或造成不自然姿态。[动画论文第7–9页](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

这给出了历史设计的结构，但没有给出每类权重、交叉约束容差、所有退化分支或本机动作裁决。原公开求解允许一定伸缩；下面选择固定骨长的自研例子，不用论文的缩伸比例当自有默认值。

| 证据层 | 读到了什么 | 边界 |
| --- | --- | --- |
| 开发团队§4.2 | 从脚沿连接段到脊柱的路径，支持分叉腿结构 | 不是“每只脚单独创建一条完整骨架” |
| 社区EditorRigblock | mpParent、mChildren、连接骨变换、端/基/中关节索引 | 容器容量8不证明每部件只能有8个孩子 |
| 社区CreatureBlock、anim_cid | parentIndex/pParent以及实例到描述块的链接 | 类型/字段存在不证明原作采用某种冲突仲裁 |
| 37实际所选手的RW4元数据 | 10骨层级含一个公共根与三条子链 | 是该部件的内部骨架，不能称为三条整生物手臂或三根真实手指 |

复用所选手模型2f4e681b:40606000:0df11468，解码内容摘要9575d53175a28240c4ce591664fa66dee8eb962bf659ada1f00c8d1a5d28b9dc。既有元数据中section16的父索引产生：

~~~text
0 -> 1 -> 2 -> 3
0 -> 4 -> 5 -> 6
0 -> 7 -> 8 -> 9
~~~

本轮仅从现有JSON重新检查该树及稳定索引，不重读模型顶点、纹理或完整动画。两个局部动画目录各有10个channel ID，并与此骨架name ID逐项一致；这只建立选中资源的ID对应，未证明它与外部身体的PCTP角色绑定或多手variant机制相同。[本机已选模型元数据](evidence/local-selected-rigblock-metadata.json)、[公开及复用证据](evidence/public-mirror-branch-contracts.json)

SDK的父子关系、对称关系和身体块ID是不同字段；骨架parent_index也不是PCTP mapping.index。全身肢体拓扑、部件内部骨架、求解点集及显示LOD分别拥有映射。[固定EditorRigblock声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/EditorRigblock.h)、[固定骨架格式](https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/rw4/RWSkeleton.java)

## 2 自研：公共关节只能有一个状态拥有者

以下全部是自研政策。动作模块提交目标；身体姿态协调器拥有最终关节状态。每只手保留自己的语义、局部profile、碰撞和执行动作，但不能各自写一份公共肩/分叉点。

~~~text
Joint {
    stableJointId, parentJointId, bodyGeneration, topologyRevision
    referencePosition, referenceFrame, limits, mobility
}
BoneConstraint {
    stableBoneId, endpointJointIds[2], referenceLength
    hardLengthTolerance
}
EffectorGoal {
    actionToken, cohortId, executorPartId, effectorFeatureId
    resolvedJointId, targetPosition, targetRotation
    requiredPositionTolerance, requiredOrientationTolerance
    actionPriority, styleWeight, frameRevision
}
CrossPreference {
    childJointIds[2], referenceRelativeFeature
    kind: HardRigidAttachment | SoftPoseStyle
    weightOrTolerance
}
PoseState {
    one position/orientation per stableJointId
    bodyGeneration, topologyRevision, mountRevision
}
SolveReport {
    requiredGoalResiduals, boneLengthResiduals, limitResiduals
    supportResiduals, collisionResiduals, iterationCount
    status, involvedActions, conflictingJointIds
}
~~~

同一个节点B被路径A→B→C和A→B→D引用两次，状态表里仍只有一条B。求解分区按共享可动自由度和约束依赖连接；共同的固定边界可只读引用，不能复制成两个可写肩膀。脊柱阶段完成后，各分区与32的支撑/接触约束使用一致版本，最终一次提交整个姿态包。

31的锁脚、32的接触/碰撞，以及关节限位会使“单看末端距离够得着”仍然不可行。能力和灵魂策略只能选择身体可执行的目标；不能把两个独立可达判断当成联合可达证明。

cross-constraint也要声明性质：刚性分叉附件需要硬相对关系；带独立关节的分叉可用软姿态偏好。禁止把所有孩子之间的距离都硬锁到参考值，否则张开/合拢的动作可能被误判失败。这里的策略是自有资产契约，不是对原作权重的猜测。

## 3 自研：目标先协调，再共同求解

控制归属延用28的自由度政策，同角色标签不自动授权共享。位于不同末端的动作即便没有直接写同一通道，也可能通过共同祖先争用身体工作空间。

~~~text
BuildOwnGoalComponent(body, incomingGoals):
    validate finite targets and generation/topology/frame revisions
    resolve stable effectors; reject missing/aliased features
    pin each fixed boundary once
    for each goal:
        collect ancestor joint DOFs to its allowed boundary
        record action dependencies and required cohort
    union goals sharing movable DOFs or coupled constraints
    detect inconsistent mandatory goals on the same joint
    return components and diagnostics

PrepareOwnBranch(component, reference):
    keep reference geometry immutable
    visit branches rootward to compute descendant goal sets
    at a shared branch:
        centerRest = weighted mean of descendant reference effectors
        centerGoal = weighted mean of their targets
        if either direction is degenerate:
            keep last valid/reference frame; report AimDirectionWeak
        else:
            aim using own minimal rotation and bounded temporary axial scale
        recurse outward into each child branch
    temporary points may violate lengths; never overwrite reference lengths
~~~

actionPriority决定动作取舍，styleWeight用于姿态偏好/预处理；两者不能混为同一权重。归一化加权平均前要求总权重大于0，且同一目标不会因两条祖先路径被重复计数。临时aim只是初值，不是已满足骨长和碰撞的结果。

本方案的aim可具体写为：r=centerRest−branchAnchor、t=centerGoal−branchAnchor，u=r/|r|、v=t/|t|；用将u转向v的最小旋转R。非反向情况下令a=u×v、c=u·v、K为a的叉乘矩阵，则R=I+K+K²/(1+c)。近反向时用有效参考pole在垂直u的平面内投影来选择180°轴，投影退化则保留参考框架并报AimDirectionWeak，不直接除以1+c。临时伸缩s=clamp(|t|/|r|,0.25,4)，F=(I+(s−1)vvᵀ)R；以分叉锚点为中心对临时点应用F，再向孩子递归。0.25/4是本例自研预处理预算，不是原作参数；发生夹持另报AimScaleClamped。F允许暂时缩伸，不能作为41要求正交的安装旋转或覆盖参考骨长。此完整3D预处理公式是规格，32项检查未验证它在任意分叉上的收敛。

~~~text
SolveOwnComponent(component, reference, lastValidPose):
    x = one shared joint-state table from PrepareOwnBranch
    for iteration in bounded budget:
        apply admitted target corrections into owned DOFs
        project all bone lengths, joint limits and fixed boundaries
        project current support and contact constraints
        apply soft cross/reference preferences
        recheck hard constraints after soft changes
        measure every required goal and hard residual
        if all required tolerances met:
            reconstruct proper frames and declared twist
            if reconstructed constraints valid: return Success(x, report)
    return FailedCandidate(x, actual residuals, IterationBudgetExceeded)

CoordinateOwnActions(component):
    try all currently admitted action cohorts together
    if solve fails:
        keep previous valid pose; retain diagnostics
        try lower-priority cohort removal in declared stable order
        re-solve from immutable reference/current valid state
        publish only if remaining required goals and hard constraints pass
        mark rejected cohort FailedPoseConflict; release only its reservations
    if no valid set: reject action update, keep previous valid pose
~~~

“预算用尽”不证明数学上不存在解。对特定简单拓扑可用几何判别直接证明冲突；一般图保留残差和预算原因。不得把最小误差候选直接发布为已达目标，或因一个末端成功就把另一末端的动作也标成功。

需要两只手共同交接物品的动作应为不可拆cohort：任一必需目标失败时，整个交接取消，不能静默退化成单手成功。两个独立动作可分别裁决；掉低优先级动作后仍由剩余动作占用公共关节，不能全部解锁。

## 4 自研：距离修正怎样共用一个B

以下是05自研节点投影的具体协作形式。边a→b长度L、d=xb−xa，误差C=|d|−L，端点可动权重wa/wb：

~~~text
delta_a = wa/(wa+wb) * C * normalize(d)
delta_b = -wb/(wa+wb) * C * normalize(d)
~~~

固定点权重0；两端都固定且有误差返回FixedConstraintConflict。零距离使用明确的有效参考方向，没有方向则DegenerateReference。骨长/输入非有限或负可动权重也拒绝。

所有边直接引用共同状态表，不能先在每条链内求出B，再“平均两份B”而忽略重新核对骨长。接触约束若同一节点出现在多个梯度槽，要先按稳定ID合并梯度，再计算投影分母；相反梯度可能抵消。按两个槽分别推动同一个节点会产生错误修正。

旋转另需处理：父骨方向可从位置确定，但轴向扭转仍有自由度。自研使用参考框架运输、显式扭转目标和限位，不任意取某两条近共线边组成坐标系。分叉边退化时保留有效参考方向并输出诊断，不制造NaN或随机翻转。41的镜像pole/frame规则与此共享契约。

## 5 自研贯通算例：单独都够得着，合在一起有冲突

使用二维位置，单位米；这是一个可精确判别的自研简化例。A=(0,0)为固定根，AB、BC、BD的长度全为1。参考B=(1,0)、C=(1,1)、D=(1,-1)。刚性骨长是硬约束；孩子之间只用软风格偏好，未硬锁CD=2。

两个独立动作：C抓取优先级20、目标TC=(1.5,0.5)；D指向优先级10、目标TD=(1.5,-0.5)。每个目标距离A为√2.5≈1.581139，小于两段路径长度2；各自的双圆交点也存在，故单独可达。

**联合预处理。** 两个styleWeight均为1，目标均值(1.5,0)，参考末端均值(1,0)。共享分叉预处理的轴向临时尺度为1.5；递归到孩子后可把C/D先放在目标上，但AB变1.5、BC/BD变0.5。这是有长度错误的初值。

**联合可达判别。** 若C/D都精确到目标，B必须同时落在两个半径1的圆上。它们交于：

~~~text
B1 = (1.5 - sqrt(0.75), 0) = (0.633974596, 0)
B2 = (1.5 + sqrt(0.75), 0) = (2.366025404, 0)
~~~

AB要求|B|=1，两个候选都不满足；最近的AB误差仍为0.366025404 m。因而本例不能同时精确满足三段长度与两个目标。该数不是一般软容差下的误差界。

若每个末端允许0.01 m位置误差，本例仍可独立证明冲突。令B=(cosθ,sinθ)，它到TC/TD的距离平方分别为3.5−3cosθ∓sinθ。满足骨长1且末端距原目标不超过0.01，要求这两项距离都在[0.99,1.01]。两平方之差使|sinθ|≤0.02，因此|cosθ|≥0.99979998；它们平方的平均值3.5−3cosθ只能≤0.5006001或≥6.4993999，均在所需[0.9801,1.0201]之外。这是本例特有的判别，不能代替一般图的残差测量。

**取消较低优先级D动作，重新求C。** 固定A和TC，求AB=BC=1的交点，选择最靠近参考B的一支：

~~~text
B = (0.943649167, -0.330947502)
C = (1.5, 0.5)
|AB| = |BC| = 1
~~~

D动作被明确标记FailedPoseConflict，不再要求TD。D进入自身中性偏好：令其相对B的方向随AB旋转，取(B.y,-B.x)，得到D≈(0.612701665,-1.274596669)，BD仍为1。这只是本例选定的中性政策，非原作“未选中身体”必然的位置。

公共B只写一次；C抓取仍持有相关占用。D的动画预约释放，C在检查接触与自己的动作承诺条件后才能执行抓取结果，姿态成功不会直接提交伤害或物品所有权。

**之后断掉D。** 删除D叶与BD约束，保留仍被C路径使用的B。拓扑版本7→8时，版本7后台结果拒绝发布，即使里面仍有看起来合法的B位置。重绑定使用稳定ID，不能按旧数组槽把C的目标套到新部件。若断的是公共B，则C/D都失去路径，需要一起取消。

本例只计算位置；扭转目标、限位、支撑与体内碰撞没有被这组圆交点验证。若硬定义CD=2，两个当前目标距离为1还会另有刚性分叉冲突；这与公共AB约束冲突分别记录。

## 6 失效、验证与未知

| 事件 | 自研明确处理 |
| --- | --- |
| 两目标占同一关节但不一致 | ConflictingGoalsOnOneJoint，禁止后写覆盖 |
| 分叉根/骨长参考退化 | 报告拓扑、方向或长度诊断，不进入无界迭代 |
| 子动作取消 | 去掉其cohort目标/预约；重新计算公共祖先使用集合 |
| 公共关节断开 | 取消所有依赖该路径的动作 |
| 安装/身体/局部骨架版本改变 | 旧目标与结果失效，重绑定 |
| 迭代耗尽或重建产生非法帧 | 保留合法旧姿态及实际残差；不给成功事件 |
| 局部内部骨骼与全身映射变化 | 通过稳定映射重建，不共用不同层的数字下标 |

[检查脚本](checks/verify_mirror_branch_examples.py)实际共32项通过：41有16项、42有14项，另2项核对既有JSON。42覆盖公共节点去重、拓扑环、单独可达/共同不相容、优先级后合法骨长、可行双目标、失败残差、固定约束与零方向、硬交叉约束、取消叶节点、旧结果拒绝、同节点冲突、不可拆cohort及共享梯度合并。完整记录见[验证JSON](evidence/mirror-branch-verification.json)。

原作未知：玩家的任意分叉如何被编译成身体块与求解点、权重/交叉约束的参数、目标排序与失效、近共线重建补偿、分叉内部局部动作与身体求解的层次，以及具体技能是否会取消或重选目标。后续最小自有场景为一根共享上臂接两只手，固定脚时让两手分别对相近、相反和互相冲突的目标动作，记录共享关节唯一性、骨长、末端误差、支撑和取消事件。

未做：游戏启动/附加、私人配方、原生求解器恢复、完整资产导出、生产IK实现、三维画面与性能测试。风险：本轮数学检查只验证简化几何/状态不变量，不证明一般分叉图收敛、最优或视觉自然；原作历史设计及所选手内部树不能代替全身运行证据。
