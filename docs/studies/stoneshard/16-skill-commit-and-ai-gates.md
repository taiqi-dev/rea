# 16 技能提交、预告取消与 AI 使用门禁

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [技能执行](10-combat-skill-execution.md) · [预告攻击](13-telegraphed-attacks.md) · [回合与伤害](14-combat-turns-and-damage.md)

本章补查三个具体问题：敌人选择技能时是否已扣费；预告攻击什么时候写入冷却和扣 MP；取消后是否退款或重置冷却。次要问题是自 Buff 和召唤的防重复条件。结论来自本机发行制品的静态指令和资源记录，未运行游戏。

控制/取消的第十轮增量见 [36 控制叠加](36-control-overlap-and-action-locks.md) 与 [37 预告中断](37-telegraph-interruption-and-cancellation.md)。现已核准取消检查的spell/skill文本和两招class=skill写入，以及预告格先清理再销毁的实际范围。下面所列“未见直接补偿”继续保持有限否定证据，不能据新增类别闭合扩大成全局无退款。

**已确认普通敌人施法的提交路径先调用冷却写入、再写 MP，之后创建施法对象。预告等待和命中结算是后续阶段。已读冲击波、投石取消事件未发现直接退款或冷却重置；尚不能把这个有限范围的否定证据写成“所有取消绝不退款”。AI 通用防重复施放规则仍未闭合，出生效果的一次执行标志不能替代它。**

## 1. 对象与适用证据

| 制品 | SHA256 |
| --- | --- |
| `StoneShard.exe` | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| `data.win` | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

目标位于 `E:\Steam\steamapps\common\Stoneshard`，为 GameMaker YYC x64 制品。地址均为 image base `0x140000000` 下的静态 VA。沿用匹配摘要的既有证据，并对相关入口用 Capstone 5.0.9 做局部重新解码；没有 REA 提供者会话，不赋予这些文件虚构的 Evidence ID。

新增解码包括 `scr_enemy_cast_spell`、`scr_cast_aoe_spell`、`scr_use_skill_or_not`、`scr_skill_extra_validate`、`scr_skill_attack_buff_validate` 和 `scr_skill_AI_buff_skill`。解码函数段不等于已经理解所有分支；`.pdata` 可能为片段，未追到的动态方法调用、运行时属性访问和间接派发保留未知。

## 2. 真实配置：冲击波和投石

两行数据采用已核准的同一技能表头 `0x145e4bdc0`，不是凭名称推测：

| 字段 | Shockwave | Rock_Toss |
| --- | --- | --- |
| 表行 VA | `0x145e53910` | `0x145e53830` |
| Object | `o_shockwave_birth` | `o_rock_toss_birth` |
| Target | Target Area | Target Area |
| Range | 3 | 16 |
| KD | 3 | 10 |
| MP | 30 | 80 |
| Duration | 0 | 0 |
| AOE_Lenght / AOE_Width | 3 / 3 | 2 / 2 |
| is_movement | 0 | 0 |
| Class | skill | skill |
| Pattern | pyramid | normal |

静态字符串构造分别位于 `0x140bda93e / 0x140bda94c` 和 `0x140bda900 / 0x140bda90e`，绑定到槽 `0x14980df90 / 0x14980df70`。列名保留制品中的拼写 `AOE_Lenght`。

表中 KD、MP 是输入配置，**不是已经测得巨魔最终冷却和最终扣费**。技能耗能、冷却修正、被动和创建补偿仍参与公共流程。表内 Duration=0 也不等于预告对象零等待：`o_aoe_spell_multiturn.Create` 另写 `skill_duration=2`，两种持续字段的责任不同。

巨魔 Create 真实注册 Shockwave 和 Rock_Toss：

- Shockwave 名称槽 `0x1498d62e0`，构造 `0x1437bac3f`，注册调用 `0x1437b97e7`。
- Rock_Toss 名称槽 `0x1498d62f0`，构造 `0x1437bac5e`，注册调用 `0x1437b987f`。

OBJT 3962 `o_ancientTroll` 的资源继承为 3955 `o_Omnivore` → 3805 `o_enemy` → 3804 `o_unit`。这证明技能配置确实属于巨魔；它不单独证明某场战斗一定选择哪招。

