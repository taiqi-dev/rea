# 34 敌人自救：弩手的绷带、夹板资源与生存判断

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [29 玩家绷带](29-bandages-and-wound-treatment.md) · [30 玩家夹板](30-splints-and-injury-stabilization.md) · [33 弩手行动选择](33-arbalester-skill-scoring-and-action-choice.md)

这次对象是 `o_bandit_arbalester`（强盗弩手）。本机制品确认它的Create会尝试创建自己的敌人版绷带、夹板代理，成功时绑定owner并加入consum_list；它们是可消耗的真实实例，来源独立于之后的掉落闭包。**可以确认弩手存在自救资源生产与执行机制，不能保证每只弩手都携带，更不能只凭受伤就断言它下一回合必然治疗。**

敌人治疗采用 `o_b_mobBandage/o_b_mobSplint`，不是玩家医疗UI。敌人版执行先调用父事件扣charge，再做流血清理或伤势恢复/稳定。当前回合如何将治疗分数与攻击、装填、移动竞争，须结合本轮AI选择器篇及本文明确的缺口，不能把一张评分表当作完整选择器。

## 1. 身份、方法与适用范围

调查开始为2026-10-12 22:20:57 PDT（2026-10-13 05:20:57 UTC），目标仍为 `E:\Steam\steamapps\common\Stoneshard`。根调查完整摘要与此前一致：EXE `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。

证据是本地资源索引、EXE配置和选定Capstone5.0.9解码；REA provider缺失沿用既有阻塞，没有伪造REA Evidence。没有运行、附加或修改游戏，没有读取新存档或监测网络。字段名称按RIP引用地址前8字节指针核对；资源ID、实例ID、配置文本与初始BSS值分别解释。

本机可选证据：[选定原生入口](../../../_reference/stoneshard-study/ninth-survival-native.json)、[对象与评分分派](../../../_reference/stoneshard-study/ninth-survival-resource-and-dispatch.json)、[完整物品表头与选定行](../../../_reference/stoneshard-study/ninth-survival-item-config.json)。下文保留地址和输入，使结论不依赖这些本机可选文件才能阅读。

## 2. 弩手确实尝试生产治疗资源

| 资源 | ID | 父ID | data.win OBJT偏移 |
| --- | --- | --- | --- |
| `o_bandit_arbalester` | 172 | 3892 | 9400672 |
| `o_enemy` | 3805 | 3804 | 10530088 |
| `o_b_consum_imitation` | 6184 | -100 | 11416656 |
| `o_b_mobBandage` | 6185 | 6184 | 11417152 |
| `o_b_mobSplint` | 6186 | 6184 | 11417504 |
| `o_db_bleed_parent` | 6043 | 1845 | 11355360 |
| `o_wound` | 5965 | 5964 | 11326536 |

弩手继承链是172→3892 `o_Bandit`→3891 `o_Grey_Army`→3890 `c_human`→3805 `o_enemy`→3804 `o_unit`。父Enemy.Create建立consum_list（`0x14361f11c..f152`），弩手Create `@0x142994d30` 除配置武器技能外，真实调用下列生产助手。

| Create调用VA | 对象参数 | 机会输入 | charge输入 |
| --- | --- | --- | --- |
| `0x1429959d7` | 6185 / 敌人绷带 | 50 | 从候选值1、2选择 |
| `0x142995aba` | 6186 / 敌人夹板 | 30 | 从候选值1、2选择 |
| `0x142995b45` | 6187 / 另一消耗代理 | 10 | 1；不在本篇展开 |

原作候选1/2、对象6185/6186和机会50/30由调用前RValue常量核对（`0x142995940..59be` 与 `0x142995a28..5aa1`）。候选选择助手 `0x1451de130` 收到两个参数，在 `0x1451de183` 按选中索引读取候选RValue并复制到结果。此处不是把1、2解释成物品掉落等级；底层候选抽样分布尚未完整恢复，不宣称两者严格等概率。

生产助手 `scr_enemy_create_invisible_consum @0x141176190` 有当前楼层、dungeon_modification=`supplies`、dungeon_tier等分支：所查supplies路径可以改写机会输入（存在 `50*dungeon_tier` 的乘加，`0x14117698a/0x1411769b3`），以及按0..1随机结果增加charge输入（`0x1411769e5..0x141176a0a`）。这些是有条件修正，不是所有地图都套用同样增益。本轮不恢复整个关卡修正器。

助手在 `0x141176af1` 调用公共 `scr_chance_value`，只有成功分支才创建资源。它创建指定对象（`instance_create_depth`元数据读取 `0x141176c0e`，实际引擎调用 `0x141176c38`），把charge设为第三输入（`0x141176c91..0x141176ccd`），owner设为调用敌人ID（`0x141176ced..0x141176d33`），随后把新实例ID加入敌人consum_list（`ds_list_add`元数据读取 `0x141176dd9`，实际调用 `0x141176e03`）。

所以50/30是概率助手输入，而非已核准的“恰好50%/30%拥有率”：公共概率还涉及未知运行时下限、0..100含端点取样与浮点容差，详见19。生产失败时没有该实例，不因技能名字存在而认为资源无限。

同一弩手Create到 `0x142995b63..5b85` 才把匿名闭包 `0x1429916c0` 赋给loot_script；其中掉落候选和随机调用属于另一份工作。**本篇“可携带”的证据来自生产/add list，不来自loot_script。** 已有实例快照没有在本轮读取，因此不保证用户遇到的某一只弩手具体库存。

## 3. 两个许可助手是状态与资源存在检查

`scr_enemy_skill_bleed_bandage @0x140290140` 的局部逻辑是：先查询本对象当前状态列表是否存在6043（流血父类，`0x1402902f3`），为真才查询consum_list是否存在6185（`0x1402903bd`）。最后将布尔结果转换为数值0或1返回（`0x1402903ca..3f0`）。

`scr_enemy_skill_wound_splint @0x140290690` 同型：第一候选是5965普通伤势父类（`0x1402907ec`及其列表查询），第二候选是6186（读取consum_list后查询）。其意义是具备相应状态且有代理实例，而不是恢复百分比、伤害权重或必须使用的指令。

列表参数为undefined时，列表查找助手采用已有默认状态列表规则。父类匹配的语义沿本机对象继承与列表助手解释，不把6043/5965当作某一个固定部位。

这两个独立入口在本轮已核对，但它们被哪个当前配置回调实际调用尚未完全绑定。后面的consum评分函数本身也检查相关状态；**不能把“返回1”冒充最终主选择器许可缓存或最终选择结果**。目前已能说明局部许可输入与输出，当前主调度消费点仍须交叉核实。

## 4. 治疗评分真实分派，不用默认权重填空

`scr_enemy_consum_get_priority @0x1414993b0` 按传入实例的object_index分派。表不是拿PE初始零猜测：函数的初始化段 `0x14149cf5f..cffc` 写5条类型/分支记录，表VA `0x149876530`、跨度20字节；跳表 `0x14149f45c` 将6185绑定到 `0x141499934`，6186绑定到 `0x14149b123`。

### 绷带分数的已确认部分

初值为0。存在6043流血状态时加2（列表查询 `0x141499a85`，加法 `0x141499ac0`）。计数助手 `scr_enemy_count_around(1,其余默认参数)` 的结果K在 `0x141499c8f` 取得：

- K=0时加5（`0x14149a2b8..a305`）。
- K>0且当前评分主体HP小于 `0.3*max_hp` 时减10（计算 `0x141499d66..d93`，减法 `0x141499e12`）。

这里K是本轮确认的计数结果；其八参数默认模式和筛选对象未全部展开，不把传入1直接解释为一格半径、一个敌人或一个队友。

随后评分还进入self.target上下文，读取两方HP/max_hp、格距离和range，继续可能减分。**这段有主体切换**：with target后self是被选目标，other仍是评分敌人；`0x14149a096`与 `0x14149a12d`不是同一个人的HP。本文没有把复杂路径简化成“敌人低于50%血一律减10”。精确目标距离、主体组合与剩余门禁保留局部边界。

### 夹板分数的已确认部分

初值0，先要求普通伤势5965存在（`0x14149b274..b28f`）。它按是否有轻/中/重父类状态分别加1/2/3：5966→加1 `@0x14149b3d7`，5969→加2 `@0x14149b520`，5971→加3 `@0x14149b669`。这三个是独立存在检查：若不同部位分别有不同等级，可能累计，不能擅自改写为只取最大等级。

计数K=0再加5（`0x14149b889..b8d6`），K>0且当前主体HP<0.3*max_hp时存在−10路径（`0x14149b99e..ba36`）。后续同样有target/距离/生命组合。所有有限浮点比较使用已核对的RValue compare容差 `1e-5`，构造整数值远离边界。

这些分数是传给候选竞争的局部数值，不是使用概率。主选择器可以受其他行动分数、许可、当前FSM、资源有效性和相等时的选择规则影响；不能把分数7直接换成70%治疗几率。

## 5. 当前FSM到代理治疗事件的静态桥已贯通

当前继承回合入口 `o_enemy.Other10` 调 `scr_enemy_choose_state_new` 后调 `scr_update_FSM_new @0x14364b719`。新版更新函数 `@0x141b546c0` 的初始化将attack绑定case3（字符串复制 `0x141b58b02`、case写入 `0x141b58b1e`）；跳表 `0x141b5aa6c` 的slot3指向 `0x141b55212`。此attack分支在skip_turn=false时于 `0x141b5533a` 派user2，对应enemy.Other12。另一派发 `0x141b54f1c`属于case4，不把它也叫attack。**当前attack状态确实存在到选择事件的静态桥**，无需借用旧update_FSM。

`o_enemy.Other12 @0x143644cd0` 在 `0x1436457a3` 取得consum priority，遍历consum_list并与当前best比较（`0x1436457da`）。普通有限值分数小于best时不选；大于或等于时替换best/selected，并将消费品标记设真。所以consum彼此平分时，后遍历者覆盖先前者。之后skill_active_set还会评估普通技能，它们满足分数与许可条件时可以覆盖治疗候选；普通平分还有随机选择，详见33。本文不把未恢复的攻击/装填权重填成默认数字。

已核对的最终路径先写enemy.skill=选中候选（`0x143646f98`或 `0x143647759`），再派发 **enemy自己的user1/Other11**（`0x143646fc1`或 `0x143647782`，事件参数1）。这个中间事件真实区分两类skill：

1. Other11读skill并调is_string（`0x143649568..95b5`）。普通技能字符串走另一条施法准备路径。
2. 治疗代理的实例ID不是字符串，进入with(skill)（`0x143649659`）。
3. 把代理target设为外层enemy.target（`0x1436496c8`），随后派 **代理user0/Other10 @0x1436496f2**。代理的owner仍由第2节创建阶段绑定，不把target字段误当治疗宿主。

这使 `当前FSM分支→enemy.Other12→选中代理→enemy.Other11→代理.Other10→消费/治疗` 的静态链闭合。它证明在相应状态/门禁和竞争结果下能执行敌人治疗，不等于已经观察某只弩手的一回合；全state分派、全部技能竞争权重、运行快照和相位仍有边界。

可选证据：[新版FSM](../../../_reference/stoneshard-study/ninth-ai-disassembly/gml_Script_scr_update_FSM_new.txt)、[候选选择](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Object_o_enemy_Other_12.txt)、[代理分派](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Object_o_enemy_Other_11.txt)。评分的完整竞争语义由33共同说明。

## 6. 敌人绷带：先消费，再清一项流血

`o_b_mobBandage.Other10 @0x14452e4a0` 先继承父事件（`0x14452e611`），随后查询owner.buffs：

1. 查询 `o_db_bleed_head @0x14452e7c8`；查到则跳过下一候选查询（`0x14452e7f4`）。
2. 否则查 `o_db_bleed_tors @0x14452e9a2`；查到同样跳过后备查询（`0x14452e9ce`）。
3. 否则按6043流血父类找一个owner列表中的实例（`0x14452eaf8`）。后备列表遍历的稳定顺序未恢复，不声明必定选最严重/最早/随机流血。
4. 进入所选实例并无参数调用销毁助手 `0x1451f70d0 @0x14452eb56`。普通实例派发Destroy/CleanUp，已在29核准。不是把所有部位流血一起清除。

它之后创建GUI动画并写动画charges=1、播放声音、重新读取owner.buffs。这份动画charge不等于代理charge。所查执行体没有调用HP/Condition直接恢复助手，也没有像夹板路径那样调用 `scr_consum_use`；不能从物品表Duration30/Bleeding_Resistance5推断敌人绷带本事件一定建立了持续抗流血Buff。

### 公共资源扣除和清理

父 `o_b_consum_imitation.Create0 @0x14452bb80` 默认is_persistent=false（`0x14452c124..c14a`）。父Other10 `@0x14452d080` 在 `0x14452d733..d749` 读取它：非persistent路径把charge减1（有限double `0x14452d78c..d798`；整型分支也减1），随后以charge对0的比较判断耗尽（`0x14452d7e7`）并销毁自身（`0x14452d821`）。辅助比较的所有动态类型分支未穷尽；正常整数charge=1→0的耗尽情形成立。

Destroy `@0x14452c970` 在owner上下文从consum_list找到自身ID并删除（`ds_list_find_index @0x14452cb3e`、`ds_list_delete @0x14452cb7d`）。因此有限资源被消费后能退出候选列表，不只是界面数字改变。

继承调用在流血查询前；耗尽销毁不会自动停止调用者后面的机器指令，子事件仍继续效果流程。未见“找不到流血后退还已经扣掉的一份”的补偿。是否主选择器总能防止这种失效提交，仍须完整桥与运行时验证。

## 7. 敌人夹板：自行选部位，表驱动Condition增量

`o_b_mobSplint.Other10 @0x14452fe10` 在 `0x144530081` 先继承，同样先消费。随后自行选择伤势实例，采用不同于玩家鼠标选部位的规则。

- 初始部位字符串head（`0x144530090`），读owner.Body_Parts_map[head]（`0x144530182`）。C正常处于0..100之间时，按等级3、2、1查询 `o_db_inj_head等级`（循环与构造 `0x144530285..306da`），找到即停止这一轮。
- 若未找到头部候选，改部位字符串tors（`0x144530738`）并按同样等级查询（`0x144530c4a`）。该门禁仍使用先前局部Condition；本篇不替原作补写一个未观察到的重新读取torso.Condition。
- 若仍无候选，遍历轻/中/重普通伤势类5966、5969、5971，要求其target等于owner，并缓存Body_Part/id（`0x144530cdf..5310ea`）。此后备路径会覆盖缓存；枚举顺序及多同级实例择优未知，不能称恢复了“全身最严重部位的精确排序”。

选到伤势后，按真实表接口取得 `scr_consum_get_attribute_from_tables("splint","Condition") @0x144531208`。完整表头文本 `0x146708c10` 与splint行 `0x146709430` 对齐后，Condition列为 **35**；不是依据名字猜值，也不是直接套用玩家动作heal属性。

读取选中部位当前C（`0x1445312e8`），与查表值加法（`0x144531434`），上限100取min（`0x1445314b5`），写owner.Body_Parts_map（`ds_map_replace @0x1445314da`）。局部公式是 `C'=min(100,C+35)`。

