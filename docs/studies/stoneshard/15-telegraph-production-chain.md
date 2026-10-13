# 预告攻击续查：准备状态生产、行动占用与投石落点结算

预告状态保存、离图与时钟的证据边界另见 [17 保存与逻辑时钟](17-persistence-and-clock-boundaries.md)。

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [前篇：拍地与投石](13-telegraphed-attacks.md) · [公共回合与伤害](14-combat-turns-and-damage.md) · [技能提交与 AI 门禁](16-skill-commit-and-ai-gates.md)

这篇补查 `o_shockwave` 与 `o_rock_toss` 的生产和释放边界。新增证据确认了出生效果如何创建持续状态、施法准备如何占用一次通常的敌人 AI 行动事件，以及投石终点碰撞如何触发预警格伤害。投石发射事件的上游派发、创建当轮是否先消费一次持续值，仍没有完整闭合。

## 1. 制品、证据层级与本轮覆盖

研究对象仍是 `E:\Steam\steamapps\common\Stoneshard` 中的 GameMaker Windows x64 原生制品。2026-10-11 16:26:55 PDT 的完整摘要复核与前轮相同：

| 制品 | SHA256 |
| --- | --- |
| StoneShard.exe | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| data.win | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

本篇复用第三轮对象、预告攻击与回合指令记录，沿问题选择出生效果父类、敌人行动事件、投射体父类碰撞、目标载体、动画阻挡与少量数值助手作增量核对。没有执行游戏、附加进程或修改游戏与存档。这里只确认选定路径，不能由登记数或解码文件数推导全游戏覆盖。

正文中的“指令确认”指具体参数、读写和可达分支；“资源确认”指对象继承与登记；“局部链确认”指这些事实可以连接起来，但不保证已经找齐上游入口和所有运行顺序。构造例子是算法演算。独立设计建议不代表目标原作者的实现。

可选的[本轮指令登记](../../../_reference/stoneshard-study/fourth-telegraph-native.json)、[对象资源索引](../../../_reference/stoneshard-study/third-telegraph-object-index.json)和后文反汇编链接仅在本机存在。本文保留必要的地址、参数和限制，可以独立阅读。记录来自本地 PE、资源与 Capstone 静态分析，不是 REA Evidence 会话对象。

## 2. 数据职责：出生效果、持续状态、预警格和终点是四种对象

| 对象 | 已确认职责 | 资源身份与继承 |
| --- | --- | --- |
| o_shockwave_birth / o_rock_toss_birth | 准备效果；配置待创建的 `spell`；在父事件执行后写施法者占用状态 | 两者继承 o_spellbirth，父对象 ID 5338 |
| o_shockwave / o_rock_toss | 保存多回合持续值，接收开始释放和取消事件 | ID 5515 / 5528；OBJT 绝对偏移 11145600 / 11151184；父类 5513 |
| o_aoe_spell_multiturn | 初始化 duration=2、is_movement=false | ID 5513；偏移 11144752；继承 o_aoe_spell（5337） |
| o_skill_aoe_zone | 保存预警位置、归属和结算用目标；执行时按自身坐标找占格对象 | ID 5677；偏移 11212992 |
| o_troll_rock | 飞行表现；命中终点事件会销毁投石状态 | ID 5529；偏移 11151968；父类 o_shell（5291） |
| o_attacked_target | 独立终点载体；被赋给飞行石头的 target | ID 5287；偏移 11042880；没有对象父类（-100） |
| o_animation_blocker | 表现阶段的临时阻挡对象 | ID 5635；偏移 11197920；与逻辑 duration 是不同状态 |

特别要区分三种 `target`：投石状态中可能是原目标单位；飞行石头中是创建出来的终点实例；预警格在执行时会把它改成该格此刻的对象。仅依据同名字段，无法判定整个技能持续追踪玩家。

`owner` 与 `main_owner` 也不同。正常结束、取消和格子去重经常按 `main_owner` 关联施法者，部分事件会改变当前 `owner`。这种关联目前没有恢复出独立的“每次攻击实例 ID”；多实例隔离不能默认成立。

## 3. 新确认的生产链：出生效果 → 持续状态

### 3.1 子类给出生效果填写具体状态对象

两个真实技能的出生 Create 都写入数值 `cast_frame=2`，随后配置 `spell`：

