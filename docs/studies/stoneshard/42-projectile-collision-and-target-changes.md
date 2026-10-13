# 42．Fire Barrage 投射物：发射、飞行、碰撞与目标改变

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [反射与来源归属](39-reflection-redirection-and-source-ownership.md) · [攻击事件顺序](35-attack-results-and-event-order.md) · [链式闪电](40-chain-lightning-target-propagation.md)

本章选一个真实法术投射物 `Fire_Barrage → o_fire_barrage_birth → o_fire_barrage`。**它以目标实例和目标坐标维护飞行方向；目标消失时，子类会先在保存坐标创建终点代理，再调用父层飞行。单位碰撞只有当前目标匹配、尚未执行且靠近终点时才结算；反射改变目标则先保留投射物，后续 Step 再跟随新目标。** 这不是“撞上任意单位就立即命中”的已证实规则。

墙体、门、终点代理的事件与单位事件不同。本轮确认这些公共事件的门禁和派发，仍未恢复所有地图墙表示与选择阶段的遮挡算法，因此不保证任意墙都会在飞行阶段拦截。

## 1．制品、静态方法与覆盖

目标是同一 GameMaker YYC x64 制品，路径 `E:/Steam/steamapps/common/Stoneshard`；EXE首选基址 `0x140000000`：

| 文件 | SHA-256 |
|---|---|
| StoneShard.exe | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| data.win | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

根节点本轮再次复核摘要。REA MCP/provider不可用的记录沿用00，没有setup、联网或虚构Evidence。使用既有登记、PE节映射、OBJT与Capstone5.0.9解码26个入口，包括Fire Barrage自己的Create/Step/Destroy/Other10–12、出生事件及公共shell层。字段名由refVA−8名称指针恢复；BSS常量保持未知；不能把首个ret或首段.pdata当完整语义。

本机可选记录：[原生入口与覆盖](../../../_reference/stoneshard-study/eleventh-projectile-native.json)、[对象与继承](../../../_reference/stoneshard-study/eleventh-projectile-objects.json)、[原配置索引](../../../_reference/stoneshard-study/sixth-skill-config-inventory.json)。下述伪代码是重新组织的局部行为规格，不是原作恢复代码；算例是明示构造输入，不是游戏运行捕获。

## 2．真实配置、继承与事件责任

资源行 `Fire_Barrage @ 0x145e4ed20` 映射 `o_fire_barrage_birth`，Target Point、Range5、KD4、MP12、Bonus_Range1、pyromancy；这些是名义输入，不是实际最终扣费、冷却或飞行距离。

| ID | 对象 | 父对象 | OBJT偏移 |
|---:|---|---|---:|
| 5400 | o_fire_barrage_birth | 5338/o_spellbirth | 11093888 |
| 5397 | o_fire_barrage | 5296/o_shell_damage | 11092256 |
| 5296 | o_shell_damage | 5291/o_shell | 11048352 |
| 5291 | o_shell | 5290/o_spotlight | 11045008 |
| 5287 | o_attacked_target | -100/无 | 11042880 |
| 5286 | o_abstract_stuff | 5285 | 11042312 |
| 5289 | o_transitions_door | 3783 | 11043800 |

实际Fire Barrage对象有自己的Step与Destroy，不能只解shell父事件。其对象表没有自己的Collision事件；单位、stuff、终点代理、门的四项碰撞绑定位于shell：event type4分别指向3804/5286/5287/5289。

| 环节 | 真实事件与作用 |
|---|---|
| 出生 | birth.Other10准备point/first_target，调用父spellbirth创建spell实例 |
| 子类Step | target不存在时创建终点代理，然后调用inherited |
| 父shell.Step | 取目标mask中心、改direction/target_x/y、特定门类目标检测 |
| 单位碰撞 | 只处理当前target，带靠近终点与反射门禁，派user0 |
| Fire.Other10 | 自身附带逻辑，调用父shell_damage.Other10进行伤害流程 |
| 代理/门碰撞 | 派user1，走Fire.Other11的另一类效果路径 |
| Destroy | 释放父层责任，检查后续弹数量并可创建下一实例 |

## 3．发射不是已经命中：目标点、偏移与实例创建

`birth.Create @ 0x143efbe30` 先调用inherited（`0x143efbeaa`），随后写spell=5397（字段`0x143efbef8`，值`0x143efbf26`）。birth.Other10 `0x143efc490` 读取point并写first_target（`0x143efc5e6..0x143efc61d`），再走is_execute与owner/point存在等检查。

