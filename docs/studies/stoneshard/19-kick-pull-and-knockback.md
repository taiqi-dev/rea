# 19 猛踹、拉拽与公共击退

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [伤害与回合](14-combat-turns-and-damage.md) · [技能成本与提交](16-skill-commit-and-ai-gates.md)

本章研究本机 Stoneshard 的 `Power_Kick`、`Tongue_Pull` 与公共强制位移。已确认真实配置、攻击后控制门禁、距离请求、方向计算、逐格停止和一条碰撞伤害参数链。没有运行游戏；本文的数值例子都是构造演算，不代表实测战斗日志。

“钩取/拉拽”在这里是用户关注的行为类别。`Tongue_Pull` 是已确认使用反向位移的真实例子，不把它认定成玩家某个中文译名技能。Arcane Tether、Wide Cut 的独立配置研究见 [第 21 章：奥术束缚与钩取斩](21-arcane-tether-and-hooking-cut.md)；本章不凭 `hook` 字符串替代技能身份。

## 1 身份、方法与覆盖

目标为 `E:/Steam/steamapps/common/Stoneshard/StoneShard.exe`，GameMaker YYC x64；`data.win` 未含可供字节码解编的 CODE 块。本章依据原生指令、原始字符串表、OBJT 继承和已有运行时助手核对。

| 制品 | SHA-256 |
| --- | --- |
| StoneShard.exe | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| data.win | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

本机没有可用 REA MCP/深层分析提供者；使用已建立的 PE/原生符号映射和 Capstone 5.0.9 做限定静态读取。名称绑定使用 RIP 引用前 8 字节的名称指针。函数 `.pdata` 首段可能只是片段，邻接解码窗口不自动归属同一函数。本文没有虚构 REA Evidence ID。

文中的“指令确认”指本机指令与操作数形成的局部事实；“资源确认”指表、对象编号及继承；“推断”明确标记。完整指令输出位于未版本化的 `_reference/stoneshard-study/`，正式正文保留必要结论和地址，读者不依赖这些本机输出也能理解覆盖范围。

## 2 模块边界与数据

技能负责准备攻击参数、决定是否申请控制和请求多少步；公共入口负责目标资格和位移上下文；公共位移负责方向、格子验证、位置更新、碰撞后果及状态效果。伤害计算、状态生命周期和动作资源消耗是另外的模块。

| 对象或字段 | 本章确认的职责 |
| --- | --- |
| `owner`、`target` | 施加者、被位移对象；两者存在性是公共入口门禁 |
| `STR`、`Legs_DEF` | Power Kick 的伤害准备输入；STR 也进入控制阈值 |
| `Knockback_Resistance` | 在本章两技能中从控制阈值扣除 |
| `Knockback_Immunity` | 公共入口直接拒绝位移的独立门禁，不等同于抗性数值 |
| `distance` | 公共载体保存的请求步数；算法以整数转换后循环 |
| `is_reverse` | 改变方向；真保留指向施加者的向量，假取反 |
| `xx/yy` 与 `x/y` | 位移计算和位置更新中都参与；不能只修改绘制坐标替代完整更新 |
| `newgrid`、`grid`、占位 | 格合法性、碰撞清理和占位重建相关数据 |
| `o_knockback` | 公共入口创建的载体；其 Step 还处理透明度/缩放/销毁表现 |
| `o_db_knockbacked` | 经 `scr_effect_create` 接入的状态对象；不是同一个视觉载体 |

OBJT 直接确认：`o_tongue_pull` 编号 3522，父 5296 `o_shell_damage`；`o_tongue_pull_birth` 编号 8450，父 5338 `o_spellbirth`；`o_power_kick` 编号 5559，父 5531 `o_target_spell`；`o_knockback` 编号 5326，无父；`o_db_knockbacked` 编号 6189，父 5949 `o_invisible_buff`。`o_unit`=3804，`o_enemy`=3805，后者继承前者。这里的编号是该制品 OBJT 索引，不能跨版本直接复用。

## 3 猛踹：伤害准备与一格位移

### 3.1 真实配置

