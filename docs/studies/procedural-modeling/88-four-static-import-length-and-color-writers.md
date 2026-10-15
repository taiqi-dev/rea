# 四款游戏：导入缓冲、对象长度门与顶点色写端

接续[86](86-four-static-bucket-loader-and-material-owners.md)。本轮四款各新增专题，重点补实际写入/分配与外层检查：**Tiny Glade 的导入分派保留原raw handle，没有在此扩容；沙堡通用直接读取分支会核对对象消费长度；SUMMERHOUSE 找到实际墙块的顶点alpha写端；掘地求财查清普通配置加载的属性门。** 所有结果均为静态证据，运行验证 **Not Run**。

| 专题                                                                                            | 新增的确定连接                                                                                                            | 仍未回答的部分                                                                                                                   |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| [Tiny Glade：命令backing与后续写端](87-tiny-glade-final-command-backing-and-writers.md)         | 同typed写租约→raw handle图导入；新记录tag3经实际跳转表进入保留原handle的注册分支。资源容器经GraphApi和compile接到注册器。 | 槽23四个非计数字段的生产者、完整生命周期的其他资源写入、最终逻辑范围是否覆盖480 B。不能再用此导入分支或图记录Vec增长当扩容证明。 |
| [沙堡：三值生产与SerializedFile长度门](sandcastle/15-tail-production-and-serialized-loader.md)  | 通用直接分支对对象调用vtable+0x90，返回后比较读量与记录长度；上下文+0x48的界限来自对象终点并受缓冲可用量收紧。            | class129实际是否走此直接分支、诊断后的实际效果、构建端是谁生产末尾3。另一类型树分支尚须区分，不能宣称本作已报错。                |
| [掘地求财：属性标志与配置加载门](digging-a-hole/13-material-property-flags-and-config-gates.md) | MaterialConfig/RenderType的本作描述符与构造flags不含Config；同EXE普通LoadConfig按bit14跳过该属性。                        | 其他CDO/基类初始化、反射标志修改、特殊配置解析或游戏脚本写入仍未穷尽；无同名setter不等于只读。                                   |
| [SUMMERHOUSE：顶点alpha与局部初始化](summerhouse/14-vertex-color-mask-and-local-updates.md)     | 实际墙块Mesh427有412个alpha=255的顶点；Maskable.Awake将子网格alpha写0，接到Shader622的遮罩裁剪输入。                      | 实例是否出现、生命周期先后、当前shader变体/像素、其他写入渠道和遮罩相机重绘频率。                                                |

## 两个优先问题的当前结论

Tiny Glade 初始请求仍是23×20=460 B，槽23完整命令需要 `[460,480)`。本轮已把tag3导入状态与注册器精确分派接上：它保留原raw handle，不经过通用buffer池化/新建分支。因此这一段并没有解释新增20 B，也没有解释 `count/firstIndex/vertexOffset/firstInstance` 的模板。整个生命周期中的其他替换/更新尚未穷尽，不能从这一段无扩容断言最终只有460 B或运行越界。下一步有效目标仍是同typed key的其他CPU/GPU写端与记录的其它变化。

沙堡额外四字节仍位于class129对象内部。现在可以排除“该通用直接分支无条件把余量视为padding”的解释：reader返回后确有消费量与对象记录长度比较。若class129进此分支，912/916会进入不匹配处理；但对象factory到本次加载分支的连接和另一类型树支路尚未闭合。末尾3的构建producer仍未知，不能改名为allowed、版本位或可丢弃填充。

## 美术表现与局部成本的新信息

SUMMERHOUSE 的包内顶点alpha=1与初始化后alpha=0会给同一遮罩公式不同输入。新专题用具体墙块的根组件、子MeshFilter、Mesh COLOR0和三槽材质引用把这条链串起；其中Awake写端遍历的是该实例子网格，不能称为每帧整栋建筑重建。透明与裁剪的实际像素、GPU开销仍需另行运行验证。

掘地求财则把“配置可能覆盖默认值”拆得更精确：以已读构造flags进入普通LoadConfig时，这两个属性被跳过；其他主动写入仍可能存在。六个已解包name表没有同名入口，只作有界名称覆盖记录，不扩大成全游戏无写者证明。

## 证据、验证与交付边界

新原始记录统一位于 ignored `.cache/procedural-modeling/static-final-followup/`，按游戏分目录。正式目录只保存解释和必要读取工具；沿用既有版本与授权，未重算摘要，未启动/附加游戏、执行目标函数/GPU、读取私人存档或安装软件。REA原生分析此前的超时状态未变，本轮使用已建立的只读静态路线。

本轮核对了Tiny Glade实际跳转表及39条新增定点指令、沙堡对象上下文和长度门、掘地求财两个描述符及原生bit门、SUMMERHOUSE完整Mesh布局和CIL写端；复读结果、非法输入/拒绝覆盖与Python语法另作定点检查。各专题分别标记Answered、Partial和Unknown，文档引用、UTF-8、围栏/空白及仓库hooks另行验证。这些检查不构成游戏效果、稳定帧时或运行性能通过。

运行问题继续留在[独立运行验证用例](74-runtime-validation-cases.md)，本轮未执行。
