# 紫色晶石调查证据与阅读范围

[返回拆解目录](README.md)

这组文档研究本机 Stoneshard 的部分地图和角色系统，供团队理解系统设计、编写自己的行为规格。文档中的算法描述按证据强度划分；伪代码由我们重新组织，用于说明输入、状态和分支，不是原始 GML 源码，也不是原游戏代码的生产实现。

## 调查对象

目标安装目录是 `E:\Steam\steamapps\common\Stoneshard`。调查记录时间为 2026 年 10 月 11 日，美国西部时间；前一轮详细文档整理时的权威时间为 13:37:46 PDT，第三轮战斗调查收尾核对时间为 14:22:15 PDT（2026-10-11 21:22:15 UTC）。

| 制品 | SHA256 | 作用 |
| --- | --- | --- |
| `StoneShard.exe` | `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa` | 原生机器指令、函数登记与运行时元数据 |
| `data.win` | `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c` | 对象继承、事件、房间、字符串及资源登记 |
| `FastAstarClang.dll` | `12d0e61efe736249fa22ca687ed992951c7064ab773b068f5c65abb57c6ce7e1` | 包内存在的寻路相关库；尚未恢复其完整算法 |

安装制品采用 GameMaker Windows x64 原生编译形式。`data.win` 没有普通 GML 字节码的 `CODE` 块；代码解释主要依赖 EXE 指令、参数、控制流及资源元数据。包内的 `0.9.2.6` 字符串不是单独核实过的版本显示结果。文件摘要比推测版本号更适合固定本次结论的适用对象。

现有资源调查覆盖 1,067 个房间和 9,663 个对象的相关元数据，函数登记索引含 25,272 条记录。登记数量不等于业务算法数量，房间资源数量不等于一次地图生成的房间数量。第一轮解码 61 个选定函数，后续按问题选择更多函数；这些覆盖存在交叉，不能相加宣称所有函数已经解释。

第三轮沿战斗技能、Buff、召唤、巨魔冲击波与投石，以及公共回合/伤害入口继续静态解码。10–14 提供实际配置表、对象继承、事件调用、局部公式和构造演算。新增记录与前两轮也存在重叠，不以文件数冒充全游戏覆盖；延迟攻击的逻辑倒计时已建立，创建当轮是否消费第一次、画面上的精确回合间隔仍需运行核对。

第四轮增量见 [15 预告攻击生产链](15-telegraph-production-chain.md)、[16 技能提交与 AI 门禁](16-skill-commit-and-ai-gates.md)、[17 保存与逻辑时钟](17-persistence-and-clock-boundaries.md)。新增确认出生效果创建持续状态、施法占用计数、投石终点碰撞至格伤害的局部链，正常敌人施法的冷却/MP/创建提交顺序，以及 floorSeed 的 PRNG 设定和局部保存/时间处理器。准备动画、投射碰撞和 Alarm 确实参与部分生产与结算；不能宣称所有结算完全独立于表现。首次逻辑消费相位、巨魔最上游调度与投石发射派发、完整取消补偿、独立预告对象保存、NPC 离屏算法及全部地牢返回/读档稳定性仍保留未知。

第四轮开始的权威时间为 2026-10-11 16:26:55 PDT（23:26:55 UTC），收尾记录时间为 16:49:25 PDT（23:49:25 UTC）。主要 EXE/data.win 的完整摘要复核与上表一致；没有读取新存档、启动或附加目标、修改制品/存档或监测网络。增量记录仍来自本地静态分析，不是 REA Evidence 会话。

第五轮开始时间为 2026-10-12 18:37:40 PDT（2026-10-13 01:37:40 UTC）。完整摘要复核与上表一致。增量 [18](18-swap-and-mobile-attacks.md)–[21](21-arcane-tether-and-hooking-cut.md) 研究换位、自身移动攻击、猛踹、敌我拉拽、公共击退、AOE 候选形状与目标筛选。已确认部分具体属性公式和事件次序；形状候选数不等于有效格数，概率助手输入不等于界面百分比，位移请求不等于全部完成距离。没有启动/附加游戏、读取新存档、修改制品/存档或监测网络；这些记录继续属于本地静态分析。

