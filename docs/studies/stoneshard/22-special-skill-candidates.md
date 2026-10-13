# 值得继续研究的特殊技能

[返回拆解目录](README.md) · [证据范围](00-evidence-and-scope.md) · [已有位移与范围技能](21-arcane-tether-and-hooking-cut.md)

这是第六轮的候选记录。后续已推进 [36–39 控制与响应](36-control-overlap-and-action-locks.md)、[40 连锁](40-chain-lightning-target-propagation.md)、[42 投射物](42-projectile-collision-and-target-changes.md)、[46 巨石消费](46-combat-terrain-and-entity-consumption.md) 与 [47 盟友响应](47-ally-skills-and-group-response.md)。这些增量篇的具体事实和未知优先，候选阶段“待查”不表示现在仍全部只有入口。

本篇回答“除了已经研究的换位、猛踹、拉拽、移动攻击和 AOE，还有哪些特殊技能值得查”。这轮先筛选候选并核对关键入口，不将每个候选都展开成完整实现说明。下面使用配置中的英文键；中文机制描述不保证对应游戏界面的正式译名。

第十轮已继续展开 [36 控制锁](36-control-overlap-and-action-locks.md)、[37 预告取消](37-telegraph-interruption-and-cancellation.md)、[38 格挡响应](38-block-reactions-and-counterattack.md)、[39 反射重定向](39-reflection-redirection-and-source-ownership.md)。本篇保留候选阶段的记录；Stasis、Riposte/Deflect与封印的当前覆盖以增量篇为准，其余候选不会因同列出现就自动获得这些完整链证据。

目标仍是同一本机 GameMaker YYC x64 制品，EXE/data.win 的完整 SHA256 复核与 00 一致。开始时间为 2026-10-12 19:12:57 PDT（2026-10-13 02:12:57 UTC）。本轮限定枚举了技能表文本地址区间 `0x145e4b000–0x145e60000` 的 249 条匹配配置，再读取选定对象事件。249 是这次匹配行数，不是全部可用技能数，也不说明所有行仍在实际游戏中启用。

## 建议先研究哪些

以“给自己的游戏补充可复用战斗机制”为目标，建议先研究符文物体、连锁目标传播，以及反射/格挡响应。它们分别涉及世界实体、动态目标列表和事件顺序，能补上现有 10–21 尚未解释的结构。

| 候选组 | 特殊之处与借鉴价值 | 这轮已确认的局部内容 | 建议深查顺序 |
| --- | --- | --- | --- |
| Runic Boulder / Boulder Toss / Runic Explosion | 同类实体被多种技能操作，连接战斗与地形 | 巨石状态转换为抛投/爆破参数，随后消费巨石 | 优先，需补参数消费者及不同销毁原因 |
| Chain Lightning | 从一次选中扩展到多个后续目标 | 收集 `(id,距离)`，按已命中状态排除候选 | 优先，适合做目标传播规格 |
| Seal of Reflection | 状态改变效果目标与来源记录 | Buff 门禁、`reflection_attacker` 和目标实参改写 | 优先，调用者适用范围工作量较大 |
| Riposte / Deflect | 格挡等结果触发后续状态与冷却变化 | 结果字符串分支；属性、格挡恢复、冷却辅助调用 | 优先，可与反射共同研究事件排序 |
| Ball Lightning / Short Circuit | 有位置的法术实体、吸引和人数收益 | 空间登记、一格反向位移请求、局部人数伤害公式 | 第二批，结合已有位移/AOE 更容易推进 |
| Stasis | 行动门禁、退出清理和条件结算 | 持续状态创建；五类锁清理和发言状态恢复 | 第二批，控制状态体系价值高 |
| Astral Phantasm | 独立分身、外观复制和能力边界 | 防重复创建、独立召唤、动态 sprite 复制 | 有分身/召唤玩法时优先 |
| Stone Spikes | 出生、生成器、命中载体的多层结构 | 格对象/形状调用、持续输入、伤害与击退入口 | 地形控制玩法的第二批 |
| Befoul the Remains / Corpse Devourment | 死亡留下的实体参与下一次技能 | 标签查询与敌人创建；距离/坐标处理及 HP/MP 恢复 | 有尸体、亡灵或吞噬玩法时再查 |
| Tunnel Through / Dig In | 特殊移动与状态门禁的可能组合 | Tunnel Through 坐标变更和两个 Alarm 入口；Dig In 仍只是配置候选 | 特殊怪物移动方向 |
| Protect the Hive / Sic Em | 单位技能影响盟友与后续行动 | 前者查盟友目标并调用敌人技能类别冷却修改 | 敌人协作方向 |

