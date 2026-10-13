# 秘术缚索、斧类钩取与技能机制分类

本篇继续解释“怎样把敌人拉过来”，选取实际存在的 `Arcane_Tether` 和 `Wide_Cut`。这两个英文标识来自本机制品；尚未核实当前中文界面的完整技能译名，因此不会仅凭“钩取”一词断定用户指的是其中哪一招。怪物舌头拉拽、猛踹和公共击退算法另见 [19](19-kick-pull-and-knockback.md)，换位和移动攻击见 [18](18-swap-and-mobile-attacks.md)，范围生成见 [20](20-area-shapes-and-hit-selection.md)。

## 证据和确定程度

第五轮开始于 2026-10-12 18:37:40 PDT。重新计算 `StoneShard.exe` 与 `data.win` 的完整 SHA256，均与 [00](00-evidence-and-scope.md) 一致。本篇为本地静态资源、指令和控制流分析，没有运行游戏，也不是 REA Evidence 会话。

新增本机记录：

- [选定技能的完整表头与配置行](../../../_reference/stoneshard-study/fifth-skill-config-rows.json)：按实际 PE 节换算位置，从 EXE 字符串地址读取到 NUL，没有沿用先前索引的 200 字符预览作为完整表行。
- [秘术与斧类控制入口](../../../_reference/stoneshard-study/fifth-control-native.json)及[对应指令文本](../../../_reference/stoneshard-study/fifth-control-disassembly)：入口至下一登记入口的限定窗口可能包含编译器初始化、辅助函数或不可达片段；正文只引用实际事件路径中的指令。
- [对象继承索引](../../../_reference/stoneshard-study/third-telegraph-object-index.json)：`parent28` 为核对过的父对象索引，不能误用邻接的 `parent24`。

这里能确定局部属性计算、调用顺序、抗性输入和拉拽请求。最终扣血、所有装备修正、取消退款、视觉动画，以及每一种墙体的处理没有因此全部恢复。

## 原始配置：定义与运行实例分开

表头位于 `0x145e4bdc0`，前六列为技能键、`Object`、`Target`、`Range`、`KD`、`MP`。下表是名义配置；最终耗能可能经过公共修正，不能将 `MP` 列直接当成每次实际扣除量。表中的 `AP` 列也不能与角色的 `Arcanistic_Power` 字段混同。

| 技能键 | 表行 VA | 执行对象 | 目标 | Range / KD / MP | 类别 |
| --- | --- | --- | --- | --- | --- |
| `Arcane_Tether` | `0x145e4fd90` | `o_arcane_tether_birth` | Target Object | 4 / 4 / 14 | spell / arcanistics |
| `Wide_Cut` | `0x145e4cbc0` | `o_wide_cut` | Target Object | 2 / 12 / 12 | skill / 2haxe |

`Arcane_Tether` 的表指向出生代理，而伤害/拉拽事件在实际缚索实体中。对象 `o_arcane_tether`（1166）继承 `o_shell_damage`（5296），后者继承 `o_shell`（5291）；出生代理 `o_arcane_tether_birth`（8088）继承 `o_spellbirth`（5338）。`Wide_Cut` 的实体（5550）继承 `o_target_spell`（5531）。这是两条不同执行路径，不能因为都调用拉拽就合并整个生命周期。

## Arcane Tether：伤害输入和控制判定是两件事

### 从出生到接触后的延后执行

出生代理 Create 调继承逻辑后，写 `cast_frame=7`（`0x144e01f70/1f7a`）、`spell=1166`（`0x144e01fb2/1fbc`，即实际缚索对象）、`image_speed=1` 与 `is_crit=false`（`0x144e01fff/2030`）。公共出生生产门禁见 [15](15-telegraph-production-chain.md)；这里的 7 是字段值，不能直接换算秒数，也不能自动认定所有后续帧都保留该值。

实际缚索的 `Collision_o_unit` 在 `0x142d88fe0`：

1. 只有接触对象 ID 等于 target、且当前 `is_execute` 不为真，才进入目标接触分支（比较与真值门禁 `0x142d89140/9162`）。其他接触另有 owner 与状态分支，不能泛化为碰到任何单位都立即结算。
2. 计算缚索当前位置到缓存 `target_x/y` 的 `point_distance`（`0x142d8935d`），以整数常数 13 调用有序小于助手（`0x142d8936a`）。助手 `0x140089b20` 使用动态比较，排除不可比较返回 -2，只接受负结果；有限 double 有 `1e-5` 容差。因此必须落到该局部距离门槛内，单有 Collision 回调不够。
3. 先写 `is_execute=true`（`0x142d893b2`），再写 `alarm[3]=20` 和 `alarm[4]=1`（`0x142d8941e/946d`），将 `_image_index` 归零、更新 x 并将 speed 设零。这个标记阻止同一接触分支再次排程，不能当成全技能所有回调的幂等保证。
4. `Alarm_4` 中看到朝向、音效、GUI 动画和行动占用相关调用；其主体没有直接调用本文的拉拽公式。
5. `Alarm_3` 在 `0x142d878dc` 派发用户事件 0，即 `Other_10`，随后在 `0x142d878f4` 销毁当前实体。因此本篇的伤害/拉拽执行由这个后续事件进入。

