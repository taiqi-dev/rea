# 05 敌人技能集合、选择缓存与盟友协作

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [装备与掉落](04-enemy-equipment-loot.md)

本模块说明敌人如何注册技能集合、按技能名分派评分、缓存评估结果，以及逃跑事件如何影响经过过滤的盟友。具体例子仍为强盗弩手；盟友部分使用已验证的共享事件与士气回调。所有算法表达来自静态证据，未观察到真实游戏回合；伪代码是我们自行编写的行为规格，不是恢复的原始源码。

第九轮增量见 [33 弩手行动选择](33-arbalester-skill-scoring-and-action-choice.md) 和 [34 敌人自救](34-enemy-self-treatment-and-survival.md)。现已绑定Taking Aim/Headshot真实权重、当前新版FSM到候选事件、消费品/技能竞争与平分、每次所查回合入口重建缓存，以及选中治疗代理的执行桥。本页保留前轮集合/缓存/协作证据；下文旧演示分数仍只是构造，当前评分与消费者以33为准。

## 1. 模块职责与数据流

技能处理至少包含四种责任：

1. **类型配置**：创建时注册某个敌人拥有的技能与集合。
2. **活动集合**：选择当前技能集合，维护 `skill_active_set` 与相关范围。
3. **候选评估**：计算评分、额外校验、buff 修正、目标和使用许可。
4. **动作决策**：从评估结果进入实际动作。当前候选排序和平分已在33增量恢复；全技能流程和全部场景仍未完成。

盟友协作另外采用“事件来源→候选过滤→回调”的通路。已经证明一名单位的逃跑可通过这条通路产生盟友士气请求；没有证据证明所有敌人由一个统一指挥器控制，也没有完整包抄或保护弓手算法的验证。

## 2. 输入、状态与对象身份

| 数据/状态 | 已确认用途 | 尚不能确定 |
|---|---|---|
| 技能名称字符串 | 注册、集合数组成员、评分映射查询键 | 全部技能名称到评分 callback 的绑定 |
| `skill_sets_map` | 集合键到技能数组 | 所有集合键的业务含义与切换规则 |
| `skill_active_set` | 当前活动技能集合 | 每种装备/状态下最终活动列表 |
| `map_skills`、`skills_stat_csv` | 技能构造与参数查找 | 完整表值、权重和参数契约 |
| `__skills_map` | 新评分入口按技能名查询方法 | 全部映射初始化和具体权重 |
| `unit_skill_cache` | 按技能键缓存四项评估结果 | 所有失效条件与生命周期 |
| `skill_target` | 评估时取得的技能目标 | 目标在所有条件下如何选定 |
| `crossbowIsLoaded` | 弩手远程技能使用条件之一 | 全部装填触发与弹药消耗时机 |
| 阵营、可见性、视觉状态 | 盟友候选过滤 | 所有调用参数组合的过滤矩阵 |
| `Tier`、士气 | 逃跑来源与接收者的影响请求 | 非法 Tier、最终士气更新规则 |

真实弩手身份是 OBJT 172，记录起点 9400672，父对象字段 9400700；继承到 `o_enemy` 和 `o_unit`。其 Create 事件元数据位于 9400828，动作位于 9400840，code ID 18600，原生入口为 `0x142994d30`。对象关联和共享函数是两种证据，不能只因为名称里有 enemy 就认为所有敌人都进入同一路径。

## 3. 强盗弩手的真实技能配置

### 3.1 创建时注册的数据

| 技能名 | `create_skill_map` 第二参数 | Create 调用 VA |
|---|---:|---|
| Taking_Aim | 1 | `0x1429951e6` |
| Suppression | 1 | `0x142995259` |
| Headshot | 1 | `0x1429952cc` |
| Distracting_Shot | 1 | `0x14299533f` |
| Sweep | undefined | `0x1429953c5` |
| Seize_the_Initiative | undefined | `0x14299544b` |
| Raise_Shield | 2 | `0x142995796` |
| Cleave | 2 | `0x142995809` |

这里的 1、2 是**集合键**，不能解释成技能等级。其语义由数据流确认：`scr_create_skill_map` 把自己的 argument1 作为 `scr_enemy_skill_add_to_set` 的 argument0，把技能名作为其 argument1；后者用 argument0 查询和写回 `skill_sets_map`。

undefined 表示此处未提供具体集合键，不能直接解释成“集合 0”“默认近战组”或“所有集合共享”。默认参数在其他分支中的处理没有全部复原。

