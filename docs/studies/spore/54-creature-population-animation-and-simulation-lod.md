# 54 多生物同屏：网格、动画与模拟的LOD

[目录](README.md) · [研究入口](09-related-systems-and-verification.md) · [显示成本](34-editor-validity-complexity-and-runtime-cost.md) · [战斗动作](11-action-plans-and-execution.md) · [群体协作](21-pack-coordination-and-shared-intents.md) · [重建一致性](44-editor-rebuild-undo-and-animation-cache-consistency.md)。范围为登陆后、部落前的陆地生物及其编辑器；不把星球或其他阶段的LOD当作陆地个体算法。

这次补到真实配置：本机选定CreatureGameTuning父资源里，SimulationLOD的Low/Med最小距离原值分别为**100/75**，Game与Patch相同。**单位、距离参考对象、载入变体和实际调度仍未知**，所以不能写成“离玩家75米就把AI改成某个频率”。后半篇是自己的100个多足NPC分层调度规格。

## 原作：三种LOD不能合成一个开关

固定SDK与FX公开声明及摘要见[公开记录](evidence/public-creature-lod-contracts.json)。SDK提交`2d71289adc71aa5c58f4516c6c835c99f5f9ca19`，FX提交`a482c51d8d37fc8cf416acecc3c00a5b0723f2e5`。它们是社区接口/格式资料，未与本机函数体逐项对齐。

| 层 | 实际公开表示 | 尚未确认 |
| --- | --- | --- |
| 网格/模型显示 | Graphics/Model.h 158–175有mesh/animation LOD数组、距离、当前LOD索引；IModelWorld.h 391–409有数量、强制档位和距离尺度接口 | 陆地生物实际有几档、各档顶点/骨/纹理、距离乘数和转换 |
| 动画管理 | FX登记LODMaxHigh/Medium/Low、LODCutoffHigh/Medium、TintCreaturesByAnimLOD、useHighAnimLOD；IAnimWorld.h 34–36有多个更新阶段 | 具体配置、求解降频/跳过策略、队列/更新容量 |
| 个体模拟 | FX登记creatureSimulationLOD_MinDistanceLow/Med，选定本机资源读到直接值；cCreatureBase.h 225–244有Update/饥饿/意图等接口 | 谁计算LOD、个体AI与移动/交互实际频率、远处是否聚合 |

`Graphics::Model`的`mAnimationLods[4]`是模型侧表示，不能直接等同于动画世界的High/Medium/Low调度层，更不能当作三档AI。数组容量不说明每只陆地生物四档全部存在。`useHighModelLOD`和`useHighAnimLOD`也是不同名字。

[IModelWorld固定声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Graphics/IModelWorld.h)的SetLOD注释描述0–3强制档位、-1恢复按距离；GetNumLODs查询模型数量，另有kUpdateLOD渲染标志。这支持模型显示独立入口，仍不是当前陆地资源阈值或运行观察。

[IAnimWorld声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/IAnimWorld.h)包含Update、UpdateCreatures、PostUpdateCreatures。一个未知方法的注释说与lod max相关，没有恢复其语义；“must be called every frame?”仍是社区疑问，不能当固定频率。新查到的`cAnimWorld.h`只是全段注释占位类，没有实现。

cCreatureAnimal/cCreatureBase的Update声明和BakeManager的队列/取消声明分别提供个体更新、资源构建入口，没有给出100个生物如何调度。固定仓库路径清单中的MyRenderable只是示例，星球High/LowLOD头文件属于别的对象，没有用于陆地个体结论。模型显示沿实际Model/IModelWorld/cSpatialObject声明核对，不因文件名含Renderable就混入示例算法。

## 本机新读取：SimulationLOD原始配置

沿26已经选定的CreatureGameTuning准确资源键继续读取LOD字段，没有全包扫描属性。检查两个包全部DBPF索引，然后只解码8份已选PROP：group `0x00000000`、`0x02AE0C7E`、`0xF71FA311`、`0xAD56080C`各在Game/Patch一份，type `0x00B1B104`、instance `0x7C340397`。

| 位置 | 属性与类型 | 直接原值 |
| --- | --- | ---: |
| 两包group AD56080C | `0x052583BC creatureSimulationLOD_MinDistanceLow`，float32标量 | 100 |
| 两包group AD56080C | `0x052583D4 creatureSimulationLOD_MinDistanceMed`，float32标量 | 75 |
| 其他六份选定变体 | parent指向AD56080C；两项LOD不直接出现 | 直接缺失，不能填0 |