第六轮开始时间为 2026-10-12 19:12:57 PDT（2026-10-13 02:12:57 UTC），完整摘要复核与上表一致。[22 特殊技能候选](22-special-skill-candidates.md) 在限定技能表文本范围匹配 249 行，再核对选定出生、状态、实体与响应事件，筛出 11 类值得继续研究的机制。新增确认包括巨石状态向抛投/爆破参数转换后被消费、连锁候选收集、球状闪电反向一格请求、人数伤害准备、静滞清理、幻象外观复制、反射参数改写以及石刺的分层生成。这是候选价值评估，未全面恢复每项技能；配置匹配数不是全部技能覆盖率。没有启动/附加/修改目标、读取新存档或监测网络。

第七轮开始时间为 2026-10-12 19:30:59 PDT（2026-10-13 02:30:59 UTC），文档核对时的权威时间为 19:50:59 PDT（2026-10-13 02:50:59 UTC）。EXE/data.win 完整摘要与上表一致。新增 [23 视野与迷雾](23-player-vision-and-fog.md)、[24 主动探查](24-investigation-and-reveal.md)、[25 部位命中与伤势](25-body-part-hit-selection-and-injuries.md)、[26 玩家听觉提示](26-player-hearing-and-noise-signals.md)。已确认当前/历史网格分离与历史保存恢复、陷阱/秘密门的机会和成功状态、默认与限定部位抽选、护甲接入及 Condition/流血局部公式，以及玩家提示的来源复用与寿命。这仍是静态局部研究；完整遮挡、派发频率、概率实际下限、Condition 下界与所有伤势属性未闭合，没有运行目标或读取新存档。

第八轮开始时间为2026-10-12 20:41:27 PDT（2026-10-13 03:41:27 UTC），目标完整摘要与上表一致。新增 [27 部位减益](27-body-part-injury-debuffs.md)、[28 流血](28-bleeding-and-blood-loss.md)、[29 绷带](29-bandages-and-wound-treatment.md)、[30 夹板](30-splints-and-injury-stabilization.md)、[31 恢复](31-injury-recovery-and-health-restoration.md)。已恢复六部位三级贡献表、普通/稳定差异、流血持续与伤害链、选部位绷带清理、夹板即时Condition增量和稳定替换，以及剩余治疗量驱动部位恢复的局部公式。属性贡献不等于全部最终面板，状态计数不等于实测行动跨度；所有消费/取消、医学保存、睡眠与离屏时序仍有缺口。本轮未运行或修改目标、读取新存档或监测网络，继续使用本地静态证据。

第九轮开始时间为2026-10-12 22:20:57 PDT（2026-10-13 05:20:57 UTC），EXE/data.win完整摘要与上表一致。新增 [32 物理剑击](32-physical-attack-damage-resolution.md)、[33 弩手行动](33-arbalester-skill-scoring-and-action-choice.md)、[34 敌人自救](34-enemy-self-treatment-and-survival.md)、[35 攻击结果与事件](35-attack-results-and-event-order.md)。已绑定Drifter Sword真实表行、Slashing格挡/护甲/抵抗实参和局部公式、攻击的多个随机标志及选择顺序、HP应用和保护；同时闭合Taking Aim/Headshot评分、当前新版候选消费者与敌人治疗代理执行。构造例子和真实配置分别标注，不把未知共享下限、配置到聚合属性、全部特殊修正、完整战术场景和逃跑触发补成默认值。本轮继续静态分析，没有运行/附加/修改目标、读取新存档或监测网络。

