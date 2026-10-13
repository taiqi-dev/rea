# 43. 吸血、吸魔与资源返还的结算基础

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [攻击和最终 HP](35-attack-results-and-event-order.md) · [混合伤害与修正](44-mixed-damage-crit-and-fumble.md)

**本轮已闭合普通伤害路径的吸血和吸魔：它们按进入 `scr_physical_damage` 的伤害参数计算，在目标实际扣 HP 之前执行；不是按最终实际掉血差值，也不是只在击杀后触发。** 吸魔助手的已查路径是给攻击来源增加 MP，没有从受击者 MP 扣除对应资源的指令。独立资源效果和特殊技能仍不能统一归入这一规则。

目标身份沿用 00 与本轮完整摘要核对：EXE SHA256 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。REA 提供者缺失沿用已有记录，本轮使用 Capstone 5.0.9 静态读取。未运行、附加、改内存、目标文件或存档，也没有读取新存档。

## 1. 实际入口和参数所有权

普通结果处理器把计算伤害送进 `scr_damage`，后者在已到达的路径调用 `scr_physical_damage@0x141291910`，调用点 `0x1412a9974`。本轮新恢复下游：

```text
physicalDamage(target, D, additionalContext, ...)
    → lifesteal(D, target, undefined)
    → manasteal(D, target, undefined)
    → 条件 on_damage_method
    → simpleDamage(target, D, ...)
```

这里的名称是按实际实参整理的规格，不是原始代码。吸血与吸魔调用点为 `0x141292148 / 0x14129222c`，simple_damage 为 `0x141292455`。D 来自本函数第 1 参数，受击目标来自第 0 参数；这两个值在调用前分别复制到参数数组。

两种助手的当前 self 是这一伤害执行上下文，即资源接收来源；没有在上述调用前把 self 切换成受击目标。前置检查要求受击目标存在、其 object_index 与 OBJT3804 `o_unit` 的对象关系检查为真；来源 self.id 与 target 不相等，否则绕过吸取段。对象关系返回写入 `0x141291c8d`，使用门禁 `0x141291ddc`；来源 ID 与目标比较 `0x141292058 / 0x14129205f`。

因此不能把“受击者生命减少”和“来源生命增加”理解成同一个字段的两次写入，也不能把普通路径推广给没有单位资格的门、地形或自伤。

## 2. 吸血：输入伤害、比例和治疗收到倍率

入口 `scr_lifesteal@0x141293bb0`，主要三个参数为：

| 参数 | 已确认消费者 |
| --- | --- |
| 0 | 计算基础 D |
| 1 | 对方实例；存在时读取其 Lifesteal_Immunity，还用于表现 |
| 2 | 吸血比例；undefined 时读取当前 self.Lifesteal |

比例默认读取 `0x1412940ba–0x1412940e6`。目标存在检查 `0x141294137`；目标 `Lifesteal_Immunity` 真时直接把返回结果设为 0 并结束，`0x141294177 / 0x141294187 / 0x141294377`。

另外有来源对象资格分支：来源属于 OBJT3805、`ai_is_on` 假且不等于另一个指定对象时拒绝。关键位置 `0x141294283 / 0x1412942ae / 0x141294318`。该特例没有在本轮完整绑定指定对象的业务身份，保留字面门禁，不能把它补成某种阵营、尸体或训练假人的统一规则。

在普通有效有限数值路径：

```text
rate = 显式参数2，或 self.Lifesteal
A = math_round(D * (rate/100) * (self.Healing_Received/100))
capH = math_round(self.max_hp * self.Health_Threshold / 100)
Hcandidate = min(capH, max(Lh, self.HP + A))
if Hcandidate > self.HP:
    self.HP = Hcandidate
```

`Lh` 来自 RValue 槽 `0x149871c70`，本轮未核准初始化及完整写入生命周期，不能默认为 0。比较使用本机动态值比较助手与 `1e-5` 容差，不把非常接近的浮点值写成任意精度的数学保证。