### 3.2 字符串构造如何建立身份

以 Taking_Aim 为例：静态构造把槽 `0x1498aebb0` 绑定到文本 VA `0x147b48023` 的 `"Taking_Aim"`，构造调用位于 `0x142996111`；Create 读取该槽，然后与整数 1 一起调用 `scr_create_skill_map`。因此“Taking_Aim 属于这里注册的集合 1”有构造、读取和传参的连续证据。

同一构造段逐槽建立 Suppression、Headshot、Distracting_Shot 等名称关联。不能把某个 `.bss` 槽的初始零字节直接称为技能名，也不能把“文件中存在这个名字”当成“此敌人使用这个技能”。

## 4. 集合算法：查找、建空、去重、追加、写回

### 4.1 已验证的步骤

`scr_enemy_skill_add_to_set` 的局部规则：

1. 读取单位的 `skill_sets_map`。
2. 根据集合键取得技能数组。
3. 若结果为 undefined，建立空数组。
4. 调用 `scr_array_contains` 检查技能名是否已在数组中。
5. 若已存在，跳过追加与后续更新分支。
6. 若不存在，使用 `array_push` 追加技能名，然后 `ds_map_set` 写回集合。

### 4.2 行为伪代码与演算

```text
add_skill_to_set(unit, set_key, skill_name):
    members = lookup(unit.skill_sets_map, set_key)
    if members is undefined:
        members = []

    if contains(members, skill_name):
        return

    append(members, skill_name)
    unit.skill_sets_map[set_key] = members
```

这是正常输入下的局部规格，未覆盖 GameMaker 动态类型的全部错误语义。

例如集合 1 起初不存在，加入 Taking_Aim 后成为 `[Taking_Aim]`；再次加入同名技能，数组不增加。继续加入 Suppression 后成为 `[Taking_Aim, Suppression]`。集合 2 另行以其键查询，不会因为集合 1 已有成员而复用它。

这是对函数行为的构造演算，不是修改原游戏或观察某个存档。它解释了去重设计，但不能据此宣称所有技能集合在全生命周期只初始化一次。

### 4.3 活动集合与边界

`scr_apply_skill_set` 读取技能数据和 `map_skills`，操作 `skill_active_set`，并调用 `scr_enemy_skill_set_range` 更新相关范围。已注册技能集合与活动集合是不同状态。

所以“弩手注册了八个技能”不能推出八个技能每一回合都同时可用。集合切换条件、活动列表过滤、是否随武器状态变化以及默认集合处理尚未全部确认。

## 5. 新评分入口：按技能名分派到方法

### 5.1 `priority_new` 的职责

`scr_skill_get_priority_new` 的已验证流程读取共享 `__skills_map`，以技能名检查成员存在性，然后取得对应值、绑定为当前单位的 method，并执行该 method。它将“查询哪个技能”与“执行该技能的评分规则”分开。

```text
evaluate_priority_via_new_dispatch(unit, skill_name):
    mapping = shared_skill_priority_mapping
    if mapping has skill_name:
        evaluator = mapping[skill_name]
        bound_evaluator = bind_to_unit(unit, evaluator)
        return call(bound_evaluator)
    return the_unresolved_missing_entry_result
```

缺失条目在原生块中有单独返回路径，但本页没有给返回值附上未经验证的业务意义；不能写成“默认最高优先级”或“自动随机选技能”。

旧的 `scr_skill_get_priority` 也存在，体积很大并引用大量上下文函数。这说明至少存在多个评分入口，不能把旧入口的每个分支自动当成所有当前敌人技能的实际路径。此文只陈述新缓存路径中确切调用到的 `priority_new`。

### 5.2 已知与未知的分界

已知：新入口按技能键分派函数，运行时评估关联当前单位。未知：Taking_Aim 和 Headshot 的具体 evaluator、权重、距离曲线、冷却与资源判断、概率扰动、终局排序。不能写“距离远时一定瞄准，近时一定盾击”，也不能把未映射的名字解释成固定连招。

## 6. 评估缓存：四项结果与合成评分

### 6.1 逐步算法

`scr_unit_skill_cache_update` 的 normal 路径：

