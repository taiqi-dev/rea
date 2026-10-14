# 49．链式闪电：跳数预算、已击中标记与清理时钟

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [原传播算法](40-chain-lightning-target-propagation.md) · [状态生命周期](11-buffs-and-effects.md) · [投射物墙体门禁](50-projectile-wall-blocking-and-endpoint-selection.md)

本章继续核对 40 的“总跳数未确定”。新增结果是：**不能把 `count_of_bolts` 当 Chain Lightning 的实际跳数预算。对整个 EXE `.text` 的指定字段引用形式扩查后，链载体仍只有初值写入；真正的递减/后继数量消费来自 Fire Barrage、Mana Crystal Bolt 等其他对象。链传播已核的限制仍是资格状态、距离、原 owner/当前目标排除，以及单位上的 chain_struck。** 没有找到一个独立的“最多 N 跳”计数门禁，但这不证明所有动态路径均无限。

同时补到 marker 的继承、属性失效和销毁清理。它不是一个每个飞行实例都携带的 visited 集合，也不是看到 Alarm2 就每帧减少 duration。

## 1．身份、方法与这轮搜索边界

目标为 `E:/Steam/steamapps/common/Stoneshard` 的 GameMaker YYC x64 制品，首选映像基址 `0x140000000`。本轮完整摘要由根调查复核，仍为：

| 制品 | SHA-256 |
|---|---|
| StoneShard.exe | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` |
| data.win | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` |

沿用 REA 提供者缺失记录，使用已有函数登记、PE 布局、OBJT 和 Capstone 5.0.9 局部静态解码。没有 REA Evidence 会话或虚构 ID。字段名由 RIP 引用地址减 8 字节的名称指针恢复；未初始化的运行槽不按零补齐。

新搜索以 `count_of_bolts` 字段 ID 槽 `0x1495d3f68` 为目标，在整个 `.text` 原始范围匹配 `mov r32,[rip+disp32]` 指令形式，记录 21 处候选引用、所属登记入口，再结合既有真实指令复核。它扩大了上一轮“17 个链相关入口”的边界，但没有涵盖所有可能的字符串动态取字段、反射、运行时替换和非此指令形式。匹配数不是业务跳数。

本机可再生成记录：[字段引用扩查](../../../_reference/stoneshard-study/twelfth-chain-count-field-xrefs.json)、[新增生命周期入口](../../../_reference/stoneshard-study/twelfth-chain-native.json)、[OBJT 身份](../../../_reference/stoneshard-study/twelfth-chain-wall-object-bindings.json)。正式正文保存必要事实，不要求其他机器具有这些本机产物。

## 2．为什么初值 0 不是跳数上限

真实载体 9561/o_chain_lightning 的 Create 在 `0x1450edd8c..0x1450eddba` 写字段初值 0。40 已解载体 Collision、Alarm3、Other10/11 等相关事件：它们根据候选创建新的同类载体，复制伤害、owner、name、暴击字段，并写下一目标；没有在该生产段恢复一个“读旧次数→加一→与上限比较→拷入新次数”的链预算。

这轮整个 `.text` 指定引用形式的分布是：

| 对象/入口组 | 匹配次数 | 所能确认的角色 |
|---|---:|---|
| Chain Lightning Create | 1 | 写初值 0；本轮未发现对应链预算消费 |
| Fire Barrage Create、Destroy、Other12 | 7 | 真正存在剩余数量检查、减一、传递给后继；详见 42 |
| Mana Crystal Bolt birth.Other11、Create、Destroy、Other12 | 9 | 另一个技能的数量生产/消费线索，不能套给链式闪电 |
| Grimace of Terror、Discharge、Bone Throw、旧 Scream of Doom Create | 各 1 | 其他对象的字段使用；不是本次链载体的额外预算 |

21 处落入 12 个登记入口。Fire 的 `2→1→0` 表示本对象的首发与后继预算；字段名相同不表示每个法术复用同一消费者。Chain Lightning 没有自己的同名 Destroy/Other12 连发链，本对象没有被证明接入 Fire 的递减流程。

因此，对“连锁闪电到底能跳几次”的回答分两层：