| 出生 Create | cast_frame 写入 | spell 写入 |
| --- | --- | --- |
| o_shockwave_birth，入口 0x143fed2b0 | 0x143fed5b5..5bf 写 2 | 0x143fed5f7..601 写 5515，即 o_shockwave |
| o_rock_toss_birth，入口 0x143ffb0f0 | 0x143ffb3f5..3ff 写 2 | 0x143ffb437 后写 5528，即 o_rock_toss |

这是对象 ID 常量与 OBJT 身份共同核对后的结果，不是根据技能名称猜测连接。技能注册和耗费见[16 技能提交与 AI 门禁](16-skill-commit-and-ai-gates.md)：巨魔 Create 登记 Shockwave / Rock_Toss，实际表行指定各自出生效果；共同敌人 Other11 调用 scr_enemy_cast_spell，其范围施法分支在 0x141866e11 调用 scr_cast_aoe_spell。巨魔自己的继承分派入口已知，中间父类的完整事件绑定和最上游触发仍未闭合，因此本篇不把共同脚本升级为完整巨魔行动轨迹。

### 3.2 父 Step 根据动画进度派发准备事件

两个子类 Step 均先继承父 Step，再把自身 visible 设为 false；它们隐藏自身绘制不等于停止父逻辑。例如投石继承派发在 0x143ffc294。

`o_spellbirth.Step`（0x143e4b100）读出生效果自己的 `image_index` 和 `cast_frame`。0x143e4b595 装载 0.5，在 0x143e4b59d 调用数值调整助手 0x14007b810；该助手的有限数值分支确为加法。随后比较 image_index 与 cast_frame+0.5，比较结果非负时在 0x143e4b5f6 派发 user0，即 Other10。

对本例初值 2，门槛是 **2.5 的动画进度**。这不是“等待 2.5 回合”。有限 double 比较允许 1e-5 的接近相等范围，因此精确说法是“达到或近似达到 2.5”，不能不加条件地写成数学上的严格 `image_index>=2.5`。

还有第二入口：父类 `o_spellbirth.Other7`（动画结束事件，0x143e4d700）在 0x143e4d74c 派发 user0，随后在 0x143e4d764 销毁出生效果。两条事件入口都可进入准备事件；静态证据没有证明实际播放每次一定先经过哪条。

### 3.3 父 Other10 确实创建具体持续状态，并有重复执行门禁

子类准备 Other10 的第一段是继承派发：冲击波在 0x143fee1fa，投石在 0x143ffc64e。父类 `o_spellbirth.Other10`（0x143e4be50）有以下局部路径：

~~~text
若出生效果 is_execute 为真：退出父逻辑
若玩家对象 5376 不存在：退出父逻辑
若出生效果 point 实例不存在：退出父逻辑
继续相应反射/位置分支
把出生效果 is_execute 写成 true
读取出生效果 spell 对象 ID
以该对象 ID 调用 instance_create_depth
在新实例上下文继续设置 damage、direction、owner、target 等字段
~~~

门禁地址为 0x143e4bff0..ff7、0x143e4c011..018、0x143e4c05b..062；`is_execute=true` 写入在 0x143e4c35f；读取 `spell` 在 0x143e4c3c4；创建调用在 **0x143e4c436**，第 4 参数是刚读出的 spell。

因此，从这两个 birth 的配置到持续状态 5515/5528 的生产链已闭合。创建后的具体字段赋值仍有反射、目标位置、上下文切换等分支，不宜将所有新实例都概括成“无条件出生在施法者脚下”。

重复门禁的边界也要保留：`is_execute` 阻止的是**父逻辑重复生产状态**。子类在继承调用之后仍有自己的写入；不能据此声称整个子类 Other10 被幂等地跳过，或绝不再次刷新缓存和 owner 状态。

可选证据：[父 Step](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Object_o_spellbirth_Step_0.txt)、[父 Other10](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Object_o_spellbirth_Other_10.txt)、[冲击波 Create](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Object_o_shockwave_birth_Create_0.txt)、[投石 Create](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Object_o_rock_toss_birth_Create_0.txt)。

### 构造演算：准备效果重复经过动画门槛

设出生效果可见路径仍保留 cast_frame=2，玩家与 point 存在，父事件其他门禁通过：