表中的借鉴价值是我们的设计判断。具体机制证据、例子和缺口如下；完整适用技能、最终数值和实战频率仍需逐项闭合。

## 1. 符文巨石、抛投与爆破：技能操作世界实体

配置键是 `Runic_Boulder`、`Boulder_Toss`、`Runic_Explosion`，原表行分别是 `0x145e4f140 / 0x145e4f430 / 0x145e4f4d0`。Runic Boulder 出生代理的 `spell=5473`，实际创建 `o_runic_boulder`（`0x143f9c8b5–0x143f9c8ef`）。另外两个技能也实际检查目标是否为该巨石类型，关联已经超过名称线索。

抛投出生入口在新投射物上下文读取被选巨石 `duration`，将 `0.1×duration` 写入投射物 `add_damage`（`0x143f6a3fd–0x143f6a46f`）。爆破出生入口若 point 是巨石，将其 duration 复制给 impact；非巨石分支使用 3（`0x143f83204–0x143f8332e / 0x143f83c9b–0x143f83cbd`）。两者末段只对原目标的精确巨石类型写 `last_attacker=-4` 并销毁（`0x143f6a754 / 0x143f8427d`）。duration 的单位与消费者，以及 -4 对普通死亡效果的影响仍未知。

直接证据包括：`o_runic_boulder.Destroy` 在 `0x143f8c3c9` 调用 `scr_destroy_aura`，在 `0x143f8c5ee` 调用 `wallgrid_remove`，后续还有条件伤害入口 `0x143f8cd85`。抛投 Other 10 调用公共击退（`0x143f62d67`）；爆破 impact.Other 11 包含伤害（`0x143f7f038`）、击退（`0x143f7fa72`）和 MP 恢复（`0x143f7fd91`）入口。这些调用存在，不表示每次都进入其条件分支。

**局部构造例子**：被选巨石 duration=8 时，抛投初始化 `add_damage=0.8`，爆破初始化 impact.duration=8。非巨石的爆破局部分支使用 3。不能把这解释成多造成 80% 伤害或持续八回合；尚未核准字段语义和后处理。

**待验证例子**：先生成一块巨石，分别测试让它到期、对它抛投、对它爆破。记录参数消费、占位移除和退出副作用。已有消费巨石的指令证据，但未观察完整实战流程。

**为什么值得查**：可以学习一个世界实体怎样承载阻挡、技能目标、效果来源和退出结算。下一步查 duration 生产与消费、抛投/爆破选择条件、父层网格登记及不同销毁原因；尚未保证所有移除路径都会执行同一事件。

## 2. Chain Lightning：目标传播与防重复

资源行 `0x145e4f8b0` 映射 `o_chain_lightning_birth`。出生 Create 的 `spell=9561` 指向实际 `o_chain_lightning`；实体 Create 初始化 `count_of_bolts=0`，这不是跳数上限。

Other 10 在 `0x1450f1eb1` 查询候选是否含对象 1943 `o_db_chain_struck`，结果为真时跳过当前收集路径（`0x1450f1ec0`）。通过相关门禁后，调用距离助手（`0x1450f208e`），向数组追加候选 ID 与距离（`0x1450f2355`）。还不能据此说“每次选最近敌人”或“整个施法期间绝不会重复命中”。

**局部构造例子**：候选 A 在上述查询中返回含有 marker，候选 B 没有 marker 且通过距离门禁，则 A 跳过收集，而 B 的 `(id,距离)` 可进入列表。下一跳最终是否选择 B，取决于本轮尚未恢复的选择器。

