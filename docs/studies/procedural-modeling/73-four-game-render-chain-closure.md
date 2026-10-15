# 四款游戏：材质、渲染与局部更新的续查账本

本轮承接[71 的缺口](71-four-game-art-updates-and-performance.md)，优先补实际资源身份、CPU 调用与产物接收点。新增四款专题，另把[需要运行的用例](74-runtime-validation-cases.md)独立成页。**静态未闭合不等于只能运行才能查；运行 Not Run 也不推翻已经读出的代码和资源链。** 本轮没有启动、附加或改写游戏，没有读取私人存档。

## 新增专题和实际进展

| 游戏 / 阅读入口                                                                                       | 本轮新增静态连接                                                                                                                    | 仍未闭合的静态问题                                                                                  | 必须取得运行观察的问题                                              |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| [SUMMERHOUSE 07：回贴、深度与局部修改](summerhouse/07-pixel-blit-depth-and-local-render-route.md)     | feature 配置的 Shader 65，经材质和全局纹理，连到解压后的 DXBC 取样、颜色/深度输出及包内 AlphaBlend/ZWrite；单块修改由层筛选重绘消费 | inline sampler/实际 LOD、引擎 attachment/覆盖、所有场景与清理所有者、主体 shader 全貌               | 实际像素过滤、透明遮挡、运行中的 feature/目标选择、分配与帧耗       |
| [Tiny Glade 72：CPU 绘制绑定](72-tiny-glade-cpu-render-bindings-and-lifecycle.md)                     | render_world 注册 G-buffer、调用 render_bucket；另注册 deferred 光照并传四种具体 shader 路径；间接绘制函数实际提交 20 B 步长命令    | G-buffer 写端与 light shader 读端的句柄同一性、墙类条目到回调的指针/ID 映射、所有图条件             | 实际 pass/barrier 与驱动执行、候选/可见数、画面和 GPU 时间          |
| [沙堡 08：材质绑定、渲染状态与更新](sandcastle/08-material-bindings-render-state-and-invalidation.md) | 实际场景 Ground/Water 组件连到 Sand/Water 材质、Shader 和贴图；补 cell buffer/全局参数的 CPU 入口和沙水 pass 状态                   | 尚未逐项闭合的 global ID、资源句柄、全部参数生产与场景变体，以 08 的逐项范围为准                    | 实际使用的材质/尺寸、取样边缘、读回与碰撞延迟、帧耗                 |
| [掘地求财 06：section、材质接收与销毁](digging-a-hole/06-mesh-material-binding-and-edit-lifecycle.md) | Basic handler 的虚表目标、合并结果队列、section settings/buffer 落入组件、GetMaterial 查询及渲染/碰撞标记；解开 DestroyOre 条件     | 游戏实际 handler/材质配置、煤矿 StaticMesh 材质 slot、材质参数来源、其它 handler 与旧 cook 最终验收 | 实际组件/材质绑定、该次挖掘走哪条路径、旧结果时序、长期稳定性与性能 |

## 哪些旧结论得到补充

**SUMMERHOUSE：** 上轮未解的 Shader 65 已通过其真实 LZ4 表恢复两个有效 DXBC。片元直接采颜色和深度，并输出 `SV_Target`、`SV_Depth`；状态表同时允许 alpha 混合和深度写入。因此“源 alpha 为零”不能在静态机制上被解释成自动不写深度。仍需区分包内状态、引擎最终状态与实际像素。

**Tiny Glade：** 已超出上一轮仅有 shader 格式相容的证据，现在有真实 `render_world → main_pass → G-buffer raster → render_bucket` 和 `render_world → deferred_raster → Apply deferred lighting` 调用。两个 pass 位于同一静态编排中，但输出/输入句柄还没逐字段对齐；不能据此把“两个 pass 已定位”写成“整条资源链已完整证明”。