父资源Game：文件偏移12641977，存储2412字节、解压3808字节；Patch：偏移13758115，存储2413、解压3808。原始PROP各249属性，本轮只导出选定20个名字的匹配值和阴性清单。两项LOD值相同不代表整个PROP相同，解压摘要仍有差异。

全包摘要再次与既有身份匹配：Game `9d085118c649d211a86723d363592fd66ad655fd24497289b3eab96bb07db329`；Patch `cadbff237076b441e6981503f80538705aefa5863bb4c8d1b869f9db98d1adff`。各选定资源的存储/解压摘要也与26记录匹配。[局部值与阴性范围](evidence/local-selected-creature-lod-properties.json)、[本轮读取器](checks/read_selected_creature_lod_properties.py)。EXE身份复用00，本轮没有重新读取原生指令。

`modelLODDistances`、模型档位键、`useHighAnimLOD`、Anim侧max/cutoff等在这8份PROP中均没有直接出现。**这只是选定查询的阴性结果，不证明原作未启用它们。** 全局/父级/其他资源、读取默认值与本机装载顺序未恢复。没有把三个子变体或Patch自动宣布为运行中有效值。

已回答：模型/动画/模拟有不同表示入口；指定资源中的SimulationLOD两项直接值。部分回答：距离/容量候选。未回答：原作调度、更新周期、实际降成本、群体聚合和公平性保证。下一处证据应是两项属性的本机消费者，以及动画LOD max/cutoff载入与更新循环，而不是继续凭名字补频率。

## 自研分层与所有权

以下频率、阈值、成本、调度、事件和缓存政策全部自行定义，不是原作参数。

```text
ActorAuthority {
    actorId, bodyGeneration, capabilities, damageState,
    actionTimeline, nextAvailableTickByAbility, committedEventIds,
    movement/support/contactState, projectilesOwnedElsewhere
}
PopulationSchedule {
    fixedTick, stableActorIds,
    interactionImportance, plannerPeriod, plannerDeadline, pendingUrgentReasons
}
VisualPolicy {
    meshQuality, posePeriod, visualEpoch, cameraDistance,
    currentPoseSampleTick, asyncPoseTickets, lodHysteresis
}
VisualPoseTicket { actorId, bodyGeneration, visualEpoch, quality, sampleTick }
GroupSummary { speciesId, actorIds, revision, counts, sharedIntent, summaryTick }
```

权威身体保持完整能力/部件身份；低模/骨合并仅属于显示映射。群体摘要按实际actorId计数，不能远处卸载显示后就减少物种数量；相反也不能每次走近重新生成同一群体的随机个体、重复增加数量。事件与出生/死亡归自己的权威生命周期，摘要是派生视图。

模拟重要性看真实交互：战斗、受击、投射物、玩家可能接触、社交/拿物、支撑危险。视觉重要性主要看屏幕/距离；摄像机转开不能让敌人攻击冷却缩短，也不能令不可见投射物消失。两种重要性只在构造算例里恰好使用同一组数量，不要求生产始终绑定。

## 自研算法一：权威事件不挂在AI或显示更新上

本规格以60Hz固定tick维护动作时间线、冷却、已提交效果与交互碰撞。`nextAvailableTick`是绝对截止tick，不是“每次Think减一点cooldown”。1Hz规划器只少做重新选技能/目标的工作，不改变同一技能的时间和伤害。

```text
AdvanceOwnAuthority(oldTick, newTick):
    require monotonic ticks and bounded catchup work
    for tick in (oldTick, newTick] in order:
        consume body/target revision changes and urgent interaction events
        advance movement/support under its real contact contract
        advance active action timelines and all due effect ordinals
        validate uncommitted executor/target references at each actual event tick
        commit each effect identity at most once
        advance already spawned projectiles/effects under their own identities
        publish authoritative state for planners and visuals
```

真实碰撞和命中需要当前权威轨迹/身体姿态，不能拿低频显示骨骼的位置猜伤害。对正在攻击、受击或接触的角色，必要的碰撞姿态求解属于受保护的权威工作；仅显示用IK可降频。31的支撑与落地事件同样不能因为显示脚没更新而直接丢失。

远处不交互角色可以采用自有廉价运动/身体代理和群体摘要，但与实际人物交互前必须重建有效详细状态并通过接触验收。代理不能声称提供了全部六足精确姿态；升级失败就保留明确限制移动/交互原因。NPC AI是否较慢会影响反应，不能将这种差异伪装成纯视觉LOD。