## 3. 从候选评估到提交入口

已有[05 技能决策](05-enemy-skills-cooperation.md)确认评估缓存将评分、使用许可、额外结果和目标分别保存。缓存建立和候选评分不能自动视为已经消耗资源。

`scr_use_skill_or_not` 的本次局部确认：

1. 读取单位当前 MP，位置 `0x14175a220`。
2. 以候选技能和键 `MP` 查询数据，调用 `0x14175a2a9`。
3. 比较当前 MP 与查询结果，位置 `0x14175a2bf`；比较返回负值时 `0x14175a2c6` 跳入失败出口 `0x14175af39`，将许可结果置为零。
4. 后续又读取候选 `KD`，调用 `0x14175ad95`；与零比较不相等时走 false 路径，相等时还要结合先前许可和参数决定最终结果。
5. 许可通过且第三参数为真时，存在将候选写入单位 `skill` 的分支，写回 `0x14175aec0`。这段是选择状态写入，不是 MP 写回。

MP 比较使用带容差的动态值比较助手，传入容差常数 `1e-5`；不能把所有动态类型、NaN 或容差边界改写成某语言普通 `<`。正常整数输入下，这一段可解释为“资源不足拒绝”。这里查询的 MP 值与提交时经过后续修正的 `effectiveCost` 也不能直接宣称完全一致。

真实执行桥中，`o_enemy.Other11` 在 `0x143649af2` 以当前单位上下文调用 `scr_enemy_cast_spell`，参数数为零；后者读取单位 `skill`。该事件存在 `isFakeMob` 专有提前出口，不是每次事件都无条件施法。

巨魔自己的 Other11 在 `0x1437c377a` 明确调用继承事件助手。结合上述资源父链，可以建立它连接共享敌人施法事件的强线索；本次仍未完整恢复“最终选择器何时派发巨魔 Other11”、中间父类的事件查找表及所有覆写条件。因此这里的生产桥是**配置和局部执行已确认，最上游调度尚有缺口**，不能把推断画成已运行的完整闭环。

## 4. 提交阶段：冷却 → MP → 创建

`scr_enemy_cast_spell` 入口为 `0x14185e970`。在已经到达普通技能提交分支的正常路径中，顺序如下。

### 4.1 先构造有效值

普通 `Class=skill` 分支的一段耗能计算是：

```text
partialCost = gameRound(
    skill.MP * (
        unit.Skills_Energy_Cost / 100
        + unit.Abilities_Energy_Cost / 100
    )
)
```

字段读取 `0x1418602f1 / 0x141860307`，除法 `0x141860366 / 0x14186037d`，相加 `0x141860541`，乘法 `0x1418605b7`，取整调用 `0x14186066a`。后续存在额外被动修正，本章将最终传到提交处的值称为 `effectiveCost`，不把 partialCost 当所有情形的最终值。

有限正常数值的自定义 `gameRound(x)` 已由 14 核准为 `sign(x)*floor(abs(x)+0.5)`，并非默认语言的银行家舍入。异常浮点和动态类型分支未由此公式覆盖。

冷却局部量在栈槽 `[rbp+0x268]`，另有乘数 `[rbp+0x218]`。提交前二者相乘 `0x1418657fa`；取最终值后的具体被动组合与创建当轮补偿未全部恢复。

### 4.2 写冷却

`0x141865863` 调用 `scr_set_kd`，实参为当前技能键、字符串 `KD`、上述冷却乘积。`scr_set_kd` 内的正常地图写入是 `ds_map_replace`，已定位 `0x1417538c3`；它有查找和缺失值处理，不保证传入无效技能也会成功写入。

因此更准确的陈述是：**创建前已发出冷却写入请求，正常已登记技能路径写入地图**。不是等攻击命中才开始首次写入冷却。

### 4.3 再写 MP

随后取得当前单位的可写 MP 字段 `0x1418658b1`，执行：

```text
MP_next = max(F, MP_current - effectiveCost)
```

减法助手调用在 `0x141865922`，max 在 `0x141865977`，最终复制进 MP 字段在 `0x141865991`。`F` 来自槽 `0x149881310`，位于未有完整静态初始化映射的区域；本次没有确认它的运行时值，**不将其自动写成零**。

