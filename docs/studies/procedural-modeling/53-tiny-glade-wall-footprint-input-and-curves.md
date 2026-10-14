# Tiny Glade 建筑轮廓输入、平滑与墙曲线

本篇从发行版追到自由绘墙的采点、raw Curve、选定最终平滑/简化和WallState替换；另确认圆形/矩形参数怎样变成离散曲线。底层存储是二维墙线及弧长参数，不能直接当成有厚度的墙两侧边界。自动闭环、厚度偏移、直曲分类和自交修复仍部分未知。

拾取与贴墙见[54](54-tiny-glade-edit-picking-and-wall-placement.md)，状态提交和调度见[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)，身份/验证见[58账本](58-tiny-glade-input-edit-and-natural-shapes-ledger.md)。地址为同一EXE的RVA；下面区分实际调用、局部公式与构造例。

## 1. 实际生产链与选定分支

`A50E90 draw_wall`中实际calls建立了如下连接：

```text
DrawingInputSmoother.process
  → 非空Vec2 slice
  → InProgressCurve.try_add_raw_input_points
  → Curve.try_extend
  → compute_final_curve
  → 已有墙更新，或新墙创建
```

主要call为`A5143C / A51789 → BEDEF0`、`A517BA → BECDB0 → 19A74D0`；最终计算`A5209D / A52173 → BEC4B0`。两处调用的r9b均为1、epsilon为0.1。

成功后，已有墙路径在`A52381`调用`92E8E0`替换曲线；另有新墙创建路径。UI注册函数`9466A0 add_wall_shape_ux`和signifier闭包`AB6FD0`不能当作几何生产者。完整UI命令发布到draw_wall的所有按钮/模式分支仍未贯通。

接续绘制另有`A53293 → InProgressCurve.new`：它接受已有Curve，长于2.1的选定输入还存在尾部切分及21点重采样。该缓存/接续分支没有简化成下面普通无marker分支的同一种流程。

## 2. 采点同时考虑世界距离和屏幕距离

`BEDEF0 DrawingInputSmoother.process`把世界点的x、z组成二维目标B。有前点时以A为插值起点，无前点时以B为起点。r9对象`+18`的N控制候选次数，正常有限路径考察：

```text
P_i = (1-i/N)*A + (i/N)*B，i=1..N
```

没有previous标记时第一点直接接受。之后以最后接受点为参考算欧氏距离d，同时满足以下严格比较才append：

```text
d > 0.01
k*d > 3
```

`BEE11F–BEE131`确认两个门槛。k来自实际`14C7800 ws_to_ss`，选定路径为`0.5×projection[+14]×viewport_height/depth`，depth由世界到视图变换后取负号。k和N的上游生产、实际投影及调用频率未恢复；3是该屏幕换算量的门槛，不是三个世界单位。

这说明采点密度会受观察尺度影响，但不能由此宣称固定鼠标采样频率或所有绘图工具共用该规则。

## 3. Curve怎样保存点、长度与失败

已确认Curve的字段：

| 字段 | 偏移 |
| --- | --- |
| Vec2点Vec，cap/ptr/len | `+00 / +08 / +10` |
| float弧长比例Vec，cap/ptr/len | `+18 / +20 / +28` |
| 总折线长度L | `+30` |

构造至少要求两个点。长度和参数按折线计算：

```text
L = Σ length(P_i-P_(i-1))
u_0 = 0
u_i = 前i段累计长度 / L
```

`80CB5–80EC8`的选定路径中，少于2点、L=0或非有限比例走显式失败。r8b=1时额外拒绝相邻点精确相等，并返回错误tag2及索引；r8b=0不执行该附加检查。它没有在这个范围内用曲率判定直墙，也没有线段两两相交测试。

`19A74D0 try_extend`先将新点追加到原raw点Vec，再复制全点并以r8b=1构造；成功tag3时替换元数据。因此失败不能概括成原raw状态完全不变。`BECDB0`成功后给新增点添加u64权重1，权重与弧长比例是不同数组。

## 4. 选定普通路径先平滑，再简化

`BEC4B0 compute_final_curve`在r9b=1、没有可复用历史marker的选定路径，先执行50轮带权平滑，再执行RDP epsilon=0.1。证据包括`BECA4C / BECB55`的迭代实参和`BECA95 / BEC5D9`的RDP调用；不能写成统一“先RDP后平滑”。

每轮固定两端，内部点使用该轮开始的邻点，等价为：

```text
P_i^(k+1) =
  (w_i*P_i^k + 0.5*P_(i-1)^k + 0.5*P_(i+1)^k) / (w_i+1)
```

w_i是每点u64权重转float。weights数量必须等于点数，否则panic；不足3点或迭代次数0不做内部平滑。新增点权重1不意味着接续缓存中的所有点永远都为1。

历史marker路径还存在分段RDP与stitch_with，本轮没有恢复其全部缓存时序和接续规则。50轮是这两个已确认调用的实参，不外推为所有曲线处理的常数。

## 5. RDP的距离不是线段距离

`B41DC0 Rdp.new`维护待处理首尾index区间，找最大偏差点。选定距离式为：