**为什么值得查**：链式治疗、弹射箭、连锁伤害都需要候选过滤、下一跳选择和停止规则。下一问是跳数、距离边界、视线/阵营、排序/随机策略、伤害衰减，以及 marker 的创建、归属和移除时机。

## 3. Seal of Reflection：目标重定向与来源归属

资源行 `0x145e4ec70` 映射 `o_seal_of_reflection`。Alarm 0 用对象 3968 创建 `o_b_seal_reflection`（`0x143305e4c`）；`scr_skill_reflection` 也实际查询同一 Buff（`0x14039e2f0`），关联并非靠名称推测。

反射脚本包含距离、可见性和第二次 Buff 检查。在允许的局部分支，将原第一个实参写入候选的 `reflection_attacker`（`0x14039ee3c–0x14039ee79`），再把第一个实参改成候选 ID（`0x14039ee92–0x14039eede`）。这是目标引用与来源记录的改写证据，尚未证明任意攻击都会反弹，或反射总是返回最初施法者。

**局部构造例子**：输入实例存在且带 Buff3968，另一个候选通过后续门禁并进入改写分支，则候选记录原实例，目标实参变为该候选 ID。要把它解释为实际反射技能，还需证明调用者采用改写后的值。

**为什么值得查**：重定向会影响伤害归属、击杀、资源、仇恨和再次触发。下一步应选一个实际调用者，追到目标消费和最终效果；再选双方都有封印的例子，查循环防护。反射深度上限是可考虑的自研规则，尚未证明原游戏采用它。

## 4. Riposte / Deflect：格挡结果驱动的响应

配置行分别位于 `0x145e4c9a0` 和 `0x145e4dca0`，直接映射 `o_b_riposte` 和 `o_b_deflect`。这轮读取的是状态事件，不是恢复了每个技能从施放到攻击的全部过程。

Riposte.Other 13（入口 `0x14445cd10`）读取 `attack_result`，依次与 `block`、`fumbleBlock`、`critBlock` 比较，通过局部分支后调用冷却减少（`0x14445d272 / 0x14445d334`）以及临时属性修改（`0x14445d6ce`）。Deflect.Other 14（`0x14451bf20`）包含属性修改、格挡恢复（`0x14451c69f`）以及技能类别冷却修改（`0x14451c88d / 0x14451cb10`）。没有仅凭 Riposte 名称断言每次格挡必定额外攻击。

**局部构造例子**：在已读 Riposte 事件中，`attack_result="block"` 可通过第一项结果比较并进入后续响应主体；其他结果要继续检查另外两项，三项都不匹配时绕过该主体。冷却修改量、具体技能键和主体内后续条件未完全恢复。

**为什么值得查**：事件响应能组成“格挡收益、反击、重置冷却、资源返还”的玩法。下一步追 Other13/14 的派发者、行动结果产生者、作用对象和重入防护，才能确定响应相对受伤、死亡和反击的先后顺序。临时属性修改不能自动理解为永久加点。

## 5. Ball Lightning / Short Circuit：区域载体与人数收益

Ball Lightning 的出生 `spell=1827` 绑定实际 `o_ball_lightning`。Create 登记碰撞、灯光网格和 tile 区域（`0x142f85f40 / 0x142f85ffd / 0x142f86255`）。Other 10 的条件分支申请 `scr_cast_knockback(本体id,候选target,1,1,undefined)`（`0x142f8b7e5`）；结合 [19 公共击退](19-kick-pull-and-knockback.md)，这是向来源靠近一格的请求，仍受免疫、目标和阻挡约束。初始化 `duration=1` 不能当成最终寿命。

Short Circuit 的 birth.Create 使用 `spell=-4`，因此需追实际创建：birth.Other 10 在 `0x14336e685` 创建对象 8505 `o_short_circuit`。实体 Other 11 在 `0x144eb7f6c` 写入局部准备值：

```text
preparedShock = gameRound(8 × (100 + owner.Electromantic_Power) / 100)
                × (1 + 0.25 × enemy_count)
```

**构造演算**：EP=50、`enemy_count=3` 时，`gameRound(12)×1.75=21`。随后还存在 Magic Power / 暴击相关段和伤害调用，所以 21 不是已确定的最终扣血。Ball Lightning 的一格请求也不保证候选实际移动一格。

