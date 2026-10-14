# 48．远程选位的候选竞争、最终返回与无路处理

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [前轮格门禁](41-ranged-ai-position-scoring.md) · [弩手动作消费](33-arbalester-skill-scoring-and-action-choice.md) · [巨石实体](46-combat-terrain-and-entity-consumption.md)

**本轮从“有空间检查”推进到两个真正的选择器：目标周围的远程射线候选按路径点数严格取小；当前单位周围的九格候选累计局部贡献、严格取大，再经过末尾覆盖条件返回。** 已恢复实际比较、平分、坐标换算、无路哨兵和消费字段；仍不能宣称恢复了任意战场的完整最优下一步。远程圆周搜索和九格评分是不同层，不能合并为一个未经证实的距离权重公式。

目标为00中固定摘要的 GameMaker YYC x64 Stoneshard。本轮复用eleventh静态证据，并补解九个登记入口、一个整数比较上下文，以及从dataLoader实际入口连续解码得到的初始化调用窗口；使用Capstone 5.0.9。这些是普通文件静态后备证据，不是REA Evidence。新制品摘要由[本轮身份](../../../_reference/stoneshard-study/twelfth-target-identity.json)固定。REA缺失记录继续沿用，没有setup、启动或附加目标，没有修改制品、存档或监测网络。

## 1．三个层次与实际消费者

| 层 | 输入／输出 | 本轮新增结论 |
| --- | --- | --- |
| 远程射线搜索 | `range_tile_find(target, radius, threshold, selfID)` → 三元素数组 | 最少路径点数胜出；平分保持前者；全无合格候选保留初值 |
| 新版目标格查询 | 远程结果、状态、危险、占格和九格贡献 → 两元素像素坐标数组 | 九格累计分严格取大；末尾可能覆盖为当前像素位置 |
| 敌人动作选择 | `find_target_tile_new(false)` → 敌人`pathTargetTile`，随后评分与执行 | 结果被真实主选择器保存；空间位置不自动成为胜出技能 |

主入口`o_enemy.Other12@0x143644cd0`先取得`pathTargetTile`写引用（`0x14364505d`），在`0x1436450af`调用新版查询，随后`0x1436450c5`把输出复制进该字段。这补足33里只称工作值targetTile的所有权：**结果由当前敌人实例保存**。消耗品评分消费与技能竞争继续遵循33，不把选位结果等同于本回合一定移动。

新版查询入口`0x14063cb30`的已解首段为69526字节。它含多个状态、AOE、近战、远程和特殊对象路径；完整字节解码不等于解释全部可达组合。本章将真实选择环与尚未绑定生产者分开。

## 2．远程搜索实参不是固定写死的射程

当前单位读取`is_shoot`并保存局部值（`0x14063edb8→0x14063edce`）。在已到达的射击路径中，调用`range_tile_can_search(self.id)`（`0x1406428e5`）；返回假即跳过本次远程搜索（`0x1406428f4`）。法师还有另一门禁路径，不能将它们称为同一个“远程单位必做”的条件。

这个门禁本轮补闭合了普通self.id调用的主要路径：

1. `object_is(unit.object_index,3804)`须通过（`0x1408c5725`），3804为o_unit。
2. `unit.is_shoot`为真，或者`range_tile_can_use_skill(unit.id)`返回真（`0x1408c575e / 0x1408c57e8`）。技能助手的全部内部许可仍未展开。
3. `is_player(unit.target)`须为真（`0x1408c5869 / 0x1408c5878`）。不能把这条搜索门禁推广为对所有NPC目标都相同。
4. 本次tile_distance_math(unit.id,target)的结果须不大于`unit.VSN * global.range_tile_search_vsn_factor`（乘法`0x1408c597d`、距离`0x1408c599f`、大于则继续拒绝`0x1408c59de`）。本轮已绑定这个vsn因子的初始化值为1，详见下表；不保证其他运行路径从不改写它。
5. 调用`enemy_vision_check(target,unit.id,undefined)`（`0x1408c5ac2`），**返回假才转到输出布尔真**（`0x1408c5ad1→0x1408c5c9b`，true写`0x1408c5cc8`）；返回真继续结束为false（`0x1408c5b57`）。因此此入口会在已有视线检查失败时寻找射击位置，不是“看得见才能搜索”。

