# 50．投射物墙体门禁：发射前射线、偏移落点与实际碰撞

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [Fire Barrage 飞行](42-projectile-collision-and-target-changes.md) · [反射归属](39-reflection-redirection-and-source-ownership.md) · [链预算](49-chain-lightning-hop-budget-and-marker-lifetime.md)

42 留下“途中墙体如何处理”的问题。本轮补到了真正的发射前入口：**偏移候选格会先经过目标格判断，再调用像素坐标转网格的 barrier 射线；这条路径使用 controller.wallgrid 与位掩码3，检测到匹配格就拒绝该候选。另一个投射目标入口先扫描射线上的实例，并按 size 分支选择可能的截获对象。** 最终 shell 的碰撞仍要求碰撞对象等于当前 target，两阶段不能合成“任何碰撞墙都停”。

已经确定局部墙格读值规则和候选拒绝，没有恢复每一种墙/门资源到 wallgrid 位值的全部生产规则，也没有运行 GameMaker 的碰撞引擎。本文把这些边界放在算法旁，不靠墙对象名称补空白。

## 1．身份、范围与入口

同一 `E:/Steam/steamapps/common/Stoneshard` GameMaker YYC x64 制品；首选基址 `0x140000000`。EXE SHA-256 为 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win 为 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`，本轮完整复核一致。

沿用 REA 不可用记录，无安装/setup/虚构 Evidence。使用函数登记、PE 原始字节、OBJT 与 Capstone 5.0.9，解码指定入口第一登记段；短无 pdata 入口若出现则明确以邻登记边界限制，不将其当完整复杂函数。BSS 初值未知，类型5 undefined、类型13布尔和−4对象哨兵分开保留。

| 入口 | VA | 已解释的责任 |
|---|---|---|
| scr_shoot_target_miss | `0x1412e1680` | miss 准备、偏移格验证、最终回到实例目标 |
| __shoot_target_miss_cell_validate | `0x1412e5e00` | 候选格拒绝目标本人和有 barrier 的路径 |
| scr_projectile_have_barriers | `0x1412db040` | 特定 self 例外、像素转格、LOS射线 |
| scr_raycast_mod | `0x140758d20` | 选择网格、按射线路径调 callback、提前成功退出 |
| raycast_callback_LOS | `0x140763a70` | 读格、整数位与、转布尔 |
| scr_projectile_scan_tiles | `0x1412d60d0` | 射线格坐标→格实例→截获候选 |
| scr_projectile_target | `0x1412cc700` | 消费有序实例、size 小/中/大分支 |
| scr_attack_tile_get_back_target | `0x1412d4000` | 格实例查询；必要时创建终点代理 |

本机记录：[新入口与覆盖](../../../_reference/stoneshard-study/twelfth-wall-native.json)、[对象身份](../../../_reference/stoneshard-study/twelfth-chain-wall-object-bindings.json)。42 提供真实 Fire_Barrage 配置和实例事件；这里不把 helper 名称当作已经核准概率或物理规则。

## 2．偏移格的真假返回是候选许可

Fire Barrage 出生 Other10 的真实调用 `scr_shoot_target_miss @ 0x143efc821` 已由42确认，含 point 与 owner.Spell_Hit_Chance；它发生在飞行对象创建之前。shared miss 主体有概率和偏移选择，还包含 live_call；本文解释静态默认主体，不宣称运行替换分支不存在。

miss 在 `0x1412e35d7/0x1412e38f6/0x1412e3df8` 调候选格验证。验证入口的三个实参按使用分别是原目标实例 T、候选像素 x、候选像素 y。静态默认段：

1. `scr_check_tile_target(x,y) @ 0x1412e61cd` 查询这个候选格实例，与 `T.id` 比较（`0x1412e61e4`）。相同则返回 type13/value0（`0x1412e6243..0x1412e6262`）。候选仍落在原目标上不能当作通过该 miss 落点验证。
2. 不同才取得 T.x/y，调用 `scr_projectile_have_barriers(T.x,T.y,candidateX,candidateY) @ 0x1412e6354`。
3. barrier 返回真，则验证返回布尔假（`0x1412e636c..0x1412e638b`）；无 barrier 返回布尔真（`0x1412e63bc..0x1412e63e1`）。

所以这次 barrier 的线段起点是**目标 T 的位置**，不是必然的射手位置。它是在检验 miss 候选相对于 T 的偏移可达性；不要把这个调用单独画成射手→目标的完整射击视线。射手到射线实例的处理另见第4节。

```text
验证偏移候选(T,cx,cy):
    若候选格查询结果 == T.id：拒绝
    若have_barriers(T.x,T.y,cx,cy)：拒绝
    否则允许
