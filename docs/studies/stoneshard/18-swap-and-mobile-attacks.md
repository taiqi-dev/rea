# 18 秘术换位与攻击中的自身移动

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [技能执行](10-combat-skill-execution.md) · [回合与伤害](14-combat-turns-and-damage.md) · [技能提交与门禁](16-skill-commit-and-ai-gates.md)

本章研究三个实际技能：`Planar_Exchange`、`Crippling_Lunge`、`Heroic_Charge`。中文“秘术换位”“致残突刺”“英勇冲锋”在这里用于说明机制，实际身份以制品中的英文键、执行对象和资源继承记录为准。本章没有核对中文本地化名称。

**换位是选取两个不同单位，先捕获双方坐标，之后顺序提交两次位置变更，再进入伤害处理。两种移动攻击选择敌人对象，通过共享移动函数接近目标，在距离判定等于 1 的分支攻击；致残突刺将攻击放在后续 Alarm 1，英勇冲锋在 Alarm 0 的相邻分支攻击。** 单位存在不等于仍存活，移动完成不等于攻击命中，两次位置提交也不证明原子交换。

## 1. 证据身份、方法和覆盖

| 制品 | SHA256 |
| --- | --- |
| `StoneShard.exe` | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| `data.win` | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

目标为 `E:\Steam\steamapps\common\Stoneshard` 的 GameMaker YYC x64 制品，静态 image base 为 `0x140000000`。本轮复用与上述摘要一致的注册索引、PE 节映射和 OBJT 资源记录，针对明确候选用 Capstone 5.0.9 局部解码；没有运行游戏、修改目标或读取新存档。此调查采用本机替代分析产物，没有 REA 提供者会话或 REA Evidence ID。

解码覆盖为 40 个候选函数的可定位 `.pdata` 段，包含三招 Create/Alarm/Other 入口、两段换位闭包及共享移动、坐标和筛选函数。段内指令成功解码不代表理解了全部动态派发、父事件、函数片段或引擎分支。本章只把下述字段、实参、分支和调用顺序作为已确认规则。

- **直接制品事实**：技能配置行、对象 ID/父对象、函数注册地址、字段写入和直接调用。
- **控制流推导**：双方坐标缓存后交叉传入坐标函数；距离与锁列表控制移动分支；攻击位于后续事件或相邻分支。
- **未观察**：真实帧间隔、玩家交互、最终伤害、命中率、存活判断、失败退款和复杂障碍下的实际路线。

YYC 缓存字段的名称指针位于引用地址减 8 字节，不能从后一条记录推名称。`type=0xD,value=0` 表示数值布尔假，本章没有将它写作 undefined；未给定参数的 undefined 是另一种值。间接 `with` 派发会改变当前 `self/other`：移动分支的当前 `self` 是 owner，`other` 是技能执行对象，不能将两个 `id` 混用。

## 2. 真实配置与对象身份

技能表头位于 `0x145e4bdc0`，按 `Object / Target / Range / KD / MP / … / is_movement / … / Class / Bonus_Range / … / Branch` 等列读取。表头中的原拼写 `AOE_Lenght` 保留在本机证据，未把字段名臆改成另一个契约。

| 表字段 | Planar_Exchange | Crippling_Lunge | Heroic_Charge |
| --- | --- | --- | --- |
| 行 VA | `0x145e4fa00` | `0x145e4c2a0` | `0x145e4cb10` |
| Object | `o_planar_exchange` | `o_crippling_lunge` | `o_heroic_leap` |
| Target | Target Object | Target Object | Target Object |
| Range | 5 | 2 | 3 |
| KD | 8 | 12 | 24 |
| MP | 14 | 16 | 26 |
| is_movement | 0 | 1 | 1 |
| Class | spell | skill | skill |
| Bonus_Range | 1 | 0 | 0 |
| Branch | arcanistics | axe | 2hsword |
| Attack / Charge 标记 | 空 / 空 | 1 / 1 | 1 / 1 |

