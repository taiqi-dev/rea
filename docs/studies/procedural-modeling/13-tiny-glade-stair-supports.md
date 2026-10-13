# Tiny Glade：楼梯支撑、墙侧连接与结构图

前置端点、宽度和路径见 [11](11-tiny-glade-stair-anchors-and-paths.md)，踏步与楼面见 [12](12-tiny-glade-stair-treads-and-platforms.md)。这些参数之后进入多条支撑链；结构图数值传播和漂浮砖动画需要分别解释。受建筑变化影响时的产物清理见 [14](14-tiny-glade-stair-local-rebuild.md)，完整证据范围见 [15](15-tiny-glade-stair-evidence-ledger.md)。

本报告确认了木支撑的站位、承托高度、斜撑筛选和参数输出，以及结构图数值传播和漂浮砖块生产链。没有把 `MagicSupports::clear` 当生成算法，没有把结构图等同于物理受力模型，也没有把已有木拱参数生成器的调用夸大成已恢复全部拱形网格。

## 证据范围

原程序只读。没有启动游戏、附加进程、读取私人存档、安装工具或修改原制品。采用此前静态 fallback：离线 DbgHelp 匹配符号范围，Capstone 5.0.3 解码原生 x64 指令。它们是普通静态分析产物，不是 REA Evidence，不提供运行时复现。支撑调查的 19 个所选函数均完整线性解码；另复用 12 的墙侧射线切片。完整字节解码不能证明所有字节在正常路径可达。

EXE SHA-256：`4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`。本机 `tinyglade-stairs-supports/analysis.json` / `findings.json` 保留完整函数范围、原文件偏移、SHA-256、listing 路径和逐项子范围字节哈希。下文使用 RVA；不是文件偏移。文件偏移以 JSON 为准。

这里的公式是对所列指令和有限普通浮点输入的推导，数字演算是独立计算，未执行目标程序。字段名称除符号中已有名称外采用解释性名称；未知字段不强行赋予材质、碰撞层、设计意图。

## 1. 木支撑站位与承托高度

`support_station_at` (`827820`, 459 B) 先在路径的水平投影折线上找采样坐标。被调用的 `Curve::get_approx_coord_from_pos` (`13FA210`, 585 B) 对每条线段做：

```
t = clamp(dot(q-A,B-A) / max(dot(B-A,B-A),1e-8), 0, 1)
distance = length(q - lerp(A,B,t))
```

然后选距离最小的线段，返回索引和 `t`。水平坐标来自 float3 的 X/Z，不把曲线的 Y 纳入最近投影距离。宽度和二维切线分别线性插值，切线归一化后送进 `support_station_from_sample`。相邻数组索引不合法有显式 bounds panic。少于两个曲线点时投影函数自身返回索引 0、`t=0`，但这不保证后面的站位调用有效。

投影公式证据 `13FA247–13FA332`、`13FA38C–13FA43A`；站位插值和归一化 `8278DE–82799F`。`station_at` 为水平定位准备的下移位置仅用于投影，调用 `station_from_sample` 时传回原 position，不能把 −0.34 重复应用两次。

`support_station_from_sample` (`8279F0`, 1010 B) 实际构造：

```
c = p + (0,-0.34,0)
a = max(width/2 - 0.11, 0)
n = (-t.z,0,t.x)
L = c - a*n
R = c + a*n
```

这里 `t` 是传入的水平单位方向，L/R 是本报告给两个槽位取的名字。证据 `827A78–827B2E`。输出 64 字节记录：L/R/c 三个 float3（+0/+C/+18），三个底端高度（+24/+28/+2C），方向 float3（+30）和宽度（+3C）；写入证据 `827D0B–827D52`。

调用者可传高度 override：flag bit 0 为真时，把同一个指定高度直接作为三个底端高度。否则，L/R/c 各自从其上方 0.1 单位向下探测，方向 `(0,-1,0)`，最大距离 `FLT_MAX`，原始 flags `0x202`。返回 tag 1 使用结果高度 +0.3；tag 2 根据附带 bit 使用原高度或高度 −1；失败/其他回退路径调用地形 `sample_at_world_xz`。证据 `827B2E–827D0B` 和 `827DB9–827DE1`。没有从 `0x202` 猜碰撞层名称；地形采样 RVA 有多个同址模板实例，不能仅凭最短符号区分物理高度或视觉高度。

构造演算：`p=(10,5,20)`，width=2，`t=(1,0)`，override=0，得到 `c=(10,4.66,20)`，`a=.89`，`L=(10,4.66,19.11)`，`R=(10,4.66,20.89)`，三个 bottom 均为 0。另一个 `p=(14,5,20)` 的站位具有同样高度和宽度，L 为 `(14,4.66,19.11)`。若用自动探测且 tag1 返回 1.2，该槽底端改为 1.5；这只是该返回分支的演算，不模拟实际场景碰撞。