### 4.4 再创建施法对象

上述提交后，Target 分支才进入创建：普通实体调用 `scr_cast_spell`（`0x141866a8a`），范围路径调用 `scr_cast_aoe_spell`（`0x141866e11`），No Target 状态路径调用 `scr_effect_create`（`0x141867237`）。这些是不同条件分支，不能写成同一技能依次调用三者。

本章没有证明创建失败自动回滚前两项写入，也没有恢复创建异常后的所有容错。函数中调用地址的顺序只用于已追局部正常控制流，不以地址排序推断所有执行路径。

## 5. 出生效果到真实预告对象

`scr_cast_aoe_spell` 的相关路径先创建范围格，再创建技能表 Object 指向的出生效果，绑定 owner、target、name、point 等字段，并调用 startcast；出生效果与实际等待攻击是两个实例。

- 出生效果创建的 `instance_create_depth` 标识读取在 `0x1418711b1`，实际运行时调度调用在 `0x1418711e2`；owner 绑定 `0x141871299`，startcast 调用 `0x1418714c2`。
- `o_shockwave_birth.Create` 将自身 `spell` 写为 double 5515，在 `0x143fed5c9–0x143fed601`；OBJT 5515 为 `o_shockwave`。
- `o_rock_toss_birth.Create` 将 `spell` 写为 double 5528，在 `0x143ffb409–0x143ffb441`；OBJT 5528 为 `o_rock_toss`。
- 共享 `o_spellbirth.Other10` 读取 `spell`（`0x143e4c3c4`）作为第四个实参；`0x143e4c408` 读取创建函数标识，实际创建调度调用在 `0x143e4c436`，随后绑定 owner、target 等字段。入口还有 `!is_execute`、玩家实例存在、point 存在等前提，不能把任意 birth.Other10 调用都当成功生成。
- 两种出生效果自己的 Other10 先调用继承事件；投石出生效果又把 owner.is_cast_spell 写为 1（`0x143ffc6c1–0x143ffc6e8`）。

这使“表行指定 birth→birth 指定实际攻击对象”的身份链得到指令和资源的交叉核对。何时经过动画到达 birth.Other10，以及最上游派发缺口，仍需要另行验证。

实际预告对象继承 `o_aoe_spell_multiturn`。其创建写 `skill_duration=2`；共享回合结束检查 owner、锁定列表等门槛，然后递减，零时派发 Other11，进入释放。冲击波随后等待动画/Alarm；投石创建投射物与终端格。空间选格和命中执行见 13 及 15；它们不能替代提交阶段的扣费证据。

## 6. 取消与清理：证据支持到哪里

共享 `scr_global_turn_end` 相关循环中的取消先派发预告对象 Other12，再销毁。已确认门槛包括 owner 不存在，以及移动、技能/法术锁条件；`is_movement=false` 的对象不能单因 `lock_turn` 非空就断言取消。

| 路径 | 已确认局部行为 | MP / KD 补偿证据 |
| --- | --- | --- |
| `o_shockwave.Other12`，`0x143ff3240` | 调整 owner 动画；筛选同 main_owner 格对象并销毁；视觉处理 | 本事件已读指令中未见直接 MP 写回、map_skills 写回或 set_kd 调用 |
| `o_rock_toss.Other12`，`0x144000450` | 具有动画处理、相关格/对象清理 | 同上，未见直接资源补偿 |
| `o_aoe_spell.Other12`，`0x143e49db0` | 本机入口是极短返回路径 | 没有补偿主体 |
| `o_aoe_spell.Destroy`，`0x143e48c60` | 选择同 main_owner 的格对象，设置 alarm[1]=1，衔接格对象生命周期 | 已读主体未见直接退款/冷却重置 |
| 取消后共享销毁 | 执行对象正常 Destroy/CleanUp 通路 | 是否所有回调均无补偿尚未证明 |

这里的“未见”严格限定所列入口的直接字段和已命名调用。动态属性访问、间接回调、其他父类/状态的清理和目标删除后的分支并未全部闭合。也不能把所有 Destroy 当取消：正常释放同样可能用销毁触发范围格结算，取消先移除格子的先后关系需要与 15 合读。