这些是输入配置，不是实际最终扣费和冷却的实测值。尤其 `Planar_Exchange.is_movement=0` 不否认它改变坐标：该列不能代替执行行为。英勇冲锋实际指向 `o_heroic_leap`，不能因为存在名字相近的狮子冲锋对象，就把后者作为本技能证据。

| 对象 ID | 对象 | 父对象 ID / 名称 | OBJT 记录文件偏移 |
| --- | --- | --- | --- |
| 2381 | `o_planar_exchange` | 5531 / `o_target_spell` | 10087328 |
| 4341 | `o_skill_planar_exchange` | 6426 / `o_skill_arcanistics` | 10703808 |
| 5531 | `o_target_spell` | -100 / 无 | 11152960 |
| 5539 | `o_moving_skill` | 5531 / `o_target_spell` | 11156856 |
| 5540 | `o_heroic_leap` | 5539 / `o_moving_skill` | 11157280 |
| 5547 | `o_crippling_lunge` | 5539 / `o_moving_skill` | 11160464 |
| 6199 | `o_skill` | 6198 / `o_abilities` | 11422440 |
| 6231 | `o_skill_crippling_lunge` | 6199 / `o_skill` | 11436224 |
| 6242 | `o_skill_heroic_charge` | 6199 / `o_skill` | 11440168 |
| 6426 | `o_skill_arcanistics` | 6199 / `o_skill` | 11510480 |

技能选择对象负责设置筛选、目标列表等交互状态；表里的 Object 指向后续执行对象。三条链不能只用选择对象的字段解释伤害，也不能只用执行对象的父类解释完整目标选择。

## 3. 换位：两个目标的收集和验证

### 3.1 输入与状态

`o_skill_planar_exchange.Create`，入口 `0x1439dfdb0`，写入技能键 `Planar_Exchange`，安装 `scr_planar_exchange_filter`，初始化 `use_count=2`、`max_use=2` 和空的 `target_array/mark_array`；目标组常量 3804 对应 `o_unit`。关键写入为技能 `0x1439dffd9`、筛选函数 `0x1439e007e`、两个计数 `0x1439e047e / 0x1439e04c3`、目标组 `0x1439e04fe`。

`Other 20` 入口 `0x1439e3ab0` 是本轮读到的目标收集事件。鼠标坐标和目标组传入 `collision_point`，找到候选实例。随后逐个比较已选目标；候选与列表已有项相同，候选被换成 -4，之后的实例存在门禁失败，进入 `scr_skill_denied`。

候选必须通过以下实际局部门禁：

1. 存在，并通过 `instance_is(candidate,o_unit)`。
2. `Unbreakable` 为假。
3. `is_poly_cell` 为假。
4. `no_tp` 为假。
5. `size` 不等于字符串 `giant`。
6. 通过 `scr_skill_can_interact` 的布尔结果门禁。

通过后加入 `target_array`，创建/保存目标标记，`use_count` 减 1；计数与 0 相等时，将剩余计数作为参数调用 `scr_skill_prepare_to_use`。这里的目标列表长度限制由“初始计数 2、每次有效选择减 1、零时准备执行”建立，不能从脚本名推断为任意两格互换。

| 选择证据 | VA |
| --- | --- |
| 鼠标碰撞找候选 | `0x1439e3e1c` |
| 重复目标变为 -4 / 随后存在门禁 | `0x1439e40cb / 0x1439e411f` |
| `instance_is` 单位判断 | `0x1439e41bd` |
| 三个禁止字段门禁 | `0x1439e4212 / 0x1439e4258 / 0x1439e429e` |
| `giant` 比较 | `0x1439e435f` |
| 交互门禁 | `0x1439e43c8` |
| 目标加入 / 标记创建 | `0x1439e448d / 0x1439e47e4` |
| 计数读写与减 1 分支 | `0x1439e487b / 0x1439e4cf0–0x1439e4d26` |
| 零比较 / 准备使用 | `0x1439e4d54 / 0x1439e4df5` |