## 2. 附着点筛选和斜撑下端

`plan_braces_to_attachment_tops` (`827DF0`, 977 B) 不对所有站位无条件添加斜撑：

1. 两站位必须同属窄/宽类别。窄为 `width < 1.0499999523`；一窄一宽直接返回空列表。
2. 两者都窄只选中央槽 2；都宽选两个侧槽 0/1。常量表原字节读出 `[0,1,2]`，不是从名称猜索引。
3. 原站位该槽的顶端 Y − bottom 必须 ≥0.1，附着记录 tag 必须是 1。
4. 附着目标 float3 上移 0.06，调用真正的 `country_core::systems::wooden_stair_support::plan_braces_between_posts` (`C99DB0`, 3331 B)。

证据 `827E2B–827E69`、`827E7C–827FCF`，表 RVA `3009EE0–3009EF8`。宽度恰好等于阈值属于宽；净高恰好等于 0.1 可通过。

core planner 的 flag bit 0 分支对输入 post A/B 和附着点 Q 推导候选下端：

```
D = length(Q.xz - A.xz)
S = (A.x, max(A.bottom+.11, min(A.y,Q.y)-.7*D), A.z)
theta = acos(min(1, abs(dot(normalize(B-A), normalize(Q-S)))))
```

`theta > 0.2157993913` 时，分配一个 tag1 直杆 plan，记录 S/Q 和标量 0.17。post A/B 距离小于 `1e-4` 或候选杆平方长度小于 `1e-8` 会返回空。证据 `C99EBA–C99F5F`、`C99FB1–C9A09A`；`C9A022` 调用的确切符号为 `acosf` (`2E32940`, native size 0)。夹角绝对点积意味着取无向杆夹角。角度 ≥1.1089969873 时还有额外高度条件与细分分支，此报告不把它简化成“总是只一根斜撑”。

贯通构造演算：沿用上一节两个宽站位。只给左附着记录 tag1，右记录 absent；Q 为 B.L 上移 0.06，即 `(14,4.72,19.11)`。选择 core flags=1：D=4；候选 `S=(10,1.86,19.11)`；与水平 A→B 的夹角约 `0.6207223 rad`（35.5648°），大于 0.2157994，且小于触发后续细分的 1.108997。因此该分支产生一条 S→Q、标量 0.17 的直杆 plan。这是明确选择 helper 输入的演算；producer 传入的完整 flags 取值来源没有全部还原。

## 3. 直杆、曲杆参数怎样进入构件列表

`add_support_piece` (`827360`, 1209 B) 接受上述 plan。tag1 分支追加 **56 字节直杆参数记录**：端点实际在记录 +0x10/+0x1C，标量 +0x28，调用者元数据 +0x2C，seed +0x30，flags `0x100` 在 +0x34。部分枚举 padding 被成块复制，不能把所有复制字节都解释成几何字段。证据 `8273A2–82747D`。

seed 使用包装 64 位整数计算，而不是每次为单杆取新的浮点随机数：

```
M = base XOR (id * 0x9E3779B97F4A7C15) XOR (counter * 0xBF58476D1CE4E5B9)
seed32 = low32(M) XOR high32(M)
counter += 1
```

乘法按 uint64 溢出包装；base 来自 `stairs_assembly_params::from`，此处不猜它的内部 ID 编码。沿用前一节 plan，输入 base=0/id=1/counter=2，得到 seed `0xA6044004`，列表长度增加 1，counter 变 3。

曲线 plan 至少要两个点。`curved_brace_params_from_positions` (`8281D0`, 250 B) 和 `add_support_piece` 都**实际调用** `wooden_arch_frame_params_from_points` (`7FBCE0`, 1565 B)，传入 tag `0x13` 和三个浮点值 `.165/.111/.044`。函数名线索和调用证据结合可以确认复用木拱框架参数生成器；三个标量的语义名称、最终截面和网格三角形尚未贯通。少于两个点返回 absent；add helper 对 absent 曲线参数可退化为首末点的直杆、标量 0.17；成功时追加 64 字节曲线参数行。证据 `8281D0–8282BF`、`8274DC–8276DE`。

`7FBCE0` 在每个 48 字节点记录 +0xC 保存累计 3D 线段长度，证据 `7FBDB0–7FBEAE`。若输入 dense point 的 positions 为 `(0,0,0),(3,0,0),(3,4,0)`，这些长度为 `0,3,7`。这是 callee 输入的构造演算；前面的 dense point 映射闭包 `1420570` 未追完，不能据此承诺任意原始曲线会完全保留这些位置。