第九轮收尾的EXE/data.win完整摘要复核一致，见 [制品复核](../../../_reference/stoneshard-study/ninth-target-final-verification.json)。目录的UTF-8、标题/代码块、当前本地链接、新增VA定位及构造算术检查见 [文档验证](../../../_reference/stoneshard-study/ninth-document-validation.json)；这些检查不替代游戏实际运行或完整动态算法验证。

第十轮开始权威时间为2026-10-12 23:21:19 PDT（2026-10-13 06:21:19 UTC），完整制品核对为23:22:57 PDT（06:22:57 UTC），摘要仍与上表一致。新增 [36 控制重叠](36-control-overlap-and-action-locks.md)、[37 预告取消](37-telegraph-interruption-and-cancellation.md)、[38 格挡响应与反击](38-block-reactions-and-counterattack.md)、[39 反射重定向](39-reflection-redirection-and-source-ownership.md)。已连通两控制的列表生产/删除与部分消费者、真实skill/spell类别到取消/清格、critBlock的响应及真正反击登记/Alarm6，以及封印选替代目标、实际换位消费和来源清除。删除位置槽值、完整初始化/解除相位、死亡/投射物取消和全局重入仍未知；本轮继续静态读取，未运行/附加/修改目标、读取新存档或监测网络。

第十轮收尾的 [制品摘要复核](../../../_reference/stoneshard-study/tenth-target-final-verification.json)、[全目录与新增地址验证](../../../_reference/stoneshard-study/tenth-document-validation.json) 和 [条件状态/算术例子](../../../_reference/stoneshard-study/tenth-derived-examples.json) 保留为本机检查记录。独立例子检查的是明示前提下的规格演算，不是游戏实际运行测试或所有状态组合的保证。

第十一轮开始权威时间为2026-10-13 01:00:50 PDT（08:00:50 UTC），完整摘要读取为01:02:41 PDT（08:02:41 UTC），EXE/data.win与上表一致。本轮按用户授权研究八个方向，新增 [40 连锁传播](40-chain-lightning-target-propagation.md)、[41 远程选位](41-ranged-ai-position-scoring.md)、[42 投射物](42-projectile-collision-and-target-changes.md)、[43 资源吸取](43-life-and-energy-drain.md)、[44 混合伤害](44-mixed-damage-crit-and-fumble.md)、[45 属性流水线](45-equipment-buff-attribute-pipeline.md)、[46 地形实体消费](46-combat-terrain-and-entity-consumption.md)、[47 盟友响应](47-ally-skills-and-group-response.md)。已补具体配置、实参、状态消费者、清理分支与构造算例；全部空间评分、链总跳数、墙体选择、巨石自动到期和全部属性/类型副作用仍有明确缺口。

第十一轮沿用REA工具/提供者缺失记录，使用本地静态后备分析，没有setup或虚构REA Evidence。不同新证据文件分别记录Capstone 5.0.7或5.0.9，不能统一宣称由同一版本生成；字节解码、地址核对和独立算术不等于实际运行。仍未启动、附加、修改目标、读取新存档或监测网络。本机检查记录为 [开始身份](../../../_reference/stoneshard-study/eleventh-target-identity.json)、[收尾制品复核](../../../_reference/stoneshard-study/eleventh-target-final-verification.json)、[全目录验证](../../../_reference/stoneshard-study/eleventh-document-validation.json) 和 [属性条件演算](../../../_reference/stoneshard-study/eleventh-attributes-derived-examples.json)。正式文档自包含必要规则；这些本地可再生成证据不随仓库分发。

第十一轮收尾完整摘要复核时间为2026-10-13 02:56:45 PDT（09:56:45 UTC），两项制品均与开始摘要一致。全目录49篇Markdown的UTF-8、标题/围栏和本地链接已经核对；40–47的地址检查验证来源关联及PE映射，不自动证明指令语义。八方向的 [条件规格演算](../../../_reference/stoneshard-study/eleventh-derived-examples.json) 均通过，其中真实配置、构造条件与未知运行槽分开保存。

