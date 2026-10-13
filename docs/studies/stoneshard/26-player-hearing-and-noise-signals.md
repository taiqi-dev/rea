# 玩家听觉提示、声音来源与迷雾的边界

[返回拆解目录](README.md) · [敌人感知与声音传播](03-enemy-perception.md) · [玩家视野与迷雾](23-player-vision-and-fog.md) · [主动探查](24-investigation-and-reveal.md)

此前的 03 主要解释敌人接收声音、传播代价和消费听觉信号。本篇补玩家声音提示：什么入口请求提示、感知怎样参与范围和寿命、同一来源怎样刷新，以及提示与真正揭开迷雾的区别。证据来自同一安装制品的原生指令与对象资源，未执行游戏。下面的伪代码是我们组织的局部行为规格。

## 1. 三种状态需要分别追踪

| 状态 | 本轮确认的局部规则 | 不能直接推出 |
| --- | --- | --- |
| 敌人收到噪声 | 03 的传播、方向修正、信号置位和一次消费 | 玩家也使用完全相同的声音判定 |
| 玩家有声音提示 | 独立 `o_hearing_indicator` 实体，绑定来源，维护 `turns` 并淡出 | 敌人实体已可见、陷阱已发现，或地图已探索 |
| 地图可见/已探索 | 23 的 `fogmap` 与 `fogTiles`，以及各自更新和保存 | 所有声音提示都会写这两个网格 |

“视觉探查”“听见提示”“历史探索”可以使用相同坐标，但当前已见的生产者和消费者不同。不要在自己的实现中只用一个 `revealed` 布尔值替代这些语义。

## 2. 真实入口与调用证据

| 入口 | VA | 已核对的职责 |
| --- | --- | --- |
| `scr_hearing_source_in_radius` | `0x1411b5c30` | 玩家/来源存在检查、PRC 范围和距离比较 |
| `scr_hearing_noise_update` | `0x1411af260` | 一条带特殊状态存在门禁的噪声判定路径 |
| `scr_hearing_indicator_create` | `0x1411b29e0` | 按 owner 查找或创建提示，重设寿命 |
| `scr_hearing_get_fogtiles` | `0x1411b0370` | 从当前 fogmap 收集假值格坐标 |
| `scr_hearing_indicator_fake` | `0x140b19b20` | 另一个提示入口；本轮只确认调用，完整生成算法待查 |
| `o_hearing_indicator.Create` | `0x144137cd0` | 初始化 owner、turns、isDuration、diss |
| `o_hearing_indicator.Step_0` | `0x144137fb0` | 来源检查、表现位置跟随与淡出分支 |
| `o_hearing_indicator.Other_10` | `0x144138c70` | 当 isDuration 为真时，turns 减 1 |

调用并非只靠名称猜测：从登记入口开始解码，确认 `o_ancientTroll.Other_10` 在 `0x1437c59b0` 把字符串 `troll` 和自身 id 传给 `scr_hearing_noise_update`。噪声功率如何把 `troll` 映射为数值，本篇未恢复，因此不虚构巨魔声音的固定范围或成功率。

另一个已确认调用者是 `scr_enemy_fog_visible_update`（`0x141e41400`），它在 `0x141e41d5a` 和 `0x141e41f2f` 调提示创建。前一路读取状态并通过 `scr_isStateIndicatorVisible`；后一路读取实体 visible、检查状态和听觉范围，并要求 `o_state_megalomania` 实例不存在。两条调用都使用当前执行实体作为默认来源。状态比较的完整业务含义尚未命名，不能把任何一路称为无条件普通听觉规则。

这也解释了为什么不能把下一节的概率公式扩展到全部玩家提示：其他入口可以直接请求同一个提示创建器。

## 3. 感知范围怎样计算

`scr_hearing_source_in_radius` 的局部规则是：

```text
source = 显式来源参数，否则当前执行实体的 id
如果玩家或 source 不存在：返回失败
R = gameRound(10 + 0.2 × player.PRC)
D = scr_tile_distance(source, o_player, undefined)
返回有序比较 D <= R 的结果
```

