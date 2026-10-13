# 先预警、后结算的怪物技能：拍地与投石

[总目录](README.md) · [证据范围](00-evidence-and-scope.md)

后续增量见 [15 生产、行动占用与终点碰撞](15-telegraph-production-chain.md)和 [16 提交、取消与 AI 门禁](16-skill-commit-and-ai-gates.md)。其中已补出生效果到持续状态、投石终点碰撞门槛与正常施法提交顺序；本篇记录的前轮未知应与增量篇合读，首次逻辑消费及投石发射的上游派发仍未闭合。

第十轮 [37 预告中断与取消](37-telegraph-interruption-and-cancellation.md) 进一步闭合类别槽：spell/skill与lock_spells/lock_skills对应，两招Create实际写class=skill。还区分取消先清格与正常Destroy排格执行、按owner归属的清理范围，以及提示对象与已发射石块；完整退款和动态相位仍未知。

这次追踪选中了本机古代巨魔关联的两个真实技能对象：o_shockwave（冲击波／拍地关联）和 o_rock_toss（投石）。已经确认它们共用“逻辑回合持续值 → 释放事件 → 动画或投射表现 → 按提示格查找命中对象 → 技能伤害”的结构。这里有一个关键区别：**持续值的递减确实发生在逻辑回合收尾入口，而释放后的 alarm 负责另一层计时；不能把 alarm[1]=20 理解成等待 20 回合。**

当前可以精确说明“初值 2、两次有效消费后释放”，但尚未证明实例创建当轮是否已经执行第一次消费，因此“玩家看到提示后的下一个行动就命中”仍需运行观察验证。本文没有启动游戏，也不把用户描述的现象当成已经捕获的运行证据。

## 1. 输入身份与研究边界

目标为 E:/Steam/steamapps/common/Stoneshard 的 Windows x64 原生编译制品。StoneShard.exe 的 SHA256 为 d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa；data.win 为 84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c。资源包没有普通 GML 字节码 CODE 块，以下结论来自对象资源、原生函数登记、数值指令和可达控制流。

本次用原生指令追踪了 174 个选定登记入口，存在相关辅助脚本与其他候选技能，数量不代表 174 种玩法已经解释。正式正文保留关键数值、分支和地址；本机可选证据在被 Git 忽略的 _reference/stoneshard-study，克隆仓库不会自动带上它们。没有导出美术资源，也没有把恢复代码写成生产实现。

## 2. 两个实例，以及容易误认的对象

OBJT 中每个对象记录的 +28 字段是父对象索引。本机数据中的以下关系与登记事件对应；对象 ID 是资源索引，文件 offset 是 data.win 中对象记录起点。

| 角色 | 对象、ID、资源 offset | 已确认职责或关系 |
| --- | --- | --- |
| 怪物 | o_ancientTroll，3962，10580816 | 多个技能结束／取消入口选择这个对象并设置动画；父类链为 o_Omnivore → o_enemy → o_unit |
| 拍地关联的技能状态 | o_shockwave，5515，11145600 | 父类为 o_aoe_spell_multiturn（5513） |
| 拍地起始表现 | o_shockwave_birth，5512，11144184 | 从相同施法者的提示格坐标创建 o_shockwave_tile |
| 拍地格子表现 | o_shockwave_tile，5518，11147016 | 有 is_idle 和动画状态；不能据此把它当成伤害格本体 |
| 投石技能状态 | o_rock_toss，5528，11151184 | 同样继承 o_aoe_spell_multiturn |
| 投石视觉投射体 | o_troll_rock，5529，11151968 | 继承 o_shell；与上面的技能状态对象不同 |
| 投石额外提示表现 | o_troll_rock_aoe_inducator，5530，11152608 | 单独对象；名称拼写来自实际资源 |
| 范围提示／执行格 | o_skill_aoe_zone，5677，11212992 | 保存位置、施法者归属、spell 和目标去重数组；执行时按自身所在格找对象 |
| 投射终点载体 | o_attacked_target，5287，11042880 | 投石发射事件在 point_x/y 创建此对象，并将它赋给视觉投射体的 target |
| 多回合父类 | o_aoe_spell_multiturn，5513，11144752 | 父类为 o_aoe_spell（5337），再到 o_shell（5291） |