第三轮结束前重读 EXE 与 data.win 的完整 SHA256，与本轮开始及前轮记录一致，见[本机制品复核](../../../_reference/stoneshard-study/third-target-hash-verification.json)。本轮没有修改这两个目标文件。

## 如何理解确定程度

| 标记 | 能支持的结论 | 不能支持的结论 |
| --- | --- | --- |
| 指令确认 | 指定入口中的读写、运算、参数和局部分支 | 其他入口也遵循同一规则，或完整调用链已恢复 |
| 资源确认 | 某对象父类、某房间连接标记、某配置确实存在 | 资源一定仍活跃，或每局一定使用 |
| 存档确认 | 被读取快照中实际存在的结构和值 | 快照必定由当前 EXE 生成，或两次快照间采用某种模拟算法 |
| 静态调用确认 | 指定位置确实调用目标入口 | 调用在玩家运行中已发生，或按某个频率发生 |
| 推断或独立设计 | 根据已知规则提出合理结构、实现方案 | 原开发者的实现或意图已被证明 |
| 待查入口 | 函数名与地址已定位，适合下一轮追踪 | 仅凭名称即可确定公式、时间粒度或完整行为 |

“完整指令解码”表示给定字节范围可全部解析为指令，不表示全部指令语义、辅助函数或业务路径都已理解。每篇模块文档的具体限制优先于概括性描述。

## 地址与数值的约定

文中的 VA 是静态首选映像地址，EXE 首选基址为 `0x140000000`。运行时地址可能因 ASLR 改变，VA 不能直接作为运行时注入地址。已记录的 `.text` 映射中，文件偏移可由 `VA - 0x140000000 - 3072` 得到；这个公式只适用于这一个制品的相应节，不适用于任意 PE 文件或其他节。

某些运行时函数的 `.pdata` 第一项只描述首片段。已跟踪的数值最大值助手便继续跳转到后续片段，不能把第一项的 43 字节当成全部算法。反汇编 context 文件可能包含邻近函数，只能引用从明确入口可达的相应指令。

元数据 RIP 引用经常指向 ID 字段，名称指针在引用地址前 8 字节；后 8 字节可能属于相邻名称记录。变量名结论由这一布局与具体读写、调用关系共同核对。未绑定的运行时槽保留未知，不因 PE 初始零值就认定游戏运行中始终为零。

GameMaker 的 undefined、布尔 false、对象哨兵和数值零可能表达不同状态。睡眠清理实际写入 type `0xD`、数值零，即假值；前两轮将它误称为 undefined，第三轮结合本机运行时真值转换助手 `0x145196dc0` 更正。类型 13 与类型 5 走不同分支，不能因为载荷同为零就混同。部分实体流程使用 `-4` 或 `-1` 哨兵。跨语言自研实现可以自行定义清楚的类型，但应先记录原有语义。

伪代码中的占位名如 `initialProgressKey`、`unresolvedFilter` 表示参数未恢复。构造演算明确说明假定输入；不会把假设的墙系数、出生坐标或随机输出冒充实际游戏数据。

## 存档证据

经用户授权，只读解析了已有角色目录中的一份退出存档与一份自动存档。两者的压缩内容可解析为 JSON 主体；主体后有 32 个十六进制字符及 NUL，尾串用途未确定。简单的主体 MD5 未与尾串匹配，这既不能证明存档损坏，也不能证明某种校验通过。

| 快照 | SHA256 |
| --- | --- |
| 退出存档 `data.sav` | `0155bd9b288fe1e71813815a912bfc3f4cab765f3a2c89a080961cbac9487a95` |
| 自动存档 `data.sav` | `f6245c52429bdb11ea4813d5dcb8f19b0b2da5769b533b07c1af374719376fb1` |

读取前后摘要一致。正式文档仅引用必要的 NPC 字段和结构，不收录完整存档、账号设置、私人角色信息或原始游戏资产。两份快照包含不同进度，不能把差异直接归因于离屏模拟。`wipeVersion="0.9"` 的具体语义也未完全恢复，不能用它证明精确发行版本一致。