PRC 读取、乘 0.2、加 10 和取整分别可在 `0x1411b5f2c`、`0x1411b5f66`、`0x1411b5f91`、`0x1411b5ff6` 复核；距离调用在 `0x1411b6098`，比较在 `0x1411b60c9`。比较助手使用 `1e-5` 容差；这里描述普通有限数值的有序比较。

本次调用的距离模式参数是 undefined。03 恢复了一种距离模式，但尚未证明此处默认模式等于那种模式。因此 R 可以确定，具体斜向格、边界格距离不能直接套用欧氏、曼哈顿或切比雪夫距离。

**构造例子：**PRC=20，则 R=14。假设该距离调用返回 12，来源在范围内；返回 15 则不通过。这里的 12 和 15 是假定的返回值，不是实际放置游戏实体后测得的距离。

## 4. 一条噪声路径的门禁与概率输入

`scr_hearing_noise_update` 先要求 `o_state_megalomania`（对象 6160）实例存在，还要求玩家与来源存在。这个状态对象缺失时，本入口走失败返回；对象存在也不能单独证明它的所有游戏效果已经生效。

通过存在门禁后，它检查来源 visible：来源已经可见就退出；范围判定不通过也退出。随后计算：

```text
c = 0.1
如果 o_pass_skill_trailblazer 存在且 is_open 为真：c = 0.2
P = scr_alarm_get_noise_power(传入的动作/声音类别)
C = P × player.PRC × c
如果 scr_chance_value(C, undefined, undefined) 成功：
    scr_hearing_indicator_create(source)
```

状态存在门禁在 `0x1411af4da`；visible 检查在 `0x1411af593`；范围调用在 `0x1411af625`；功率查询在 `0x1411af782`；概率调用在 `0x1411af94c`；成功创建在 `0x1411af9bf`。系数 0.1/0.2 来自指令里的实际标量。

C 是概率助手输入，不能写成严格的 C%。[19](19-kick-pull-and-knockback.md) 已解释该助手的近 100 直接成功分支、运行时下限槽、包含端点的 0..100 整数抽样及比较容差。下限槽的运行时值仍未知。

**构造例子：**假定这条路径全部门禁通过，功率查询返回 P=6，玩家 PRC=20。默认 C=12，开通该被动时 C=24。可以确定传入助手的数值翻倍，不能据此宣称实测成功率恰好从 12% 变成 24%。P=6 是演算输入，没有证明 `troll` 或任何特定动作返回 6。

## 5. 提示按来源复用，寿命另作随机

提示创建器先验证玩家和来源，然后计算：

```text
Lmin = gameRound(2 + 0.25 × player.PRC)
Lmax = gameRound(5 + 0.5 × player.PRC)
找第一个 owner == source 的 o_hearing_indicator
未找到：创建一个提示实体，设置 owner = source
找到或刚创建的提示：turns = irandom_range(Lmin, Lmax)
```

寿命公式的取整在 `0x1411b2f26` 与 `0x1411b3040`；owner 比较在 `0x1411b312e`；创建对象 5647 的调用在 `0x1411b3303`；随机调用与 turns 写入在 `0x1411b37bb`、`0x1411b37da`。整数范围助手的 span 含 `+1`，支持包含两个端点的解释。

同一来源再次请求时，会刷新已找到提示的 turns，而非此处必然再生成一个提示。这个规则只保证本函数按 owner 查找并复用第一个匹配，不证明所有其他创建路径都防止重复，也不证明多个重复提示会被全部刷新。

创建器还存在非玩家来源、Trailblazer 已开通以及对应效果尚未存在的分支，可创建 `o_db_trailblazer`（对象 303）。本篇只确认该分支与对象身份，效果如何进一步修改属性另属 Buff 调查。