大 producer `construct_playermade_wooden_stair_supports` (`8282D0`, 48109 B) 有以下真实 direct calls：`82BA45→8279F0`（采样站位），`82BADA→827DF0`（附着斜撑），`82CBC4/82D35D→827360`（加入构件）。`82B977–82BA4B` 可核插值宽度、水平切线归一化和无 override 的站位调用。这证明上述规则不是只靠孤立符号猜出的候选函数。整段 producer 的站点密度、所有分支与曲线/立柱视觉选择没有完整重建。

## 4. 横向撑与曲线轮廓的 bounded 规则

`plan_cross_brace` (`826390`, 4035 B) 的规则可核，但它不在上述 48KB producer 的直接调用表里；此报告不承诺当前 producer 一定经由这一同名 helper（可能有其他调用或内联，需要另证）。

窄站位取中央净高，宽站位取左右净高的最小值；净高 ≤2 时返回空。顶端的两侧位置先下移 0.7，再下移 0.11；宽站位可生成横杆 plan，标量 0.17。额外层的阈值按 `6,10,14,...` 增长，使用严格 `clearance > threshold` 判断。证据 `82640E–82645E`、`8264B5–8265A6`、`8265F1–826679`。

构造演算：width=2、两个侧顶 Y=8、bottom=0，净高=8；第一横向 plan 高度为 7.19。净高越过额外阈值 6，但没有越过下一阈值 10；这里只计算经过哪些层门槛，不替未恢复的完整层构件做形状推断。

该 helper 实际以 r=.7 调用 `quarter_ellipse_midpoint_height_ratio` (`1473DB0`, 416 B)。指令构造 7 个节点、找横坐标 .5 所在段，再做 clamp 的线性插值。因此它是**分段折线近似**，不能写成直接求解析椭圆方程。r=.7 时包围 .5 的两个节点约为 `(0.35502526,0.64497474)` 和 `(0.54999999,0.80621780)`，插值 t≈.7435566，返回高度比例≈`.76486808`。证据 `1473DB0–1473F3C`。这不是从函数名猜出的椭圆解析公式。

## 4.1 墙侧连接识别与子段拆分

这条链与木柱向下探测不同。视觉组装器 `<false>` 在 `0x5B3866` 实际调用 `split_segment_into_supported_and_unsupported_subsegments`（`0x8A6E90`），后者在 `0x8A6F6C` 调用其闭包 `0x8A7560`。闭包首先调用 `StairWallAnchor::wall_normal`，结合曲线水平切线的垂向与墙法线的叉积符号，选择朝墙的一侧。

`0x8A76BA–0x8A7715` 读取局部宽度和三维位置，沿选择的水平侧向移动半宽；原点 Y 还有 `−1.17` 偏移。`0x8A7736` 向 `RaycastWorld::raycast_simple` 传入这个水平射线，距离来自调用参数。该方向并不是站位生成器中的 `(0,−1,0)`。

返回 tag `0x11` 走 absent；tag 0 的命中计算水平距离：

\[
 d=\sqrt{(o_x-hit_x)^2+(o_z-hit_z)^2}-w/2.
\]

`0x8A7759–0x8A779B` 将该标量与命中 collider 身份写入结果。其他非零 tag 在这段有效命中路径上会触发 invariant panic。完整射线结果类型的原枚举名没有恢复，不能仅凭数字命名每种失败原因。

构造演算：前置为宽度 `w=2` 的有效命中分支，射线原点与命中点的水平距离为 3，结果标量为 `3−1=2`，并保留该命中的 collider 身份；若原点基准 Y 为 5，其垂向偏移后为 3.83。若返回 tag `0x11`，则没有这个支持结果。这里确认的是局部射线返回到参数的映射，不保证任意墙侧都必然命中，也没有恢复所有拆分边界的插值和最终连接件形状。

## 5. 结构图确有实际数值消费者

`create_structural_colliders_and_initial_graph` (`8AD180`, 7814 B) 先用 `(StairGraphEdge,u32)` 键更新 collider，然后实际调用 `StairsStructuralGraph::upsert_span`，并以 `add_edge_by_span` 建立连接。示例调用 `8ADA03→14E5340`、`8ADA53→C460B0`、`8ADDD3→14E5340`、`8ADE26→C460B0`、`8ADF16→C46480`。

`upsert_span` (`C460B0`, 972 B) 维护 span→collider、collider→span 双向映射、collider 的 f32 表和 dirty 集合；替换旧 collider 时移除旧图节点、关联值，并把相关节点标记 dirty。尾部写新映射、标量和 dirty 的证据 `C46390–C46435`。这说明是有身份和邻接关系的增量状态，不能仅称“固定支撑模型”。