| image_index | 与 2.5 的比较 | 父生产结果 |
| --- | --- | --- |
| 2.0 | 未达到 | 此 Step 不派发准备事件 |
| 2.5 | 相等 | 派发 Other10；is_execute 原为 false 时创建状态，并先写 true |
| 3.0 | 超过 | 可以再次派发 Other10；父 is_execute 门禁阻止重复创建 |
| 动画结束 | 不依赖上述 Step 比较 | 父 Other7 再派发 Other10，然后销毁出生效果 |

表内进度是假设输入，不是本机播放捕获。父 Step 不可见分支还会修改 image_speed 和 cast_frame，子类后续副作用也没有被父门禁全部覆盖。

## 4. 新确认的行动占用：一个计数门禁跳过正常选招

准备 Other10 在 owner 上写入 **is_cast_spell=1**：冲击波在 0x143fee291..298，投石在 0x143ffc6e1..6e8。它是数值 1，与多回合状态的 skill_duration=2 是两份计数。

`o_enemy.Other10`（0x14364a890）的相应分支先重置 is_use_skill，然后在 0x14364b2d3 读取 is_cast_spell：

~~~text
若 is_cast_spell 真值为真：
    在其数值路径把 is_cast_spell 减 1
    跳到共同尾部
否则：
    检查 ai_is_on
    执行对应通常选招/状态流程
共同尾部继续其他维护
~~~

数值递减在 0x14364b330；0x14364b341 跳往 0x14364b7de。它绕过 false 路径中的通常选招 `script_execute(scr_enemy_choose_state_new)`（0x14364b65d）和 `scr_update_FSM_new`（0x14364b719）。

所以在这个事件消费点，以 1 进入时，结果是 0，且本次通常 AI 选招不执行。它不是“整帧什么也不做”：此前已经有感知、缓存等处理，跳转后还有共同维护。

古代巨魔自己的 Other10（0x1437c5340）在 0x1437c59c5 执行继承事件；OBJT 继承链是 ancientTroll → Omnivore → enemy → unit。当前局部核对能说明它有继承入口，以及共同敌人事件的消费规则；没有把每个资源事件绑定和所有运行派发都恢复成一条已观测的行动轨迹。

**已回答：**施法准备设置了会占用通常选招的一次事件计数。**未回答：**它一定是玩家画面中的哪一回合、出生效果重复写 1 的期间是否先发生消费、是否还有其他入口继续执行特殊行为。若计数消费前又被写回 1，简单的“只占用下一次且绝不更多”结论便不充分。

可选证据：[敌人行动事件](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Object_o_enemy_Other_10.txt)、[巨魔行动继承入口](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Object_o_ancientTroll_Other_10.txt)。

## 5. 预警格生产与位置：当前能闭合的具体接口

### 5.1 单格生产器的输入与输出

`scr_create_one_aoe`（0x141858d60）的确认片段从参数 2 读 x/y，在 0x14185921b 用对象 ID **5677** 调用 instance_create_depth。输出为一个 o_skill_aoe_zone。随后有这些字段赋值：

| 输入 | 新格子字段 | 关键地址 |
| --- | --- | --- |
| 参数 0 | owner | 0x14185924f 后的赋值路径 |
| 参数 1 | shift_angle | 0x141859466 |
| 参数 2 | main_owner；初始 x/y 来源也在该对象上 | 0x1418594c4；x/y 读取 0x141859161 / 193 |
| 参数 3 | is_moving | 0x141859522 |
| 参数 4 | is_start_shift | 0x141859580 |

参数号从 0 开始。缺少参数会进入 undefined 默认路径，因此这是一份需要调用者提供有效状态的接口，不是所有参数都可随意省略的完整自研 API。

范围生产器 `scr_create_aoe`（0x141851c10）有多条调用单格生产器的路径，例如 0x14185357c、0x141853742、0x141853951；`scr_cast_aoe_spell`（0x14186fd70）在 0x141870b64、0x141870ca2 调用范围生产器。这确认了复用关系。该范围施法脚本的相关路径先创建范围格，随后按技能表 Object 创建出生效果（0x1418711e2），绑定 owner（0x141871299），调用 startcast（0x1418714c2）。这补上了“格子已经存在，再由出生效果把实际持续状态生产出来”的局部顺序；尚不能据此确定第一次 global_turn_end 的消费相位。

**目前没有把巨魔两个技能的完整形状参数和活跃调用分支接到所有这些接口上**，不能据此给它们编造固定扇形宽度、3×3 范围或具体格数。16 记录的表行 AOE_Lenght / AOE_Width 和 Pattern 是真实配置，配置数值并不自动等于最终格子集合；后者仍需恢复范围生成的具体分支。

