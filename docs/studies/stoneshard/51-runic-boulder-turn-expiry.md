# 51 符文巨石自动到期核对：逻辑回合、帧事件与销毁条件

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [46 巨石实体与主动消费](46-combat-terrain-and-entity-consumption.md) · [11 状态生命周期](11-buffs-and-effects.md)

本篇继续核对“巨石的 duration=20 是否会逐回合递减并自动销毁”。**所选本体事件、直接父事件、共享回合入口和 duration 字段引用仍未闭合这个到期链。新增证据能确认共享 Buff 递减有明确容器边界，本体帧事件另有 HP≤0 的通知，不能把它们拼成巨石二十回合寿命。**自动到期在本篇保持未确定；同样不能据此宣布巨石永久存在。

适用制品与 [00](00-evidence-and-scope.md) 一致：EXE SHA256 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win SHA256 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。本轮完整摘要复核一致。REA 工具／提供者缺失沿用既有记录，以下是 Capstone 5.0.9 本地静态读出，不是 REA Evidence，没有运行游戏、附加、修改制品或存档、读取新存档或监测网络。首 `.pdata` 覆盖不等于全部语义，元数据名按 refVA−8 识别，动态选择器及 BSS 未补成常数。

## 1. 要成立的完整算法需要四段证据

“二十回合自动消失”需要同时证明：

1. Create 的20确实是寿命，而非技能强度、其他参数或保留字段。
2. 哪个调度器每个逻辑回合选中巨石，是否受冻结、离屏、切图影响。
3. 调度后对**这块巨石实例**执行 `duration -= step`，并明确先减后判或先判后减。
4. 到达何种门槛后请求本体 Destroy，随后经过 aura、占格与容器清理。

现有第1段只能确认字段生产，第4段只有一般销毁与主动消费链。缺失的第2／3段不能用 Buff、召唤物或视觉 Alarm 的已知机制替代。

## 2. 本体和继承事件的增量核查

资源父链为 `o_runic_boulder(5473) → o_totem(5470) → c_broken(5469) → o_abstract_stuff → o_stuff → o_barrier`，详见46。本轮补查的关键入口如下。

| 入口 | 新确认的职责或局部行为 | 与到期问题的关系 |
| --- | --- | --- |
| `o_totem.Other12@0x143f89f90` | 写当前上下文记录后直接返回 | 这个父事件本身没有递减或销毁；不等于所有父行为为空 |
| 巨石 `Other4@0x143f98b40` / `Other5@0x143f98b30` | 同样只写当前上下文记录后返回 | 无法把切换相关事件名称当自动过期处理器 |
| `Other7@0x143f93c60` | sprite、image_index、image_speed、光照相关 | 无已闭合寿命消费 |
| `Other13@0x143f96440` | 在选中 owner 的上下文临时改变 change_mp，分派另一用户事件，再恢复 | 是一段来源单位事件通知，不是本体 duration 递减 |
| `Other14@0x143f96e00` | 表现、光照与场景格处理 | 所选段没有 duration 递减 |
| `Other12@0x143f942a0` | 来源存在性、可见性、MP／状态／被动与临时属性请求 | 状态请求不证明巨石自身加入 Buff 寿命列表 |
| `Step0@0x143f92560` | 继承分派、震动／尘土与 HP 门槛通知 | 明确是帧事件入口；不能叫20回合计时器 |

`Other4/5` 和父 `Other12` 为没有普通 `.pdata` 条目的短函数，取到下一登记入口的16字节作边界核查；有效指令是上下文写入与 ret，余下为 int3填充。这是所选入口的实际负证据，不是按“没有 .pdata”就认定事件缺失。

证据：[本轮入口登记及解码范围](../../../_reference/stoneshard-study/twelfth-expiry-native.json)、[父Other12](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Object_o_totem_Other_12.txt)、[巨石Other13](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Object_o_runic_boulder_Other_13.txt)、[巨石Step](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Object_o_runic_boulder_Step_0.txt)。

## 3. 共享回合确实递减状态，但容器边界不同

`scr_global_turn@0x1416c2a60` 在两个不同阶段调用 `scr_states_duration_dec@0x141ae5c20`，调用地址为 `0x1416c2e5e` 与 `0x1416c475b`。它还有 cutscene、时间冻结、角色时间更新和恢复等分支，不能因为有两个调用就说同一状态每回合减两次。

持续助手读取被选单位的 `buffs` 列表，再逐成员读取 have_duration、is_next_turn、is_delete 等。对到达正常递减分支的状态成员，在 `0x141ae6719` 获取可写 duration，局部减法经 `0x141ae6737` 后的算术入口提交；到期门槛调用 `0x141ae675f` 后成立才在 `0x141ae6799` 请求销毁该成员。列表选择、相位跳过与无持续状态仍按11的详细规则处理。

这段算法的对象所有权是：

```text
单位 → 单位.buffs → 所选状态成员 → 成员.duration → 成员销毁
```

要把它用于地图巨石，必须另证明巨石 ID 进入了相同 buffs 容器，并且通过这些状态门禁。本轮没有这样的生产证据。巨石关联 aura 列表与单位 buffs 列表是两个不同容器；Destroy 销毁 aura 成员不能反证本体也属于 buffs。

`scr_temp_effect_duration@0x141cdb810` 的所选段也读取 buffs、source、atr 与 duration。它针对特定来源和属性的状态成员，不能只因 duration 字段名相同就作为地图实体寿命处理器。名称近似的 `scr_duration_decrese(_simple)` 还涉及 Armor_Damage、装备 data／Duration_Resistance；它同样不能自动解释为召唤物生命周期。