资源表结合事件里的明确对象选择，可以把本例与古代巨魔关联起来；没有仅因英文名包含 troll 就选择目标。拍地关联对象是否对应界面上的具体本地化技能名称、玩家描述的是这一招还是另一种震地招式，未经过界面核对。本机还存在 o_tremor_strike_troll，但本文没有把它和 shockwave 合并成同一算法。

## 3. 状态保存在哪里

| 状态 | 保存位置 | 用途与证据 |
| --- | --- | --- |
| owner | 技能状态、提示格或表现对象 | 表达当前事件的施法归属；某些执行事件会重写它 |
| main_owner | 提示格 | 保留同一次施法者的归属；用于筛选对应提示格与共享去重列表 |
| skill_duration | 多回合技能实例 | Create 写 2；逻辑收尾通过门禁后递减至 0，触发 Other11 |
| is_movement | 多回合技能实例 | Create 写 false；收尾入口只在移动技能且 owner.lock_turn 非空时走该项取消分支 |
| class | 技能实例 | spell匹配lock_spells，skill匹配lock_skills；两招所查Create写skill，详见37 |
| x/y | 提示格 | 执行时真正用于查找当前位置上的对象；不是初始目标实例的身份 |
| target | 提示格／投石状态／投射体 | 同名字段在不同对象里语义不同：待攻击单位、当前格对象、独立终点载体都可能使用此名 |
| target_execute_array | 提示格 | 同 main_owner 的格子之间共享已处理目标信息，支持避免多格重复处理同一目标 |
| point_x/y | 投石状态 | Create 先从状态实例自身 x/y 初始化；发射事件据此创建终点载体 |
| target_x/y、target_exists | 投石状态 | Other11 检查目标实例是否仍存在；存在时刷新它的当前位置缓存 |
| alarm[1] | 技能／提示格 | 技能表现排程与提示格执行排程；不是 skill_duration 的逻辑回合计数 |

需要保留 owner 与 main_owner 的区别。例如提示格 Other11 在真正执行前把 owner 改成 main_owner，随后借该提示格的上下文调用技能对象的伤害事件。原生编译形式允许“使用某对象的事件代码、以另一个实例作为当前上下文”，因此不能根据函数名前缀就认定所有字段都属于那个函数名里的对象。

## 4. 确认的算法一：多回合技能的递减、释放与取消

o_aoe_spell_multiturn.Create 从 0x143fef270 开始，明确把 is_movement 写成 false，并在 0x143fef318 取得 skill_duration 写槽，0x143fef346..350 写入数值 2。这个初值由两个子类继承。

真正消费该值的是scr_global_turn_end（0x1419c0e50）中的第二组对象遍历。0x1419c16c8装载double常量5513，即多回合父类；0x1419c16f5建立遍历，0x1419c1760为循环体。下面类别值已由第十轮37的字符串构造与消费核准：

~~~text
对每个多回合范围技能实例：
    如果 owner 实例不存在：
        触发 Other12，随后销毁技能实例
        处理下一个实例

    如果 owner.lock_turn 非空 且 skill.is_movement 为真：取消
    如果 owner.lock_spells 非空 且 class == "spell"：取消
    如果 owner.lock_skills 非空 且 class == "skill"：取消

    如果 skill_duration 的真值为真：skill_duration 减 1
    如果 skill_duration 等于 0：触发 Other11
~~~

“减 1”不是由字段名推测：数值路径在 0x1419c1baa 使用 addsd 加上从 0x145aac120 读取的 -1；另有整数路径在 0x1419c1c4e / 1c53 执行 add -1。0x1419c1c90 把更新后的持续值与 0 比较，相等时在 0x1419c1ce3 调用事件助手，传入 user 索引 1。

