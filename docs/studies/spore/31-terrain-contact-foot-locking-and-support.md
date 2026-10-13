# 31 地形接触、锁脚与身体支撑

范围：登陆后、部落前的生物移动。重点是六足长短不一时怎样上台阶、转弯和停步，以及身体加宽后为何必须重查落脚。下文算法是自研规格，不是恢复的 Spore 源码。

## 原作证据与仍然未知的部分

开发团队[动画论文](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)§4.2（印刷页6–7）说明：按近似腿长分组，以简单频率比例协调；脚沿作者曲线运动，轨迹按腿长缩放，并随速度插值；髋部可位移/旋转以调整身体。每组1–6足采用作者数据，更多足程序化产生参数。无脚时有漂浮、爬行和以脊柱节点作“假脚”的启发式。

§3.2.2的 ground-relative 是通用目标坐标模式，垂直轴在参考高度与地面高度之间归一化；它不说明足部如何查询地形或保持接触。§4.3的姿态点求解并不等于刚体动力学；§5明确忽略自身碰撞。论文身份：11页，SHA-256 `f64be1b504845f715e2ab440e1653d1c487bf16d51b478eab1c913162fbc3d82`。这是历史开发者说明，未逐项对齐本机1.3.0.29。

[26](26-land-approach-stopping-avoidance-and-gait.md)已有本机移动/GAIT配置，不能据此推出真实地形采样、台阶探测、锁脚世界坐标、支撑多边形、摩擦或根骨平衡算法。实际撞地查询和步态到地面约束的调用链仍未知。补充原作入口见[本轮地形观察记录](evidence/local-terrain-contact-entry-observations.json)。

固定提交社区声明另有 `PlanetModel::GetHeightAt/ToSurface`、`ITerrain::Raycast/GetOrientation`、`cTerrainMapSet::GetHeight`。它们提供地面查询候选，不证明Creature脚实际调用。`Anim/IAnimWorld.h`有返回float并输出法线的回调类型，由未命名接口接收；回调用途、注册者和脚部连接仍未知。AnimatedCreature相关声明没有找到具名锁脚API；这只说明本次查找覆盖，不能证明原游戏没有锁脚。

## 自研状态及其所有者

```text
FootContact {
  partId, bodyGeneration, state: Stance | Swing | Settling | NoContact | Disabled
  surfaceId, surfaceRevision, anchorInSurface, contactNormal
  from, landing, swingStartTime, swingDuration, clearanceHeight
  supportEligible, solverResidual, lastFailure
}
GroundCandidate {
  point, normal, surfaceId, material, patchClearance, reachable
}
GroundController {
  bodyGeneration, rootRequest, actualRoot, contacts[], mode, diagnostics[]
}
```

身体图拥有足ID和骨链；地面控制器拥有接触生命周期；步态调度器只提出哪只脚何时迈步；姿态求解器实现目标并回报误差。支持资格来自已实现的接触，不能由“相位处于支撑段”直接宣布。身体换代后旧接触全部失效；断足只删除相应记录，再重评支撑与步态。

锁脚保存的是地面物体的局部锚点：`anchorWorld = surfaceTransform * anchorInSurface`。静止地面自然得到固定世界点；移动平台会携带它。不能每帧拿当前髋部位置重算支撑脚，否则脚会滑；也不能永远缓存旧世界点，否则平台移动时脚留在空中。地面消失、变形版本过期或求解残差超阈值时转为 NoContact，记录原因。

## 落点与摆脚

预测下次落脚时髋部位置：`hipFuture = predictedRoot * shapedHipMount`，根速度包括平移与转向；瞬时髋速度为 `v + omega × r`。以未来髋与参考足位为中心枚举有限环形候选，逐个做地形与身体查询。候选稳定排序，避免相同分数随机抖动。

```text
chooseLanding(foot, futureRoot):
  candidates = probeRing(futureRoot * foot.restContact, fixedOffsets)
  for c in candidates:
    reject if dot(c.normal, up) < cos(maxSlope)
    reject if supportPatchIntersectsEdge(c, foot.soleRadius)
    reject if materialCannotSupport(c) or surfaceIsInvalid(c)
    reject if chainDistance(futureHip, c) outside [minReach, maxReach]
    reject if proposedBodyOrFootSweepsObstacle(c)
    score = wTravel*distanceSquared(c, restContactFuture)
          + wSlope*(1-dot(c.normal,up)) + wEdge*edgePenalty(c)
  return lowestScoreThenStableSurfaceId or Failure(NoLanding)
```

查询需要足底覆盖区域，不能仅射一条中心射线：脚中心在台阶边缘有地面，半个足底仍可能悬空。足目标是 `point + normal * soleThickness`，转换到身体空间后交给IK。接触法线决定足底姿态；扭转仍受关节限位及参考弯曲方向约束。

