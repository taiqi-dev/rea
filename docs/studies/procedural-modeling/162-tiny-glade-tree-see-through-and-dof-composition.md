# Tiny Glade：树木局部渐隐与景深的关系

后续 [164](164-tiny-glade-tree-settings-and-cone-producers.md) 将配置字节命名为 ImageFormationConfig.artistic.tree_see_thru，并接回模式门、平滑距离状态及镜头 FOV 角度；[165](165-tiny-glade-scene-depth-to-focus-and-coc.md) 补场景深度记录与自动焦点/CoC 的绑定。中间 pass 版本和真实 GPU 树深度仍未冒称闭合。

2026-10-24，America/Los_Angeles。景深的输入、近远侧和开关见 [161](161-tiny-glade-dof-focus-and-near-far-blur.md)。本篇回答局部树木透明是否是“树触发透明、建筑触发景深”的优先级选择。静态范围、制品身份和截图限制沿 161；当前仅调研，不授予项目新实施或运行权限。

## 结论：两种效果分工，存在树专用资格

**现有证据支持两条可组合的结构：树材质按相机相关范围丢弃部分片元；景深对画面深度生成近远模糊。没有发现所选景深阶段按树/建筑类别二选一的分派。** 这不等于所有相机模式、设置和材料都必然在同一帧同时启用，完整最终深度/颜色绑定与 GPU 画面尚未验证。

原作的树冠和树干都存在局部 see-through；树干还保留了随局部高度变化的资格，不能简单说“仅叶片透明，树干永远不变”。反过来，本轮没有找到证据证明所有建筑也走同一树木圆锥切口；单个砖 shader 未使用该树特有输入，也不能代表所有建筑材料都不存在其他渐隐。

## 片元层证据：有噪声的覆盖丢弃

本轮重新解析两个文件的主 vertex/fragment，以及所选砖 fragment：

| 文件及主 fragment                                    | 实际使用的输入                                                                                                                                            | 结果/限制                                                              |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| clearing/tree_canopy.precomp，偏移 22839，5545 words | see_thru_anim_t、prim_center、相机矩阵；实际访问 render_overrides、is_firstperson_mode、tree_canopy_cone_angle_mult、tree_canopy_max_cone_cull_dist_range | w3230 是圆锥分支的 demote；w3550 是另一个叶片纹理阈值 demote，两者不同 |
| clearing/tree_trunk.precomp，偏移 10904，6217 words  | see_thru_anim_t、local_y、handplaced_flag；实际访问 render_overrides、is_firstperson_mode 和最大圆锥距离字段                                              | w5052 为所选圆锥切口 demote；树干的角度构造/材料分支不同于树冠         |
| wall/wall_brick_lod0.precomp，偏移 33327，4639 words | 所查模块没有树木 see_thru_anim_t，未见实际读取上述树特有圆锥字段                                                                                          | 自己也有其他 demote，不能把任何 discard 都命名为树木透明               |

上述“实际访问”来自 OpAccessChain 的根对象和常量索引，而不是共享 FrameConstants 类型里恰好存在这些成员名。

树冠片元的选定过程：

1. `w2855–2913` 在 `(render_overrides & 0x2)!=0` 时保留输入动画值，否则取 0；该值大于 0 才继续所选 conical 路径。`w2984–3012` 还要求 is_firstperson_mode 为 0。
2. `w2918–2974` 把 prim_center 变换到 view space，以投影矩阵尺度形成距离范围；`w3018–3040` 限制所选视图深度小于最大距离。
3. 后续从冠片中心与局部纹理位置构造视图方向，距离平滑项调圆锥角；角度再乘 see_thru_anim_t。
4. `w3170–3224` 实际采 `blue_noise_textures.uniform01`，给角度阈值加小扰动，用 cos 阈值与方向比较，成立就 `OpDemoteToHelperInvocation`（w3230）。