事件助手 0x1451ef5b0 的全部主体只有三个指令：把传入索引加 10、设置事件类型 7、跳到事件派发器。因此 user 索引 1 对应 Other11，2 对应 Other12，与本机对象事件编号一致；不是靠通用 GameMaker 文档猜出关系。取消分支在 0x1419c1bde 传 2，然后在 0x1419c1c01 销毁技能实例。

锁门禁的含义不能扩大。父类把is_movement设为false，所以本例不因lock_turn非空就必然取消。前轮未核准的类别槽已在37通过字符串构造与消费恢复为spell/skill；两招所查Create写skill，因此lock_skills非空可命中该取消条件。同样，owner不存在是实例存在性判断，**不等于HP刚降到0**。尸体仍保留实例时究竟何时取消，仍需跟踪怪物死亡阶段。

### 逐步演算

假设实例已经创建、owner 存在、类别锁门禁通过，且每次下面的调用都是一次成功的逻辑收尾消费：

| 消费序号 | 进入时值 | 递减后值 | 结果 |
| --- | --- | --- | --- |
| 1 | 2 | 1 | 不释放，实例保留 |
| 2 | 1 | 0 | 派发 Other11，开始释放表现 |
| 取消分支示例 | 1 | 不继续递减 | owner 不存在时派发 Other12，再销毁状态实例 |

这确立了两个离散消费点，不能直接把它们命名成“玩家本回合和下一回合”。公共调用调查确认 scr_unitTurnBreak 在 0x14169abf5 调用 scr_global_turn_end，之后同入口还可在 0x14169d82f 调用 scr_global_turn。两者之间有条件分支与大量更新；本次没有证明创建瞬间相对于第一消费点的精确位置，也没有证明任意玩家输入都只消费一次。相关回合分层见本机公共证据，后续文档应以此为边界。

## 5. 确认的算法二：提示格在结算时找目标，并派发伤害事件

父类 o_aoe_spell.Destroy（0x143e48c60）不是直接逐格扣血，而是遍历 o_skill_aoe_zone。若格子的 main_owner 等于被销毁技能的 owner，则在 0x143e48dc5 写这个提示格的 alarm[1]=1。格子的 Alarm1（0x144159b60）递增 iteration，随后在 0x144159c3c 派发自己的 Other11。

Other11 中有一条完整可确认的数据流：

1. 读取提示格自己的 x/y，在 0x14416396e 调用 scr_tile_get_instance，并把结果赋给 target（0x144163988）。
2. 区分不存在／undefined／空指针、实例存在性与可破坏对象分支。没有单位时可能使用该格实例作为后续目标，不能概括成“空格立即全部返回”。
3. 在 0x1441642eb 调用 scr_skill_check_target_repeat；在对应分支中，遍历同类型且 main_owner 相同的提示格，把本格 target 加入它们的 target_execute_array（array_push 在 0x144164498）。
4. 在 0x14416486c 把自己的 owner 改为 main_owner。
5. 读取自己的 spell 对象 ID，以类型 7、事件号 10 调用事件派发助手 0x1451ef590（0x1441648d0）。这对应所选技能的 Other10，当前上下文仍承载本格位置和刚找到的 target。
6. 两个实际技能的 Other10 初始化伤害、计算钝击输入、调用继承事件；父类 o_aoe_spell.Other10 在 0x143e497ec 进入公共 scr_skill_damage。

第五轮在 [20](20-area-shapes-and-hit-selection.md) 进一步核对第 3 步：重复目标会被替换为当前格自身 ID，后面的技能事件派发仍继续。这是目标筛选/替换机制，不能概括成“重复时整个事件立即返回”，也不能仅靠数组存在就保证所有技能全链一次伤害。20 同时补充范围候选生成与定位的证据和参数映射缺口。

这证明**这里的提示格兼有空间位置和执行职责**，执行时读取的是该位置的当前对象。它没有简单地把“最初玩家实例 ID”送入扣血。至于当前两个技能的全部提示格集合怎样形成、是否在释放之前仍会移动，以及所有视觉边缘是否严格等于攻击格边缘，还没有恢复完整形状生成链。

### 构造例子：玩家离开提示格