构造排程例子：一次有效接触使原来为假的 `is_execute` 变真并设置上述两个 Alarm；紧接着再次接触同一个 target，便不能再次进入同一目标接触排程分支。若 Alarm_3 后来正常派发，就进入下面的计算并销毁缚索。是否暂停、打断或其他回调会改变 Alarm，实际帧率以及接触后游戏画面持续多久，都没有运行测量。

### 执行顺序

实际实体 `Other_10` 从 `0x142d89a80` 开始：

1. 调用用户事件 1（`0x142d89ccb`），检查 owner 与 target 存在（`0x142d89d0b`、`0x142d89d49`）。
2. 在当前技能实体写入 `Arcane_Damage`。使用 owner 的 `Arcanistic_Power`，建立以下局部伤害输入：

   ```text
   arcaneInput = 18 × (1 + owner.Arcanistic_Power / 100)
   ```

   字段读取在 `0x142d89d72/9d84`，除以 100 在 `0x142d89dbf`，加 1 在 `0x142d89ded`，乘 18 在 `0x142d89e1b`，写入在 `0x142d89e32`。18 是机器指令中的实际常数；这不是最终 HP 损失公式。
3. 调用继承事件派发（`0x142d89ea0`），随后重新检查 target 存在（`0x142d89ee0`）。先继承结算再检查存在，可以避免继续使用已销毁实例。存在性不等于 HP 大于零；所有死亡回调的影响仍未全部解释。
4. 读取 `is_shield_block`（`0x142d89eed`）；真值跳过本事件剩余拉拽和被动处理（`0x142d89f06 → 0x142d8a56f`）。这是具体盾牌门禁，不能推广为所有格挡状态都等同。
5. 计算抗性后的控制输入，调用公共概率助手。成功才计算拉拽距离和提交位移请求。
6. 概率失败会跳到 `0x142d8a47a`，继续公共被动调用部分；并非跳过本技能之前已执行的结算。

### 控制公式

这一有限数值路径使用：

```text
pullInput = 100 × ((owner.Magic_Power + owner.Arcanistic_Power) / 100)
            − target.Knockback_Resistance
```

普通有限数值下等价于 `Magic_Power + Arcanistic_Power − Knockback_Resistance`。保留未化简形式能反映实际运算。读取三个字段在 `0x142d89f88/9fad/9fd2`，相加、除以 100、乘 100、减抗性分别在 `0x142d8a04a/a065/a093/a0eb`；`scr_chance_value` 调用在 `0x142d8a216`。不要把这个输入自动视为已经钳制到 0–100 的百分数，公共助手的边界另见 [19](19-kick-pull-and-knockback.md)。

本轮公共助手核对发现普通路径使用包含两端的 `irandom(100)`，还会与一个初始化尚未定位的下限槽取 max；近似比较输入达到 100 时有直接成功分支。因此“输入 85”不是已测量的“85%”。例如在下限不影响输入、按整数阈值严格小于判定、暂忽略取模微偏的条件下，85 对应 0–84 共 85 个成功值，分母是 101。构造例子只假设本次判定成功，不冒充原作长期概率测量。

成功后准备 `tile_distance(target, owner) − 1`，并通过公共 min 助手与常数 3 比较；然后请求反向击退，即拉向施法者：

```text
requestedDistance = min(tileDistance(target, owner) − 1, 3)
castKnockback(source=owner, affected=target,
              distance=requestedDistance, reverse=1, optional=undefined)
```

距离调用 `0x142d8a355`、减 1 `0x142d8a36a`、min `0x142d8a3fb`，反向标记 1 的准备在 `0x142d8a427`，提交在 `0x142d8a466`。`tileDistance` 是游戏助手，不预设为欧氏距离。请求距离与实际完成距离分开：墙、占格和公共控制门禁可能缩短或拒绝位移。相邻目标的请求为 0，不代表本技能完全无效，伤害路径此前已进入。

### 贯通例子：构造属性，使用已确认运算

假设施法者 `Magic_Power=100`、`Arcanistic_Power=25`，目标 `Knockback_Resistance=40`，游戏距离助手返回 4。这些属性和位置是构造输入，不是本机角色测量。