短函数 `structural_graph_subscribe` (`8A8000`, 56 B) 本身订阅的是 `RaycastWorld::mesh_intersect_collider_diff_publisher`，随后 `Publisher::subscribe`；它不是变形公式。真正消费者 `calculate_distortion_from_structural_graph` (`8A8040`, 18736 B) 在 `8A8292` 取 `ColliderDiff`，有实际 remove_node、disconnect_node、shape overlap 更新，再使用 `PriorityQueue<ColliderHandle,OrderedFloat<f32>>` 传播标量。

传播循环的这条分支：取出队列 priority q，生成 `candidate=min(1,3/64-q)`；对邻接 collider 的存储值，只在候选更小时写入并按 `-candidate` 重新入队。若 priority=-c，就得到每条连接递增 `3/64=.046875` 并限幅 1 的代价传播。证据常量 `8A8ADE–8A8AF4`、pop `8A9C30–8A9C6B`、公式 `8A9D46–8A9D5C`、更新 `8A9F80–8A9FC8` / `8AA035–8AA0E9`。

构造演算：明确假设一个队列输入 c=0，线性连接一跳得 .046875，两跳得 .09375，十跳得 .46875；存在更小的另一条候选时保留更小值。这没有证明所有 seed 都是 0，也没有宣称它按世界长度或物理应力传播；种子分类和 overlap edge 类型尚不完全。

更后面的每项标量向量先按映射 collider 的值取 min，然后输出：

```
if c < .45: output = 0
else:
    t = clamp((c-.45)/.55,0,1)
    output = .7 + .3*t*t*(3-2*t)
```

证据 `8AA3A5–8AA3DB` 和 `8AAA6E–8AAAEE`；`8AA670` 写入 float 数组；与缓存比较、设 dirty 证据 `8AACA3–8AACE9`。`.449→0`，`.45→.7`，`.6→.75477085`，十跳代价 `.46875→.70102220`。**.45 处有跳变**，不能简化为整体平滑函数。该数组是后续视觉装配的输入候选；本报告没有恢复最终如何移动踏步/曲线，所以不把上述 output 直接标成米、位移或稳定度。

## 6. MagicSupports 的生产端与漂浮砖运动

`playermade_stair_floating_bricks` (`81F940`, 11907 B) 才是已确认的实际生产端。它有 per-WallId `MagicSupports` map insert（`820DA6→1408C90`），并最终编码与写入 `BrickTransformSsbo`（`8212E3→94C790` / `8212F7→13F66A0`，另一分支 `8217D2/8217E6`）。还写 `SparkleSsbo`（`820AA5`）。`MagicSupports::clear` 只是其清理/替换调用，不代表生成。

一段入口扫描使用 `point.y-terrain(point.xz)>.05` 检查是否存在离地采样点，然后还有记录状态和布尔字段条件才能进入创建；证据 `8205E0–820643`。构造输入 point.y=2/terrain=1.8，差=.2，可以越过这个扫描门槛，但不能据此保证整个生产函数在实际游戏状态里生成砖。

渲染更新中 progress 字段 `s=clamp(s+delta/.3,0,1)`，证据 `821030–82105E`。64 字节记录的平移 Y 还有真实正弦摆动：

```
amplitude = .1*(1-u) + .2*u
y = record.y - amplitude * sin(time*(2+v)+phase)
```

这里 u=记录 +3C、v=+38、phase=+34；`8210EE` 调确切 `sinf` (`2E32B30`, native size 0)，Y 计算 `82108A–82110A`。随后有四元数展开、轴缩放、构造矩阵和 `BrickTransform::encode`，不是仅凭名字推断漂浮。

构造演算：record.y=5、time=1、u=v=.5、phase=0，振幅 .15，Y≈`4.91022918`；progress 从 0、delta=.15 得 .5。轴缩放前调用的 easing helper `DEDCD0` 未恢复，因而不宣称 scale 就等于 progress。这段动画公式不能推出砖承担物理承托或相同结构图控制动画。

## 未做与风险

没有执行运行时视觉复现，故以上都是发行版指令事实、条件公式与独立构造演算。没有解 `pillars_visual` (`822BF0`) 和 `brackets` (`8366C0`) 的整段 mesh 生成，也未恢复所有墙/基础、所有站点间距、木杆 GPU 网格拓扑或实例渲染。这些仍是准确的下一入口，不应由已恢复的 station/brace helpers 推广到全系统。

未证实初始结构图→木支撑构件或→MagicSupports 的直接因果关系；现有证据显示三个有不同入口、输出容器和消费者的链。上述 graph cost 分支、flagbit0 斜撑分支、横撑 helper 都有明确范围，不承诺全分支等价。无源文件或游戏文件修改风险；主要残余风险是把局部分支公式误读为完整生产规则，以及误把字段数值当世界位移。