假设某个提示格的坐标是 Q=(260,182)，初始玩家在 Q。此例只示范刚确认的查格算法，坐标与过程不是运行捕获：

~~~text
准备阶段：提示格位于 Q；玩家 P 位于 Q
等待阶段：玩家从 Q 移到 R=(286,182)
执行阶段：提示格用自己的 Q 查询当前占格对象
若 Q 空：不把现在 R 上的 P 自动当成 Q 的单位命中对象
若敌人 B 此时在 Q：查格结果会是 B，再进入有效性与去重过滤
~~~

所以“移动躲开预警”可以由结算时按格查对象实现；它不需要投射物每帧追踪玩家。不过，若提示格本身在等待阶段跟随目标移动，Q 就会变化。Step 中实际存在 is_moving、is_activate、owner/main_owner 与 shift 的门禁，当前不能把所有技能都写成准备时永久锁格。

## 6. 真实例子一：拍地关联的 shockwave

### 提示、表现与释放链

o_shockwave_birth.Other10（0x143fee050）遍历 o_skill_aoe_zone，在 0x143fee764 比较提示格 main_owner 与 other.owner。匹配后读取提示格 x/y，并在同坐标创建 o_shockwave_tile（5518，调用 0x143fee898）。因此至少这层冲击波格子表现直接复用了提示格坐标，而非在另一个中心重新独立计算位置。

逻辑持续值归零后进入 o_shockwave.Other11（0x143ff2940），设置施法动画与音效，并在 0x143ff2d3f 写 alarm[1]=20。Alarm1（0x143ff0be0）首先在 0x143ff0c5e 派发 user4，即 Other14。这个事件的主体在 0x143ff3d37 销毁当前技能状态，从而进入上节的父类 Destroy → 提示格 Alarm1 → 提示格 Other11 → 技能 Other10 伤害链。该 Alarm1 后面的逻辑还选择 o_shockwave_tile，将 is_idle 设为 false 并产生震屏；不能把所有后续表现的出现时间当成唯一伤害生效时间。

状态归零与动画警报是两层：归零让释放开始；alarm20让表现和结算在相应事件链中继续。没有验证全局帧率与 alarm 的最终调度精度，本文不换算毫秒。

### 已确认的钝击输入算法

o_shockwave.Other10 从 0x143ff10f0 开始。在 owner、target 实例存在且 target 不等于 owner 的对应路径中，先调用 scr_tile_distance(target, owner, undefined)，再写：

~~~text
d = scr_tile_distance(target, owner, undefined)
Blunt_Damage = 30 × (1 + 0.1 × d)
~~~

证据是常量 0.1（0x143ff1492）、1（0x143ff14bd）、30（0x143ff14eb），对应乘、加、乘调用，以及写槽 0x143ff1525。数值助手也已解码确认：0x14000bc20 的数值分支是 mulsd，0x1400038c0 的数值分支是 addsd。

| 假定距离脚本返回 d | 计算过程 | 写入 Blunt_Damage |
| --- | --- | --- |
| 0 | 30×(1+0) | 30 |
| 2 | 30×(1+0.2) | 36 |
| 5 | 30×(1+0.5) | 45 |

这些是对已确认表达式的构造演算。d 的几何定义与取整规则尚未在本篇恢复，不能把表中的 5 自动解释成欧氏距离或曼哈顿距离 5 格。这里也不是最终掉血量：继承事件会进入 scr_skill_damage，护甲、抗性、格挡与其他公共战斗修正仍可能改变结果。

继承伤害后还检查 is_hit（0x143ff15b1），才进入 Knockback_Resistance、scr_chance_value（0x143ff1703）与 scr_cast_knockback（0x143ff182a）路径。本文确认了“命中门禁之后才可能击退”，尚未完整恢复击退方向、步数与概率助手边界。

### 取消

Other12（0x143ff3240）有古代巨魔动画处理、按 main_owner==other.owner 筛选并销毁对应提示格，以及格子表现的状态处理。其中匹配比较在 0x143ff3574，提示格销毁在 0x143ff359f。公共收尾入口取消时先触发这个事件再销毁状态，因此不是单纯留下原提示格等待父类 Destroy 继续结算。不过全部表现对象是否都按同一施法实例精确隔离，需要进一步检查。