可选证据：[单格生产器](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Script_scr_create_one_aoe.txt)、[范围生产器](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Script_scr_create_aoe.txt)、[范围施法调用](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Script_scr_cast_aoe_spell.txt)、[新增提交与出生创建核对](../../../_reference/stoneshard-study/fourth-commit-disassembly/gml_Script_scr_cast_aoe_spell.txt)。

### 5.2 冲击波表现格直接复用已有预警坐标

冲击波 birth.Other10 在继承生产和 owner 设置之后，遍历已有 o_skill_aoe_zone；比较 main_owner==other.owner（0x143fee764），匹配后按格子 x/y 创建 o_shockwave_tile（0x143fee898）。这闭合了**该层表现格与预警位置的共同来源**。

但它读取的是“此刻已有格子”，并非在这个事件里恢复完整范围生成。格子 Step 存在 owner/main_owner、is_moving、is_activate 等门禁；例如 0x14415a2e7 在 is_activate 为真时跳过一段目标准备路径。由此不能证明两个技能所有格子在出生之后都永久固定，也不能证明贴图每个可见像素都等于命中区域。

### 5.3 投石的新发现：point 缓存确实来自目标位置

投石 birth.Other10 在 0x143ffc954 装载 5528，遍历投石状态。每个被选状态的 target 存在时（0x143ffca17），执行：

~~~text
状态.point_x ← 状态.target.x  // 赋值 0x143ffca83
状态.point_y ← 状态.target.y  // 赋值 0x143ffcaf1
~~~

因此不能只根据 Create 的初值，认为 point 永远是状态出生坐标。准备阶段已经有实际目标位置复制。

该循环在所核对片段中按对象类型 5528 遍历，未见同一次施法实例 ID 的筛选门禁。这是覆盖到的实际行为，不能擅自改写为“只更新本次新建的那个实例”；多投石状态同时存在时的真实影响还需验证。

释放开始的 Other11 还把现存目标的位置刷新到 target_x/y（0x143fff9fc / 0x143fffa6c）。**刷新 target_x/y 不等于刷新 point_x/y。** Other14 中随后在 0x144001498 按 point_x/y 创建 o_attacked_target，把它的实例身份赋给新石头 target（0x1440014b2）。该事件有条件分支和网格操作，不可省略后直接声称所有路径都永不调整终点。

可选证据：[投石准备与 point 写入](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_rock_toss_birth_Other_10.txt)、[投石发射事件](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_rock_toss_Other_14.txt)。

## 6. 新闭合的投石链：朝终点飞行 → 终点碰撞 → 格子伤害

### 6.1 飞行方向更新所追踪的是终点实例

投石 Other14 从 owner 的 x/y 创建 o_troll_rock（0x1440012f7），再创建前节的独立终点并绑定 target。石头自己的 Step 在 0x1440035ea 先执行 o_shell 的父 Step。

父 Step（0x143dc4a40）检查 target 存在性（0x143dc4ce3）。目标不存在的对应路径在 0x143dc4eb0 销毁石头；存在时在 0x143dc4d6f 调用 scr_findMaskCenter(target)，把所得中心坐标送入方向助手，并在 0x143dc4fe3 写 direction。它还更新石头 target_x/y（0x143dc506d / 0x143dc50fe）。

这说明飞行对象随 Step 重读**它的 target 载体**，不是在此处重读“原玩家 ID”。方向助手的完整角度数值算法尚未恢复；目前只能确认这些坐标输入和 direction 输出。o_attacked_target 的已核对 Step2（0x143dbaf80）调用表现位置更新脚本，没有直接向自身 x/y 写入玩家坐标。尚未检索所有外部写入，故不升级为全局不动保证。

石头自己的后续表现规则仍是 image_angle+=speed、speed=lerp(speed,15,0.05)。这些是每次 Step 的表现参数，不是回合计数。

### 6.2 真正的终点碰撞事件及门槛

本轮新增的关键入口是父类 **o_shell.Collision_o_attacked_target，0x143dc68e0**。它有明确的条件和顺序：

