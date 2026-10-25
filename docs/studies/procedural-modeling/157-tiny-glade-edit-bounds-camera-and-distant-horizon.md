# Tiny Glade：可编辑边界、相机约束与可见远景

2026-10-24，America/Los_Angeles。延续用户界面反馈，供既有地形/相机 owner 取舍；本轮只读范围、制品身份和截图版本限制见 [155](155-tiny-glade-menu-snapshot-and-hover-visibility.md)。已读指定 reference-8/9/10；图中白色虚线、积雪山坡、草树与远景雾是视觉线索，不是范围和算法的完整证明。

## 三种范围必须分开

| 范围            | 当前证据                                                                                                                                                    | 不能据此推出                                           |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 可编辑地面/水域 | [31](31-tiny-glade-terrain-strokes-and-heightfield.md)、[07](07-tiny-glade-water-shape-and-banks.md) 的选定坐标映射使用世界宽 130，XZ 的 -65..65 映射到栅格 | 全部工具共享同一裁剪；白线就是所有工具的最后合法坐标   |
| 普通相机约束    | 本轮 normal camera 更新内存在不同尺度的径向/圆角方形投影，并区分 demo/full 分支                                                                             | 白线等于相机目标范围；自由/步行相机、书签都用同一约束  |
| 可见远景        | [153](153-tiny-glade-ground-startup-grid-and-background-seams.md) 已接通现成非平面远景网格及背景高度图；原始远景资产 XZ 约 ±450                             | 远景都能编辑；镜头看得见就可建造；该数值是相机距离上限 |

因此不能把“扩大世界”“把相机拉远”“把白线隐藏”和“补远山”当成同一个设置。远景可以延伸到可编辑区之外，又不扩张编辑、存档和生成预算。

## 普通相机中实际发现的投影

本轮选取 `NormalCamera` 的 `CameraBody::update`（preferred VA `0x140AC71E0`，2,356 B）、普通相机 translate（`0x140AC6F30`，364 B）及 `MainCamera::zoom`（`0x140A36630`，658 B）。以下是 update 内两个 **中间 XZ 向量** 的约束，尚未给它们强行命名成最终 camera position/target：

在 full 分支，`0x140AC754F–0x140AC7594` 使用 L≈33.475：

```text
q = clamp(p, -L, L)       // 逐分量
d = p - q
当 dot(d,d) > L²：p = q + d * L/length(d)
```

这相当于把点投影到方形外扩圆角区域，轴方向最外端约为 2L=66.95；不是把每个分量直接夹在 ±66.95。另一个中间向量在 `0x140AC760B–0x140AC7653` 使用 L≈44.85，轴向外端约 89.7。demo 对应分支使用径向长度限制，出现 66.95 和 89.7（`0x140AC7483–0x140AC7540`）。函数内还有三维长度与插值条件，不把上述某个投影独立宣布为相机全部运动契约。

**构造例，非原作运行。** 对 L=33.475、p=(100,0)，q=(33.475,0)、d=(66.525,0)，投影得到 (66.95,0)。对角线时 q 的两个分量都参与计算，不能用轴向外端组成更大的硬方框来替代该区域。

## 白色虚线的生产者仍有断点

发行包存在 `country-core/compiled/dashed_line.precomp`。PDB 的 `DebugRectangle3d::dashed_line`（`0x140A889C0`）只给矩形记录的 `+0x34` 写标记并复制该记录。本轮 recovered direct E8 caller `0x1420EDAC0` 属于 onboarding hint position 更新，不是可编辑区边界生产者的确认。

这一结果排除了一个容易误认的入口：不能因为 helper 叫 dashed line，就声称已找到图 10 白框。实际地图白线的坐标来源、入场/离场淡化、缩放关系和最终 draw binding 仍未知；内联调用与其他绘制路径也未排除。

## 远景观感可以怎样独立制作

已有 [153](153-tiny-glade-ground-startup-grid-and-background-seams.md)、[154](154-tiny-glade-ground-materials-and-pack-decoration.md) 区分近处可变格网、现成远景资产、地表着色与资源实例；[56](56-tiny-glade-tree-resources-growth-and-canopy.md)、[61](61-tiny-glade-tree-mesh-processing-and-publication.md)、[138](138-tiny-glade-vegetation-wind-shader.md) 说明树资源及植物表现。雪地主题、雾和树草层不能只靠背景纯色替代。单张参考图的亮边也不证明某个 bloom 算法或真实照度。

适合我方的独立规格是：可编辑区外仍有带起伏的远景承托；近远边缘的高度、材质和植被密度连续；远处减少实例/阴影成本并用已有雾表现距离。实际用资源包的远景、树草和岩石；不从原作导出网格或贴图，不创建第二套世界状态。

用户希望“每个存档可调整可编辑大小”和“按硬件建议范围”是 **我方新增需求**。它涉及地块索引、存档、历史、联机 host 和成本上限，需要独立方案及迁移；不能只改白框，也不能缩小后静默裁掉已有物件。按当前协调记录，地形既有 owner 收口后再安排后继，研究不授予新的共享写权。

## 证据与后续边界

原始 PDB 和 dumpbin 记录在 ignored `tiny-menu-environment/`，选取文件为 `normal-camera-update.asm.txt`、`normal-camera-pan.asm.txt`、`camera-zoom.asm.txt`、`dashed-rectangle.asm.txt`、`pdb-dashed-map-caller.json`。工具限制沿 155。

本轮可交付范围是分清三种边界并提供实际相机投影证据。若继续追原作，优先找白线的真实实例生产和相机中间字段身份；综合 demo 的基本远景制作无需等这两个细节。游戏/相机实际手感、GPU 和 Unity 验证均 **Not Run**。
