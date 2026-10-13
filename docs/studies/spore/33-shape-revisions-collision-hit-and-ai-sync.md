# 33 身体变形后的碰撞、命中与AI同步

范围：陆地生物加宽、拉长肢体、断肢与换体后，导航占地、攻击执行位置和灵魂策略怎样一起更新。本篇首先列原作入口，再给自己的版本协议和命中算法；Spore没有在本研究中被证明存在灵魂机制。

## 原作证据能回答到哪

社区SDK固定提交 `2d71289adc71aa5c58f4516c6c835c99f5f9ca19`，本轮完整读取四份相关声明并记录摘要及行号：[入口清单](evidence/public-shape-hit-sync-entries.json)。

| 来源 | 具体入口 | 可以确认与不能确认 |
| --- | --- | --- |
| [cSpatialObject.h](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cSpatialObject.h)69–108 | SetScale、SetLocalExtents、GetBoundingRadius、GetFootprintRadius、SetHasModelChanged、SetModel | 社区声明区分模型、边界与占地；不能证明生物编辑后调用顺序或各半径公式 |
| [cCreatureBase.h](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCreatureBase.h)235–236、359、425 | CalculateScale、SetCreatureTarget、mCurrentAttackAnimId、TakeDamage | 存在体型、目标、攻击动画和伤害接口线索；未恢复从骨链到伤害的函数链 |
| [cCreatureAbility.h](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cCreatureAbility.h)140–185 | mRangedDamage、mRange、mRushingRange、mRangeMin | 区分技能距离字段；其与手长、嘴长、实例缩放的最终关系未知 |
| [AnimatedCreature.h](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/AnimatedCreature.h) | 模型与动画对象访问入口 | 不能据此推出碰撞绑定或每帧更新次序 |

这是社区恢复声明，不是原开发团队源代码。结合[25本机技能配置](25-body-reach-attack-ranges-and-hit-resolution.md)、[26移动配置](26-land-approach-stopping-avoidance-and-gait.md)及[29开发者皮肤说明](29-creature-mesh-joins-and-automatic-skinning.md)，仍不能断言原游戏按最终网格触碰决定伤害，也不能断言加宽同步某个导航半径。没有做新的原作运行测量。

## 自研：同一个肉体快照，多种几何职责

```text
BodySnapshot {
  bodyId, generation, shapeRevision, topologyRevision
  graph, restBones, skinBinding, abilityContributors
  reachChains, hurtShapeDefinitions, attackSocketDefinitions
  navigationFootprint, supportDefinitions, geometryDigest
}
PoseSnapshot {
  bodyStamp, simulationTick, worldBones, rootTransform
  hurtShapesWorld, attackSocketsWorld, broadphaseBounds
}
ActionToken {
  actorId, bodyStamp, actionId, executingPartIds
  skillId, targetId, effectOrdinal, reservedResources
}
```

身体图负责shape/topology版本；运行角色拥有generation，换体时即使新配方版本也叫1，generation仍不同。姿态每个模拟tick变化，不因此重建整个网格。外观颜色/纹理版本独立；不能把改颜色当作换体取消攻击。导航使用保守的占地包络，受击使用身体区域体积，攻击使用技能定义的发射点/扫掠形状；三者可以不同，但都必须来自同一个身体快照。

“有碰撞盒”也不意味着“整条手臂都能造成伤害”：拳击只开放指定拳头的命中窗口，身体碰撞仅解决空间关系。灵魂法术可使用SoulOrigin而无物理手部依赖；若技能要求头部念咒/可见发射器，应明确增加肉体依赖，不自动推断。

## 编辑提交与每帧更新是两条流程

```text
commitBodyEdit(recipe, actor):
  candidate = compileGraphRestPoseAndBindings(recipe)
  validatePartIdsChainsAndSocketReferences(candidate)
  deriveNavigationSupportReachAndHurtShapes(candidate)
  stagedQueries = collisionWorld.prepareReplacement(actor, candidate)
  if any step fails:
    discardCandidate(); keepOldSnapshot(); report(stage, reason)
  at simulation boundary:
    publishBodyAndQueryReplacementTogether(candidate, stagedQueries)
    invalidateActionsWithChangedPhysicalDependencies()
    invalidateNavigationAndBodyAssessmentCaches()
    reevaluateSoulPlansBeforeSchedulingNewActions()

updatePose(tick):
  body = actor.currentBody
  pose = solveAuthoritativePose(body, tick)
  shapes = deriveWorldShapesFromSamePose(body, pose)
  bounds = unionOfCurrentAndSweptShapeBounds(shapes)
  publishPoseAndBroadphaseTogether(body.stamp, tick, shapes, bounds)
  evaluateHitWindowsUsingPublishedTick(tick)
  renderMayInterpolateOrUseCheaperLOD()
```

prepareReplacement必须只是暂存，发布阶段必须支持事务或在查询暂停的模拟边界完成替换；如果物理系统不能原子替换，适配层必须补足这一契约。不能先展示新模型、下一帧换碰撞、再下一帧更新AI。异步烘焙返回时先查配方版本，过期结果丢弃但记录版本，见[06](06-editor-input-and-rebuild.md)。碰撞注册失败时保留完整旧快照，不能只留下半个新身体。