| 计算步骤 | 指令/调用位置 |
| --- | --- |
| 取 Healing_Received | `0x1412943d6` |
| 比例乘 0.01、乘 D | `0x141294425 / 0x14129447c` |
| 乘 Healing_Received、再除 100 | `0x1412944d0 / 0x1412944eb` |
| 请求量取整 A | `0x141294594` |
| max_hp × Health_Threshold / 100、cap 取整 | `0x141294643 / 0x141294661 / 0x1412946db` |
| HP + A、下限 max、上限 min | `0x1412947d1 / 0x141294824 / 0x14129484f` |
| 只在候选高于旧 HP 时进入写入段 | `0x14129487c / 0x141294883` |
| HP RValue 最终复制 | `0x141295ad0` |

上限是经过 Health_Threshold 的有效上限，不是无条件 max_hp。请求恢复量 A 与最终 HP 增量不同：接近上限时会截断；旧 HP 已高于有效上限时，本助手的“必须高于旧值”门禁也不会为了执行吸血而强制降低 HP。

## 3. 吸魔：按 D 恢复来源 MP，没有证明等量转移

入口 `scr_manasteal@0x1412977a0` 的参数顺序与普通调用相同：`(D,target,rateOverride)`。undefined 比例读取 self.Manasteal，`0x141297c95–0x141297cc1`。本轮解码范围没有找到目标 MP 的读写，也没有找到与吸血一样的 target.Lifesteal_Immunity 检查；这一否定结论仅限本助手已查范围。

普通数值路径为：

```text
Amp = math_round(D * Manasteal / 100)
capM = math_round(max_mp * Max_Energy_Threshold / 100)
Mcandidate = min(capM, max(Lm, MP + Amp))
if Mcandidate > MP:
    MP = Mcandidate
```

`Lm` 为未知运行槽 `0x149871cb0`。此路径没有乘 Healing_Received，也没有据目标剩余 MP 限制 Amp。Max_Energy_Threshold 是来源的有效能量阈值属性，不是目标“可被抽取的能量”。

比例 × D `0x141297f16 / 0x141297f6a`，请求取整 `0x141297fdf`；上限乘法/除100/取整 `0x141298098 / 0x1412980b6 / 0x141298130`；MP 加法、max、min `0x14129823a / 0x14129828d / 0x1412982bc`；增量门禁 `0x1412982e9 / 0x1412982f0`，MP 写入 `0x1412999b4`。

所以这里的“吸魔”是游戏字段名称对应的伤害挂钩返能量。**不能由名称补成来源获得几单位、对方就必然损失几单位的守恒模型。** `Essence Leech` 等技能另有对象和事件，本篇没有将它们全部等同于此助手。

## 4. 按每个伤害调用计算，不能直接换成整次技能结算

这段没有先累计一整次技能的所有目标，再统一调用吸取；它在一个 target 的 `physicalDamage` 中各请求一次。若一个范围技能分别调用此链两次，恢复计算也有两次机会并分别取整。是否该范围技能确实这样派发、一个目标是否被重复调用，要由它的生产者决定。

这里没有本轮确认的事件 ID 去重、全技能吸取预算或每次施法统一上限。因此只能证明**每次到达这段伤害调用的局部行为**，不能声称“所有 AoE 都能按每目标吸取”或“同目标同回合只触发一次”。

| 场景 | 已核结果 / 前提 |
| --- | --- |
| block 后仍有 D>0 | 进入同一实际伤害链且门禁通过时，以这个 D 计算；没有结果字符串排除 block |
| D=0 | 数值请求 A=0；若未知下限不抬高当前资源，不产生增加。下限未确认时不能无条件推出这一结论 |
| 致命伤害 / overkill | 吸取在 simple_damage 前完成，本段未按目标剩余 HP 截断 D，也不等待死亡确认 |
| HP 被保护分支恢复 | 来源吸取已发生；未找到由最终 HP 回退自动撤销本段吸取的事务链 |
| 来源等于目标 | 此普通调用源绕过吸取 |
| 对方吸血免疫 | lifesteal 返回 0；不自动证明 manasteal 同样被禁止 |

## 5. 条件完整的构造演算

给定本次伤害链 D=18、来源 Lifesteal=20、Healing_Received=125、HP=78、max_hp=100、Health_Threshold=80；Manasteal=10、MP=38、max_mp=50、Max_Energy_Threshold=80。所有对象门禁通过，目标不免疫，并**另假设 Lh≤80、Lm≤40**，不将未知槽赋值为 0。

