# Tiny Glade 建筑落地：地面采样、墙高与石基高度

发行版中已找到两条需要区分的计算：公共墙状态生产会沿平面曲线采样地面，并保存墙参考曲线与地形的差值；另一个形状高度入口会根据边界采样的均值/最大值调整高度，并平滑高度状态。石基顶高又由独立参数和上限计算，不能归为“在建筑中心采地面，然后整座建筑平移”。

笔刷与高度场见 [31](31-tiny-glade-terrain-strokes-and-heightfield.md)，石基面片和显示见 [33](33-tiny-glade-foundation-surfaces-and-cutouts.md)，读回和局部更新见 [34](34-tiny-glade-terrain-readback-and-local-updates.md)，身份与取证限制见 [35](35-tiny-glade-terrain-evidence-ledger.md)。以下RVA属于同一发行版，例子为独立构造演算。

## 1. CPU地形高度不是原始笔画参数

`TerrainHeightsData.sample_at_world_xz<TerrainHeightSsbo>`，RVA `19C1AC0`，从CPU缓冲+8读四个u16，使用资源+50/+54两个高度端点：

```text
q = encodedHeight/65535
h = (1−q)*rangeMin + q*rangeMax
```

再作三次线性插值，得到世界XZ对应高度。世界映射为 `xz/130+.5`；一个全局字节选择 `uv*512−.5` 或 `uv*512` 对齐，各自夹紧相邻索引到511或510。该字节含义及运行值未知，不能任意选择其中一种当发行版唯一采样方式。

读回函数把端点保持为[-2.5,24]，详见34。CPU取样与GPU可见地形是两个相关阶段；采样在读回完成前可能仍代表之前数据，实际同步时间不能凭静态调用顺序推定。

**构造例。** 在[-2.5,24]范围中，u16值0、65535、32768分别解码为−2.5、24、约10.750202。四个已解码角高度[0,2,4,6]，横向比例.25、纵向比例.75，双线性结果为3.5。后者使用构造角高度，不要求这些数恰好被u16逐位表示。

## 2. 公共墙的实际落地生产者

`publish_public_wall_state(B9F450)` 在 `BA10CD` 调 `19AC6D0` 重采样映射实例，输入为二维墙曲线、.5目标段长、模式及CPU地形资源。`19AC7E2/19ACA56` 实际调用高度采样；捕获的InnerWall上下文+58读标量f，正常有限值下：

```text
bound = f>0 ? f : −2.7
P = (x, max(terrainHeight(x,z),bound), z)
```

这里只确认f在该布局中的数值用途，完整编辑语义未知；它与后文形状高度函数的+44字段不是同一个对象偏移。

每原始曲线段计算长度L，目标s=.5，取 `u=min(s/max(L,1e−8),1)`，以 `roundf(1/u)` 决定细分，至少两点，再线性插值XZ并逐点取地形。`roundf`实际目标为 `2E32B00`，不能误写成ceil。模式还影响首尾/闭合处理，完整输出点数未全部归纳。

随后 `BA1168` 调 `15EB960`：对这些Vec3再取其XZ地形值，保存：

```text
delta_i = P_i.y − terrainHeight(P_i.x,P_i.z)
```

`15EB9F4–15EBA02` 核到实际取样与减法。这是墙参考曲线与地形的高度差，不是第二份原始地形高度。

**构造例。** f=2，三处地形高[1,3,0]：参考曲线Y=[2,3,2]，差值=[1,0,2]。该分支允许地形低于墙参考曲线，不能据此说所有墙都会随地面下降。单边长1.2、目标.5，计数为round(2.4)+1=3，位置为0、.6、1.2，因此.5不是硬性最大采样间距。

## 3. 形状高度入口沿矩形/圆形边界采样

`calc_shape_height_and_stone_foundation(92CF10)` 的指定形状分支实际调矩形 `as_curve2(DF37E0)` 或圆 `as_curve2(DEFCD0)`，后者传.2参数；再在 `92CFD0` 调 `19ABBE0`，传.5目标段长和地形/墙状态上下文。

这一映射把节点Y设为 `max(terrainHeight, context+44)`。接下来 `92D040–92D0B9` 对映射后的Y求均值μ和最大值M（最大值初始为0），同时另采raw terrain并结合不同下限求最小值G，用于已有石基过渡的比较。映射后的Y统计与raw terrain统计不能混用。

