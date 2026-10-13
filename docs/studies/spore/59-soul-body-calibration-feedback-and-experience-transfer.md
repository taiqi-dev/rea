# 59 灵魂怎样校准新肉体、归因失败并迁移经验

[目录](README.md) · [14经验反馈](14-ai-strategy-and-action-scoring.md) · [16联合决策](16-soul-ai-body-assessment.md) · [46执行资格](46-capability-contributions-body-statistics-and-executor-qualification.md) · [55关节可行性](55-joint-limits-shape-edits-and-motion-feasibility.md) · [57功能预览](57-editor-animation-preview-and-functional-validation.md) · [58整链编辑](58-limb-subtree-copy-replacement-and-reparenting.md)。只借鉴陆地Creature编辑器与动作适配；本篇灵魂学习全部是用户产品的独立设计。

目标是让灵魂知道“这个肉体当前怎样用更可靠”，同时保留真正的身体限制。**经验改变预测与策略，不授予缺失肢体，也不绕过关节、资源和动作所有权。** 不能把新肉体的一次失败解释成灵魂永久忘了技能，或把旧身体的命中率直接搬到新手上。

## 原作参考与尚未建立的机制

46实际四份手/嘴资源表明角色与攻击字段分开；50保留编辑配方、编译表与运行骨索引的区别；51区分原始动画坐标与自有权威动作时钟；52说明注视目标与具体器官不是同一个身份。它们给我们提供身体描述、执行者绑定和变化失效的参考。**没有取得Spore灵魂、换体自校准、在线命中学习或经验迁移的原作证据。** 不把这篇算法称为原游戏AI。

本轮只复核九份既有文档/证据的完整摘要，未读取新游戏载荷；14、16、17本来就是独立规格，不能作为原作学习证据。[参考身份清单](evidence/soul-body-calibration-study-references.json)区分复用和新增，原生提供者缺口沿用00。本篇是把14的计数反馈细化成可执行的归因、校准和迁移契约。

## 自研：四种知识分别归属

| 知识 | 所有者/适用条件 | 换体时处理 |
| --- | --- | --- |
| 技能概念与战术 | 灵魂；例如知道可打断蓄力、会某个法术 | 保留知识，重查新肉体执行模式 |
| 几何/功能证书 | 当前编译身体与规则版本；关节、连接、支撑、接触代理 | 验证依赖摘要；失效部分重建 |
| 动作熟练预测 | 技法版本＋具体提供者/依赖几何＋情境＋动作风格 | 精确相容才保留；其他情况仅允许带来源的弱先验 |
| 当前动作与观测 | 身体生命期、控制租约、资源/冷却、目标观测 | 旧计划失效；世界已提交效果保持自己生命周期 |

几何证书是自有编译器/约束检查给出的事实或范围，不能由“过去十次都成功”替代。操作熟练度与战术知识也不同：灵魂可能会双手仪式，但新肉体只剩一只手；知识仍在，当前执行模式被硬条件拒绝。

原始反馈按身体生命期和稳定执行者归因，避免串号。跨肉体共享的技法与弱先验另存灵魂，避免为每个身体从零遗忘一切。两层同时存在，不按模型数组下标保存学习数据。

## 自研核心结构：依赖、情境、试验与证据

```text
CapabilityCertificate {
  bodyLifeId, bodyRevision, compiler/solverVersion,
  exactProviders, joint/mount/supportDependencies,
  validatedBounds, coverageDomain, failures
}
MotorMetricKey {
  learnerSoulLifeId, bodyLifeId, providerInstanceId, abilityModeId, techniqueVersion,
  dependencyDigest, motorStyleVersion, solverVersion,
  contextBin(distance, targetMotion, ground/stance), evidenceDomain/protocol
}
EvidenceBucket {
  realSuccesses, realFailures, priorAlpha, priorBeta,
  transferWeight, transferSources, observationIds, modelVersion
}
AttemptTicket {
  uniqueAttemptId, metricKey, bodyRevision, controlGeneration,
  selectedProviders, targetLife/observation, executionEventId,
  start/endTime, committed, measurementProtocol, resultStatus
}
CalibrationSnapshot {
  body/control identities, certificates, estimates, missingCoverage,
  sourceObservations, rejectionReasons
}
```

