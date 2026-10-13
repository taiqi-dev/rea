# Tiny Glade 普通墙砖与木骨架：CPU 到可见表面

本篇解释砖行、转角砖和木梁规划之后的数据怎样变成可见表面。布局规则分别见[普通砖行](36-tiny-glade-brick-row-layout.md)、[转角与扰动](37-tiny-glade-brick-corners-and-noise.md)、[木骨架与窗洞](38-tiny-glade-timber-layout-and-window-avoidance.md)。证据是同一份发行版 EXE/PDB 和包内 SPIR-V，身份与复核见[第十轮账本](40-tiny-glade-wall-layout-evidence-ledger.md)。

## 1. 同一个外层构造器调用多种专用生产者

`construct_walls` RVA `808800` 中确认的直接调用如下。地址顺序表示本函数中的指令位置；不同条件分支决定是否执行，不能当成每帧必走的固定流水线。

| 调用点 RVA | 实际目标 | 职责与确认边界 |
| --- | --- | --- |
| `80A2B0` | `14299B0 add_wall_corners` | 普通转角砖及避让区 |
| `80A54A` | `13F7BD0 SparseBrickWriter.clear` | 清除选中写入器的旧砖记录 |
| `80A659` | `142E7B0 half_timbering` | 木骨架候选、窗口避让及构件输出 |
| `80A6D7` | `1436B60 place_rectangle_corner_beams` | 矩形角梁的另一生产者；本轮未完整恢复 |
| `80A750` | `142D650 roof_outline` | 屋顶轮廓木构件的另一生产者 |
| `80AD25` | `1446690 WallConstructor.from_curve` | 普通墙的行分割、沿墙分砖、实例输出 |
| `80AE7C` | `A69D30 WindowCutRecords.finalized` | 取得精细窗口 cut，相关格式见[窗洞重建](17-tiny-glade-window-wall-reconstruction.md) |
| `80AFC7` | `144A4C0 construct_wooden_wall_boards` | 木墙板，与木骨架各有生成入口 |

这里有“清旧并构造”的证据，但没有证明每次参数编辑会逐砖比较、只更新变化的砖。上游选择哪些墙、全部材质资格分支和实际调度次序仍有缺口。`818C60 curved_halftimber_maintain_entities` 内也存在实体创建/销毁调用；本轮不以这些调用名宣称已经恢复完整局部重建契约。

## 2. 普通砖：CPU 保存布局和四角变形，GPU 继续加工

`94C790 BrickTransform.encode` 把 96 字节 CPU 记录压成 64 字节 GPU 实例。矩阵、种子、标志、四角 Y 位移及拱高的布局已在[拱砖专题](28-tiny-glade-arch-bricks-and-rendering.md)确认。本轮重新检查普通砖消费者，重点如下。

### 2.1 随机缩放是离散选择

`wall/wall_brick_lod0.precomp` 的 vertex blob0，文件偏移 `3527–371B`：先检查 `flags & 4`。未开启时缩放为 `(1,1,1)`；开启时用实例 seed 经整数混合，形成 `U∈[0,1)`：

```text
k += k << 10; k ^= k >> 6;
k += k << 3;  k ^= k >> 11; k += k << 15;  // u32 运算
U = bitcast_f32((k & 0x7fffff) | 0x3f800000) - 1
```

随后按标志分支：

```text
flags & 1 != 0: scale = (1.05, 1.05, 1.05)
否则:          q = U > 0.9 ? 1 : 1.1
               scale = (q, q, 1)
```

因此这段不是在 `.9–1.1` 之间连续抽样，也不能无条件套给所有砖。阈值、向量和选择均来自 `3697–36F3` 的 `GreaterThan/Select`。实例另有 `seed & 3` 参与旋转；原始网格形状和旋转后视觉朝向未完整恢复，保留为四分支消费事实。

### 2.2 同一空间场让砖面产生连续起伏

文件偏移 `630F–65CB` 把八角采样结果按三个轴插值，`65DF–667B` 再计算：

```text
delta_xz = 0.06 * clamp(2.5 * (noise_xz - 0.5), -0.5, 0.5)
P += (delta_x, 0, delta_z)
```

这一项两个方向的位移各在 `[-.03,.03]`。它依据空间采样，不能等同于 CPU 按砖 seed 随机抖动中心。输入坐标的完整变换和所有相关噪声用途仍未逐一恢复。

### 2.3 CPU 正弦结果由 GPU 双线性消费

文件偏移 `6773–6837` 解码实例中的四个半精度数，沿局部两个轴做两次横向插值、一次纵向插值，再加到世界 Y。该消费者没有重新执行正弦函数：正弦生产在 CPU，GPU 消费四角样值。这样一块砖内部仍能平滑变化，而 CPU 只需保存四个数。

之后还有拱高和精细墙洞相关显示路径。本篇不把普通砖行布局、转角避让、拱高裁剪与窗口片元处理合并成一个布尔网格算法。

## 3. 曲梁的 80 字节记录不是木板矩阵

`CurvedHalfTimberInstanceData` 与 `WoodenPlankSSBO` 都可能是 80 字节，但含义不同。曲梁 vertex blob0 的成员名与 `Offset` 指令共同确认：

| 字节偏移 | 字段 |
| --- | --- |
| 0 | position，三个 float |
| 12 | color_id |
| 16 / 20 | radius0 / radius1 |
| 24 / 28 | angle0 / angle1 |
| 32 / 36 | is_straight / is_xz |
| 40 / 44 | plank_depth / caps |
| 48 / 52 | mesh_atlas_part_idx / seed |
| 56 / 60 | flags / wall_slot_id |
| 64 | window_cut_buffer_address，u64 |
| 72 / 76 | window_cut_list / pad |