再以选中旧伤势对象名加 `_stabil`、查新类型（`0x1445315fe..3175d`），调用 `scr_inst_change_buffs @0x1445317a2`，使用29/30已核准的先销旧、后建新规则。稳定状态的同级减益、降级与清理门槛见27/30。

**敌人版本还有后续处理**：在 `0x144531a00` 调 `scr_consum_use`，从消耗品属性表继续使用splint相关参数。本轮未完全恢复该调用的所有属性消费者，因此C加35是已确认局部写入，不能保证最终屏幕数值只经历这一个变更，也不能把后续调用的名字当作完整恢复速率。动画、声音与身体图数据刷新随后发生。

## 8. 低生命与逃跑要分开解释

治疗评分里已确认的0.3*max_hp门槛是K>0时的−10处理，不是直接设置flee。例如max_hp=100、HP=20，满足低生命分支，但只知道相应治疗分数被减，不自动证明它选择逃跑。

另一个名称容易误读的字段是Enemy.Create默认 `flee_limit=0.9 @0x14361e4f8..e502`。旧 `scr_enemy_choose_state` 在 `0x141d74001..748ce` 读取HP/max_hp/flee_limit并比较HP与max_hp*flee_limit；HP不大于结果的局部路径到 `0x141d750a6 → 0x141d759f8`，返回当时state，**不是这一分支直接发起逃跑**。当前回合使用新版choose_state_new，旧路径的状态分派和可达性尚未在本篇绑定，因此不能公布“90%生命触发逃跑”。