**沙堡：** 材质不再只停在 shader 参数名称。场景组件、材质、Shader 605/587 和对应纹理已有真实引用链，水的折射因子也有包内数值。颜色与模拟状态仍由不同生产者供给；静态材质初值不代表某个游戏帧的最终 uniform。

**掘地求财：** 原先只追到任务完成门与 mesh handler，现在能在 Basic 分支继续追到组件 section 数组和材质查询。`FinishSectionsUpdates` 标记渲染状态并更新碰撞，表明可见产物有接收点；它仍不是 GPU 已完成或游戏默认选择 Basic 的证据。矿物是独立 StaticMesh 组件分支，不能把 Voxel section 的材质接收链当成煤矿材质槽的证明。

## 局部更新如何与渲染相接

四款的局部性分别落在不同边界：SUMMERHOUSE 修改单块后，像素化 pass 按当前层和 cull results 重绘；Tiny Glade 对象级实例更新之后，还经过候选列表、binding 与 draw recorder；沙堡局部格值变化经全局 cell buffer 给表面 shader，CPU 读回/碰撞另有频率；掘地求财则从被选 chunk 的完成结果经过队列、section 与组件失效通知。它们都不能用一个“局部重画”概念合并。

**跨层构造例，非原作运行记录。** 假设一次操作只改一个语义对象：SUMMERHOUSE 可以只换它的材质槽，而渲染消费者仍重绘筛选到的其它对象；Tiny Glade 可以只上传该墙的新实例，但当前视图候选不是自动缩成这些新实例；沙堡可以只写刷内格值，而 Dispatch 覆盖整层 resolution；Voxel Basic 可以只接收该 chunk 的新 sections，而完成后仍触发组件渲染/碰撞更新。这里把四篇已证局部分工放在同一个问题下比较，不假设它们具有相同输入、频率或成本。

## 下一段静态调查的精确入口

- **SUMMERHOUSE**：Shader 65 inline sampler 记录、`_BlitMipLevel` 的生产者、实际 `Blitter`/renderer attachment 设置；不要再从压缩字节中直接索引 DXBC。
- **Tiny Glade**：`main_pass` attachment 捕获字段与 `deferred_raster` binder 对照，墙 draw-list item 注册与 `indexed_indirect::draw_fn` 指针；保留 graph read/finish 所有权。
- **沙堡**：按 08 尚未闭合的字段追 global property ID、各纹理生产与消费者的同一资源身份，不能用材质/属性同名补完。
- **掘地求财**：VoxelWorld 配置与 Basic/Clustered/Mixed 选择、`FVoxelMaterialInterface` 的具体对象/参数、StaticMesh slot 的可靠序列化 schema。没有 schema 时保留包依赖层级，不把任意字节猜成 slot。

这些是后续入口，不是已经取得的证据。运行问题的场景、指标与通过依据单列在 [74](74-runtime-validation-cases.md)，当前全部 Not Run。

## 可复查与验证范围

正式新增工具是[Unity Shader 状态前缀读取器](tools/unity-shader-state-probe.py)和[沙堡材质引用读取器](sandcastle/tools/material_binding_probe.py)。前者只读取调用者定位的状态前缀，后者只覆盖本次格式/选定对象；并未安装引擎或宣称完整支持 Unity/Unreal 的所有版本。SUMMERHOUSE 继续复用既有 Shader LZ4/DXBC 和参数读取器，Tiny Glade/掘地求财复用 PDB、PE、蓝图工具。原始输出集中在 ignored `.cache/procedural-modeling/render-chain-followup/`，各篇给出具体地址、偏移或 token。

本轮验证包括：当前制品身份及匹配范围、REA 选定托管成员、真实 Shader/材质读取与解码、原生调用和虚表目标回读、构造演算、Python 语法与有界失败检查，以及专题链接/UTF-8/空白检查。没有以文件数或解码数代替完整性结论。真实游戏、GPU 抓帧、运行参数、线程/内存和性能测量为 **Not Run**。

产出用于独立行为规格和自研设计；恢复的指令、游戏代码及素材不作为生产实现交付。