这是所选普通有限路径的条件链，保持距离助手和视线助手实际语义；异常类型与遍历无实例不能省略为成功。具体门禁例：射击单位、玩家目标、距离5、VSN=6、构造vsnFactor=1，且上述视线返回false，则到达true输出；将距离改为7则在视线之前被拒绝；只把视线改为true则最终false。此例并未模拟具体墙角，也没有把helper返回false直接命名为“撞墙”。

调用者先将单位`range`更新为`min(currentVSN, range)`（字段读取`0x140642943 / 0x140642959`，min调用`0x1406429b2`），再构造四个实参，于`0x140642bea`调用：

```text
range_tile_find(
    self.target,
    self.range * global.range_tile_search_max_factor,
    self.range * global.range_tile_search_threshold_factor,
    self.id)
```

两因子分别读取`0x14063d57d`和`0x14063d593`；乘法在`0x140642ae5`、`0x140642b64`。新增`scr_enemy_range_tile_search_init@0x140789830`明确写入三个初始化值；`o_dataLoader.Other10`实际调用位置为`0x142ce41ce`，已从其登记入口连续解码核对，非只扫到E8字节猜调用。

| 全局因子 | 初始化值 | 写入VA |
| --- | ---: | --- |
| `range_tile_search_vsn_factor` | 1 | `0x140789908` |
| `range_tile_search_max_factor` | 1 | `0x14078992a` |
| `range_tile_search_threshold_factor` | 0.6 | `0x140789950–0x14078995a` |

因此沿这个初始化且没有其他改写，radius=range，threshold=0.6*range。不是0.5阈值，也不是固定格数。该结论是默认初始化与明确消费者，不是读取到一场正在运行的战斗配置。range字段自身被min修改后再使用，不是仅计算一份不影响后续的局部min。

返回数组前两项复制为查询内部格坐标（`0x140642c70 / 0x140642ce1`），随后转换到像素单位；第三项路径点数存在于助手输出中，但此调用点没有把它当成最终九格utility分。

具体条件例：构造`currentVSN=6`、原range=8，沿已确认默认因子且没有其他改写，则本路径先写range=6，再传radius=6、threshold=3.6。VSN与原range是构造输入，1／0.6是实际初始化常量。若构造外部改写两因子为1.25与0.75，则会传7.5／4.5；这组改写不是原作已确认的常规路径。

## 3．射线候选生成：16度步长与22次预算

`scr_enemy_range_tile_find@0x1401bdd80`读取实参0的`grid_x/grid_y`为中心T，读取self的格坐标U；方向助手`0x1451de650`在`0x1401be13b`计算T→U的角度。该方向助手使用float坐标；不是把向量归一化结果直接当角度。

本助手明确设置角步长16（`0x1401be1a3`），将360除以16（`0x1401be1e7`），截断为整数循环预算（`0x1401be2f6`），所以普通有限路径得到22。**这不是16个候选，也不是完整圆周的逐格遍历。**

每次准备的浮点端点为：

```text
endX = round(T.grid_x + cosDegrees(angle) * radius)
endY = round(T.grid_y - sinDegrees(angle) * radius)
```

dcos/dsin调用`0x1401be3bc / 0x1401be520`，乘radius `0x1401be404 / 0x1401be564`，x相加`0x1401be458`、y相减`0x1401be5b8`，round `0x1401be665 / 0x1401be6e6`。格舍入可能使不同方向产生相同端点，没有在这一段见通用候选去重。