证据：[共享回合](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Script_scr_global_turn.txt)、[状态递减助手](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Script_scr_states_duration_dec.txt)、[临时状态时长助手](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Script_scr_temp_effect_duration.txt)、[装备相关持续值处理](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Script_scr_duration_decrese_simple.txt)。

## 4. 能闭合的另一类自动处理：HP门槛不是到期

巨石 Step 在 `0x143f92b9b` 读取自身 HP，`0x143f92baf` 将它与0比较，成立后在 `0x143f92bce` 发出用户事件3请求。该运行时包装 `0x1451ef5b0` 明确将请求号加10并送 Other 事件分派，因此事件3对应 Other13，**这个调用本身不是 instance_destroy**。

比较助手 `0x14007b750` 把第二参数整数转换为数值，再动态比较；正常有限数值路径返回“比较结果≤0且不是不可比较−2”。于是此处正常数值门槛为 HP≤0。非数字、特殊值与浮点容差不在简单整数演算中替换成 C 风格比较。

直接父 `c_broken.Step@0x143f87de0` 另有 can_broke 门禁和同一 HP≤0 检查（`0x143f881a4`），随后请求噪声、碎片，并在 `0x143f88395` 调用销毁入口。巨石 Step 首先调用继承分派（`0x143f926eb`）。静态上可以建立“可破坏父行为”和“本体HP通知”两个处理段，但本轮没有运行验证继承销毁与后续事件之间的精确存活可见性／重入次序，不能写成固定的先退款后销毁。

**具体条件例：**构造刚创建巨石B，其 duration=20、HP=5。仅将HP改为0并让它到达该Step分支，比较成立，用户事件3请求产生；若父行为 can_broke门禁允许，也存在父碎裂与销毁请求路径。这个例子说明被破坏后的处理，不能解释为B已经等待二十回合，也不能声称 duration 已经减至0。

证据：[HP比较助手](../../../_reference/stoneshard-study/twelfth-expiry-0x14007b750.txt)、[用户事件包装](../../../_reference/stoneshard-study/twelfth-expiry-0x1451ef5b0.txt)、[父Step](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Object_c_broken_Step_0.txt)。

## 5. 字段引用扩大检索及其限制

前轮仅检索 `mov edx,[rip+disp32]`。本轮将第一PE代码节内的 RIP 相对 mov／lea 扩大到所有低位目的寄存器，保留552处 duration 元数据候选引用；最近登记函数仅作候选归属，尚不能证明控制流或所属实例。

与巨石最直接相关的现有两处仍是 Create 写20和抛投出生读取原 duration。共享回合、状态助手、skip_turn与临时属性助手虽有duration引用，实际对象选择与巨石不一致或尚未证明一致。`scr_turn`、`scr_global_turn_end`、`scr_characterTimeUpdate` 的选定首段也已解码，没有取得“巨石剩余回合→本体销毁”的新链。

这项检索不覆盖所有间接字段ID、字符串动态查找、所有高位寄存器编码、外部DLL、全部异常／冷代码或场景保存恢复。552是候选定位数，不是已解释函数数，更不是无到期算法的全程序证明。

证据：[扩大duration引用定位](../../../_reference/stoneshard-study/twelfth-expiry-duration-allreg-xrefs.json)、[回合结束入口](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Script_scr_global_turn_end.txt)、[角色时间更新](../../../_reference/stoneshard-study/twelfth-expiry-disassembly/gml_Script_scr_characterTimeUpdate.txt)。

## 6. 具体等待例子与到达销毁后的已知结果

构造一块Create后 duration=20、HP仍为正且没有被主动消费的巨石。在共享回合中只有单位 Buff 成员被选中递减时，不能据此计算本体20→19。即使构造连续20次这样的回合调用，也**没有已证明的本体变化量可以演算**。这是输入与覆盖边界明确的例子，不是实测二十回合不消失。

若另一未知入口确实使本体进入 Destroy，可复用46已闭合的后半段：结束 aura关联实例、移除wallgrid占格、条件退出副作用，CleanUp释放 aura列表容器。该后半段不依赖我们把原因叫“到期”，但到期时last_attacker取值和退出报复是否成立仍未知。主动抛投／爆破先写last_attacker=−4的证据也不能移植到未知到期入口。

独立实现建议是让退出原因与寿命显式：`LifetimeTurns`由指定逻辑时钟持有，递减与到期判定同属一个消费者；`Expired`、`DestroyedByDamage`、`ConsumedBySkill`分别决定来源与副作用，再共享占格／效果清理。是否采用20、是否被冻结、是否离屏更新应由自己的产品规格决定。

## 7. 本篇回答范围

已回答：本体补充事件与短空父事件、Buff寿命容器边界、HP门槛通知和可破坏父路径、一般Destroy/CleanUp可复用后半段。**仍未回答：巨石自动到期是否存在，以及它的完整调度、递减量、门槛和首次消费相位。**静态到期链没有闭合，后续最有效验证是独立记录同一实例的duration／HP、回合号与销毁原因；本轮没有执行该运行观察。

未做：游戏运行、内存观察、存档读写、修改或联网监测。剩余风险是把HP破坏当寿命、把用户事件调用当销毁、把Buff递减套到地图本体、或把有限负证据写成巨石永久存在。