筛选函数 `scr_planar_exchange_filter`，入口 `0x14041dde0`，调用 `scr_barrier_filter` 和 `scr_tile_get_instance`。在识别出的 `o_unit` 分支，`is_sleeping` 为真或者 `animation_state == "sleep"` 会到 `0x14041e480`，向返回值写布尔假（type 0xD/value 0）。这些是真实睡眠状态筛选；它们不是本轮运行观察，也不是所有睡眠、所有屏障、所有跨区条件已恢复的证明。

### 3.2 选择规格伪代码

以下是根据已读分支自行编写的行为规格，省略资源管理、标记动画和间接派发细节，不是原游戏代码。

```text
选择状态：remaining = 2；targets = []；marks = []

处理一个候选 candidate：
    若 candidate 已在 targets：将 candidate 视为无效
    若 candidate 不存在或不是 o_unit：拒绝本次选择
    若 Unbreakable 或 is_poly_cell 或 no_tp：拒绝
    若 size == giant：拒绝
    若交互门禁不通过：拒绝
    将 candidate 加入 targets，并登记选择标记
    remaining -= 1
    若 remaining 与 0 相等：进入准备使用流程

格筛选的已读单位分支：
    若 is_sleeping 或 animation_state == sleep：返回 false
    其余格/屏障分支仍由原筛选流程处理
```

表中 Range=5、Bonus_Range=1 是名义选择配置。本轮没有把动态属性修改、范围加成和公共鼠标选择流程完整恢复成最终范围公式，也没有证明任意单位组合都允许玩家实际确认。

## 4. 换位执行：缓存位置、交叉提交、后续效果

`o_planar_exchange.Alarm 0` 入口 `0x1431473d0`。它读取选定目标、处理标记及准备状态，包含 `scr_check_reflection`；反射可能改变后续参与者，因此不能假定最初鼠标选中的实例永远等于最终 A/B。

关键局部路径将目标数组索引 0/1 读到 A/B。它建立准备闭包 `0x143141d00`，分别传入 A、B。闭包先读取单位的 x/y 到局部缓存，之后才处理隐藏渲染、效果和状态，最终返回由这两个坐标组成的数组。任一准备结果走到未定义/空值判断的失败出口，会先销毁执行对象，未到两次坐标提交。

成功路径先对 A 调用坐标函数，使用 B 的缓存位置；之后对 B 调用坐标函数，使用 A 的缓存位置。这解决了“先移动 A，再读取 A 坐标会丢掉原位置”的问题。但两次调用是分开的，调用后没有本轮确认的双向成功检查与回滚协议，因此不能称为原子交换。

| 执行证据 | VA |
| --- | --- |
| 建立坐标准备闭包 | `0x143148378 / 0x143148386` |
| 分别调用准备闭包 | `0x143148431 / 0x143148965` |
| 闭包缓存 x / y | `0x143141f84 / 0x143141fc7` |
| 用缓存 x/y 构造两元素返回数组 | `0x14314344d–0x14314349f` |
| 准备失败出口 | `0x1431487e2 / 0x143148d7a` |
| A → B 的缓存坐标 | `0x1431490e4` |
| B → A 的缓存坐标 | `0x1431492b4` |
| 后续朝向更新 | `0x1431494a3 / 0x1431495cc` |
| 建立后续效果闭包 `0x1431445b0` | `0x143149b56 / 0x143149b64` |
| 分别以 A/B 调用后续效果闭包 | `0x143149ee0 / 0x143149f61` |
| 效果闭包内 `scr_skill_damage` | `0x143144abd` |
| 效果创建调用之一 | `0x1431451cc` |
| Alarm 1 恢复渲染相关调用 | `0x14314d140 / 0x14314d3f0` |

