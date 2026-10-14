# 40．链式闪电的候选收集与下一跳传播

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [特殊技能候选](22-special-skill-candidates.md) · [反射](39-reflection-redirection-and-source-ownership.md) · [投射物](42-projectile-collision-and-target-changes.md)

后续跳数字段全代码节指定形式扩查与marker真实父链/时钟，见 [49 跳数与标记寿命](49-chain-lightning-hop-budget-and-marker-lifetime.md)。仍未恢复固定硬跳数，较广负证据不表示无限传播。

本章追真实 `Chain_Lightning`，把出生对象、命中事件、候选过滤、下一跳选择与新载体创建连通。**已核的下一跳不是任意附近单位：候选排除已有 chain_struck 状态、原 owner 和当前目标，距离不超过 8，并要求具有 Resonance 或 Impulse 对应状态。通过后按距离取更小值，创建一个新的同类载体。** 名义技能范围、传播距离、表现粒子数量和总跳数不能混为一谈。

本轮尚未恢复一个明确的总跳数上限。`count_of_bolts=0` 的初始化只证明初值；在所查本对象事件中没有找到它作为传播次数门禁。后续 damage 字段直接传递，也不能反推所有最终伤害都相同。下面分别说明正证据与未决部分。

## 1．制品、方法与实际对象

目标仍是 `E:/Steam/steamapps/common/Stoneshard` 的 GameMaker YYC x64 制品，EXE 首选基址 `0x140000000`：

| 文件 | SHA-256 |
|---|---|
| StoneShard.exe | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| data.win | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

本轮根节点已再次复核相同摘要。REA MCP/提供者缺失的限制沿用 00，没有 setup、联网或伪造 Evidence ID；用既有 PE/OBJT 索引与 Capstone 5.0.9 局部解码。字段名称指针位于引用地址减 8 字节；BSS 值不按零解释；完整登记段的字节解码不等于所有动态事件语义已恢复。

本轮选定 17 个含 chain_lightning/chain_struck 的登记入口，包括实际载体 Create、Collision、Alarm2/3、Other10/11/21 与出生对象。Other21/Draw 大部分是视觉表达，不据此扩大成额外逻辑命中。可选本机记录：[原生入口与覆盖](../../../_reference/stoneshard-study/eleventh-chain-native.json)、[原对象身份](../../../_reference/stoneshard-study/sixth-lightning-object-metadata.json)。

| 层次 | 真实身份与作用 |
|---|---|
| 配置 | `Chain_Lightning @ 0x145e4f8b0`，Object=`o_chain_lightning_birth`；Target Object、Range6、KD22、MP60、electromancy。都是表输入，非最终消耗实测 |
| 出生对象 | 5404/o_chain_lightning_birth，父5338/o_spellbirth；Create 在 `0x143f00544..0x143f0054e` 写 spell=9561 |
| 实际载体 | 9561/o_chain_lightning，父5296/o_shell_damage；父层继续到5291/o_shell |
| 已击中状态 | 1943/o_db_chain_struck，父5949/o_invisible_buff |
| 下一跳资格状态 | 4934/o_db_resonance、9587/o_db_impulse，父5904 |

## 2．首段创建与命中调度

出生 Other10 入口 `0x143f00970` 检查 `is_execute`、point/owner 存在等条件，实际把 `spell` 送入 `instance_create_depth`（字段 `0x143f00e37`，创建派发 `0x143f00eba`）。新对象得到 damage、name、owner、target、is_crit 等字段；对应拷贝可见 `0x143f00f11..0x143f01523`。该对象以自己的状态继续飞行，不能把创建对象等同于已经造成伤害。

载体 Create `0x1450edb00` 调 damage 初始化，并写 `count_of_bolts=0 @ 0x1450edd8c..0x1450eddba`。这个字段没有在本轮该载体其他已读事件中形成跳数上限。

载体自己的 `Collision_o_unit @ 0x1450ee960` 覆盖父层单位碰撞事件。其中反射调用 `0x1450eedd6` 的返回值写回 target（`0x1450eedec`）。若反射改变目标，已读分支会创建 chain_struck 状态在被碰撞的原对象上（`0x1450eef59`），然后走返回路径；它没有在此分支立刻对新目标造成伤害。

正常到达命中分支时，设置 `is_execute=true @ 0x1450ef13e`、`alarm[3]=1 @ 0x1450ef1ab`，并把 speed 设为0（`0x1450ef201`）。Alarm3 `0x1450ee5b0` 先创建表现（`0x1450ee6fa`），再派自身 user0/Other10（`0x1450ee70f`），随后销毁载体（`0x1450ee727`）。**这里的 1 是 Alarm 输入，不是游戏逻辑回合数或链跳上限。** 它与第 6 节的状态 duration 实参也是不同的时钟。

## 3．先结算当前段，再寻找下一跳

载体 Other10 `0x1450ef7e0` 先派自身 user1/Other11（`0x1450efcc9`），随后有 `live_call` 条件分支。以下结论限定进入已解静态主体的路径，不宣称运行时替换分支永不介入。