- **已确认的局部传播：**每次从当前目标附近重新收集合格候选，选最近者，创建一个新载体；没有候选则不再创建。
- **仍未确认的全局硬上限：**没有恢复数字 N 或一个完整全局计数器。不得把 0 当“不能跳”、把 Range6 当“六跳”，也不得把扫描未发现当“任何环境下无限跳”。

## 3．真正的排重数据在目标单位上

40 已确认正常当前段相应路径调用 `scr_effect_create`，把 1943/o_db_chain_struck 创建到当前目标，duration 实参 1；调用在 `0x1450f1a51`。该段受格挡等分支影响，不能说任何命中结算都必定获得 marker。反射改变目标的碰撞分支也有 marker 生产（`0x1450eef59`），其对象是原碰撞目标。

下一跳候选循环读取候选单位默认状态列表中的 1943；存在则拒绝（`0x1450f1eb1/0x1450f1ec0`）。没有传本次施法 ID、载体 ID 或共享链 token。其含义是“这个单位当前具有 chain_struck”，而非“这个单位已被当前唯一施法记录访问”。

精确继承通过 `data.win` OBJT 复核：

```text
1943/o_db_chain_struck
  → 5949/o_invisible_buff
  → 5897/c_abstract_states
  → 2679/o_guiInteractive
  → 4018/c_GUI
```

它的直接祖先不是 c_buff；不能因为它是效果状态就硬套另一个对象的所有事件。chain_struck 的 Create 调 inherited 后自行写 `stage=1`、`have_duration=true`，见 `0x142fe2653..0x142fe26b6`。

共享 `scr_effect_create` 仍负责 target、owner、duration 与加入目标列表。所传 1 是创建输入；持续补偿/合并由共享创建分支决定，参见 11。不能任选“创建参数 1”“状态 stage1”“Alarm[3]=1”中的一个当精确一帧或一回合。

## 4．Alarm2、Other15 和到期是不同责任

chain_struck 的 Alarm2 调 inherited。沿上述父链到 `c_abstract_states.Alarm2 @ 0x144355660`，实际选择 target 上下文，在 `0x14435570b..0x144355728` 写 target.stats_is_change=true。它没有在这个入口执行 duration 减一或销毁 marker。因此 Alarm2 的存在不能证明“每个动画 tick 都刷新 visited”。

`o_invisible_buff.Other15 @ 0x1443cdfb0` 同样选择 target，并在 `0x1443ce05b..0x1443ce078` 令属性缓存失效。该父对象 Other11/12/13 的登记入口分别为 `0x1443ce290/0x1443ce2a0/0x1443ce2b0`，所查短入口是空返回。这里只确认这些事件没有额外次数递增，不能把一个空事件扩大成所有生命周期无行为。

真正的持续递减入口是 `scr_states_duration_dec @ 0x141ae5c20`。它选择宿主状态列表，保留 phase、decrement 和筛选/特殊状态条件。在相应有效路径中：

```text
若状态有持续时间，且本次允许递减：
    duration -= decrement
    若新的 duration < 1：销毁该状态
否则/另一相位：派状态回合事件
```

普通数值减法 `0x141ae673e`，比较 `0x141ae675f`，销毁 `0x141ae6799`，后续相位标记与状态 Other10 派发 `0x141ae67d8/0x141ae6848`。筛选来源和所有特殊状态时序未在此全部恢复；不是对全游戏任何状态无条件递减。

这轮核对 `scr_allturn @ 0x1416c1e60` 至 `scr_global_turn @ 0x1416c2a60` 的真实连接。global_turn 在两个位置调用 duration_dec：`0x1416c2e5e` 与 `0x1416c475b`，均以 5376/o_player 为首参数过滤，后一个第二参数实值 1。这建立“存在共享逻辑时钟消费者”，**不建立所有敌人 marker 也在这个玩家过滤调用中删除**。链本身无候选时存在 scr_allturn 调用（40 的 `0x1450f3c3a`），但进入全局回合与整条链飞行是否完全连续、敌人自己的递减路径何时运行仍需区分。

### 退出时列表也需要删除