两个坐标调用的已核实实参顺序为 `(目标 x, 目标 y, 被移动单位 id, true, true, true, undefined)`。后三个真值是位置函数的输入，未完整还原各位置参数的契约名称；不能分别擅自命名成“穿墙”“忽略占用”“免费移动”。

后续效果闭包读取 `Magic_Power / Arcanistic_Power / Stun_Resistance` 等字段，调用技能伤害和效果创建。本章只确认其位于交换提交之后，并不把中间字段读写缩写成未经恢复的最终伤害或眩晕概率公式。该闭包还有噪声与传送相关调用，不能据此将所有单位、所有反射分支的最终可见效果写成相同结果。

```text
换位执行的局部成功路径：
    取得执行阶段最终参与者 A、B
    oldA = 准备参与者并返回其旧 x/y(A)
    oldB = 准备参与者并返回其旧 x/y(B)
    若准备结果无效：销毁技能执行对象；结束本局部路径

    change_coordinate(oldB.x, oldB.y, A.id, true, true, true, undefined)
    change_coordinate(oldA.x, oldA.y, B.id, true, true, true, undefined)
    更新朝向等后续状态
    分别向 A、B 派发后续伤害/效果闭包
    后续 Alarm 1 处理渲染恢复相关工作
```

这是专门的玩家换位链，本轮没有在其中看到 `scr_enemy_swap` 调用。另一个名称含 swap 的函数不能替代本链证明回避、工作移动或玩家施法规则。

### 4.1 具体例子与构造演算

真实案例选用 `Planar_Exchange → o_planar_exchange`。构造两个不同的普通 `o_unit` A/B，均满足第 3 节的门禁；假设 A 当前 x/y 为 `(100,200)`、B 为 `(300,400)`，且反射没有改换参与者。坐标数值是解释控制流的构造输入，未宣称来自运行截图或合法地图格中心。

第一次有效选择后，目标列表为 `[A]`，计数由 2 变为 1；第二次有效选择后为 `[A,B]`，计数变为 0，进入准备流程。执行先缓存 `oldA=(100,200)`、`oldB=(300,400)`，再把 A 传给 `(300,400)`，把 B 传给 `(100,200)`，随后分别进入效果闭包。即使第一个调用改变了 A，第二个调用仍使用先前缓存的 oldA。

若第二次仍选择 A，重复判断将候选变为无效并进入拒绝流程，不构成两个有效参与者。若 B 在准备阶段已不满足准备结果要求，执行可在坐标调用前中止。若第二次坐标提交内部失败，是否回滚第一次的位置、本次技能是否退款，本轮均未闭合。

## 5. 移动攻击的公共责任与门禁

两个选择对象 Create 均指定敌人组 3805（`o_enemy`）、`scr_line_filter`，并把 `delete_on_line` 写为真：

| 选择配置 | Crippling_Lunge | Heroic_Charge |
| --- | --- | --- |
| 选择 Create 入口 | `0x1445c6920` | `0x1445d8e90` |
| `scr_line_filter` 配置 | `0x1445c6ee1 / 0x1445c6ef3` | `0x1445d903e / 0x1445d9050` |
| `delete_on_line=true` 写入 | `0x1445c6f7e / 0x1445c6f94` | `0x1445d9096 / 0x1445d90ac` |

`scr_line_filter` 入口 `0x1413ff210` 调用 `scr_path_filter`（`0x1413ff437`）。这证明两招走真实线/路径筛选入口，不证明全部墙体、拐角、视线和多格怪物条件，也不等于“冲锋必定穿过障碍”。`delete_on_line` 的设置已核实，其全部消费者和具体删除时机未在本章完整恢复。