正常 owner 存在路径准备 Shock_Damage，普通有限数的第一段为：

```text
preparedShock = gameRound(10 × (100 + owner.Electromantic_Power) / 100)
```

字段/加100在 `0x1450efe8e..0x1450efed6`，除100 `0x1450efef1`、乘10 `0x1450eff1f`、round `0x1450effb7`、写 Shock_Damage `0x1450effd1`。之后还有 Magic_Power、Electromantic_Power 和暴击相关准备段，不能把 preparedShock 当最终 HP 扣除。

此主体在 `0x1450f04e9` 调 inherited Other10；已确认继承父5296/o_shell_damage，父事件会经过简单目标检查、buff/格挡门禁与 `scr_skill_damage @ 0x143e14a86`。随后链载体还有状态、被动、噪声等响应。盾牌格挡分支 `0x1450f08c4` 会跳过一段命中附带效果，直接接到候选收集前部；不能因此把格挡简单等同于全链立即停止。

当前目标的 chain_struck 创建在 `0x1450f1a51`：对象1943，duration输入1，target与owner参数均为当前目标，其他参数为未指定。它位于前述格挡跳过段内，不能写成任何结算路径都必定创建。新状态的 `stage=1`、`have_duration=true` 由其 Create `0x142fe2653..0x142fe26b6` 写入。状态命中与实际最终伤害成功是两种结论，不能把 marker 当“必定扣血”的证明。

## 4．候选收集的实际条件与数据表示

在当前载体上下文记 owner 为 O、当前已处理目标为 T。脚本创建候选数组，随后 with 常量3804/o_unit（`0x1450f1d6e..0x1450f1d9b`）。with 内 self 是候选 C、other 是链载体，不能把候选上的 id 和载体的 owner/target混读。

| 门禁 | 精确输入 | 证据 |
|---|---|---|
| 已标记排除 | C 的默认状态列表有1943/o_db_chain_struck则跳过 | `0x1450f1eb1/0x1450f1ec0` |
| owner排除 | C.id==载体.owner则跳过 | `0x1450f1ecd..0x1450f1f19` |
| 当前目标排除 | C.id==载体.target则跳过 | `0x1450f1f26..0x1450f1f72` |
| 传播距离 | `tile_distance(C.id,T,undefined)≤8` | `0x1450f208e`、比较 `0x1450f20b8/0x1450f20bf` |
| 特定状态资格 | 有4934/o_db_resonance **或** 9587/o_db_impulse | 两查询 `0x1450f2186/0x1450f2258`；OR分支 `0x1450f2284..0x1450f2291` |

通过才 `array_push`（`0x1450f2355`），一次追加两项：`C.id` 与距离。它是 `[id0,d0,id1,d1,…]` 的平坦成对数组，不是恢复出来的 `(对象结构,距离)` 数组。后续遍历步长2和 `i+1` 距离读取验证了这个表示。

这个已读候选循环没有显式阵营、目标 HP 或 fog/LOS 门禁。并不证明所有前置技能选择、状态产生和后续碰撞都忽略这些限制；这里只能把资格写成上述实际条件。没有状态的附近敌人，即使距离更近，也不进入这段下一跳列表。

## 5．下一跳取最小距离，平分保留先遇者

收集完成后，初始化最佳距离为100（`0x1450f23cc..0x1450f23d6`）、选中目标为−4（`0x1450f2408..0x1450f2412`）。数组长度查询 `0x1450f249a`，索引从0开始，以2递增（`0x1450f2e34`）。

每次从 `i+1` 取候选距离（`0x1450f25dd..0x1450f2686`），与 bestDistance 做严格较小比较（`0x1450f26c6..0x1450f26d6`）。只有更小时，才保存该项 id 和新距离（`0x1450f277b/0x1450f2798`）。因此普通有序数输入下是最小距离选择，同距后项不覆盖前项。实际 with/实例枚举顺序未恢复，不能把这个平分规则扩成稳定方向或随机选取。

同一循环还查询附近1827/o_ball_lightning（`0x1450f2984`），以26×其 tile_region_size 构造矩形并检查候选碰撞（`0x1450f2d1f`），累加一个局部计数。循环后与2比较并进入成就 helper（`0x1450f2e72..0x1450f2f23`）。这段局部计数没有作为最小距离比较的加分，也不是链跳次数。成就名称初始化未恢复，不凭条件猜具体成就。

```text
候选Pairs = []
对o_unit候选C：
  若有chain_struck，或C==O，或C==T：跳过
  d = tile_distance(C,T)
  若d>8：跳过
  若C既无Resonance状态也无Impulse状态：跳过
  追加C.id,d到平坦数组

bestDistance=100；nextTarget=−4
按成对数组遍历：
  若该距离严格小于bestDistance：保存id与距离
  另执行已核BallLightning相关计数，供后续独立分支使用
```

## 6．传播由新载体继续；marker与次数/衰减的边界

