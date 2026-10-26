# Tiny Glade：树冠／树干材质绑定的实际生产入口

后续 [171](171-tiny-glade-tree-instance-to-draw-binding.md) 已补树自身的实例参数 flush、同 buffer 到材质的字段身份及树类别绘制回调，并纠正本文首项的 uniform 表述。特定树的排序结果、最终间接表 backing 与 layout B 仍未全闭合。

2026-10-25，America/Los_Angeles。续 [61：树资源和实例发布](61-tiny-glade-tree-mesh-processing-and-publication.md)、[162：局部渐隐 shader](162-tiny-glade-tree-see-through-and-dof-composition.md)。身份和静态方法沿 [166](166-tiny-glade-focus-and-tree-fade-ui-writers.md)。

## 本轮闭合了哪一段

已找到树冠和树干 **各自专用的材质更新实例**，并将原始纹理名、CPU 参数顺序、生成 binder 相对槽位和片元 shader 绑定对应起来。它补的是材质资源绑定生产端；**没有把 61 的实例上传断点或实际 bucket→最终 draw 的断点宣称消失。**

以 PDB 定位 `GraphicsDevice::update_binding_set<...tree_canopy::MaterialData<RawProtocol>>`（`0x1415711A0`，6519 B）及 trunk 专门化（`0x14154F8B0`，6455 B）。对 PE `.text` 的 E8 候选扫描各找到一个引用，再由 PDB 包含范围与真实反汇编核对：

- `0x1409E6C44 → 0x1415711A0`：树冠。
- `0x1409E732B → 0x14154F8B0`：树干。
- 两者均属于 `startup_nani::update_world_subset_material_args`（`0x1409E6AB0`，5548 B）。候选字节命中本身不作为有效调用证明，也不将本轮扫描称为所有间接调用的完整枚举。

## 原始名字到生成 binder

生产函数通过 `AssetTextureLibrary::get_by_name_hash` 取得纹理；分析器只读取名称及调用，没有执行目标内的 NameHash 函数或另算摘要。材质组名精确为 `country_core/clearing/tree_canopy/material_data` 与 `country_core/clearing/tree_trunk/material_data`。

| 材质 | 原始纹理 lookup 名称         | CPU 参数块 | native 相对 binding | 片元 SPIR-V                             |
| ---- | ---------------------------- | ---------- | ------------------- | --------------------------------------- |
| 树冠 | `canopy_alpha`               | +8         | B+1                 | set 0 / binding 1，canopy_alpha_texture |
| 树冠 | `canopy_flowers_color`       | +0x10      | B+2                 | set 0 / binding 2                       |
| 树冠 | `glade:canopy_flowers_depth` | +0x18      | B+3                 | set 0 / binding 3                       |
| 树冠 | `glade:canopy_color`         | +0x20      | B+4                 | set 0 / binding 4                       |
| 树干 | `bark_color`                 | +8         | B+1                 | set 0 / binding 1                       |
| 树干 | `bark_color_naked`           | +0x10      | B+2                 | set 0 / binding 2                       |
| 树干 | `bark_lines`                 | +0x18      | B+3                 | set 0 / binding 3                       |

两种参数块首项 +0 指向**实例只读 storage buffer 的引用**，不能误当为颜色纹理或普通 uniform 数据。此前只按块首项推断为 uniform 不准确；171 已核 native `RawBinder::read_buf` 与 SPIR-V 的 Uniform-class + BufferBlock/runtime-array 编码。这里 B 是实际 binding-layout 条目取出的基址；树冠从 `0x141571378` 取，`0x14157140E–14B8` 依次生成 B+1..4；树干 `0x14154FB12–FB93` 生成 B+1..3。本轮未完整追到每个最终 pipeline layout 的 B 选择，不用“shader 里从 0 起”替代它。

树冠生产参数组装在 `0x1409E6BF1–6C01`，顺序是实例 buffer 引用、alpha、flowers_color、flowers_depth、canopy_color；树干在 `0x1409E72D5–72E8` 组装实例 buffer 引用与三纹理。`glade:` 的最终季节资源解析及所有替换条件未在本轮重新恢复。

发行 `assets/prefabs/clearing/tree/default.ron` 的 canopy/trunk parts 分别指定 `country_core/clearing/tree_canopy` 与 `_trunk`；这与专用更新类型和片元接口吻合，但资源声明不是实际某棵树本帧入桶的证据。

## 更新到后端，以及还缺的最终绘制关联

两种专门化都调用 RawBinder，构建/保留对应资源；正常选定路径最后分别在 `0x141572121`、`0x1415507F1` 调设备对象 `+0x280` 的间接接口。本轮已追到这个后端调用点，尚未从设备函数表的加载写端命名它；不能只由参数相似把它冒称为已核对的某个 Vulkan 函数。

[72](72-tiny-glade-cpu-render-bindings-and-lifecycle.md) 已有 `render_bucket` 的三项 binding stack 查找、pipeline 绑定和可选额外 set；但缺少**具体树材质组到该 draw 条目所选 layout/set 的逐字段身份关联**。树实例 `anim_t_packed` 到真正上传/所绘实例的关联也继续保留 61 的边界。因此“专用材质已找到”不等于“可证明这棵树的该切口进入最终深度”。

**构造演算。** 仅设某 layout 的 B=0，树冠四个纹理槽为 1/2/3/4，恰与所读 shader 装饰一致；若 B 未解析，则只能确认相对偏移，不能给运行 descriptor handle 编造数值。这是接口一致性演算，不是 GPU 提交或纹理内容验证。

## 适合我方借鉴的边界

统一维护树冠和树干的材质接口与共享覆盖参数，分别允许自己的纹理/形状差异。已有资源包负责植物模型和纹理；我方独立实现材质、顶点风和局部覆盖，不搬运原作资产或恢复代码。

首批验证应检查同一实例的颜色、深度、法线和运动向量是否读取同一覆盖参数，再看焦点/水深度组合；不把这一表现状态写成树被删除、存档改变或第二套树实例权威。其余布局/上传断点有研究价值，但不必全部复刻才开始我方实现。

新证据在 ignored `.cache/procedural-modeling/tiny-focus-ui-depth/`，含 PDB 地址归属、精确函数范围及候选扫描记录。[focus_ui_depth_probe.py](tiny-glade/tools/focus_ui_depth_probe.py) 实读七个材质纹理的 shader 装饰并核 CPU 调用锚点，**Passed**。游戏、GPU、Unity、纹理最终内容、画面和性能验证均 **Not Run**。