资源字符串 `0x145e4e260` 的行将 `Power_Kick` 绑定 `o_power_kick`，目标类型 `Target Object`，`Range=1`、`KD=6`、`MP=6`，`Class=skill`、`Branch=athletic`、`is_knockback=1`，Maneuver 列为 1。列名来自 `0x145e4bdc0` 的同表标题。

这些是基础配置；不是证明“每次最终扣 6”“一切情形冷却 6 回合”。实际成本与提交路径另见第 16 章，伤害抵抗另见第 14 章。

### 3.2 攻击参数准备

`o_power_kick.Other25` 读取 `owner.Legs_DEF` 和 `owner.STR`，执行两次乘法和两次加法，再写入技能上下文的 `Blunt_Damage`：

```text
preparedBlunt = 6 + 0.3 * owner.Legs_DEF + 0.4 * owner.STR
```

读取发生在 `0x14406af61/0x14406af86`，0.4 乘法在 `0x14406afb4`，0.3 乘法在 `0x14406afe2`，加 6 在 `0x14406b010`，合并在 `0x14406b068`，字段赋值在 `0x14406b568`。这属于输入伤害准备，不能直接当最终扣血。

公共 `scr_skill_attack` 在本轮也解码：其技能事件分派路径传 User 索引 15，例如 `0x1412dca38/0x1412dca3e`。本机事件助手 `0x1451ef5b0` 将索引加 10，故对应 Other25；调用前切换到调用上下文的 other.id。该证据连接了攻击入口与技能准备事件；不是要求每种武器分支同时执行所有分派点。

### 3.3 攻击成功后才申请控制

`o_power_kick.Alarm0` 的本章路径如下：

1. 检查 owner、target 实例存在（`0x144066ab5/0x144066aff`）；无效时跳过主体。
2. 在 owner 上以 `noWeapon` 调用 `scr_skill_attack`（`0x144066c1b`）。
3. 读取 `owner.attack_result`，依次排除 `miss`、`fumble`、`fumbleBlock`；任一匹配跳到 `0x144067c69`，绕过本章的击退判定。
4. 读取 owner.STR 与 target.Knockback_Resistance，计算下列阈值 C。
5. `scr_chance_value(C, undefined, undefined)` 返回真才调用公共击退；否则继续后面的技能分支。
6. `scr_cast_knockback(owner,target,undefined,undefined,undefined)` 使用公共默认参数：请求 1 步，reverse=false。

```text
Ckick = 60 + 2 * owner.STR - target.Knockback_Resistance
```

STR 与抗性读在 `0x144066ef4/0x144066f16`；乘 2、加 60、减抗性在 `0x144066f84/0x144066fb2/0x14406700a`；概率调用 `0x1440670e8`；位移调用 `0x144067242`。

Alarm0 随后还存在另一套 AGL、抗性、chance 和状态效果分支，本章没有将其恢复成完整眩晕/踉跄规格，也不把它与前面的击退成功视为同一结果。

### 3.4 贯通构造演算

设 `Legs_DEF=20`、`STR=15`、目标抗性 25，目标 HP>0、无免疫，攻击结果不属于三个排除值：准备钝击为 `6+6+6=18`；位移阈值为 `60+30−25=65`。

再**条件性假设**概率助手的未解槽值不大于 65，抽得整数 r=64，则控制判定通过。公共入口请求向远离 owner 的方向走 1 步。首格合法且无阻挡才完成这一格位置更新；首格阻挡会进入碰撞分支。18 是准备伤害，65 是阈值，1 是请求步数，三者都不是最终伤害/最终概率/保证走完距离。

## 4 舌拉：攻击后请求向施加者靠近

### 4.1 配置与出生对象

资源行 `0x145e50f90`：`Tongue_Pull → o_tongue_pull_birth`，`Range=5`、`KD=8`、`MP=18`，`Class=skill`、`Branch=none`。该行 `is_knockback=0`，但实际执行调用公共反向击退。因此不能把这一表标志当作全部强制位移技能的充分分类。

