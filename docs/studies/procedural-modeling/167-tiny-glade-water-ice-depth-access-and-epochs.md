# Tiny Glade：水／冰深度访问与焦点的版本边界

2026-10-25，America/Los_Angeles。续 [165：场景深度到焦点/CoC](165-tiny-glade-scene-depth-to-focus-and-coc.md)，结合 [10：水面固定状态](10-tiny-glade-water-render-pipeline-and-bank-transition.md)。身份、普通文件方法与新记录目录沿 [166](166-tiny-glade-focus-and-tree-fade-ui-writers.md)。

## 本轮补上的结论

**水和冰的所选 raster 路径，都把传入场景深度登记为深度/模板可读写附件。** 不是只读深度支路，也没有在这些登记点为自动焦点复制一张历史深度。CPU 记录来源相同依然不代表两个消费者看到同一批深度内容。

本轮已补到实际访问类型和 Vulkan 映射；完整图编译依赖、调度后两个读取点的内容阶段仍是未知。以下“阶段/epoch”是研究用语，不冒充程序内已找到一个递增 version 字段。

## 第四实参到两个附件

165 的 D 副本 `[rbp+0x840]` 在 `render_world` 的 `0x1400FC51D` 作为第四实参 r9 进入 `0x1400FC52E` 选择的水或冰入口。

| 路径 | 真实入口/大小                                | 附件与 graph 创建                                                                                                                                                                  |
| ---- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 水   | `water_surface_pass`，`0x140B025A0` / 1728 B | 保存 r9 为 r14；`0x140B02994` 写 depth attachment tag=0，`0x140B029A0` 写 D 指针；`0x140B02A6C` 调 raster `0x141758710`，后者 `0x14175877E` 调 create_rg_raster_node `0x14174C000` |
| 冰   | `ice_surface_pass`，`0x140B012E0` / 4787 B   | `0x140B0130D` 保存 r9；`0x140B01A2B` 写 tag=0，`0x140B01A36/3D` 取回并写 D 指针；`0x140B01AE2` 调 raster `0x14174F020`                                                             |

水的 graph creator 从 attachment +0x20 读 tag、+0x28 读视图指针（`0x14174C03B/03F`），`0x14174C0C1/0C4` 的 tag=0 支路进入 `0x14174C153`。冰专门化有相同 tag 选择及视图处理。由此可以区分下面两个相邻分支，不用任意选一个访问码解释全函数。

## 选中支路是读写，旁支才是只读

两个选中支路在调用 `add_resource_access_impl<1>` 前写 **raw 0x30**：水 `0x14174C225/22A`，冰 `0x14174F2A3/2A8`。同函数另有 raw 0x17 支路（水 `0x14174C320`、冰 `0x14174F3A3`），但本轮传入的 tag=0 并不选它。

`NodeResourceAccessType::new`（`0x140E45930`）调用 `vk_sync_fork::get_access_info`（`0x140E97750`，51 B）。它以 raw 类型索引三张实际表：`0x143220918`、`0x143220A1C`、`0x143220B20`，分别产生阶段、访问掩码和布局：

| raw 类型           | stage flags | access flags | image layout | 含义                                                           |
| ------------------ | ----------- | ------------ | ------------ | -------------------------------------------------------------- |
| **0x30，实际选中** | 0x300       | **0x600**    | **3**        | early/late fragment tests；深度/模板读和写；attachment optimal |
| 0x17，另一个分支   | 0x300       | 0x200        | 4            | 深度/模板只读；read-only optimal                               |

表值取自发行指令/数据；枚举语义核 [Khronos VkAccessFlagBits](https://docs.vulkan.org/refpages/latest/refpages/source/VkAccessFlagBits.html)（0x200/0x400 分别为深度/模板读/写）、[VkImageLayout](https://docs.vulkan.org/refpages/latest/refpages/source/VkImageLayout.html)（3/4 分别为对应可写/只读布局）与 [VkPipelineStageFlagBits](https://docs.vulkan.org/refpages/latest/refpages/source/VkPipelineStageFlagBits.html)（0x100/0x200 为 early/late tests，0x800 为 compute）。本篇不以访问声明替代每个像素确实通过测试的证明。

`add_resource_access_impl<1>`（`0x141764080`，709 B）按资源索引维护该节点的访问记录，重复项会合并访问类型；`0x141764232/236/23A` 写索引/辅助数据/节点字段，末尾返回记录索引。它不是创建图像副本的函数，也不能据返回值给物理纹理编一个版本号。

## 对自动焦点、CoC 的实际影响

自动焦点在 `0x1400FBC1B` 注册，水／冰在 `0x1400FC52E`，CoC prepare 在 `0x1400FC598`。其实际 binder 已接到访问登记：自动焦点 `0x140BDCD0F–CDA3` 按视图条件选择 raw 0x19/0x1A，传深度的资源索引给 add_resource_access_impl；`0x140BDCDD5–CE24` 再把视图前两个 u32、绑定位置和访问记录索引登记到数组。CoC binder 在 `0x141B04286/28D` 以含 raw 0x19 的访问组登记。这里没有复制深度像素。

同一 get_access_info 表中 raw 0x19 和 0x1A 均为 stage=0x800、access=0x20，即 compute shader 的 shader read；布局分别为 5 和 4。它们与水／冰 raw 0x30 的附件读写声明不同。完整视图格式/布局选择和可变格式处理仍未穷尽。

所以当前证据已经排除“只因 CPU 按值拷贝了 24 B TexView，自动焦点就拥有冻结的深度快照”这一解释。**尚不能仅按注册先后宣布 GPU 必定先读陆地、后写水面、最后 CoC 读含水深度**；仍需完整编译依赖/回调消费才能把这一时序确认为静态结论。也未声称深度被重建成新的 VkImage。

**构造例，非运行。** 若同一物理深度附件某像素先为地面值 .2，水面测试通过后写 .4，早期读取可能得到 .2，后期读取可能得到 .4；复制视图记录不复制这两个值。这个例子只说明“句柄相同、内容阶段不同”的可能性，.2/.4 不是游戏实测值，具体读取顺序仍未证明。10 已证水面管线深度写开启；本轮没有把水的固定管线状态直接套给冰的所有变体。

## 综合 demo 的明确选择

我方应先决定焦点策略：自动焦点和 CoC 共用最终相机深度，或者明确让自动焦点用不含水的深度、CoC 用含水的深度。后者需要两个明确输入/采样阶段，不能把 URP 某个名字叫 CameraDepth 的纹理当成任意阶段都已更新。

树木局部覆盖也要在选定深度阶段保持一致；先确定哪些颜色、深度、法线、运动向量 pass 使用同一覆盖，再配置景深。无需先复刻原作全部调度细节，这是一项适合首批实现的行为契约。

未决：完整 graph 编译后的 read→write→read 依赖、实际屏障与队列执行、冰固定状态全部变体、最终深度像素。[focus_ui_depth_probe.py](tiny-glade/tools/focus_ui_depth_probe.py) 的附件/访问表核验 **Passed**；目标、GPU 抓帧、Unity、视觉及性能验证 **Not Run**。
