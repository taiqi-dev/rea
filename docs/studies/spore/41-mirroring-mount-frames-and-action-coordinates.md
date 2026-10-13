# 41 镜像、安装方向与动作坐标

[目录](README.md) · [部件参考与局部动作](30-part-shape-rest-pose-and-local-animation.md) · [部件定义](37-part-definition-edit-controls-rigs-and-capabilities.md) · [身体选择与变体](39-same-role-effectors-variant-binding-and-default-mixing.md)。

限定登陆后、部落前的生物与编辑器。左右部件、左右身体查询、动作镜像和安装方向分别有证据，但本机完整转换顺序没有恢复。第1节记录证据；第2节起是针对自研拼装游戏的独立规格，公式和算例均不是 Spore 源码或原作参数。

## 1 原作能确认到哪里

开发团队论文§4.1.2说明变体生成可产生矢状面镜像，作者能控制动作对不同身体如何特化，包括选择保留一侧动作的情况。这不等于给全部左侧模型设置负缩放。[动画论文第6页](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

本轮重新核对相关完整页，并复用39的动作原值、37的部件与模型元数据；没有重新扫描包或导出模型。摘要、页码、来源哈希、实际字段读取范围及复用记录见[公开与复用证据](evidence/public-mirror-branch-contracts.json)。

| 证据层 | 已有事实 | 不能推出 |
| --- | --- | --- |
| 本机37所选普通手与 symmetric 包装 PROP | 普通手 modelLeftFile→0x0df11468、modelRightFile→0xe53af88e；modelRotation 分别(0,7,-4)/(0,-7,4) | 旋转单位、Euler顺序、消费者以及它是否就是玩家安装旋转 |
| 本机39已选基础 com_charge_rush 通道 | grsp左右主查询为0x8/0x4；foot局部左右为0x20004/0x20000 | 查询得到哪只具体手、局部的精确运行边界，或该通道是否自动镜像 |
| 社区FX固定通道格式 | bindFlags镜像掩码0x32；枚举default=0、left=2、right=0x10、reverseDefault=0x12、never=0x20 | default对该模型是否实际翻转、输入/目标的变换顺序 |
| 社区SDK EditorRigblock | mModelEditorInitialRotation、mCSnapBoneTransform1/2、mCSnapBoneIndex、父子及对称伙伴各自保存 | 原作安装矩阵乘法、轴约定与snap算法 |
| 社区SDK CreatureBlock | symmetricIndex、cal3DBoneName、cal3DOrigin、isLeftHanded | isLeftHanded是否等于负行列式，或某字段的运行时判定 |

本机旋转的相反分量只是选中两个配置的真实差异；不拿这组数证明通用镜像公式。modelRotation与modelEditorInitialRotation是不同属性，不能互相替代。社区声明仅给出名称/类型，本轮不把其内存偏移当成本机ABI。[EditorRigblock固定声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/EditorRigblock.h)、[CreatureBlock固定声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/CreatureBlock.h)、[FX通道格式](https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimationChannel.java)

39的数字secondary类型读写不一致、variantGroup有符号右移诊断继续保留。左右筛选字段不会因此成为绑定后的骨骼ID。PCTP default_value/default_weight的实际混合公式仍未知，下面的几何镜像不改变这一结论。

## 2 自研：把坐标与镜像归属写进契约

以下采用列向量、右手坐标系，矩阵从右到左应用；长度用米、角度在算法入口用弧度。身体解剖框架的X为左右、Y为前后、Z为上下，这是我们的约定。

| 框架 | 保存什么 | 何时变化 |
| --- | --- | --- |
| B：身体根到世界 | 根位置、正交旋转 | 移动和朝向更新 |
| A：部件编辑后的参考安装到身体 | 安装位置、正交旋转、正尺度及连接特征 | 编辑造型/安装事务 |
| S：当前求解后的安装到身体 | 由身体姿态求解输出的位置和旋转 | 每帧求解 |
| P：部件内部 | 编辑后的参考骨架、内部形变和局部特征 | 内部动画与造型版本 |
| K：动作语义框架 | Body、RestEffector、ExternalTarget或PartLocal | 按通道定义及目标更新 |

全肢体的末端目标由参考安装A与动作语义生成，交给身体IK得到S。内部手指/嘴的局部姿态在P内生成，再由S与B放入世界：

~~~text
whole-part goal: authored K -> target in body B -> body solver -> solved mount S
internal part: edited reference P + local profile -> local posed point -> S -> B -> world
~~~

已经得到世界坐标的目标不能再当P坐标乘一遍安装变换；S也不能替换A不断积累下一帧目标。30的“造型参考”和“动态增量”继续分别拥有状态，动作结束回到编辑后的中性形状。

~~~text
PartFrameContract {
    partId, bodyGeneration, shapeRevision, mountRevision, localRigRevision
    referenceMount: {translation, properRotation, positiveScale}
    solvedMount: {translation, properRotation}
    actionFrameType
    mirrorProfileId, sideAssetId, mirrorApplicationStage
    localFeatureBindings[], jointMirrorPairs[]
}
LocalChannel {
    semanticId, coordinateFrame, mirrorRule
    neutralValue, dynamicValue, sourceAction
}
~~~

对称伙伴是稳定部件ID的对应关系；独立安装、非对称身体或断肢后不靠骨骼数组下标猜另一侧。mirrorRule必须由自有profile声明：本例Grip是[0,1]的归一化闭合量，保持同一数值；Twist是[-1,1]的有符号归一化量，改变符号，再由自己的profile换算角度。它们是不同参数域，不能把Twist的-.6放进Grip通道，也不把所有scalar都取负。原作某个deformID的具体含义尚未确认。

## 3 自研：反射与普通旋转不同

在身体空间用M=diag(-1,1,1)反射：

~~~text
point' = M * point
rotation' = M * rotation * M
mountTranslation' = M * mountTranslation
~~~

M的行列式为-1，不能直接塞进只接受旋转的四元数。R'的行列式仍为+1。采用右手、scalar-last四元数q=(x,y,z,w)时，该约定对应q'=(x,-y,-z,w)，最后归一化。把q全部取负只得到同一个旋转，达不到镜像。

世界反射要跟身体走：

~~~text
worldMirror(p) = bodyPosition
               + bodyRotation * M * transpose(bodyRotation)
                 * (p - bodyPosition)
~~~

不能无条件把世界X坐标取负：生物可以移动和转身，镜像平面是它自己的解剖平面。

方向向量按M变换；由叉积定义的角速度轴/弯曲平面法向是轴向量，按det(M)*M变换。镜像三角形的顶点还需反转绕序，才能让外向表面法线按M保持正确朝向。镜像后重新检查参考框架的正交性和右手性，尤其是膝肘pole、局部铰链和扭转轴；不会把左手框架直接当四元数。

本方案选择两种明确模式：

- CanonicalMirror：自有定义中的几何、参考骨架及需要镜像的动作坐标只转换一次，安装旋转用上述共轭关系。
- SideSpecific：使用已单独制作的左右资产和各自profile；不会再次反射已完成镜像的几何。安装与动作适配按该profile显式处理。

两种模式不能叠加。运行中保留mirrorApplicationStage，重复应用返回MirrorAlreadyApplied。非均匀造型缩放在29/30的几何与特征更新阶段处理；这里的旋转框架不能带缩放或剪切，标量位移适配也不能重复乘已经烘焙的形状尺度。

## 4 自研具体算法与错误分支

~~~text
BuildOwnMirroredDefinition(source, body, policy):
    require current body/shape/mount/localRig revisions
    require finite values; positive scales; valid jointMirrorPairs
    if policy == SideSpecific:
        require side asset and its declared profile
        return its own reference definition
    if source.mirrorApplicationStage already applied:
        return MirrorAlreadyApplied
    out.mount.translation = M * source.mount.translation
    out.mount.rotation = M * source.mount.rotation * M
    out.geometry = reflect own canonical geometry once; reverse winding
    out.referenceJoints = reflect positions and conjugate proper rotations
    out.mirrorPairs = stable-ID remap; verify bijection for paired joints
    out.profile = per-channel declared invariant/signed/geometric mapping
    validate rest lengths, proper frames, local feature/skin bindings
    return new immutable definition and changed revision

BuildOwnActionGoals(frameSnapshot, channels, target):
    require all revisions match the active body
    convert external world target through inverse B exactly once
    for channel:
        decode declared frame and semantic mirror rule
        if RestEffector:
            targetB = A.translation + A.rotation * adaptedLocalDisplacement
            record as body IK goal; do not apply solved S here
        if PartLocal:
            localPose = ownProfile(edited reference, semantic values)
            defer world placement until solved S is available
        if unknown rule/frame: return UnsupportedActionCoordinate
    return goals with frame provenance and stable effector IDs

PublishOwnPose(bundle, body):
    reject stale generation/revision, missing mount or non-finite values
    validate each proper rotation and length/contact/support residual
    publish one consistent body pose and local pose version
~~~

镜像策略可以由灵魂的动作风格选择，但肉体定义决定可用安装框架、铰链轴与碰撞特征。方向不合法或部件被删时，取消旧动作、释放该动作的预约并重选执行器；不能通过静默翻转坐标掩盖错误。

## 5 自研贯通数值例子

以下数值是构造输入，不是原作字段单位解释。身体根在世界(10,0,0)，根旋转Rz(90°)。右侧参考安装A.translation=(2,0,1)，A.rotation=Rz(90°)，本次尺度=1；自有动作的部件局部特征位移v=(0,1,0)。

1. 右侧身体空间结果：Rz(90°)v=(-1,0,0)，加安装位置得(1,0,1)。
2. 经身体根进入世界：(10,0,0)+Rz(90°)(1,0,1)=(10,1,1)。
3. 对应镜像安装位置变(-2,0,1)，旋转M Rz(90°) M=Rz(-90°)，局部位移Mv仍为(0,1,0)。身体结果(-1,0,1)，世界结果(10,-1,1)。
4. 该世界反射发生在生物的解剖平面；直接取世界X负值会错误地产生(-10,1,1)。
5. 如果这是全肢体RestEffector轨道，上述点成为IK目标；如果是固定安装下的内部特征，P→S→B产生该点。每条轨道选择一种路线，不重复应用局部位移。
6. 新编辑把安装版本3改到4时，版本3求出的结果拒绝发布；使用新A重建目标。撤销镜像不修改当前造型中性值，Grip=0.6仍为0.6；有符号Twist=0.6才按自有声明变-0.6。

Rz(90°)的scalar-last四元数为(0,0,√0.5,√0.5)，镜像后(0,0,-√0.5,√0.5)。两者旋转方向相反；这与给四元数四个分量都取负不同。

## 6 验证、未知与下一步

[独立算例检查](checks/verify_mirror_branch_examples.py)包含16项镜像/框架检查及一项39既有JSON左右字段检查；与42合计32项通过。涵盖矩阵与四元数的一致性、轴向量、三角形绕序、世界平面、完整安装算例、重复镜像、非正交/非有限输入、scalar策略和旧版本拒绝。它不验证 Spore 渲染或任意自有骨架。结果与文件摘要见[验证记录](evidence/mirror-branch-verification.json)。

原作仍未知：左右资产的具体镜像构造、原作轴/角单位、Euler顺序、安装与局部曲线的乘法顺序、各镜像枚举的完整消费者，以及参考弯曲/扭转的运行时选择。最有判别力的后续自有场景是同一部件安装在正向、侧向与倒置框架，身体旋转后同时检查末端位置、面朝向、pole和内部Grip。对原作则需匹配函数提供者及明确运行授权；本轮未扩大该范围。

未做：游戏启动/附加、私存档、原生函数恢复、完整资产导出、三维渲染与性能测试。风险：历史与社区解释没有逐项对齐本机；极端非均匀造型、特殊左右资产和局部轴退化仍需自有三维验证。不存在已确认的原作镜像矩阵公式。