出生 Create 在 `0x144ea814c` 写 `cast_frame=1`，在 `0x144ea818e` 写 `spell=3522`，与 OBJT 的 `o_tongue_pull` 精确对应。它继承 `o_spellbirth`；公共出生/动画事件见第 13 章。舌拉主体 Create 在 `0x1434c8d99` 调 `scr_damage_init`，初始化 target 为 −4，并涉及 alarm、声音、速度和舌体 sprite。这些是原生字段和局部链，不等于已经证明全部弹体碰撞必然派发 Other10。

### 4.2 执行入口与距离

`o_tongue_pull.Other10` 先派发 User1（Other11），再在 owner 上以 `noWeapon` 调用 `scr_skill_attack`（`0x1434cc4bd`）。返回值存到局部变量。随后要求 target 仍存在，并且该返回值转为真（`0x1434cc541–0x1434cc55c`）。

满足这些前提才计算和申请拉拽：

```text
Ctongue = 99 - target.Knockback_Resistance
D = scr_tile_distance(owner, target, undefined)
requestedSteps = min(D - 1, 4)
cast_knockback(owner, target, requestedSteps, true, undefined)
```

减抗性 `0x1434cc624`、chance `0x1434cc6ae`、距离 `0x1434cc804`、减 1 `0x1434cc819`、min `0x1434cc8aa`、reverse=1 参数 `0x1434cc8cc`、公共入口 `0x1434cc91d` 均已核对。减一助手 `0x140005910` 是复制 RValue 后减传入整数；min 助手 `0x1451de510` 在普通有限数路径比较并保留较小值。

这条表达式没有显式 `max(0,...)`。D=1 请求 0；若 D=0 则请求 −1。后续公共循环只在整数请求>0时执行，不能反过来声称本技能在所有零/负距离下完全无副作用。`scr_tile_distance` 的完整距离度量本轮没有重解，D 是它的实际返回值，不擅自称欧氏/曼哈顿距离。

### 4.3 贯通构造演算

假定实际距离助手返回 D=5、目标抗性 20：阈值 C=79，请求步数 `min(4,4)=4`。若前置攻击返回真、chance 判定真、公共免疫门禁通过，方向向量保留“目标指向 owner”的方向。

以同一行上 owner 在格 (10,10)、被拉对象在格 (15,10) 的构造场景示例，公共一格长度 26，候选格依次 (14,10)、(13,10)、(12,10)、(11,10)。前三格都合法，第四格也合法时到达相邻格；若第二格有阻挡，则保留第一个合法候选，不越过障碍强制到终点。这里格位置示例只解释公共循环；不证明每个实际玩家/NPC对象都进入本章已核准的 `is_enemy` 分支。

## 5 共同概率助手：阈值不是百分比标签

`scr_chance_value` 入口 `0x1413e5360`，默认成功返回值 1、失败返回值 0。正常有限数输入下：

1. 先以容差 ε=`1e−5` 比较 C 与 100。比较结果非负时直接返回成功值，不抽随机数（`0x1413e573f–0x1413e5775`）。
2. 否则取 `T=max(C,S)`；S 来自未确认初始化的 `.bss` 槽 `0x149874248`（`0x1413e58c6–0x1413e58ee`）。
3. `irandom(100)` 返回整数 `r∈[0,100]`，两端包含（`0x1413e58fb`）。
4. 计算 `r−T`，用 ε 容差将其与 `−ε` 比较；有序负比较且非特殊返回 −2 才成功（`0x1413e5913–0x1413e5949`）。

运行时 `0x1402057b0` 在 `0x1402057e4–0x140205806` 同时要求比较返回值≠−2且为负。数值比较表索引 0 和 0xdd 都落到 `0x1451cdf1b`，普通有限数路径先检查差值绝对值≤ε，再返回符号。因随机差值又与 −ε 比较，不能把所有小数边界简化成无容差的 `<`。

对于整数 `0≤C<100`，**额外假设 S≤C** 时，成功整数输出就是 `r<C`。例如 C=65 对应 65 个成功输出（0…64）、101 个可能输出；C=99 对应 99 个成功输出（0…98）。这不是无条件精确成功率：S 未知、上游命中和免疫也有条件，随机实现采用取模且可能有微小偏差。C 达到 100 则进入直接成功边界，与“101个输出中挑100个”不同。

