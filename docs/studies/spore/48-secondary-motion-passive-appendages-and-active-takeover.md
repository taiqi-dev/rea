# 48 尾巴、耳朵与装饰：被动运动和主动接管

[目录](README.md) · [参考姿态与IK](05-particle-ik-and-rest-pose.md) · [部件局部动画](30-part-shape-rest-pose-and-local-animation.md) · [体积/接触](32-body-volume-contacts-and-self-collision.md) · [共享关节](42-branched-limbs-shared-joints-and-goal-conflicts.md) · [受击中断](47-hit-reactions-action-interruption-and-ai-recovery.md)。

限定陆地Creature。身体运动后耳朵/尾巴跟着摆动，和动作主动甩尾、抬耳或控制装饰，是不同的控制来源。原作历史设计明确说明动态被动子树及无反馈，但本机弹性参数与接管细节未恢复。第1节是证据；后续动力学、过渡和命中政策均为自研。

## 1 原作：根据当前目标决定被动，不按部件名称硬分

开发团队论文§4.3.1用本体或后代是否有姿态目标决定“has IK”；§4.4将没有IK的子树交给高阻尼Jiggles，并要求被动运动不反馈主动身体。早期Wiggles会给IK设目标、影响作者动作，因此两者不能混为最终方案。论文§5还明确当时忽略体内碰撞。[动画论文第7、9、10页](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

这能解释同一尾巴为何有时跟随、有时主动做动作；没有公布频率、质量、阻尼、接管/归还、碰撞或命中算法。本轮重新读取这三个完整页；历史说明不等于本机1.3.0.29函数跟踪。

| 社区/本机入口 | 可以说什么 | 不能说什么 |
| --- | --- | --- |
| SDK cCreatureDataResource Flags | kFlagIsJiggable=0x200、kFlagExtraJiggly=0x800；RigblockData有父/对称索引与flags | 旗标怎样产生、Extra如何改弹性、哪些部件实际启用 |
| FX固定登记表 | modelJigglable=B6F17B6C、modelExtraJiggly=A64E0669 | 属性到编译flags的直接映射与默认值 |
| 39已读46份ANIM | 每份有ear/eye主查询模式，flags=0 | 查询一定形成有效姿态目标，或耳朵/眼睛一直被主动控制 |
| 已读EditorRigblock | Jiggl/Wiggl/Flexib/Rigid字面检索无命中 | 编辑器或原作没有相关功能 |

Context查询、启用组件、有效目标以及最终控制归属仍要分别核对。只出现ear查询并不能决定其当帧是否归Jiggles。动态部件形变还可能只改变内部骨架，不需要移动外部身体安装点；30与42的两种层级不合并。[SDK编译数据声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/cCreatureDataResource.h)、[既有查询原值](evidence/local-same-role-selector-observations.json)、[本轮来源与边界](evidence/public-reaction-secondary-contracts.json)

没有按tail/pain/ear名字导出任何新资产，也没有把局部手骨架的raw flags当作上述Jiggable旗标。原作是否让装饰参与伤害或实体碰撞仍未知，不能从“被动摆动”推出“完全无玩法作用”。

## 2 自研：状态属于肉体，控制租约属于动作

以下全部是独立规格。肉体拥有被动运动状态、编辑后的中性框架及代理；灵魂/动作可以取得输出租约，不把弹性状态塞在某次技能实例里。

~~~text
AppendageDefinition {
    stablePartId, stableJointIds, parentBoundaryId
    editedReferenceFrames, localRigRevision, hingeAxes
    permittedModes, angularLimits, dynamicProfile
    collisionClass: Cosmetic | QueryHitShape | CoupledPhysical
}
SecondaryState {
    bodyId, bodyGeneration, topologyRevision, mountRevision, localRigRevision
    jointStates: relativeAngle/velocity or own 3D equivalent
    referenceFrame, parentPoseRevision, ownerEpoch, lastSimulationTick
    mode: Passive | AcquireBlend | Active | ReturnToPassive
    diagnostics
}
ActiveLease {
    actionToken, requiredCohort, exactJointOutputs
    body/control versions, ownerEpoch
    desiredPoseTrajectory, releasePolicy
}
SecondaryJob {
    body/version/output set, capturedOwnerEpoch
    prescribedParentPose, candidateState, candidateProxies
}
~~~

子树判定用当前有效姿态请求及实际输出租约。自己规定：纯声音、VFX或不改身体姿态的scalar不会因名字相同而自动把整条尾链标为IK；但某个内部骨骼被局部动画占用时，被动层也不能写同一个自由度。

~~~text
PartitionOwnMotion(body, effectiveGoals, outputLeases):
    validate graph, stable mappings and all versions
    active = root + ancestors of required body-pose outputs
    exclude every output already owned by active internal profiles
    passiveCandidates = maximal remaining permitted subtrees
    each passive subtree gets a prescribed parent boundary
    return one owner per output plus declared transitions
~~~

主动孩子需要共同祖先时，祖先属于主动求解；未参与的兄弟子树可在这个已求出的边界下被动运动。BodyGraph与部件内部骨架采用明确映射。固定脊柱/肩框架不被每个耳朵或尾巴分区分别重写。

## 3 自研：一个可核算的高阻尼角度模型

用单铰链角度q示范，不声称是原作弹簧。q为相对编辑后中性姿态的角偏差，单位rad；v为rad/s。定义：

~~~text
q'' + 2*omega*q' + omega²*q = a
~~~

omega单位s⁻¹，a单位rad/s²，为该步内固定的自有驱动输入，例如映射后的父框架加速度。它不是原作modelExtraJiggly的已知公式，也不是实际质量/冲量模拟。

在一步h内a不变时，临界阻尼可精确推进：

~~~text
qEq = a / omega²
y = q - qEq
b = v + omega*y
e = exp(-omega*h)
qNext = qEq + (y + b*h)*e
vNext = (v - omega*b*h)*e
~~~

必须验证omega>0、h>0、全部有限。父运动/驱动在步内变化时分子步更新输入；恒定输入的闭式解不保证任意大步跨碰撞或接管仍有效。下述数值例使用omega=10 s⁻¹、角范围[-.5,.5]rad、速度预算4rad/s，均为自研构造参数。

积分后检查角度、代理和有限值。越上限时夹到上限，仅清除朝外的正速度；朝内负速度保留。这个局部限位政策不等于三维碰撞解算，更不直接把尾巴顶点推开后下一帧又拉回。

## 4 自研：主动接管与归还要保持连续

被动姿态不能与主动动作各写一遍再相加。接管时先封存当前q/v，推进ownerEpoch，旧被动任务立即失效；主动过渡取得该输出的唯一写权限。

使用时长T的三次Hermite连接当前(q0,v0)与目标(q1,v1)：

~~~text
s=t/T
q(s)=(2s³-3s²+1)q0
    +(s³-2s²+s)T*v0
    +(-2s³+3s²)q1
    +(s³-s²)T*v1
v(s)=dq/ds / T
~~~

它保持入口/出口位置和速度；不能用入口速度强制0的普通权重淡入替代。检查角度/速度极值：对q(s)=As³+Bs²+Cs+D，内部角度极值来自3As²+2Bs+C=0，速度极值来自6As+2B=0，加上端点一起核对。过渡无法满足限位、支撑或接触时延长/重选目标或返回TransitionConstraintFailed，不直接输出非法曲线。

主动期间被动积分器不拥有该输出。归还时以**当下已求出的姿态和速度**种入Passive，不恢复源资产的默认角，也不把q强制清零：

~~~text
AcquireOwnAppendage(lease):
    require current body/control/rig and available exact output set
    capture current solved q/v in the declared parent/reference frame
    ownerEpoch += 1; invalidate old passive candidates
    construct/check own continuity trajectory
    if failed: retain previous owner/state and report failure
    enter AcquireBlend, then Active

ReleaseOwnAppendage(lease, currentPose):
    verify exact current lease and revisions
    capture actual q/v, transform into current passive parent/reference frame
    ownerEpoch += 1; release active output
    seed Passive from captured values
    preserve diagnostics and body-owned state

PublishOwnSecondary(job):
    reject mismatched body/rig/parent revision or ownerEpoch
    require every destination remains Passive and has one owner
    validate local pose/proxies; apply atomically
    never write the prescribed parent boundary or active ancestor
~~~

接管/构造检查需作为一次状态事务，失败不能先丢掉旧拥有者。异步任务不能只凭“这个部件还叫tail”发布。47硬直取消主动尾动作后，也从最新反应姿态归还，旧攻击结果没有写回权限。

平面例中，世界角=parentAngle+referenceAngle+q。父框架改变时，qNew=worldAngle−parentNew−referenceNew；相对速度同理用worldAngularVelocity减父/参考速度。这样避免只换父框架而让尾巴跳动。三维版本应按41的正确旋转/角速度框架变换，不直接搬旧三个Euler值。身体拓扑、骨长或限位改变后再验证新约束；必要时显式重置/投影并记录FrameOrShapeChanged。

## 5 自研：碰撞和命中由声明决定

帧顺序选择：主动身体/局部姿态→被动子树→对应代理→发布一致姿态。模型尺度、父安装、reference与动态偏差各用一次，不重复烘焙30的玩家造型。

| 自有模式 | 被动运动与玩法关系 |
| --- | --- |
| Cosmetic | 可低频显示/限制局部穿插；不生成命中或反推父身体 |
| QueryHitShape | 角度在固定模拟tick求出，命中代理使用同版本权威姿态；显示LOD不能改变命中 |
| CoupledPhysical | 若需要碰撞冲量反推父身体，交给明确物理拥有者并协调主动目标；不再冒称无反馈Jiggles |

QueryHitShape表示可被查询击中，不自动等于会阻挡世界并产生实体冲量。真正硬障碍/反作用力需求选择CoupledPhysical或主动约束方案。不能一边称“只作无反馈装饰”，一边让其偷偷移动脚/根。

纯被动撞到边界时，可改自身可动关节或限制局部轨迹，不能推走主动祖先。找不到合法被动姿态时保留明确残差与代理状态；对纯显示允许显式降级，对权威命中部件则按声明失败政策处理，不悄悄使用上一个不匹配父姿态的碰撞体。

主动甩尾攻击的效果槽、窗口、目标去重仍由40/47管理。被动尾巴扫过敌人不会自动变成一次攻击；自有被动接触伤害需要另有明确技能、固定采样和账本。命中装饰是否伤及肉体由定义决定，不根据画面摆幅猜。

## 6 自研完整数值例子

同一尾铰链，编辑中性姿态保持不变；初始q=.2rad、v=0。父框架在这一步恒定、a=0，omega=10。

1. Passive推进.1s：e=exp(-1)，q=(.2+2·.1)e≈.147151776rad；v=(0−10·2·.1)e≈−.735758882rad/s。父身体没有被更新。
2. t=.1s动作取得尾输出，目标q=.4、v=0，T=.2s。入口保持上一步q/v，旧Passive job因ownerEpoch改变拒绝发布。
3. 过渡中点t=.2s、s=.5：Hermite得到q≈.255181916rad、v≈2.080301rad/s；端点t=.3s为q=.4、v=0。极值检查按自己的[-.5,.5]和4rad/s预算执行。
4. 主动保持到t=.5s，结束时用真实(.4,0)归还Passive；不会瞬间跳到0。
5. 再推进.1s得到q≈.294303553、v≈−1.471517765。Grip、嘴形或参考尾长没有被这一过程回写。
6. 若另一步候选q=.7、v=+2，局部上限裁到.5并把朝外速度清0；若v=−2则保留朝内速度。这只是该铰链限位演算。
7. 尾如果是QueryHitShape，固定模拟姿态q用于代理；相机LOD画成直尾也不能把判定体角度换成0。Cosmetic模式不参与攻击判定。
8. 本体换魂时，身体未变可保留被动机械状态，旧主动租约失效；换肉体/骨架时旧revision结果拒绝。是否迁移状态由稳定映射和新框架验证决定，不能原样沿用数字骨索引。

例子验证一个标量铰链的推进、接管与归还；没有完整多节尾/耳形、移动父框架输入、三维碰撞或实际Spore生物轨迹。它不是把论文源码转换为生产实现。

## 7 验证、未知与风险

[检查脚本](checks/verify_reaction_secondary_examples.py)30项通过：本篇14项、47有14项，2项核对旧JSON。本篇覆盖闭式阻尼数值与恒定输入子步一致性、祖先/兄弟划分、唯一输出拥有者、Hermite入口/中点/出口、归还连续性、父框架重映射、限位方向、旧owner/body任务拒绝、非法参数、显示与判定分离和无父反馈。[验证记录](evidence/reaction-secondary-verification.json)

原作未知：模型flag的生产/消费、弹性/柔韧性启发式与单位、不同部件参数、接管/归还的实际插值、局部deform是否参与hasIK、碰撞与伤害代理。最小自有场景是一条两节尾和双耳，固定模拟时钟下测试身体急转、尾主动攻击、受击中断、LOD切换和编辑尾长，记录边界不反馈、速度连续性、残差与旧结果拒绝。

未做：游戏运行/附加、私人配方、新包载荷、完整资产导出、生产物理或3D蒙皮、性能与高阶尾链测试。风险：高阻尼单铰链例子不保证任意三维链稳定；接管与碰撞可能要求重新规划过渡；历史设计不能证明本机对每种尾/耳都采用相同方案。