旧函数还有 `morale_value` 与0比较后调用 `scr_stateFlee @0x141d741f8` 的路径，但其上游条件和新版FSM是否采用同一规则仍未知。字段默认、旧局部比较、当前逃跑触发是三项证据；本文不将它们合成一个貌似完整的生存公式。

本轮已恢复真实低生命评分检查，未恢复新版逃跑触发门槛与治疗/退却最终仲裁。详细逃跑目的格搜索也未展开，避免把本小例子扩大为全部AI。

## 9. 构造例子：受伤弩手的一次自救候选

以下实例ID、状态集合、生命、K、抽样结果均为构造输入；原作常数50/30、1/2、35和各事件位置来自前文证据。它不是本轮实际运行的一回合截图。

### A. 有头部流血和两份绷带

假设弩手Create的绷带生产概率判定成功、候选选择为2，没有supplies覆盖，得到代理B，owner=弩手、charge=2，并进入consum_list。弩手buffs含头部流血H及左手流血L。

许可助手可得到流血存在和代理存在，返回1。绷带评分初值0，流血存在+2；若计数K=0则再+5，得到该已确认阶段的7。若后续距离/双方生命分支没有进一步扣分，候选分数保持7；构造其余获许可候选均低于7、没有后续更高分候选覆盖，则它可留为selected。其余候选分数是构造限制，不是原作固定权重。