1. 技能实体准备的局部奥术输入为 `18 × 1.25 = 22.5`。
2. 假设继承结算后目标仍存在，且 `is_shield_block=false`，进入控制判定。
3. 控制输入为 `100 × 125/100 − 40 = 85`。
4. **条件假设：概率助手此次成功。** 请求 `min(4−1,3)=3` 格反向位移。
5. 继续假设目标 HP 大于零、无击退免疫且进入 [19](19-kick-pull-and-knockback.md) 已核对的目标分支。若施法者在 `(0,0)`、目标在 `(4,0)`，且三格路径均被公共算法接受，目标可到相邻 `(1,0)`。这是无阻挡条件下的坐标演算；不能用它证明穿墙、角落规则或其他目标类型的受力行为。
6. 若盾牌门禁为真，本事件跳过步骤 3–5；若概率失败，前面的伤害输入/继承结算不会自动回滚。

### 行为伪代码

以下为独立组织的说明，辅助函数的原作缺口保留在注释中：

```text
onTetherExecute:
    dispatchUserEvent(1)
    if not exists(owner) or not exists(target): return
    self.Arcane_Damage = 18 * (1 + owner.Arcanistic_Power / 100)
    dispatchInheritedEvent()             # 最终护甲/抗性/扣血未在本篇展开
    if not exists(target): return
    if self.is_shield_block: return

    input = 100 * ((owner.Magic_Power + owner.Arcanistic_Power) / 100)
            - target.Knockback_Resistance
    pullResult = false
    if chanceValue(input, undefined, undefined):
        distance = min(tileDistance(target, owner) - 1, 3)
        pullResult = castKnockback(owner, target, distance, 1, undefined)
    callPassiveWithLocalResult(...)       # 调用已见，全部实参与副作用未恢复
```

这里的 `return` 表示被研究事件主体的已见退出分支；不是对自研生产代码错误处理的建议。

## Wide Cut：攻击成功以后才尝试拉一格

### 局部控制流程

`o_wide_cut.Alarm_0` 入口 `0x144046df0` 中读取 owner 的 STR、AGL、Knockback_Chance（`0x144047594/75b6/75d8`），加实际常数 80，再调用已解释过的 `math_round`：

```text
basePull = gameRound(80 + owner.STR + owner.AGL + owner.Knockback_Chance)
```

三次相加在 `0x144047620/7675/76ca`，取整在 `0x14404775c`；局部变量接收在 `0x14404776b`。有限数值的 `gameRound` 规则见 [14](14-combat-turns-and-damage.md)，不自行替换为某语言银行家取整。

随后先调用 `scr_skill_hit`（`0x14404787e`）和 `scr_skill_attack`（`0x1440478f5`），再检查：

- `is_deal_damage` 为真（`0x14404792d` 的失败分支跳过）。
- `attack_result` 不等于 `fumble` 和 `fumbleBlock`（`0x1440479b4/7a3b` 的相等分支跳过）。
- 本路径距离比较大于 1（`0x144047b0d` 调距离，`0x144047b3e` 比较，`0x144047b5b` 的非正分支跳过）。动态比较有 `1e-5` 容差；不能将浮点边界扩大成无容差的通用运算。
- 抗性后的 `basePull − target.Knockback_Resistance` 通过 `scr_chance_value`（减法 `0x144047c20`，概率 `0x144047cab`）。

满足后在 `0x144047ddb` 调公共 castKnockback，距离参数为 1，reverse 为 1，即请求目标向攻击者靠近一格。后面还有 `last_damage_taken` 与身体部位处理，不能把拉拽调用当成该技能的最后一步。

技能定义的 `Other_17` 也向 `data` 中的 `Pull_Chance` 项写入按同一属性组成的取整结果（键准备 `0x14463ebc6`，取整 `0x14463ec00`，映射写入调用紧随其后）。执行实体仍在执行路径读取属性并计算，不能推定所有技能都直接把 UI 描述缓存当成真实概率。

### 贯通例子：两格距离的一次攻击

构造 owner 的 `STR=15`、`AGL=12`、`Knockback_Chance=8`，target 抗性为 30，游戏距离助手返回 2：

1. `basePull = gameRound(80+15+12+8)=115`。
2. 假设攻击已处理且 `is_deal_damage=true`，结果不是上述两种 fumble。
3. 距离 2 通过大于 1 的门槛。
4. 概率助手接收 `115−30=85`。**条件假设：此次返回成功。**
5. 提交一格反向位移。继续假设公共 HP/免疫门禁通过、目标进入已核对分支；owner `(0,0)`、target `(2,0)`，中间格可用时得到 target `(1,0)`。
6. 若原距离为 1，就不进入这次拉拽概率调用；前面的攻击已经发生。若中间格不可用，实际位移由 [19](19-kick-pull-and-knockback.md) 的公共算法决定，不能直接搬到施法者格。

