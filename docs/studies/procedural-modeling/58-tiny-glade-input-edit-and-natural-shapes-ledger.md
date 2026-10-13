# Tiny Glade 轮廓、编辑、重建与树岩：第十三轮账本

本轮对应用户授权的四个方向：建筑轮廓与墙线、编辑拾取/贴墙/约束、一次编辑的重建顺序、树木与岩石造型。正式路线为：

- [53轮廓输入与Curve](53-tiny-glade-wall-footprint-input-and-curves.md)。
- [54拾取与墙面放置](54-tiny-glade-edit-picking-and-wall-placement.md)。
- [55阶段图与实例上传](55-tiny-glade-edit-rebuild-stages-and-upload.md)。
- [56树木资源与展开](56-tiny-glade-tree-resources-growth-and-canopy.md) → [57岩层位移](57-tiny-glade-rock-mesh-displacement-and-masks.md)。

本轮起始时间工具返回2026-10-13 08:03:11 UTC，对应 **2026-10-13 01:03:11 PDT（America/Los_Angeles）**。继续使用同一可再生成产物根目录，目录日期不代表当前制品发生变化。

## 1. 固定身份与授权

目标仍为`E:/Steam/steamapps/common/Tiny Glade`，匹配制品：

| 制品 | 字节数 | SHA256 |
| --- | --- | --- |
| tiny-glade.exe | 65,612,184 | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| tiny_glade.pdb | 310,513,664 | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |

PDB GUID=`d8d61d04-9e31-5b47-4c4c-44205044422e`、age=1；preferred image base=`0x140000000`。CPU按真实PE节表换算RVA/file offset，shader按原precomp及内嵌module定位。

REA MCP未连接、本地CLI缺少编译运行文件的阻塞未变，沿用DbgHelp、Capstone5.0.3与SPIR-V静态备用流程。没有REA Evidence/session，也没有通过名称冒称恢复原源码。PDB可提供函数/类型名称及源行定位，但本机UDT枚举受限，未获得所需完整私有结构字段，字段解释来自实际读写。

只读游戏制品/包内资源，只编辑研究文档与索引。未启动、附加、改原文件/内存、读私存档、安装、构建、修配置或Git写入。并行分工依据已读取reverse-engineer-anything技能“Plan broader investigations”第6项；根任务整合并独立复核。

## 2. 四个方向的回答程度

| 方向 | 已回答 | 部分/未知 |
| --- | --- | --- |
| 建筑轮廓 | 采样双门槛、raw Curve/权重、弧长比例与错误；选定50轮平滑→RDP .1；圆点数/矩形闭合点；WallState owner替换 | UI全部消息、marker接续、直曲分类、自动闭环、厚度偏移、自交修复 |
| 拾取与约束 | 精确屏幕ray；选定Rapier查询；64B UI hit分派；墙线最近段/弧长投影、周期/范围资格、目的地高度及storage写端；屋顶关联实体/实际UV caller | UI hit producer、40B→64B转换、完整磁吸/merge/尺寸规则、mask枚举及相机约定 |
| 编辑重建 | 墙组状态提交/dirty键；公共墙消息与屋顶消费者；45阶段名称、枚举到阶段图连边；普通砖allocation清旧、64Bpush、typed GPU范围写入口 | 所有函数stage归属、窗口全通知、run条件、deferred屏障、完整上传callback与实机帧时间线 |
| 树木与岩石 | 现成网格/配置/属性；树干/树冠不同展开、风摆/弯曲、冠片扩展及纹理门槛；岩层CPU记录、实际compute绑定、组合mask位移/法线及失活NaN | extract与prim_normals、树ECS发布、源资产离线制作、岩filename caller/普通岩placement、最终renderer及NaN设备行为 |

各方向都有源绑定构造例。树岩的“未见实时拓扑输出”仅限所选模块，不泛化到全产品。阶段配置与运行观察分别保存，未宣称所有四系统已完全还原。

## 3. 本轮明确修正及补充

1. 自由绘墙选定普通支先50轮带权平滑再RDP，历史marker还有不同分支。不能用通用流程替代实际顺序。
2. RDP投影t不clamp，普通墙放置的段投影则clamp。两个距离算法分别说明。
3. 圆N是含首末几何同位端点的点数，分母N−1；单位圆32点/31段，不能写32个互异点。
4. 48中的ui_move_decorator UV getter候选已经经完整caller实际call核对，54更新其事实级别；RT标记到UI hit仍未知。
5. 50的raw stage 0x1D通过全局名称表对应RoofAssemble。55另核真实阶段图连边，实际帧/GPU/deferred缺口不随名称恢复消失。
6. 49的HZB矩阵字段名称校正为ViewConstants.member 1的`clip_to_view`，不是正向投影矩阵；原倒数公式不变。原SPIR-V已有明确MemberName与字段读取，本轮同步正文。
7. 树冠展开f可过冲；反向SmoothStep保留原调用，不作跨设备数值保证。岩层M是岩/水组合mask，不用直接rock.R替代；NaN写入不称已验证硬件discard。

历史账本的检查统计保持当时范围，本轮当前文档和新增/复用证据另行检查。

## 4. 关键定位