依赖摘要至少包含该动作真实使用的部件定义/造型、连接路径/安装框架、相关共享关节、执行profile/socket、支撑与感知协议。测试条件还包含健康/疲劳和姿态域；不能假定同样长度的手都一样。摘要是有依赖清单的校验结果，不只是整个模型文件名的hash。

拉长右臂使右爪相关摘要改变；左手是否可复用取决于其支撑、根姿态和共享关节是否也变化。身体整体加宽若移动左右安装点，两个分支都受影响。只换涂装且碰撞/运动输入不变可保留动作测量；换了动力风格、感知方式或求解器版本则另建情境。旧证据保留历史身份，不删除来伪装兼容。

## 自研评估：先硬资格，再性能预测

```text
AssessOwnCalibration(body, soul, plan, context):
  validate current control lease and immutable body/definition identities
  enumerate owned Body and Soul abilities and distinct executor groups
  inspect exact required parts, connection/function state and named output profiles
  check available resource pools, cooldown deadlines and output reservations
  validate target permission, distance/direction, joint/volume/support constraints
  if hard gate fails: return Rejected(reason, source); do not score it away
  derive dependencies and protocol/context key for this exact candidate
  if matching current evidence exists: return estimate plus sample coverage
  if explicit compatible transfer receipt exists: return weak prior with provenance
  return EligibleButUnmeasured with declared prior and uncertainty
```

“EligibleButUnmeasured”不是不能用。灵魂可按保守预测选择它，也可在合适的测试场申请少量试验；重要的是不把未知写成保证命中或永久禁止。预览测出的固定站位不能无条件推到斜坡、奔跑目标或真实战斗。

几何可达范围用空间域/限位证书表示；命中表现按明确情境记录。例如distance1.0–1.5m、中速移动目标、平地是一个单元，distance2.0–2.5m或飞行目标是别的单元。有限采样只证明采样覆盖，不能宣布所有中间姿态、共享关节组合和新距离都已通过。

## 自研反馈归因：不是所有失败都记一次miss

| 已记录结果 | 更新哪一层 | 本篇二项命中统计 |
| --- | --- | --- |
| 已合法提交并测得接触成功 | 指定动作/情境的接触表现 | success+1 |
| 已合法提交、测量完整且未接触 | 同情境的正常动作结果 | failure+1 |
| 手忙、能量不足、冷却未到 | 当前可执行性/资源诊断 | 不计miss |
| 骨链/关节检查拒绝 | 精确几何域与约束诊断 | 不计miss，也不整体删除技能 |
| 目标销毁、观测缺失、测量超时 | 环境/测量完整性 | censored，保留原因 |
| 发射前断肢或动作取消 | 执行生命周期 | 不计miss |
| 发射后命中但已换体/换魂 | 旧动作的历史归因 | 更新旧历史，不污染当前身体模型 |

接触成功而伤害为0可能是护甲/免疫，应该分别记录“接触”“有效伤害”“打断结果”。目标正常移动躲过攻击，在协议允许的目标运动域中可算有效miss；目标生命期被删除则不是同一观察。诊断不合并成一个failure计数。

```text
RecordOwnOutcome(ticket, observation):
  require known unique attempt and authoritative/owned measurement source
  validate outcome kind, identity and result interval
  if outcome ID already consumed:
    reject conflicting payload as ConflictingOutcomeReceipt; exact repeat is DuplicateOutcome
  retain raw observation and classification; diagnostic results remain visible
  if censored, uncommitted or execution blocked: do not update hit counts
  else:
    attribute to ticket's original mode/provider/context/dependencies
    if body/control/key still current: update active evidence model
    else: update separate historical model under the old ticket
  schedule re-evaluation only from affected current evidence and hard-state changes
```

历史和活动模型是分开的表。即使字段key碰巧一样，旧控制代次的迟到回报也不能直接增加活动模型计数；要通过明确的重新验证/迁移步骤。已经提交投射物仍能命中，是世界效果生命周期允许的历史结果，不允许它在新身体上产生一个新的动作。