执行对象持有 owner 和 target。两招 Alarm 0 在进入主要移动逻辑前检查这两个实例是否存在，之后调用 `scr_tile_distance_min`，把结果写入 `turn_count`。**该字段在这里首先装的是距离结果，不是已证明的剩余逻辑回合计数。** 距离大于 1 时，它又被 `ds_list_empty(owner.lock_turn)` 的布尔结果覆写，用于门控继续移动。

因此可核实的公共局部规则是：

- 距离大于 1，且 owner 的行动锁列表为空，才调用共享移动。
- 距离大于 1、锁列表非空，不进入同一路径移动；随后相邻判断看到的是布尔假值 0，不是原始距离。
- 距离与 1 相等进入攻击准备/攻击分支；“相等”经过 YYC 比较辅助函数，不能声称已经恢复了所有浮点容差。
- 移动函数返回假，会用技能执行对象的 id 请求销毁。它不是对 owner 请求死亡。

`scr_one_path_move` 入口 `0x1418b5c20` 是共享移动入口。两招在 `with(owner)` 上下文传入 `(技能的 target, true, owner.id, undefined, undefined)`。它默认选择 `astar_grid_path_skill` 方法，读取目标坐标，含多格单位附近格解析、`scr_astar_get_cell`、路径点读取，以及 `scr_player_move / scr_change_coordinat` 的分支调用；也有备用路径分支。我们没有从名字推成完整 A* 代价函数，也没有证明每次调用恰好移动一个固定格距。

| 公共位置/路线证据 | VA |
| --- | --- |
| 默认路径方法地址装载 | `0x1418b635b` |
| 多格单位附近格解析调用 | `0x1418b6861` |
| 路径格选择调用 | `0x1418b6b8d / 0x1418b6ecb` |
| 读取路径点 x/y | `0x1418b778b / 0x1418b77cc`，另一路 `0x1418b7971 / 0x1418b79b2` |
| 玩家移动 / 通用坐标提交分支 | `0x1418b7a1e / 0x1418b7b50` |
| 公共坐标函数入口 | `0x1418bce40` |
| 坐标函数的碰撞清理分支 | `0x1418bda1d / 0x1418bdad1` |
| 碰撞补回 / 多格填充 / 位置事件分支 | `0x1418be392 / 0x1418be449 / 0x1418be524` |

公共坐标函数包含占用、碰撞、多格和位置事件维护。不是简单直接写 x/y；这些调用分布在条件分支内，本章没有将它们平铺成“每次移动一定全部执行”。具体障碍阻挡原因、备用路径选择和失败前是否已有局部副作用，仍需要继续核对。

## 6. 致残突刺：移动事件与攻击事件分离

实际链为 `o_skill_crippling_lunge → Crippling_Lunge → o_crippling_lunge`，执行对象继承 `o_moving_skill`。执行 Create `0x14403c480` 先调用父事件，父层默认行为不能从这个短入口单独恢复。

Alarm 0，入口 `0x14403c6c0`，局部顺序为：

1. 检查 owner/target 实例存在。
2. 调用最小距离函数，写入 `turn_count`，并准备位置/动画相关状态。
3. 首次执行相关分支设置 `is_execute`，包含技能 Buff 钩子。
4. 距离大于 1 时检查 owner.lock_turn；为空则调用共享移动。
5. 共享移动返回假，销毁技能执行实例；该分支之后仍有上下文退出/清理指令，不能理解成一般程序语言的立即 return。
6. 移动分支设置 `alarm[0]=2`，用于后续事件调度。数字 2 是 Alarm 值，不是已经证明的 2 个逻辑游戏回合。
7. 相邻分支准备攻击表现，调用 `scr_skill_set_alarm`。已读调用传入常量 1、10 和 owner/技能上下文；本轮不完整命名其全部五个参数。

后续 Alarm 1，入口 `0x14403ed70`，再次检查 owner/target 是否存在，并在 owner 上下文调用 `scr_skill_attack`。它还含 `is_take_injury=false` 和冷却相关处理；后者不能替代最终资源提交分析。

