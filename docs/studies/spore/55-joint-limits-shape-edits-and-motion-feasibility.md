# 55 造型改变后的关节限位、弯曲偏好与动作可行域

[目录](README.md) · [参考姿态与IK](05-particle-ik-and-rest-pose.md) · [造型与局部动作](30-part-shape-rest-pose-and-local-animation.md) · [部件定义](37-part-definition-edit-controls-rigs-and-capabilities.md) · [共享骨段](42-branched-limbs-shared-joints-and-goal-conflicts.md) · [完整配方](50-complete-creature-recipe-runtime-bones-and-bindings.md)。只研究登陆后Creature和编辑器。

**编辑长度、粗细、参考弯法与运行关节限位应分别表示。** 本轮重新读取一只原作手模型的局部轨道与4行绑定姿态数据，但没有取得明确的原作swing/twist角限位配置，或编辑后修改运行可行域的消费者。下面的三维关节约束和两节臂演算是我们的独立规格；不能因字段叫MuscleScale就补出肌肉力学。

## 原作证据：造型与运行状态之间仍缺哪一段

复用05/30的开发者资料：玩家创建的姿态是参考数据；形状轨道生成新基础网格，运行局部动作可适配新的参考；公开粒子IK以参考形状偏好抑制折叠。这证明参考对动作有影响，**没有公布每种部件的硬角限位、粗细→限位公式或肌肉强度模型**。本轮未重新下载这些PDF。[动画论文§4.3](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)、[Rigblocks演讲§3，第20–24页](https://www.cs.cmu.edu/~ajw/s2007/0248-Rigblocks-slides.pdf)，来源身份分别复用05/30的记录。

固定社区源码提交：SDK`2d71289adc71aa5c58f4516c6c835c99f5f9ca19`，FX`a482c51d8d37fc8cf416acecc3c00a5b0723f2e5`。重新读取8份完整小文件并散列，语义检查限定以下行段，整文件再查`swing|twist|bend|joint.*limit|angle.*limit|constraint`，8份均无匹配；这项有限阴性不证明游戏没有角限位。

| 来源/行段 | 确认到的表示 | 未确认 |
| --- | --- | --- |
| EditorRigblock.h 359–367、389–405、472–486 | orientation、deform base/middle/end骨索引、MuscleScale、Min/MaxScale、连接尺度和handle数组 | 这些尺度不是运行摆角；未知字段不命名成肌肉或限位 |
| cCreatureDataResource.h 52–90 | scale、orientation、muscle数值和capability/morph起点 | SocketConnectorDistance注释仍疑似半径；没有硬限位消费者 |
| CreatureBlock.h 31–77 | orientation、scale及8个含未知值的deform槽 | 槽值与关节锥/扭转范围没有建立联系 |
| RWMorphHandle.java 31–37、44–60 | spatial start/end、defaultTime、动画引用 | 把手进度不是关节硬角度区间 |
| RWKeyframeAnim.java 77–127 / RWKeyframe.java 77–110 | 通道目录、32字节LocRot：4分量rotation、3分量location、float time | 曲线的最大/最小样本值不能当所有动作的关节限位 |
| RWAnimationSkin.java 35–38、49–70 / RWMatrix3x4.java 30–38、54–69、86–90 | 工具命名absBindPose/invPoseTranslation；48字节矩阵＋3float＋4padding | 空间、inverse-bind乘法和编辑后参考弯法映射未知 |

直接来源：[编辑部件](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/EditorRigblock.h#L389)、[编译部件](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/cCreatureDataResource.h#L66)、[CreatureBlock](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/CreatureBlock.h#L31)、[MorphHandle](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/rw4/RWMorphHandle.java#L31)、[KeyframeAnim](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/rw4/RWKeyframeAnim.java#L77)、[LocRot](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/rw4/RWKeyframe.java#L77)、[AnimationSkin](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/rw4/RWAnimationSkin.java#L49)、[矩阵](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/rw4/RWMatrix3x4.java#L86)。[完整身份与查询记录](evidence/joint-limits-shape-feasibility-observations.json)

固定`reg_property.txt`全表191259字节，SHA256`456ce6c6a8171bc7fae4c04afc8a1440f9834388909dfe7d280ea87334032abd`。限定model的joint/bone/limb/muscle/connector/scale/rotation/angle/limit/bend名称取得56个候选，保留10个相关精确标签；更窄的`joint.*limit|swing|twist|bend.*limit|angle.*limit`查询没有匹配。名字范围涵盖编辑手柄/吸附，也不自动属于运行约束。[固定登记表](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/reg_property.txt#L3917)

37的Patch手PROP原值本轮只复用：modelMinScale=0.5、modelMaxScale=2、modelScale≈1.3；modelRotation=[0,7,-4]与modelEditorInitialRotation=[0,-30,0]分开；modelRunTimeBoneCount=4。保留原类型/显式属性ID和来源摘要，**没有把这些数值换算成骨长、弯角、质量或强度**，也没有按未经恢复的继承规则合成有效配置。

## 本机新增：一只手的局部原值

本轮实际读取`Spore_Graphics.package`一个既定RW4：键`2f4e681b:40606000:0df11468`，包文件offset152564158，stored33479、decoded55388字节。实际读取头/完整DBPF索引并核验摘要，再读取/内存解压这一个资源，存储SHA256`ac94219c42fa426bd6dc710b0df4cf1eb04bc490b29a5fd5f930bda5f8647d14`，解压SHA256`9575d53175a28240c4ce591664fa66dee8eb962bf659ada1f00c8d1a5d28b9dc`，均与37一致。

Graphics完整摘要`e01bb86d8ddf02c56d52394b4e1db7181c1e1ebe1878bf6fb72c4ee523fcedd1`只复用37，**本轮没有重新散列整个大包**。EXE固定摘要`f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d`复用已有身份，未重新读或运行EXE，Game/Patch payload也未新读。调查起始时间2026-10-13 01:22:17 PDT；实际读取时间另存证据JSON。

21个section中没有类型`0x00ff0000`的MorphHandle section，这是单个模型的限定结果，不证明所有把手不存在。两个骨架头仍为1/10骨，两份局部KeyframeAnim仍各10通道；配置的4保持原义，不和资产骨数混合。本轮重新读取其前两条有邻接边界的LocRot通道，共10个32字节样本，未读取完整轨道或执行插值。

| section0 / channel1 `d0be09e9` | decoded offset | rotation四分量原值（约） | time原值 |
| --- | ---: | --- | ---: |
| 样本0 | 656 | [-0.699406,-0.680368,0.161970,-0.147298] | 0 |
| 样本1 | 688 | [-0.784494,-0.620136,≈0,≈0] | 0.625 |
| 样本2 | 720 | [-0.761302,-0.627715,-0.047783,0.155274] | 1.25 |

三者的范数近1。在**“这些Vector4是同一ordering四元数”假设**下，首末归一化绝对点积≈0.928925，`2acos(abs(dot))`诊断角跨度≈43.4642°。它不是解出的最大关节角、编辑参考弯法或特定手指张开角；time也未当秒使用。section1/channel1的两样本相同，诊断跨度近零。原字节与假设均保留。

新增局部读取AnimationSkin section6：头从decoded27808开始，pointer27824、count10，后续64字节stride；只读取ordinal0–3，另6行未读。ordinal1在27888，工具名`invPoseTranslation`的原3float为[0.0350445,-0.0188963,0.00839527]；矩阵第0行为[0.8349582,-0.5503134,≈0,0]。保存每行全部64原字节、矩阵raw和独立translation raw。**没有把这个矩阵自动倒置成编辑rest pose，也没有从它提取一条关节限角。** 链接section8把该AnimationSkin与section16骨架、section7矩阵缓冲关联，字段编号仍各属自己的空间。

因此，这轮阳性结果是“真实局部姿态与曲线可以按有界格式读取”；编辑造型参数→新参考→运行关节限位→技能可行域的原生连接仍未恢复。

## 自研：形状、参考偏好、硬可行域分别输出

以下表示、阈值、公式和行为为我们的独立设计。灵魂提出技能/目标，肉体与自有资产给出当前结构、几何和可用关节；灵魂不能用高优先级越过身体硬限位。

```text
ShapeEdit { stablePartId, lengthParameters, girthParameters, restJointEdits }
ReferenceRig { bodyRevision, stableBoneIds, referenceTransforms, lengths,
               preferredBendDirections, shapeGeometry, bindAndInverseBind }
JointProfile { limitFrame, axis, swingCone, signedTwistRange,
               hingeRange?, constraintMappingVersion, referencePreference }
MotionDomain { jointProfiles, contacts, neighboringGeometry, allowedDofs,
               referenceValidity, invalidReasons }
ActionFeasibility { bodyRevision, actionRevision, executorIds,
                    requiredPhaseReports, trajectoryStatus, rejectReasons }
```

编辑造型首先生成新的长度、中心线/半径、参考变换和绑定数据；运行限位从**自有资产明确的关节规格与映射规则**生成，不能从某动画已采样的角范围推断。粗细改变碰撞体并缩小无穿透可行域，不必改变硬关节角。若资产确有“变形参数→关节锥”的映射，必须保存该自有规则/版本和导出的范围，再重算动作资格；没有规则时维持声明的角限位，并检查它在新几何上的可用性。

参考弯法是软偏好与编辑真值，不能每帧被解算角度覆盖。编辑将参考弯角摆到硬限外，可以保留有限、合法的编辑草稿，明确标记`ReferenceOutsideHardLimits`并禁用依赖的可播放姿态；不偷偷改回玩家的造型，也不把硬限改大消除警告。是否允许这类草稿提交为可玩身体，是产品规则；本文自研默认要求可玩身体的参考姿态也通过硬约束。

比较最终角度时使用独立的anatomical limit frame，不能仅检查`q_action`：运行绝对姿态可能由`q_reference*q_action`形成，形变后的参考角并没有因此变成无限合法的零角。硬范围锚在资产关节语义坐标；编辑后安装/关节框架的映射须重编译。来自IK的绝对解也不能再乘一次参考弯法，沿用05/30的数据契约。

## 自研三维关节锥、扭转与镜像

自有示例用标量在前的单位四元数`q=(w,v)`，限制轴`a`为单位向量。这是自研约定，不把它强加到原作Vector4布局。先在关节限制框架里求`q`，再拆：

```text
t_raw = (w, a * dot(v,a))
if norm(t_raw) <= tolerance: TwistUndefinedAtHalfTurn
twist = normalize(t_raw)
swing = q * conjugate(twist)
swingAngle = 2*acos(clamp(abs(swing.w),0,1))
twistAngle = wrapToMinus180Plus180(2*atan2(dot(twist.xyz,a),twist.w))
valid = swingAngle <= coneMax && twistMin <= twistAngle <= twistMax
```

此处圆锥是真正的3D方向范围，不是把Euler三个角分别夹持。需要不对称椭圆锥的部件可另声明两条主轴/边界曲线，但本轮测试只覆盖圆锥。拒绝非法单位四元数、退化轴、反向范围；近180°且扭转投影退化时使用仍匹配当前版本的上一合法框架或返回显式不可解，不产生NaN/随机翻转。投影后的姿态需要重新检查目标残差，不能因夹角合法就声称已命中目标。

镜像`H=diag(1,-1,1)`时，位置和“朝肘部的偏好方向”是极向量，按Hv映射；平面法向`cross(u,v)`是轴向量，按`det(H)Hn`映射。自有旋转采用`R'=HRH`，保持det=+1；同一四元数约定下变为`(w,-x,y,-z)`。不要把负尺度直接塞进骨旋转。

扭转符号变换同时影响不对称范围：[-10°,40°]镜像成[-40°,10°]。只镜像网格而不镜像pole/轴/范围，会使左手错误反折。镜像身体与在同一身体上选择相反弯曲分支是不同操作：后者若得到signed elbow=-113°，不能拿unsigned113°绕过只允许正屈曲的关节规格。

## 自研两节臂：改长后反而不能收回

这个完整算例使用米/度，肩固定O=(0,0,0)，限制框架+X为直臂方向、bend pole为+Z。肘屈曲定义直臂0°、折叠趋近180°；上臂方向的肩swing锥≤80°，肘hard range为[10°,130°]，手部轴向扭转[-35°,35°]。所有数值均自选，不是Spore参数。

| 自有肉体版本 | 上/前臂长度 | 胶囊半径 | 参考肘偏好 | 运行硬角范围 |
| --- | --- | --- | --- | --- |
| rev8改造前 | 1.0 / 0.8 | 0.08 | 90° | 保持上述规格 |
| rev9改造后 | 1.6 / 0.8 | 0.28 | 110° | 保持上述规格 |

自有技能有前摇目标W=(0.8,0.6,0)、手扭转15°；发力姿态目标W=(1.4,0.2,0)、手扭转30°。“发力”这里只指动作阶段，**没有计算真实肌肉力、扭矩或伤害**。另一个身体部位用球C=(1.4,0.55,0)、r=0.12表示；它不属于被允许相接的肩肘安装邻接区域。

两骨几何求解：`d=|W|`，先验证`|L1-L2|≤d≤L1+L2`，令u=W/d，v为pole在u垂直平面的归一化投影，

```text
a = (L1²+d²-L2²)/(2d)
b = sqrt(max(0,L1²-a²))
E = a*u + b*v
elbowFlex = acos((d²-L1²-L2²)/(2L1L2))  // 本例合法正屈曲分支
shoulderSwing = acos(dot(normalize(E),Xaxis))
```

完整3D有符号屈曲还按参考hinge normal与`cross(E,W-E)`的方向检查，脚本没有把反折分支取绝对值。pole投影退化时返回`BendPlaneUndefined`；骨长、有限数和误差另验证。

| 版本/阶段 | 肘点E（约） | 肘屈曲 / 肩swing | 结果 |
| --- | --- | --- | --- |
| rev8前摇 | (0.544,0.408,0.733212) | 113.578° / 57.044° | 样本姿态角度与接触合法；偏好误差+23.578° |
| rev8发力 | (0.826,0.118,0.551181) | 76.997° / 34.310° | 样本合法；偏好误差-13.003° |
| rev9前摇 | (1.168,0.876,0.654523) | 149.246° / 43.114° | 长度几何可解，但肘超130°；`ElbowFlexExceeded` |
| rev9发力 | (1.372,0.196,0.799500) | 117.953° / 30.963° | 角度合法，但相邻身体穿透；`NeighborPenetration` |

前摇两版本d都为1米。只看骨长区间，rev9仍可达到；但有肘最大角时最近距离为`d_min=sqrt(L1²+L2²+2L1L2*cos130°)`，rev8≈0.782010、rev9≈1.246781。**拉长上臂增大最远范围，也使固定肩位置下的近身动作失效。** 不允许为到达目标直接把L1临时拉回1或把肘限提高至150；可以由自有动作目录另选站位/身体移动/替代动画，并重新预检。

发力阶段两版本的前臂胶囊到C最近轴距都是0.35米（最近点为W）。净间距`distance - armRadius - otherRadius`从`0.35-0.08-0.12=+0.15`变成`0.35-0.28-0.12=-0.05`米。加粗没有改变这里的角度合法性，却引入身体穿透。移走邻部位可以修复发力样本的接触，不能修复前摇149.246°的角超限。

两版本的编辑参数都合法，参考90°/110°也都在硬限内；rev9技能两个阶段仍各有不同失败原因。形状验证、参考合法、端点长度可达、完整姿态约束和技能执行资格不能合并成一个布尔值。

## 自研核心流程与连续路径边界

```text
OnOwnCommittedShapeEdit(edit, oldBody):
    validate edit parameters and stable part IDs; retain invalid-stage diagnostics
    build new immutable shape/reference: lengths, radii, transforms, bind data
    compile declared joint limit frames/profiles for this bodyRevision
    derive bend preference from reference, keeping it separate from hard limits
    rebuild contact volumes and explicit allowed-join exclusions
    validate reference pose against hard joints and contacts
    invalidate old action/IK/mesh/collision consumers by revision
    publish one consistent bundle or keep editor draft with nonplayable reasons

PreflightOwnSkill(body, executor, authoredPhaseGoals):
    require current stable executor/asset/role and body/control revisions
    for each mandatory phase:
        solve selected branch with reference pole and exact current lengths
        measure bone errors, swing/twist/hinge range and goal residual
        check current-body collision volumes, excluding only authored join zones
        retain separate geometry/angle/contact/target failure reports
    if any mandatory phase invalid: reject before scheduling gameplay effects
    verify intermediate trajectory with collision and joint-limit bounds
    require trajectory result Valid before granting full execution certificate
    reserve DOFs and effects under this same version, then start action
```

两个合法关键姿态仍不能证明中间运动合法；所有样本报告都保留`swept_path_validated=false`。本轮没有把两阶段离散测试升格为连续扫掠保证。生产轨迹验证应按自有角速率/位移界给区间界、保守扫掠或受控自适应细分，接触或限位界无法证明时返回`TrajectoryUnverified`，而非默认成功。

形状/身体改变后，旧计划还可能引用消失或重排的骨骼；按50稳定BoneId重绑、44完整版本发布、40旧事件回调失效。共享肩/分叉骨段由42联合求解，不能为两个末端各修改同一肩的长度或角度。技能等级保留但可执行性可以变化，灵魂AI应使用新可行域报告选择行为，不因技能图标还在就沿用旧出手距离。

## 验证、未做与风险

[本机读取器](checks/read_joint_shape_feasibility_metadata.py)重新读取单个55388字节模型元数据、4行skin pose与10个LocRot样本；不修改旧reader。14行原字节/偏移与解析字段一致性检查通过。[独立检查](checks/verify_joint_shape_feasibility_examples.py)实际 **39项测试，0失败、0错误**，覆盖3D摆锥/扭转、组合/四元数符号、镜像及不对称范围、180°奇异、非法参数、两阶段改造差异、反折、几何可达与接触、参考偏好分离、骨长误差、有限pose读取/越界/预算等。[研究检查记录](evidence/joint-shape-feasibility-verification.json)

**未做：** 未启动或附加游戏、读私人存档、导出完整动画/模型资产；未恢复编辑造型到原生运行限位/IK/技能可行域的消费者；没有获得真实限角或肌肉配置。REA提供者缺口沿用，不重复setup或安装。

**风险：** 原作资源中的局部姿态仍不能归因于编辑把手或某关节的参考弯法；角跨度与绑定矩阵都不是硬限位证据。自有检查使用圆锥、两骨解析解、球/胶囊及离散姿态，未验证任意分叉3D IK、完整轨迹、物理力学或产品资产。下一步需明确格式/原生消费者来补原作链；独立产品则先实现同版本约束/碰撞/动作资格接口与连续路径验证。