1. 读取 `unit_skill_cache`，以技能键检查是否已有成员。
2. 已有时跳过重新计算，进入清理返回。
3. 没有时调用 `scr_skill_get_priority_new`，保存基础评分。
4. 取得 `skill_target`。
5. 调用 `scr_skill_extra_validate`，以技能、单位 id 和技能目标为参数。
6. 调用 `scr_skill_attack_buff_validate`。
7. 用已核对的加法助手把 buff 结果和 extra 结果加到评分。
8. 调用 `scr_use_skill_or_not`，取得使用许可结果。
9. 创建 `[合成评分, 使用许可, extra结果, skill_target]` 四项数组，以技能键存入缓存。

加法的确认来自 helper `0x1400038c0`，double 路径含 `addsd`；不能凭函数名把这两个修正理解成乘法系数。

### 6.2 行为伪代码

```text
update_one_skill_cache(unit, skill_name):
    if unit.unit_skill_cache has skill_name:
        return

    base_priority = evaluate_priority_via_new_dispatch(unit, skill_name)
    target = unit.skill_target
    extra = evaluate_extra_validation(skill_name, unit.id, target)
    attack_buff = evaluate_attack_buff_validation(unit.id, skill_name)
    combined_priority = base_priority + attack_buff + extra
    usable = evaluate_use_permission(skill_name, target, defaults)

    unit.unit_skill_cache[skill_name] = [
        combined_priority,
        usable,
        extra,
        target
    ]
```

这些英文名称是为说明责任自行写的规格名称。目标在评估中的全部副作用、函数参数的所有默认值没有恢复；伪代码不是可执行生产实现。

### 6.3 构造演算与缓存边界

为了解释相加结构，假设某次 evaluator 返回 12，buff 返回 3，extra 返回 -2，则合成评分是 13。若许可为 false，缓存可表达为 `[13, false, -2, 目标]`。这三个数是演示数据，**不是 Stoneshard 某个技能的真实权重**。

这说明评分与使用许可分别保留：分数不为零并不保证技能可以执行。但最后动作选择器如何处理这四项、是否直接排除 false、怎样平分决胜，本轮没有全部恢复。

缓存命中跳过计算的事实已确认。完整失效契约尚未确认，不能宣称缓存跨整个战斗有效，也不能宣称每帧重新算。第一轮共享更新入口调用过 `scr_unit_skill_cache_refresh`，但不能凭 refresh 名字补齐全部触发时机。

## 7. 真实使用条件：未上弦拒绝 ranged

### 7.1 已确认的条件链

`scr_use_skill_or_not` 内有一条与弩手 Create 形成闭环的规则：

1. 读取 `isCrossbowmanEnemy`。false 时跳过这段专有检查。
2. true 时读取 `crossbowIsLoaded`。true 时跳过本段拒绝规则。
3. 未上弦时比较当前技能类别与 `"ranged"`。非 ranged 跳过本段拒绝规则。
4. 未上弦且类别匹配时，将局部许可结果置为布尔 false。

```text
apply_crossbow_gate(unit, skill_category, current_permission):
    if unit.isCrossbowmanEnemy
       and not unit.crossbowIsLoaded
       and skill_category == "ranged":
        current_permission = false
    return current_permission
```

这表达的是这一局部规则。跳过此规则不等于整函数返回 true；资源、状态、路径、目标等其他检查可能继续拒绝技能。

### 7.2 真实初值演算

弩手 Create 明确写入 `isCrossbowmanEnemy=true`、`crossbowIsLoaded=false`。若某候选技能的运行时 Category 确认是 ranged，这三个条件同时成立，该局部许可会被置为 false。

当上弦字段变成 true 时，此项拒绝被跳过。非 ranged 技能也跳过此项。并非弩手的单位则根本不进入这段检查。上述分支有直接字段读取与条件跳转证据。

本轮没有把每个已注册技能的 Category 表值全部恢复，不能仅凭 Taking_Aim 等名字替代类别证据。也没有确认实际装填行为哪一回合触发，因此不能把这条规则改写成固定的“装填→瞄准→爆头”行动顺序。

## 8. 盟友事件：经过过滤再执行回调

### 8.1 逃跑事件入口

第一轮确认 `scr_stateFlee` 将来源单位士气清零，调用 `scr_unit_flee_morale`；后者通过 `scr_unit_ally_process` 分派 `scr_morale_ally_flee` 回调。它建立了“逃跑事件可以影响盟友”的具体通道。

共享处理器的候选过滤包含：受参数控制的可见标志检查、排除自己、阵营一致、视觉检查。通过后执行调用者提供的回调。不能把某条事件路径中的参数设置推广到所有盟友事件。