| 致残突刺证据 | VA |
| --- | --- |
| owner/target 存在门禁 | `0x14403c841 / 0x14403c88b` |
| 距离函数调用 | `0x14403c9ed` |
| `turn_count` 被锁列表为空结果覆写 | `0x14403d420 / 0x14403d43f / 0x14403d478` |
| 共享移动调用 | `0x14403d711` |
| 移动假值分支的执行实例销毁 | `0x14403d72c / 0x14403d78b` |
| Alarm 0 值 2 写入 | `0x14403d7fe / 0x14403d80c` |
| 相邻后的攻击 Alarm 调度 | `0x14403e022` |
| Alarm 1 owner/target 存在门禁 | `0x14403ef68 / 0x14403efb2` |
| Alarm 1 攻击调用 | `0x14403f094` |

```text
致残突刺 Alarm 0 的局部决策：
    若 owner 或 target 实例不存在：不进入主要移动/攻击准备路径
    gate = 最小距离(owner,target)
    保存 gate 到执行对象.turn_count
    若 gate > 1：
        gate = owner.lock_turn 列表是否为空
        保存 gate 到执行对象.turn_count
        若 gate 为真：
            ok = one_path_move(target,true,owner.id,undefined,undefined)
            若 ok 为假：请求销毁技能执行实例
            按原事件退出/清理；该移动分支调度 Alarm 0 值 2
            不在本移动分支直接调用攻击
    若当前 gate 与 1 相等：准备表现并调度后续攻击事件
    其余分支包括父事件处理，未全部恢复

致残突刺 Alarm 1 的已读攻击路径：
    若 owner、target 实例均存在：在 owner 上下文调用技能攻击
    其后处理相关状态和清理
```

**构造例子**：选中一个符合名义 Range=2 和选择筛选的敌人；假设最小距离函数返回 2、owner.lock_turn 为空，共享移动返回真。第一次 Alarm 0 走移动分支并写 Alarm 0 值 2，没有在该分支调用攻击。后续事件重算距离，假设返回 1，则进入攻击调度；Alarm 1 到达时两个实例仍存在，才调用攻击。这里的 2→1 是构造的函数返回序列，未声称实测路线、帧数或伤害。

若共享移动返回假，技能执行实例收到销毁请求；若攻击事件到达前 target 已不存在，存在门禁会阻止该主要攻击路径。若 target 只是 HP 为 0 但实例尚存在，这个门禁本身不能证明会阻止攻击。攻击调用也不等于一定命中或附加某状态成功。

## 7. 英勇冲锋：相邻后在同一处理入口攻击

实际链为 `o_skill_heroic_charge → Heroic_Charge → o_heroic_leap`。执行 Create 入口 `0x14401e280`，含 `cast_frame=0.5` 和 Alarm/延迟相关配置。Alarm 1 `0x14401ea20` 检查目标/owner、处理 Buff，并读取 target.x/y 和距离字段作为准备工作；不能因为 Alarm 编号为 1 就将它自动当成“攻击事件”。

主要移动与攻击在 Alarm 0，入口 `0x14401f340`：

1. 检查 owner/target 是否存在，重算最小距离并写 `turn_count`。
2. 距离大于 1 时，用 owner.lock_turn 是否为空覆写 `turn_count`；真则进入共享移动。
3. 移动失败请求销毁技能执行实例；移动分支写 `alarm[0]=3`，退出本次处理的这一路径。
4. 非移动出口对当前 `turn_count` 比较 1；相邻分支才调用 `scr_skill_attack`，之后调用 `scr_skill_hit`。