本章没有确认 S=0。既有一次精确 `lea rcx,[rip+disp]` 扫描未找到该槽构造，覆盖只限这种指令形式；不能拿文件未承载 `.bss` 的初始零填充代替后续初始化证据。

## 6 公共入口、方向与逐格停止

### 6.1 入口资格与载体

`scr_cast_knockback` 入口 `0x141248570`。默认参数确认：distance=1（`0x141248a8b–0x141248a9c`）、reverse=false（`0x141248af6–0x141248b2f`）、第五参数=−4（`0x141248be6–0x141248bf7`）。第五参数用于 `scr_knockback` 的来源选择，尚未完整恢复所有替代来源约定。

实参顺序明确为 `(source/owner, target, distance, reverse, optionalSourceSelector)`，索引从0到4。reverse=true改变的是 **target的移动方向**，没有把施法者改成被移动对象；反向请求仍要通过 target 的 HP、继承、免疫门禁。

owner 或 target 不存在，target.HP 与 0 比较不大于零，target.object_index 不是 `o_unit` 后代，或 `Knockback_Immunity` 为真，都会跳到共同返回处。本轮 HP 比较含 ε，不能为极小正数承诺通过。

合格后创建 `o_knockback` 载体，在载体上下文写 target、owner、passive=true、is_reverse、distance、image_angle，随后立即调用 `scr_knockback`（`0x141249485`）。位移解析已经发生于这次调用；`o_knockback.Step` 的透明度、缩放和销毁循环不能作为“每帧移动一格”的证据。

### 6.2 已核准的目标分支

下述主体是在 target 上、`is_enemy` 转为真才进入的分支（`0x141236d51–0x141236d67`）。这个字段与对象类并不自动等价。本章不据此宣称玩家不可被推，也未证明玩家状态字段和其他专用路径；玩家最终行为保留未知。

默认来源从 owner 的 x/y 与 target 的 x/y 取格坐标，逐轴形成向量：

```text
baseDir = 26 * (sign(ownerGridX-targetGridX), sign(ownerGridY-targetGridY))
dir = baseDir if is_reverse else -baseDir
```

owner 坐标转格与参数组装在 `0x141236027–0x14123613e`；target 转格在前段 `0x141235dc6` 起。符号差和乘26在 `0x1412362c0/0x1412362e7/0x14123630f` 及 y 对应操作；非 reverse 的两分量乘 −1在 `0x141236e0f/0x141236eeb`。不是归一化欧氏向量：斜向时每轴都可步进26。

### 6.3 逐步算法

以下是自行组织的行为伪代码，`tileProbe`/`patternProbe`保留尚未解开的参数契约，不是原代码恢复件：

```text
origin = target.xx, target.yy
lastValid = origin
attempt = 1
remaining = integer_truncate(carrier.distance)
blocked = false
hitOtherEnemy = false

while remaining > 0:
    candidate = origin + dir * attempt
    blocker = tileProbe(candidate, S_tile, S_tile)
    hitOtherEnemy = blocker存在且是o_enemy后代且blocker.id != target.id
    blocked = patternProbe(candidate, S_tile, S_tile)为真且blocker != target.id
    if not blocked:
        blocked = not gridNextValidate(lastValid/26, candidate/26, true)
    if blocked or hitOtherEnemy:
        break
    lastValid = candidate
    remaining -= 1
    attempt += 1

if 未受阻:
    清理原占位
    changeCoordinate(candidate)
else:
    if attempt != 1:
        清理原占位
        changeCoordinate(lastValid)
    执行所命中对象/地形对应的碰撞后果
```

`S_tile` 对应槽 `0x149871590`，本轮未确认初值，未将其命名成某个具体图层/布尔常量。

