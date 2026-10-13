# Tiny Glade 接缝：瓦片裁剪、洞口与显示细节

建筑连接处有几种不同职责：CPU 检测相交、生成洞和接缝砖梁，GPU 决定某片瓦或底板的哪些片元可见。CPU 部分见 [建筑相交](04-tiny-glade-intersections.md)，剖面参数见 [屋顶形状](03-tiny-glade-roof-shapes.md)，证据和验证边界见 [账本](06-tiny-glade-evidence-ledger.md)。本篇主要解释直接确认的 GPU 数学。

本次仅静态阅读发行版 `.precomp` 中的 SPIR-V，不启动游戏、不执行 shader、不复制游戏资产、不改原安装目录。这里所有十六进制位置都是 **原 `.precomp` 文件的字节偏移**，不属于 EXE 地址。JSON `seams-findings.json` 固定文件 SHA256、模块、偏移、公式、未知与复核范围。解码器复用上一轮已下载的官方 SPIR-V 语法，验证容器长度及每条指令长度；没有运行完整语义验证器。记录是普通本地静态分析，不能冒称 REA Evidence。

## 1. 瓦片切割明确使用片元半空间测试

`nani_instanced_roof.precomp` SHA256 `1eb428a8262ac739b4353771acf8219e9def853808fe32c2d40afdc77e522672`。`RoofShingle_natural` 的第 2 成员 `clipping_plane__` 位于结构偏移 16；存储为两 u32。顶点模块 blob0 起点 157，将两 u32 分别 `UnpackHalf2x16` 得到 `(nx,ny,nz,d)`，见 `0x2049–0x20e1`。输出与输入都是 Location 5、`Flat`。

片元模块 blob1 起点 36998，`0xba4e–0xbaca` 的实际操作为：

```text
signed_test = dot(float4(pos_ws, 1), clipping_plane)
if signed_test < 0:
    OpDemoteToHelperInvocation
```

第二片元模块 blob3 起点 99485，在 `0x1a41d–0x1a469` 重复相同条件。`OpDemoteToHelperInvocation` 是让调用成为 helper，普通片元贡献被舍弃，执行可能继续用于导数等目的；不能误写成 CPU 删除三角形。

**确认的范围**：此渲染路径通过平面测试裁掉瓦片片元，平面压缩为四 half。**没有确认的范围**：CPU 如何为相交建筑选择该平面，是否还有多次切割/多个瓦片实例，瓦片网格是否也被 CPU 切分，建筑整体是否做拓扑布尔，碰撞模型是否跟随。单个 plane 字段不足以断言整个相交系统仅允许一个平面。

**独立演算。** 取平面 `(1,0,0,-1)`，即边界 `x=1`：`x=0.8` 的判定值为 -0.2，取消片元贡献；`x=1.2` 的判定值为 0.2，保留。等号处不被这条严格小于判定剔除。这个例子没有判断实际游戏选择哪一个面朝方向。

## 2. 顶点位移后还会校正平面的常数项

顶点模块 `0x8969–0x89f1`：

```text
plane_out.xyz = n
plane_out.w   = d + dot(p_ref - p_final, n)
```

`p_ref` 为 `%732`：本地顶点在 nudge 后乘实例仿射变换得到的位置，尚未加 current_height，见 `0x2b6d–0x2b95`。`p_final` 为 `%1185`：实际世界位置，在高度及其他变形之后加水平噪声偏移，见 `0x6d19–0x6d59`，最终输出于 `0x8fdd`。校正后的 plane 输出于 `0x9019`。

对于该次顶点计算，代数上成立：

```text
dot(p_final,n) + d_out = dot(p_ref,n) + d
```

这表明裁切参数并非简单地从 CPU 原样传到像素阶段。解释为“抵消动画/噪声造成的切边漂移”合理，但仍是用途推断。**Flat 是重要限定**：真正片元使用 provoking vertex 对应平面，不能把上述单顶点恒等式扩大为整个变形三角形上每个片元都精确维持原边界。也没有从这里确认 CPU 与 GPU 接缝公用同一平面的契约。

