# 57 编辑器动画预览与肉体功能验证

[目录](README.md) · [编辑重建](44-editor-rebuild-undo-and-animation-cache-consistency.md) · [吸附](49-editor-surface-snapping-attachment-and-connection-validation.md) · [多器官注意](52-gaze-head-orientation-and-multi-organ-attention.md) · [子树编辑](58-limb-subtree-copy-replacement-and-reparenting.md)。只涉及陆地Creature编辑与登陆后、部落前的生物。

这次补到了原作Test Drive的明确操作说明，以及编辑事件→动作配置的局部资源链。**原作能够预览动作与行走；没有证明它会输出攻击可达、支撑安全或技能冲突测试报告。** 功能验证报告是为自己的拼装游戏独立设计的扩展。

## 原作行为与公开入口

官方手册PDF第14页、印刷22–23页说明：Test Drive里单击地点行走、双击奔跑；动作面板提供动作、舞蹈、反应和情绪；幼体可以模仿动作。它支持实际公开交互说明，不需要从SetTargetPosition名字猜出完整试走。[官方手册](https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/17390/manuals/manual.pdf?t=1642702281)

本轮完整复核手册第10、11、14页文本，SHA256与既有记录相同：`9a1cd765673454b3fbdf0edf2026b853b3354a4fa6ef144076b10eb508bdae1d`。首次宽输出发生截断，随后只重读相关完整页；图示未视觉核验，其他阶段不用于结论。

固定SDK提交`2d71289adc71aa5c58f4516c6c835c99f5f9ca19`补充下列表示，来源/摘要/实际行范围见[公共契约](evidence/public-editor-preview-subtree-contracts.json)。

| 公开位置 | 可确认表示 | 未确认 |
| --- | --- | --- |
| Editor.h 79–83、203–205 | Build/Paint/Play枚举；返回中性姿态的事件注释 | 本机模式转换、绑定/取消顺序 |
| cEditorAnimWorld.h 20–37 | 编辑动画实例、控制器、目标位置/角度、模型世界 | 当前身体更新怎样替换预览实例 |
| EditorCreatureController.h 20–33、42–59 | 当前动画ID、目标/当前位置与角度、移动/转向/LookAt字段 | 真实动作选取、dt单位和运动算法 |
| PlayModeActor.h 13–44 | WalkAction、创建/添加行走动作、控制器与队列 | 可达性、避让/支撑与中断算法 |
| EditorPlayMode.h 44–81 | 鼠标/UI、Load/Dispose、主actor、modules/UI/动画/背景 | 四个module具体职责及攻击/社交玩法执行 |
| PlayModeAnimations.h 40–54 | 动画播放、读面板/按钮配置的接口和组注释 | 实际按钮可用性、选哪只肢体和伤害 |

这些是社区声明，未确认本机ABI。`Editor.cpp`的中性姿态方法只是auto_METHOD包装，没有恢复原作事件发送函数体。`cEditorAnimEvent`的消息类型`0xD1511790`与具体事件ID不同；不能把两者合并。

## 本机：选定预览配置的事件和动画引用

沿声明的三个组，只读取Game/Patch的DBPF索引：editorAnims组`0x40606300`两包各105份PROP，名称中也含Cell资源，未解码它们；面板/按钮候选组`0x4060E000/0x4060E100`在这两包索引未命中，不证明所有包里不存在。

仅解码明确选择的五个Creature名字，两包共10份PROP。固定FX注册表按实际属性ID补到animID、animRespondsToEvent、animName等名称，记录见[本机局部值](evidence/local-selected-editor-preview-properties.json)。

| 所选名字 | animID原值 | 响应event原值 | animName原值 |
| --- | --- | --- | --- |
| creature_button_attack_1 | `0xF14FAA37` | `0xEE3ED216` | `_final/creature/com_bite` |
| creature_button_attack_2 | `0x02A12F13` | `0xEE3ED216` | `_final/creature/com_headbutt` |
| creature_button_dance_1 | `0x044F475B` | `0xE5025CD9` | `_final/csa/csa_baby_dance_01` |
| creature_idle | `0x04373C4F` | `0x29FB4130` | 未直接出现 |
| creature_rest_pose | `0x04372FC9` | `0x6581B78E` | 未直接出现 |

Game/Patch这些选定字段相同；并没有因此宣布实际载入包顺序。idle/rest的animTriggerOnBlock、animRequiredBlocks是直接空key数组，不能当成最终绑定条件全部为空。event数组里的type/group为0，保留原样，不伪造它们指向某个ANIM资源。