请求转整数及循环在 `0x1412370b4–0x1412370f6`；候选 x/y 是**原点加方向乘尝试序号**，不是不断累加候选（`0x1412371e8/0x141237234`、`0x141237358/0x1412373a4`）。首个序号=1（`0x141236f79/0x141236f83`）。

对象探测 `0x14123749f`；其他敌人后代和排除自身 `0x141237599–0x141237655`；pattern 检查 `0x14123772b`；下一格合法检查 `0x141237a1b`；受阻退出 `0x141237a79/0x141237a8d`；合法候选存入 lastValid 与 remaining--、attempt++ 在 `0x141237aab–0x141237b5f`。

`scr_grid_next_validate` 内部取候选与起点逐轴差再取 sign，读取控制器的 `newgrid.grid`，将起点、方向、网格、`scr_cell_astar_validate` 与第五参数交给下游。故这里调用了方向/网格验证，不能简单等同于“只查终点为空”；角落穿越和所有 tile 类型规则仍需下游完整契约。

### 6.4 正常更新、部分完成与受阻

未受阻分支清理碰撞占位（`0x141237e19`），向 `scr_change_coordinat` 传 candidate（`0x141237f5b`），之后经 effect_create 传 OBJT6189、duration参数1、target.id、owner（`0x14123818f`）。状态创建的持续补偿、递减阶段与清理规则见第 11 章；参数1不直接当最终可见回合数。

受阻分支先比较 attempt 与1（`0x1412386a2`）。若在第一格受阻，跳过 lastValid 位移；若之前已走过合法格，调用 collision_clear（`0x141238889`）并把 lastValid 传给 changeCoordinate（`0x1412388e7–0x1412389cb`）。随后还有效果、日志和碰撞分支。由此可以确认受阻不是统一回滚到原点，也不等于没有任何效果。

`scr_change_coordinat` 参与 is_moving/force_stop、xx/yy、x/y、grid_x/grid_y、占位清理与重建，并在条件分支调用单位位置事件；本章没有声称所有这些分支无条件发生。它比视觉坐标赋值有更大的状态职责。

## 7 碰撞伤害的具体局部例子

受阻后取得 blocker，调用 `scr_can_be_broken(blocker)`（`0x141238f5e`）。真分支在位移载体上下文读取载体 target 的 max_hp，计算：

```text
collisionPreparedBlunt = min(0.1 * displacedUnit.max_hp, 25)
```

max_hp读 `0x141239033–0x141239050`；乘0.1助手 `0x1400610a0` 调于 `0x14123905f`，本轮已核准其复制值后执行乘法；min调 `0x1412390be`；结果写当前载体 `Blunt_Damage` 在 `0x1412390d8`。随后在 blocker 上设置 last_attacker，调用 `scr_damage_with_calc(blocker,false,...)`（`0x1412392b9`）。这是可破坏对象碰撞路径的准备伤害，不是被推对象一定扣掉同量 HP。

构造例子：被推单位 max_hp=180，准备钝击=min(18,25)=18；max_hp=400 时为25。目标物体的抗性、护甲和下游计算仍可改变最终结果。公共函数还存在对单位、地形标记、其他阻挡的额外伤害/效果分支（例如 `0x14123ae1e`、`0x14123c841`、`0x14123d10a`），本轮没有把它们扩写成完整“撞墙伤害表”或“连锁击退”算法。

## 8 证据位置表