**为什么值得查**：可研究有位置的效果载体怎样脉冲、吸引和维持区域，以及目标数量如何改变局部强度。下一步确定持续重写、回合触发来源、目标计数范围、重复命中、最终伤害，以及载体退出后的网格/声音清理。逻辑脉冲与动画应分别核查。

## 6. Stasis：行动锁与退出效果

配置行 `0x145e4fc90` 指向 `o_stasis`。其 Alarm 0 根据 `is_crit` 向持续时间助手输入 3 或 6（`0x144c83622 / 0x144c8362c`），随后创建对象 361 `o_db_stasis`（`0x144c838a2`）。3/6 是修正器输入，不能直接标为最终回合数。

状态 Destroy（`0x142a4e770`）操作目标的 `lock_turn / lock_attack / lock_skills / lock_items / lock_spells` 五个列表，并恢复 `can_speak`。后续有条件伤害入口（`0x142a500a4`），尚不能说每次解除都必定造成伤害，也未证明冻结世界时钟。

**局部构造例子**：`is_crit=false` 的施法进入已读持续分支时，交给持续助手的基础输入为 3；状态走到对应 Destroy 清理分支时执行五类锁的删除。实际持续长度和删除索引来源仍待查。

**为什么值得查**：不同控制状态并存时，解除一个状态是否错误地解除了另一个，是值得验证的状态所有权问题。下一步补加锁入口、持续递减时钟、保存/读档、解除条件和退出伤害门禁。自研可以明确每个效果只释放自己持有的锁；这不等于原游戏已使用锁 token。

## 7. Astral Phantasm：独立分身与外观复制

配置行 `0x145e4fd00` 映射 `o_summon_astral_phantasm`。出生 Other 10 检查 `is_execute`，在有效 owner/point 路径调用 `scr_enemy_summon`，实体参数是对象 9346 `o_astral_phantasm`（`0x144e7e9c0`），随后写执行标记。

实际实体 Create 注册自己的技能/被动入口；Alarm 10 的玩家相关分支调用 `sprite_duplicate`，把结果写入 `sprite_index` 并置复制标记（`0x144ffb6c5–0x144ffb748`）。这是外观资源复制证据，不能扩成复制玩家全部装备、属性、技能和 AI。

**局部构造例子**：未执行的出生对象进入有效创建路径后被标记为已执行，再次进入同入口可跳过主要创建段；此处不保证首次共享召唤调用必定成功。实体若走到玩家外观分支，会产生单独的 sprite 资源。

**为什么值得查**：分身要划分外观、属性快照、能力配置和主人生命周期。下一步查属性白名单、技能注册键、行为决策、动态 sprite 的释放、主人死亡与跨区边界。实体 `distance_limit=2` 的消费者尚未恢复，不能直接说离主人两格就消失。

## 8. Stone Spikes：形状、生成器与命中分层

birth.Other 10 创建对象 5451 `o_stone_spikes_impact` 和对象 5456 `o_stone_spikes_spawner`（`0x143f5cea3 / 0x143f5d1cf`）。spawner.Other 10 调用格查询与形状助手（`0x143f5f680 / 0x143f5f7a5`）；两个返回值的真值门禁都为假才创建对象 9479 `o_stone_spikes_instance`（`0x143f5f956`）。新实体还复制 owner、通过持续修正器设置 duration；创建 y 参数的 +7 是像素偏移，不是七格范围。

impact.Other 11 调专用伤害准备（`0x143f59bb2`）、技能伤害（`0x143f59eb1`）和公共击退（`0x143f5a50d`）。因此伤害对象与实体生成对象确实分开；派发时序、空间登记和阻挡责任仍需继续核对。

**局部构造例子**：第一查询返回真时跳过创建；第一查询假但第二门禁真也跳过；二者都假才进入 9479 的创建段。尚未把查询的完整类型命名为“墙”“可走格”等规则。

**待验证例子**：在有单位和障碍的狭道施放，分别记录候选格、实际生成物、命中单位和结束后的通行性。当前入口证据不足以保证每个候选格都会长出尖刺，或每个尖刺都构成持久障碍。