## 7. 真实例子二：rock_toss 投石

### 坐标不是只有一份

o_rock_toss.Create（0x143ffe660）写 point_x/y 和 target_x/y，初值来自技能状态自身的 x/y；这通常与创建参数有关，但本文没有恢复完整创建点选择规则。Other11（0x143fff7d0）再检查 target 实例是否存在（0x143fff947），记录 target_exists（0x143fff974）。若存在，在 0x143fff9fc、0x143fffa6c 刷新 target_x/y 为该实例此刻的位置。

发射事件 Other14（0x144000e70）从 owner 的坐标创建视觉投射体 o_troll_rock（调用 0x1440012f7），随后使用**状态实例的 point_x/y**创建 o_attacked_target（调用 0x144001498），将创建结果赋给视觉投射体的 target（0x1440014b2）。因此有“目标实例当前位置缓存”和“投射终点载体”两个不同的数据来源，不能把其中一个字段叫 target 就认定全程追踪玩家。

Other14 还存在后续调整终点、方向和寻路网格的条件分支。本次仅确认上述具体创建与赋值，没有把所有分支归纳成“准备时一经锁定、此后永不改变”。相应未知会影响玩家能否在发射前后分别躲避。

### 表现与结算链

Other11 在 0x143fffdbf 调用 sprite_get_speed，以 7 除以结果（除法助手调用 0x143fffde9），写 alarm[1]（0x143fffe37）。o_rock_toss 自己的 Alarm1 本体没有发射逻辑，所以仅靠这次写值不能确定 Other14 的调用来源。发射事件入口已经确认，**从巨魔动画事件或公共表现控制器到此入口的完整调用链尚缺一段**。

视觉投射体的 Step（0x144003540）先执行父事件，再更新旋转和速度；可确认局部数值规则为：

~~~text
image_angle ← image_angle + speed
speed ← lerp(speed, 15, 0.05)
~~~

这属于投射表现，不能把参数 15 理解成飞行 15 回合。创建／发射时还可见 speed=10；例如假设某一步进入时速度为 10，线性插值计算得到 10.25，下一步得到 10.4875。这是表达式演算，未证明实际播放帧数或运动终点触发阈值。

视觉投射体 Other11（0x144003b50）遍历 o_rock_toss（5528），在 0x144003dae 销毁选中状态实例，触发公共父类 Destroy → 提示格执行链。该事件后面还处理碎片、震屏与额外提示表现。这证明“视觉投射体结束事件驱动范围状态清理和格子结算”，尚未证明所有相同类型并存实例都怎样相互隔离。

### 已确认的钝击输入算法

投石技能 Other10（0x143ffed10）有 owner 和 target 存在性门禁，并排除 target 等于 main_owner 的对应路径。其距离调用在 0x143ffef9e，数值路径为：

~~~text
d = scr_tile_distance(target, owner, undefined)
Blunt_Damage = 60 × (1 + 0.1 × d)
~~~

证据为常量 0.1、1、60 和三次运算，最终写槽 0x143fff03d；随后在 0x143fff096 执行继承事件，进入公共伤害计算。

| 假定距离返回 d | shockwave 的输入 | rock_toss 的输入 |
| --- | --- | --- |
| 0 | 30 | 60 |
| 2 | 36 | 72 |
| 5 | 45 | 90 |

同一个 d 下，投石的这个钝击输入是 shockwave 的两倍；不意味着最终掉血总是两倍，也不意味着两个技能共享完全相同的范围和有效目标。

Other12（0x144000450）同样筛选 o_skill_aoe_zone，比较 main_owner==other.owner（0x1440005e1），匹配时销毁提示格（0x144000605），并处理古代巨魔动画。它与正常表现结束时的“状态销毁导致提示格执行”是两条不同路径。

## 8. 串联图与已确认范围

