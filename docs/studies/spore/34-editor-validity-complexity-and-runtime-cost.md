# 34 陆地编辑限制、复杂度与运行成本

研究限定陆地生物编辑器，衔接[网格与蒙皮](29-creature-mesh-joins-and-automatic-skinning.md)、[造型与局部动画](30-part-shape-rest-pose-and-local-animation.md)和[动作并行](28-parallel-actions-channel-ownership-and-conflicts.md)。当前证据支持“有多个限制维度和烘焙管理入口”，不能恢复本机限制阈值、最终计费或性能公式。后半篇是自研肢体拼装游戏的独立规格。

来源身份与范围保存于[公开入口记录](evidence/public-editor-budget-entries.json)和[本机字面量记录](evidence/local-editor-budget-entry-observations.json)。固定 SDK 提交 `2d71289adc71aa5c58f4516c6c835c99f5f9ca19`、FX 提交 `a482c51d8d37fc8cf416acecc3c00a5b0723f2e5`；每个公开文件记录 URL、bytes、SHA256、读取范围及阴性检索。沿用[00 的提供者缺口](00-evidence-and-scope.md)，没有安装或修复工具。

## 原作问题与证据

| 问题 | 可确认的材料 | 尚未确认 |
| --- | --- | --- |
| 是否只存在一个容量数字 | SDK 分别声明 budget、complexity、bone complexity、baked blocks、geometry score | 生物编辑器实际启用哪些维度、计数对象和上限 |
| 部件的代价在哪里表示 | EditorRigblock 声明 price、complexity score、runtime bone count、bake level | 镜像部件、躯干/脊椎、共用骨和替换的聚合与退款规则 |
| 编辑是否合法 | 边界、可玩尺寸和限制接口存在 | 连接规则、校验顺序、失败恢复和统一提交事务 |
| 快速预览与后台构建 | dirty/loading 字段、实时/HQ 分辨率、bake queue/cancel/stats | 本机线程、排队优先级、版本检查及缓存失效机制 |
| 多足是否更贵 | 有骨复杂度入口、动画播放与 LOD 名称候选 | 每足求解次数、CPU/GPU 成本、动画 LOD 实际策略 |