这支持按像素形成软化的局部缺口，不能称为“整棵树换透明材质再 alpha=.5”。噪声阈值的存在是所选路径的事实；完整 blend/depth/sampler 配置及其他 pass 尚未查全，不把这一点升级为全产品从不使用 alpha blending。

树干另在 `w2123–2179` 计算：

```text
effective_see_through = see_thru_anim_t * smoothstep(0,6,local_y)
```

它还受覆盖位的所选分支控制。此式使局部高度接近底端的部分弱化或不进入该渐隐资格，较高处逐步增强；6 是 shader 局部坐标参数，不能直接称世界 6 米。树干后面的圆锥方向、角度和 handplaced 分类比树冠复杂，本轮不输出一份声称适配全部树的统一等价算法。

## 动画来源：实例内第二个 half，而非景深进度

两个 vertex 都从实例 `anim_t_packed`（实例 +0x20）取 uint，再用 GLSL.std.450 `UnpackHalf2x16` 取第二分量输出 see_thru_anim_t：树冠在 w2386/w4118/w5490，树干在 w1907/w2591/w2626。该操作编号 62 的命名已核 [Khronos 官方扩展指令 grammar](https://raw.githubusercontent.com/KhronosGroup/SPIRV-Headers/main/include/spirv/unified1/extinst.glsl.std.450.grammar.json)。它与 DOF 的 focus0/1、CoC 不在同一个状态字段中。

`forest::tree_animation::handplaced_tree_animation`（preferred VA `0x14288E1E0`，3145 B）补到了实际写端：

- AppMode 跳表 `0x1435AB888` 选择全局目标；raw mode 4 到 `0x14288E467`，其中子层为 6 时走另一方向。结合 [160](160-tiny-glade-water-brush-and-layered-eraser.md) 中已核的临时 Eraser 模式构造与 EraserLayer::Tree=6，这接通了树层橡皮会改变该目标。raw mode 12 直接到同一反向目标入口；该模式完整 UI 名称仍不在本篇猜写。
- 目标的一部分还来自 `AudioTriggerCollection::boxes` 返回的有界记录，对相机前方短线段调用 Aabb3::intersect_segment（`0x14288E4ED–0x14288E658`）。**这不是已证明的逐树“相机到选中房屋”遮挡射线**；盒的业务分类、全部 producer 仍未展开。
- per-tree 更新在 `0x14288EA60–0x14288EA92` 检查目标和出现进度是否已到 1；所选状态按时间增量加/减并夹到 [0,1]。因此新树的出现动画与渐隐资格有衔接，不是任意时刻把整个显示立即开关。
- `0x14288EAC3–0x14288EAD5` 将第二参数作 `1-(1-s)^2` 后调 `pack_2x16f_uint`；`0x14288EAEA` 把结果写到 PrefabInstanceData 的 +0x20。顶点读取的相同偏移接到片元 see-through 动画。

这里确认的是 CPU 实例字段与 shader 布局/half 编码约定一致，不是某帧已经成功上传。[61](61-tiny-glade-tree-mesh-processing-and-publication.md) 仍保留树实例 staging 到真实 GPU transfer 的断点；本轮也未逐个最终 buffer handle 闭合，不能仅凭相同偏移冒称 GPU 绑定已证。

**构造例，非游戏运行。** 在所选目标为真、树已完全出现的前提下，s=.2、时间增量 .1 得 s=.3，打包前的渐隐系数为 .51；若目标为假则 s=.1，系数为 .19。它证明时间渐变与回程，不证明截图中的持续时间、设备结果或进入/退出采用不同距离阈值。

`prepare_frame_constants`（`0x1409252D0`）也有实际 GPU 字段写端：`0x1409263CA` 写 +0x138 对应树冠角度字段，`0x1409263DB` 写 +0x13C 对应最大圆锥距离。这个距离不是所选 shader 内唯一固定常数；所有源参数、森林树与手放树的统一关系尚未闭合。不能把“CPU 有插值”称为已证明的空间滞回。

## 对用户问题逐项判断

| 问题                                | 当前静态结论                                                                                                       |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 是否按树/建筑决定景深或透明二选一？ | 不支持这一解释。景深消费深度/焦点，树 see-through 消费实例动画/相机范围；没有在所选 DOF 程序中发现树分类选择       |
| 相机接近是否参与？                  | 参与：树的视图距离与圆锥范围会限制局部丢弃；景深则依相对焦点的投影距离，近远两侧都可模糊                           |
| 是否判断挡住选中对象？              | 尚未证明完整“相机→选中物”raycast/目标遮挡协议；已见相机空间圆锥和另一类盒/短线段判断                               |
| 编辑状态是否参与？                  | 是。手放树入口读取 AppMode，接通树层橡皮等选定分支；全部工具/选择状态未穷尽                                        |
| 叶、干是否完全一样？                | 否。两者都有 see-through，树干额外按 local_y 调制，后续材料/方向条件也不同                                         |
| 是 dither、alpha、裁切还是 LOD？    | 所选树冠路径是带蓝噪声阈值的片元 demote；叶纹理 alpha 阈值是另一路。树几何 LOD、视角冠片剔除和后期模糊均为其他职责 |
| 能否同时出现？                      | 结构支持组合：剩余的树表面/后面的景物可再进入景深；最终同帧图像与全模式互斥关系未运行确认，不承诺始终同时启用      |
| 是否有优先级和滞回？                | 有配置/模式资格和连续动画；未证实统一“透明优先于景深”的仲裁器，也未证实空间进入/退出双阈值滞回                     |

若逐像素切口已经改变了最终送入后处理的深度/颜色，景深处理的自然会是改变后的画面；这是一项管线推论，**本轮尚未恢复每个树 pass 到最终 DOF depth handle 的全部边**，所以不将其写成已观察的 GPU 帧事实。

## 我方候选方案与下一步

独立设计可以分成两项：一项管理景深焦点、近远模糊和预算；另一项只给选定资源包树材质提供相机相关局部渐隐，分别设置和验证。建筑保持可读和树木让开视线不是互斥目标，无须先制造一个全局“类别优先级”系统。

渐隐资格与范围由既有相机/表现所有者发布，不给每片叶子或每个材质独立 Update；每个视图独立，避免玩家相机使另一个视图/阴影错误开洞。颜色、深度、法线及运动向量的覆盖需要一致，叶片原本的 alpha clip 和资源包 LOD 应继续保留。时间平滑与空间双阈值是不同设计选择，后者若需要由我方明确新增。

验证候选：近树/近墙/远景分开看，关景深仍可检验树渐隐，关树渐隐仍可检验近远景深；贴树干底部、对树层橡皮、刚放树、撤销/换工具、第一人称与普通相机分别检查。再检查 TAA/升频下边缘闪烁、相机停下后稳定、UI 清晰以及颜色/深度轮廓一致。demote 不是免绘制或免几何成本，景深也有全屏/带宽成本；本轮没有性能数值。

报告与验证候选回报现有 Supervisor，等待其按用户后续指令决定制作范围；不新建实施 owner，不改 Unity 源码/资产/状态。

## 证据与边界

原始记录在 ignored `.cache/procedural-modeling/tiny-dof-tree/`，包括本轮 PDB 查询、forest/handplaced 动画、FrameConstants 与 render_world 的 dumpbin、5 个 shader 文件的逐模块解析。[dof_tree_probe.py](tiny-glade/tools/dof_tree_probe.py) 校验关键操作、实例/常量写端及实际调用；完整 shader、原资产和恢复代码不进入产品。

尚未知全部树类别/编辑模式、AudioTrigger 盒的生产与业务资格、最终 blend/depth/阴影策略、每个 shader 到 DOF 的纹理身份、空间滞回及确切视觉延迟。游戏、GPU、Unity、画面、手感与帧时验证均 **Not Run**。