脚本用顺序处理和一个完成回报验证核心归因；没有实现完整测量源鉴权、时间区间采样、多阶段结果合并或持久化事务。生产实现还要处理一试验多个语义结果、超时后的显式更正和并发去重，不能把示例字典当数据库保证。

## 自研可解释预测：均值与不确定性一起参与

本例构造二项模型：同一协议/情境下每次合法完整尝试记s/f，初始a0=b0=1。`a=a0+s`、`b=b0+f`：

```text
mean = a/(a+b)
sigma = sqrt(a*b / ((a+b)^2 * (a+b+1)))
pScore = max(0, mean - lambda*sigma)  // 本例lambda=1
```

这是自有概率模型及保守评分政策，**pScore不是95%置信下界或下一次必定成立的概率保证**。模型要求结果定义和情境近似稳定；样本相关、选择偏差、动作风格变化或目标行为改变都会影响适用性。没有真数据时返回先验及缺覆盖，不给它套“已校准”的名字。

无真实样本时mean=.5、sigma≈.288675，pScore≈.211325；8成功/2失败时mean=.75、sigma≈.120096，pScore≈.629904。未知表现不会被当成100%命中。明确无效的硬条件则直接拒绝，不使用上述先验。

本例评分沿用16的独立尺度但简化保护项：

`U=pScore×damage/30 − .25×(bodyCost/10+soulCost/20) − .05×durationSeconds − predictedSelfLoss/30`。

数值为构造输入，damage在完整产品里需按已知目标生命/护甲与效果定义修正，风险估计也必须有来源。不能按击杀次数训练命中模型，或为了提高评分隐式使用隐藏敌人HP。

## 自研校准任务与经验迁移

校准在57的隔离预览副本里执行。优先级0为关键未测动作，其后按稳定试验ID；限定时间与尝试数，实际新敌情/真实控制切换到来立即取消待执行校准，不在战斗中强制角色试招。

```text
PlanOwnCalibration(snapshot, coverage, budget):
  choose missing or invalidated metrics needed by current owned action modes
  build explicit probes with target/motion/stance/reset/measurement protocol
  sort by declared criticality and stable ID
  admit only finite positive durations fitting remaining time/attempt budgets
  report PartialCoverage and untested cells; do not claim whole-body validation

RunOwnProbe(probe):
  instantiate isolated exact recipe/pose/control snapshot
  wait for current-version mesh/bind/capability bundle and baseline stance
  validate resources/cooldown and execute only the declared action mode
  collect contact, timing, resource and constraint results under one attempt ticket
  retire owned effects/actors; retain diagnostics and unconsumed time on failure
```

脚本只验证探针排序/预算；没有运行3D动作或直接验证这些测量步骤。每次独立试验从已声明的就绪快照开始，记录reset方式；预览副本重置不能清空真实角色的身体/灵魂冷却、资源、损伤或世界奖励。测量时间用实际权威动作进度，不以画面FPS或原作time整数猜秒。

迁移分三类：技能概念保留；完全匹配且仍有效的当前身体证据可按依赖保留；同一灵魂仅相似的新身体使用弱先验。相容回执逐项声明同一学习者、程序版本、角色、链拓扑、安装框架、形变差异范围和感知协议；字段缺失是未建立相容，不能静默当通过。换到另一灵魂保留身体几何证书，默认不继承前一灵魂的动作熟练统计。

本例相容迁移上限为w=2个**先验权重单位**，不是两次真实尝试。用源模型均值p：`a0'=1+w×p`、`b0'=1+w×(1−p)`，新身体s=f=0，保留来源。8/2源模型p=.75得到a0'=2.5、b0'=1.5，新均值.625；不会直接宣称新身体已有10次测试。无源实测样本则w=0；不相容技法/链拓扑则回到未测先验并记录原因。

本篇代码接收显式相容回执，没有实现通用三维几何相似度判定；生产回执应由可审计的定义/形变比较器产生。相容阈值是产品规则，不是Spore参数。静态结构经验、动作技巧和目标战术也不能用同一个w来混合。

## 自研完整例子：四手六足肉体、改右臂、换体