当远景NPC进入战斗或收到有效威胁，规划周期提升到同类战斗统一的最多6 tick，并立即排入紧急任务；敌方/友方采用相同规则。普通远景漫游可1Hz，新攻击不能回填到上次Think时刻补伤害。先在当前权威tick创建动作，再使用自己的合法前摇/冷却。

断肢使尚未提交、依赖该肢体的动作事件失效；已提交伤害不撤回，已发射投射物按自己的身份继续。只对未提交近战执行者做身体generation校验，不能用新身体版本取消世界里已经飞出的效果。

## 自研算法二：分散tick与预算

整数period表示多少权威tick执行一次：`tick % period == stableScheduleSlot % period`。slot保存在actor生命周期，不用进程随机hash；新演员可按负载选择slot并保持。改变频率时保存下一deadline或显式安排新slot，不能重置动作时钟。测试用actorId取模作可复现简化。

```text
ScheduleOwnFrame(tick, measuredBudget):
    required = due authority and critical combat/contact pose jobs
    required += urgent/interaction planner jobs with common reaction deadlines
    execute required jobs in deadline/actorId order
    if required work exceeds reserve:
        report MandatoryBudgetExceeded with cost, actors and overdue duration
    optional = ordinary planning, visual pose, background summaries and bakes
    sort optional by deadline, accumulated age, stable actorId
    admit only jobs whose declared estimated cost fits remaining budget
    retain due planning deadlines and age, record deferred visual samples
    update observed costs and reject invalid estimates explicitly
```

权威预算与可选视觉/规划预算分开。关键战斗任务不能靠“剩下的钱不够就丢弃”处理；必要工作过载先取消/降低可选视觉，再限制背景编译/新群体激活。仍无法完成则报告模拟积压，按统一时间策略补固定tick或让全局模拟变慢；不能只让某个低档敌人漏扣血。

过期的非战斗规划可延后，但不能无限饿死：保存deadline与延期年龄，超上限记录PlannerDeadlineMiss并提高优先级。示例admit只验证预算与关键优先级，没有实现完整年龄调度/群体准入；生产还须测最长等待和紧急突发容量。

时间跳过较多tick时，逐步处理期间所有权威事件；超过catchup预算保留未消费时间和原因，分后续批次补算。暂停时世界tick不推进；视角/显示掉帧不能把动作时间重新从0开始。

## 自研算法三：视觉LOD滞回、升级与异步结果

自研视觉距离单位米、参考摄像机，仅用于算例。High离开阈值30，Medium回High阈值25；Medium离开至Low阈值80，Low回Medium阈值70。等于阈值保持原档；大幅跨越允许直接切High/Low。这组参数属于自己的视觉政策，与原作未定单位的SimulationLOD=75/100分别管理。

每次实际档位变化递增visualEpoch，身体修改另递增bodyGeneration。姿态sample带这两个版本及采样tick；High→Low→High后，最早High结果即使quality相同也不再拥有发布资格。

```text
ChangeOwnVisualQuality(actor, newQuality, nowTick):
    increment visualEpoch without changing authority capabilities/cooldowns
    choose current-generation own mesh/bone/profile mapping for new quality
    derive current action time and gait phase from authority, not old render sample
    invalidate incompatible async tickets
    evaluate first current pose; validate contact/mount/skin mappings
    blend cosmetic display transition if allowed by current contact ownership

OnOwnAsyncPose(ticket, pose):
    require actorId, bodyGeneration, visualEpoch and quality still match
    reject future samples or samples older than last published tick
    validate finite transforms and exact palette/bind dependencies
    publish visual sample only; never emit action damage events here
    retire stale/duplicate resources under44 ownership rules
```

步态phase来自连续权威周期，例如1Hz、tick18时phase=18/60=0.3。升级显示从0.3开始，不重播离地/落地或攻击关键事件。锁脚和接触不应在视觉blend中被移走；必要接触姿态由权威求解提供约束，普通耳尾等装饰可平滑。骨合并重建必须有稳定ID映射，不能低档骨索引直接塞入高档palette。

## 自研完整算例：100个六足NPC

构造100个NPC，每只六足、四手。20个近景且当前可能交互，30个中景非战斗，50个远景漫游。权威事件/冷却均60Hz维护；这并不宣称所有ActorAuthority工作同价或全身IK都每tick运行。先假定这组负载的权威保留预算已测得够用，下表只算另外的可选pose与规划成本。