```

这里“允许”只允许这个局部候选；还需经过外层随机/候选选择、实际对象存在、出生创建和飞行碰撞，不能直接变成最终命中。

## 3．barrier 精确读取什么

### 3.1 特定 self 例外

helper 在 `0x1412db179` 读取当前执行上下文 self.object_index，与数值2606比较（`0x1412db1a5/0x1412db1cc`）。等值路径在 `0x1412db25b..0x1412db281` 直接返回布尔假。OBJT 绑定2606是 `o_npc_guard_brynn_arbalester`，不是一个通用“箭类型”，也不是所有弩手的祖先判断。

**非等值**路径才继续射线。这个例外依赖调用时 self，不依赖传入 T 的对象类型；不能看 T 是普通敌人就忽略施法上下文，也不能凭 exception 猜守卫完整攻击是否穿墙。

### 3.2 四个像素坐标转格

helper 对四个实参先作运行时整数转换，再用乘法常量 `0x4ec4ec4ec4ec4ec5`、高位有符号移位及符号补偿实现除26：`0x1412db2b2..0x1412db2f7`、`0x1412db316..0x1412db357` 等。

在正常有限、可转换整数的输入下可重新组织为：

```text
gx = truncTowardZero(integerConvert(pixelX) / 26)
gy = truncTowardZero(integerConvert(pixelY) / 26)
```

负坐标不等于数学 floor；这个 helper 的坐标转换不能直接借用另一个 scan 中显式 math_floor 的名字。0、undefined、对象哨兵也不能混成坐标默认值。

它随后调用：

```text
scr_raycast_mod(gx0,gy0,gx1,gy1,raycast_callback_LOS,3,undefined,undefined)
```

callback ID 来源 `0x1412db418`，mask3 `0x1412db450`，八参数调用 `0x1412db4ae`；返回值直接拷回（`0x1412db4b9`）。

### 3.3 格位掩码与提前返回

raycast_mod 对未指定网格参数采用 controller.wallgrid：字段 `0x1407593bc`，对象常量4028/o_controller（`0x1407593d3`），读取 `0x1407593de`，保存网格 `0x1407593f1`。它不是从当前墙碰撞对象临时取得 mask。

LOS callback 把实参x/y转换为格整数，以第三实参为grid ID，读格（`0x140763c22`），将返回值转整数，再与第四实参mask按位与（`0x140763c2f`）。结果严格正值才返回布尔真（`0x140763c42..0x140763c57`），否则布尔假（`0x140763c74..0x140763c91`）。对这里的mask3：

```text
blocks = (integerConvert(grid[gx,gy]) & 3) > 0
```

mask3只检查最低两位；不是 `cell!=0`。若值4，则4&3=0，不因这个 callback 判阻挡。位1和位2分别由哪些墙、门、建筑、临时效果写入，尚未完全追到生产者；不能给这两位擅自命名。

### 3.4 已找到一种真实阻挡位生产者

进一步按 wallgrid 字段 ID 在整个 `.text` 指定引用形式扩查，定位到 `wallgrid_add @ 0x140ada400`、`wallgrid_remove @ 0x14170c2c0` 和实际 `o_projectileBarrier.Alarm0 @ 0x144c17c00`。这次不再只有消费者，也有明确写入来源。

projectileBarrier 的 Create 写 Alarm[0]=2（`0x144c17970..0x144c1798e`）；这是事件调度输入，不标成两逻辑回合。Alarm0 先调用 `scr_normalizeTileObject @ 0x144c17dc9`，读取x/y、sprite_width/height，并取得wallgrid尺寸与clamp的边界。随后在格区间循环中用当前坐标、**mask=2** 与第四个坐标解释参数调用 wallgrid_add（mask `0x144c18817`，四参数调用 `0x144c1885f`）。外层精确像素包围范围/端格包含条件尚未完全恢复，不凭sprite大小编矩形宽高公式。

add helper 对有效格读旧整数值（`0x140adabe8..0x140adabf5`），将第三实参转整数，在 `0x140adac14` 执行按位 OR，并经格写入助手提交（`0x140adacd1`）：

```text
wallgrid[gx,gy] = integer(oldCell) | integer(addMask)
```

这里不是数值加2：旧值2再次OR2仍为2，旧值1 OR2得到3；其他已置位被保留。因此真实 projectileBarrier 相应覆盖格写入的第二个低位会被前述mask3 callback识别。尚未绑定每个地图实例的资源摆放与所有删除路径，不能进一步保证任何命名“墙”的对象都创建这个代理，或代理一销毁就立刻清掉位2。

本机记录包括 [wallgrid 引用候选](../../../_reference/stoneshard-study/twelfth-wall-grid-field-xrefs.json) 与新增入口文件。按位消费者与一个实际生产者的连接已闭合；全部墙种类仍不属于已恢复范围。

raycast_mod 逐步取得路径位置并调所传callback（`0x14075a1f7`），返回真则进入成功提前返回（`0x14075a206→0x14075a92f`，写布尔真 `0x14075a962`）；到达终点等退出走假（`0x14075a985..0x14075a9b2`）。它包含方向、dcos/dsin、整数位置和终点比较；未恢复所有步进/拐角覆盖证明，不给它擅自命名为 Bresenham 或“遍历所有相交格”。

## 4．射线实例选择不是只有墙布尔值

miss 主体另在 `0x1412e30f5` 调 `scr_projectile_target`。它接收一条候选路径的扫描结果，并以 ordered array 消费；这与偏移格是否合法的 bool 不同。

`scr_projectile_scan_tiles` 使用起止坐标，调用 `scr_raycast_mod_array @ 0x1412d6a32`。array wrapper 选择 callback_sep（`0x14096c684`），创建收集数组，并调用 raycast_mod（`0x14096c920`）。callback_sep把当前前两个参数组成坐标对，再追加到 `__raycast_array`（创建 `0x14096d016`，append `0x14096d051`）。因此这一层先得到格坐标路径，再通过格实例查询（`0x1412d75ce`）转换成候选实例。

在扫描中已核的一类环境候选路径：

- 检测 `instance_is(candidate,3804/o_unit) @ 0x1412d7ab2`，这条环境处理分支将单位候选改为−4哨兵（`0x1412d7aee`）。这不证明整个扫描永不返回单位；前面有其他候选生产分支。
- 当前环境候选须为正值，并通过 `scr_can_be_broken @ 0x1412d7bbd`。
- 候选不等于相应排除实参；还通过 `scr_stuff_visible(self.x,self.y,candidate) @ 0x1412d7cfc`。
- 才 append 到结果数组（`0x1412d7d5c..0x1412d7d8d`）。因此这条环境候选不是“所有墙对象”。

### size 分支决定是否截获

消费者从索引0开始，依序检查数组元素；索引以1增加（`0x1412cd050..0x1412cd05c`），遇到相应原目标/实参条件可停止或跳过。候选必须具有 `size` 字段，字段不存在则跳到下一索引（检查 `0x1412cd42b`，假分支 `0x1412cd43a→0x1412cd070`）。

| size | 已读消费 | 精确输入/分支 |
|---|---|---|
| small | chance helper 请求15；返回真选该候选 | 字符串比较 `0x1412cd53c`；helper `0x1412cd634`；真分支到 `0x1412cdef1` 并复制候选至输出 |
| medium | chance helper 请求50；返回真选该候选 | 字符串比较 `0x1412cd74c`；helper `0x1412cd838`；对应候选输出分支 |
| large | 相应等值分支直接选择候选 | 字符串比较 `0x1412cd94c`；等值跳 `0x1412cdc20` |
| 其他已列 size 分支 | 存在另一字符串比较 | 未把该分支未绑定字符串补成默认large |

15、50是实际概率助手请求，不在这里宣称最终分别精确15%/50%；随机助手的下限、截断和其他修正须单独核对。这支持“顺序检查、尺寸资格/机会截获”的局部机制，不支持“找最近墙且一律100%阻挡”。扫描坐标重复、实例重复和完整去重尚未全部闭合。

## 5．落点变回实例，飞行阶段仍按 target 匹配

miss 的最终准备坐标在 `0x1412e3f71` 送给 `scr_attack_tile_get_back_target`。该 helper：

1. 无两个显式坐标时可读取 mouse_x/y；有两个则用调用者坐标（`0x1412d4353..0x1412d439d`）。因此本次两个坐标调用不应擅自换成实时鼠标。
2. 默认创建对象常量5287/o_attacked_target（`0x1412d43d2`）；第三实参可改变该对象并设置相应标记。
3. 查询格实例（`0x1412d4556`）。正常有效实例且未要求强制代理的路径保留查询结果（`0x1412d45a9..0x1412d45c0`）；否则经坐标整格处理后调用instance_create_depth（`0x1412d4dd1`），获取新实例id（`0x1412d4e4a/0x1412d4e55`），作为目标返回。

这解释了为什么出生处理可能得到实际障碍/环境实例，也可能得到一个坐标代理。整格助手是内联共享语义，未完整核对所有半格/异常类型结果；不把它随意写成floor到左上角。

Fire出生随后在相应返回坐标路径创建5287代理并更新point/first_target，见42的 `0x143efc991..0x143efca02`。父spellbirth再把最终point设为飞行实例target。前置选择对象、最终代理和当前追踪对象可能经历几次转换，不能把所有中间值都叫“原敌人”。

42已核的飞行碰撞继续有效：单位碰撞须other.id==target、未执行、距当前终点小于13像素；stuff碰撞也须other.id==target；代理和门走另一事件。匹配后派Fire事件，标记is_execute并销毁载体；Fire.Destroy仍可能按剩余预算创建后继。**有墙格检测不等于碰撞任意墙；碰撞无匹配也不等于保证能穿墙。** 完整行为需要连接该具体墙的网格位生产、出生最终target和实际引擎碰撞。

## 6．具体例子：墙格拒绝偏移，与小障碍截获

### 例A：一条经过阻挡位的 miss 偏移

构造 self 不是2606，T位置(65,65)，候选点(143,65)，候选格实例不是T。正常整数转换得到射线格起点(2,2)、终点(5,2)。假定实际射线callback在途中访问(3,2)，该wallgrid格值为2。

```text
2 & 3 = 2 > 0
callback返回true → raycast提前返回true
have_barriers=true → 偏移格验证=false
```

这个候选被外层 miss 处理拒绝，不会仅因其接近目标就当合格落点。若该格值改为4，4&3=0，**这个格**不触发该mask门禁；路径上其他格仍可阻挡。若候选查询结果就是T，第一步直接拒绝，根本不需要此射线判断。

例子明确假定访问该格，不声称未恢复的对角步进一定访问所有碰线角格；也不把wallgrid值2指定为某一种实际墙资源。

若这个例子中的(3,2)确实是 projectileBarrier.Alarm0 遍历的覆盖格，旧格值为0，则实际生产请求mask2经OR写为2，再被mask3读出2。旧值为1时写成3，同样阻挡；同一请求重复写仍为3，不累加成5而丢失bit2。这给出一条有实际对象生产者的条件例子，不需要假造墙资源名称。

### 例B：同一路径上的 small 与 large 实例

构造扫描结果按实际顺序为[S,L,T]，S.size=small，L.size=large，三实例有效、前置实参门禁允许。size检查确认字段存在：

- 若S的请求15对应chance helper返回真，输出S，后面的L不再参与此次截获选择。
- 若返回假继续；L满足large等值分支，输出L。
- 是否最终生成真实S/L为target，还是Fire出生把坐标转换成代理，需要按该调用返回值与出生分支继续追；不能由候选输出单独保证实际对S扣血。

这是明确指定随机helper输出的条件例子，不是15次实战统计或最终概率测量。它展示顺序与尺寸阶段如何影响目标选择，区别于物理碰撞阶段的target匹配。

## 7．确定程度、自研借鉴与剩余核对

已回答：真实 miss 候选门禁、T→偏移格的坐标来源、26像素格转换、特定上下文例外、wallgrid/mask3读取、projectileBarrier写mask2的实际生产者与OR合并、callback成功提前退出、射线坐标到实例候选、size局部截获与终点代理入口，以及最终shell碰撞的阶段差别。

部分回答：墙体阻挡通过发射前网格门禁和目标选择参与；并非只靠shell碰撞。仍未回答：所有墙/门/临时效果写入最低两位的规则；全部射线步进、边界、起终格和角点覆盖；完整随机概率；全部候选去重/对象组；动态门开闭后与高速移动时的引擎碰撞结果。这些未决不改写成通用“可穿墙/不可穿墙”的保证。

进一步最小核对是选一种实际墙，追其创建/开闭/销毁到wallgrid位写入；再用一条具体射击核对最终target、飞行期间地图变化和碰撞事件。自研可以明确采用“发射时选首个阻挡者”“每步碰撞重算”或二者结合，并把网格bit含义、角格规则和目标丢失策略写成自己的契约。这里交付行为研究，不提供复制原专有实现。

未运行、附加、修改游戏或存档，没有新读存档、网络监测、setup或提交推送；纯静态文档未执行游戏实战测试。风险是把candidate许可当命中保证，把所有非零格都当墙，把T→miss偏移线误画成射手LOS，以及把一个size机会输入当全局准确概率。

本机 [两篇局部验证](../../../_reference/stoneshard-study/twelfth-chain-wall-validation.json) 已核对文本、链接与地址关联；[位运算/坐标条件演算](../../../_reference/stoneshard-study/twelfth-chain-wall-derived-examples.json) 保留输入与结果。它们不替代墙实例生产范围、射线角点与实际碰撞运行验证。