## 3. 瓦片与屋顶底板共享有形状的天窗洞剔除

瓦片 blob1 的 `0xbb3a–0xc43a`，`nani_roof_floor.precomp` blob1（起点 7330）的 `0x52de–0x5bce`，包含相同的数据结构与主要算法：`DormerHole` 有 `position, wall_slot_id, size, normal, k, a`。洞按平面网格桶索引，而非每个片元遍历全部洞。

```text
cell_x = floor((p.x + 65) * 0.11538460850715637)
cell_z = floor((p.z + 65) * 0.11538460850715637)
cell   = cell_x + 15 * cell_z
count  = min(128, data.count[cell])
for j in 0 .. count:
    hole = data.holes[50 * cell + j]
    if hole.wall_slot_id != instance.wall_slot_id:
        continue
    ... 局部坐标与洞形测试 ...
```

这里 **128 与 50 都是观察到的编译指令常数**；它们不证明每格安全储存 128 个洞。CPU 写入上限、分配方式、世界范围与地址保证未确认。上述地址计算没有在这一 shader 路径中观察到网格下标钳制，不应把它写成可直接照搬的生产数据契约。

局部坐标取水平法线 `n=(normal.x,0,normal.y)`，侧轴 `cross(n,up)`，显式构造逆矩阵，随后除洞尺寸。令二维法线为 `(a,b)`，`delta=p-position`，`r2=a*a+b*b`，该构造的代数等效为：

```text
q.x = (-b*delta.x + a*delta.z) / r2 / size.x
q.y = delta.y / size.y
q.z = ( a*delta.x + b*delta.z) / r2 / size.z
```

shader 在这个序列没有 normalize；不能默认 `(a,b)` 已单位化。CPU 是否保证非零法线、非零 size 未检查。这里 `a,b` 是法线临时符号，**不是**洞字段 `hole.a`。

洞宽由竖直位置驱动的三次项调节，随着 `s` 增大而收缩；`k` 的完整取值范围尚未确认：

```text
s         = clamp(hole.k*q.y + hole.a, 0, 1)
half_width= 0.5 * (1-s^3)
y_upper   = hole.k == 1.0 ? 0.5 : 0.699999988079071
hit       = abs(q.x) < half_width
            && q.y > -0.5 && q.y < y_upper
            && abs(q.z) < 0.5
if any hit:
    OpDemoteToHelperInvocation
```

瓦片的洞路径仅在 `is_main_roof_body != 0` 时执行；底板在材质着色前执行洞路径。`k==1` 是实际 f32 相等比较。所有边界是严格比较，所以数学等号处不属于洞内。这个结论是实指令支持的解析形状剔除，不能称为“用了距离场做网格布尔”。

例：当 k=1、hole.a=0 时，q.y=0 的半宽为 0.5，q.y=0.25 为 0.4921875，q.y=0.49 为 0.4411755。这些是公式算例，不是运行截图或对游戏天窗外观的测量。

## 4. 底板高度按墙身份设置稳定细微分相

`nani_roof_floor.precomp` SHA256 `4281bd13a3537ee3d2f2b85c0ab2a6b504ff17503e9d46729b897fc553ed1a72`。顶点 blob0 起点 149 的 `0x1915–0x19f9`：

```text
wall_id = wall_identity_data.slot_wall_ids[instance.wall_slot_id]
y_out   = (floor(y_in*512) + fract(float(wall_id)*1.6180340051651)) / 512
```

这是直接确认的 **量化高度 + 按墙身份稳定分相**。分相位于 `[0,1/512)`，即约 `[0,0.001953125)`；不是帧随机抖动。不同墙的共面底板可能得到不同深度，这与避免共面闪烁/接缝干扰相符，但用途尚是推断。由于 f32 精度或相位碰撞，不保证任意两种 wall_id 都得到不同高度。