具体例子：SDK的SetCreatureToNeutralPose注释写事件`0x6581B78E`，真实rest配置的animRespondsToEvent含同值、animID为`0x04372FC9`。这是可交叉核对的静态关联，原生分发和实际播放仍未知。两个attack资源响应相同事件也不证明它们同时攻击，更不证明伤害结算两次。dance名字明确含baby，不能直接当成陆地社交比赛的完整流程。

包完整摘要与既有身份匹配；读取器只导出局部配置值和摘要，没有取出动画/模型主体。[读取器](checks/read_selected_editor_preview_properties.py)。本轮没有操作游戏Test Drive或读取玩家存档。

## 自研：预览实例和功能结果各自拥有版本

以下结构、算法、阈值和例子全部自研。

```text
PreviewInput {
    bodyInstanceId, generation, recipeAndBundleDigest,
    partCatalogVersion, solverVersion, collisionProfileVersion
}
PreviewSandbox {
    sandboxId, input, runEpoch, ownedWorld/actors/dummyTargets,
    clock, seededInputs, selectedMode, actionReservations, ownedDevices
}
FunctionalSuite {
    suiteId, suiteVersion, requiredCases, fixturesDigest,
    fixedDt, randomSeed, thresholds, acceptedKernelVersion
}
FunctionalResult {
    runId, input, suiteDigest, status: Pass|Fail|Inconclusive,
    executedCases, executorPartIds, observedMeasurements,
    failures, deferredCases, sampleTickRange
}
```

当前配方、编译包、能力、骨/局部profile映射与接触代理必须同版本。旧完整模型可以继续展示，但不能将旧generation43的测试当generation44结果；即使撤销后内容相同，运行版本仍不同。功能报告覆盖配置指纹与求解器版本，不只保存一个“通过”布尔。

sandbox使用自己产品的动作/姿态/命中内核和独立场景，目标是可验证内核行为，不另写一套仅为好看的动画替代真实动作。没有运行适配器、关键测量缺失或只播放动画时，状态为Inconclusive，不宣布功能合格。工具本身的生命周期有Loading/Ready/Running/Stopping/Disposed/CleanupFailedOwned，详见44所有权。

## 自研算法一：创建与绑定

```text
CreateOwnPreview(editor, suite):
    snapshot = immutable current recipe and completed bundle
    reject missing/current-generation mismatch or incomplete dependency manifest
    create owned sandbox world with its own clock and deterministic seed
    instantiate body and optional test soul under sandbox identities
    create fake ground, attack dummy and social actor from own assets
    bind requested executor/helper/profile IDs against this exact body
    route dummy damage to sandbox metrics; disallow world rewards/persistence
    return Ready sandbox or explicit construction failure with retained cleanup owners
```

不共用真实肉体的HP、冷却、受伤、灵魂记忆、世界关系或奖励账本。预览内可以重置假目标与假冷却重跑，但真实技能冷却不随点击预览改变。攻击结果仅更新dummy与报告；预览社交只向假伙伴记录时序/动作匹配，不提高真实种族关系。

Effect接口校验sandboxId与目标realm，世界目标/奖励事件直接拒绝；不能仅靠显示一个“测试场景”标题保障隔离。产生模型、声音、输入捕获等设备由session拥有；不停止别的编辑器或全局设备，异步结果携带runEpoch，退出后不能继续操作已释放actor。

## 自研算法二：哪些功能必须实际测量

| 自研用例 | 输入与执行 | 输出和判定 |
| --- | --- | --- |
| 攻击可达 | 指定技能、稳定执行手ID、目标表面及站位；驱动真实动作/命中窗口 | 可达残差、遮挡、自碰撞、命中次数；骨链总长只作初筛 |
| 行走/停转 | 固定轨迹、加减速/转向、坡与台阶fixture | root误差、最大滑脚、支撑/落脚失败、骨长误差 |
| 多技能共用输出 | 手H2攻击、H3护盾；声明各自必需肩/脊柱/局部输出 | 全量预约和约束冲突原因，不能仅各动画都播放就判成功 |
| 局部嘴/手形变 | 多个造型值与Open/Grip动作，结束回中性 | 参考保留、接缝残差、重复变形、当前部件版本 |
| 社交表演 | 假伙伴提出动作、指定参与器官、统一时间窗口 | 展示/配合时序与动作选择；能力评分规则由自有玩法定义 |

每个用例先验证执行者/目标/fixture合法性，再记录实际执行的阶段。碰撞/支撑关键项必须由运行适配器产生数值；未执行不能写0，读到NaN不能变成Pass，缺profile不能自动换另一只手继续测。