**社区声明：限制分离。** [EditorLimits.h L20–54](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/EditorLimits.h#L20)暴露 GetValue、HasEnough、SetLimit；StdEditorLimits 用不同枚举表示预算与复杂度。社区注释描述数值限幅和通知，没有对应目标函数体。不能据注释断言“超限编辑一定被拒绝”，更不能把限幅当作可生成性的验证。

[Editor.h L420–449](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/Editor.h#L420)分别声明皮肤/足部边界、最小可玩尺寸、block/bone complexity、baked block 数及几何评分；L98–112 另有显示复杂度标志与 undo/redo 状态中的预算。这是共用编辑器声明，未证明每项在陆地编辑里生效。注释的 `-1`、`MAX_FLOAT` 不是本机运行上限。

**社区声明：部件与模型。** 复用 30 的 [EditorRigblock.h L470–486](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/EditorRigblock.h#L470)代价与形变入口。[EditorModel.h L81–96、130–134](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/EditorModel.h#L81)有部件集合、加载/修改/皮肤更新状态；GetRigblocksCount 的社区 helper 直接返回集合长度，不能由此推出复杂度等于部件数量。

**社区声明：后台构建。** [BakeManager.h L32–92](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/BakeManager.h#L32)声明 tag/priority、队列、取消、烘焙和时间统计字段。时间单位及统计覆盖未知，CCF/BVU 未解释。与 29 的实时/HQ 分辨率字段一起，只说明质量和构建管理入口存在，不能证明距离 LOD、后台线程或成本实测。

**名字登记：LOD 与预算候选。** 固定 FX 注册表登记 editorMaxBudget、editorComplexityLimit、editorBoneComplexityLimit、modelBakeMeshBudget、modelLODDistances、creatureSimulationLOD_MinDistanceLow/Med、useHighAnimLOD 等。详见来源记录的行号；没有读取这些属性的具体资源值、继承/default 或调用者。modelBakeRubble/Sprites 等明显跨类型名称没有用于陆地结论。Simulation LOD 与 Animation LOD 的名字不能互换。

**本机完整字面量。** 本轮重新散列 `SporeApp.exe`：20,626,168 bytes，SHA256 `f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d` 一致。在 `.rdata`、`.data` 指定范围内检查完整 NUL ASCII 字符串，15 个候选包含：

- `0xff4990`：帮助文本描述编辑复杂度限制可切换，超限作品不参与传播。它支持提示文字存在；没有执行该命令，也未恢复传播检查。
- `0xff4a88`：addDNA；`0x107a13c`：CRG_FirstDNA。只说明名称存在，不能建立 DNA 余额与编辑预算字段的关系。
- `0x108c908`：MaxComplexity，所属读取者未知。

cardName、associatedName、unstructuredName 是不区分大小写匹配 DNA 子串的假命中，已单独标为排除；Scenario/World/Terra 与其他经济 budget 名称也未用作陆地证据。这个有限 ASCII 检查没有命中指定 LOD 表达式，不是全制品不存在 LOD 的结论。

## 独立规格：把经济、可生成性和显示成本分开

以下数值、聚合、事务和 LOD 都是我们的构造规则，不是 Spore 恢复参数。身体仍可保留任意多对足，但必须在自研产品预算内，并保留明确拒绝原因。

`RecipeRevision` 拥有稳定 partId、父/对称关系、部件类型、造型、附着位置和目录版本；成本来自受信部件目录，不能接受客户端自报。`BudgetProfile` 独立保存复杂度点、骨数及几何上界。`DNAAccount` 是经济资源账本。`CompileJob` 拥有不可变输入快照和资源 lease；`ArtifactBundle` 拥有同版本皮肤、绑定姿态、骨架/动画映射和纹理。

本例对实例计费，镜像操作先扩成两个实例；共享数据只扣除编译器明确识别的共享部分，不凭左右对称自动减半。DNA 价格不是骨数乘常数。复杂度是设计计分；骨与几何计数是资源维度。先用保守上界估算，实际编译 manifest 再复核，超估失败保留具体维度和目录版本。

经济变化按 `newCost-oldCost` 结算，删除/替换按本规格允许退回原目录价格。这是可修改的产品规则；需要用绑定的目录版本避免涨价后倒卖。恢复历史配方产生新 revision，并按差价记新账，不恢复旧钱包快照，因此不会抹掉编辑期间的外部 DNA 奖励。

## 独立规格：从拖拽到提交

1. 拖拽创建 candidate 快照，扩展镜像部件后检查 partId 唯一、单根、父存在、无环、类型/附着兼容、有限数值与正尺度。此时不改变权威配方或扣款。
2. 从目录计算 DNA、复杂度、骨及几何上界，同时返回所有失败维度。形变极端值若扩大网格，上界必须包含其影响；不能只在添加部件时验证。
3. 提交带 expectedRevision、actionId 和 candidate digest。配方/资源同一事务重查 revision、差额和预算；拒绝保持所有权威状态。相同 actionId+payload 幂等，复用 ID 换 payload 明确报错。
4. 成功产生新配方 revision 和账本条目；预览与编译均读取这个不可变快照。旧实际游戏身体保持完整，直到新身体可玩。不能在新皮肤上暂接旧绑定姿态。
5. 编译结果复核完整性与实际资源计数；只有输入 key 等于当前 key 才安装。构建失败保留配方、账本和错误，可重试、编辑或撤销；不静默恢复旧钱包。不允许直接进入游戏。

原子事务需要产品存储支持；示例是单进程顺序模型，没有验证数据库持久化、崩溃恢复或并发锁。编辑中取消整个会话时，用会话拥有的账本条目做幂等反向结算、恢复入口配方为新 revision，再取消 owned jobs；其他来源奖励不回滚。

## 独立规格：快速预览与编译一致版本

缓存 key 至少含配方摘要、revision、部件目录版本、生成算法版本、平台/渲染配置、质量及材质参数。快速代理允许减少表面细分，骨架、附着、能力和参考姿态必须来自同一输入；需要改变绑定时创建另一份完整代理 bundle。

连续拖拽合并待排任务，只保留最新 candidate；已执行任务请求取消后仍可能完成，所以回调必须检查 key。每个 job lease 仅释放一次，取消/重复完成不能导致负计数。队列数量、暂存字节、峰值内存与任务时延另作运行指标，不能用 DNA 余额估计。

预览允许展示上一个完整模型并标识正在更新，不能把旧结果伪装成当前 revision。切换质量不改经济成本。完成按钮要求配方合法、当前 bundle 编译成功、当前 manifest 在预算内；提交/保存时间还要复核输入版本。构建任务不能私自发布身体或更改能力。

## 完整构造演算：四手六足

DNA 总可用量 500；本例上限 C=96、骨=50、顶点上界=9000。

| 部件 | 数量 | 每件 DNA | 每件 C | 每件骨 | 每件顶点上界 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 躯干 | 1 | 100 | 12 | 6 | 2400 |
| 足肢 | 6 | 30 | 8 | 4 | 600 |
| 嘴 | 1 | 40 | 6 | 2 | 400 |
| 手臂 | 4 | 25 | 5 | 3 | 350 |
| 眼 | 2 | 5 | 1 | 1 | 100 |

初始 revision42：DNA投入430、余额70，C=88、骨46、顶点上界8000。添加一对足得到 DNA490、C104、骨54、顶点9200：钱足够，但后三维超限，拒绝且余额仍70、revision仍42。添加一个 DNA80/C3/骨0/顶点300 的装甲：DNA510，其他三维91/46/8300合法，仍因缺少10 DNA拒绝。

改为将 arm0（25/5/3/350）换成 wing（35/4/2/400）：新投入440，余额60，C87、骨45、顶点8050，提交 revision43。此时 revision42 的旧构建完成，释放自己的 lease 后丢弃结果。revision43 新皮肤若混入 revision42 bind，明确失败。正确 bundle 才安装。

期间获得外部奖励7，余额67；撤销替换按差价退10，恢复原配方为 revision44，余额77。旧 revision43 的完成/失败回调都不能改变它。取消、重试与撤销不依赖回调成功来保护钱包。

## 独立规格：多足动画 LOD 与权威状态

本例权威运动、支撑足接触、技能时间线和命中代理按固定60Hz维护，视觉动画可用60/20/5Hz更新。六足的 phase、有效肢体集合和支撑判断属于权威身体；远景跳过视觉 IK 或隐藏脚不能删除支撑足。动作命中由权威轨迹/代理与一次性事件决定，不能从低频显示骨骼的偶然接触判定。

视觉升级继续当前 phase，不能重新开始步态或重复攻击事件。显示骨的合并映射独立于能力/命中参与者，断肢先修改权威 body revision，取消失效参与者，再失效视觉缓存。允许 NPC 模拟降频需要另一份有误差与公平性约束的规格，本模块不把它偷换为显示 LOD。

下面只算工作量代理，未计时，也不声称与原作等价。每足视觉 IK 四次、每手臂两次；渲染保持60帧/秒。姿态更新频率与 GPU 绘制频率分开：降低 CPU 动画频率，不会自动降低每帧执行的 GPU 蒙皮。

| 视觉档 | 姿态更新Hz | 顶点/影响上界 | 显示骨 | IK迭代/秒 | 矩阵更新/秒 | 加权顶点乘积/秒 |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| 高 | 60 | 8000/4 | 46 | 1920 | 2760 | 1920000 |
| 中 | 20 | 3000/4 | 32 | 640 | 640 | 720000 |
| 低 | 5 | 900/2 | 18 | 160 | 90 | 108000 |

IK为 `(6×4+4×2)×姿态Hz`；矩阵为 `显示骨×姿态Hz`；顶点为 `顶点×影响×绘制Hz`。插值、上传、剔除、纹理带宽和每帧多 pass 都可能增加成本。权威单足每tick一次接触查询，六足为360查询/秒，不因视觉低档变成30。目录复杂度88和权威骨46也不因远景降低。

真正性能验收另测形态/数量/距离/编辑频率矩阵：CPU动画与构建时延分位数、GPU时间、峰值内存、队列峰值、取消回收时间、命中/支撑一致性。预算参数需在目标硬件测量后校准，不把这里的工作量代理写成毫秒或帧率保证。

## 验证、未知与未做

[独立检查](checks/verify_editor_budget_examples.py)共12项，覆盖完整总量、经济与资源分别拒绝、边界+1、结构/无效输入、替换退款与外部奖励、版本/幂等、旧任务与lease、混版本bundle、失败重试、LOD工作量与权威支撑/命中不变量。它们验证构造规格，不验证游戏运行或生产事务。

实际执行结果：12/12通过；四个交付文件的UTF-8、两个JSON、相对链接、围栏及公开读取行范围检查通过。检查用已有打包Python运行，禁止生成pyc；没有安装运行环境或执行项目构建。

原作已回答：限制种类与候选接口。部分回答：部件代价字段、烘焙管理和LOD入口。未回答：陆地实际属性值、复杂度聚合/硬上限、DNA计费/退款、统一合法性事务、原生缓存/线程、CPU/GPU成本、支撑/命中与显示LOD的关系。

未做：没有解码新的PROP、读取私人存档、启动/附加游戏、安装提供者、执行原生函数、实现完整网格/动画生产系统或跑性能基准。未读取PROP是因为名称尚未绑定到明确陆地资源；不以共用字段填上猜测值。风险是跨编辑器/版本混用，以及把独立算例误认原作阈值；本模块显式保留这些边界。
