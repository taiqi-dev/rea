# Tiny Glade 建筑资产与实际拼装：第十五轮证据账本

本轮对应用户问题：房子按什么建模、窗是否独立、窗怎样改变墙、灯具怎样接入、接缝属于哪种模型/材质，以及自研造房游戏应怎样组织资产。

- [64资产与建筑状态](64-tiny-glade-building-kit-and-asset-assembly.md)：实际JSON部件、局部叠合预览、包内起始小屋的参数组成。
- [65窗洞与灯具](65-tiny-glade-window-holes-and-lantern-components.md)：模型请求、精细洞资源层、挂墙、无窗式洞、实际光源与发光。
- [66接缝与独立规格](66-tiny-glade-seams-and-independent-building-kit-spec.md)：砖/梁实例、屋瓦裁剪与自研资产清单/所有权。

时间工具起始返回 **2026-10-14 04:43:22 UTC = 2026-10-13 21:43:22 PDT（America/Los_Angeles）**。跨UTC日期按该具体Pacific时间解释，不以旧产物目录名当当前日期。

## 1. 固定目标和方法

| 制品 | 大小 | SHA256 |
| --- | ---: | --- |
| tiny-glade.exe | 65,612,184B | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| tiny_glade.pdb | 310,513,664B | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |

路径仍为`E:/Steam/steamapps/common/Tiny Glade`，PDB GUID/age和preferred image base沿用既定身份。原生RVA通过真实PE节表转换；shader偏移是原precomp文件偏移，不能当EXE地址。

REA MCP未连接、本地CLI缺编译runtime的既有阻塞未变。继续DbgHelp、Capstone5.0.3、JSON/RON原资源读取和SPIR-V结构/局部指令分析，没有REA Evidence/session。函数名只给入口；实际参数、字段、条件、调用与原字节支持结论。

本轮原制品只读，没有启动、附加、修改原文件/内存、私存档读取、安装、构建、配置或Git写入。新增的是研究说明、统计、字节记录和本机诊断投影。包内starting-builds样例属于已选发行目录资源；不将其误报为用户存档或当前实机观察。

## 2. 原问题回答程度

| 问题 | 已确认 | 部分/未知 |
| --- | --- | --- |
| 按什么建模 | 独立砖/板/瓦/梁/窗/灯网格，自定义属性，RON子类；样例存墙轮廓/屋顶/装饰参数 | 原DCC软件和导出工具、全部最终renderer绑定 |
| 窗独立吗 | cottage主窗与窗格/玻璃、楣梁，gothic条件帽各有实际模型请求 | 普通窗台主体、所有corner/dormer、完整最终mesh handle桥 |
| 放窗动态挖洞吗 | 粗墙洞、精细cut、CPU砖板消费者；精细SDF层0/3显式加载组件 | 通用整栋3D Boolean、完整室内内腔、全部最终边界 |
| 灯怎样拼 | 主体/inside共用builder变换；独立light slot与emissive实例；两窗洞数组保持空 | 碰撞文件全部key绑定、支撑变形、完整ECS发布与照明/阴影 |
| 中间接缝是谁 | 独立接缝候选，写BrickTransformSsbo/WoodenPlankSsbo；屋瓦有plane裁剪 | 砖exact drawlist、所有专用ridge/eaves/contact资产、全局封口 |
| 我们自己怎样做 | 已交付独立资产契约、逻辑owner/派生产物规格和优先级 | 没有编写或适配用户产品，不冒称已实现 |

## 3. 新连接与修正

1. 以前17已确认SDF烘焙，但层号资产组合未知；本輪补18层显式路径表。shape0用cottage主窗+glass，shape3用gothic主框+glass+hat_full，不是仅collision_outline。gothic视觉帽仍按条件选，不能和固定SDF组合混用。
2. 原始glass资源是混合几何：cottage1x1只有6/1056个顶点is_glass=1。文件名不代表整份mesh都是透明玻璃。
3. 灯inside是灯体内部独立发光部分。三份原inside只有Position/Normal/Color，无UV；Uber组配置声明追加UV是另一层，不能写成原资源已有UV或保证发光组同样追加。
4. 灯builder保存的模型变换和后续蓝图Y+0.5基准分开；没有把它重复叠加到模型位置。
5. 接缝额外布局写共享实例类型，尚不等于完整源网格/材质相同。普通brick的专用drawlist仍未知。
6. root首次RON文本搜索截断到前100项，因此没有将“未显示木板”保留为缺映射结论；完整所选配置明确WoodenPlank/木山墙两组引用同三网格。
7. 根核验发现灯具terrain support的细范围末端84A028落在指令内部，已扩至84A02A，333B修为335B并重算摘要；其余11段native和6段shader细范围边界独立复核通过。修正记录和原/新hash保留在本机证据目录，不将旧范围冒称完整指令。

