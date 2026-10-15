# 四款游戏：替换边界、构建端线索与效果开关

接续[91](91-four-static-other-writers-and-reader-selection.md)。本轮继续收紧静态链：**Tiny Glade 已排除重复插入和通用字节更新作为本缓冲扩容解释；沙堡发行范围仍缺少尾值 `3` 的构建生产者。** 掘地求财接通链接后的单字节属性复制，SUMMERHOUSE 补完两台相机的追加配置及后处理／抗锯齿门。没有运行游戏或目标函数。

| 专题                                                                                         | 本轮新增连接                                                                                                                                                     | 当前缺口                                                                                     |
| -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| [Tiny Glade：替换入口与最终范围](92-tiny-glade-typed-buffer-replacement-and-final-range.md)  | 本类型 `add_new` 重复键进入失败分支；其它 typed 类型的真正替换会销毁旧对象并写回指针。通用字节更新用 raw 记录 `+0x320` 检查目标范围，大数据新建的是暂存 buffer。 | PDB 具名集合未见本类型 replace；类型擦除／其他替换仍未穷尽。槽23四字段和最终容量仍 Unknown。 |
| [沙堡：构建端证据边界](sandcastle/17-tail-build-writer-and-profile.md)                       | 七个明确选定的 SerializedFile 均无 type tree，只有一个 class129；本机 `+0x78/+0x98` 虚槽是空函数，不能解释额外4 B。                                              | 未定位 writer、真实 build profile 或成员归属；需要对应构建的生产侧证据，不能由消费者反推。   |
| [掘地求财：模式属性复制宽度](digging-a-hole/15-property-copy-virtual-target.md)              | 实际描述符 → FEnumProperty／FByteProperty → LinkInternal 设置元素宽度1并置bit30 → InitProperties 的一字节 memcpy。                                               | 默认源最终值、actor 实际构造分支和运行模式仍未观察。                                         |
| [SUMMERHOUSE：追加配置与效果门](summerhouse/16-additional-camera-layout-and-effect-gates.md) | 本作 metadata 的类型／SerializeField 校验后完整消费两对象180 B；主后处理1、遮罩0，两者AA=None；version2跳过旧bool迁移。                                          | 原生相机准入、其它覆盖、实际pass／重绘频率和性能仍 Partial。                                 |

## 优先问题的范围没有被扩大

Tiny Glade 仍有 460 B 初始请求与槽23需要 `[460,480)` 的差额。[89](89-tiny-glade-other-command-writers.md)的23条模板止于槽22。本轮确认更新接口在原大小仍为460时，`offset=460,length=20` 会因480>460进入拒绝分支；暂存分配不会把原目标扩容。另一 typed 类型存在 replace 机制，只能解释容器怎样替换，不能替代本类型的调用证据。因此，后续仍应追同一 BufferState 的指针／vtable 写端和新 raw handle 的描述符；没有这条连接就不宣称最终460或实际越界。

沙堡已知消费链继续成立：对象长916 B，reader从首字节读912 B，余4 B为3。新检查排除了七份已选资源中另有同类对照／未剥离树，以及本机另一个虚槽补读四字节的解释。授权安装目录未提供能绑定该值的构建 writer；`BuildProfile` 的限定字符串阴性也不证明从未使用profile。最有判别力的是同构建 Editor writer与工程配置／实际profile／日志，或同次构建未剥离class129树。其余发行入口尚未全程序穷尽，生产来源继续 Unknown。

## 两个需要修正理解的时间点

掘地求财[14](digging-a-hole/14-other-mode-writers-and-default-copy.md)按构造期flags分析了虚复制条件；本轮补到属性链接期会额外置bit30。正常链接后两字段各复制1 B，Config bit14仍为0，因此普通LoadConfig的旧结论不受影响。构造零值、属性链接、模板复制和renderer读取是不同阶段。

SUMMERHOUSE 的TAA参数虽保存于资源，当前AA模式仍是None；初始化按这些值进入CameraData后，TAA启用门在第一条件即返回false。主相机后处理开关与遮罩相机不同；这说明两条渲染路径的静态配置成本不能混算，但没有给出帧时。旧版本迁移也不会在version2时用尾部两个false覆盖当前UsePipelineSettings选项。

## 证据与验证

新增原始文件位于 ignored `.cache/procedural-modeling/static-replacement-followup/`，分四款保存。正文提供来源坐标、具体条件和演算，必要读取器保存于正式研究目录。复用既有目标身份和授权，未重算摘要；REA native Ghidra 先前阻塞未变，未重试。普通静态输出没有标作 REA Evidence。

本轮检查原安装资源复读、属性标志／复制宽度演算、CIL读取器构建及旧字段输出兼容、非法输入与拒绝覆盖、Python语法、中文UTF-8、相对链接与围栏；沙堡支线已运行仓库 `docs:check`。实际结果及文件范围留在同轮 `focused-validation.json`、`document-validation.json` 和交付回执。**Not Run：** 游戏、附加、目标函数／GPU、私人存档、截图、Unity构建和性能测量；[运行用例](74-runtime-validation-cases.md)保持独立。
