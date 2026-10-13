# 04 多足步态：时钟、接地与摆动目标

[目录](README.md) · [结构](03-core-structures-and-frame-pipeline.md) · [求解器](05-particle-ik-and-rest-pose.md)。本模块负责“脚什么时候去哪里”；骨链怎样弯由 05 处理。公开设计锚点见 00；以下分组阈值、公式、事件处理和停步规则都是独立规格。

## 公开设计与自研公式之间的边界

论文 §4.2 明确区分动画师配置的组内 1–6 只脚与程序生成的 7 只以上，并描述髋部随足部运动调整。这个数量指组内脚数；本节六足偏移表和轨迹多项式都是另选的教学参数。[开发团队动画论文](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

后续[26：移动与步态连接](26-land-approach-stopping-avoidance-and-gait.md)已读取本机gait0–6资源的局部结构与参数：gait6六个槽的触发偏移和着地比例，与下文教学交替三脚方案不同。26分别列出原值、补丁包差异和实际速度反馈的自研规格；本节公式不因此变成原作恢复算法。

## 数据与职责

边走边攻击与主动控制脚的共享骨链问题见[28](28-parallel-actions-channel-ownership-and-conflicts.md)。自研踢击需先完成支撑转移，结束后确认落脚再回步态；不能用攻击目标直接覆盖仍承重的世界脚锚点。

输入：有效足部列表、参考腿长、角色运动、地形查询、时间。状态：连续时钟、每脚模式、上次落脚锚点与正在进行的摆动。输出：每脚的世界位置目标、可选髋部目标、接触状态与失败诊断。我们将髋部上下/侧向摆动配置为独立低优先级曲线；足部目标也通过 05 的简化连接参与躯干调整。

```text
GaitGroup { feet[], representativeLength, frequencyRatio, phaseOffset }
FootState {
    nodeId, groupId, phaseOffset, dutyFactor
    mode: Stance | Swing | Settling
    anchorWorld, swingStartWorld, swingEndWorld, swingStartClock
    restFootLocal, reachLimits, lastContactResult
}
GaitClock { cycles: Float64, previousCycles, stopRequested }
```

长度取参考骨链长度，不能用动画中两端距离替代：弯腿会令端点距离改变，却不会令腿瞬间变短。接地资格是独立配置，不假设所有带 Foot 标签的末端都能支撑。

独立分组方法：按长度排序，当前组中最长/最短不超过 1.25 才允许合并；该值不是游戏参数。组代表长度取中位数。以最长组的频率为基准，对各组期望频率，从 `{1/2, 1, 2}` 选择对数误差最小的比率；这些候选和期望公式都由我们定义。原游戏准确阈值、比率集合与优化方法未知。

## 共享时钟、各脚偏移

```text
clock.cycles += baseFrequency(speed) * dt
p_i = frac(group.frequencyRatio * clock.cycles - foot.phaseOffset)
p_i < beta_i  => 支撑期
p_i >= beta_i => 摆动期
```

独立六足算例：频率 1 Hz，β = 0.65，L1/R2/L3 的偏移为 0，R1/L2/R3 为 0.5。在 t=0.28 s，两组相位为 0.28 / 0.78；第一组支撑，第二组摆动。t=0.78 s 对调。每周期双组同时支撑的时间比例为 `2β−1 = 0.30`；这是教学配置，不是本机六足表。

组内脚数与腿对数不同：同长度组可能包含身体不同位置的单脚。对称关系能帮助安排相位，但不能只凭左右名称推断其支撑资格。

## 事件跨越比“当前相位”更重要

低帧率可能一帧跨过离地和落地。只比较 `p < beta` 会漏掉整个摆动。独立实现使用未取小数的连续相位，按时间排序处理所有边界，并限制单次工作量。

```text
AdvanceFoot(oldCycles, newCycles, foot, groups):
    ratio = groups[foot.groupId].frequencyRatio
    a = ratio * oldCycles - foot.phaseOffset
    b = ratio * newCycles - foot.phaseOffset
    events = all boundaries in (a, b]:
        k + beta => LiftOff
        k + 1    => TouchDown
    if events.count > configuredBudget:
        return Error(TimeStepTooLarge, nodeId, a, b)

    for event in chronological(events):
        if LiftOff:
            foot.swingStartWorld = foot.anchorWorld
            foot.swingEndWorld = PlanOwnLandingAt(event.time, foot)
            foot.mode = Swing
        if TouchDown:
            contact = ProbeTerrain(foot.swingEndWorld)
            if contact.invalid: return Error(NoValidContact, nodeId)
            foot.anchorWorld = contact.position
            foot.mode = Stance
```

时钟精度和长时间累积可另做分段，不能通过每脚随意重置相位让组间同步消失。错误后由上层选择细分时间步或显式重置步态；不能默默跳过事件。

## 支撑脚固定；摆动脚规划下一次落点

支撑期令脚的世界锚点 A 不动：`footLocal = inverse(bodyWorld) * A`。身体以 0.8 m/s 前进、支撑 0.65 s 时，脚相对身体后移 0.52 m。若仅后移 0.20 m，将产生约 0.32 m 的滑动误差。

摆动期在离地时冻结起点 A 和计划落点 B。自研轨迹采用：

```text
u = normalizedSwingProgress in [0,1]
s = 3*u*u - 2*u*u*u
P(u) = lerp(A, B, s) + up * H * 16*u*u*(1-u)*(1-u)
```

高度项端点及一阶导数为零，中点高度 H。H=0.12 m 时 u=0.5 抬高 0.12 m。若地形两端高度不同，A/B 已包含地形高度；up 的定义要固定。此模型尚未提供障碍绕行和落地碰撞反应。

```text
PlanOwnLandingAt(liftoffTime, foot):
    touchdownTime = liftoffTime + remainingSwingDuration
    predictedBody = PredictOwnRootMotion(touchdownTime)
    candidate = predictedBody * foot.restFootLocal
    candidate = ClampToOwnReachRegion(candidate, foot.reachLimits)
    contact = terrainProbe(candidate, maxSlope, permittedSurfaceTypes)
    return contact.valid ? Ok(contact.point) : Error(UnreachableLanding)
```

预测、可达区域、坡度阈值都是自研政策，未恢复 Spore 的落点公式。在线重规划若直接替换 B 会令轨迹跳动，需要连续拼接或只在下一步生效。

## 转弯、停步、长短腿与无脚

刚体近似下，髋部速度 `v_i = v_body + omega × r_i`。例如绕竖直轴角速度 1 rad/s，某髋部距轴 0.4 m，仅旋转贡献速度大小就是 0.4 m/s。因此原地转弯仍需调整足部目标，不能把线速度为零等同于所有脚静止。

独立停步规则：不再启动新的步伐；正在摆动的脚完成或转入 Settling；重新取得合法支撑后收敛至参考姿态。我们不把频率立即置零冻结半空中的脚。恢复走动时统一重新建立相位和锚点，具体连续过渡策略需要额外实现。

不同腿长可以具有不同频率比和摆幅，但共用连续时钟。过短腿是否闲置、调整躯干高度或进入其他运动模式是产品选择，不能未经判定拉长所有腿。无脚生物返回显式 `NoSupportFeet`，交给单独配置的滑行/蠕动模式；其原游戏细节见 09 的待研究条目。

## 验证与缺口

可检验关系：相位分组、30% 双组支撑、0.52 m 相对位移、轨迹端点/中点，以及跨周期事件顺序。它们只能验证本规格。没有测量原游戏脚滑动、坡地落点、组频率、停步或支撑资格。

风险：平地轨迹无法自动解决地形与碰撞；步态产生可达目标仍不保证求解器收敛。不能从显示的足部动画推导实际推进力或游戏移动速度。
