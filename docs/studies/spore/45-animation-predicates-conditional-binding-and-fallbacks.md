# 45 动画条件、绑定失败与回退

[目录](README.md) · [同类肢体绑定](39-same-role-effectors-variant-binding-and-default-mixing.md) · [动作事件](40-action-events-emitters-hit-windows-and-stale-callbacks.md) · [特殊身体](43-unusual-bodies-locomotion-modes-and-transitions.md) · [编辑重建](44-editor-rebuild-undo-and-animation-cache-consistency.md)。研究范围是登陆后、部落前的生物动作及其身体绑定。

**这轮确认了三种不同层次：整段动画的条件、通道的绑定要求、事件自己的条件。** 本机既定46份技能ANIM中，整段条件和事件条件都是零值；612条通道有15条置了社区格式所称的`require`位。缺少所需肢体时，原作究竟换另一动画、跳过通道还是拒绝整段，仍未恢复。下文回退规则是为我们的肢体拼装与灵魂系统独立设计的规格。

## 原作证据与搜索边界

调查起始时间为 **2026-10-12 23:19:59 PDT（2026-10-13 06:19:59 UTC）**。重新读取完整EXE及Game/Patch包做SHA256核验，读取两个DBPF索引，实际读取并在内存中解压28已选的46份ANIM；覆盖33个不同资源键，版本21和25。没有扩大到其他ANIM、TLSA或资源包，没有导出动画曲线、模型或纹理。

| 制品 | 完整SHA256 |
| --- | --- |
| `SporeBin/SporeApp.exe` | `f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d` |
| `Data/Spore_Game.package` | `9d085118c649d211a86723d363592fd66ad655fd24497289b3eab96bb07db329` |
| `Data/PatchData.package` | `cadbff237076b441e6981503f80538705aefa5863bb4c8d1b869f9db98d1adff` |

EXE的PE/版本元数据沿用已有身份，没有重新解析。资源存储位置、压缩前后摘要、字段偏移和原字节见[本机条件证据](evidence/local-selected-animation-predicates.json)。这些是普通文件观察，没有REA Evidence ID；此前提供者缺口沿用，不再次安装或诊断。

开发团队论文§4.1.1描述HasFeet、HasGraspers、UprightSpine等身体分支。这项历史设计复用43对PDF第6页的核验，本轮未重新下载论文；它没有给出本机状态生产、判断阈值或失败回退的完整函数。[原开发团队论文](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)，[43来源记录](evidence/public-locomotion-rebuild-contracts.json)。