1. 在 0x143dc6a5d 比较石头 target 与碰撞对象 other.id；不同则跳过。
2. 在 0x143dc6a80 判断 is_execute；已执行则跳过。
3. 在 0x143dc6bee 调用 point_distance，输入是石头 x/y 和其 target 的 x/y。
4. 在 0x143dc6bfb 把距离送入助手 0x140089b20，整数参数为 **13**；条件成立才继续。
5. 在 0x143dc6c23 派发 user1，即石头自己的 Other11。
6. 在 0x143dc6c5e 写 is_execute=true，0x143dc6c94 销毁石头；还给被选终点设置 alarm[0]=room_speed（0x143dc6d5b）。

有限 double 比较的数值路径已进一步核对：运行时比较助手 0x1451cddb0 的类型组合 0x00 经两个跳表到 0x1451cdf1b；它计算 a-b，绝对差不大于 epsilon 时返回 0，否则负差返回 -1、正差返回 1。此处 epsilon 来自 0x149769ff0，值为 **0.00001**。

0x140089b20 接受负结果且排除 -2。因此有限 double 距离的命中门槛可表达为 `distance-13 < -epsilon`，即显著小于 13；边界的浮点舍入仍按机器结果。不能写成“碰撞立刻命中”或无条件数学严格 `<13`，也没有在此覆盖 NaN、字符串和其他动态类型。

要避免另一个容易混同的入口：父 Step 在 0x143dc5325 调用 collision_point 的分支还要求 is_missile 为真、目标属于 **o_door_parent（9436）**。它不是上述 o_attacked_target 的通常落点路径；不能拿这个分支替代真正的终点碰撞证据。

### 6.3 碰撞事件连接到伤害；飞行石头本身不直接逐格扣血

终点碰撞派发的 o_troll_rock.Other11（0x144003b50）遍历 **o_rock_toss（5528）**，在 0x144003dae 销毁状态。接下来沿已核对父类路径：

~~~text
石头终点碰撞
→ 石头 Other11
→ 投石状态销毁
→ o_aoe_spell.Destroy 筛选同 main_owner 的预警格
→ 预警格 alarm[1]=1
→ 预警格 Alarm1：iteration++、Other11
→ 用预警格当前 x/y 查询当前对象、去重
→ 用预警格上下文派发所选技能 Other10
→ 父 o_aoe_spell.Other10 调用 scr_skill_damage
~~~

主要后半段地址是父 Destroy 写 alarm @0x143e48dc5、格子 Alarm1 派发 @0x144159c3c、按格查询 @0x14416396e、按 spell 派发 @0x1441648d0、公共伤害调用 @0x143e497ec。

这是**表现运动和逻辑结算确实相连**的具体链。它不意味着当前玩家只要碰到石头贴图便受伤；最终占格对象来自预警格执行时的查询。并且石头 Other11 的类型遍历片段没有本次攻击实例过滤，不能默认为只销毁其唯一关联状态。

可选证据：[终点碰撞](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Object_o_shell_Collision_o_attacked_target.txt)、[飞行父 Step](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_shell_Step_0.txt)、[石头 Other11](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_troll_rock_Other_11.txt)、[有限数值比较及跳表](../../../_reference/stoneshard-study/fourth-telegraph-compare-route.json)、[比较助手](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/runtime_RValue_compare_prefix.txt)。

### 构造演算：到终点附近才执行

假设石头 target 指向终点 Q，Collision 已发生，is_execute=false，距离返回有限 double：

| 距离 | distance-13 | 比较结果及行为 |
| --- | --- | --- |
| 20 | 7 | 正；不派发落点结算 |
| 13 | 0 | 相等；不派发 |
| 12.999995 | -0.000005 | epsilon 内视为相等；不派发 |
| 12.5 | -0.5 | 负；派发 Other11，再写已执行并清理 |

若碰撞的是另一个终点 R，身份不匹配便在第一道门禁结束，与距离是否小于 13 无关。门槛单位来自对象空间坐标，未核定为格、米或其他物理单位。

再设准备时目标 P 位于 (260,182)，birth 写 point=(260,182)；释放前 P 已移到 (286,182)，Other11 把 target_x/y 刷新为新位置，而 point 未再被其他入口改写。则 Other14 创建的终点仍来自旧 point。这里“point 未再改写”是**构造假设**，不是永久锁格的已证结论。最终命中还要看执行时预警格的位置和占格对象，不能只看这个终点坐标。

## 7. 冲击波释放与动画阻挡的已知边界