所读B9F450完整范围没有看到对92CF10的直接调用，因此两条路径分别陈述：不能把此形状入口画成每次地形dirty更新必经的步骤。矩形/圆形边界采样也不证明整个建筑底面被二维扫描，中心凹坑等情况不能从周长统计外推。

## 4. 高度由统计值调整，显示状态另作平滑

在92CF10的已选分支中，矩形基础B=6、圆形B=8；原始材料字节+34==1时最小a=1.6，否则a=.7；最大值14。输入对象+10!=2时：

```text
target = μ+B−.46
h = clamp(target−(M−.46),a,14)
  = clamp(μ+B−M,a,14)
```

写入该对象+48。另一原始tag分支用先前保存值调整target，完整产品枚举未恢复，不把B/a当所有材料固定默认墙高。

`92D2B8–92D333` 更新另一高度状态：下限 `lower=(context+44==0 ? −2.5 : context+44)`，目标顶高 `topTarget=h+M−.46`；未初始化时直接采用目标，已初始化时对当前值作：

```text
topNext = topCurrent + (topTarget−topCurrent)*(1−exp(−10*dt))
relativeHeight = topNext−lower
```

`time_continuous_lerp(DE93B0)` 实际调用expf后执行上述混合；dt来自调用资源，不能据此确定运行帧率、所有地形变化的动画或物理下落。

**构造例。** 指定矩形分支，映射Y=[0,1,2]，材料分支a=.7，上下文+44=0：μ=1、M=2，h=5，顶高目标6.54，下限−2.5，初始化相对高度9.04。若已有顶高5、目标保持6.54、dt=.1，下一次顶高约5.973466。这个算例只适用于明确输入分支。

## 5. 石基偏移与过渡顶高分别约束

`PublicWallState` 的指定Vec3曲线在+90/+98，石基偏移参数D在+294，下限字段b在+284。`stone_foundation_y(92F940)` 正常有限值下返回：

```text
Ymin = min(curvePoint.y)        // 空数组时使用b
nominalFoundationY = max(b,Ymin+D)
```

归约使用浮点total-order的位比较，NaN/Inf不能由有限值例子替代。`stone_foundation_offset_range(92FE00)` 和 `clamp_stone_foundation_offset(92FCF0)` 根据source给出：

```text
offsetLimit=max(source−Ymin,0)
clampedOffset=min(offsetLimit,max(requestedOffset,0))
```

source按布尔实参选择+114，或+10C−.79−.146；对应Optional +110/+108缺失时调用panic helper，不把未初始化数据当0。在33的石基表面消费者中，该布尔由 `Roof.is_flat` 产生；它与逐点top-at的插值开关是两个参数。

`stone_foundation_transition_y(92FF30)` 再计算：

```text
transitionY=max(b,Ymin+min(max(source−Ymin,0),max(D,0)))
```

木墙石基表面top helper在成功资格下再加.08，并可受局部墙高数组或+10C上限约束；几何详见33。此处nominal石基高、transition高和表面top是三个不同量。

**构造例。** Ymin=1、b=0、D=2、source=5：nominal=3、transition=3，未受额外上限时表面top=3.08。source改成2后，nominal仍3、transition变2，表面top=2.08。负的requestedOffset夹到0；缺失source会进入诊断路径。

## 6. 与道路、屋顶和石基的连接

`init_wall_height_and_arch_segment_height(8453E0)` 按消息墙ID更新每点上限数组，释放旧存储再按当前曲线点数分配。所选原始类别+258<2分支把 `max(max(−2.5,curveY)+wall+288−.46,.96)` 统一填入数组；其他分支含局部Y、山墙与屋顶剖面，未全部恢复。

这个+E0/+E8数组由石拱profile和石基top-at消费者实际读取，连接前轮的拱高上限与本轮石基边界。标量公式不能替代完整屋顶拓扑或所有墙形态。地形更新怎样筛选墙、发布消息、清旧几何分别在34、33说明。

未做：没有运行地形拖拽或建筑落地场景；未恢复完整输入枚举、底面扫描、自由形状全链和所有退化情况。

风险：边界采样分辨率、CPU读回时机和分支下限会影响结果；参考曲线高于地面并不自动证明所有空隙都由同一种石基填补。形状高度入口与公共墙生产者保持各自对象、字段和适用范围。