构造在已确认FSM分支满足skip_turn=false，B最终被选中：enemy.skill=B→Other11非字符串分支→B.Other10。父事件先charge2→1；子事件先查头部得到H，销毁H，L留在buff集合内。下一次假定再执行有效治疗，若charge1→0，则Destroy将B从consum_list删除，子事件仍能继续处理当次目标。没有新的资源生产时，之后不能再靠这个已销毁代理无限治疗。

### B. 中等头部伤势和一份夹板

假设夹板生产成功、选中charge1，头部Condition40且有 `o_db_inj_head2`，无影响选择的其他伤势。评分可包含中等伤势+2和K=0的+5；最终选择仍是构造条件。

执行父事件把1→0并删除代理列表项；子事件按3→2→1寻找头部候选，找到head2。查真实Condition35，局部写 `min(100,40+35)=75`，销毁head2并创建head2_stabil。后续scr_consum_use及状态更新不能凭本例宣称都已完成；C75也不表示所有减益立即消失。

### C. 有伤但没资源

若生成概率失败，consum_list里没有6185/6186实例，即使相应状态存在，独立许可助手返回0。掉落表仍可能包含绷带候选，这不会替代缺少的执行资源。若K>0、HP20/max_hp100，绷带已确认分数阶段为2−10=−8；夹板中伤阶段同为2−10=−8，后续仍可能修正。候选能否替换best，按第5节的比较及33的竞争规则判断；−8不是“逃跑概率”或无条件执行命令。