实际有 `scr_shoot_target_miss @ 0x143efc821`，输入包含point和owner.Spell_Hit_Chance（`0x143efc73c..0x143efc761`）。本轮没有恢复这个helper的完整概率、偏移和遮挡契约，不杜撰命中公式。相应返回坐标路径创建5287/o_attacked_target（创建派发`0x143efc991`），更新point与first_target（`0x143efc9cb..0x143efca02`）。所以first_target不一定永远是最初选中的活单位；可能在准备阶段变成终点代理。

随后 `0x143efcb8d` 调inherited Other10，实际父为o_spellbirth。父事件用当前spell创建实例，将owner、target、is_crit等拷入新对象（真实创建阶段与字段传递见`0x143e4c3c4..0x143e4c8ad`）。父层在相应条件下还会调用反射，并把返回值写回point（`0x143e4c164/0x143e4c17e`）；因此出生阶段最终point也不能一概等同于最初鼠标选中对象。

Fire子类出生在父创建之后还向spell实例传递first_target及相关坐标（`0x143efcc01..0x143efcd38`）。owner是施法来源，target是当前飞行目标，first_target是连发所保存的引用，target_x/y是坐标；四者不能合并。

### 实例初始化的可确认参数

`o_fire_barrage.Create @ 0x143ef0010` 调inherited（`0x143ef01b1`），故接入shell_damage与shell的创建责任。它写is_missile=true（`0x143ef0296..0x143ef02ca`）、can_reflect=true（`0x143ef0846..0x143ef0870`）、count_of_bolts=2（`0x143ef05fd..0x143ef0635`）。这些布尔真使用type0xD/value1。

speed由区间助手以6、8为输入（`0x143ef04bd..0x143ef04cd`），写入`0x143ef051a`。本章保留实际参数，不以此推游戏逻辑“一回合六至八格”；它是飞行实例speed字段，与逻辑回合、名义技能范围不同。本轮未重新证明该运行时随机助手的端点分布。

## 4．飞行与目标丢失：先子类，再父层

### 4.1 子类恢复一个坐标终点

Fire.Step `0x143ef1df0` 检查target实例存在（`0x143ef1f01`）。不存在时：

```text
proxy = 创建o_attacked_target(target_x,target_y,未恢复的depth输入)
target = proxy
调用inherited Step
```

创建常量5287在`0x143ef1fbe`，创建派发`0x143ef1ff4`，写target `0x143ef200a`；随后`0x143ef2026`调用父层。不能把未在文件初始化的depth槽当0。

这解释了一个具体取消边界：失去活目标不必在该子类Step直接消失，而可以继续飞向保存点。父shell.Step也有“target不存在则销毁”分支，但Fire已经先尝试替换；直接把父层规则套给本子类会漏掉终点代理。

### 4.2 父层按当前目标mask中心重定向

shell.Step `0x143dc4a40` 在target存在路径调用 `scr_findMaskCenter(target) @ 0x143dc4d6f`，取返回的两元素坐标数组，与投射物当前x/y计算方向（方向助手`0x143dc4f90`），写direction `0x143dc4fe3`，同时写target_x/y（`0x143dc506d/0x143dc50fe`）。因此可支持随当前目标位置更新飞行方向，而不是只在发射时固定一条向量。

这个Step没有在所读主体直接写`x += ...`或`y += ...`；位置推进通过GameMaker实例speed/direction运动机制。未运行目标时，不能量化实际帧间隔、碰撞引擎内部步进或高速漏碰概率。

若is_missile为真且`object_is_ancestor(target.object_index,9436/o_door_parent)`门禁通过，再用当前投射物坐标对target做collision_point（`0x143dc51e7..0x143dc5325`）；真时派user0/Other10（`0x143dc534d`），写is_execute=true，再销毁（`0x143dc53c7`）。这是门类目标的额外Step检测，不是所有终点代理共用的唯一结算方法。9436的OBJT父对象是7042；该常量来自真实浮点资源值与对象表，非由碰撞名猜门类型。

## 5．单位碰撞：当前目标、13像素门禁、反射与伤害入口

公共 `shell.Collision_o_unit @ 0x143dc5d50` 的顺序：

