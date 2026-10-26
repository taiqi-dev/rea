# Tiny Glade：场景深度到自动焦点与景深准备

后续 [167](167-tiny-glade-water-ice-depth-access-and-epochs.md) 将水／冰接到可读写深度访问声明；[168](168-tiny-glade-tree-material-descriptor-producers.md) 补树材质的专用绑定生产端。完整图调度和树实例最终绘制仍保留边界。

2026-10-24，America/Los_Angeles。续 [161](161-tiny-glade-dof-focus-and-near-far-blur.md)、[162](162-tiny-glade-tree-see-through-and-dof-composition.md)，本轮重点区分“同一 CPU 图资源记录”“注册时点/版本”“最终 GPU 深度”。身份、工具与本轮记录目录沿 [163](163-tiny-glade-autofocus-parameter-producers.md)。

## 已补上的身份链

以 D 表示 `render_world` 入口栈参数中指向的深度 TexView 记录，本篇不伪造运行句柄。已有 [75](75-tiny-glade-texture-handle-provenance.md) 证实 G-buffer 结构首项的颜色记录；这次补第二项及景深 binder：

| 阶段               | 实际 preferred VA / 数据流                                                                                                  | 本轮结论                                               |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 放入 G-buffer 结构 | `0x1400FA9DF–0x1400FA9F6` 取 `[rbp+0xA90]` 所指记录，复制 16+8 B 到 `[rbp+0x7C8]`                                           | 它是结构首项 +0x18 的另一记录，不能与颜色记录混称      |
| 深度附件           | `main_pass` 以所传结构 +0x18 形成指针（`0x1409ACB0A`），存入 raster 的 depth attachment 参数（`0x1409ACB5B`）               | 此主 pass 的深度附件使用 D 的结构副本                  |
| 再次复制           | 75 已核 `[7B0..7EF]→[5F0..62F]→[198..1D7]`；第二项因此位于 `[rbp+0x1B0]`                                                    | 记录位置是按值复制关系，不是又创建了一个同名深度纹理   |
| 自动焦点传参       | `0x1400FBBEA` 取 `r15=&[1B0]`，`0x1400FBC18–0x1400FBC1B` 作为第三实参传入 calculate_dof_autofocus                           | 自动焦点使用当时的 D 记录指针                          |
| 自动焦点 binder    | `0x140B3843C` 保存该指针，后放入参数块首项；`0x140BDCCE2` 从首项取 TexView                                                  | 不是从附近的 G-buffer color 或 velocity 猜出来的 depth |
| CoC 准备传参       | `0x1400FC38E–0x1400FC39D` 从当时仍指向 `[1B0]` 的 r15 复制 8+16 B 到 `[840]`；`0x1400FC58B–0x1400FC598` 传其地址            | CoC 输入源自此时 D 记录的副本，注册时点晚于自动焦点    |
| CoC binder         | `dof_prepare` 保存该参数到 rbx（`0x140B04C99`），写到 shader 参数块 +8（`0x140B04FFD`）；binder 从 +8 读取（`0x141B041AC`） | 与另一个 buffer/输出图不同，是明确的深度输入槽         |

两个实际模块 `dof/calc_autofocus.precomp` 与 `dof/prepare.precomp` 的 `depth_tex` 均装饰为 **set 0 / binding 1**；其入口各有对应生成 binder。所选资源指针、参数块槽位与 shader 名字/绑定一致，不再只是“二者都读取某种深度”的解释。

**地址演算，非运行。** 结构始于 S，颜色占 `[S,S+24)`，D 占 `[S+24,S+48)`。S 从栈偏移 0x7B0 复制到 0x198，D 自然从 0x7C8 到 0x1B0；不能把 +0x18 当成一个新的纹理 ID，也不能把“相同栈局部名称”当成跨所有时期都未改变。

## 为什么还不能说两个消费者总读同一版本

CPU 调用存在以下顺序：自动焦点在 `0x1400FBC1B` 注册；随后还有 late_forward_and_deferred、半分辨率深度/法线、屏幕阴影与 deferred 光照；`0x1400FC38E` 才复制给后段，后续经过 grass debug overlays、volumetrics，以及 `0x1400FC52E` 间接选择的水/冰 pass；`0x1400FC598` 再注册 CoC prepare。

因此必须分开三个事实：

1. **已证实：** 选定 CPU 结构复制和 binder 指针可以追到同一深度记录的来源。
2. **部分回答：** 原 pass 与后续消费者之间有多个注册和可能的深度写入阶段；本轮未证明它们全部不改视图记录、不形成新版本或只读深度。
3. **未证实：** 图编译后的 GPU 图像对象、两个消费者具体取得的版本/执行时序、可见树切口对应的最终深度像素。

相同的资源家族/句柄来源不能替代版本证明。也不能只按 CPU 调用顺序断言所有 compute 已按该顺序在 GPU 完成。

## 树木切口到深度仍差哪一步

[162](162-tiny-glade-tree-see-through-and-dof-composition.md) 已证树冠/树干的局部 demote；本篇又接通主 pass 的 D 和两种景深消费者。但要宣布“这棵树切掉的片元一定不会进入该帧景深深度”，还需要具体树材料/实例到该 pass 的最终绑定、所有相关深度 pass 的覆盖一致性和图版本。

既有 [61](61-tiny-glade-tree-mesh-processing-and-publication.md) 仍保留树实例 staging 到真实 GPU transfer 的断点，本轮没有通过借用砖的上传路径把它补成事实。也没有从 demote 数量、shader 文件名或同一偏移推出整棵树的真实最终渲染。

所以总体判断仍是：**结构支持树木局部渐隐与景深组合，没有找到按树/建筑二选一的优先级分派；原作全模式同帧效果尚未运行确认。**

## 我方可以直接采用的设计约束

- 明确自动焦点和 CoC 希望使用哪一个深度阶段。若采用同一最终深度，应记录同一视图/帧与深度版本；若自动焦点刻意忽略水面而 CoC 使用含水面的深度，也应是显式策略。
- 树的颜色、深度、法线和运动向量保持同一局部覆盖。否则颜色看似让开了，景深或其他屏幕效果仍可能沿未切掉的树轮廓处理。
- 叶片原 alpha clip、相机局部渐隐、树几何 LOD、遮挡剔除和景深质量分别设置，分别验证，避免用一个开关偷改另一种成本或效果。
- 每视图有自己的资格与焦点；不把玩家相机的切口写成世界树删除/存档状态，也不让其他相机或阴影无意继承。

这些是我方独立规格候选，未读取或修改用户 Unity 项目。最有价值的后续原作静态入口是中间水/冰等 pass 的深度访问和具体树材料桶；只要目标是综合 demo，不需要等待所有原作图边恢复才设计上述契约。

## 验证与保留

复用前轮实际模块解析，本轮 [dof_followup_probe.py](tiny-glade/tools/dof_followup_probe.py) 新校验选定深度附件/参数槽指令，并重新读取两个模块的 set/binding。`proof-final.json` 是普通文件验证回执，不是运行截图、GPU 验证或 REA Evidence。

原始数据保留在 ignored `tiny-dof-followup/`，场景主函数及两种准备模块复用 `tiny-dof-tree/`，旧复制链与主 pass 记录沿 75 的明确文件。游戏、GPU、Unity、深度可视化、画面和耗时验证均 **Not Run**。