以下发生在隔离编辑测试场，面对同一中速移动假目标，distance1.0–1.5m/平地/normalV1；所有结果都是构造输入，不是实际游戏测量。B1/revision8由灵魂S/control3控制。R、L代表四手中两个合格攻击者；其余手目前占用。纯灵魂SoulBolt模式使用有效SoulSense，体形变化不影响该模式的定义与感知来源；若改用肉体眼睛瞄准，则必须另建依赖模型。

| 方案 | 本情境完整成功/失败 | pScore | 伤害 | 身体/灵魂成本 | 时间s/预测自身损失 | U |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| R爪击 | 8/2 | .629904 | 30 | 6/0 | .7/3 | .344904 |
| L爪击 | 4/2 | .463626 | 20 | 4/0 | .5/2 | .117417 |
| SoulBolt | 5/1 | .605662 | 24 | 0/8 | .6/1 | .321197 |

1. 当前三方案硬资格都通过，选R爪击。若R被盾动作占用，即使分数最高也先HardRejected，剩余合法方案中选SoulBolt；不会自动把R品质和历史命中搬给L。
2. 玩家只拉长R臂，revision9/右链摘要改变；L的安装/共享支撑确实未变，L证据保留。新R几何范围由55的证书重新评估，不由统计决定。旧R的8/2仅保留历史，当前R无测量时pScore=.211325，U≈−.073675，灵魂暂选SoulBolt。
3. 请求四次新R探针，每次声明.7秒动作＋.2秒复位，总预算3.6秒/4次。脚本验预算可容纳；实际probe是否完成仍依赖57的副本执行和测量。本例输入四次合法成功，得到a=5、b=1，pScore≈.692474、U≈.407474，重新选R。一次忙碌拒绝或断肢中断不算第五次miss。
4. revision8已发射投射物的迟到命中按旧ticket归历史，只增加历史R证据，当前revision9的四次样本仍是4/0。显示模型palette重排则不改变稳定R ID与依赖摘要，但提交仍读取当前绑定。
5. 复制右臂产生Rclone新实例，不能共享R的实测计数；可在确证技法/拓扑/安装相容后使用上述弱先验，再做自己的测量。换到B2的新手同理。严重反折、换侧装框架、损坏支撑或缺手均拒绝相容或执行资格，灵魂保留技能概念并改选其他合法模式。
6. 换魂到control4时，旧control3结果不能写当前活动模型。新的灵魂风险权重、技法和动作style需明确版本；身体几何证书仍属肉体，动态动作预测按授权重建。新控制者可以更保守地选SoulBolt，但不能把缺手方案靠高分变合法。
7. 进入真实战斗时domain改为combatV1。测试场数据不直接成为combat的真实样本；只能采用明确的弱先验和覆盖提示，再用该战斗情境的合法观测更新。目标丢失、资源改变和敌人新招会触发16的重新评估，不等待累计十次才处理。

## 检查、未做与风险

[32项独立检查](checks/verify_soul_body_calibration_examples.py)通过：6个计数/不确定性检查、14个归因/范围/身份检查、11个迁移/评分/探针预算检查、1个既有来源身份检查。覆盖重复回报、未提交命中、旧身体/控制历史隔离、不同灵魂/技法、未测域、相容弱先验、硬资格、完整R→Soul→R算例与探针预算。[本篇检查记录](evidence/soul-body-calibration-verification.json)和[五项总记录](evidence/editor-body-ai-five-topics-verification.json)保留实际范围，不累计上一轮139项。

已交付：可讨论的自研状态结构、反馈归因、有限校准、经验迁移和数值例。没有新增原作学习算法结论。代码仅模拟顺序统计/身份政策，不实现全部IK、接触测量、目标观察、纯灵魂技能执行、三维相容比较或生产数据库。

未做：游戏运行/附加、真实身体测量或AI对局、用户项目实现、概率拟合、生产调度、并发/保存恢复/网络验证。没有安装、改配置、改变原游戏文件或写Git。

风险：二项假设和有限情境单元会受样本相关、选择偏差与环境变化影响；数值通过不保证概率校准、最佳打法或趣味性。迁移回执若漏了安装/支撑/感知依赖会错误复用经验，历史迟到回报若混入活动表会污染新身体。预览与真实世界的资源/事件账本必须隔离。