1. 碰撞对象U.id须等于投射物target（`0x143dc5e79..0x143dc5e97`），否则返回。
2. is_execute为真则返回（`0x143dc5e9d..0x143dc5eb6`）。
3. `point_distance(projectile.x,y,target_x,target_y)<13` 才继续（`0x143dc5fda..0x143dc5fee`）。这是像素点距，不能写成13格范围；数值helper容差边界仍保留。
4. 保存处理前target；can_reflect真时调用ReflectionTarget(target,undefined,undefined)，并把返回值写回target（`0x143dc60f9/0x143dc610f`）。
5. 新target与保存值相同才继续当前命中提交（`0x143dc6149..0x143dc6150`）。相异时返回，不在该碰撞事件派伤害，也不在该分支销毁。
6. 继续者派投射物user0/Other10（`0x143dc6169`），写is_execute=true（`0x143dc61a3`），再销毁（`0x143dc61d4`）。

Fire对象没有覆盖这个Collision，所以真实入口进入Fire自己的Other10。该事件先派自身user1（`0x143ef26b3`），准备Fire相关逻辑，随后在`0x143ef2b82`调用inherited Other10。父shell_damage事件实际调用简单目标检查（`0x143e144cb`）、buff调用（`0x143e14881`）、射击格挡概率（`0x143e1494a`）和 `scr_skill_damage @ 0x143e14a86`。调用存在并不保证每个门禁都通过，更不等于最终HP必扣某个固定数。

实际HP、攻击响应与死亡顺序见35。本章不重复完整伤害数值，也不把碰撞成功当攻击成功。

### 反射后的连续飞行

39已确认反射helper选择无封印的合格替代单位C，并记录C.reflection_attacker=旧目标T。这里can_reflect=true使它实际可被调用；返回C后目标比较改变，本次T碰撞的后续命中分支被跳过。后续Step若C仍存在，mask中心/方向计算采用C。因此静态链支持“先改目标，再飞向新目标”，而不是该碰撞处直接把伤害瞬移施加给C。

helper没有在此统一更改投射物owner；伤害归属中的reflection_attacker消费与清除是另一条规则，见39。双封印候选拒绝不等于全局递归深度保护。

## 6．环境、门与终点代理：不同事件不能当一种碰撞

| 碰撞对象 | 已读门禁 | 执行/退出 | VA |
|---|---|---|---|
| o_abstract_stuff | other.id==target，is_execute=false | user0；标记执行；销毁载体 | 比较`0x143dc66cc`；派发`0x143dc6704`；销毁`0x143dc6769` |
| o_transitions_door | other.id==target，is_execute=false | user1；标记执行；销毁载体 | 比较`0x143dc730c`；派发`0x143dc7347`；销毁`0x143dc73ac` |
| o_attacked_target | other.id==target，is_execute=false，点距<13 | user1；标记执行；销毁载体，继续相关代理清理 | 比较`0x143dc6a5d`；距离`0x143dc6bfb`；派发`0x143dc6c23`；销毁`0x143dc6c94` |

对Fire而言user1进入自己的Other11；其中有 `scr_create_fire_on_tile @ 0x143ef3f27` 和 `scr_skill_create_impact @ 0x143ef4252` 等条件路径。它不同于父层单位伤害入口，不宣称门、终点、单位必定收到相同伤害。

本轮没有把所有墙体资源关联到这几个父组，也未恢复tile墙、不可射击格以及 `scr_shoot_target_miss/scr_attack_tile_get_back_target` 的完整墙体处理。已读公共stuff/door事件要求碰撞对象就是当前target；它们不能支持“途中碰到任意墙都停”的结论，也不能反向支持“任意墙都可穿过”。选择/偏移阶段可能先把终点改为障碍对象，需要补实际障碍生产链才能回答。

## 7．销毁仍可能产生下一发；执行锁不是全局事务

Fire.Destroy `0x143ef1270` 先调inherited（`0x143ef1397`），连接shell.Destroy。父事件在所读player对象上下文把lock_movement清为布尔假（`0x143dc479c`）；它不是一个已证实的按本投射物token释放的锁列表协议。

子类Destroy检查count_of_bolts：真时派user2/Other12（`0x143ef163d`）。Other12先查is_created为真则退出（`0x143ef7134`），count_of_bolts真才继续（`0x143ef7161`），然后置is_created=true、数量减1（`0x143ef71a0/0x143ef7204`），在xstart/ystart创建同object_index（`0x143ef7383`），将damage、name、owner、first_target和递减后的count复制给新实例（`0x143ef741b..0x143ef7577`）。其后还有后方目标、偏移/命中点查询，不假设后续所有发都锁定当前反射目标。