摆脚轨迹使用[04](04-gait-synthesis-and-foot-targets.md)的教学形状：`u∈[0,1]`，`s=3u²−2u³`控制水平插值，`b=16u²(1-u)²`控制抬高；`z=lerp(zA,zB,u)+H*b`。实际实现可以改用同一平滑参数控制各分量，但碰撞检查必须针对最终曲线。

在内部采样点，要求 `H >= (obstacleHeight + margin - baseHeight)/b`。端点的 `b=0` 必须独立验证合法接触，不能除以零；采样只用于估计H，最后对完整足体积做分段扫掠。有限高度采样不保证连续无碰撞；采用与曲率误差界匹配的细分和膨胀扫掠，超预算返回明确失败，不能宣称已验证安全。

例如起点高0、落点高0.2，在 `u=.25` 时基础高度0.05，障碍高0.2，余量0.02，`b=.5625`，需要 `H≥.302222…`。原来的0.12会撞台阶，取0.31通过这个采样条件。它还须通过整条足体积扫掠，不能只检查最高点。

## 身体高度与支撑约束

先用简化、站立向上的链包络计算可行高度。对第i只支撑足，水平距离d、允许链距离 `[Lmin,Lmax]`、髋部相对身体竖直偏移hi：

```text
if d > Lmax: unreachable
lower_i = footZ - hi + sqrt(max(0, Lmin²-d²))
upper_i = footZ - hi + sqrt(Lmax²-d²)
bodyZ ∈ intersection(all [lower_i, upper_i], [bellyClearanceZ, +∞))
```

这是髋部位于足上方的球壳近似；真实关节限位、分叉链和参考弯曲可进一步缩小集合。不能把长度包络直接当成IK成功。改变身体倾角后水平距离和髋偏移会变，需重算并以最终姿态残差验收。体表/肚子离地查询提供下界，不能用根节点高度代替最宽最低的身体表面。

六足算例：四长腿最大长0.9，两短腿0.6，当前短腿落地，水平距离0.3。短腿给身体高度上界 `sqrt(.6²-.3²)=.519615…`。旧身体离地下界0.45，选0.50可行；肚子加厚使下界变为0.55，交集为空。不能硬伸腿，应暂停根运动、重新安排短腿落点或降低身体倾角。把短腿落到水平距离0.2处，上界变为0.565685…，选0.56才再次可行；移至高0.2的台阶会得到另一组高度区间，仍要与其他支撑足共同求交。

缓慢、近似静态移动可把有效支撑点投影到垂直于重力的平面，建立凸包，要求质量中心投影离边界有余量。抬足前先用剩余足重算；攻击占用一条兼任手臂的腿也走同一流程。两点支撑、多块斜面、跑跳、加速度和低摩擦不能仅凭二维凸包判断稳定；需要动力学/接触力模型，或切换到明确支持这些动作的简化运动模式。质量中心须来自身体质量分布，不能默认等于根骨位置。

## 一帧流程与停步

```text
updateGround(body, dt, now):
  invalidateDetachedOrStaleContacts(body)
  refreshSurfaceAnchorsAndValidateSupport()
  rootProposal = movement.request(dt)       // 26的实际移动意图
  for dueFoot in gait.proposeLifts(actualSpeed, now):
    if remainingSupportIsAcceptable(dueFoot):
      landing = chooseLanding(dueFoot, predictedRoot)
      if valid: startSwingWithSweepCheckedTrajectory(landing, now)
      else: recordFailureAndRestrictRootMotion()
  advanceActiveSwings(now)                  // 速度归零也继续计时
  rootPose = solveHeightAndLimitedTilt(rootProposal, validContacts)
  if infeasible: reduceMotionOrSwitchExplicitModeWithDiagnostic()
  solveFootGoalsAndBodyPose(rootPose)
  downgradeContactsWhoseActualResidualIsTooLarge()
  movement.publishActualRootAndSpeed()      // 下一帧步态读实际速度
```

转弯时，远离旋转中心的髋速度更大，不能只看根平移速度。停步时阻止新周期迈步，但已腾空的脚必须完成落地或安全回落，进入 Settling 后转 Stance；把所有脚的相位直接冻结，会把脚悬在半空。无可落点时保留 NoLanding、UnsupportedSurface、BodySupportInfeasible 等原因；无足生物采用专门漂浮/爬行控制器，不能把空凸包当正常支撑。

## 可验证边界

构造算例见[检查脚本](checks/verify_terrain_contact_examples.py)，覆盖高度区间、台阶抬脚、平台锚点、转弯髋速度、停步继续落脚和不安全抬足。它们验证独立数学与状态规则，不验证原游戏。

未做：运行游戏、读取私人生物存档、恢复碰撞查询调用链或真实测量足底。风险：原作锁脚和根高度公式未知；本规格的球壳/静态支撑是近似，须在自研物理环境中验证摩擦、坡度及动态步态。