**当前最强解释**是该已观察结构将成本/冷却提交放在出生效果创建之前，取消负责停止后续攻击并清理提示；这些取消主体没有直接执行补偿。这个解释是有证据范围的推断，尚不是全游戏通用“取消无退款”契约。

## 7. 构造演算：一次投石提交和取消

以下使用真实 MP 表值 80，其他未确认运行值均显式假设：当前 MP=120，耗能比例之和为 1，额外被动不修改成本，有效冷却写入值 `K`，下限 `F≤40`。

```text
评估：120 与配置 MP80 比较，这一项资源检查通过
提交：发出 KD := K 的正常地图写入
提交：effectiveCost = gameRound(80 * 1) = 80
提交：MP := max(F, 120 - 80) = 40
创建：o_rock_toss_birth → o_rock_toss
等待：技能对象持有 skill_duration=2
取消：若进入已确认取消门槛，Other12 → 清理 → Destroy
```

这不是实测巨魔的 MP、能耗比例或冷却。若 `F>40`、被动改价、地图写入失败、最上游入口不同或后续回调补偿，结果也不同。已读取消主体没有把 40 加回 120，也没有把 KD 设置回零；“玩家运行中最后仍为40/K”需要运行观察或完整回调闭环才能确定。冷却在公共回合中的递减另见 14，不能将持续等待时的数值变化误叫退款。

## 8. AI 门禁、状态免选与防重复的区别

### 8.1 已确认的是不可选中状态门禁

`scr_use_skill_or_not` 在 Target 等于 `Target Object` 时继续验证目标类型。常量槽 `0x14954b8d8` 的 double 值是 3804，资源确认是 `o_unit`。目标属于该类型后，读取 target.buffs，再调用 `scr_instance_exists_in_list` 检查对象 5233；该 double 来自 `0x14954b8e8`。

OBJT 5233 的名称为 `o_b_untargetable`，记录偏移 11023512，父对象 6052。检查结果为真时，`0x141759452–0x141759475` 将局部使用许可置为布尔 false。

```text
apply_one_target_gate(candidate, target, permission):
    if candidate.Target == "Target Object"
       and target is a unit
       and the examined helper finds o_b_untargetable in target.buffs:
        permission = false
    return permission
```

这是目标状态限制，**不是“目标已带这个技能的同名 Buff，所以不能重施”**。查找助手第三参数为 undefined，其全部匹配默认规则本次没有再恢复；不能把这个位置推广为全部 Buff 类型的去重。

### 8.2 出生效果幂等已确认，AI 重复候选尚未确认

`o_summon_mana_crystal.Other10` 中有真实一次执行条件：`is_execute=false` 且 owner 存在才进入，先把 is_execute 置真，再于 `0x142da0749` 调用 `scr_enemy_summon`。具体链见[12 召唤](12-summoned-units.md)。

这阻止同一个出生效果实例反复请求生成。它没有证明施法者不能创建第二个出生效果，没有证明同类召唤总数限制，也没有证明主人已有召唤物时 AI 会过滤技能。

集合成员去重、缓存已有键跳过评估同样只管理集合/评估记录。它们不是 Buff 叠层策略或召唤数量门禁。

新增 `scr_skill_AI_buff_skill`（`0x141c2f940`）读取目标、距离、单位模式及状态评分辅助，调用 stance_effect 后还存在减去 2 的评分修正（`0x141c30835–0x141c30876`）。本次没有恢复其全参数绑定和所有调用者；因此不从函数名宣称它实现“自 Buff 同名不得重复”。`extra_validate` 是查映射并派发额外规则的入口，动态映射的具体回调也未闭合。完整防重复问题仍是未知。

## 9. 关键证据与复核入口