随后`raycast_collision_hit(Tx,Ty,endX,endY)`（`0x1401be787`）返回H。预算在射线结果比较后减1（`0x1401be836–0x1401be83d`）。通常继续路径会在`0x1401bef95`令angle+=16；但距离拒绝`0x1401bec4b`直接回循环头，绕过角度增加，仍已经减少预算。**22次预算不保证22个不同方向。**

构造例：T=(10,10)、U=(14,10)、radius=5，方向为0°时端点为(15,10)。下一次真正经过角度增加的扫描才尝试16°。如某条拒绝路径绕过增加，则下次预算仍可能再试0°，不能用均匀22点模型替代实际控制流。

## 4．射线结果布局与筛选

新解`raycast_collision_hit@0x1401afb70`首先将全局`__raycast_hit_x/y`设为输入起点、len设为0，选择controller的newgrid，再调用`scr_raycast_mod`（`0x1401affa2`）。末尾建立数组，三项分别来自这些全局槽（复制`0x1401afff4 / 0x1401b0004 / 0x1401b0013`，建数组`0x1401b004a`）：

```text
H = [hitX, hitY, hitLength]
```

这证明结果布局和网格来源；完整raycast_mod如何逐格前进、哪种编码停射线尚未在本篇全部恢复。不能仅把hitLength解释为物理欧氏距离或把结果称为“第一个墙格”。

range助手先比较H[2]与threshold（`0x1401be831`），普通有限路径小于门槛则跳过寻路。合格H的x/y乘26，再加13，得到格中心像素；调用`path_to_point`（`0x1401beb20`），其第三实参是传入selfID，第四实参在此显式传undefined。

又调用tile_distance_xy，以生成的舍入端点与T做距离查询（`0x1401bec2e`），普通有限路径要求结果严格小于radius，才继续路径成功／分数比较。**这处比较用的是生成端点，不是H撞击坐标。** 默认／模式参数是实际运行槽，经本篇未全面恢复的距离助手解释；不强行替换为欧氏、Manhattan或Chebyshev。

具体例：构造threshold=4.5，某射线H[2]=3则预算已减，但不会调用该轮path_to_point；H[2]=5则继续。即使H合格，若后面的距离查询返回7.5且radius=7.5，该轮也跳回头，不参加最佳路径比较。阈值是两层独立门禁，不是同一个范围条件。

## 5．真正的远程评分、平分与无路初值

助手开始把bestX/bestY设为T格坐标（`0x1401be269 / 0x1401be283`），bestCount设为99999（`0x1401be243–0x1401be24d`）。因此未找到位置并不返回普通布尔假，也不是必然返回self坐标。

`path_to_point@0x141c48360`选定路径调用A*包装（`0x141c48fc9`），根据结果真值决定返回已创建路径引用还是数值−4（判真`0x141c492cb`，失败写`0x141c49338–0x141c49342`）。range助手用−4作为失败比较值（`0x1401bec65 / 0x1401bec8b`）；失败跳到增加角度并继续，**不立即终止整个搜索**。

成功路径上查询`path_get_number`（`0x1401bed1b`），对pointCount与bestCount作严格有序小于（`0x1401bed52–0x1401bed62`，排除unordered返回−2）。仅更少时更新bestCount、bestX、bestY（`0x1401bedbd / 0x1401bee92 / 0x1401bef06`）。相等不替换，所以同分留先者。

```text
best = [T.grid_x, T.grid_y, 99999]
对本助手实际扫描到、通过两个距离门禁的H:
    p = path_to_point(H的格中心像素, selfID, undefined)
    如果p == 数值-4: 继续扫描
    n = path_get_number(p)
    如果orderedLess(n, best.pointCount):
        best = [H.x, H.y, n]
返回best
```

返回三元素数组在`0x1401bf076`。同一成功处理段写`self._path_final`（`0x1401bed72→0x1401bed96`），随后仍调用`path_delete(p)`（`0x1401bef78`）。不能仅因字段名就认定返回后该路径句柄仍可供移动；**输出位置与路径资源生命期是不同契约**，完整_path_final下游未闭合。