冲击波逻辑归零进入 Other11 后写 alarm[1]=20（0x143ff2d3f）；Alarm1 在 0x143ff0c5e 派发 user4/Other14。Other14 在 0x143ff3d37 销毁状态；自己的 Destroy 在 0x143ff0b91 继承父 Destroy，接到第 6 节格子结算链。这条释放桥已闭合，alarm20 的实际帧率与毫秒转换未核对。

投石 Other11 写 alarm[1] 的值来自 7/sprite_get_speed（0x143fffdbf、0x143fffde9、0x143fffe37），但自己的 Alarm1 没有发射主体。**本轮仍未找到从实际巨魔动画控制到投石 Other14 的完整派发桥。**不能把这个 alarm 值写成“警报到期直接发射”，也不能把 AnimationEnd 名称当成已经证实的投石发射 caller。

另一个可核对的表现状态是动画阻挡：石头 Create 在 0x144003080 调用 scr_animation_blocker_create，Destroy 在 0x14400338a 调用删除助手。创建助手 0x141dacb70 创建 o_animation_blocker（调用 0x141dad02e），设置其 owner（0x141dad10d）；选中归属实例后把 lock_movement 写为 false（0x141dad1a2）。阻挡对象 Alarm0 在 0x14413071c 同样清除归属实例 lock_movement，然后销毁自己（0x14413076a）。

这里名称容易误导：虽然对象叫 animation_blocker，已核对字段写入却是 lock_movement=false。不能仅凭名称声称它把施法者锁定几回合，或把它等同前节 is_cast_spell 的选招占用。scr_skill_set_animation（0x1414132b0）另有 argument2 与 HP 门禁后创建阻挡的路径（0x141413afb），也不能脱离具体调用参数认定任何技能动画都会执行它。

可选证据：[创建助手](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Script_scr_animation_blocker_create.txt)、[阻挡 Alarm0](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Object_o_animation_blocker_Alarm_0.txt)、[动画设置](../../../_reference/stoneshard-study/fourth-telegraph-disassembly/gml_Script_scr_skill_set_animation.txt)。

## 8. 创建首消费、控制、死亡和离图：明确回答范围

| 问题 | 当前结论 | 未闭合部分 |
| --- | --- | --- |
| 创建后怎样开始持续计数？ | 出生父事件生产状态；其父 Create 初始化 2；scr_global_turn_end 对 5513 消费并在归零派发 Other11 | 出生动画生产与第一次 global_turn_end 的运行先后 |
| 是本回合预警、下一回合攻击吗？ | 已证两个成功的 duration 消费点；已证准备写一次通常选招占用计数 | 玩家输入、敌人事件、两个消费点和动画释放的精确相位 |
| 怎样中断？ | global_turn_end 的 owner 不存在、匹配类别锁等分支先 Other12，再销毁状态 | class 初始化值、所有控制效果怎样填锁列表、动画期间其他中断入口 |
| owner 死了会立即取消吗？ | owner 实例不存在时会走公共取消；巨魔 Destroy 调删除动画阻挡（0x1437bb5cd） | HP 归零至实例销毁的完整顺序，以及是否另有直接取消待发状态的分支 |
| lock_turn 非空必定取消吗？ | 该分支还要求 is_movement；两个状态父 Create 写 false | 其他阶段是否另有门禁，不可由此推导免疫所有控制 |
| 取消会让预警格继续伤害吗？ | 技能 Other12 先筛选归属格并销毁；冲击波 @0x143ff359f，投石 @0x144000605，再由公共入口销毁状态 | 同类型多实例、表现残留和所有异常清理组合 |
| 离开地图会怎样？ | 本轮没有恢复地图切换、持久化和 RoomEnd 的完整生产/销毁链 | 是否持久保存待释放状态、切图是否强制取消、跨房间 owner 查找语义 |
| 飞行终点不存在？ | o_shell.Step 对 target 不存在的对应分支销毁石头 | 此异常销毁是否还通过其他事件取消或结算待发状态；不能自动等同取消 |

公共入口的确切锚点是 scr_unitTurnBreak 中 0x14169abf5 调用 global_turn_end，后续 0x14169d82f 调用 global_turn。它们之间有大量分支和单位维护。出生效果在动画 Step 中创建状态，所以仅比较两条调用的地址，不能证明新状态已经在前者之前出现。相关[本机公共入口](../../../_reference/stoneshard-study/third-turn-damage-disassembly/scr_unitTurnBreak.txt)保留这个边界。