| 问题 | 位置 | 证据性质 |
| --- | --- | --- |
| 巨魔注册两技能 | `0x1437b97e7 / 0x1437b987f` | 指令 + 名称构造 |
| Shockwave / Rock_Toss 参数 | `0x145e53910 / 0x145e53830` | 表行和表头交叉确认 |
| 巨魔继承施法事件 | `0x1437c377a` | 指令；上游触发未闭合 |
| 共享执行入口 | `0x143649af2 → 0x14185e970` | 直接调用 |
| 评估 MP / KD | `0x14175a2a9 / 0x14175ad95` | 查询与比较，不是扣费 |
| 冷却提交 / MP 提交 | `0x141865863 / 0x141865991` | 直接请求与字段写回 |
| 范围创建 | `0x141866e11 → 0x14186fd70` | 条件分支调用 |
| 出生效果创建 / startcast | `0x1418711e2 / 0x1418714c2` | 指令调用与参数绑定 |
| 出生效果绑定实际 spell | `0x143fed601 / 0x143ffb441` | 5515 / 5528 实际写入 |
| 共享出生实体创建 | `0x143e4c3c4 / 0x143e4c436` | spell 字段进入创建 |
| MP 下限 | 槽 `0x149881310` | 使用点确认，运行值未知 |
| 目标 Buff 门禁 | `0x141759437–0x141759475` | 检查 untargetable 后拒绝 |
| 目标类型 / 状态类型 | double 3804 / 5233；OBJT 10528224 / 11023512 | 常量 + 容器元数据 |
| 召唤单实例一次执行 | `0x142da0749` 及上游 is_execute 分支 | 指令；不是 AI 总数限制 |

本地可选证据：[本轮解码索引](../../../_reference/stoneshard-study/fourth-commit-native.json)、[施法提交解码](../../../_reference/stoneshard-study/fourth-commit-disassembly/gml_Script_scr_enemy_cast_spell.txt)、[使用门禁解码](../../../_reference/stoneshard-study/fourth-commit-disassembly/gml_Script_scr_use_skill_or_not.txt)、[范围创建解码](../../../_reference/stoneshard-study/fourth-commit-disassembly/gml_Script_scr_cast_aoe_spell.txt)、[Buff AI 局部入口](../../../_reference/stoneshard-study/fourth-commit-disassembly/gml_Script_scr_skill_AI_buff_skill.txt)、[预告证据索引](../../../_reference/stoneshard-study/third-telegraph-native.json)、[字符串构造映射](../../../_reference/stoneshard-study/third-static-string-slots.json)。`_reference` 为未版本化本机产物，其他机器可能无法打开；必要行为、字段、常数和限制已保留在本文。

## 10. 独立设计借鉴与剩余问题

可以借鉴“评估→提交→创建→等待→释放或取消→清理”的阶段划分。独立实现时应明确哪些阶段允许改变目标，何时扣资源，冷却何时开始，以及取消是退款、部分退款还是不退款；为动作建立独立身份，记录 costCommitted、cooldownCommitted、cancelReason 和 compensationApplied，避免重复补偿。这些是自研契约建议，不是原游戏已验证字段。

自 Buff 候选过滤、允许刷新/叠层、召唤数量上限、同一出生效果幂等和缓存失效应各自定义。可把硬性许可与评分分开，让低分和不可用都保留原因。无需照搬原制品表值、对象或代码。

| 原问题 | 完成程度 | 剩余所需证据 |
| --- | --- | --- |
| 通用敌人技能何时扣费/写冷却 | 已确认正常提交局部顺序 | 全被动修正、异常与失败回滚 |
| 两招配置与出生对象身份 | 已确认 | 实战实际值与最终选择调度 |
| 巨魔真实入口完整闭环 | 部分确认 | 最终选择器派发 Other11、中间父类事件表和覆写 |
| 取消是否补偿 | 所列主体未见直接补偿 | 全继承清理/状态回调或只读运行观察 |
| 自 Buff 同名防重复、召唤上限 | 未确认 | 特定技能 evaluator 与映射初始化、存在/数量查询的实际参数 |
| 同个召唤出生效果反复执行 | 已确认有门槛 | 所有其他召唤类型不能据此推广 |

未启动、附加或修改游戏，未修改存档，未验证实战时序与数值，未提交或推送。主要风险是把表价当最终价、把调用请求当任何输入都成功、把有限取消覆盖当全局无退款，以及把幂等或缓存去重误叫 AI 防重复。这些缺口保留为后续调查问题。