## 4. 原资源与预览身份

`assets/nani_meshes.ron`：16,124B，SHA256=`fefe20932f8112d6b6628ff6a1f8e75836b07ef92e219ac93298c9c3a22cda16`。

包内01-cottage：

| 文件 | 字节数 | SHA256 / 解释 |
| --- | ---: | --- |
| history.json | 44,454 | `6cf9a3d2d30cf46ff0b9cee48585bd4a7121d7caee81c7bb4b9c245be0dc9d97`；Version18，78个edit_chain项 |
| 5476761123159047511.snapshot | 363,910 | `bb08992dbd869244cdb958048cf4919518f92baaa642d508702df3721964a0fc`；只解析偏移16的4752B JSON，Version2 |

选定JSON元数据有3墙、3屋顶、4装饰；它是历史schema的包内例子，不证明当前全存档schema或所有运行状态。剩余二进制数据未作为网格/完整栅格解析。

静态部件预览直接读取四份原网格；保存的是本机诊断PNG，没有导出原顶点/索引为生产资产。未应用原shader/纹理；玻璃示意透明。这只能说明局部几何与原点关系，CPU实际部件配对另有独立证据。

## 5. 本机证据记录

共同根目录：`C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7`。

| 子目录 | 内容 |
| --- | --- |
| tinyglade-building-kit-overview | selected-assets、包内样例摘要、asset-preview及PNG |
| tinyglade-building-kit-windows | findings、16资源元数据、18层表/原字符串、native manifest与17细范围 |
| tinyglade-building-kit-lanterns | findings、17资产/配置、9个native与12细范围、4 shader模块/6细范围 |
| tinyglade-building-kit-seams | findings、9资产/3subset、20 native与9细范围、格式数据原字节 |

先前16–19、37、39、42–43、60的既定结论分别引用，旧轮数量保持其历史覆盖。新统计不把所有旧模块算作重新完整恢复。

## 6. 根核验

根任务核验记录为本机`building-kit-assembly-validation.json`。覆盖原制品摘要、fresh native重解码/范围hash、关键细范围/实际call、模型JSON索引/属性/包络、RON所选子类、SDF路径表/字串、shader包/模块/细范围、包内snapshot范围和独立算术、PNG身份及正式文档链接/围栏。

最终核验通过**3434项、失败0项**，具体覆盖：

| 检查对象 | 本轮实际覆盖 |
| --- | --- |
| 原制品身份 | EXE/PDB完整摘要，Capstone5.0.3 |
| native原范围 | 窗10段/41898B、灯9段/25396B、接缝20段/73532B；去重38段/138405B |
| native细范围与调用 | 38段起止边界/原字节摘要，10个选定实际call |
| 模型与配置 | 43份去重JSON重新核索引、属性、数量/包络；RON完整摘要、3所选subset块/顺序及灯引用行 |
| 窗SDF与资源绑定 | 67个字符串/常量原字节范围、18层count/ptr及逐条path pointer |
| 灯shader | 1包、4模块/37788B/1838条结构指令、6个细范围；另核3个窗shader包摘要，未新增其语义解码 |
| 包内样例 | history和snapshot摘要、4752B有界JSON、版本/数量及3墙/3屋顶/4装饰语义字段 |
| 诊断图 | 1800×1210 PNG身份及4份来源摘要/计数 |
| 文档与演算 | 69份Markdown UTF-8/围栏、421个相对链接；粗洞、灯槽/发光、接缝及独立owner演算 |

数字中的“检查项”包括逐指令结构检查和逐资源字段检查，不等于3434个已恢复算法。native统计含选定旧范围复用及一份跨组重复loader，去重后不重复计数。字节、结构和例子检查不能证明运行可达、所有shader语义、完整帧时间线或画面等价。

## 7. 未做与风险

未做：游戏运行、模型在真实编辑场景中的最终拼装、逐帧/性能检查、私人存档和工具安装/REA项目构建；没有自研生产代码或原资产复用。原因是沿用发行制品静态调查，诊断投影和独立规格可回答资产职责，但不能替代实机行为。

风险：材质子类与网格文件不是一一对应；坐标/原点对齐不等于所有最终变形；fragment取消不产生已证封口；历史样例不等于当前保存输出；共享实例格式不证明相同draw资源。文档明确区分原作事实、局部推导、自研建议和未知。
