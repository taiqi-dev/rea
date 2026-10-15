# 四款游戏：碰撞接受、命令槽与渲染目标的静态续查

本轮接续 [78](78-four-static-submission-chains.md)，只检查四个指定断点。掘地求财的碰撞最终门、沙堡的打包色彩空间字段和 SUMMERHOUSE 的目标创建/附件链已有答案；Tiny Glade 已接通基址与槽 16–22，槽 23 的生产者仍未闭合。**游戏启动、附加、私人存档、GPU 抓帧与性能测量均未执行。**

| 指定问题 / 专题                                                                     | 本轮实际结果                                                                                                                                                                                                          | 证据与剩余边界                                                                                                                                   |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| [掘地求财 09：碰撞结果接受门](digging-a-hole/09-collision-result-acceptance.md)     | 完成队列保存 cooker 编号和组件弱引用；消费时要求弱组件有效、当前 cooker 存在、编号相等、任务状态/BodySetup 有效，再执行 Finalize；成功后才交换 BodySetup 并重建物理状态                                               | 静态接受链已答。取消请求和最终拒绝分开；真实调度、是否走异步分支与物理效果未观察                                                                 |
| [Tiny Glade 79：绘制命令槽](79-tiny-glade-draw-command-slot-provenance.md)          | compute 写入与回调读取经同一 typed buffer；两个 CPU 常量块都实际传基址 16，pass2/reset 对应槽 16–19，shadow 对应槽 20–22，prefix 阶段另写槽 16，均为 20 B 命令                                                        | **部分回答**。墙目录 7 个 compute 已有界检查；回调阶段 3 确实选择 23，不能把 shadow 的 `+5=21` 改名为 23，槽 23 的生产者和全部模板初始化仍有缺口 |
| [沙堡 11：色彩空间配置](sandcastle/11-color-space-configuration.md)                 | 精确版本 Release 布局把 PlayerSettings 的 `m_ActiveColorSpace` 定位到对象 `+0xf8`，打包值为 `1=Linear`，有身份字符串及邻接字段验证                                                                                    | 字段层已答；布局消费 912/916 B，末尾四字节显式未解。项目配置不能替代 native `QualitySettings.activeColorSpace` 的实际返回值                      |
| [SUMMERHOUSE 10：mip 与附件](summerhouse/10-low-resolution-mips-and-attachments.md) | level0 主相机 targetTexture 为空；普通 descriptor 初始化 `useMipMap=false/autoGenerateMips=true`，两低分辨率申请继承；分配器将带深度位数的申请转为 Depth。copy/render 写 lowPair，back 写 cameraPair，附件 mipLevel=0 | 序列化配置到创建请求/绑定已答；外部 target、运行替换、具体兼容格式和实际 GPU/mip 数未观察                                                        |

## 关键区别与构造例

**旧碰撞结果靠当前身份检查拒绝。** 旧 A 编号 101 已入队、新 B 编号 102 已写入组件后，A 的节点在 `101 != 102` 处跳过，尚未清 BodySetup。这里依赖的是实际编号相等门，不是“取消 A 曾返回成功”。专题另列空指针、弱引用失效和 Finalize 返回分支。

**命令格式相同仍需要同槽证明。** Tiny Glade 已进一步证实 CPU 基址 16。pass2 的一个构造条件选择槽 19 时，增加的是 `19×20+4=384` 处的 instanceCount，回调读取从 `19×20=380` 开始的整条命令；字段偏移与命令偏移已对应。槽 23 仍不能借这个算例补成已证生产者。

**打包配置与实际生效值分开。** 沙堡现在能明确报告项目打包为 Linear；若设备实际回退 Gamma，已读颜色格式代码仍会走另一转换分支。此回退只是说明条件的构造例，不是本机运行结果。

**采样 LOD、mip 链与附件选择分开。** SUMMERHOUSE 的成功复制可为回贴建立 LOD 0；本轮又证实默认主相机路径不开启 mip 链，并以附件 mip 0 绑定。autoGenerateMips=true 单独存在，不等于 useMipMap=true。低分辨率深度申请经分配器改选 Depth，也不能只看游戏局部 descriptor 曾有 HDR 格式就当成颜色纹理。

## 复核与仍可静态追的窄点

新证据保存在 ignored `.cache/procedural-modeling/static-resource-followup/`。新增两个有界资源读取器分别解释相机 Release 布局和 PlayerSettings；CIL 读取器增加声明字段常量与参数名，不加载或执行目标程序集。精确版本 TypeTreeDumps 是外部**布局参考**，实际值仍来自本地对象；未计算参考摘要或安装新软件。

验证覆盖原生编号比较/提交顺序、CPU 常量到 SPIR-V 字段与 buffer、资源字段/长度/引用、mip 位运算和附件实参，以及读取器兼容/拒绝覆盖/错误输入、构建、UTF-8 和链接检查。PlayerSettings 未映射尾部没有被当作 padding 吞掉，Tiny Glade 槽 23 没有由命名或猜测补完。

后续静态入口主要是 Tiny Glade 槽 23 的模板/其它生产者与内部阶段语义、沙堡 PlayerSettings 的末尾四字节、其它场景和运行替换代码，以及未展开的主体 shader。它们不改变本轮已证的局部链；[74 的运行用例](74-runtime-validation-cases.md)继续全部 **Not Run**。产出用于独立行为规格，不交付原作代码或素材作为产品实现。