CPU `AAA870 new_curved_xy`、`AAA9F0 new_curved_xz` 把中心、内外半径、起止角、截面参数编码进去；XY/XZ 选择分别写入 `is_xz=0/1`。`new_straight` 另用同一记录的字段表达直梁，因此不能无条件把所有实例的 radius 字段都解释成圆半径。

曲梁 builder 的半径来自 `r±thickness/2`。网格层级先由

```text
ceil((abs(angle1-angle0) * (r+thickness/2) + 1) / .6)
```

再加 caps 查表值、取下一幂次与指数，最后把指数限制在 `2–5`。`2E329C0` 的独立 public 符号确认是 `ceilf`。caps 查表所有有效取值与端帽语义尚未完整绑定，不把上式单独当最终层数。

`AAAB70 with_window_cut_list` 写入 `+48`（十六进制，即十进制 72）。不要把这个字段与 `mesh_atlas_part_idx +30` 混淆。木板同地址 setter 可能因编译器合并而共享实现，字段语义仍须按各自数据类型解释。

## 4. 曲梁顶点如何沿曲线展开

`nani_curved_halftimber.precomp` vertex blob0，`2F7B–308B`，对 `is_straight<=0` 的曲梁分支：

```text
theta = lerp(angle0, angle1, along)
rho   = lerp(radius0, radius1, profile_x)
P     = center + rho * (cos(theta), 0, -sin(theta))
P.y  += profile_y * plank_depth
```

`along` 和 `profile` 已经过端帽/截面分支处理，不是直接把原始顶点 Z 无条件代进去。七点截面、两种轴布局、端帽过渡与直梁分支仍需结合网格资产才能恢复全部形状。

三个附加处理已确认：

1. `1Dxx–2007`：截面扰动使用物理实例索引和原始顶点 Z 构造两个整数 key，整数混合后用 `.05*U` 修改截面。其 key 含实例槽位；尚未证明换槽后形状永远稳定。
2. `309F–312F`：Y 被分相量化：`Y=(floor(Y*512)+fract(instanceIndex*1.618034005))/512`。
3. `3147–332B`：若 `flags & 1`，seed 控制 `A=lerp(.05,.1,U)`，再以 `4*z*(1-z)*A` 从 Y 扣除，产生中段下垂。公式适用于这段曲梁分支，不能宣称所有木梁都下垂。

世界法线也由截面方向、径向或端帽切线计算并归一化（`336F–34D3`），不是仅保留原模型法线。

## 5. 窗洞避让仍有 GPU 收尾

木骨架 CPU 会排除点、按窗口 AABB 减去一维梁段，详见[布局篇](38-tiny-glade-timber-layout-and-window-avoidance.md)。输出曲梁还能携带精细窗口列表。

`257F640 nani_update_curved_halftimber` 确认以下更新：`25800E0` 写颜色；`25801CC` 写墙槽位；`25802F9` 写 GPU cut 缓冲地址；`2580360` 调用 `OwnedGpuWorldSubset.update_instance_data<CurvedHalfTimberInstanceData>`。找不到缓冲或地址为零时，上传副本里的列表被清零（`2580290–2CD`），避免用非零列表配空地址。

曲梁 fragment blob1 确认：`6E30` 取 `packed>>24` 为数量，`75E0` 取低 24 位为起点；循环 `77C8–79B4` 先从列表索引区读 u32，再按每个精细记录 48 字节读取数据。`window_cut_sdf` 被实际采样；后续存在 `C1E0 DemoteToHelperInvocation` 和 `C2EC` 深度修正。它不只是在 CPU 候选阶段绕开窗户。

这里只确认选定片元路径的遍历、采样、丢弃及深度处理。完整形状距离求解、所有形状层、法线修正及材质绑定仍未恢复；不能把“看到 SDF 采样”写成“所有木梁采用同一种 SDF 几何布尔”。

## 6. 构造例：把各层变形分开验证

以下是按发行版公式演算的独立构造输入，不是运行游戏采样：

- 砖空间噪声取 `(.8,.1)`：clamp 后为 `(.5,-.5)`，附加位移为 `(.03,0,-.03)`。
- 砖四角位移取 `.01,.03,-.01,.01`，局部权重 `u=.25,v=.75`：底边 `.015`、顶边 `-.005`，最终 Y 增量 `0`。这是插值，不需要 GPU 再求正弦。
- 曲梁 `r=2,thickness=.2,theta=π/2,profile_y=.25,depth=.4,center=(0,3,0)`：取截面中值半径 2，展开点为 `(0,3.1,-2)`。之后才应用 Y 分相与可选下垂。
- 下垂参数 `U=.4` 得 `A=.07`；`z=0/1` 下垂为零，`z=.5` 下垂为 `.07`。
- 窗口列表 `0x03000012` 解出 start=18、count=3；空 cut 地址上传时列表归零，片元数量也随之归零。

## 7. 独立实现时可以借鉴的分工

可以自行设计“墙坐标中的候选布局 → 窗口粗范围减法 → 类型化构件实例 → GPU 细形状/扰动”的架构。保留砖、木板、曲梁各自的数据类型和可诊断输出，有利于解释同一建筑编辑为什么影响不同产物。层高、分段长度、扰动幅度和资产截面应按自己的产品目标设计；不要直接把这些取样数值或恢复代码当生产实现。

未做：未运行游戏、抓帧、读取原网格资产或验证完整渲染次序。本篇的 CPU 到 GPU 桥是实际调用/布局相符的静态证据，不能建立所有模式的运行等价性。

风险：标志和材质枚举未全面绑定；物理槽位参与扰动的稳定性未确认；端帽和片元求交只恢复部分分支。