断肢是明确的topology改变。删除受击区域与socket、结束它的占用、取消其未来效果并重算支撑；已经产生的伤害不会回滚。换体使全部旧物理行动token失效；纯灵魂技能是否继续，由其显式依赖和产品规则决定。导航路径、能力统计、策略评价都必须包含身体stamp，避免使用另一具肉体的缓存。

## 技能资格、预测与实际命中

技能资格先由配方和资源决定，再评估几何。每个技能明确指定距离规则，例如 FixedRange、ChainReach、ProjectileOrigin；不能统一用一个“手长加技能范围”。AI预测使用同一个几何谓词的预测输入，命中使用效果时点的实际姿态与实际目标，不直接采纳前摇开始时的成功判断。

```text
evaluateEffect(action, effectTick):
  reject StaleBody if physicalDependenciesNoLongerMatch(action)
  reject MissingExecutor if executingPartIsGone(action)
  close this effect as Cancelled if interruption forbids it
  pose = authoritativePoseAt(effectTick)
  target = currentTargetSnapshot(effectTick)
  if policy is meleeSweep:
    witness = sweepAttackVolume(previousValidPose, pose, target)
  elif policy is projectile:
    witness = projectileSystem.resolveFromCurrentSocket(pose)
  elif policy is fixedRangeSoul:
    witness = soulRangeAndVisibilityQuery(pose, target)
  commit Hit or Miss once per (actionId, effectOrdinal, targetId)
  preserve witness, bodyStamp, poseTick, reason
```

窗口中每tick查询与窗口结束结算分开：暂时没有接触并不立即耗掉整个连续命中窗口；一次性打击可以在指定tick提交Miss。Hit去重键须包含目标，允许一次横扫伤害两个敌人；是否允许同目标多段伤害由effectOrdinal明确表达。不要在任意接触时都重复扣血。

## 完整算例：手变粗，AI与命中同时变

设拳头中心x=1.20、目标受击球中心x=1.48，目标半径0.15。旧拳半径0.08，两中心距离0.28大于0.23，无法触碰；新拳半径0.16，和为0.31，当前姿态可触碰。视觉和狭相碰撞更新了，但若广相仍登记旧拳范围 `[1.12,1.28]`，目标范围 `[1.33,1.63]` 不重叠，目标根本不会进入狭相。新广相 `[1.04,1.36]` 必须与新拳体积同tick发布。

与此同时，拉长手臂使最大链可达从0.8变1.2，目标近表面距髋1.05：原计划应接近，更新后可以在关节限位与遮挡通过时攻击。灵魂AI不需要重新定义性格权重，只需使肉体能力/可达缓存失效，再将同一候选技能绑定到新手。若加粗导致窄道不可通，导航占地也一并重算：能攻击更远与能穿过通道是不同评价项。

随后手被斩断：物理行动token因部件消失取消，释放手和躯干预约；支撑规则见[31](31-terrain-contact-foot-locking-and-support.md)。灵魂重新生成“另一只手攻击、嘴攻击、独立法术”候选，再依[16](16-soul-ai-body-assessment.md)评分。不能只把旧技能换一个动画通道、继续从已经不存在的拳头扣血。

## 快速动作的连续扫掠

移动球与静止目标球可用相对运动线段求交：`p(t)=A+t(B-A)`，解 `|p(t)-C|²=(rAttack+rTarget)²` 的最早 `t∈[0,1]`；开始已重叠则t=0，位移近零单独判断。目标也移动时用相对A/B。例如拳从x=0到2，目标在1，总半径0.2，首次接触t=0.4；两端都未接触，端点检测会漏判。

旋转的长嘴/骨链不是直线移动球。需对子区间插值姿态，以最大角变化和长度推导几何误差界，膨胀扫掠形状覆盖弧线，再按精度细分；命中结果可返回保守接触并进一步精查。只扫嘴尖端点连线会漏掉弯曲轨迹或长杆中段；角速度未知、预算耗尽时保留UnverifiedSweep诊断，采取产品明确的降级策略，不能静默声明未命中。

命中体积从权威模拟姿态生成，显示动画LOD/插值不改变伤害判定。若降低模拟姿态更新频率，也必须提供扫掠误差界和明确预算策略，不能以“看不见”跳过仍在战斗中的对象。相关成本见[34](34-editor-validity-complexity-and-runtime-cost.md)。

## 验证与限制

[独立检查](checks/verify_shape_hit_sync_examples.py)覆盖变粗后的广相/狭相一致、换代失效、注册失败保留旧体、扫掠穿越、按目标去重、换外观不取消物理行动、同tick几何与LOD无关。

未做：原游戏碰撞函数反编译、运行时命中测量、自研引擎接入。风险：原作命中几何与同步顺序未知；这里是独立设计，真实关节、转动扫掠和事务式物理注册仍需目标引擎验证。