## 10. 独立开发的借鉴与剩余风险

可以借鉴资源生产和掉落分离、可用性和优先级分离、资源代理保存owner/次数、状态清理归状态所有者、部位键连接伤势和治疗数据。我们的实现可以明确规定效果失效时是否耗材、何时锁定部位、死亡/离图是否清理资源，以及平分时如何选；这些是独立设计建议，不是本轮恢复的原作规则。

原作敌人版本先扣资源再查询目标，在我们的产品中要按需求决定是否保留这种顺序，并提供可诊断的失败结果。不能从研究代码直接搬运完整AI或专有资产。

| 结论 | 关键VA | 边界 |
| --- | --- | --- |
| 弩手自救资源生产 | `0x1429959d7/5aba` | 概率尝试，不保证每实例携带 |
| 生产实例入列表 | `0x141176c91/0x141176ced/0x141176dd9` | 成功分支 |
| 许可0/1 | `0x1402902f3/3bd/3f0`；`0x140290690` | 当前回调注册/消费尚未全绑定 |
| 绷带评分分派及加分 | `0x14149cf74`、`0x141499ac0/49a305` | 分数不是最终概率 |
| 夹板等级加分 | `0x14149b3d7/b520/b669` | 多等级存在可累计 |
| 父事件扣1/耗尽 | `0x14452d798/d821` | 默认非persistent正常次数 |
| 列表移除 | `0x14452cb3e/cb7d` | owner有效时Destroy局部 |
| 敌人绷带销毁所选流血 | `0x14452eb56` | head→tors→后备一项 |
| 敌人夹板局部Condition增量 | `0x144531208/31434/314b5/314da` | 后续consum_use未完全解释 |
| 稳定类型生成 | `0x14453175d/317a2` | 先销旧建新，补偿未知 |
| 低生命扣分 | `0x141499d93/9e12` | 不等于逃跑触发 |