这说明“攻击附带钩取”至少包含攻击结果、距离、概率、路径四层。不是一个 `target.position -= direction` 就能等价。

## 本轮技能种类索引

下表把选定的真实配置和执行问题对应起来，不表示所有技能已经逐个恢复。

| 机制 | 真实代表 | 关键区别 | 详情 |
| --- | --- | --- | --- |
| 双目标交换位置 | Planar_Exchange | 双实体/两次坐标变更，不沿用击退距离算法 | [18](18-swap-and-mobile-attacks.md) |
| 自身移动后攻击 | Crippling_Lunge、Heroic_Charge | 位移事件与攻击事件分开，动作期间目标有效性需核对 | [18](18-swap-and-mobile-attacks.md) |
| 近战控制 | Power_Kick | 力量与击退抗性输入，公共受力位移 | [19](19-kick-pull-and-knockback.md) |
| 怪物长距拉拽 | Tongue_Pull | 投射/接触路径与反向位移请求，不能自动归为玩家技能 | [19](19-kick-pull-and-knockback.md) |
| 法术拉拽 | Arcane_Tether | 局部奥术输入、盾牌门禁、法术属性判定、最多三格请求 | 本篇 |
| 武器攻击附带拉拽 | Wide_Cut | 攻击后依据结果、距离和概率请求拉一格 | 本篇 |
| 线形范围攻击 | Piercing_Lunge | 表中 Target Area、Pattern=line、is_movement=0；名称含 Lunge 不能证明施法者移动 | [20](20-area-shapes-and-hit-selection.md) |
| 延后范围控制攻击 | Shockwave、Rock_Toss | 形状生产、独立格对象与去重；延后释放的相位另见前轮 | [20](20-area-shapes-and-hit-selection.md)、[15](15-telegraph-production-chain.md) |
| 纯自身位移候选 | Dash | 表中 Target Point、is_movement=1、Validators=DASH；本篇只核实配置，未恢复全部 validator | 后续候选 |
| 攻击/击退候选 | Onslaught | 表中 is_knockback=1、Tags=knockback；不能只靠标签断言每次击退或自身跟进 | 后续候选 |

## 值得借鉴的独立实现结构

下面是自研建议，不是恢复出的 Stoneshard 源码或作者意图。

1. **分别表达四种位置操作。** 交换位置、施法者移动、目标受力位移、技能区域移动具有不同的合法性条件；不要只保留一个模糊的“movement”标志。原表中 `is_movement`、`is_moving_zone` 与实际回调就是不同层次。
2. **伤害与控制结果分开。** 可以独立记录 `attackOutcome`、`damageApplied`、`controlRoll`、`requestedSteps`、`completedSteps` 和阻挡原因。这样拉拽失败不会被 UI 描述成伤害也没发生。
3. **明确每招的次序。** 比如“先攻击再拉一格”和“先移动再攻击”会改变距离、死亡和占格；每个阶段重新校验所需实体，而不是用最初坐标一路到底。
4. **定义概率单位与边界。** 本篇恢复的是助手输入，不是可以随意复制的自研概率接口。自己的接口应明确接受百分数还是 0–1、负数/超过上限怎样处理、随机样本来自哪里。
5. **把请求和结果分开。** 拉三格请求遇墙可能只完成部分路径。动画应消费已提交的路径和结果，不能独自决定角色最终占格。

## 未完成的核对

已核对完整表行、对象继承、事件内调用顺序与关键数值助手，并对本篇及同轮相关文档的构造公式进行 [独立算术检查](../../../_reference/stoneshard-study/fifth-example-validation.json)。这些断言仅验证说明中的演算，不能替代原游戏测试。纯研究文档没有执行 REA 项目全量构建或测试。

- 用户所说“钩取敌人”的具体中文 UI 技能身份仍未测量；目前交付两种真实玩家拉拽实现，避免错误匹配译名。
- Arcane Tether 已接上出生的 spell 指向、有效接触排程、Alarm_3 → Other_10 → 销毁；初始发射运动、接触前全部路径、暂停/取消对 Alarm 的影响仍未完整恢复，不能仅凭动画观感确定实际结算帧。
- 22.5 等是技能内部属性输入；最终法术伤害、护甲/抗性、暴击、盾牌消耗和死亡不能据此精确算出。
- 上述独立建议尚未适配 CommonGamePlayKit 的真实契约，也没有实现到该仓库。
- 没有启动游戏、附加进程、修改制品/存档或进行网络监测。风险是将局部控制流泛化到所有技能、把候选创建数当有效命中数，以及混同配置描述与实际事件。
