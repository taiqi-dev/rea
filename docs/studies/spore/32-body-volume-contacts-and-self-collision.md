# 32 身体体积、局部接触与体内碰撞

[目录](README.md) · [并行动作](28-parallel-actions-channel-ownership-and-conflicts.md) · [网格与绑定](29-creature-mesh-joins-and-automatic-skinning.md) · [部件局部动作](30-part-shape-rest-pose-and-local-animation.md)。只研究登陆后、部落前的生物及编辑器，不扩展到其他玩法阶段。

本模块回答胖身体挡住手、长嘴穿胸、握合怎样碰到表面，以及多个动作共用身体时怎样协调。**原作公开资料直接承认这一类问题的限制；下面的体积约束与接触算法是针对拼装游戏的独立设计。** 它不是原作已恢复的自碰撞实现。

## 原作证据与未知

开发者动画论文§5明确说明，当时的动作系统不理解体积与边界，不能有效表达拥抱、摸下巴；并忽略体内碰撞。§3.2.2支持身体部位/外部目标的相对运动，举过双方手互为目标的例子。**能对准身体节点，不保证接触网格表面，也不保证过程避开自身。** [Hecker等，动画论文第4、10页](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

这是2008年开发者说明，不能由此证明本机1.3.0.29全部代码都没有相关补偿。反过来，论文§1.2说身体节点具有包围盒，也不能推导包围盒参与了体内碰撞求解。固定提交的社区`Anim/CreatureBlock.h`第47–65行有bbox与父节点声明，仍没有恢复求解调用。公开论文完整第2、4、10页与社区头文件的摘要、读取位置见[证据记录](evidence/contact-volume-design-observations.json)。

| 原问题 | 当前答案 | 缺口 |
| --- | --- | --- |
| 目标能否随不同身体结构适配 | 公开设计支持目标相对运动 | 具体陆地技能的通道、对象与目标选择 |
| 是否自动让长嘴/手绕过身体 | 当时公开设计明确忽略体内碰撞 | 本机修补、个别资产补偿、运行现象 |
| 握手能否对齐两只手 | 公开设计给出双向外部目标的表达方式 | 表面接触、双方同步、失败处理 |
| 张嘴/握合能否感知局部体积 | 论文把局部deform作为不透明参数 | 牙齿/手指与物体的局部接触链 |

没有运行游戏、附加进程或检查私人生物配方；本轮没有新的本机碰撞字段/函数证据。只复用已固定目标身份，不把社区字段偏移当成本机函数位置。历史设计不能替代发行版运行验证。

## 自研：三种几何与三种意图

以下结构、公式、阈值、求解与失败政策全部由我们自行定义。

29的参考模型包增加`ContactGeometry`，与参考骨架、部件内部绑定和肉体版本一起发布。可见网格、移动包围体、局部接触体不是同一种数据：胖身体的通行轮廓由26及后续命中模块管理；本模块专管动作路径和接触，不直接修改移动速度或技能伤害。

```text
ContactGeometry {
    bodyRevision, shapeDigest, localRigRevision
    proxies: Capsule|Sphere|OwnSurfacePatch[]
    stableBoneIds, partFeatureBindings, authorizedJoinRegions[]
}
Capsule { proxyId, endpointBindings[2], radius, sourcePartId }
Feature { partId, featureId, localFrame, surfaceRegion, contactProfile }
ContactPermit {
    actionToken, exactFeaturePair, phase, bodyRevisions,
    maxPenetration, normalCone, expiresWhenPhaseEnds
}
ContactGoal {
    actionToken, executorPartId, targetFeature,
    desiredGap, desiredNormal, tangentialTolerance, priority
}
ContactResult {
    status: ContactReady|ContactTargetUnreachable|ConstraintConflict|StaleContactGeometry
    targetResidual, penetrationResidual, boneLengthResidual,
    involvedPartIds, blockingPair, solvedBodyRevision
}
```

三种意图应分开：`Avoid`不允许穿入；`Touch`接近表面并保持法线关系；`Grasp/Bite`授权指定局部区域接触，仍不允许前臂、头部穿过躯干。骨骼节点没有表面积，不能把“手到嘴节点”当成“食物到口腔内的指定区域”。

身体变宽重新生成半径、安装框架与接触特征；30的张嘴/握合改变局部姿态，更新对应代理。只改渲染网格会令避让仍使用旧身体。胶囊半径从造型后的横截面/自有资产范围取得，不从某根骨骼的长度猜厚度。尖角、手掌、牙齿可用多个代理或自己的细表面；简单胶囊对凹腔会保守阻挡，需要明确局部模型。

## 自研算法一：胶囊候选与距离

骨段胶囊用于便宜的第一层检测。每帧用当前身体姿态与局部deform更新端点，再按端点范围加半径形成AABB。用空间网格/BVH得到相交候选，不能每个帧阶段各建一套不一致的端点。小型生物可以先遍历有限代理对；实际数量大时再依据测量换空间索引。

两骨段轴为`a+s(b-a)`、`c+t(d-c)`，s、t都在0–1；找使距离平方最小的参数。令u=b-a、v=d-c、w=a-c：

```text
A=dot(u,u); B=dot(u,v); C=dot(v,v)
D=dot(u,w); E=dot(v,w)
det=A*C-B*B
s=(B*E-C*D)/det; t=(A*E-B*D)/det   // 只在非退化、内部候选合法时使用
```

另外必须比较四条参数边界各自的最小值，处理平行线、零长段和端点夹持。不能独立把无限直线的s、t截断一次，就认为得到正确的两线段最近点。选最小候选得到轴上见证点p、q：

```text
gap = |p-q| - radiusA - radiusB - ownSafetyMargin
penetration = max(0, -gap)
normal = normalize(p-q)             // 从B指向A
```

完全重合时法线未定义：优先用该代理对上一帧稳定分离方向；没有历史则使用合法参考方向并记录退化诊断。不要除以0或随机抖动。所有端点、半径、矩阵先查有限值；负半径、失效骨骼ID返回具名失败。

胶囊是代理几何，**通过它的检查不证明可见网格绝不穿插**。包住整个网格的保守代理会产生假阻挡；贴近骨架的近似代理可能漏掉大甲片。重要局部接触先查自有细表面/多个代理，记录采用哪一层判断。

## 自研算法二：过滤相邻接合与授权接触

“不检测相邻骨段”会让上臂与前臂深度折叠时互相穿过。我们选择更窄的规则：只有两见证点都落在声明的共同接合区域，才排除正常接合重叠；出了接合区域，相邻骨段也参与约束。具有真实连续皮肤的根部、多个代理表示同一组织的情况都通过明确区域处理。

```text
ClassifyOwnPair(pair, witness, frame):
    if RepresentsSameDeclaredMaterialRegion(pair): return OwnRepresentationDuplicate
    if BothWitnessesInsideAuthorizedJoin(witness, pair): return JoinOverlap
    permit = FindExactActiveFeaturePairPermit(pair, frame.actionTokens)
    if PermitVersionsAndPhaseMatch(permit, frame)
       and InsideAllowedContactRegion(witness, permit)
       and PenetrationWithinLimit(witness, permit)
       and NormalWithinCone(witness, permit):
        return AuthorizedContact
    return NeedsSeparation
```

不能因为双方都有`mouth`标签就排除全部嘴碰撞；不能因某只手正在握物而允许整条手臂穿身。`jaw.innerSurface↔own upperMouth.innerSurface`可在闭合相位授权；牙齿与前胸仍需避让。食物进入口腔需要自己的入口、空腔模型与动作相位，不把实体嘴外壳全局禁用。授权深度是明确的小容差；超出容差重新产生阻挡，不属于“已经授权所以忽略”。

灵魂可以选不同的技能风格和接近方向，不能提高穿透容差来绕开身体。阶段结束、动作取消、断肢、目标改变或版本改变立刻失效接触许可。

## 自研算法三：接触目标来自表面

例如拿一个球形物体：中心c、半径R，从手掌接近位置h求外向法线n=(h-c)/|h-c|。物体表面点q=c+Rn；若手掌近似球半径r，手掌中心目标是`q+r*n`，而不是c。目标法线决定手掌朝向，Grip控制内部手指动作，二者结合30但不互相替代。

```text
BuildOwnContactGoal(executor, target, approach):
    RequireCurrentFeatureAndBodyVersions(executor, target)
    hit = QueryOwnTargetSurface(target.featureRegion, approach)
    if no valid hit: return TargetSurfaceUnavailable
    desiredContact = hit.position + desiredGap * hit.normal
    desiredEffector = OffsetUsingExecutorContactProfile(desiredContact, hit.normal)
    if ExceedsChainLengthUpperBound(desiredEffector): return ContactTargetUnreachable
    return ContactGoal(desiredEffector, hit.normal, exactFeaturePair)
```

目标表面可以从自有碰撞形状/特征patch得到，网格接近点须保留三角形与重心坐标、目标版本。最近点到中心退化时应由指定接近方向消歧。链长上界只能快速拒绝明显够不到的目标；通过上界不表示满足关节限位、避障和支撑约束。遮挡后应尝试少量明确接近候选，比如左侧、右侧、上方；候选都失败则反馈给灵魂AI换肢体、换技能或重新站位。

握手时不能每帧双方都追逐另一只正在移动的手，形成振荡。我们的接触事务从双方当前表面选一个共同目标框架，双方各提交对应末端目标与版本；未承诺之前任一方可拒绝。接触保持阶段更新目标框架，超出误差则解除。该同步政策是自研，不是原作target-relative声明的推论。

## 自研算法四：接触与骨长、支撑一起求解

不能在最终蒙皮后把穿入的顶点单独推出来，再下一帧又由骨骼拉回；不能推走脚而忽略锁脚和稳定性。给28的联合身体求解增加接触约束，所有共用脊柱/肩/髋的目标进入同一个状态向量。选择关节角变量或05的节点位置变量后保持一种拥有者；局部手指变量也通过明确映射加入。

节点位置形式的分离约束是`C(x)=gap(x)>=0`。以当前见证点的段参数s、t建立四端点梯度，暂时冻结参数作一次线性投影：A段端点梯度为(1-s)n、s*n，B段为-(1-t)n、-t*n。设每节点可动权重wi，wi=0表示本轮锁定：

```text
denominator = sum_i(w_i * |gradient_i|²)
delta_x_i = w_i * gradient_i * (-C) / denominator   // 仅C<0、分母合法时
```

这是**我们自己的几何约束投影规格**，不是完整物理碰撞/冲量解算。每次修正后重算见证点与实际代理，骨长、限位和支撑投影可能再次产生碰撞，必须反复核对全部残差。共享端点先合并同一节点梯度，不能按两个数组槽重复推动一个肩膀。

```text
SolveOwnVolumeAwarePose(reference, authoredGoals, contacts, support):
    RequireOneConsistentBodyAndLocalRigRevision()
    x = StartFromCurrentValidPose(reference)
    for iteration in boundedBudget:
        ApplyGoalsWithinOwnedJointVariables(x, authoredGoals)
        ProjectBoneLengthsAndJointLimits(x, reference)
        ProjectGroundSupportAndCurrentFootLocks(x, support)
        proxies = EvaluateCurrentBodyAndLocalContactProxies(x)
        pairs = BroadPhaseAndRefreshWitnesses(proxies)
        for pair in StablePairOrder(pairs):
            if ClassifyOwnPair(pair, witness, frame) == NeedsSeparation:
                ProjectSeparationIntoSharedJointState(x, pair)
        ProjectDeclaredSurfaceContactGoals(x, contacts)
        residual = MeasureAllGoalsLengthsLimitsContactsAndSupport(x)
        if AllRequiredResidualsWithinTolerance(residual): return ContactReady(x)
    return BestAdmissiblePoseAndExplicitFailure(residual, blockingPair)
```

关键失败分支：全部有关节点锁定则`NoMovableContactDOF`；目标位于躯干内部且没有合法空腔则`TargetInsideForbiddenVolume`；迭代预算用尽保留最大穿透、目标误差与阻挡对。把碰撞、支撑和骨长视为需满足的有效性约束，目标姿态可让步；无法得到有效姿态则保留之前有效姿态并拒绝动作，不把一个穿透更小但仍非法的结果提交为成功。

不能仅凭一次投影达到无碰撞就发布`ContactReady`。攻击的伤害确认仍按独立命中规则执行，不由接触求解成功直接触发；社会握手和拿物则必须满足自己的承诺条件。多个技能同时到不同手时，如果共享肩/躯干移动才能满足两个目标，联合求解失败会反馈28的协调器取消/改选其中一个动作。

## 自研完整算例：变胖、拿果实与长嘴

同一只六足生物先走到果实附近，脚的支撑目标由31负责。下面只演算上半身局部体积，不声称已仿真六足身体的完整稳定解。

**1. 原体能通过。** 躯干用球形截面代理，中心(0,0,0) m、半径0.4 m；手臂轴从(-0.3,0.6,0)到(0.3,0.6,0)，半径0.08 m，安全间隙0.02 m。轴最近距离0.6，gap=0.6−0.4−0.08−0.02=0.10 m。

**2. 身体加宽后旧动作无效。** 半径变0.7 m时，gap=-0.20 m。29更新网格/绑定，30保留参考造型，新接触体同步发布；旧手臂路径不能继续当成可行路径。若简化成自由移动轴，该截面需要至少移到y=0.8 m；实际骨链则重新求解肩、肘、手，并检查骨长和脚支撑，不可直接平移蒙皮顶点。

**3. 到果实表面，不到中心。** 果实中心(1.2,0,0) m、半径0.2 m，手从左边接近，接触面在(1.0,0,0)。手掌半径0.05 m，中心目标为(0.95,0,0)，也在加宽躯干的0.7+0.05+0.02=0.77 m排除范围之外。先沿躯干外部路径接近，再允许指定手指/果实表面的小容差接触；假如这只手够不到，灵魂得到`ContactTargetUnreachable`及执行手ID，换另一只手或重新站位。

**4. Grip只闭合手内部。** 外部接触目标固定后，Grip逐渐增加；每次手指局部姿态更新其代理。授权容差示例0.003 m只适用于指定指尖/果实表面、Grasp相位和版本4。换体为版本5或深度0.01 m均不授权，不能继续完成旧拿物事务。

**5. 拉长嘴后吞食也需重查。** 为独立数值例，躯干代理半径0.52 m，嘴轴根(.65,.5,0)，朝左。短嘴端(.5,.5,0)，轴到躯干中心距离约0.707107 m；嘴半径0.08与间隙0.02给出正gap约0.087107 m。拉长到端(-.25,.5,0)，轴最近距离0.5，gap=-0.12 m。长嘴穿过胸前的路线被拒绝。先调整头朝向、让另一只手送到新的口前，仍无解就取消吞食动作；不缩短玩家嘴形，也不让Open回写造型参数。

这个例子只证明粗几何、接触目标和状态分支的演算。三个代理场景用同一系统关系串联，数值对应各步骤明确设定的代理；不是同一真实Spore生物的连续测量。

## 失效与反馈

| 事件 | 自研处理 |
| --- | --- |
| 变胖、加粗手臂、拉长嘴 | 重建相关代理与接触特征；重新评估旧路径/目标 |
| 只改参考弯法 | 更新代理端点与关节参考约束；原参考许可不自动迁移 |
| Open/Grip变化 | 当帧更新内部代理与见证点；不重跑编辑造型 |
| 断肢 | 删除该部件的代理/许可/事务；动作失败反馈能力系统 |
| 换肉体 | 全部旧身体版本请求失效；灵魂评估新可用执行器 |
| 求解失败 | 返回阻挡部件、残差、阶段和目标；AI可重选方向/肢体/技能 |
| 动作结束 | 释放精确许可；逐帧从当前参考与新动态请求求值 |

灵魂评分可以把预测避障成本、接触不可达、支撑破坏作为扣分或资格拒绝，但不能每次失败静默换默认手。诊断允许区分“距离不够”“身体挡住”“同时技能争用肩”“目标表面丢失”；这些原因才能使策略重评有依据。

## 验证、未做与风险

[独立检查](checks/verify_body_contact_examples.py)包含12项：交叉、平行与零长线段，变宽间隙，自由点投影，重合法线诊断，许可的对象/相位/版本/深度，接合区域过滤，目标表面偏移，长嘴穿胸，失效版本，失败残差与非法输入。实际结果记录在[证据JSON](evidence/contact-volume-design-observations.json)。它们不是原作测试，也不是完整骨链求解器验证。

未做：原作运行/函数调用验证、自有三维生物渲染、完整IK与内部手指碰撞实现、连续碰撞检测和性能测量；本轮交付研究规格而非生产实现。后续最小自有场景是胖躯干、长嘴、双手同时接触目标且六足锁脚，记录最大穿透/末端误差/骨长误差和各动作失败原因。

风险：历史公开系统与本机版本未逐项对齐；离散帧代理会漏掉高速穿越，需要对高速动作做分步或扫掠检测；保守代理可能使细部动作过度受限；局部约束投影可能卡在局部解，多个共享骨链目标不保证有解。不得据12项数学/状态测试宣称任意拼装都能无穿插。