**为什么值得查**：可以区分一次伤害的范围形状与留在地图上的状态实体。下一步应追生成对象、占位注册、持续递减、销毁清理和重叠尖刺规则，再与 [20 AOE](20-area-shapes-and-hit-selection.md) 的候选格算法连接。

## 9. 尸体利用：创建、恢复与消费是否同一过程

`Befoul_the_Remains` 配置行 `0x145e50800` 指向 `o_befoul_the_remains`。Other 10（`0x142951be0`）涉及 `corpse` 字段、按标签查找（`0x14295259a`）、敌人创建（`0x1429528ea`）、特殊销毁入口（`0x142952a2d`）和技能伤害（`0x1429532b6`）。谁被创建、谁被销毁以及尸体是否被消费，不能只由这些调用名确定。

`Corpse_Devourment` 配置行 `0x145e53790` 映射 `o_corpse_devourment`。Alarm 0 调距离助手（`0x1441097e4`）；一条路径做坐标变更（`0x1441099fa`），另一相关段有 HP/MP 恢复入口（`0x144109fed / 0x14410a0f1`）。尚未恢复完整目标过滤和移除过程。

**待验证例子**：同一具尸体先被一个施法对象选中，结算前再由另一效果操作；记录是否重新验证存在性、是否允许二次使用、恢复或生成效果是否还发生。没有运行此场景，不能宣称尸体是原子消费资源。

**为什么值得查**：死亡产物可以成为召唤、吞噬、范围效果的下一阶段输入，适合尸体玩法。下一步先核准真实 corpse 类型及引用，再追创建与销毁实参、无效目标、掉落与读档。`Dark_Ressurection` 只额外确认了配置至 `o_ressurection_birth`（`0x143e4e0c0`）的入口，完整复活规则尚未查。

## 10. Tunnel Through / Dig In：特殊移动与行为状态

`o_tunnel_through` 是对象 1013，父类 `o_moving_skill`。Alarm 10（`0x142d25c50`）设置入地动画（`0x142d2629f`）；Alarm 0（`0x142d24570`）从 owner.skill_move_coords 取索引 0/1，送给坐标变更（`0x142d24ae5`），再设置出地动画（`0x142d24e33`）。两项属性修改入口是 `0x142d25117 / 0x142d25289`。两个 Alarm 的真实调度顺序仍需追父层；坐标变更存在不等于穿墙、无敌、无法选中或忽略全部路径约束。

**局部构造例子**：若 owner.skill_move_coords=[299,195]，已读数组分支将二者交给坐标助手。坐标是否合法、是否检测途中墙体，是这个数组生产者和移动契约的问题，不能由该局部传参确定。

**待验证例子**：保持同样起终点，分别放置墙、另一单位和危险格，核对选择器是否接受、移动是否分阶段以及到达失败后怎样恢复状态。这些结果尚未观察。`Dig_In` 目前只作配置和事件名称候选，不与 Tunnel Through 合并成已确认的单一系统。

**为什么值得查**：特殊怪物位移常涉及选格、临时状态、占位、表现和取消。下一步查选择器、坐标参数来源、持续期、两个 Alarm 的派发关系与清理；确认实际状态责任后才能独立设计钻地/潜伏系统。

## 11. Protect the Hive / Sic Em：技能怎样影响盟友

`Protect_the_Hive` 配置行 `0x145e53180` 指向 `o_protect_the_hive`。Alarm 0（`0x14328ee00`）包含攻击调用，以及 `scr_enemy_find_ally_target`（`0x14328f5a4`）、敌人技能类别冷却修改（`0x14328f79f`）和属性修改（`0x14328f975`）。需要恢复实参，才能知道查询的是哪类盟友、改动谁以及改动什么技能类别。

`Sic_Em` 映射 `o_sic_em`（配置 `0x145e525b0`）；已读 Alarm 0 有效果创建（`0x1440e018f`）。仅凭名称和这条调用，不能说所有犬类会立即共享目标并行动。