| 组 | 数量 | 显示pose频率 | pose工作单位/次 | 常规AI规划频率 | AI工作单位/次 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 近 | 20 | 60Hz | 6 | 10Hz | 4 |
| 中 | 30 | 20Hz | 3 | 4Hz | 4 |
| 远 | 50 | 5Hz | 1 | 1Hz | 4 |

这些单位是构造估算，不是毫秒或原作CPU成本；只降低pose更新不自动降低GPU绘制频率。34的顶点/影响数与每帧多pass仍另外计算。

**1. 正常分配。** 每秒pose调用`20×60+30×20+50×5=2050`；规划`20×10+30×4+50×1=370`。pose单位`20×60×6+30×20×3+50×5×1=9250`，规划1480，总10730单位/秒。分散tick在脚本枚举60 tick后，峰值182单位/帧、最多35次pose/帧；190单位预算可完整容纳。不能把不同tick各层最大值简单相加冒称实测峰值。

**2. 远景NPC开始攻击。** NPC51之前按1Hz漫游规划，收到真实攻击/威胁时立即进入战斗重要性，规划周期最多6 tick；视觉仍可Low，因为摄像机不一定看到它。动作A在tick0已合法开始，前摇事件tick12造成7伤害，冷却截止tick60。即使没有在tick12做Think或显示pose，也须在权威tick12结算；tick30冷却未到、tick60就绪。不能等到下一次远景Think再补发攻击，也不能因显示升级重扣7。

**3. 升级画面。** 摄像机走近，在tick18将NPC51 Low→High，visualEpoch4→5；步态phase0.3，动作A的时间也是0.3 s。当前7伤害已在tick12提交，显示重新取当前姿态不发事件。随后High→Low→High到epoch7，旧epoch5的High结果也拒绝；tick10迟到pose不能覆盖已发布tick17。

**4. 断肢。** tick10先删H1时，未来tick12依赖H1的未提交近战事件被拒绝，记录StaleExecutorEvent；冷却与已提交效果按身体/技能契约保留，不由视觉LOD清零。若A在更早时间已发射一个投射物，投射物后续命中由自己的身份处理，不因H1删除而消失。

**5. 帧预算突发。** 两个受保护任务各12单位、预算20时，先处理24单位并记录MandatoryBudgetExceeded；一个1单位可选pose延期。真实帧时间可能因此增加，所以要记录积压并减少背景工作，不能宣称预算20仍满足实时帧率。更大同屏数量需重新测权威与紧急容量，不能用这个100例保证任意数量。

**6. 时间跳。** 从tick0补到30，事件12和20各处理一次，与逐tick推进结果一致；120 tick的catchup预算遇到180 tick请求返回CatchupBudgetExceeded，lastConsumedTick仍0，保留待处理180，不默默跳到180遗漏伤害。随后分批补算，再生成当前显示样本。

群体摘要可另用1Hz等自有周期管理意图/漫游统计，但死亡/出生/关系变化事件先写权威索引，再更新摘要；100个真实actor不因5Hz显示变成“只模拟5只”。在生物实际可交互范围内不采用概率战斗替代逐事件结算，除非产品另有明确且公平的远区模拟契约；本模块未定义这种替代规则。

## 验证、未做与风险

[独立检查](checks/verify_creature_lod_examples.py)24项通过：20项调度/时间/状态检查，4项登记与PROP读取检查；含LOD滞回、分散工作量、峰值、预算过载、phase、事件连续/去重、冷却、断肢与已提交投射物、catchup拒绝、身体/epoch失效和旧sample拒绝。真实局部证据检查8份选定键与100/75原值；读包同时核对完整包及所选资源摘要。详情见[验证记录](evidence/creature-lod-verification.json)。

未做：原作运行/调度观察、函数交叉引用、新动画/网格资产导出、GPU/CPU测时、完整100 NPC三维仿真、生产调度/联网/并发实现；静态授权与REA提供者缺口沿用00，没有安装或改配置。没有执行仓库全量构建，因为交付是研究文档和独立算例。

风险：原作75/100的实际作用和单位仍未知；显示/模拟降级若混用会破坏公平性；权威碰撞/支撑不能凭低频pose近似保证；任务成本需目标硬件测量，稳定排序不自动解决长期饥饿，突发负载也不保证固定帧率。这里只把这些边界和失败信号写明，没有恢复原作100生物调度算法。