| RVA/文件 | 用途 |
| --- | --- |
| `A50E90 / BEDEF0 / BECDB0 / 19A74D0` | 自由绘墙采点到raw Curve |
| `BEC4B0 / 19A9Bxx / B41DC0` | 选定带权平滑与RDP |
| `A85190 / DEFCD0 / DF37E0` | ShapeParameters圆/矩形converter |
| `92E8E0 / B0EB60` | Curve替换与新WallID状态创建 |
| `BF2630 / 14C9450 / 9F9030` | camera ray与选定物理查询 |
| `14CA550 / 148CA40 / 148CFC0 / 14CCB30` | UI hit分派、最近段和目的地 |
| `86D7CD / 14C452A / C3F110 / 86748F` | 放置写端与屋顶UV实际caller |
| `B47F40 / 92F410 / 3B05D0` | 墙组提交与变更键 |
| `93E620 / 15EB150 / 4721A0 / B6DC20` | 全局阶段枚举、名称表与vtable关联 |
| `1A0C5B0 / 17C65A0` | 跨子配置配对及图边/邻接写入 |
| `94C360 / 1A77830 / 1A76130` | 砖allocation回收、64Bpush和范围上传入口 |
| `A32F00 / 1648C80 / B39070` | 预置树、岩层转换与实际compute绑定 |
| tree_trunk/tree_canopy/displace_rocky_terrain precomp | 展开/冠片/纹理及单元位移消费 |

只定位未解释的下一步入口仍保持候选：53的marker/resample、54的merge/吸附/插入helper、56的extract与树发布、57的filename与renderer。

## 5. 原始记录位置

统一可再生成产物根目录：

`C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7`

| 子路径 | 内容 |
| --- | --- |
| `tinyglade-wall-footprint-input/findings.md/json` | 21原生范围、17细范围、七组结论和贯通例 |
| `tinyglade-edit-picking-and-snapping/findings.md/json` | 21原生范围、27细范围、常数/跳表、四例与未知 |
| `tinyglade-edit-rebuild-order/findings.json` | 22本轮范围、三复用范围、14细范围及边界 |
| `tinyglade-edit-rebuild-order/stage-name-table.json` | 45名称、两表/字符串/vtable原字节摘要 |
| `tinyglade-tree-rock-shapes/findings.md/json` | 三原生范围、三shader/九module、17细范围、资源元数据与构造例 |
| `tinyglade-tree-rock-shapes/asset-metadata.json` | 11资源schema/count/hash，无几何提取 |
| `tinyglade-tree-rock-shapes/resource-audit.json` | 全部选定模块的声明/实际读取ID |
| `input-edit-natural-shapes-validation.json` | 根任务独立身份、字节、结构、常数、算术和文档复核 |

正式交付是53–58的解释和独立规格；原字节/listing属于本机可再生成研究产物，不包装成生产代码或分发游戏资产。

## 6. 验证范围

独立重读EXE/PDB全文摘要；去重原生范围并新解码；核细范围长度、offset、摘要和指令边界。shader重读原文件、核module word count/摘要、结构遍历及细范围；包内资源仅重读摘要/元数据。阶段名称表与UI常数独立重读原EXE。

构造例核采点、弧长、平滑/RDP差别、圆/矩形、ray/墙投影/周期、阶段名称与图边参数、64B数量、树展开/弯曲/纹理门槛和岩mask/落地/法线。函数完整线性解码、结构遍历及演算均不构成游戏运行测试。

最终独立验证：**838项通过，0失败**。60份Markdown、351个相对链接有效；本轮70个不同RVA的原生范围共154,199B，摘要及新线性解码一致。另核58段native细范围、111个轮廓claim指令位置、实际call/tail目标、6组UI常数及45个阶段名称/原表。3个shader文件、9个内嵌模块的摘要、word count和边界一致，共结构遍历6,959条SPIR-V指令，另核17段shader细范围和11份资源摘要。

| 组 | 去重范围 | 字节 |
| --- | --- | --- |
| 轮廓输入 | 21 | 42,811 |
| 拾取与贴墙 | 21 | 48,342 |
| 阶段/提交/上传，含三复用范围 | 25 | 55,180 |
| 树与岩层 | 3 | 7,866 |

本轮四组的RVA无重复；部分范围在旧轮已解码，本次重新核原字节，不将它们称为全部新发现。资源仅验证原文件身份/schema/count，没有输出专有几何。838项包含字节/结构/位置和文档核对，不是838个游戏算法运行测试；完整解码与结构遍历也不等于所有路径语义已恢复。

## 7. 未做与风险

未做：真实绘墙/放窗/移动建筑/树岩场景、运行频率/性能、GPU抓帧、物理与RT命中转换、全scheduler/deferred/上传同步、完整renderer、存档/history及资源离线制作；未改REA生产代码，未运行项目构建/实现测试。

风险：输入成功不等于拓扑合法，阶段图不等于实际帧时间线，命中记录布局不能混用，资源加工/展开/位移不等于拓扑创建。浮点门槛、反向SmoothStep和NaN设备行为仍未建立逐位/跨设备保证；未知项保持明确，没有靠名称补算法。