| 英勇冲锋证据 | VA |
| --- | --- |
| Alarm 1 Buff/目标坐标准备 | `0x14401ec7f / 0x14401ec8b / 0x14401ecec` |
| Alarm 0 owner/target 存在门禁 | `0x14401f4e6 / 0x14401f536` |
| 最小距离调用 | `0x14401f68f` |
| 距离大于 1 比较 | `0x144020049` |
| 锁列表为空结果覆写 `turn_count` | `0x1440200a9 / 0x1440200c8 / 0x14402012d` |
| 共享移动调用 / 失败销毁 | `0x144020392 / 0x144020406` |
| Alarm 0 值 3 写入 | `0x144020479 / 0x144020487` |
| 相邻比较 | `0x14402051c` |
| 技能攻击 / 后续技能命中处理调用 | `0x1440207ad / 0x144020881` |

```text
英勇冲锋 Alarm 0 的局部决策：
    若 owner 或 target 实例不存在：不进入主要路径
    gate = 最小距离(owner,target)
    执行对象.turn_count = gate
    若 gate > 1：
        gate = owner.lock_turn 列表是否为空
        执行对象.turn_count = gate
        若 gate 为真：
            ok = one_path_move(target,true,owner.id,undefined,undefined)
            若 ok 为假：请求销毁技能执行实例
            按原事件退出/清理；该移动分支调度 Alarm 0 值 3
            结束本次移动分支
    若当前 gate 与 1 相等：
        在 owner 上下文调用技能攻击
        调用后续 skill_hit 处理
    其余出口不在这里补造攻击
```

**构造例子**：选中通过名义 Range=3 和筛选的敌人；假设连续重算的距离结果为 3、2、1，每次需要移动时 owner.lock_turn 均为空，移动均返回真。前两个 Alarm 0 走移动路径，后续距离为 1 的 Alarm 0 才走攻击分支。因此“移动与攻击由同一处理入口负责”不等于“同一次回调先移动立即攻击”，也不等于连续调用一定消耗三个逻辑回合。

若开始距离为 3 但锁列表非空，`turn_count` 被覆写成假值 0：它既不进入共享移动，也不通过相邻比较 1。若移动失败，销毁的是执行对象。没有证据保证技能费用恢复、将 owner 自动送回原位或攻击仍继续。

## 8. 边界比较、失败语义与未知

| 问题 | 已读局部结论 | 仍未知 |
| --- | --- | --- |
| 换位选谁 | 两个不同单位；有特定禁止字段和交互门禁 | 所有合法阵营组合、玩家自选全流程、反射的完整替换规则 |
| 换位的原位置 | 两方各先缓存 x/y，再交叉使用 | 所有多格/特殊对象如何适配、内部失败如何恢复 |
| 换位与伤害顺序 | 双坐标调用在前，后续效果闭包在后 | 最终伤害、眩晕公式与所有抗性/被动修正 |
| 移动攻击选谁 | 配置 Target Object；选择组 o_enemy；线/路径筛选 | 每种障碍、拐角、视线、多格目标的全部选择规则 |
| 自移何时进行 | 距离 >1 且锁列表为空；共享移动 | 路径点索引、最终代价、每次实际格数、所有备用分支 |
| 何时攻击 | 致残突刺后续 Alarm 1；英勇冲锋相邻 Alarm 0 | 运行中的具体帧、动画取消、全套被动与最终命中 |
| 移动失败 | 假值分支请求销毁技能执行实例 | 已发生副作用、父销毁事件、费用/冷却是否恢复 |
| 相邻但实例未死亡清理 | 两个实例存在才进入主要路径 | 完整 HP/死亡/阵营变更/目标有效性检查分布 |
| 时钟 | Alarm 0 值分别写 2 和 3 | 与逻辑回合、暂停、帧率、存档恢复的完整映射 |

调查到的 `o_piercing_lunge` 父对象为 `o_aoe_spell_animated`，而非本章两招的 `o_moving_skill`。这是名称分类容易出错的实际反例；本章没有将所有含 Lunge/Charge 的对象统一归为自身移动攻击，也没有继续扩大到所有技能。