~~~mermaid
flowchart TD
    A[多回合状态 Create: duration=2] --> B[逻辑回合收尾与锁门禁]
    B -->|通过: 减1; 等于0| C[技能 Other11: 开始释放表现]
    B -->|owner不存在或匹配锁门禁| X[技能 Other12: 删除归属提示格]
    X --> Y[销毁状态]
    C --> S[shockwave alarm1=20]
    S --> S2[Alarm1 → Other14 → 销毁状态]
    C -. 投石 Other14 的派发来源未闭合 .-> R[创建视觉石头与独立终点载体]
    R -. 到达事件触发阈值待查 .-> R2[石头 Other11: 销毁投石状态]
    S2 --> D[父类 Destroy: 匹配提示格 alarm1=1]
    R2 --> D
    D --> E[提示格 Alarm1: iteration++ → Other11]
    E --> F[用提示格当前x/y查询占格对象]
    F --> G[有效性与目标去重]
    G --> H[spell对象的Other10: 计算伤害输入]
    H --> I[继承事件 → 公共技能伤害]
~~~

实线代表本文追踪的局部可达调用或数据流；虚线明确表示仍缺少触发来源或阈值，不能拿整张图当完整运行时状态机。还有 c_tile_mark（5409）这一种持续地面伤害对象；公共单位事件会读它的 delay / placelist / position_check。它与本篇 o_skill_aoe_zone（5677）不同，本篇没有拿前者的 delay 字段解释后者的多回合预警。

## 9. 独立开发可借鉴的规格

以下是我们自研游戏的设计建议，不是恢复的 Stoneshard 代码，也不宣称目标本来采用这些更明确的数据类型。

建议把一个蓄力攻击记录拆成施法者句柄、攻击实例 ID、预计结算逻辑回合、冻结后的格子集合、目标去重集合、取消条件、视觉状态。准备时生成一次攻击格集合，渲染和结算共享该集合；如果希望有追踪技能，就明确设置“准备期间跟踪、释放时冻结”或“始终固定格子”的策略。这样不会出现提示格和最终攻击格因两套几何规则不同而偏离。

建议用绝对逻辑回合编号表达截止点，例如 resolveTurn=prepareTurn+1；动画单独计时。若玩法需要先把动画播完再扣血，可在逻辑层进入 Resolving 后暂停其他行动，让表现完成事件提交一次已经确定的结算。每个攻击实例拥有自己的 Cancelled / Resolved 状态，防止重复回调、视觉销毁或多个同类投射体误操作其他攻击实例。

建议明确“施法者死亡”的业务含义，而不是依赖 GameObject 或实例何时真的被删除。HP≤0、尸体状态、销毁状态可以是三个阶段；取消规则应该说明哪一阶段起作用。取消应一次性删除自身提示、停止自己的表现并解除行动锁，且在行为日志里保留取消原因。

| 自研选择 | 与本次目标证据的区别 |
| --- | --- |
| 准备时固定 resolveTurn | 目标确认使用初值2的持续值递减，首次消费起算尚未确认 |
| 攻击实例独立保存 frozenCells | 目标提示对象兼执行对象，并在执行时按本格查询；完整格集合形成和冻结规则未恢复 |
| 显式固定／跟踪目标策略 | 目标投石有 point_x/y、target_x/y、独立终点实例及条件调整，不能归纳成单一策略 |
| 取消以战斗状态枚举决定 | 目标公共门禁以 owner 实例存在和若干锁列表／class比较决定 |
| 一次性结算标记 | 目标在0持续值时派发释放事件，后续表现销毁推动结算；并发／重复收尾防护尚未完整核对 |

## 10. 证据表与需要继续确认的内容

本机可选证据：[原生索引](../../../_reference/stoneshard-study/third-telegraph-native.json)、[对象元数据](../../../_reference/stoneshard-study/third-telegraph-object-index.json)、[局部调查报告](../../../_reference/stoneshard-study/third-telegraph-findings.md)。以下链接都指向当前机器的调查产物；正文中的结论和演算不依赖它们才能理解。