选中值真值门禁 `0x1450f32b9..0x1450f32c0` 通过后，在 T 的坐标创建当前载体的 `object_index`（`0x1450f330f..0x1450f3432`）。这不是再次使用同一个飞行实例，而是创建新的同类载体；随后复制旧载体 damage（`0x1450f34b7..0x1450f34ee`）、name、owner、is_crit，把 target设为选出的单位（`0x1450f3704`），并将 is_flying 写成 false（`0x1450f374f`）。初始化目标坐标/方向的调用在 `0x1450f3613..0x1450f3a57`。

在新载体创建段没有恢复出“每跳乘0.8”之类的衰减。damage字段直接拷贝；新的 Other10 还会按 owner 的属性重新准备伤害，再经过父层结算。不能据此说所有每跳 HP 伤害都相同，也不能凭 count_of_bolts 初值编造衰减曲线。

marker是单位状态，不是本次施法私有的 visited 数组。所查候选查询没有链 ID 参数，状态创建owner也是当前目标。因此本章只能确认“当前有该状态的单位被排除”，不能保证两次同时施法完全隔离、每个单位一生只中一次，或第二次施法一定不受第一次 marker 影响。

duration输入1要通过共享 `scr_effect_create` 与状态持续流程；共享实现有条件持续修正，不能把它直接标成“精确持续一帧/一回合”。chain_struck 自己的 Alarm2仅调 inherited，删除与 buffs 清理依赖父层/公共状态流程。参见 [11 状态生命周期](11-buffs-and-effects.md)。本轮未恢复它在所有退出、跨区和并发链下的完整清理协议。

没有有效下一跳时不创建新链载体；已处理的旧载体在 Alarm3 的 Other10返回后销毁。找不到候选会沿 owner是玩家的相关路径调用 `scr_allturn @ 0x1450f3c3a`；这是真实调用位置，不表示所有跳跃都独占一回合。

总次数的有界静态结论是：所查17入口中 `count_of_bolts` 只定位到初始化，没有形成总次数比较；传播受候选耗尽和当前 marker过滤约束。**未恢复明确的硬跳数上限，亦未证明全系统没有上限。** 外部调度、状态更新与 live_call 分支仍可能改变它。

## 7．贯通构造演算

构造首段目标T，施法者O；命中调度已通过，Alarm3进入静态 Other10主体。场上按枚举顺序有：

| 单位 | 距离T | 状态 | 是否收集 |
|---|---:|---|---|
| O | 1 | Resonance | owner排除 |
| A | 2 | chain_struck、Resonance | marker排除 |
| B | 5 | Resonance | 收集B,5 |
| C | 3 | Impulse | 收集C,3 |
| D | 3 | Resonance | 收集D,3 |
| E | 9 | Resonance | 距离排除 |
| F | 1 | 两种资格状态都没有 | 状态资格排除 |

得到 `[B,5,C,3,D,3]`。bestDistance从100变5，再变3；D同距不覆盖C。下一段从T位置创建新9561对象，复制owner/字段、target=C；旧载体随后销毁。若后续确实到达C并进入非格挡的marker创建路径，C会获得该状态；下一次候选查询将排除仍带marker的T/A/C，而不是回跳到最近的已标记单位。若格挡等分支跳过marker，不能沿用这个“不回跳”的前提。

若O.Electromantic_Power=50，则当前主体首段准备Shock为gameRound(15)=15；它不是最终扣血，也没有在传递段自动乘一个未恢复的衰减系数。这个演算不声称B/C/D的真实状态生成、枚举次序或下一段碰撞已经在游戏运行中观察。

## 8．自研借鉴、未做与风险

可独立设计链式效果的资格状态、邻接范围、同距策略、单链visited集合和明确跳数预算。原作在此用共享单位marker与成对数组；我们的实现是否采用这些表示应由并发施法、读档、调试需求决定。若需要稳定衰减，明确它作用于准备伤害还是最终伤害，并保留每跳来源。以上是自研建议，不是新增原作规则。

已确认身份、实际命中/事件桥、候选过滤、最小距离/平分、同类载体创建、字段传播与局部退出；部分确认marker生产与公共生命周期入口。总跳数硬上限、完整清理时钟、全部后处理伤害、动态调度频率与复杂障碍下的实际飞行仍未知。

未运行、附加、修改游戏或存档，未联网、setup、提交推送。纯研究文档未运行项目构建。主要风险是把表现数量当跳数、把状态duration输入当最终时间、把复制damage字段当最终等伤害，以及把局部距离候选当无墙体限制的命中保证。

已作本机地址、相对链接、UTF-8、围栏与构造算术核对；正文80个VA均匹配选定指令或明确资源来源。记录见 [两篇局部验证](../../../_reference/stoneshard-study/eleventh-chain-projectile-validation.json)、[链传播核对](../../../_reference/stoneshard-study/eleventh-chain-findings.json)、[对象事件绑定](../../../_reference/stoneshard-study/eleventh-chain-projectile-object-events.json)。这些检查不建立实战等价性。