吸血请求 `round(18*.20*1.25)=round(4.5)=5`；有效 HP 上限80；候选 `min(80,max(Lh,78+5))=80`，实际恢复2。

吸魔请求 `round(18*.10)=2`；MP 上限 `round(50*.80)=40`；候选40，实际恢复2。随后才进入目标 HP 应用，目标最终是否减少18仍取决于 35 的保护、下限和回调。本例没有把目标 MP 减2。

另构造两个各 D=4 的目标调用、无上限截断、Lifesteal=10、Healing_Received=100：各请求 `round(.4)=0`，总恢复0；若另一个生产者先合并 D=8 再调一次，则 `round(.8)=1`。这展示“每次取整”与“汇总后取整”的差异，不证明任意实际技能采用哪一种。

## 6. 资源返还不能只按函数名称判断

`scr_attack_result_crit_modifiers_apply` 存在一个额外的资源请求分支：读 max_mp 后请求量为 `-min(math_round(.1*max_mp),25)`，调用 `scr_restore_mp(id,negativeAmount,undefined)`，地址 `0x141de4aaf / 0x141de4b0c / 0x141de4b5d / 0x141de4bde / 0x141de4bfa / 0x141de4c81`。

本轮核对 restore_mp 的普通值准备：它在资源候选计算中使用 **MP + 传入量**，加法 `0x14188ce84`，并做有效能量上限处理。因此此处传负量是负资源变更请求，不能因助手名含 restore 就称暴击返能量。该分支的全部武器/条件身份、最终减少路径与各类例外未完整绑定；本篇不推广成“所有暴击都扣10%能量”，也不把它加入吸魔公式。

例如另构造 max_mp=50，该分支输入为−5；这是确认的调用输入，不是未经门禁和写入核准的最终 MP 差值。资源返还、资源消耗、按伤害吸取应在自己的设计中明确区分。

## 7. 完成状态、证据和独立借鉴

已回答：一条普通伤害到吸血/吸魔/HP 的实际调用链；D 的来源和执行顺序；默认比例；治疗倍率区别；资源有效上限；明确增量门槛与写入；零伤害/格挡/击杀的局部边界；每次调用取整演算。

部分或未知：所有范围技能的派发次数；来源对象特例的完整身份；Lh/Lm 初值与运行写入；所有特殊资源技能、击杀返还被动；反射重定向后全部来源上下文；全部临界动态类型；额外负资源分支的完整资格和最终值。有限 `lea rcx,[rip]` 初始化扫描未找到这两个下限槽的生产者，不把“未找到”当作运行值为零。

可选本机证据：[入口覆盖](../../../_reference/stoneshard-study/eleventh-drain-native.json)、[普通实际伤害](../../../_reference/stoneshard-study/eleventh-drain-disassembly/scr_physical_damage.txt)、[吸血](../../../_reference/stoneshard-study/eleventh-drain-disassembly/scr_lifesteal.txt)、[吸魔](../../../_reference/stoneshard-study/eleventh-drain-disassembly/scr_manasteal.txt)、[资源助手](../../../_reference/stoneshard-study/eleventh-drain-disassembly/scr_restore_mp.txt)、[额外暴击修正](../../../_reference/stoneshard-study/eleventh-mixed-disassembly/scr_attack_result_crit_modifiers_apply.txt)。这些本地证据未版本化，正文已保留必要参数、公式、地址和边界；首段 pdata 解码不能当全系统恢复证明。

独立实现可以明确区分“准备伤害、实际掉血、致命前剩余 HP”三种可选吸取基数，并规定每目标或整次事件的次数、取整点、有效上限、免疫和最终扣血回退是否撤销返还。这是我们自己的契约选择，不能声称原作已有事件去重或事务回滚。按自己的需求独立编写，不复用恢复代码或专有资产。

验证为静态实参/字段绑定、普通数值指令关系和构造算术；未做游戏运行或产品测试，遵循本轮静态只读范围。风险是未知下限和未覆盖生产者/特殊效果，无法给所有技能组合的无条件资源结果。