## 本机证据与正式文档

正式文档位于 `docs/studies/stoneshard`，可以独立阅读。补充的本机索引、解码结果与早期报告位于被 Git 忽略的 `_reference/stoneshard-study`。这些可选链接在当前机器可用；仓库克隆不会自动带上本机证据。模块正文保留关键入口、地址、参数、例子和限制，不依赖读者下载游戏二进制或整个证据目录。

| 证据组 | 本机记录 |
| --- | --- |
| 制品与资源 | [容器元数据](../../../_reference/stoneshard-study/container-metadata.json)、[PE 布局](../../../_reference/stoneshard-study/pe-layout.json)、[函数登记](../../../_reference/stoneshard-study/native-function-map.json) |
| 地图 | [第一轮地牢](../../../_reference/stoneshard-study/dungeon-findings.md)、[第二轮世界地图](../../../_reference/stoneshard-study/second-world-findings.md) |
| 敌人 | [第一轮敌人](../../../_reference/stoneshard-study/enemy-findings.md)、[第二轮感知](../../../_reference/stoneshard-study/second-perception-findings.md)、[第二轮装备技能](../../../_reference/stoneshard-study/second-loot-skill-findings.md) |
| NPC | [第一轮 NPC](../../../_reference/stoneshard-study/npc-findings.md)、[第二轮 NPC](../../../_reference/stoneshard-study/second-npc-findings.md)、[实际铁匠快照结构](../../../_reference/stoneshard-study/save-smith-observation.json) |
| 后续调查 | [按名称筛选的候选入口](../../../_reference/stoneshard-study/related-system-entrypoints.json) |
| 第三轮技能与 Buff | [技能指令索引](../../../_reference/stoneshard-study/third-skill-native.json)、[对象元数据](../../../_reference/stoneshard-study/third-skill-object-metadata.json) |
| 第三轮召唤 | [召唤指令索引](../../../_reference/stoneshard-study/third-summon-native.json)、[召唤调查](../../../_reference/stoneshard-study/third-summon-findings.md) |
| 第三轮预告与公共战斗 | [预告技能指令索引](../../../_reference/stoneshard-study/third-telegraph-native.json)、[回合伤害指令索引](../../../_reference/stoneshard-study/third-turn-damage-native.json)、[数值助手核对](../../../_reference/stoneshard-study/third-runtime-helper-observations.json) |
| 第五轮选定技能配置与玩家拉拽 | [完整表行](../../../_reference/stoneshard-study/fifth-skill-config-rows.json)、[秘术/斧类指令索引](../../../_reference/stoneshard-study/fifth-control-native.json)；其他新增证据见 18–20 各篇 |
| 第六轮特殊技能候选 | [有界配置扫描](../../../_reference/stoneshard-study/sixth-skill-config-inventory.json)，以及 [22](22-special-skill-candidates.md) 末尾列出的闪电、秘术、地形与其他事件记录 |
| 第七轮迷雾与探查 | [视野指令索引](../../../_reference/stoneshard-study/seventh-fog-native.json)、[探查指令索引](../../../_reference/stoneshard-study/seventh-detection-native.json)、[实际配置与资源](../../../_reference/stoneshard-study/seventh-detection-resources.json) |
| 第七轮部位与玩家听觉 | [部位指令索引](../../../_reference/stoneshard-study/seventh-body-native.json)、[部位演算](../../../_reference/stoneshard-study/seventh-body-derived-examples.json)、[听觉指令索引](../../../_reference/stoneshard-study/seventh-hearing-native.json)、[听觉调用者确认](../../../_reference/stoneshard-study/seventh-hearing-verified-callers.json)、[目标摘要](../../../_reference/stoneshard-study/seventh-target-identity.json) |
| 第八轮伤势与流血 | [伤势指令索引](../../../_reference/stoneshard-study/eighth-injury-native.json)、[部位对象](../../../_reference/stoneshard-study/eighth-injury-objects.json)、[属性贡献](../../../_reference/stoneshard-study/eighth-injury-helper-data-candidates.json)、[流血指令索引](../../../_reference/stoneshard-study/eighth-bleed-native.json)、[流血算例](../../../_reference/stoneshard-study/eighth-bleed-derived-example.json) |
| 第八轮治疗与恢复 | [治疗指令索引](../../../_reference/stoneshard-study/eighth-treatment-native.json)、[治疗资源](../../../_reference/stoneshard-study/eighth-treatment-resources.json)、[恢复指令索引](../../../_reference/stoneshard-study/eighth-recovery-native.json)、[恢复助手](../../../_reference/stoneshard-study/eighth-recovery-helper-checks.json)、[本轮目标摘要](../../../_reference/stoneshard-study/eighth-target-identity.json) |
| 第九轮攻击与伤害 | [攻击指令索引](../../../_reference/stoneshard-study/ninth-attack-native.json)、[伤害指令索引](../../../_reference/stoneshard-study/ninth-damage-native.json)、[剑表行](../../../_reference/stoneshard-study/ninth-weapon-example-config.json)、[槽检查](../../../_reference/stoneshard-study/ninth-attack-helper-checks.json)、[伤害演算](../../../_reference/stoneshard-study/ninth-damage-derived-examples.json)、[HP演算](../../../_reference/stoneshard-study/ninth-attack-derived-examples.json) |
| 第九轮弩手选择与自救 | [AI指令索引](../../../_reference/stoneshard-study/ninth-ai-native.json)、[评分绑定](../../../_reference/stoneshard-study/ninth-ai-evaluator-bindings.json)、[治疗指令索引](../../../_reference/stoneshard-study/ninth-survival-native.json)、[物品表](../../../_reference/stoneshard-study/ninth-survival-item-config.json)、[资源与分派](../../../_reference/stoneshard-study/ninth-survival-resource-and-dispatch.json)、[目标摘要](../../../_reference/stoneshard-study/ninth-target-identity.json) |
| 第十轮控制与预告取消 | [控制入口](../../../_reference/stoneshard-study/tenth-control-native.json)、[控制对象](../../../_reference/stoneshard-study/tenth-control-objects.json)、[删除槽引用](../../../_reference/stoneshard-study/tenth-control-delete-slot-xrefs.json)、[取消入口](../../../_reference/stoneshard-study/tenth-interrupt-native.json)、[真实类别绑定](../../../_reference/stoneshard-study/tenth-interrupt-class-bindings.json)、[本轮身份](../../../_reference/stoneshard-study/tenth-target-identity.json) |
| 第十轮格挡与反射 | [响应入口](../../../_reference/stoneshard-study/tenth-reaction-native.json)、[响应对象](../../../_reference/stoneshard-study/tenth-reaction-objects.json)、[反射入口](../../../_reference/stoneshard-study/tenth-reflection-native.json)、[反射结论/例子](../../../_reference/stoneshard-study/tenth-reflection-findings.json) |

当前没有可用的 REA MCP 原生分析会话或配置好的原生深度分析提供者；证据来自本地资源解码、PE 登记和指令静态分析。这里的本机记录不冒充 REA Evidence 对象，也没有给它们虚构会话 ID。

## 验证与研究边界

已执行局部指令与资源核对、必要的存档结构解析以及文档检查。没有启动游戏、附加进程、修改内存、游戏文件或存档，也没有监测联网行为。因此“实际每回合怎样执行”“游戏内按钮最终显示什么”“不同位置听见声音的结果”等运行时问题仍按未知处理。

这些文档交付行为规格和算法解释。自行制作游戏时，应按自己的玩法目标独立实现，并采用原创或有适当授权的资源；不会把恢复代码翻译、拼接或包装为我们产品的生产代码。风险主要来自扩大局部结论、混淆旧入口与活跃入口，以及把静态调用当成运行观察。