构造竞争例：按实际扫描顺序，A满足门禁且路径7点，B路径4点，C路径4点，D返回−4。A先替换99999，B替换A，C因平分保留B，D不替换，返回[Bx,By,4]。这是最少路径点数选择，不等于最短几何距离、最小危险成本或最高攻击收益。

全失败例：T=(10,10)，全部有效射线对应路径返回−4或未通过门禁，则返回[10,10,99999]。上层仍读前两项；不能声称“99999会被所有上层统一识别成无路”。该处没有看到这种统一消费。

## 6．九格选择器：真正累计分与严格取大

新版查询后段设置bestScore=−1000（`0x140647658–0x140647662`），两个偏移循环分别从−1开始、每次加1，条件为≤1（`0x140647cd3 / 0x140647dc6`与`0x140647dfb / 0x140647ec2`）。因此此环尝试九个dx/dy组合，包括原地，不只八个相邻格。

候选G=(当前grid_x+dx,当前grid_y+dy)，写入局部（`0x140647f34→0x140647f43`与`0x140647fc0→0x140647fcf`）；每个候选score初始0（`0x140648014`）。回调、危险和实体分支对同一个score累计贡献。

已可逐项给出以下真实贡献；表中条件保留已恢复的局部前提，未绑定布尔不填业务名：

| 贡献 | 条件／位置 | 边界 |
| --- | --- | --- |
| −20 | is_shoot为真、state=`attack`、`scr_is_ground(G*26)`结果≤0，减法`0x14064837d` | 不自动等同于墙格，is_ground内部地形表未展开 |
| +3或+30 | G等于既有目标格、相关许可布尔通过，累加`0x1406486ff`；普通初值3，AOE选定路径改30 | 所有生产分支尚未绑定，不能一概称远程偏好30 |
| +20 | 指定邻接检查通过grid有效、负格门禁、多格许可后，`0x14064909f` | 危险格跳过此奖励，不等于删除整候选 |
| 再+20 | 上条成立且G等于self当前格，`0x140649132` | 明确存在保留原地的局部奖励 |
| +40或+1 | G的posgrid实例属于5473巨石，HP与1.5×self.DMG比较走低HP奖励40，否则1；`0x140649383 / 0x1406494a6` | 选定许可通过才进入，不是所有巨石统一可通行 |
| +40或+1 | 实例属于9479石刺的对应分支，`0x14064977f / 0x1406497b6` | 同样有资格与其他方向贡献 |
| −40 | 周围特殊实体查询返回一个匹配实例，with进入该实例时减40，`0x140649a46` | 此调用第四参undefined归一化false，返回单个实例而非全体集合 |

其他+1、+40、距离相关修正和+6均存在，但全部业务生产者尚未闭合。本篇不把表写成全条件覆盖的唯一总公式。数值helper确认乘、加、减；1.5由`0x140647cf8`装载，不是从名称猜测。

**确定的竞争规则**：在`0x140649ab0`比较score与bestScore，`jle`跳过更新（`0x140649ab7`）；仅严格大于时保存score和G（`0x140649ad1 / 0x140649aee / 0x140649b0b`）。同分先者保持，不在此处随机抽同分格。比较使用GameMaker运行时数值语义和1e−5容差；不能将任意类型简化为普通C# float。

构造九格例：明确给定其他贡献均为0，A取得+20且附近查询返回一个匹配实例，则scoreA=−20；B取得+20且无匹配实例，则scoreB=20；C同样20且后遍历，则保留B。若原地同时取得两项+20，它可达到40，并超过B。该例只验证已明示贡献，不保证某张真实战场下一步就选原地。

## 7．周边扣分筛选已绑定：巨石、水晶和幻象

G的直接占格来自self.posgrid，fallback为−4（`0x14064813f`）。结果用于巨石、石刺等具体实例类别判断。周边查询另调用`posgrid_around_search(Gx,Gy,global.__pf_nearest_array,undefined)`（`0x140649a02`）。全局筛选数组的读取在`0x14063da5d`。