因此一个载体被销毁，不等于整个Fire Barrage施法结束。正常构造成功链在初值2、每次只成功创建一子实例的前提下，剩余数量2→1→0，对应首发加两发后继；is_created门禁避免同一实例这段生产路径重复进入。创建失败、动态改值或别的事件路径会破坏这个演算前提，不能以此保证任何场景恰好三次命中。

当前碰撞事件的is_execute检查支持局部重复事件拒绝；它不保证所有回调原子提交。Other10/Other11内部仍可派其他事件甚至销毁自身；没有恢复一个全局状态事务或每个碰撞来源的统一幂等键。

Alarm2有直接销毁入口（`0x143ef1ccf`）；Create还设置相关Alarm。其最终时间单位和所有重写未闭合，不能把Alarm寿命当游戏回合数。继承父层Alarm0还有可见/表现逻辑，未将表现消失等同于所有逻辑结束。

## 8．一个贯通构造例与两个分支变化

构造owner=O、最终准备目标T存在，出生偏移/目标查询没有换掉T；新Fire实例P已创建，can_reflect=true、is_execute=false。假设某次Step返回的T.mask中心为(300,200)，P位置(294,200)，当前endpoint=(300,200)，碰撞引擎已经报告P与T相交。坐标是说明算法的输入，不是实战捕获。

1. P.Step读取T中心，更新direction与endpoint；位置实际推进由引擎运动机制完成。
2. 单位Collision确认U=T、尚未执行，点距为6<13。
3. 若T没有封印，helper返回T，目标不变。派Fire.Other10，再经父层门禁到技能伤害入口；之后标记执行并销毁P。P.Destroy在剩余数2且生产未执行的构造前提下派Other12，减为1并创建下一发。最终伤害量和命中成功未由这六像素输入决定。
4. 若T在P发射后、该次碰撞前获得封印，且helper选到合格C，则P.target=C，本次T的后续命中/销毁分支跳过。下一Step计算C的mask中心；只有后续实际到达、碰撞门禁成立并通过伤害许可才可能结算C。不会在步骤3的原碰撞时自动扣C生命。这样构造将出生阶段的可能反射与飞行后碰撞反射分开。
5. 若T在下次Step前消失，Fire子类在已保存endpoint创建5287代理并替换target，再交父层。到达这个代理走相应终点事件user1与退出；不能继续把失效T引用当活目标。

额外反例：P途中碰撞另一单位U且U.id!=P.target时，已读单位Collision直接返回。要证明游戏实际允许/禁止穿过这个U，还须结合碰撞引擎和发射前目标筛选，不能只从返回语句推出完整物理通行规则。

## 9．已回答、未知与独立设计建议

已确认真实配置/执行对象、出生父创建、实际字段传递、子类目标丢失处理、父层方向更新、单位与环境事件差异、反射后未即时结算的新目标、伤害父事件桥、销毁后后继生成的局部计数和防重复门禁。

未完成：miss/helper的完整概率与墙体算法；所有墙资源/碰撞组；引擎运动和高速碰撞内部细节；终点代理所有生命周期；每个Alarm的最终计时；所有取消/创建失败/退款路径；最终伤害与运行频率。名称、初始值、字段拷贝和事件存在均不替代这些答案。

自研可将“原始施法目标、当前追踪目标、静态终点、伤害来源、连发父任务”分开表示，分别处理追踪、丢目标、反射、环境碰撞和后继创建。应明确是碰撞任意单位、只碰当前目标，还是发射前选择首个阻挡者；再给每个载体设置执行/退出责任和后继预算。以上是独立设计建议，不是游戏已恢复的额外契约。

未启动、附加或改游戏，没有新读存档、联网、setup、提交推送。此次纯文档静态研究没有运行项目构建或实战测试。剩余风险是漏读子类Step，把collision回调等同于物理阻挡，把销毁等同整个技能结束，或把当前目标与owner/first_target混用；正文已逐项保留限制。

本机核对正文93个VA、相对链接、UTF-8、围栏和六像素/连发预算构造演算，未发现缺失。记录见 [两篇局部验证](../../../_reference/stoneshard-study/eleventh-chain-projectile-validation.json)、[投射物核对](../../../_reference/stoneshard-study/eleventh-projectile-findings.json)、[对象事件绑定](../../../_reference/stoneshard-study/eleventh-chain-projectile-object-events.json)。地址检查和独立算例不等于游戏运行测试。
