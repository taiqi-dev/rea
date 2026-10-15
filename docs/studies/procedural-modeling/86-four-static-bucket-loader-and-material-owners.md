# 四款游戏：墙组入桶、加载器边界与材质消费

后续[88](88-four-static-import-length-and-color-writers.md)补上导入分派、通用对象长度门、普通配置属性门与实际顶点alpha写端；本篇保留其当轮范围。

本轮承接[84](84-four-static-readers-and-render-filters.md)，四款各新增一篇专题。**Tiny Glade 已明确墙组进入首桶的组件条件，SUMMERHOUSE 已接通选定材质的遮罩消费；沙堡找到了实际 PlayerSettings 虚表和类注册，但末尾三值的构建生产者仍未知。** 全部为静态调查，运行验证 **Not Run**。

| 专题                                                                                              | 本轮接通的连接                                                                                                                                                                                                            | 尚未闭合的边                                                                                                                                  |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| [Tiny Glade：墙组首桶和写租约](85-tiny-glade-wall-bucket-and-command-writes.md)                   | 同一个 DrawLists 经 build/sort、compile 闭包到 shadow；缺少 `DontCastShadow` 的匹配实体进第一桶。墙初始 bundle 含 `Transform` 且不含该排除标记，槽23调用路径静态可达。另接通 typed `finish_write → export` 的图资源登记。 | 同一命令缓冲四个非计数字段的后续生产、逻辑容量达到480 B及最终提交。桶 Vec 的增长不能替代 GPU 命令缓冲扩容证据；export 也不是字段模板 writer。 |
| [沙堡：尾部3的 owner 与 loader 边界](sandcastle/14-player-settings-tail-owner-and-loader.md)      | class129 注册描述符 → factory → native对象构造 → 真虚表 `0x181eb1a30`；已知二进制reader位于 `+0x90`。相邻typed回调末项只见成员自拷贝，没有把末尾3直接读入allowed。                                                        | 通用SerializedFile loader对该槽的实际调用和对象长度门；构建侧为什么生成对象 `+0x390=3`。912/916 B差额继续保留，不能称padding或无用。          |
| [掘地求财：初始材质权威与后续取值](digging-a-hole/12-initial-material-authority-and-overrides.md) | MainLevel actor的template精确指向原生 `Default__VoxelWorld`，不是游戏Blueprint子类。BeginPlay→CreateWorld以及RecreateRender在创建renderer时按当时world字段重新取值。                                                      | 引擎基类/CDO配置和其他脚本写入未穷尽；不能把原生ctor默认值当成运行中绝对常量。                                                                |
| [SUMMERHOUSE：全局遮罩到材质采样](summerhouse/13-global-mask-material-consumers.md)               | Shader622逐变体参数到实际采样槽：12个前向fragment变体中8个消费全局遮罩；透明变体写alpha，Alpha Test变体提前裁剪。动画后世界坐标和材质阈值均对应到常量缓冲。                                                               | 其余shader逐变体覆盖、实际关键词、mesh颜色写端、遮罩重绘频率和可见像素。公共名称表中缺项不能证明全部程序未使用。                              |

## 本轮收窄的两处误读

Tiny Glade 的首桶资格已不是没有入口的未知：查询的可选第8列是 `Option<&DontCastShadow>`，缺席就追加桶0；墙初始bundle也有同一TypeId的 `Transform`。但 ECS 命令是否生效、实体是否存活、后来是否增加排除标记仍是运行条件，不能写成每帧必定提交槽23。初始460 B与槽23所需480 B仍是明确差额，尚无最终 backing 长度证据，不能直接定性越界。

沙堡先前从内部三槽附近找表头的办法遗漏了真正入口。构造函数把 `0x181eb1a30` 写入对象首指针，注册factory又直接接到该构造路径，才确定了reader的虚表槽位。相邻另一typed回调的整体职责仍未知，其余虚接口可能有间接作用；本轮只排除末项的直接四字节读取解释。对象末尾三值的生产来源与外层处理仍 **Partial**，没有借类型名或版本树填上答案。

## 美术与成本的新连接

SUMMERHOUSE 的材质消费补上了辅助相机与主表面之间的关键桥：MaskingMap的灰度Z通过全局纹理进入部分材质变体，用世界深度差和容差控制透明/裁剪。它使这条显示路径无需在消费shader中重建墙面网格，但不能推出游戏编辑完全没有网格更新。Alpha Test先裁剪、透明变体后部写alpha是静态执行顺序差异，实际节省与额外开销仍需运行测量。

掘地求财的模式取值边界则说明：关卡实例缺少MaterialConfig序列化值并不代表它没有初始来源；原生CDO提供默认来源，而renderer创建/重建时会重新采样world状态。现有证据支持条件化的单材质链，仍没有运行中的模式切换事实。

## 证据与验证

原始输出统一在 ignored `.cache/procedural-modeling/static-owner-followup/`，按四款拆目录；正式目录只保留解释和必要读取工具。没有启动或附加游戏，没有执行目标原生函数或GPU程序，没有读取私人存档、安装软件或重新计算摘要。既有身份、旧断点与授权继续沿用。

验证包含原生定点指令/PDB/只读类型常量比对、沙堡factory到虚表的直接边与本地reader长度边界、掘地求财包内模板引用、SUMMERHOUSE250个Material和71个Shader完整字段消费，以及选定Shader的14份DXBC和14份逐变体参数记录。旧Mask工具重跑与历史投影相同；新读取器的错误输入与拒绝覆盖边界另记 `summerhouse/focused-validation.json`。文档UTF-8、相对链接、围栏/空白、Python语法和Git hooks分别核对；这些是静态证据验证，不是游戏效果或性能通过。

后续静态工作的最小入口仍在各专题末尾：Tiny Glade同一typed资源的四字段写端/backing分配，沙堡generic loader的实际虚调用/返回长度门及构建writer，掘地求财CDO或world的其他写端，SUMMERHOUSE其它shader的逐变体与颜色生产。运行验证继续单独留在[运行验证用例](74-runtime-validation-cases.md)，本轮未做。
