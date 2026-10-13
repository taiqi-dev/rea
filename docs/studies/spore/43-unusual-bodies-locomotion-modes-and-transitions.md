# 43 特殊身体的移动模式与转换

[目录](README.md) · [步态](04-gait-synthesis-and-foot-targets.md) · [移动](26-land-approach-stopping-avoidance-and-gait.md) · [地形与支撑](31-terrain-contact-foot-locking-and-support.md) · [编辑重建](44-editor-rebuild-undo-and-animation-cache-consistency.md)。范围为登陆后、部落前的生物与编辑器。

这次把长短腿、分叉腿、奇怪安装足、无足、急停转身连接到一个完整模式控制器。**原作确认无足启发式和腿长分组；支撑资格、状态转换及失败政策仍采用我们的独立算法。** 无足时的画面漂浮不自动等于飞行技能或脱离地面寻路。

## 原作已回答与未回答

开发团队论文§4.2把腿定义为从脊柱髋节点到末端foot的骨链，长度近似分组，并用小有理数协调组周期。不同组可同时用不同步态；没有脚时，启发式选择漂浮或爬行，爬行把部分脊柱节点用作pseudo-feet并生成类似尺蠖的步态。[动画论文，PDF第6–7页](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

论文§4.1.1另有HasFeet、HasGraspers、UprightSpine等动作绑定分支。**动作能绑定与足是否真的能支撑并非同一判定。** 原作无足选择阈值、pseudo-feet分配、共用骨段协调、转换相位和停步策略没有恢复。历史设计也没有证明本机所有无足身体都遵循同一表现。

本轮完整复核论文第6、7页，摘要仍为`f64be1b504845f715e2ab440e1653d1c487bf16d51b478eab1c913162fbc3d82`。SDK固定声明`EditorModel.h`第90行有`mMinimumLeglessCreatureHeight`，只能说明编辑表示含无腿高度字段，不是无足运动阈值。读取范围和摘要见[公开来源记录](evidence/public-locomotion-rebuild-contracts.json)。

复用26的Game/Patch各gait0–6资源与固定FX读取规则，本轮未读取新GAIT资源。gait0存在不自动证明运行无足时一定选gait0，更不能把它填成尺蠖完整算法。04、05、31的数学公式仍是自研规格。

| 问题 | 原作当前答案 | 下一证据入口 |
| --- | --- | --- |
| 多脚且长短不同 | 分组、小有理数协调、组可有不同风格 | 组长度/阈值/频率计算消费者 |
| 分叉骨链 | 公开图示支持这类结构，foot到hip的路径参与分组 | 共享骨段协调和末端资格 |
| 无足如何移动 | 漂浮/爬行启发式、脊柱pseudo-feet | 选择启发式和pseudo-foot生成调用 |
| 朝上/侧装足能否落地 | 不能仅从foot标签回答 | 参考方向、限位与地面目标实际绑定 |
| 停止、转身、换模式 | 公开设计追求与根运动匹配 | 原作事件与转换状态机 |

## 自研表示：拥有脚不等于拥有可用支撑

以下类型、公式、阈值、控制器和算例全部是我们自己的规格。

```text
LocomotionDefinition {
    allowedModes: Legged|Crawl|Hover,
    footContactProfiles, ownCrawlContactPatches,
    rootHeightRange, jointLimits, ownTransitionProfiles
}
SupportCandidate {
    stableContactId, partId, bonePath, referenceLength,
    soleFrame, legalOrientationRange, contactRegion,
    modeEligibility, rejectionReason
}
LocomotionState {
    bodyGeneration, mode: Legged|Crawl|Hover|Disabled,
    transition: None|Preparing|Settling|Activating|Failed,
    sharedClock, activeFootContacts, virtualBodyContacts,
    actualRootPose, rootVelocity, diagnostics
}
```

肉体决定候选与可用模式；灵魂决定速度、方向、谨慎程度和希望采用的合法风格。灵魂不能给没有Hover支持的肉体凭空增加悬浮功能。编辑器展示可用的可视预览模式，与局内允许模式是两个配置；原作画面漂浮不能替用户游戏作能力定义。

对足逐项检查：稳定ID和当前造型版本，foot→hip完整骨链，自有资产是否允许承重，法线/脚底范围能否在关节限位内转到接触面，当前落点是否可达，是否被攻击或其他动作占用。侧装足不因标签就参加支撑；允许扭转的自有足可以求解后再参加。排除只影响该实例，不删除同款其他脚。

几条足路径共用一段骨时，在身体图标记共享节点；不能各腿独立写同一节点。31的联合支撑和28的动作所有权处理共享路径。一条分叉末端失去接触不等于共用根段消失，也不等于所有另一分支一起失效。

## 自研算法一：分类后再分组

```text
ClassifyOwnLocomotion(body, terrain):
    candidates = EnumerateDeclaredFootAndBodyPatchInstances(body)
    for c in candidates:
        validate stable IDs, current shape, chain, finite positive lengths
        find feasible contact orientations within own joint/sole limits
        probe and validate support patches and reach, retaining rejection reason
    feet = currently usable real feet
    if feet can form valid support for an allowed Legged controller:
        return Prepare(Legged, GroupEligiblePathsByReferenceLength(feet))
    if ownCrawlProfile exists and body patches can establish valid contact:
        return Prepare(Crawl, bodyPatchContacts)
    if ownHoverProfile is explicitly allowed and world clearance permits it:
        return Prepare(Hover)
    return Disabled(NoSupportedLocomotion, all rejection reasons)
```

“可用足数量大于0”只是一道候选检查，不能代替有效支撑/动力学判定。代码检查脚本的简化模式选择只验证有无候选和显式模式授权；完整模式激活还必须通过31的支撑验收。两足、单足、跳跃需要自己的动态运动契约，不能沿用慢速静态多足凸包规则就宣布合法。

自研分组延用04：按长度排序，组内最长/最短≤1.25；代表长取中位数，以最长组为1Hz基准，从{0.5,1,2}选最接近期望`longest/groupLength`的比率。原作准确候选集合与阈值未知。长度是参考路径总长，不是弯曲后的端点弦长；粗腿不自动获得更大的步长。

## 自研算法二：长短腿和不合理参考姿态

31的球壳近似求身体高度可行交集。短腿上界可能令全身不能抬得很高；例如腿长0.6 m、水平足距0.3 m、足高0且髋偏移0，上界是`sqrt(.6²-.3²)=.519615 m`。肚子离地下界0.55 m时交集为空，须重新落脚、调整倾角或进入另一个已允许模式，不能暗中加长腿。

弯曲参考姿态提供弯法和目标偏好，不是最终关节角硬锁。链目标失败区分`NoReachableLanding`、`SoleOrientationInfeasible`、`BodyHeightIntersectionEmpty`、`SharedChainConflict`。极短腿可以作为非承重动画附件，但能力与显示标明该实例不参与当前支撑；无可用足时重走模式选择，不把未知转换伪装成自然站立。

```text
UpdateOwnLeggedMode(actualMotion, now):
    refresh still-valid world/surface anchors
    speedForGait = measured root translation and rotational hip speed
    propose lift events from shared clock and group ratios
    validate remaining support before releasing each anchor
    plan reachable and sweep-checked landing
    solve body height/tilt and all shared-chain foot goals
    report contact and pose residuals; restrict root motion if infeasible
```

原地转身也有足目标变化：髋速度`v_i=v_root+omega×r_i`。根平移为0、ω=1 rad/s，髋半径0.4 m时贡献0.4 m/s；变宽到0.7 m时为0.7 m/s。这不是给每脚各自独立时钟的理由，组仍共享连续相位。

## 自研算法三：无足爬行与悬浮

**Crawl：**自有资产声明身体接触patch及允许的形变范围。虚拟接触ID由`(partId,patchId)`组成，绑定脊柱/皮肤上的实际区域。它不是新增了一件脚部资产，也不因此增加Foot能力等级。可采用三个身体接触区的交替贴地/抬起方案：保持前后承重区域时，中段拱起；前段移动到新点并确认接触，再让后段跟进。每次解算骨长、肚子离地、自碰撞与有效支撑，不把整条身体同时悬起。

```text
AdvanceOwnCrawl(state, now):
    contact = declared phase's moving patch
    if remaining support invalid: hold phase, diagnose CrawlSupportUnsafe
    target = ownProfile(currentShape, actualRootRequest, phase)
    validate target reach, deformation limits and surface sweep
    move only the owned contact and its permitted body DOFs
    when phase completes, confirm real contact before advancing phase
```

这是自研接触式爬行控制器，未恢复原作尺蠖的波形、推进规则和点选择。贴地体型可能用蛇形或其他自有profile，但每种必须声明接触与根运动约束，不能所有无脚生物硬套一条波。

**Hover：**只有肉体明确允许时使用：平面路径移动由26负责，参考根高度由地面高度加自己设置的离地偏移计算，再检查整个身体净空。视觉上下浮动可叠加，但不自动把命中代理、技能距离或移动路径改成飞行。地面丢失/上方空间不足需要明确拒绝或另一个真实飞行契约；本模块没有定义空中自由寻路。

## 自研算法四：停步与模式转换

停步先禁止新的常规迈步事件；正在摆动的足以独立动作时间继续落地，不能把步态频率置0后冻结在空中。落点失败时进入NoContact并反馈，不能仅到达预定时间就宣称Stance。需要额外调整支撑时可启动明确Settling动作，它不是偷偷重开走路周期。

```text
RequestOwnModeTransition(newMode, current):
    capture current root pose, velocities, contact IDs and action owners
    validate new mode is allowed by current body generation
    enter Preparing; constrain root movement while building new contacts
    finish or safely settle old airborne contacts
    preserve compatible retained anchors; invalidate incompatible ones explicitly
    activate new controller only after its own contact/clearance contract passes
    publish one mode owner; retire old controller without duplicate root updates
    if preparation fails: keep previous valid mode or Disabled with reason
```

转换开始不瞬间跳根位置，也不把旧模式当前偏移当新参考姿态。两模式短暂过渡必须通过同一个根运动/接触协调器；不能让Legged与Crawl各推进身体一次。编辑删除全部足时，旧足无法“完成落地”，立即失效；编辑器可暂停预览并编译新身体，局内断足按身体变更/跌落处理，不能把缺失的足当兼容锚点。

## 自研贯通例：六足变胖、停转、撤销与无足

这与44沿用同一组配方变化，全部数值为构造参数。

1. 配方A有F1–F4四条0.9 m长腿、F5/F6两条0.6 m短腿，均可接地。得到两组，长组比率1、短组比率2；同一身体允许Legged、Crawl，未允许Hover。短腿水平距0.3 m，肚子最低要求0.45 m，根高度0.50 m处于可行区间。
2. 编辑加宽成为B，肚子最低要求0.55 m。旧短腿落点不再可行；把短腿水平距离改到0.2 m，上界`sqrt(.6²-.2²)=.565685 m`，0.56 m才通过近似高度验收，仍须核对其他长腿、限位和真实支撑。未求出合法新落点时暂停根推进。
3. B中原地转身ω=1 rad/s、髋半径0.7 m，髋速度贡献0.7 m/s。停步时F6尚在Swing、落地截止时间0.25 s；当前0.20 s保持Swing，0.25 s接触验证通过才转Stance。若未命中地面则NoContact，不从相位推定落地。
4. 侧装F5若法线朝水平、自己的关节契约不能旋到可支撑范围，则排除F5并重评其余足。反向弯曲只改参考弯法，不改变0.6 m骨链长度。不允许为恢复六足动画随意生成一只虚构脚。
5. 在编辑器替换/删足得到C，无合法足但仍有自己的三个身体接触patch，编译后准备Crawl。旧F1–F6锚点全部失效，根位置先保留，待新身体patch接触和净空确认才开始爬行。另一种既无足又无爬行/悬浮授权的身体返回Disabled，不静默漂浮。
6. 撤销回到A的配方内容时，44产生新的generation，重新建立脚绑定与接触；不能恢复最早A的世界足锚点，因为当前根/地面可能已改变。若地面与身体身份、接触版本确实都兼容，才通过显式迁移保留，否则重新落脚。

## 检查、未做与风险

[独立检查](checks/verify_locomotion_rebuild_examples.py)的9项移动检查核对长度分组/阈值、频率比、短腿高度、侧装足候选、无足模式授权、停步落地/失败、转身速度和转换发布时保持根/兼容锚点。后者只验证状态传递，不证明完整转换支撑已建立。实际结果见[验证记录](evidence/locomotion-rebuild-verification.json)。

原作部分回答：腿/组/无足机制、动作绑定分支。未回答：浮/爬选择条件、原作特殊足资格、短腿分组常数、共用骨段与转换实现。未做：新本机资源读取、游戏运行、私人配方、完整3D爬行/六足IK和物理验证；静态授权与提供者缺口沿用00。

风险：长度包络与静态支撑不是完整动力学；复杂分叉、侧足、地面消失和模式转换可能无合法解。真实产品需用自己的极端身体集验证，不能以9项数学/状态检查保证任意拼装都可移动。