可选反汇编：[弩手Create](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Object_o_bandit_arbalester_Create_0.txt)、[生产助手](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Script_scr_enemy_create_invisible_consum.txt)、[绷带许可](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Script_scr_enemy_skill_bleed_bandage.txt)、[夹板许可](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Script_scr_enemy_skill_wound_splint.txt)、[评分](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Script_scr_enemy_consum_get_priority.txt)、[候选消费者](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Object_o_enemy_Other_12.txt)、[绷带执行](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Object_o_b_mobBandage_Other_10.txt)、[夹板执行](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Object_o_b_mobSplint_Other_10.txt)、[公共消耗](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Object_o_b_consum_imitation_Other_10.txt)、[列表清理](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Object_o_b_consum_imitation_Destroy_0.txt)、[旧状态比较](../../../_reference/stoneshard-study/ninth-survival-disassembly/gml_Script_scr_enemy_choose_state.txt)。

已回答：弩手的真实资源生产、状态/资源局部许可、治疗评分的明确分派和部分规则、执行时扣除/销毁、绷带目标和夹板局部恢复。部分回答：全部FSM分支和治疗/攻击/装填具体竞争、夹板后处理。未回答：完整实际场景的各候选输入与运行行为、逃跑实际触发、全部异常取消、资源保存/离图生命周期和所有多伤势枚举排序。验证为静态解码与构造演算，未运行游戏。主要风险是把已贯通的静态条件链误当某次运行已发生；本篇明确不作这种保证。