```text
dispatch_flee_event(source, event_options):
    for receiver in ally_candidates(source):
        if event_options requires visible_flag and receiver fails it:
            continue
        if receiver is source:
            continue
        if receiver.faction differs from source.faction:
            continue
        if required_visual_check fails:
            continue
        execute_flee_morale_callback(receiver, source)
```

候选获取集合、所有 option 默认值、视觉调用全部模式仍未知。此规格只保留已确认过滤项，不编造同屏广播、无限距离广播或全队同步状态。

### 8.2 具体例子

强盗 A 逃跑，不意味着附近任何敌人 B 都逃跑。B 至少需要通过这条调用中的自身排除、阵营和感知等筛选，才进入该士气回调；即使进入，也只是产生一个士气降低请求，是否随后改变 B 的 FSM 仍取决于 B 的状态与共享士气处理。

这一机制可以表现出群体反应，但静态证据不能证明它一定形成“近战保护弓手”“两翼包抄”或“头目分配统一目标”。另一个盟友目标入口确实读取阵营、AI 开关、技能目标和战斗目标数组，并查询视觉；完整传递矩阵未恢复，不能补成编队战术。

## 9. 逃跑引起的盟友士气请求

### 9.1 正 Tier 输入的局部算法

以参数 0 为接收单位、参数 1 为逃跑来源的调用关系，`scr_morale_ally_flee` 的有限正常数值规则是：

```text
flee_morale_request(receiver, fleeing):
    ratio = fleeing.Tier / receiver.Tier
    if fleeing.Tier > receiver.Tier:
        base = 25
    else:
        base = 10

    requestedReduction = max(1, math_round(ratio * base))
    morale_reduce(
        requestedReduction,
        receiver,
        attackerIsPlayer,
        other_unresolved_arguments
    )
```

除法、乘法和最大值均由助手指令核对，不是看到两个 Tier 就猜到比例。`math_round` 保留原入口名称；本轮没有证明半整数时采用哪种舍入规则，不替换成某种语言默认 round。

### 9.2 构造演算

| 逃跑来源 Tier | 接收者 Tier | 分支 | 中间值 | 请求值 |
|---:|---:|---|---:|---:|
| 1 | 1 | 不高于，base=10 | 1×10=10 | 10 |
| 2 | 1 | 高于，base=25 | 2×25=50 | 50 |
| 1 | 2 | 不高于，base=10 | 0.5×10=5 | 5 |

这些例子避开了半整数舍入歧义，并对应已验证的局部公式。数值 50 是传给 `scr_morale_reduce` 的 **requestedReduction**，不是观察到接收者士气最终减去 50。该处理器可能有其他约束、修正或状态更新；本轮未完整恢复，不能直接写 `receiver.morale -= requestedReduction`。

`max(1, …)` 为正常输入的请求值提供下限，但没有解决 receiver Tier=0、负 Tier、NaN 或异常类型的语义。这些边界未验证，不能为原游戏凭空补上保护分支，也不能据未验证断言它存在除零缺陷。

## 10. 关键证据位置

| 模块 | VA / 元数据位置 | 证据含义 |
|---|---|---|
| 弩手身份 | OBJT 172；文件偏移 9400672 / 父字段 9400700 | 类型与继承 |
| Create 事件 | 9400828 / 动作 9400840 / code ID 18600 | 容器入口关联 |
| Taking_Aim 构造 | `0x142996111`；槽 `0x1498aebb0`；文本 `0x147b48023` | 名称身份 |
| 技能集合参数转发 | `0x141741817`…`0x14174188c` | 集合键与技能名顺序 |
| 集合 helper | `0x141ce74f0` | skill_sets_map 操作入口 |
| 去重 / 追加 / 写回 | `0x141ce7adb` / `0x141ce7b8a` / `0x141ce7c1e` 后 | contains、push、set |
| 活动集合应用 | `0x1404655d0` | apply_skill_set 入口 |
| 缓存命中检查 | `0x1400a50cc` / `0x1400a50db` | 存在时跳过重算 |
| priority / extra / buff 调用 | `0x1400a516a` / `0x1400a5254` / `0x1400a531a` | 评分与校验分工 |
| 修正相加 | `0x1400a5326` / `0x1400a533a` | 两次加法助手 |
| 许可 / 四项数组 / 缓存写回 | `0x1400a53fc` / `0x1400a54bf` / `0x1400a54ea` | 使用判断与结果结构 |
| new 评分分派 | `0x140398820`；method `0x140398dbf`；执行 `0x140398e40` | 技能名到方法的路径 |
| 弩手 / 上弦条件 | `0x1417594a7` / `0x1417594ca` | 实际读取字段 |
| ranged 比较 / 拒绝 | `0x14175954b` / `0x14175957c`…`0x14175959f` | 局部 false 写入 |
| ranged 静态构造 | `0x141760379`；槽 `0x14987ec20`；文本 `0x14712a3c1` | 类别身份 |
| 逃跑状态 / 事件桥接 | `0x141141510` / `0x14002ffa0` | stateFlee / unit_flee_morale |
| 盟友筛选 helper | `0x140045e90` | 共享事件处理入口 |
| 阵营 / 视觉 / 回调分派 | `0x1400465c9` / `0x1400466e2` / `0x1400467c9` | 筛选与调用分开 |
| 逃跑士气回调 | `0x14078f360` | Tier 公式入口 |
| 25 / 10 常数写入 | `0x14078f769` / `0x14078f7bc` | 分支的系数 |
| 除法 / 乘法 / max 助手 | `0x140016cc0` / `0x14000bc20` / `0x1451de3d0` | 实际数值运算 |
| 士气降低处理器 | `0x140789d20` | 请求值进入后续共享规则 |