固定SporeModder-FX提交`a482c51d8d37fc8cf416acecc3c00a5b0723f2e5`的`AnimationPredicate.java`定义两个小端32位字。其文本格式转换把第一字置位的条件写出，把第二字同一位解释为所需布尔值；已命名的位是uprightSpine=1、hasGraspers=2、hasFeet=4。它是社区格式读写代码，**没有执行身体条件的函数**。[AnimationPredicate，第14–64行](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimationPredicate.java#L14)

`SPAnimation`在解压资源偏移`0x154`读取这8字节，非默认值的文本命令叫`branchPredicate`；`AnimationEvent`在每条96字节记录的相对`0x50`读取同一种结构，文本解析器同时设置事件标志`0x01000000`。二者的存储位置与启用方式不能混为一层。[SPAnimation，第87–88、221–224行](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/SPAnimation.java#L87)，[AnimationEvent，第292–314、662–669行](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimationEvent.java#L292)。这证明格式编码，没有证明本机原生消费者对未知位的行为。

通道有自己的主次context与`bindFlags`。社区常量把低位`0x4`命名为`BIND_FLAG_REQUIRE`，解析`require`选项时置位；该类没有独立的`AnimationPredicate`成员。主次context筛选、require、blend/variant分组及事件source筛选分别保存，不能把它们都叫同一个布尔分支。[AnimationChannel，第82–85、219–233、480–496行](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimationChannel.java#L82)，[AnimChannelParser，第48–53行](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimChannelParser.java#L48)。未找到原生绑定失败处理。

固定SDK提交`2d71289adc71aa5c58f4516c6c835c99f5f9ca19`的`AnimatedCreature.h`第51–68行声明Play/LoadAnimation接口：`pChoice`用于输出选择，初值非-1可强制一个choice。该接口没有给出“被条件拒绝后的下一choice”、强制选择是否绕过条件、返回失败值或回退实现。SDK的`SPAnimation.h`及`SourceCode/Anim/Animations.cpp`所读完整55/89行也没有相应条件执行入口。这是限定阴性查询，不能推成整个SDK或游戏没有该函数。[固定SDK接口](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/AnimatedCreature.h#L51)

八个固定公开文件均重新读取完整字节并散列，精确URL、行段和摘要见[公开条件契约](evidence/public-animation-predicate-contracts.json)。没有把社区头文件当作原游戏源代码。

## 本机的实际字段

| 层 | 位置或掩码 | 此批资源观察 | 可推导范围 |
| --- | --- | --- | --- |
| 整段动画 | decoded `0x154`，8字节 | 46份均`00000000 00000000` | 此批没有显式非默认条件；不代表所有动画无分支 |
| 通道要求 | CHAN相对`0xac`，低位`0x4` | 612条中15条置位，均来自所读Patch版本 | 确认位与所在通道；失败后果未知 |
| 事件条件 | event相对`0x50`，8字节 | 818条均零，且启用位均未置 | 此批没有启用的事件身体条件 |
| 事件其他限制 | disabled/chance/archetype原字段 | 原值逐项保存 | 与身体predicate分别读取，不恢复触发规则 |

三个代表都属于`EE17C6AD:00000000:<instance>`，位于PatchData，版本25。下表位置均是**解压ANIM内部偏移**，不能加到压缩数据的包文件位置上。

| instance / 内嵌名提示 | 包文件存储offset / stored / decoded bytes | require通道与decoded偏移 | bindFlags原值 | 主context原值与位置 |
| --- | --- | --- | --- | --- |
| `32183548` / `com_strike_lb_lvl05` | 18855478 / 11693 / 89536 | #6 `R hand`，22680 | `0x01070005` @22852 | flags`0x00800108`，cap bytes`736b7273`（原字面`skrs`）@22820 |
| `9a1bf2ca` / `com_strike_tl_lvl05` | 17225732 / 11766 / 71160 | #9 `tail Wpn`，58152 | `0x0008000d` @58324 | flags`0x00810020`，cap`7374726b`（`strk`）@58292 |
| `d6787152` / `com_strike_hd_lvl01` | 1464969 / 4270 / 31664 | #10 `strike`，29376 | `0x0001000d` @29548 | flags`0x00200000`，cap`strk` @29516 |

这些名字只帮助识别。`skrs`保留文件中的四字节原值，不按名称猜成某能力；`strk`也不能直接等同于最终伤害。`0x00200000`的未解语义保持未知。15条require分别是5条所读lb版本、5条tl版本、5条hd版本；其他597条没有该位。没有据此宣称Game被Patch如何覆盖。

实际事件例子：Patch `32183548`事件#0从decoded85132开始，flags`0x00000060`、ID`0xbf2c63c9`，predicate位未置；predicate位置85212，原8字节全零。Game/Patch喷吐`38ed1075`事件#0分别位于42612/17136，flags都为`0x00000048`，社区disabled位存在，而predicate仍零且未启用。**disabled原位不等于已观察到运行时不触发；整段条件为零也不抹去其他限制。** 原事件消费及伤害边界继续见40。

按社区文本语义，构造`flags1=7, flags2=6`可以表示“检查三个已知条件，upright=false、graspers=true、feet=true”。这是**人工格式演算**，不是这46份里读出的非零样本，更没有证明原作按同一逻辑合取执行。未知位、未选中而第二字置位的情况都由读取器原样记录，不静默抹除。

## 自研结构：肉体、条件与执行计划分开

以下是我们自己的设计。自有条件不必复制原作名称或位段，使用显式类型可避免“mask值未知但仍当成功”。肉体提供结构事实和稳定部件ID，灵魂提供意图与已授权技能；任一灵魂都不能把缺失的执行部件变成有效绑定。

```text
BodyFacts { bodyRevision, structuralTraits, operationalRoles, stablePartIds }
ControllerContext { soulRevision, allowedActions, intent }
AnimationAlternative {
    ownClipId, condition: list<Trait == boolean>,
    channels: list<RoleSelector + Required|Optional>,
    compatibilityProfile, declaredFallbackOrder
}
BindingPlan {
    ownClipId, bodyRevision, soulRevision,
    channelToStablePart, reservedPaths, omittedOptionalChannels, diagnostics
}
ConditionResult = Pass | Fail(reason) | Unknown(reason) | Invalid(reason)
SelectionResult = Ready(plan) | NoCompatibleAnimation(allRejections)
```

结构事实与运行资格有不同生命周期：肉体仍有一只手时`hasGraspers`可以为true，但“右侧可执行抓握者”的候选仍可能为空。断肢、麻痹、被另一动作预约、骨链不完整、当前造型超出可解范围都应影响绑定资格。支撑检查继续由31/43负责；拥有foot标签不能代替接触可达性。灵魂更换时，身体的几何事实可以复用，旧灵魂动作计划的授权与事件不得复用。

候选角色筛选应先检验稳定ID、当前身体版本、部件功能、目标侧/区域、骨链、冲突与求解契约，保留每项拒绝原因。本文小型算例由调用者直接提供已经筛好的角色列表，**不声称它实现了完整IK、预约或32/39的角色筛选器**。有多个同类候选时，此算例用稳定ID排序后取首个，目的是可复现；实际产品可以选择其他明确策略。

## 自研选择与失败回退

```text
PreflightOwnAction(bodySnapshot, soulSnapshot, request, alternatives):
    reject request if soul lacks authorization or body cannot provide action
    compute typed structural facts; unknown/invalid facts retain diagnostics
    for alternative in its own declared order:
        evaluate each explicitly selected boolean requirement
        if any requirement false: reject this alternative with exact mismatch
        if unresolved requirement remains: reject with ConditionUnknown
        stage bindings without changing live pose or emitting events
        for each required channel:
            filter stable part candidates with current body/role/chain constraints
            select candidate with declared deterministic or seeded policy
            if none: reject alternative; discard every staged binding/reservation
        for each optional channel:
            bind if valid; otherwise omit it with reason
            omit events dependent on an omitted channel unless an explicit
            separately validated fallback event source was authored
        validate joint writes, shared chains and resource compatibility
        compare captured body/soul revisions before reservation commit
        if changed: return StalePreflight and rebuild from a fresh snapshot
        commit complete plan atomically; then permit pose/event scheduling
        return Ready(plan)
    return NoCompatibleAnimation(rejected alternatives)
```

零条件只通过“条件门”，不会替代必需通道验证；optional不代表可以把发射点偷偷换成另一只手。命中/发射事件必须绑定到同一份已提交执行计划；视觉资源缺失可以按自有等级降级，决定攻击资格的执行骨链缺失应阻止攻击或选择一个事先写好的合法替代动作。没有合适替代时返回显式失败，可恢复中立姿态，不自动施放别的技能。

播放中身体或灵魂版本变化，先取消尚未提交的动作与事件任务、释放计划拥有的预约、拒绝旧版本回调，再重建绑定。已经提交的世界结果按40的规则保存，不能因换动画就重复扣伤害或回滚其他对象。是否保留动作进度须按自有动作契约明确决定；本文默认重新预检，不能将旧时间直接接进不同clip。

“换动画”不是恢复所有错误的万能入口。条件false通常换预先定义的备选；未知位/不完整资源应诊断并拒绝；required角色为空是绑定失败；资源丢失是资源错误；求解不收敛是约束失败；版本变化是失效。它们拥有不同原因与清理责任，避免无限回退循环。备选只在有限列表中检查一次。

## 贯通算例：有手但没有右手

以下自有clip、ID和修订号都是构造值，不是Spore参数。三份备选依次为：`right-swipe`需要`hasGraspers=true`和`rightGrasper`；`left-swipe`需要相同结构条件和`leftGrasper`；`body-shove`不查手，要求`torso`且该技能明确允许身体推撞。

| 状态 | 结构事实和可执行角色 | 预检与输出 |
| --- | --- | --- |
| 肉体rev8、灵魂rev3 | grasps=true；右`R22`，左`L11`，躯干`T0` | 条件通过；首备选绑定R22；保存body8/soul3 |
| 右手断开，肉体rev9 | grasps仍true；只有左L11与T0 | 旧plan版本失效；首备选`MissingRole(rightGrasper)`；第二备选绑定L11 |
| 双手断开，肉体rev10 | grasps=false；只有T0 | 前两备选条件失败；第三备选绑定T0 |
| 本技能没有身体推撞备选 | grasps=false；只有T0 | `NoCompatibleAnimation`，不凭动画失败创造新技能 |
| 未换身体但换成灵魂rev4 | 仍有R22，但旧plan记soul3 | 旧plan失效；新灵魂重新验证授权和动作，不沿用旧回调 |

这个例子揭示身体条件与角色绑定之间的缺口：在rev9，条件`hasGraspers=true`仍满足，但右侧执行者不存在。若只查身体总类别便播放右手攻击，动画和事件都会缺少稳定锚点。先预检完整绑定，再提交计划，才能避免执行到一半才发现发射点消失。

## 验证、未做与风险

[读取器](checks/read_selected_animation_predicates.py)对46资源进行重新字节读取、摘要比对和有界字段解码；全零结果不是复用39/40的推测。[验证脚本](checks/verify_animation_predicate_examples.py)实际完成 **32项测试，0失败、0错误**，覆盖小端条件、未知位保留、三层分离、缺字段/越界/预算、三值独立判断、缺侧肢体、合法备选、无备选诊断、稳定绑定及肉体/灵魂版本失效。

另对46份证据逐项检查与28的键、包存储范围、存储/解压摘要一致，重新从所保存原字节计算condition words、require位和event gate，并检查字段相对偏移；统计复核为46/612/818/15。[实际验证记录](evidence/animation-predicate-verification.json)。这46项是证据一致性检查，和32项测试分别计数，不当作46次游戏运行。

**未做：** 未启动或附加游戏，未调用SDK接口，未读取私人存档，未恢复原生predicate评估函数、TLSA排序或失败调用链。因为本轮仅授权静态研究且现有提供者仍不可用，原作“缺手后究竟选哪个动作”保持未回答。测试验证的是读取边界与我们的规格，没有验证Spore运行行为。

**风险：** 所读技能集合全部条件为零，对条件分支的本机阳性样本仍为空；社区格式的require名与历史论文不能证明本机具体失败语义。自研预检示例没有实现完整IK、原子预约、碰撞伤害或异步资源回收。后续需要原生消费者的静态交叉引用，或另获授权的最小缺肢场景观察，才能补齐原作执行链；本轮不自动扩大权限。