```text
RunOwnFunctionalCase(session, case):
    require current input key and active runEpoch
    reset sandbox-owned dynamic state from the declared fixture
    resolve exact executor/helpers and reserve outputs/resources atomically
    for each fixed tick within declared case duration:
        feed seeded scripted intent into own authoritative kernel
        sample actual root, contacts, pose residuals and effect ordinals
        accumulate maxima and timestamped failures
    if any required adapter/measurement absent: return Inconclusive
    compare actual metrics against this suite's explicit thresholds
    return reproducible Pass/Fail with inputs, traces and reasons
```

控制与画面预览、几何初筛和实际动作验收可在UI分别显示。静态两骨链够长不证明动态碰撞、关节限位或共享躯干能满足；57检查脚本只提供包络/状态演算，不是一份全三维功能运行适配器。

## 自研算法三：结果接纳与退出

```text
AcceptOwnFunctionalResult(result, editor):
    require run ownership, input generation/digest and suite/kernel versions match
    require all mandatory cases executed and all required measurements present/finite
    reject contradicting Pass labels and measured failures
    if mandatory failures exist: show Fail and implicated parts/constraints
    if coverage incomplete: show Inconclusive with missing adapter/cases
    accept current design only under the product's stated completion policy

StopOwnPreview(session):
    advance epoch and reject subsequent callbacks before freeing actors
    stop owned actions/audio/input captures and retire only owned world/actors/jobs
    on cleanup failure retain resource identity and CleanupFailedOwned for retry
    keep recipe/history unchanged; do not save final animation pose as reference
```

完成编辑是否强制某套功能用例是产品规则，不能所有艺术型身体都要求具有攻击能力。这里的战斗型示例明确要求Reach/Support/SharedOutput；未提供技能的身体可以选择另一套完成政策，但不能缺测后照样显示该战斗suite通过。

## 自研贯通例：四手六足编辑→功能结果→接受

四手H1–H4、六足F1–F6，generation42为身体A，宽半径0.4 m。编辑加宽生成43/B，宽半径0.7 m。以下都是自研构造输入与数学/状态演算。

1. 当前B尚在编译时，点击试走不得绑定旧42/A并宣称测试B。返回StalePreviewBody或CurrentBundlePending；等B的骨/皮肤/能力/profile/接触完整一致后才创建sandbox。
2. 选择H2攻击假目标，链总长1 m、目标到肩0.8 m，初筛通过。H1已被测试护盾占用，不自动改绑它。完整运行还须测H2实际命中窗口和碰撞，初筛报告不直接充当真实命中证明。
3. 两短腿长0.6 m、落点水平距髋0.3 m，近似身体高度上界0.519615 m；B肚子最低要求0.55 m，Support包络失败。报告指向相关短腿/体型，不能通过拉伸骨骼隐去失败。
4. 自有落点调整至水平距0.2 m，上界0.565685 m，选身体高度0.56 m再次通过包络。ω=1 rad/s、髋半径0.7 m，期望髋转向速度0.7 m/s；正式Turn用例仍需测实际足滑移与支撑变化。
5. H2攻击与H3护盾若各要独占SharedTorso输出，SharedOutput返回冲突；改为先防御再攻击或自己的合法兼容策略后重测，不能仅让两只手各动就判通过。
6. sandbox里假目标一次收到7点测试伤害，重复hit ordinal不重扣；真实目标、奖励和世界关系写入全部拒绝。完成时停止session，清理失败保留actor所有权和原因，不让旧callback写入下次预览。
7. 数学教学suite得到三项Pass及有限残差后，只能接纳该suite覆盖的设计。自己的完整运行suite要额外取得真实命中/接触/滑脚等测量，才能生成完整功能Pass；当前仓库没有该产品运行适配器，因此完整三维结论仍Inconclusive。任何新编辑/Undo产生44，即使内容仍B，43的报告也失效。

## 验证与剩余未知

[检查脚本](checks/verify_editor_preview_subtree_examples.py)中57有14项：旧身体拒绝、假伤害/去重、非有限/负伤害拒绝且不污染事件账本、跨world/奖励拒绝、支撑包络与转向值、共享输出冲突、缺测/失败/旧suite/矛盾数值/重复结果字段拒绝、当前版本结果、退出回调与失败清理，以及10份真实资源字段核对。58另有16项，不与本节重复计数。结果见[专属验证](evidence/editor-preview-subtree-verification.json)。

原作已回答：Test Drive公开操作、预览相关模式/队列/事件字段及10份动作配置。未回答：本机当前身体预览重绑、具体执行肢体、动作事件选项分发、真正攻击/社交逻辑、退出清理与功能报告。未做：游戏运行、私人存档、完整动画/模型提取、生产sandbox和三维功能测试；提供者缺口沿用00。

风险：共享技术/配置与实际陆地编辑选择仍缺调用对齐；自己的包络检查不能替代实际动作/碰撞验证，sandbox隔离也需要真实产品边界测试。没有据预览画面宣称肉体全部可玩。