| 结论 | 核心 VA / 元数据 | 本机可选证据 |
| --- | --- | --- |
| 两条真实技能配置 | `0x145e4e260`、`0x145e50f90`；标题`0x145e4bdc0` | [字符串槽索引](../../../_reference/stoneshard-study/third-static-string-slots.json) |
| 猛踹准备伤害 | `0x14406afb4–0x14406b568` | [Other25](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Object_o_power_kick_Other_25.txt) |
| 攻击事件接准备事件 | `0x1412dca3e`等，User15 | [skill_attack](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Script_scr_skill_attack.txt) |
| 猛踹攻击/控制门禁 | `0x144066c1b`、`0x1440670e8`、`0x144067242` | [Alarm0](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Object_o_power_kick_Alarm_0.txt) |
| 舌拉出生对象ID | `0x144ea818e`；OBJT3522/8450 | [birth Create](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Object_o_tongue_pull_birth_Create_0.txt) |
| 舌拉攻击、阈值、距离 | `0x1434cc4bd–0x1434cc91d` | [Other10](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Object_o_tongue_pull_Other_10.txt) |
| 概率边界和未知槽 | `0x1413e573f`、`0x1413e58ee`、`0x1413e5926` | [chance](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Script_scr_chance_value.txt)、[比较](../../../_reference/stoneshard-study/fifth-displacement-disassembly/runtime-compare-context.txt) |
| 公共默认、门禁、载体 | `0x141248a8b–0x141249485` | [cast_knockback](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Script_scr_cast_knockback.txt) |
| 逐格停止、部分移动、碰撞 | `0x141236d51–0x14123d300`中的已标分支 | [knockback](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Script_scr_knockback.txt) |
| 网格方向验证 | `0x140a7c6a0` | [grid_next_validate](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Script_scr_grid_next_validate.txt) |
| 坐标/占位更新 | `0x1418bce40` | [change_coordinat](../../../_reference/stoneshard-study/fifth-displacement-disassembly/gml_Script_scr_change_coordinat.txt) |
| 乘0.1与min核准 | `0x1400610fa`、`0x1451de5ab` | [乘法](../../../_reference/stoneshard-study/fifth-displacement-disassembly/runtime-multiply-double-context.txt)、[min](../../../_reference/stoneshard-study/fifth-displacement-disassembly/runtime-min-context.txt) |

OBJT 原始位置：3522对象文件偏移10438720，父5296；5559偏移11165984，父5531；5326偏移11060784；6189偏移11418560，父5949；8450偏移12119016，父5338。OBJT父字段位于对象起点+28。本章匹配与额外运行时上下文的摘要见 [本轮局部发现](../../../_reference/stoneshard-study/fifth-displacement-findings.md)。

## 9 已回答、缺口与独立设计借鉴

**已回答**：猛踹真实身份与基础配置、准备钝击、攻击结果门禁、抗性阈值和默认一格；舌拉真实出生对象、攻击返回门禁、阈值与 `min(D−1,4)` 请求；公共资格/免疫、反向向量、敌人标志分支逐格停止与部分完成；可破坏对象碰撞准备钝击的一条公式。

**部分回答**：公共碰撞规则与状态效果有真实调用链，但未穷尽所有地形、对象和后处理；普通有限数概率规则已核对，但 S 槽未确认，无法给出游戏全局准确成功率；技能主体事件已连到控制入口，但所有出生、碰撞、Alarm和取消派发条件未闭合。

**未回答**：玩家完整受推/受拉路径、Tongue Pull是否对应任何玩家译名钩取、全部技能距离度量和角落阻挡规则、撞墙/单位互撞完整伤害及连锁、免疫赋值来源、额外控制状态的最终持续、各技能成本在取消时是否退款。不要把未知的图层槽、阶段或函数返回值补成设计事实。

自研可借鉴的结构是“攻击成功→控制资格与抗性→请求路径→逐格验证→位置提交→碰撞后果”，并让一次位移结果明确区分拒绝、走完、部分完成、首格阻挡。由独立游戏需求决定概率、斜向距离、撞墙伤害和是否链式推动；不继承本机 101 输出抽样、未解槽或专有实现代码。

建议在自己的实现中使用可注入随机源、显式栅格规则和结构化位移结果，并测试免疫、目标消失、请求零/负步数、第一格阻挡、中途阻挡、斜角、对象互撞、状态清理。这里是独立设计建议，本轮没有编写或运行这些生产代码/测试。

**验证与风险**：已核对指令操作数、运行时算术/比较、配置列绑定及OBJT索引。未启动游戏、未做战斗实测；本轮采用静态续查，已确认局部规则未依赖启动游戏，实际时序和实战行为仍待运行核对。未修改目标、存档或提取资产用于复用。剩余风险是静态局部覆盖、运行时字段与事件条件尚未闭合；所有构造参数和条件概率都已单独标明。