资源提交由公共层和具体技能共同决定。[第 16 章](16-skill-commit-and-ai-gates.md) 已读普通敌人施法路径不能直接套用成这三招玩家失败后的完整扣费/退款规则。本章未在上述移动假值出口恢复退款协议，**不等于证明所有移动攻击失败都绝不退款**。

## 9. 独立开发借鉴：我们自己的可测试规格

以下是自研建议，不是本轮确认的 Stoneshard 实现：

1. 将技能状态明确拆为选择、提交、接近、攻击、收尾。各阶段记录拥有者、目标 ID 与失败原因，不将同一 `turn_count` 同时当距离和布尔门控。
2. 换位用双方快照和占用预验证建立事务：先验证两端可接受，再同时替换占用；失败时返回结构化结果。移动、触发机关和伤害按我们产品要求确定顺序，给“第二端失败”建立回归用例。
3. 移动攻击把路径步进结果写成 `moved / blocked / target_invalid / owner_locked` 等明确状态；到达攻击距离后再次验证存活、阵营、武器和目标，不只验证实例存在。
4. 把动画 Alarm 与逻辑回合分开。一次用户动作如何扣费、移动多少格、受阻是否退款，应成为我们自己的公开契约，不根据原目标的 2/3 数值猜计费规则。
5. 测试至少覆盖重复选取、睡眠/禁止传送目标、两端占用冲突、移动后目标消失、锁列表非空、途中受阻，以及移动成功但攻击未命中。原游戏研究只提供设计问题与行为规格，不提供可直接移植的代码或资产。

## 10. 本机证据与本轮验证

正式说明只包含重新表达的控制流、配置摘录和自行编写的伪代码，不收录原始专有实现或台词。以下文件是本机静态核查产物，不是发行材料：

- [局部解码索引](../../../_reference/stoneshard-study/fifth-swap-native.json)：函数 VA、段大小、解码覆盖、调用与字段引用。
- [对象继承记录](../../../_reference/stoneshard-study/fifth-swap-object-metadata.json)：OBJT ID、记录偏移及父对象。
- [三招配置与完整表头](../../../_reference/stoneshard-study/fifth-swap-table-observation.json)，以及[本轮共同技能行索引](../../../_reference/stoneshard-study/fifth-skill-config-rows.json)。空首列表头不承担技能身份，身份取每行首单元。
- [常量构造定位](../../../_reference/stoneshard-study/fifth-swap-constant-initializers.json)：技能键、giant、sleep 等绑定；仅用于补注册常量来源。
- [换位执行](../../../_reference/stoneshard-study/fifth-swap-disassembly/gml_Object_o_planar_exchange_Alarm_0.txt)、[换位选择](../../../_reference/stoneshard-study/fifth-swap-disassembly/gml_Object_o_skill_planar_exchange_Other_20.txt)。
- [致残突刺移动](../../../_reference/stoneshard-study/fifth-swap-disassembly/gml_Object_o_crippling_lunge_Alarm_0.txt)、[致残突刺攻击](../../../_reference/stoneshard-study/fifth-swap-disassembly/gml_Object_o_crippling_lunge_Alarm_1.txt)、[英勇冲锋](../../../_reference/stoneshard-study/fifth-swap-disassembly/gml_Object_o_heroic_leap_Alarm_0.txt)。

早期 `fifth-swap-builtin-reference-probe.json` 的“后一条记录名称候选”不作为证据；它会错配相邻字段。本章字段已经以 ref−8 名称指针重新核对，x/y/id 等短名字也纳入解码标注。

验证：针对这三招重新核对表行、继承、主要门禁、with 上下文实参和事件调用顺序，检查文档 UTF-8、相对链接及伪代码围栏。本轮选择静态续查，没有执行游戏、实机行为或存档测试；既有的必要运行授权继续保留，实际时序与复杂场景仍待运行核对。剩余风险是未闭合动态派发、父事件和辅助函数契约；这些风险已在各段明确保留，不能拿构造演算代替实测。
