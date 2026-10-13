# 24 主动探查与隐藏物揭示

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [23 玩家视野与战争迷雾](23-player-vision-and-fog.md)

本篇恢复一个真实动作的局部执行链：内部配置名 `Trap_Search`，执行对象 `o_trap_search`。它搜索陷阱和秘密门，让当前迷雾可见性参与发现机会的准备，再经过公共概率助手决定是否写入目标状态。**它不是统一的“揭示所有隐藏信息”接口**：玩家视野、敌人发现玩家、局部隐藏交互物、世界地图地点标记，各有不同入口和状态。

本轮没有在已解析的 42,825 条 `data.win` 字符串中找到 `Examine Surroundings` 等指定显示名称。因此可以确认内部动作及算法，尚不能仅凭习惯名称确认当前语言界面上哪一个按钮与之同名。技能图标到技能对象的绑定已确认；按钮输入到本次执行对象创建的完整派发仍有缺口。

## 1. 身份、方法和覆盖

沿用本机 `E:\Steam\steamapps\common\Stoneshard`，本轮开始时间为 2026-10-12 19:30:59 PDT。根调查重新读取完整摘要，EXE 为 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，`data.win` 为 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`；与前轮一致。

这里的新增来源是本地资源索引及选定原生函数的 Capstone 5.0.9 解码。没有可用的完整 REA provider 会话，不能把这些记录标为 REA Evidence。元数据名称按 RIP 引用地址前 8 字节的指针核对，数值类型和调用参数共同验证含义。下文“指令确认”限于给出的入口与分支，不等于全游戏动态覆盖。

覆盖包括动作/图标 Create、执行 Alarm0、搜索助手、默认可见性助手、公共概率助手、视觉效果三个事件、陷阱 Create/Step，以及两个世界地图对话揭示入口。没有启动或附加游戏、改制品或存档、读取新存档、监测网络。搜索效果的帧表现和动作实际占用多少逻辑回合尚未采集。

本机可选证据：[本轮身份](../../../_reference/stoneshard-study/seventh-target-identity.json)、[原生入口与引用](../../../_reference/stoneshard-study/seventh-detection-native.json)、[选定资源和配置](../../../_reference/stoneshard-study/seventh-detection-resources.json)、[显示名称搜索范围](../../../_reference/stoneshard-study/seventh-detection-ui-label-search.json)。这些文件可能没有随仓库同步；本文保留关键地址、值和分支，阅读结论无需依赖本机文件。

## 2. 配置和对象职责

真实表头为 `Object/Target/Range/KD/MP/.../Duration/.../Pattern/...`。EXE 文本 `0x145e4bed0` 中的行是 `Trap_Search;o_trap_search;No Target;0;0;0;0;0;0;0;0;normal;;skill;0;;none;0;;;0;0;;;;;;;`；初始化登记在 `0x140bd87d2`，保存槽为 `0x14980ce50`。

| 配置值 | 本次真实值 | 可以说明什么 |
| --- | --- | --- |
| Object | `o_trap_search` | 动作对应的执行对象 |
| Target | `No Target` | 配置不要求选取一个目标 |
| Range / KD / MP | `0 / 0 / 0` | 配置层目标范围、冷却和能量字段；不等于搜索半径为零或没有行动成本 |
| Duration | `0` | 配置字段；不能拿来解释已发现陷阱的状态寿命 |
| Pattern | `normal` | 通用技能表字段；本次真实搜索没有调用 AOE 形状生成器 |

`o_skill_trap_search.Create0 @0x144646c40` 在 `0x144646cb4..ccd` 写 `skill="Trap_Search"`，在 `0x144646d35` 调 `scr_skill_atr(10)`，随后写 `target_group=7931`。`7931` 是资源 `o_trap`，不能把它解释为 7,931 格半径。

图标 Create `0x1447f8e20` 写 `child_skill=6319 @0x1447f8e9d..eae`，正是 `o_skill_trap_search`。通用 `scr_skill_atr @0x14172b790` 调 `scr_create_skill_map @0x14172bcce`，读取 `Target/Range/idName` 等字段；`spell` 写入对应读取在 `0x14172c05e..c0bb`。这一段证明配置参与技能属性构造，尚未完整恢复表中 Object 如何转换为运行时 idName 的所有路径。

| 对象 ID | 名称 | 父 ID | `data.win` OBJT 记录偏移 |
| --- | --- | --- | --- |
| 2039 | `o_trap_search` | 5531 | 9983040 |
| 5531 | `o_target_spell` | -100 | 11152960 |
| 6319 | `o_skill_trap_search` | 6199 | 11467416 |
| 6713 | `o_skill_trap_search_ico` | 6423 | 11603904 |
| 7931 | `o_trap` | 5409 | 11964984 |
| 3654 | `o_net_trap` | 7931 | 10478736 |
| 9495 | `o_secret_door` | 650 | 12399048 |
| 5633 | `o_search_effect` | -100 | 11196928 |

对象父索引来自记录 +28 字段，ID 是资源索引。通用 `scr_cast_spell @0x14185bce0` 的确会创建选定执行对象（`instance_create_depth @0x14185c718`）并写其 owner/target/point 等参数。**尚未找到玩家输入专门以 `Trap_Search` 进入该助手的完整调用链**，所以不把这段通用能力冒充已经闭合的按钮提交。

## 3. 执行入口：搜查和动画分开创建

父对象 `o_target_spell.Create0 @0x144007990` 写 `alarm[0]=2 @0x144007c99..cb7`。资源确认 `o_trap_search` 继承该父类，登记索引没有同名子 Create；这支持默认创建调度路径，但未运行检查特殊创建方是否随后覆盖 Alarm。Alarm 计数是引擎事件排程，不能直接换算为“两个逻辑回合”。

真正的探查业务在 `o_trap_search.Alarm0 @0x143036c30`：

1. 在 `0x143036d36..d60` 以对象 ID 5376 进入 `o_player` 上下文。
2. 播放声音，随后在 `0x143036ea5` **调用 `scr_trap_find(false)`**。假值参数来自 `0x143036e79` 的 type 13、数值零，区别于 undefined。
3. 在 `0x14303709b` 创建 ID 5633 的 `o_search_effect`，坐标为玩家 `x`、`y+5`，深度为玩家 `depth+20`。这里 5/20 是原作常数，坐标来自当前 player。
4. 选取 `o_pass_skill_trailblazer`（9294），派发 user3 `@0x14303711b`；本轮未恢复这个被动技能的奖励内容。
5. 调 `scr_stop_player @0x1430371cc`，离开 player 上下文后销毁当前执行对象 `@0x14303723e`。

因此可以确认搜索助手在视觉效果创建之前被调用；动画消失不是搜索成功提交的条件。本轮尚未核对 `scr_stop_player` 对玩家 Alarm、动画和逻辑回合的全部影响。

## 4. 当前可见性参与机会准备，配置 Range 不代表搜索半径

搜索助手 `scr_trap_find @0x141722070` 先遍历对象 `o_trap` 及引擎所纳入的子类（with 选择在 `0x141722440..46d`）。这是对象候选集合，不是生成一组方形 AOE 格子。对隐藏陷阱读取自身和玩家的 `grid_x/grid_y`，调用 `point_distance @0x14172288b`，再 `round @0x1417228de`，得到格坐标距离 `D`。

正常存在 `o_fogrender`（7005）的地图中，助手在 `0x141722a1b` 调 `is_visible(undefined,undefined)`。此时 self 是当前陷阱：

- `is_visible @0x140bbaab0` 把第一个 undefined 转为 self.id（`0x140bbadcb..ae11`），第二个 undefined 转为 false（`0x140bbae67..ae9a`）。
- 第二参数 false 的正常地图内分支调用 `scr_checkUnitFogVisible @0x140bbb19f`，读取的是当前迷雾可见格。
- 第二参数 true 才直接读对象的引擎 `visible` 字段（`0x140bbb345..37a`）。这不是本动作传入的模式。

这个区别很关键：**“隐藏陷阱在玩家当前可见格内”与“陷阱本身已显示”是两份状态**。主动探查可以检查前者并把后者改为真；如果先要求陷阱 visible 为真，隐藏物发现算法就无法成立。

可见性为假时，搜索助手将机会设为0；它仍调用公共概率助手。由于该助手还会使用未知运行时下限，这里不是已经证明的“视野外绝不成功”硬拒绝。因此可以确认可见性参与发现规则，尚不能划定绝对的最终成功范围。

该可见性助手还检查 grid 与地图尺寸/26 的边界后才进入 fog 查询。但其局部默认结果为 true，边界失败并不是已经证实的 false 返回；本文仅解释正常地图内目标，不给界外目标作保证。没有 fogrenderer 时有包含常数 15 的距离替代门禁（`0x141722a74..a9f`），其精确比较关系未闭合，不据此声明无条件 15 格搜索半径。

迷雾格的遮挡、更新、当前/曾经探索状态，请结合 23 阅读。本篇没有发现主动搜索在此分支把视野外 fogmap 全部打开的写入，也没有恢复透墙规则。

## 5. 普通陷阱和网陷阱采用不同机会规则

可见陷阱由 `visible` 检查直接进入 `locate=1` 的分支（`0x1417226ba..272b` 与公共写入 `0x141724980`），不重复走新发现通知。隐藏陷阱在当前可见性为真后处理以下规则。

| 条件 | 准备的机会值或处理 | 关键位置 |
| --- | --- | --- |
| D=0 | 初始机会为 100 | `0x141722b42..b5f → 0x1417231aa` |
| 本主动动作参数 false | 初始机会为 100 | `0x141722b89..b90 → 0x1417231dd..321f` |
| 当前可见性为假 | 机会写 0 | `0x141722b08 → 0x141723170..3445` |
| `unfindable` 为真 | 机会覆盖为 0 | `0x1417233f1..3445` |
| `object_index=3654`，主动参数 false | 机会改为 `(5+P)/D`，P 从角色属性键 `PRC` 取得 | `0x141723b45..be6 → 0x141724027..`，运算 `0x14172255f/257e/2630` |
| 成功 | 普通目标写 visible；特殊 spawner 派发 user8 | `0x14172353b..3597`、`0x1417235db..5f5` |

可见性/unfindable 的0分支只是机会改写，尚不能当作最终硬拒绝。主动普通陷阱的 100 与网陷阱公式不能合并。网陷阱的判断在初始机会之后，足以覆盖初始的 100；它读取 PRC 的真实值，然后用加法和除法助手完成公式。P 不是本篇虚构的玩家固定感知属性。

公共成功判定是 `scr_chance_value @0x1413e5360`，陷阱调用位置 `0x14172353b`，传入机会值及两个 undefined。助手将未指定的成功结果设为 1（`0x1413e564a..565b`），失败结果设为 0（`0x1413e56f5..5703`）。对有限 double 的机会 100，它比较机会与 100（`0x1413e573f`），非负比较结果直接返回成功值（`0x1413e575c..57cb`），不会进入后面的随机抽取。

有限 double 比较路径沿用本机已经解码的 RValue compare，绝对差不大于 `0.00001` 时视为相等。因此这个上界分支有浮点容差，不应把其精确实现改写成任意动态类型都严格 `p>=100`。

较低机会路径调用 `0x1451de240(100) @0x1413e58fb`；之前已证实这个随机基础返回包含两端的整数 0..100，采用底层随机数取余，并非已经证明的严格均匀分布。结合 [19 公共概率助手](19-kick-pull-and-knockback.md) 已核对的有限数值辅助函数，本路径先取 `threshold=max(机会值,未命名运行时下限槽)`，再判断随机值是否有序小于 threshold。比较有 `1e-5` 容差；下限槽在运行中的具体值尚未确认，不能把 PE 初始零当成实际下限。因此 `(5+P)/D=5` 是真实中间机会值，不能承诺“恰好 5% 成功”，也不能仅凭机会为 0 宣称最终随机判定绝不成功。

## 6. 成功状态、通知和状态寿命

普通非 spawner 的成功分支先写 `trap.visible=1 @0x1417235db..5f5`。之后检查 `locate/is_spawner`；已发现或 spawner 的路径跳过普通新发现通知。普通首次发现会产生 `spotTrap` 等通知/效果，更新统计 `trapsFound+1 @0x14172490a`，写 **trap.locate=1 @0x141724933..493d**，并把 **player.path=-1 @0x141724952..4987**。最后一个字段的接收者是搜索外层 player，不是陷阱；它体现搜索可影响玩家当时的路径状态。

`is_spawner` 成功分支派发的是被选目标 user8，而非统一 visible 写入。只解码了 `o_trap.Other18` 不足以覆盖每个子类的覆盖实现；其通用事件还含目标、陷阱噪声和心理状态处理，不将它概括为“与普通陷阱一样显示”。

陷阱 Create 的默认初始化是 visible=0（`0x144d832c9..2df`）、locate=0（`0x144d832ee..331c`）、unfindable=false（`0x144d82943..2971`）和 is_spawner=false（`0x144d83c03..c31`）。这说明普通实体有可表达“未显示/未定位→已显示/已定位”的状态；子类 Create、读档和关卡创建方仍可能覆盖默认值。

已查的 `scr_trap_find` 成功写入及 `o_trap.Step0 @0x144d8b530` 没有给 locate 设置倒计时或每帧递减。**这只能确认已查路径没有自动到期机制，不能证明永久保存**：尚未逐个追陷阱 Alarm/其他事件、离图重建和读档。更不能把动作表 Duration=0 或视觉对象 charge=2 当成陷阱揭示时限。

## 7. 秘密门：同一个动作，另一份结果状态

同一 `scr_trap_find` 在结束陷阱遍历后，检查并遍历对象 ID 9495 的 `o_secret_door`（`0x1417249df..4a30`）。它读取 `is_open`，真值分支跳过该候选（`0x141724a7e..aad`）。对未打开候选，重新计算格坐标距离，使用 `point_distance` 和 `round`，再应用存在 fogrenderer 时的默认 `is_visible` 检查（`0x141724dd5`）。

主动参数 false 或 D=0 的机会设为 100（`0x141724f38 → 0x1417253ea..5420`）；可见性为假则设为 0（`0x141724eb0 → 0x141725370..539c`）。另一真参数分支有 `0.5*PRC/D` 运算（`0x14172546a/5489/54d5`），但本动作传 false，不把这个公式套到主动搜索。

公共机会判定在 `0x1417255ea`。成功后先统计 `secretRoomsFound+1 @0x14172569c`，然后通过对象选择 9495 写 **is_open=1 @0x1417256e6..6fb**，并调用心理变化 `scr_psy_change("MoraleSituational","secret_find") @0x141725961`。这份状态与 trap.visible/locate 不相同。

本轮没有闭合这次 is_open 写入到房间墙体、碰撞、门动画和多秘密门场景的全部消费者。因而“成功分支标记该秘密门类的 is_open”已确认；“立即穿过墙”“一次揭开秘密房间内所有内容”“多个门一定逐实例处理”尚未证明。

## 8. 构造演算：同一视野内也可能走不同路线

以下坐标、PRC 和对象状态是构造输入，供演算使用，不是运行截图、存档或原作角色默认属性。设玩家格 `(10,10)`，三个目标均是正常地图内目标，当前 fog 查询均返回真。

| 目标 | 构造属性 | 距离与机会 | 可确认结果 |
| --- | --- | --- | --- |
| 普通隐藏陷阱 A `(13,14)` | visible=0、locate=0、unfindable=false、is_spawner=false | D=round(sqrt(3²+4²))=5；主动初始机会100，不走网陷阱覆盖 | 概率助手的100分支直接成功；visible=1、locate=1、首次发现统计+1，player.path=-1 |
| 隐藏网陷阱 B `(13,14)` | object_index=3654，其余同 A；PRC=20 | D=5；初始100被覆盖为 `(5+20)/5=5` | 进入较低机会随机路径；本篇不能把结果确定为成功或换算精确百分比 |
| 秘密门 C `(10,14)` | is_open=false | D=4；主动机会100 | 进入成功分支，secretRoomsFound+1，并写 is_open=1；物理开门后续仍待核 |

若把 A 的当前 fog 查询改为假，机会变为 0，不再走机会100的直接成功路径。若 A 已 visible=1，则走已可见定位分支，不重复上述“隐藏陷阱首次发现”的所有通知。若 A 设 unfindable=true，机会也会被覆盖为0。机会0仍经过未命名运行时下限槽参与的 threshold 处理，槽实际值未确认；不能把设计上常见的“0永不成功”强加给原作。

网陷阱 D=0 的构造例子不在本轮演算中：公式路径是否仍会除以0、引擎如何处理、是否有现实场景约束，需要专门验证，不能用普通陷阱的 D=0 初始100分支掩盖后续覆盖。

## 9. 搜索视觉的 charge 不是已揭示状态的寿命

`o_search_effect.Create0 @0x14412cb80` 写 charge=2（`0x14412cbd6..cc0b`）、image_speed=0.4（`0x14412cc2d..cc37`）。Step 在玩家存在时跟随其 x、y+5（`0x14412cd91..ce62`）；charge=1 分支将 image_alpha 除以原作常数1.3（`0x14412cea4..cf39`）。Other7 从 charge 减1（`0x14412d34a`），再比较并可能销毁（`0x14412d397..3c2`）。

这是真实的表现生命周期。Other7 与引擎动画事件对应，尚未采集画面上的实际时长；其销毁条件辅助比较的完整动态类型路径也未全部复核。但已经足以区分：它没有恢复 trap.locate=0 或 secret.is_open=0 的调用，charge不属于目标状态。原作常数0.4/1.3仅解释此效果，不是我们新游戏的推荐参数。

## 10. 世界地点揭示和敌人侦察的边界

另外两段真实入口证明世界地图揭示有独立链：`scr_dialogue_reveal_papermap_location_area @0x1422e8860` 调 `scr_glmap_getLocation @0x1422e8dd7`，读地点 x/y 后调 `scr_dialogue_reveal_papermap_area @0x1422e8f3e`。后者在 `0x1422e9a7a` 调 `scr_globalmapMarkPOI`，在 `0x1422e9c74` 调 `scr_globalmapPaperUpdateRadius`。

这组入口操纵的是地点/纸地图接口，不是本篇陷阱 visible 或局部 fog 查询。NPC 对话如何提供位置、范围、价格、重复购买防护和保存语义，本轮仅定位入口，尚未贯通，不能保证任意“侦察服务”都调用它。

敌人发现玩家的视线与听觉见既有 [03 敌人感知](03-enemy-perception.md) 及本轮声音研究。Alarm0 播放声音的调用存在，但播放声音不自动等于 AI 听觉网格已经产生同样的传播。不能用本动作的范围解释敌人察觉范围，也没有证据支持“这次主动搜索不会引起敌人反应”。

## 11. 独立开发可以借鉴的规格

从已确认结构可借鉴：先收集隐藏物候选，再查询玩家当前可见性并改变机会值；按对象种类定义发现规则；成功结果写到隐藏物自己的状态，通知与统计另行处理；搜索视觉有单独的生命周期。这些职责拆开后，能解释为什么动画结束不应撤销已经发现的陷阱。

我们的实现应从产品需求重新选择规则，而不是复用恢复代码或原作常数。例如可以明确把机会钳制到0..100，并规定0永不成功、100必定成功；用离散格距离或平方距离；为网陷阱定义 D=0 的显式结果；把可见、已发现、已交互和世界地点已知定义为不同状态；决定离图和保存是否保留发现。**这些是我们的独立建议，原作只确认本文列出的局部机制**。

如果需要一回合占用、失败反馈或可撤销的揭示效果，应另建清楚的逻辑时间与取消规格。本轮没有证明原作搜索恰好消耗一回合，也没有证明原作失败返回和动作成本完全一致。

## 12. 证据表和未决问题

| 问题 | 证据位置 | 等级与范围 |
| --- | --- | --- |
| 真实技能表和对象身份 | 文本 `0x145e4bed0`；OBJT偏移9983040/11964984/12399048 | 资源确认 |
| 图标绑定与技能名 | `0x1447f8e9d..eae`；`0x144646cb4..ccd` | 指令确认 |
| 主动参数、执行与销毁 | `0x143036ea5`、`0x14303709b`、`0x14303723e` | Alarm0局部调用确认 |
| 格坐标距离与fog门禁 | `0x14172288b/28de/2a1b`；`0x140bbb19f` | 输入和默认模式确认，界外/无fog分支未闭合 |
| 普通机会100与网陷阱公式 | `0x1417231dd..321f`；`0x141723be6→0x141724027→0x14172255f/257e/2630` | 主动路径确认 |
| 概率100特殊成功与低值随机 | `0x1413e573f..57cb`；`0x1413e58fb` | 有限double局部链确认，低值运行时下限未知 |
| 成功状态与统计 | `0x1417235db..5f5`、`0x14172490a/493d/4987` | 普通非spawner首次发现分支 |
| 秘密门机会和写入 | `0x1417253ea..5420`、`0x1417255ea/569c/56fb` | 隐藏门局部链；物理消费者未知 |
| 世界地图独立入口 | `0x1422e8f3e`、`0x1422e9a7a/9c74` | 静态调用确认，无完整服务交易 |

可选反汇编：[搜索执行](../../../_reference/stoneshard-study/seventh-detection-disassembly/gml_Object_o_trap_search_Alarm_0.txt)、[搜索与秘密门助手](../../../_reference/stoneshard-study/seventh-detection-disassembly/gml_Script_scr_trap_find.txt)、[可见性](../../../_reference/stoneshard-study/seventh-detection-disassembly/gml_Script_is_visible.txt)、[概率助手](../../../_reference/stoneshard-study/seventh-detection-disassembly/gml_Script_scr_chance_value.txt)、[陷阱初始化](../../../_reference/stoneshard-study/seventh-detection-disassembly/gml_Object_o_trap_Create_0.txt)、[搜索视觉](../../../_reference/stoneshard-study/seventh-detection-disassembly/gml_Object_o_search_effect_Create_0.txt)、[世界地点入口](../../../_reference/stoneshard-study/seventh-detection-disassembly/gml_Script_scr_dialogue_reveal_papermap_location_area.txt)。比较容差的可选来源是 [有限数值比较路由](../../../_reference/stoneshard-study/fourth-telegraph-compare-route.json)，随机基础见 [随机运行时](../../../_reference/stoneshard-study/second-perception-disassembly/runtime-0x1451de240.txt)。

已回答：真实主动动作的配置/对象、正常地图内的候选和可见性对机会的影响、普通与网陷阱差异、秘密门成功状态，以及视觉和揭示状态分离。部分回答：动作创建排程、机会函数、状态寿命、世界地点接口。未回答：界面显示名称的确切映射、玩家输入到创建的派发、精确回合占用、低机会实际下限与边界表现、D=0网陷阱、子类spawner全部结果、发现状态的离图/保存/重置、秘密门物理变化以及完整侦察服务。

验证使用静态指令读写、配置列、OBJT父索引和构造演算，没有运行时测试。风险主要是局部调查不能证明所有子类和时间/保存路径；本篇不保证无联网、无报警或任意目标均可完整还原。交付不包含可用于发售的恢复代码或专有资产。