最小运行核对可以只记录一次巨魔对应技能：birth 出现、持续状态创建、首两次 global_turn_end 的 duration、owner.is_cast_spell 消费、投石 Other14、终点碰撞和预警格执行的先后。分别在预警期间、发射前后移动，以及 owner 受控/死亡/离图，才能区分锁格、取消和表现延迟。当前未采集这些运行时序。

## 9. 对我们独立实现的启发

以下是自研建议，与目标算法的证据分开：

- 用明确的 AttackPlan 保存受影响格、唯一施法 ID、归属、释放逻辑回合和阶段。目标已见类型遍历与 main_owner 关联，但未证明有这种每次攻击唯一标识。
- 把“预警随目标更新”“达到锁定时刻后固定”“发射后飞向独立终点”写为显式策略。目标存在 point、target_x/y、终点 target 和预警格 x/y 多份数据；自研实现应说明哪份有权改最终命中区域。
- 用一次独立行动额度表达蓄力占用，避免用可重复写入的动画回调隐式重置计数。目标局部证据显示准备写 1、通常 AI 事件消费，但没有证明所有相位。
- 由逻辑状态机决定 Resolve 或 Cancel，再让动画发出可幂等处理的完成通知。目标投石的真实链由碰撞和对象销毁转入格子结算；自研可以保留表现同步，同时明确异常终点丢失、施法者消失、切图时的策略。
- 把伤害范围和提示范围共享到同一格集合，并记录 resolved/cancelled。目标冲击波表现复用预警坐标，最终按格查询，但完整生成形状与全像素一致性仍待查。

这些规格要由我们的玩法需求决定；不会把目标事件代码、资源或参数表翻译成生产实现。

## 10. 关键证据表与验证

| 声明 | 入口或精确位置 | 证据强度 |
| --- | --- | --- |
| 两个 birth 的具体状态对象 | Shockwave spell @0x143fed5f7；Rock spell @0x143ffb437 | 指令 + 对象资源 |
| 动画准备门槛 2+0.5 | 父 Step @0x143e4b59d；派发 @0x143e4b5f6；加法助手 @0x14007b83f | 数值路径指令 |
| 父准备只生产一次状态 | is_execute 读 @0x143e4bff0、写 @0x143e4c35f；创建 @0x143e4c436 | 局部控制流；不覆盖子类全部副作用 |
| 准备占用通常选招 | birth 写 1 @0x143fee298 / 0x143ffc6e8；敌人递减 @0x14364b330、跳转 @0x14364b341 | 局部控制流；非运行回合观察 |
| 单格接口生产 5677 | scr_create_one_aoe @0x14185921b；main_owner 写 @0x1418594c4 | 接口指令；boss 全形状未闭合 |
| 范围格之后创建出生效果 | scr_cast_aoe_spell 范围调用 @0x141870b64 / ca2；出生创建 @0x1418711e2；startcast @0x1418714c2 | 复用 16 的局部创建路径；首回合相位未知 |
| 投石 point 复制 target.x/y | @0x143ffca83 / 0x143ffcaf1 | 指令确认 |
| 独立终点及绑定 | Other14 创建 @0x144001498；target 写 @0x1440014b2 | 指令确认；上游派发未知 |
| 终点身份、执行门禁、距离 | Collision @0x143dc6a5d / 6a80 / 6bee / 6bfb | 局部控制流 |
| 有限 double 的距离门槛 | 类型跳表到0x1451cdf1b；epsilon @0x149769ff0；返回 @0x1451ce436 | 指令 + 常量；其他动态类型未覆盖 |
| 碰撞连接状态销毁 | user1 @0x143dc6c23；石头 Other11 销毁状态 @0x144003dae | 局部链确认 |
| 状态销毁连接预警格伤害 | 父 Destroy @0x143e48dc5；格派发 @0x1441648d0；damage @0x143e497ec | 复用前轮已核对链 |
| 首消费顺序仍未知 | birth 生产 @0x143e4c436 与公共调用 @0x14169abf5 | 两个入口已知，动态先后未核 |

已核对所引指令、对象身份、有限 double 跳表路由、示例算术和文档链接；没有启动游戏或执行运行测试，因为本轮范围是选定入口的静态补查。剩余风险是把部分生产/继承桥当作完整 boss 时序、把 target 同名字段混成同一对象、把归属筛选扩大成多实例安全保证，以及把对象销毁一概当作取消。文中保留这些缺口，不用名称或动画外观填补未知。
