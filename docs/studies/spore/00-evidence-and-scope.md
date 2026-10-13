# 00 证据、目标与推导边界

[目录](README.md)。研究限定于 PC Spore 登陆后的生物阶段及其编辑器；不把部落、冒险编辑器、车辆或整款游戏混成一个系统。“泰坦古生物”暂按 Epic Creature 理解。

## 本机身份

安装目录：`E:/Steam/steamapps/common/Spore`。本轮文档时间锚点 2026-10-11 20:55:16 PDT 对应 2026-10-12 03:55:16 UTC；日期差异来自时区。已读目标：

| 文件 | bytes | SHA256 |
| --- | ---: | --- |
| SporeBin/SporeApp.exe | 20,626,168 | `f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d` |
| Data/Spore_Game.package | 20,210,108 | `9d085118c649d211a86723d363592fd66ad655fd24497289b3eab96bb07db329` |
| Data/PatchData.package | 80,428,851 | `cadbff237076b441e6981503f80538705aefa5863bb4c8d1b869f9db98d1adff` |

EXE 为 PE32 i386，版本资源 `1.3.0.29`，首选 ImageBase `0x400000`。本轮材质与 Epic 调查再次核对 EXE 摘要一致；包摘要沿用首次研究，不宣称本轮重新散列包。`.rdata` 文件起点 `0xfcb400`、RVA `0xfcc000`、原始长度 `0x13f600`。仅该节内，静态数据 VA = 文件偏移 + `0x400c00`；不是函数入口或已知运行地址。

首次两包 DBPF 3.0 索引检查详见[历史记录](notes/initial-multi-leg-study.md)：资源数 11,529 / 25,535，存储范围在文件内，当时未解压或解释资源。后续[25](25-body-reach-attack-ranges-and-hit-resolution.md)重新散列并局部解码技能PROP，[26](26-land-approach-stopping-avoidance-and-gait.md)继续读取移动PROP和GAIT结构；这些配置观察不等于已恢复执行调用链，各自记录覆盖与限制。

## 证据等级

[27](27-perception-target-memory-and-motive-selection.md)续查再次散列两包与EXE，摘要仍与本页表格一致；局部读取8条CreatureGameTuning感知/逃跑PROP。其覆盖与公开动机声明、本机完整字面量单独记录，不将感知算法或饥饿阈值标为已恢复。

[28](28-parallel-actions-channel-ownership-and-conflicts.md)续查再次复核身份，并沿已有四类技能动画ID局部读取TLSA播放组及ANIM通道元数据。配置移动许可、历史自由度混合与自研技能预约分开，不将通道元数据当成当前身体的实际绑定或运行调用链。

| 标签 | 能说明什么 | 不能说明什么 |
| --- | --- | --- |
| 官方规则 | 公开的候选资格、内容来源原则 | 本机实际生成频率与数值 |
| 开发团队设计 | 历史公开机制 | 此 EXE 的每个实现细节 |
| 本机静态线索 | 字符串存在、偏移、邻接范围 | 谁读取、参数意义、是否执行 |
| 本机配置观察 | 选定格式下解析的资源键、字段原值与结构 | 单位、默认/继承/加载结果或实际执行公式 |
| 社区声明 | 可研究的字段/资源接口 | 本版本 ABI、字段写入路径 |
| 用户观察 | 身体加粗带动肢体等外部现象 | 唯一内部实现 |
| 独立规格 | 我们选定的数据与可检验关系 | 原游戏恢复代码 |
| 未知 | 缺少证据的具体环节 | 不得以常见实现补成事实 |

普通只读检查没有 REA Evidence ID；不生成虚构 ID。源文件摘要和偏移作为可复核定位，网页保留原始链接。后续若取得原生分析，应另外记录工具版本、读取范围与交叉引用，不覆盖这些原始事实。

## 一手资料的事实摘要

**动画。** 开发团队公开系统使用身体查询绑定动作；目标适配形态后求解姿态。步态按近似腿长分组，协调频率与足部时序，参数随速度变化；粒子约束 IK 分脊柱与肢体阶段，参考姿态与被动附属运动有独立作用。详见 [Hecker 等，SIGGRAPH 2008](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)。这些事实是研究锚点；03–06 的结构布局、阈值、状态机和代码是我们独立设计。