**构造例子：**PRC=20 时 Lmin=7、Lmax=15；假设第一次抽到 9，则写 turns=9。同一来源第二次抽到 12，则已有提示写 turns=12。它不是 9+12，也不是必定并排出现两个提示。

## 6. 位置跟随、减计数与淡出

Create 写入 owner=-4、turns=0、isDuration=true、diss=0。Step 对 owner 作存在检查；来源不存在、来源 visible 为真或 turns 非正时，进入淡出/销毁分支。

有效分支调用来源的 `scr_spriteTransformUpdate`，随后把 owner.stX、owner.stY、owner.stScaleY 分别写给提示的 x、y、image_yscale（关键写入在 `0x144138349`、`0x1441383b1`、`0x144138419`）。因此这条路径的提示随来源的表现变换更新，不能描述为固定留在第一次听见时的坐标。

Other_10 在 isDuration 为真时执行 turns-=1（`0x144138d0b`），但本轮没有恢复这个事件的完整派发频率。随机得到的 7..15 是计数字段初值，不能直接保证玩家画面上精确显示 7..15 个行动回合。淡出分支包含插值和销毁检查，不是上述条件成立后立即消失；具体淡出阈值、Draw 图像和相位顺序仍待查。

## 7. fogtiles 辅助入口读取什么

`scr_hearing_get_fogtiles` 遍历 `o_fogrender`，把输入中心及半径形成的矩形与房间边界裁剪，再读取其中的 fogmap 格。格值为真就跳过，假值则加入坐标对集合；当前局部没有观察到写 fogmap。

网格读取在 `0x1411b0fa3`，真值跳过在 `0x1411b0fb2`，坐标对写入在 `0x1411b1011` 与 `0x1411b106d`。结果初始为 false；接收首个格时转换成数组容器，不能擅自将“没有接收格”改述为必返空数组。

**构造例子：**假设裁剪后的候选矩形只有 A、B、C 三格，fogmap 依次为 true、false、false，则 A 被跳过，结果收集 B、C 的坐标。调用读取了两个不可见候选，不表示把它们改成可见或已探索。

本轮未闭合这个辅助入口到真实/虚假提示生产者的调用链。已确认 `o_db_whispers.Other_10` 在 `0x142f0cafd` 调 `scr_hearing_indicator_fake`，且此前检查 `o_state_paranoia`（6165）不存在；完整假提示位置、数量与筛选算法仍未知。因此不能断言画面上的每个声音提示必有真实敌人，也不能断言该辅助收集器必被每种提示使用。

## 8. 自研时可采用的拆分与后续验证

可独立设计四层：声音事件及传播、观察者接收判定、声音提示的来源/寿命/表现、当前可见与历史探索网格。按产品需求决定声音显示精确位置、模糊区域还是最后已知位置；本轮来源变换跟随只是目标制品这条路径的事实，不必成为我们的产品规则。

值得继续查的是：普通提示各入口的状态条件、默认距离模式、动作到 P 的功率表、Other_10 的回合派发、假提示生成和实际绘制。运行验证可选“同一不可见来源制造两次声音、随后进入视野”这一小场景，记录提示刷新、来源移动、淡出以及两个迷雾网格是否变化。本轮未运行该实验，也未监测网络。

## 本机复核记录

- [入口与局部指令](../../../_reference/stoneshard-study/seventh-hearing-native.json)、[指令目录](../../../_reference/stoneshard-study/seventh-hearing-disassembly)
- [常量、对象与短字段检查](../../../_reference/stoneshard-study/seventh-hearing-constant-checks.json)
- [从登记入口解码确认的调用者](../../../_reference/stoneshard-study/seventh-hearing-verified-callers.json)；原始 E8 扫描只是候选，未经指令边界确认不能当调用证据
- [本轮目标摘要](../../../_reference/stoneshard-study/seventh-target-identity.json)

这些记录属于本机静态分析，未创建 REA Evidence 会话。风险是把特殊门禁路径推广到正常听觉、把计数字段当作实测显示回合，以及把提示误认为实体可见或地图揭示。