本轮新增`gml_GlobalScript_mcr_base@0x140bbbb20`恢复数组初始化：以静态数值RValue常量5473、2699、9346建立三元素数组（实参`0x140bbbbfe / 0x140bbbc15 / 0x140bbbc2c`，建数组`0x140bbbc58`），随后写`global.__pf_nearest_array`（`0x140bbbc72`）。对应对象是`o_runic_boulder`、`o_mana_crystal`、`o_astral_phantasm`。**这是一组特殊实体类别，不是所有同阵营单位。** 原41的“未知周边占位”在这一具体罚分分支已可以缩小到真实对象集合。

新解周边助手`0x141cc64c0`对第三实参分支选择`instance_is`或`instance_is_array`（`0x141cc6b95 / 0x141cc6c7a`），读取posgrid（`0x141cc701a`），检查每个占格实例是否符合该对象／对象数组筛选。没有在这段助手中见faction_key或subfaction_key读取。因此这层资格是实例类别筛选；不能把−40称作固定同阵营排斥。实例类别助手可能含继承判断，不能仅按显示名字排除衍生对象。

**返回类型也已补闭合**：第四实参undefined比较后被改为type13、数值0（`0x141cc691e→0x141cc6931→0x141cc6960`），即false；只有真模式才创建数组（`0x141cc6af9 / 0x141cc6b77`）。本次false模式的匹配保存实例id（`0x141cc74b4`），将继续标志改false（`0x141cc74cd / 0x141cc74e3`），退出剩余扫描；末尾复制单个结果（`0x141cc760d`）。没有匹配保留−4初值（`0x141cc6a57`）。

所以上层with虽然写成可迭代结构，**本调用普通结果只有一个匹配实例，局部扣分为存在则−40，而非附近实体数量乘−40**。同一个助手的数组模式不能移植为这里的实际实参语义。

具体例：沿该默认数组，某候选周边存在一座巨石和一个魔能水晶，单结果模式找到首个合格实例即停止，本次局部扣40，不能算扣80。只有一个普通盟友F且F不属于这些对象／继承资格时，F不产生本项−40。若F直接占G，还要另过cell/grid、多格、路径类型与其他实体分支；没有确定“一律穿过友军”或“一律不穿过友军”。这里分别回答了特殊实体邻近、普通盟友和直接占格，不能把三者混同。

## 8．返回像素坐标前还有覆盖

九格胜者格坐标转换为像素中心：X=26*bestGX+13、Y=26*bestGY+13，保存`0x14064a2dc / 0x14064a39e`。但其后还查标记、相邻埋伏关系和距离等，可能再次改写这两个局部。

末尾`0x14064c4e3–0x14064c513`检查对象ID2606及三个布尔。OBJT将2606绑定为`o_npc_guard_brynn_arbalester`，不是普通盗匪弩手172。选定末尾段的分支可以具体写为：

```text
如果self.object_index == 2606，或末尾布尔P、Q、R之一为真:
    返回[self.x, self.y]
否则:
    返回此前工作位置的两个像素坐标
```

P位于本次函数局部`rbp+0x770`，由选定路径的next_tile_mark_get结果及undead相关条件形成；Q位于`rbp+0x498`，在后续标记／位置处理中可被改写；R位于`rbp+0x4a8`，在射击、初始视线、目标实例和距离比较成立时可被置真（`0x14064c403–0x14064c436`）。R路径比较当前／工作位置到目标的距离，不能把它叫任意敌人通用的“更近即原地”规则。P/Q全部上游资格仍未闭合，保留工作布尔名称。

原地返回分支转`0x14064c519`，重新取self.x/self.y建立数组（`0x14064c627`）；候选返回分支转`0x14064d8f8`，以此前候选位置建数组（`0x14064d992`）。两路都复制到输出引用，再统一清理返回。

