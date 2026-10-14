# Tiny Glade：装饰协调、墙厚、树加工与历史恢复证据账本

第十四轮对应用户授权的四项续查，阅读路线：

1. [59：窗户邻居协调与等级合并](59-tiny-glade-decoration-snapping-and-merging.md)。
2. [60：墙厚、轮廓与转角收口](60-tiny-glade-wall-thickness-and-contour-joints.md)。
3. [61：树木网格加工与实例发布](61-tiny-glade-tree-mesh-processing-and-publication.md)。
4. [62：历史、快照与恢复重建](62-tiny-glade-history-snapshots-and-regeneration.md)。

起始时间工具返回2026-10-13 09:54:50 UTC，即 **2026-10-13 02:54:50 PDT（America/Los_Angeles）**。本机产物目录沿用前轮固定目录；其名称日期不表示制品更新。

## 1. 身份、方法与授权

目标仍是 `E:/Steam/steamapps/common/Tiny Glade`，匹配制品：

| 制品 | 字节数 | SHA256 |
| --- | --- | --- |
| tiny-glade.exe | 65,612,184 | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| tiny_glade.pdb | 310,513,664 | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |

PDB GUID=`d8d61d04-9e31-5b47-4c4c-44205044422e`、age=1；preferred image base=`0x140000000`。RVA依据真实PE节表转换。PDB范围给出解码边界，完整线性解码不证明每条指令可达；符号同地址别名和函数内源行只辅助定位，实际读写、参数和分支才支持行为。

REA MCP未连接、本地CLI缺编译运行文件的阻塞没有变化，继续DbgHelp及Capstone5.0.3静态备用流程，没有伪造REA Evidence或session。本轮没有安装、构建、修配置、Git写入、启动游戏、附加进程、修改原制品/内存或读取私人存档；只新增研究文档、索引与可再生成证据。

并行分工依据已读reverse-engineer-anything技能“Plan broader investigations”第6项，根任务研究历史、整合并复核其他三方向。原生调查保持只读，不把恢复逻辑或目标资源交付为生产实现。

## 2. 回答程度

| 用户问题 | 本轮确认 | 仍部分或未知 |
| --- | --- | --- |
| 窗户/装饰自动协调 | 墙内候选、周期距离、类型和rank上限、查新collision尺寸、朝输入侧移中心、第三者排除、评分、目标ID/change/modified写端 | 全部UI开关、自由resize、一般磁吸、移动两持久对象的历史清理、全局避让与帧顺序 |
| 墙厚与轮廓收口 | 选定premade木墙外轮廓、墙坐标到世界坐标、普通砖深度/法线轴、短片段筛选、选定转角砖策略 | 任意自由墙统一offset polygon、signed凹凸分类、XZ自交修复、窄缝填补、全部样式 |
| 树资源加工 | 干冠颜色筛选、顶点/索引压缩重映射、冠片分组/中心/法线、默认/保留属性、Prefab实例创建与同索引CPU staging | 所有加工选项、资源离线作者算法、processed mesh到atlas全部关联、最终GPU transfer/绘制时序 |
| 历史与恢复 | 非空操作聚合、未来记录裁剪、编辑JSON/装饰楼梯差异、选定墙回放写端、快照字段/最近选择、墙和装饰ID/counter恢复 | 完整撤销重做游标、全部命令调度/反向回放、pending resolve/GC、磁盘完成/崩溃恢复、全部视觉及随机等价性 |

每篇含有源绑定构造演算，输入中的示例尺寸、对象ID和场景是明确选择的参数，不能当作发行版默认配置。算例验证规则及算术，不执行原作函数。

## 3. 相对前轮补齐与解释限定

- [54](54-tiny-glade-edit-picking-and-wall-placement.md)的邻居/合并候选现已追到具体规则与change写端。合并是等级资源替换，不是直接宽度相加；失败的proposal不等于全局禁止普通放置。
- [53](53-tiny-glade-wall-footprint-input-and-curves.md)的Curve仍是中心线输入。本轮厚度来自不同生产路径，不能自动升级为统一二维offset、自交修复或网格布尔算法。
- [56](56-tiny-glade-tree-resources-growth-and-canopy.md)的extract/prim_normals缺口由CPU producer补齐。干冠筛选不是运行时生成整棵树的分枝拓扑；已有age/appear_pos和CPU默认来源须分开。
- [55](55-tiny-glade-edit-rebuild-stages-and-upload.md)的History阶段名称现有实际记录/回放/保存入口支持。阶段图、编辑聚合、请求入队、磁盘完成和GPU完成仍是不同证据层。
- [44](44-tiny-glade-stable-randomness.md)的稳定身份增加读档/带ID创建证据，但没有把对象ID稳定等同于每块砖、每片瓦或实例槽位稳定。

## 4. 可再生成本机记录

共同根目录：`C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7`。

| 子目录 | 记录与用途 |
| --- | --- |
| `tinyglade-decoration-coordination` | findings.md/json、native范围、28段细证据、caller复用关系、验证 |
| `tinyglade-wall-thickness-and-joints` | 实际几何入口/调用、native范围、厚度/转角常数、构造演算和未知 |
| `tinyglade-tree-mesh-processors` | CPU加工/发布入口、资源属性统计、原制品摘要、细范围与实例staging |
| `tinyglade-history-and-save` | 41个native范围、28段细范围、28个实际读key、调用候选与历史/ID算例 |

未把原始网格或恢复代码复制进正式文档。表内记录是本地静态备用证据，跨机器须重新获取匹配制品再生成；本文已包含主要算法和限制，不以这些本机路径作为唯一解释。

## 5. 核验范围

根任务核验记录在本机根目录的 `coordination-contours-trees-history-validation.json`，包含原制品摘要、native范围重解码/摘要、细范围边界和原字节、选定实际调用、属性/资源摘要、构造算术以及正式Markdown链接/围栏。

本轮根任务复核通过 **782项、0失败**。具体覆盖为：

| 组别 | 不同RVA范围 | 字节数 |
| --- | ---: | ---: |
| 装饰协调本轮范围 | 17 | 9,274 |
| 装饰链复用的三个caller | 3 | 26,624 |
| 墙厚/转角（含复用外层） | 24 | 82,301 |
| 树加工/发布 | 15 | 42,213 |
| 历史/保存/恢复 | 41 | 146,522 |
| 合计去重 | 100 | 306,934 |

另外核对89段native细范围、5组装饰常数字节、28个实际读取key与调用位置、3份树资源身份；重新读取原资源计算颜色筛选和f32位模式分组，得到与报告一致的计数。65份正式Markdown UTF-8/围栏及385个相对链接通过。四篇专题均有构造例和未做/风险说明。

核验含字节身份、重新线性解码、选定实际call、细范围边界、属性统计和独立算术。没有执行100个游戏函数，也没有把782项称为运行测试；函数数量与检查项数量只表示选定覆盖，不能用于宣称整款游戏已完整还原。

## 6. 未做与风险

未做：没有运行游戏、实机编辑、截图/逐帧比较、撤销/保存/读档操作、GPU或性能测量，也没有REA项目构建/测试。原因是本次沿用发行制品静态研究范围，现有材料能回答局部算法，不能冒称运行观察。

风险：泛型别名、原始tag、不同存储布局及中间结果容易被扩大解释；本轮分别保留资格、数据所有者、状态写端和未知。普通合并失败、短砖跳过、快照入队或CPU staging都不是最终画面的直接证明。仍需运行证据的问题必须另选最小场景，不擅自扩大到私人存档或原制品修改。