注意“相位相对于量化后的高度为非负”不等于“相对于原 y_in 只上移”。floor 操作可使整体 y_out 比 y_in 更低。

## 5. 木梁与尖顶使用独立实例变形

### 木梁

`instanced_roof_beams.precomp` SHA256 `c598a64bac479f0a34d112b2c11c37ce8b64cd0da505cc91d45e26fd188b5672`，blob0 起点 159。`RoofSupportBeam` 有 `transform, circle_normal, roof_profile`。`0x1d07–0x1def`：

```text
p = packed_affine_transform(vertex)
p += circle_normal.xyz * mix(0.2, -0.15, roof_profile)
```

此后用世界 xz*0.5 的四格 hash 构造二维噪声，插值权为 `f*f*(3-2*f)`，见 `0x2dc3–0x2f7f`。竖直位移为 `0.3*noise`。这是型面参数驱动的偏移加平滑空间扰动，不是证明木梁从完整连续网格自动抽取。CPU 如何决定梁的个数、局部形状、布置和截断未知。

四个解码的木梁模块没有 `OpKill/OpDemote/OpTerminateInvocation`，也未见 clipping plane；这个有界负面结果不排除 CPU 已切分/裁短木梁。

### 尖顶

`instanced_roof_spire.precomp` SHA256 `b7a6f1705064dbd673867077b5d4c97ae1c68e9fd1f73d26c88a7ce78f5e81b2`，blob0 起点 159。实例有 `position, roof_animation_t, roof_profile, radius`，网格有输入属性 `roof_profile_mult`。`0x1423–0x15fb`：

```text
if roof_profile_mult > -0.0010000000474974513:
    radial_scale = max(0.6,
        radius*2*mix(0.6,1,roof_profile_mult)
        *mix(0.4,1.5,1-roof_profile))
    vertex.xz *= radial_scale
```

`0x15fb–0x1703` 的全体缩放动画：

```text
s = 1 + 2^(-10*t) * sin((10*t-0.75)*2.094395160675049)
p = position.xyz + 0.5*s*vertex_morphed
```

这是参数变形以及指数衰减振荡。它不证明 roof_profile 是哪类屋顶或其有效范围，也未确定 UI 如何重置 t。四个尖顶模块同样没有片元丢弃指令，CPU 生成/相交处理未知。

## 6. 屋顶瓦片算子还包括 GPU 过滤与分桶

`nani/cull_and_bucket_roof_tile.precomp` SHA256 `43d2f0149a7351c3ef70af77d0fe63a5e163e65119f3bcf23323ff2ee4b77ce5`。三个模块均成功 bounded decode。第一个模块起点 208；`0x16c4–0x1774` 从实例读取 `base_position,current_height,scale__t,is_main_roof_body`，没有加载字段 2 clipping_plane。`0x21a4–0x229c` 可见 visibility bitmask、filtered instance allocator、histogram 原子更新。这支持实例过滤/渲染分桶，不支持“此 compute 算子负责建筑相交几何求解”。其他两个模块虽已解码，未完成完整算法说明。

## 7. 交付和未确认

新增四个 shader 文件、15 个 SPIR-V 模块（木梁4、尖顶4、底板4、过滤3），复用旧瓦片文件4模块；五个输入文件 digest 已重新计算并匹配。`summary.json` 保存新增模块起点、尺寸、独立哈希；每个 `.blobN.txt` 保留原容器字节偏移与指令。

未做：完整 SPIR-V 语义验证、GPU 执行、画面/像素实验、CPU 平面生成者与桶写入者关联、资产网格拓扑解析。原因：本篇以发行版 shader 静态证据为范围，CPU/GPU 的完整连接与运行状态尚未建立；相关 CPU 局部算法见建筑相交专题。

风险：把片元剔除误写成完整网格布尔；把 Flat 下的单顶点校正误当全片元恒等；把洞列表常数误写成安全容量；把按身份高度分相用途或木梁无丢弃当作整个系统已证实。本文对这些边界已作限定。