**编辑形变。** 参数化手柄组合部件变形是公开入口，不能据此恢复滚轮输入与附着重建的完整顺序。[Rigblocks 论文](https://www.cs.cmu.edu/~ajw/s2007/0248-Rigblocks.pdf)

**皮肤。** 生物身体使用快速 UV 分区；理解身体形态的表面粒子驱动笔刷，玩家组合 base、coat、detail 与颜色，写入颜色、高光、凹凸等通道。论文的车辆/建筑运行时映射另属一类。[Maxis，Player-Driven Procedural Texturing §2–3](https://www.cs.cmu.edu/~ajw/s2007/0311-PaintingModels.pdf)。配套演讲还讨论表面局部方向、后台烘焙与缓存；不能把所有演示选项认定为本机参数。[演讲幻灯片](https://www.cs.cmu.edu/~ajw/s2007/0311-PaintingModels-slides.pdf)

**实现历史。** 开发笔记解释六向分区、表面笔刷与接缝处理，并区分原型和后来的形态感知系统；早期原型不等于本版实现。[Hecker 开发笔记](https://chrishecker.com/My_Liner_Notes_for_Spore)。开发者另有紧凑描述到可用模型的 baking 说明。[Shalin Shodhan 项目记录](https://www.shalinshodhan.com/projects.htm)

**Epic。** NPC 槽按 archetype 匹配作品，来源有订阅偏好和回退；CRG 的 Epic 捕食者有部件条件。08 记录具体条件，不能把资格解释为出现保证。[Maxis Archetypes 教程](https://www.spore.com/comm/tutorials/archetypes)。该页直开返回 502，本轮通过搜索服务读取官方页全文和表格；不是运行观察。

## 社区接口入口

| 入口 | 研究用途 |
| --- | --- |
| [Anim::CreatureBlock](https://modapi-docs.sporecommunity.com/struct_anim_1_1_creature_block.html) | 父子、对称、身体能力等结构线索 |
| [EditorRigblock](https://modapi-docs.sporecommunity.com/class_editors_1_1_editor_rigblock.html) | 附着、方向、形变和连接线索 |
| [动画导出文档](https://github.com/Spore-Community/SporeModder-FX/wiki/Exporting-creature-animations-from-Blender) | 身体选择器、变体、事件等格式研究 |
| [cCreatureBase](https://modapi-docs.sporecommunity.com/class_simulator_1_1c_creature_base.html) | 技能入口与播放入口分离 |
| [cHerd](https://modapi-docs.sporecommunity.com/class_simulator_1_1c_herd.html) | 物种、位置、缩放和角色参数 |

字段解释必须回到实际使用者验证；社区版本与本机版本关系未证实。

## 授权与未做

[55](55-joint-limits-shape-edits-and-motion-feasibility.md)–[59](59-soul-body-calibration-feedback-and-experience-transfer.md)继续查编辑器与肉体/灵魂的接口。55仅重读既定Graphics手RW4的4行AnimationSkin与10个LocRot，未复核整个大包；局部曲线角跨度只是带假设的诊断，不称真实限角。56复核Game/Patch并读两TLSA内三个普通idle组及六份ANIM metadata，共51通道，未读曲线/事件。57读取十份明确Creature编辑动作PROP、官方手册完整测试场页，并与PlayMode/NeutralPose声明分别对照；58复用编辑结构，不宣称已确认原作整链复制或保留指头替换。59只复核既有参考摘要，反馈学习、弱先验和迁移均为用户产品的独立机制，没有新原作载荷。各篇核心结构、伪代码、贯通例子和检查见[本轮总记录](evidence/editor-body-ai-five-topics-verification.json)。本轮没有启动/附加游戏、读私人保存、输出完整专有资产或实施用户产品。

[50](50-complete-creature-recipe-runtime-bones-and-bindings.md)–[54](54-creature-population-animation-and-simulation-lod.md)续查完整映射、时间、注视、表现与运行成本。50只在七包索引中选四个小CRT/creaturedata版本，共6801 decoded bytes；三椎骨模板不是完整器官生物，编译候选存在属性chunk格式诊断，原作端到端未建立。Game/Patch完整摘要复核，其他五包只复核头/索引与所选小资源，不声称完整散列。51复用八ANIM、两TLSA与两gait6的时间字段；52复用612通道，9个LOOKAT位全是手部skrs，不当凝视实现。53重读两包身份，读取六个Patch FX目录/四audioProp，10匹配导出与20叶为静态候选链，声音数组与声音组件分开。54重读八份既定移动PROP，直接SimulationLOD Low100/Med75不填单位或运行阈值。各篇新增固定公开源、独立核心结构/伪代码/同一场景变化与检查见[本轮总记录](evidence/land-runtime-five-topics-verification.json)。本轮没有重新读取EXE指令、运行游戏、读取私人保存或导出完整模型/音频。

[38](38-axis-controls-capability-role-and-local-deform-binding.md)续查三轴/放置引用和角色变形映射：七包索引的六键及同ID候选均未命中，未读取控制模板payload；两包PCTP资源键不同，v3仅头部记录，v4完整遍历边界并导出mout/grsp的选定字段。取得手部件类型ID→grsp及嘴deform→既有ANIM的静态对应，不证明运行加载或调用。28项研究检查见[本轮验证](evidence/part-binding-verification.json)；本轮重新散列两包，没有重读EXE/Graphics模型或扩查其他阶段玩法。

[39](39-same-role-effectors-variant-binding-and-default-mixing.md)续查多同类肢体选择、绑定与默认参数：开发团队明确集合查询→变体→游戏选择及相关肩部共同变化；重读28既定46份ANIM并核对摘要/全部通道元数据，导出26条context原字节代表记录。两包完整摘要再次一致；未重读EXE/Graphics、PCTP或曲线。35项证据一致性/独立算例检查见[验证记录](evidence/same-role-binding-verification.json)。默认描述、动态曲线和蒙皮权重分开；本机执行者选择、PCTP加载/混合与最终骨骼绑定尚未恢复。

[40](40-action-events-emitters-hit-windows-and-stale-callbacks.md)–[44](44-editor-rebuild-undo-and-animation-cache-consistency.md)按五项续查：本机40仅沿既有四键在两包读8份ANIM事件/INFO元数据，共60事件/770INFO，EXE完整文件、包与资源摘要复核一致；EXE的PE/版本元数据仍复用，未执行代码。其余四篇复用既有本机配置/骨架/选择器JSON并续读固定公开源与开发团队资料，没有新模型/GAIT/私人配方读取。明确区分左右与镜像、共享关节与独立末端、足角色与有效支撑、内容缓存与运行世代；原作伤害、镜像执行、无足选择及重建取消消费者仍未知。断肢/换魂结算是用户游戏的独立需求。各检查与覆盖见[总验证](evidence/land-five-topics-verification.json)，不更改先前模块的历史检查数。

[45](45-animation-predicates-conditional-binding-and-fallbacks.md)–[49](49-editor-surface-snapping-attachment-and-connection-validation.md)推进条件/统计/受击/次级/交互：45实读既定46份ANIM的整段与818事件条件、612通道require，EXE和两包摘要复核；46新读四个普通手/嘴PROP，格式明确的BBox39仅保留opaque24字节，复用旧50技能需求记录。47–49复用既有配置/模型/入口及续读固定公开资料，不读取新动作/模型/私人配方。原作条件执行、统计归约、受击裁决、Jiggles参数和拾取连接消费者未恢复；独立核心结构、伪代码、贯通例子与总检查见[本轮验证](evidence/land-behavior-five-topics-verification.json)。

[37](37-part-definition-edit-controls-rigs-and-capabilities.md)续查一个陆地部件的编辑/运动定义。再次散列两包，局部解码五份Patch手部件/模板PROP并保留null候选的未支持类型诊断；在七个Data包索引中查找一个确切模型键。进一步散列Graphics包并读取此单个RW4的目录、骨架层级/蒙皮对象关系、两个动画通道目录及前两条通道共10帧。Graphics完整摘要为`e01bb86d8ddf02c56d52394b4e1db7181c1e1ebe1878bf6fb72c4ee523fcedd1`，943MB包未整体解压；没有导出模型/纹理资产或读取实际生物存档。控制点、连接和能力桥接仍属部分回答，35项研究读取/独立算例检查见[验证记录](evidence/part-definition-verification.json)。本轮未重新散列EXE，沿用既有身份及REA缺口。

[36](36-selected-skinpaint-recipe-and-material-controls.md)续查复核两包身份与索引、读取六份明确皮肤PROP，并检查Patch的12个效果目录组件前缀、两个选定目录的边界/引用及Sequence/Distribute。取得五条绘制导出到Particle索引的静态路径；没有读取Particle/Settings/笔刷内容，不把资源引用称为运行调用。覆盖与限制见[本轮验证](evidence/selected-skin-recipe-verification.json)。

[35](35-skin-pattern-shape-edits-and-seams.md)续查完整读取贴图论文、相关演讲页、开发者Creature Texturing及发行版脚注修正；复核本机104条字面量，并检查固定社区四份Skinpaint格式源码。原作表面绘制、历史消缝和格式表示与独立密度/锚点/过渡/烘焙规则分开。未读取具体皮肤/笔刷资源或恢复原生绘制链，实际覆盖见[验证记录](evidence/skin-pattern-verification.json)。

[31](31-terrain-contact-foot-locking-and-support.md)–[34](34-editor-validity-complexity-and-runtime-cost.md)续查限定地形接触、身体体积、几何/命中同步和编辑/成本。补充固定提交社区头文件与开发者论文完整相关页、局部本机入口；具体覆盖见各证据JSON。31/32的落脚与避碰、33的事务式身体发布与扫掠、34的预算算法均为独立规格，专项检查不构成原游戏运行证明。本轮验证见[记录](evidence/contact-and-cost-verification.json)。

[30](30-part-shape-rest-pose-and-local-animation.md)续查复核EXE及38条字面量、固定社区格式和Rigblocks演讲，沿28所选键读取一个Patch ANIM的嘴部标量关键帧。原作烘焙适配说明、资源原值与自研合成算法分开；没有执行插值、选取具体生物或恢复本机层合成函数。

[29](29-creature-mesh-joins-and-automatic-skinning.md)续查复核EXE及34条完整字面量，读取开发者Creature Skin Mesh章节、相关论文和固定提交社区格式。原作历史机制、网格表示线索与独立蒙皮算法分开记录；未取得一份具体生物的实际权重或原生函数链。

已完成选定制品的只读检查和文档编写。没有启动或附加游戏、读取私人存档、修改游戏文件、安装分析软件、构建 REA 或改变配置。当前没有可用 REA MCP/provider，公共启动器缺少编译产物；保持这一限制，不以字符串扫描冒充反编译。

风险：目标版本差异、历史原型差异、社区 ABI 差异，以及自研规格与原作实现混读。后续实现应使用自己的代码和自制或适当授权资产。