```text
v = B-A
t = dot(P-A,v) / max(dot(v,v),1e-20)
Q = (1-t)*A + t*B
d = length(P-Q)
```

t没有clamp到[0,1]，所以是向无限直线投影的距离。原指令`B4201A–B420B2`确认分母下限、投影和距离。

split条件除`d_max > epsilon`外，还含首次特殊条件：全输入首尾弦长C<1e8且`d_max>C`。该额外条件首次split后清除。等距时严格大于更新使较早的最大点保持；偏差非有限进入panic。

例如A=(0,0)、B=(1,0)、P=(2,0.05)，t=2、d=0.05。epsilon=0.1时该偏差不足以split；若误用线段距离会得到约1.00125，改变结果。又如首尾同位、内部P=(1,0)，C=0、d=1，即使epsilon=2，额外条件仍触发split。后者支持防止首尾同位曲线直接压塌的解释，不构成闭环拓扑或自交修复证据。

## 6. 圆和矩形参数怎样离散成曲线

`A85190 ShapeParameters.as_curve2`的tag1调用`DF37E0 Rectangle2d.as_curve2`，另一个合法分支调用`DEFCD0 Circle2d.as_curve2`，圆spacing实参为0.2。

圆的点数和角度为：

```text
N = max(3, saturating_usize(ceil(2*pi*r/0.2)))
theta_i = wrap(phi,2*pi) + 2*pi*(1-i/(N-1))
P_i = center + r*(cos(theta_i),sin(theta_i))，i=0..N-1
```

所以N是包含两个几何同位端点的点数，不是N个互异点再追加闭合点。单位圆取N=32，对应31段，段弦长约0.20233664。首末三角函数的float结果不能默认按位相等。

矩形读二维轴a、中心C和W/H，令b=(-a.y,a.x)，组合`C ± W*a/2 ± H*b/2`得到四角，再精确追加首角，总5点。converter不normalize轴；要求W×H>0，否则panic，不能据此说它逐项检查W>0、H>0。

矩形进入Curve构造时r8b=0；重复首角表达闭合，没有恢复额外独立“closed=true”拓扑字段。这些是参数到curve的实际converter，形状UI如何限制轴、半径、尺寸仍未知。

## 7. 曲线状态由谁替换

已有墙成功更新先按WallID找状态，插入dirty集合，然后释放旧Curve两份Vec并转移新的56B字段（`92EA9B–92EB08`）。draw_wall选定路径还检查最终点数>999，走错误支；不把它称为全游戏所有墙的统一999点上限。

新墙正常路径`B0EB60`递增counter `+C0`作为WallID，经`17B3E60`插入状态map。稳定ID、raw Curve、公共墙派生数据和显示实例各有生命周期；入dirty集合尚不代表公共墙与GPU结果已经更新，见[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)。

## 8. 构造例：从拖动输入到保存曲线

这是自造输入与独立实数演算，没有运行游戏。选择有效已有墙、无可复用marker，前点A=(0,0)、目标B=(0.2,0)、N=4、k=100，已有前点也进入raw Curve。

候选为(0.05,0)、(0.1,0)、(0.15,0)、(0.2,0)。相邻距离0.05>0.01，k×d=5>3，均接受。raw Curve共5点，新增点权重设为1。理想实数下均匀直线点经50轮带权平滑位置不变；RDP epsilon=0.1删除零偏差中间点，剩[(0,0),(0.2,0)]。

最终Curve点数2、L=0.2、u=[0,1]。若旧点/参数capacity各5，owner替换分别释放40B和20B，再转移新字段并把WallID加入dirty集合。该例满足已确认低层有限、非相邻重复和点数资格；UI是否允许如此短的墙未确认，不能冒称实机画出的建筑。

另一个弧长例[(0,0),(3,0),(3,4)]保存L=7、u=[0,3/7,1]。平滑例[(0,0),(1,1),(2,0)]且权重全1，内部Y每轮减半，50轮约8.88e-16，再被epsilon=0.1的简化消去。

## 9. 独立实现规格与未知

可独立借鉴：采点用世界/屏幕双门槛；raw输入、权重、最终Curve和公共墙分别持有状态；选定平滑后再简化；弧长参数供下游采样。自研若要支持闭环、厚墙或自交，应另设拓扑契约，不能把低层Curve成功当成所有建筑资格已经验证。

未做：未运行游戏、附加进程或读存档，未验证真实绘图模式、频率和性能；没有恢复完整UI命令、历史marker接续、21点尾部重采样、厚度偏移及拓扑修复。

风险：未见某项检查只适用于已查范围，不能排除其他模块存在；float门槛、首末同位和失败后raw状态变化都需保留。独立演算不建立发行版逐位或画面等价性。

## 第十四轮续查

第十四轮补查见[60墙厚与轮廓收口](60-tiny-glade-wall-thickness-and-contour-joints.md)：已确认选定木墙外轮廓扩张、普通砖横向深度/法线轴和转角策略；任意自由墙offset、自交修复与窄缝填补仍未贯通。