**待验证例子**：一个使用技能的单位周围有同阵营单位、远处盟友和敌人，比较目标选择、状态或冷却变化，随后跟踪盟友下一次评分/决策。当前没有证明编队、统一指挥或无条件额外行动。

**为什么值得查**：这能给已有 [05 敌人协作](05-enemy-skills-cooperation.md) 补充具体技能，而非只研究通用士气。下一步核准盟友过滤、影响对象和状态消费者，再连接技能可用性与最终动作选择。

## 尚未深查的其他候选

资源中还出现 `Petrification`、`Arcane_Tether` 以外的 `Mana_Siphoning`、`Enough_For_Everyone`、`Bound_by_Blood`、`Oath_of_Protection`、`Lay_the_Eggs`、`Summon_the_Hive` 等键。适合分别问石化门禁、资源转移、连续目标、单位联结以及延后出生。这里的问题是调查方向，不能根据英文名宣称具体效果已经成立。

其中 Enough For Everyone 的 Alarm 0（`0x1440c9820`）已见 `is_attack / is_transit` 字段、攻击与效果调用，但切换条件和下一目标未闭合；可以作为下一批“连续攻击状态机”的候选。其余项目还需要先建立实际执行对象和消费者。

## 下一轮怎样做到可确定

建议一次选一组，把实际配置、创建参数、状态/目标选择、执行门禁、效果、退出清理连通，再验证一个能区分算法的场景。例如 Chain Lightning 用同距两候选和带 marker 的第三候选；反射用双方都带封印；Stasis 用两个控制状态重叠；符文物体用正常到期与被另一技能消费两条退出路径。场景是待验证设计，不是已发生的游戏观察。

若面向另一个游戏仓库，应先核对那个仓库的现有技能、效果和单位接口，再判断哪些机制需要独立实现。候选特殊、原实现层次多，不构成重构现有正常代码的充分理由。

## 本机证据、验证与未做

| 证据 | 本机可选记录 |
| --- | --- |
| 有界配置扫描 | [技能配置匹配行](../../../_reference/stoneshard-study/sixth-skill-config-inventory.json) |
| 闪电三技能 | [局部核对](../../../_reference/stoneshard-study/sixth-lightning-findings.md)、[原生入口与调用](../../../_reference/stoneshard-study/sixth-lightning-native.json)、[出生身份](../../../_reference/stoneshard-study/sixth-lightning-object-metadata.json) |
| 秘术、分身、反射 | [候选评估](../../../_reference/stoneshard-study/sixth-arcane-candidate-assessment.md)、[配置与对象](../../../_reference/stoneshard-study/sixth-arcane-config-and-objects.json)、[原生记录](../../../_reference/stoneshard-study/sixth-arcane-native.json) |
| 地形与特殊移动 | [局部核对](../../../_reference/stoneshard-study/sixth-terrain-findings.md)、[配置](../../../_reference/stoneshard-study/sixth-terrain-config-rows.json)、[对象](../../../_reference/stoneshard-study/sixth-terrain-objects.json)、[原生记录](../../../_reference/stoneshard-study/sixth-terrain-native.json) |
| 响应、尸体与盟友技能 | [选定原生事件](../../../_reference/stoneshard-study/sixth-special-native.json) |

本机证据仍是资源/PE 登记与 Capstone 5.0.9 静态解码，不是 REA Evidence 会话。部分记录只覆盖第一个登记的 `.pdata` 范围，完整指令解码也不代表动态派发和所有辅助函数已经恢复。被忽略的本机文件不会随仓库克隆，正文已保留关键事实、地址和限制。

已核对配置、实际出生身份及选定事件中的调用/读写，检查公式演算和文档链接；本机检查记录见 [文档与制品验证](../../../_reference/stoneshard-study/sixth-document-validation.json)。本轮没有启动、附加或修改游戏，没有读取新存档、观察实战回合或监测网络；筛选候选无需这些操作。没有运行 REA 构建和代码测试，因为此次只新增研究文档。

剩余风险是把局部准备值当最终伤害，把调用存在当实战频率，把名称当完整规则，或漏掉父层/其他退出路径。本篇已经逐项保留未知，交付的是值得深入的机制与下一问，不是全部技能的恢复代码或可直接出售的实现。