沿 marker 的继承，正常执行 Destroy 进入 `c_abstract_states.Destroy @ 0x144354ca0`。它检查 target/列表有效性，查状态自身 id 在 target.buffs 中的位置（find_index `0x144354f7e`），存在时从列表删除（`0x144355076`），并写 target.stats_is_change（`0x1443550b7`）。所以排重资格移除不只是把 duration 改成零，还包含状态实例销毁与宿主列表清理。

这条静态有效对象退出链没有证明宿主已销毁、跨区、保存加载或中途切换目标时的全部清理协议。

## 5．能推出什么样的有限性

只对以下明确前提成立：场上相关单位集合固定；每次处理目标均进入 marker 创建成功路径；marker 在整条传播期间保持有效；不存在新单位、状态动态清除、格挡跳过和运行替换。

在这些前提下，传播不能再次选择仍带 marker 的旧目标；每成功处理一次就使一个相关单位退出后续候选。可访问单位数有限，因此该条件模型中的传播次数也有限。这里的上界由当前可访问单位集合决定，不是已经发现一个固定技能常量。

若 marker 过期/被清理，或某分支未创建 marker，原来已处理的单位在后续查询中可能重新具有资格。下一跳还排除“当前目标”与“原 owner”，但是这两个排除不等价于保留所有历史访问。不能仅靠这些局部门禁证明复杂场景一定不会回跳；同样，静态路径允许某种状态变化也不证明实战已经产生了循环。

## 6．具体例子：四个候选，以及 marker 消失后的差别

构造 owner=O，首段目标 T；附近 A/B/C 均有 Resonance 或 Impulse，所有实际调用与创建成功，沿非格挡 marker 生产路径，且传播过程中 marker 不递减。设实际候选距离使得 T→A→B→C，其他候选均不更近。

| 处理阶段 | 新增 marker | 已处理旧单位在下一次查询中的情况 |
|---|---|---|
| T 结算后 | T | T 是当前目标排除，之后保留 marker 排除 |
| A 结算后 | A | T/A 都不再作为未标记下一跳 |
| B 结算后 | B | T/A/B 被 marker 或当前目标条件排除 |
| C 结算后 | C | 若无其他合格单位，不创建下一载体 |

这个例子是首段加三次目标转移，不是“技能默认四跳”；它依赖这组构造候选与 marker 条件。把相关单位减少到 T/A，就会在处理 A 后耗尽，不会为了填满一个尚未证明的固定跳数创建额外命中。

再构造 A 的 **实际存储** duration=2、have_duration=true，后续确实有两次允许递减、decrement=1 的共享调用：2→1，仍存活；1→0，低于1而销毁并删除 target.buffs 项。之后的新查询不会再因该 marker 排除 A；仍需通过距离、状态资格、owner/当前目标等门禁。这不声称从创建输入1必定得到存储2，也不声称两次调用等于两帧或界面两回合。

## 7．状态、未做与后续最小核对

已回答：count_of_bolts 更广引用边界与其他技能消费分离；marker 的真实继承、生命周期责任、列表删除；候选耗尽与条件有限性。部分回答：marker 通过共享逻辑持续系统到期。未回答：全系统数字硬上限、敌人 marker 的完整调度相位、传播之间是否可能发生到期，以及动态替换/跨区/并发施法的完整行为。

有价值的下一步是恢复敌人自己的 duration_dec 调用实参，或在最小运行场景观察一条长链的目标序列、每个 marker 创建/销毁时点。单看画面闪电条数不能区分表现与逻辑跳数。

本轮没有启动/附加/修改目标，未读取新存档、监测网络或 setup，未提交推送。文档与静态地址检查不替代运行验证。风险是把共享状态当本次施法私有排重、把字段名称相同当统一连发预算，以及把有界负搜索写成不存在任何限制。自研应明确设置自己的跳数预算、单链访问集合和持续语义；这属于独立设计选择。

本机 [两篇局部验证](../../../_reference/stoneshard-study/twelfth-chain-wall-validation.json) 核对UTF-8、单一一级标题、围栏、本地链接和134处地址引用，其中字段ID槽单独分类；[条件演算](../../../_reference/stoneshard-study/twelfth-chain-wall-derived-examples.json) 检查marker存储值、像素截断和位运算模型。地址关联与自写演算不证明实际运行时序。