因此**九格最高分不保证成为最终坐标**。该后段对特定守卫弩手有明确原地覆盖；不能因此给所有弩手同一规则。未完全绑定其他末尾布尔生产者时，不编成“射击敌人永远不动”。

具体返回例：九格胜者(12,8)先得到(325,221)。若后续没有改写且末尾选择候选路径，则新版查询返回[325,221]，Other12保存到pathTargetTile。若末尾实际选择self位置，self=(299,221)，则最终返回[299,221]。这两组坐标是构造值；覆盖分支与乘26加13是指令确认。

## 9．可独立借鉴的设计与剩余范围

适合借鉴：将射击位置资格、到达代价、当前九格行动效用和最终动作提交分开；提供明确原地候选；记录候选拒绝原因；把路径失败与坐标输出分别建模。我们自己的实现宜采用显式`Found/NoPath/NoEligiblePosition`结果，而不是靠99999和坐标组合推断失败。这个建议是自研设计，不是原作已采用的协议。

本轮已回答：普通self.id搜索门禁、视线失败触发搜索、三个因子初始化、真实远程候选几何生成、22次预算、两层距离门禁、path点数严格最小、同分先者、−4继续搜索、99999初值、九格累计分严格最大、若干具体常数、当前格奖励、周边筛选数组及单结果模式、特定守卫原地覆盖和pathTargetTile保存。

部分回答：完整选位。仍缺所有布尔生产者、每个特殊状态的贡献组合、初始化之后是否有其他动态配置改写、全部末尾覆盖资格，以及A*DLL内部代价与失败协议。**不能由局部完成表格宣称“远程AI完整算法全部恢复”。** 所有无路回退也没有闭合：本篇明确恢复range助手的失败继续与初值，未宣称其他移动、追击、逃离状态用相同回退。

本机可选来源：[本轮助手入口与覆盖](../../../_reference/stoneshard-study/twelfth-position-native.json)、[搜索因子初始化](../../../_reference/stoneshard-study/twelfth-position-disassembly/scr_enemy_range_tile_search_init.txt)、[dataLoader实际调用](../../../_reference/stoneshard-study/twelfth-position-disassembly/search-init-caller-context.txt)、[特殊实体数组初始化](../../../_reference/stoneshard-study/twelfth-position-disassembly/gml_GlobalScript_mcr_base.txt)、[数组数值常量](../../../_reference/stoneshard-study/twelfth-position-constant-values.json)、[射线结果](../../../_reference/stoneshard-study/twelfth-position-disassembly/scr_raycast_collision_hit.txt)、[路径成功／失败](../../../_reference/stoneshard-study/twelfth-position-disassembly/scr_path_to_point.txt)、[周边筛选](../../../_reference/stoneshard-study/twelfth-position-disassembly/scr_posgrid_around_search.txt)、[整数≤助手](../../../_reference/stoneshard-study/twelfth-position-disassembly/runtime-compare-int.txt)、[远程搜索门禁](../../../_reference/stoneshard-study/eleventh-position-disassembly/annotated-scr_enemy_range_tile_can_search.txt)、[远程候选完整选定首段](../../../_reference/stoneshard-study/eleventh-position-disassembly/gml_Script_scr_enemy_range_tile_find.txt)、[新版查询候选与返回](../../../_reference/stoneshard-study/eleventh-position-disassembly/annotated-scr_enemy_find_target_tile_new.txt)、[真实消费](../../../_reference/stoneshard-study/ninth-ai-disassembly/gml_Object_o_enemy_Other_12.txt)。正式正文自包含必要规则；这些解码文件为本机可再生成证据。

未做：没有运行游戏、动态寻路／射线场景、所有队形与全状态组合测试；研究文档不运行REA构建。风险：将最少路径点数等同于最低实际路径代价、将有限扫描等同完整圆周、将九格最高分当最终返回、将对象筛选当阵营筛选，以及把未知因子补成默认值。本章保留这些边界。
