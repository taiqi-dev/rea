# 四款游戏：二进制读取、提交条件与渲染过滤续查

本轮继续[82](82-four-static-initialization-and-tail.md)的具体断点，四款各补一篇。**沙堡已将零值槽接到本地 reader 的 allowedHttpConnections；Tiny Glade 已查清阶段3的 shadow 传参和一个只读命令转换节点，但槽23的后续模板与扩容仍未找到。** 所有结论保持静态范围，游戏及其原生函数、GPU、截图写入、私人存档与性能测量均为 **Not Run**。

| 专题                                                                                          | 新增的确定连接                                                                                                                                                                        | 保留的未知                                                                                                                                 |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| [Tiny Glade：槽23写入、容量与shadow条件](83-tiny-glade-slot23-write-growth-and-submission.md) | 第二个shadow项的索引1在closure内转为阶段3；同一DrawLists第一桶切片传给render_bucket。命令表首项还接到draw_indexed_indirect_to_dispatch，其shader只读instanceCount，输出另一args缓冲。 | 首桶是否含合格墙组1；同一命令缓冲四个非计数字段的后续写入、逻辑扩容及最终有效提交。不能由初始460B请求定性运行越界。                        |
| [沙堡：尾槽的本地reader对应](sandcastle/13-player-settings-exact-tail-mapping.md)             | 字段登记函数经唯一直接caller接到.rdata回调表，再到实际二进制reader；它把对象+0x38c的0写入allowedHttpConnections内存成员，游标到+0x390后返回。                                         | +0x390的3仍在916B对象内，但此reader未消费；构建writer的生产成员、更外层处理及实际运行值未知。它不能再被直接当作本地reader读出的allowed=3。 |
| [掘地求财：chunk材质模式生产](digging-a-hole/11-chunk-material-mode-selection.md)             | 关卡属性未覆盖MaterialConfig/RenderType，结合ctor与settings复制，正常Marching Cube路径将模式编码为mesh首字节1，消费者进入单材质支路。另追到插件索引字节、键和section分组链。          | archetype、加载/后续覆盖、实际chunk/section数量及其它非零模式的完整混合规则。                                                              |
| [SUMMERHOUSE：相机过滤与遮罩数据](summerhouse/12-mask-camera-filter-and-shader-data.md)       | 主相机759与feature471交集215，排除层8；遮罩相机只选层8。115个层8 prefab Renderer均用Mask材质；完整pass索引接到DXBC，颜色程序写saturate((worldZ-min)/(max-min))的灰度。                | renderer其余过滤、最终材质消费遮罩、动态覆盖和实际可见集合。静态prefab计数不是draw/帧时。                                                  |

## 对前轮结论的具体收窄

沙堡[12](sandcastle/12-player-settings-tail-field.md)的两种原始字节假说，现在对**本地读取语义**已有区分：零槽是allowed的输入，三值是未消费尾载荷。构建侧为什么多写四字节仍未解释，所以原[PlayerSettings读取器](sandcastle/tools/player_color_space_probe.py)继续返回schema Partial，不能为了命名尾值而忽略它。

SUMMERHOUSE[05](summerhouse/05-materials-pixelization-and-camera.md)曾按feature层掩码判断Mask也被覆盖；相机层筛选在前，主相机已排除它。新的专题同时修正旧工具将ReceiveShadows字节当成Enabled的位置错误；当前634个对象两字节恰好同值，旧完整投影逐项不变。原资产计数保留，涉及主相机重绘集合的推导以新交集为准。

Tiny Glade的阶段3已有上游生产来源，不能再只列“阶段是否可能出现”作为无入口未知。剩余重点是墙条目进入实际首桶的条件，以及typed资源的四字段写端和backing buffer长度；已查的转换节点不是这些字段的生产者。[83](83-tiny-glade-slot23-write-growth-and-submission.md)列明主函数整表传出与直接读取的具体地址，可从尚未闭合的写端继续。

## 原始记录与验证

新raw统一进入ignored `.cache/procedural-modeling/static-slot-followup/`，来源、地址、对象偏移和可复算命令分别写在四个专题中。正式目录只保存研究解释和必要读取工具，没有复制目标代码或资产作为自研实现，也没有新增分析软件。

已核对原生定点指令、SPIR-V只读/写入资源、二进制reader的游标/内存成员、关卡模式演算，以及SUMMERHOUSE每个选定对象的完整schema消费、Shader621的5个pass、15个program记录和两份DXBC。SUMMERHOUSE旧工具修正后完整投影与历史输出相等；错误版本、截断/非法标量和输出覆盖的失败边界另作定点检查。本轮13份Markdown的UTF-8、196个相对链接、围栏/空白与5份Python语法检查通过，记录在 `static-slot-followup/document-validation.json`；仓库提交/推送另执行现有hooks。不将这些检查称为游戏运行通过。