地址为 EXE image base `0x140000000` 下 VA，不是运行时 ASLR 地址。RIP 元数据 ID 的名称指针位于该 ID 地址前 8 字节；`0xffffffff` 可能是待运行时解析值，不能把不同未解析 ID 混为同一字段。`.pdata` 可只有函数 fragment，逐字节解码一个条目不等于完整函数覆盖。

本地证据：[第二轮技能调查](../../../_reference/stoneshard-study/second-loot-skill-findings.md)、[技能原生解码索引](../../../_reference/stoneshard-study/second-native-loot-skill-analysis.json)、[类别静态构造](../../../_reference/stoneshard-study/second-native-loot-skill/use-skill-ranged-static-init.txt)、[感知与盟友调查](../../../_reference/stoneshard-study/second-perception-findings.md)、[盟友原生证据索引](../../../_reference/stoneshard-study/second-perception-native.json)、[第一轮敌人调查](../../../_reference/stoneshard-study/enemy-findings.md)。这些 `_reference` 证据未版本化，其他机器可能无法打开；本页已保留关键输入、步骤与地址，不能因链接存在就宣称原始证据已公开发布。

## 11. 独立设计借鉴与区别

可以借鉴的结构是“类型数据配置→活动技能集合→候选评分和许可→缓存→动作决策”，以及“盟友事件过滤→专用反应回调”。它能把战术偏好、硬性条件和群体事件分开理解。

我们独立实现时可以自主选择：

- 用命名集合和有类型的技能 ID，明确集合默认值与切换条件。
- 用具名评估结果代替匿名四项数组，例如 score、usable、reason、target；许可失败保留具体原因。
- 明确缓存失效条件，例如目标移动、装填变化、资源变化、状态变化和新回合，防止旧评分或旧许可继续使用。
- 把“未装填拒绝远程技能”定义为硬性条件，同时让动作选择器知道装填动作是恢复可用性的选项。
- 给盟友事件定义接收范围、阵营关系、感知条件和传播频率，让群体反应可解释、可测试。
- 根据自有游戏需要设计士气公式、上下限与舍入规则，并对零 Tier/无效数据给出诊断。

以上是我们自己的产品选择，不是已经证明原游戏使用具名结果、这些缓存失效点或这套诊断策略。也不需要复制原游戏的 25/10 系数、技能表、资源或评分代码；可以先制定自有行为目标，再独立实现和验证。

## 12. 未做与风险

前轮未闭合的两技能权重、所查回合缓存重建与最后候选排序/平分已由33继续恢复，敌人治疗资源/消费见34。当前仍未恢复完整技能Category表、其余技能评分、冷却资源全契约、全部集合切换/缓存生命周期、全场景动作结果、完整队伍目标传递及士气最终差值。不能把本页或两技能样例当成完整敌人AI复刻规格。

未运行目标、未观察真实回合、未修改游戏文件。主要误判风险是把集合键当等级、注册技能当每回合候选、通过一个许可检查当可执行、把演示分数当真实权重、把士气请求当最终差值，以及从群体反应臆造包抄战术。以上风险均在对应章节保留边界。
