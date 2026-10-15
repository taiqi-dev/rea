# 四款游戏：四个指定静态断点的续查结果

> 本篇下一段入口已在 [78](78-four-static-submission-chains.md)继续：Mixed 提交、墙回调、颜色格式来源与 LOD 写入交错各有新专题；下文保留此前范围。

本轮接续 [73](73-four-game-render-chain-closure.md)，只查 Tiny Glade 纹理句柄、沙堡相机纹理、掘地求财材质槽/处理器，以及 SUMMERHOUSE 过滤/LOD。四组问题均取得新的字段或指令依据；其中默认配置、格式解读和依赖调用次序的结论分别标明。**没有启动或附加游戏，没有读取私人存档，没有执行运行验证。**

| 指定问题 / 专题                                                                       | 本轮静态答案                                                                                                                                                                                   | 结论的精确边界                                                                                                           |
| ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| [Tiny Glade：纹理句柄对应](75-tiny-glade-texture-handle-provenance.md)                | `render_world` 创建的 `gbuffer` 24 B 图资源记录，被用作 `main_pass` 首个颜色附件；经结构复制、deferred 捕获和 binder 实参进入 set 0 / binding 1，恰对应 `solid_light_sun_sky` 的 `gbuffer_tex` | 已接通 CPU 图资源记录到 shader 槽位；图编译后的实际 GPU 对象、别名和帧执行没有观察                                       |
| [沙堡：相机颜色与深度来源](sandcastle/09-camera-color-depth-resource-provenance.md)   | IL2CPP 静态 ID 解到真实属性字面量；A 颜色附件经 `Blit` 写 opaque 副本，B 深度附件经 `CopyTexture` 写 depth 副本，再各自 `SetGlobalTexture`，供水 Shader 587 的 `t1/t2` 读取                    | 资源创建、复制方向、全局 ID 和释放相接；最终相机尺寸/格式、哪些对象实际进入快照及像素结果仍未知                          |
| [掘地求财：材质槽与处理器](digging-a-hole/07-material-slots-and-handler-selection.md) | 煤网格真正的 `StaticMaterials[0].MaterialInterface=-5` 指向 `M_Ores_1-3`；MainLevel 序列化 `bMergeChunks=1`，结合另一位的构造默认值，settings 两位为 `(1,1)`，选择 Mixed handler               | 煤网格是默认材质槽；Mixed 是本关卡序列化值与原生默认值组合下的静态初始选择，不等于已观察实际加载、所有覆盖和整个游玩过程 |
| [SUMMERHOUSE：过滤与 LOD](summerhouse/08-filtering-and-lod-provenance.md)             | inline sampler 原始 `0x54/s0`，按固定格式解读是 Point/Clamp；复制 pass 的 float LOD 0 写入 Core Blitter 共享块，最终自定义材质重载不重写 LOD、沿用当前值                                       | sampler 原始记录与格式解读分开；复制成功且中间无同块 writer 时可推 LOD 0，尚未证明所有相机/feature 的交错与有效 mip      |

## 对前轮结论的具体修正

Tiny Glade 现在超出了“两个 pass 已定位”和“格式相容”：有资源记录创建、复制、捕获、参数偏移以及 binding 号的逐跳身份链。沙堡也超出了“水 Shader 需要同名纹理”：静态 ID 的真实字面量、两种复制 API 及目标标识均已对应。

掘地求财此前接通的 **Basic handler** 是已编入且读过的实现分支；本次实际 MainLevel 配置推导却选择 **Mixed handler**。因此不能把 Basic 的逐 section 路径直接当成本关卡默认执行路径。煤网格也由“材质包依赖”升级为实际默认 slot 0 引用；地形 `VoxelMaterial=M_Landscape`、LOD 3–6 的 `M_Landscape1` 是另一组关卡配置，不能与煤矿槽混为一体。

SUMMERHOUSE 的 LOD 来源已经找到，剩余问题由泛泛的“值未知”缩小为“共享状态的最后一次写入”。仅凭自定义回贴重载没有显式 LOD 参数，既不能推成恒为 0，也不能推成未设置；复制 pass 确实写过 0，但其它 Blitter 重载也能改同一字段。格式解码来源自身的 sampler 恢复限制已在专题明示。

## 静态之后仍可查的窄入口

- **Tiny Glade**：墙类 draw-list item 到具体回调的指针/ID 注册，以及图资源编译/别名规则。这不影响本轮已接通的 G-buffer 记录到 binding 1。
- **沙堡**：相机 `colorFormat` 的最终配置来源和其它场景变体，以及水材质全部 uniform 的所有者。当前两路纹理来源已有答案。
- **掘地求财**：沿本关卡选择的 Mixed handler 补渲染合并与独立碰撞产物的提交链；解析 `M_Ores_1-3` 的材质参数、地形材质接口与组件 override。不要继续把 Basic 当默认。
- **SUMMERHOUSE**：完整相机/feature 的 Blitter writer 交错、低分辨率目标的有效 mip/attachment，以及主体材质 shader。当前已知复制写 0 与回贴继承的关系。

上述是尚未闭合的静态问题；真实像素、帧执行、计时、分配和长期稳定性则属于[74 的运行用例](74-runtime-validation-cases.md)，本次按要求全部 **Not Run**，不将构造演算写成游戏观测。

## 复核与交付范围

新增三个定点 Python 读取器：沙堡的 IL2CPP 字面量槽、掘地求财的选定 unversioned 属性、SUMMERHOUSE 的 inline sampler；另有使用既有 SDK 的离线 CIL 读取器。它们保存在对应专题 `tools/`，不修改游戏、不加载目标代码执行，原始投影和构建产物保存在 ignored `.cache/procedural-modeling/static-chain-followup/`。各专题给出地址、字段、token、输入身份和复现入口；原生分析沿用匹配 PDB 与本地反汇编工具。

完成验证包括实际制品上的定点解析、关键偏移/分支/槽号回读、构造位运算与状态流演算、工具语法/构建、拒绝覆盖等必要失败检查，以及 UTF-8、相对链接和差异空白检查。未以静态解析成功代替运行表现或性能通过。研究用于独立行为规格与设计，不交付原作代码、Shader 二进制或素材作为产品实现。