| 关键声明 | 地址／数据 | 本机可选记录 |
| --- | --- | --- |
| 父类持续值初值2 | Create 0x143fef270；写槽0x143fef318；赋值0x143fef346..350 | [父类初始化](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_aoe_spell_multiturn_Create_0.txt) |
| 多回合递减与取消 | 5513 selector@0x1419c16c8；递减@0x1419c1baa；归零事件@0x1419c1ce3；取消@0x1419c1bde | [逻辑收尾](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Script_scr_global_turn_end.txt) |
| user编号映射 | 0x1451ef5b0：事件7，索引+10，尾跳 | [事件助手](../../../_reference/stoneshard-study/third-telegraph-disassembly/helper-0x1451ef5b0.txt) |
| 公共回合调用位置 | scr_unitTurnBreak的0x14169abf5 → global_turn_end | [公共回合入口](../../../_reference/stoneshard-study/third-turn-damage-disassembly/scr_unitTurnBreak.txt) |
| 状态销毁排程对应提示 | main_owner比较0x143e48d7b；alarm1赋1@0x143e48dc5 | [范围父类销毁](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_aoe_spell_Destroy_0.txt) |
| 按格查目标、派发技能 | 查格0x14416396e；去重0x1441642eb；event7/10@0x1441648d0 | [提示格执行](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_skill_aoe_zone_Other_11.txt) |
| 提示格Alarm1进入执行事件 | iteration++；user1@0x144159c3c | [格子排程](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_skill_aoe_zone_Alarm_1.txt) |
| 拍地表现复用提示位置 | 归属比较0x143fee764；创建5518@0x143fee898 | [拍地开始](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_shockwave_birth_Other_10.txt) |
| 拍地释放后计时 | alarm1=20@0x143ff2d3f；user4@0x143ff0c5e；销毁@0x143ff3d37 | [释放](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_shockwave_Other_11.txt)、[警报](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_shockwave_Alarm_1.txt)、[结束](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_shockwave_Other_14.txt) |
| 拍地伤害输入 | 距离0x143ff1457；写Blunt_Damage@0x143ff1525 | [拍地命中](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_shockwave_Other_10.txt) |
| 投石目标位置刷新 | target存在@0x143fff947；坐标赋值@0x143fff9fc/fa6c | [投石释放准备](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_rock_toss_Other_11.txt) |
| 投石独立终点载体 | 视觉5529@0x1440012f7；终点5287@0x144001498；赋target@0x1440014b2 | [发射](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_rock_toss_Other_14.txt) |
| 视觉结束销毁技能状态 | 5528选择@0x144003d32；销毁@0x144003dae | [投射结束](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_troll_rock_Other_11.txt) |
| 投石伤害输入 | 距离0x143ffef9e；写Blunt_Damage@0x143fff03d | [投石命中](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_rock_toss_Other_10.txt) |
| 取消删除所属提示 | shockwave@0x143ff359f；rock_toss@0x144000605 | [拍地取消](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_shockwave_Other_12.txt)、[投石取消](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_rock_toss_Other_12.txt) |
| 公共伤害接入 | 父Other10@0x143e497ec → scr_skill_damage | [父类命中](../../../_reference/stoneshard-study/third-telegraph-disassembly/gml_Object_o_aoe_spell_Other_10.txt) |

待确认的关键点是：实例创建与第一次逻辑收尾消费的精确相对顺序；投石 Other14 的实际派发来源；视觉石头到达事件的判断阈值；两个技能提示集合的完整形状、阻挡物过滤与冻结时点；投石条件调整是否改变已显示的区域；owner死亡到实例销毁的生命周期；并存同类技能的清理隔离；scr_tile_distance 的距离定义与公共伤害最终修正。

未做运行或存档实验；目前完成的是静态链核对，未采集运行时序。下一轮最有价值的观察是：记录创建时刻、两次收尾时刻、提示格坐标、释放事件和玩家移动位置，分别验证“离开提示格”“留在提示格”“蓄力中杀死施法者”。风险主要是把当前局部静态链误说成完整游戏行为；以上未知不能靠动画名字、alarm数值或函数地址顺序补成确定结论。
