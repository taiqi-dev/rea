# Tiny Glade：楼梯端点锚定、路径与高度生成

发行版已确认端点身份、宽度相关偏移、邻居对齐评分，以及路径到高度/宽度数组的计算。端点不是固定世界坐标：它先从装饰物变换和墙几何派生，再按连接类型与宽度移动。踏步与平台消费这些参数，见 [踏步与平台](12-tiny-glade-stair-treads-and-platforms.md)；后续 [支撑](13-tiny-glade-stair-supports.md) 与 [局部重建](14-tiny-glade-stair-local-rebuild.md) 各有独立职责。整体范围见 [楼梯证据账本](15-tiny-glade-stair-evidence-ledger.md)。

## 证据范围

只读分析 `tiny-glade.exe`，SHA256 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`，匹配 PDB 定位范围，Capstone 5.0.3 解码。地址均为 RVA，首选基址 0x140000000。33 个函数范围共 73314 字节全部完成线性指令解码；这只证明范围字节可解码，不证明全部指令可达、所有分支已解释或整个楼梯功能覆盖。报告为手工数据流研究，未使用反编译器或 REA Evidence，未运行游戏、附加进程、操作存档或修改原制品。范围哈希和完整指令在本机调查产物的 `*-decode.json` 与 `.asm.txt`，汇总在 `tinyglade-stairs-anchors/findings.json`；其位置与可用性见 15。

研究结论是：端点先从装饰物节点和墙面几何派生；局部对齐候选通过递归评分选择；路径来自墙面行走或带端点切向的三次样条；路径再形成归一化水平弧长曲线，并分别生成宽度、高度、方向及分段数据。这里没有观察到统一的“总高度除以标准步高”计算。踏步实际构造属于另一个模块。

## 1. 节点来源和锚点

节点映射 fold 0x563F10（773B）在 0x563F75 查询 storage，在 0x563FA3 获取 decorator，0x56408D 调用 CachedDecoratorTransforms::transform(0xC45EC0)，0x56409D 调用 0x901490。后者有 as_stair/as_stair_mut 同址别名，不能把其中一个名字当作唯一 callee 身份。

0x564165..0x564197 构造 48B StairPoint：+0/+8 是 storage 身份；+10 的分支标记为墙分支 0、其他分支 1；+14/+18 是方向的两个标量；+1C/+20/+24 是 transform 返回块复制的三分量；+28 是 DecoratorId；+2C 取自 stair extra 返回数据 +4。后续实际使用把 +1C/+24 作为水平位置、+20 作为高度、+2C 作为宽度。这里给出消费语义，未恢复完整源类型声明。

墙分支 0x564105 调用 WallSpaceCoord::get_tangent(0xDEA170)，0x56410A..0x564147 按墙侧标志翻转其中一个分量。derive_stair_node_params 0x89B500（557B）再读 DecoratorInfo+32：标签 0/1 走墙分支 0x89B5FC，标签 2 到 0x89B676，标签 3 到 0x89B65B，标签 4 到 panic 0x89B6F6。分支地址来自真实相对跳表，记录在 node-jump-table.json。墙分支取 public wall、取切线、翻转分量，在 0x89B6A9 调用方向转旋转 0x9015A0，继而构造 StairWallAnchor。最终锚点标签为墙 2，非墙分支为 1 或 0；两个非墙标签的正式名字未知，不能自行称为“地面/空中”。

StairNodeAnchor::try_as_wall(0xC01470)仅在标签 2 返回对象 +8 的引用；StairWallAnchor::wall_normal(0xC01480)调用两个数学 helper 后翻转符号。helper 最终身份没有在本范围闭合，所以不把 sin/cos 名字当作已验证公式。方向转旋转 0x9015A0 明确同时翻转输入两个浮点分量并尾跳 0x2E32980，后者身份亦未在此范围恢复。

derive 输出使用 +0 标签、墙对象 +8/+10 以及 +18 邻居数的低字节；32B 载体中不同分支并不初始化所有 union 字节。邻居读取涉及图 HashMap 和 40B 条目，不能因此宣称已恢复图节点完整布局。

模块算例：若 DecoratorInfo+32=0 且 wall lookup 成功，该节点走墙分支并产生标签 2，try_as_wall 返回 +8；若同 lookup 返回空，则 0x89B715 unwrap_failed。若输入标签 3，则走非墙标签 0，+4 标量来自 stair extra，而非墙切线计算。此例说明实际分支，不给未证实的地面语义。

## 2. AlignKind 与端点偏移

AlignKind::outgoing_dir(0xC016F0，91B)：标签 0 返回 +4/+8；标签 1 返回 +C/+10；其他标签走 panic 0xC01745。AlignKind::position_offset(0xC01750，88B)接收宽度 w：

- 标签 0：+1/+2 两个标志皆为 0 时返回零，否则返回 w·d，d 在 +4/+8。
- 标签 1：返回 (w/2)·(d + (b1 ? e : 0))，e 在 +C/+10。
- 此 offset helper 的其他标签返回零；它与 outgoing_dir 的失败行为不同。

caller closure 0x38C6D0 从节点 HashMap 读位置与宽度，在 0x38C8DB 实调用 offset，再在 0x38C8E8 把结果加到节点 XZ，形成实际路径端点。所以这些式子并非只是一段无人使用的 helper。

模块算例：w=2、d=(1,0)。标签 0 且两个标志皆 false，偏移为 (0,0)；任一为 true，偏移为 (2,0)。标签 1、e=(0,1)，偏移 +1 的标志为 false 时偏移 (1,0)，true 时 (1,1)。基础位置 (5,7) 因而分别成为 (5,7)、(7,7)、(6,7)、(6,8)。没有假定这些标签的产品层名称。

find_alignment_preferences(0x89B730，1182B)会根据两节点是否同墙、间距以及端点方向构造候选。在通用三候选分支：D 为归一化节点位移，d 为节点方向；直行分数为 dot(D,d)，正分数再乘 sqrt(2)−1（约 .414213568），非正不缩放；左右转分数是 ±dot(D,perp)。垂向朝向由 sign(Dz·dx−Dx·dz) 选择。0x89B915 附近保存叉积符号，其他输入分支不同，不能泛化为所有节点一定三个候选。近距离同 storage 分支在距离平方 <1e−6 时返回单候选、分数 1。缺失 decorator 查找在 0x89BB4A/0x89BB6E unwrap_failed。

find_best_neighbor_alignments(0x89E6A0，717B)对输入邻居记录递归枚举候选组合。候选标签 0 占 mask1；标签 1 根据两方向乘积比较占 mask2 或 mask4。评分为当前候选分数 + 后续最佳分数 −（此前已占该 mask ? 10 : 0）。严格大于才替换最佳结果，因此同分保留较早候选。这是当前输入列表上的组合选择，未证明全图优化、约束求解器或 memoization。

模块算例：两个邻居各有 mask1 分数 1 和 mask2 分数 .8。重复 mask1 得 1+1−10=−8；mask1+mask2 得 1.8，因此后者胜出。这个评分鼓励类别不重复，但惩罚仍是有限值，并非禁止约束。

## 3. 路径生成与采样

实际解码 caller 是 generate_playermade_stair_requests<false> 0x37E080（29460B），最终地址版本：0x37EAE0 alignment_preferences；0x37EC06 best_neighbor；0x37FCA9/0x37FCDA derive；0x37FDD8 walk_shape；0x37FE15 Curve::try_new；0x38056B compute。另一条路径 0x3807EC 调用 Spline2D::from_control_points_with_tangents(0xDEC550)，0x380888 densely_sample_spline_segment，0x380E21/0x380E55 derive，0x381000 compute。0x381AFE/0x381B67 也是 derive 调用，不是 compute。<true> 版本 0x3853A0 只定位、没有完整解码或行为比较。

densely_sample_spline_segment 0x89E4B0（487B）读取当前 segment 的 +0 参数起点，下一段 +0 或整条 spline +14 为终点。令参数区间长度 Δ=end−start：N=max(2,ceil(2Δ))；dt=Δ/(N−1)；i=0..N−1 时在局部 t=i·dt 采样。其迭代 fold 0x1496B40 在 0x1496C31 实调用 position_at_local_t(0xDEA860)。这不是按高度等分，也不能概括成水平世界距离每 .5 插一点。

0xDEA860（65B）以 Horner 式计算 x(t)=a+b·t+c·t²+d·t³，系数在 +4/+8/+C/+10；另一个分量系数在 +18/+1C/+20/+24。tangent helper 0xDEA810 计算 b+2c·t+3d·t²。dense 输出首端导数 t=0、末端导数 t=Δ 并反向末端导数。参数 Δ 与世界弧长的关系、三次样条构造器所用边界条件全细节未知；本报告不因 natural_cubic 名字就称其必为“自然边界”。

模块算例：若 Δ=2.3，N=5，dt=.575，采样参数为 0,.575,1.15,1.725,2.3。假设示例段 x(t)=t,z(t)=0，五点水平长度总计 2.3，随后 Curve 的 u 为 0,.25,.5,.75,1。Δ=1 则 N=2、dt=1，显示这里并没有保证相邻采样间距 ≤.5。这些是假设系数的独立算例，不是运行观察。

walk_shape 0x897FE0（8636B）存在多个墙形分支。已恢复的特定分支条件含 PublicWallState+258 !=1 与 AlignKind 标签 1；墙坐标差绝对值足够大（比较 .001）的路径取 intervals=max(1,ceil(abs(δ)))、点数 intervals+1。起端标志可加 wA·sign(δ)/2，末端标志可减 wB·sign(δ)/2，再分别 project_clamp。该算法按墙坐标走，并不等价所有墙形的世界空间均匀采样。另一个墙形分支调用 circular_slice_segment_points(0x14E44B0)，未闭合。

Curve::crashy_new_from_points 0x148CB10（597B）计算累计水平距离 s_i=sum(|P_j−P_(j−1)|)，总长 L=s_last，u_i=s_i/L。输出 points Vec 在 +0/+8/+10、u Vec 在 +18/+20/+28、L 在 +30。少于两点、L=0 或归一化 u 非有限数走失败 0x148CC9C。caller 的 try_new 路径会检测失败 sentinel 并走另一路径；该 fallback 的完整产品结果未知。

## 4. 宽度、高度、地形和方向

compute_stair_assembly_params 0x89BBD0（10456B）接收上述 Curve、两 StairPoint、AlignKind、派生锚点和若干可选数组。caller 的墙形路径可以提供预计算数组；样条路径在 0x380EA2/0x380EA9 设置 absent sentinel。以下是未提供相应数组时的默认式，不代表每条楼梯一定重新计算它们。

宽度：0x89BDA0..0x89BDD1 的 SIMD 和 0x89BDF5..0x89BE13 标量尾部计算 w_i=(1−u_i)w_A+u_i w_B，w_A/w_B 来自 StairPoint+2C。

默认方向由 0x1497050 → fold 0x14E1D60 取相邻点差并归一化：除最后一点外取当前到下一点；最后一点复用前一段的前向方向。后续 0x89C0DC..0x89C164 与 0x89C197..0x89C21E 用调用者端点方向覆盖首末项；有效倒长度检查失败则置零。地形高度采样发生在这次端点覆盖之前，使用初始默认方向。零长度内部边的非有限方向处理没有完整闭合，不能宣称所有重复点都安全。

高度由 0x14984E0 → fold 0x14E1900（1114B）计算。0x14E1AD5..0x14E1B00 与 0x14E1BC9 给出线性基准 H_i=(1−u_i)h_A+u_i h_B，h_A/h_B 来自节点 +20。以水平单位方向 t_i 构造垂向 n_i=(−t_iy,t_ix)，0x14E1B14/0x14E1B19 两次乘 .5 得宽度四分之一偏移：Q±=P_i ± (w_i/4)n_i。0x14E1B74/0x14E1B9E 两次调用 TerrainHeightFloatGrid::bilinear_sample_at_world_xz(0x2202D0)，取 T_i=max(terrain(Q+),terrain(Q−))−.025。0x14E1A7F..0x14E1AA0 输出 h_i=max(H_i,T_i)。地形函数身份与调用参数已定位；其完整边界采样政策未在报告解释。

另存 BitVec 项：0x14E1BF3..0x14E1C22 在 T_i+.1>H_i 时置位，否则清位，严格比较。该 bit 并不完全等于“高度被地形抬起”，因为 T_i 在 H_i 下方不到 .1 时也会置位。其后续语义应由消费者确认。

模块算例：水平点 (0,0),(2,0),(4,0),(6,0)，L=6，u=0,1/3,2/3,1；h_A=0,h_B=2；w_A=2,w_B=4。第二点 u=1/3 得 H=2/3,w=8/3，两侧采样偏移为 ±2/3。假设两侧地形 .8 和 .9，则 T=.875，输出高度 .875，bit=true。第三点 u=2/3 得 H=4/3,w=10/3；若地形较高值1.3，则 T=1.275，输出仍4/3，但 T+.1>4/3，bit仍true；若较高值1.2，则bit=false。这能区分“抬高”与 bit 的阈值。

## 5. 端点补段、分段与输出

若 AlignKind 标签 0 且 (+1|+2)&1 非零，compute 在起/末端补点。起端 0x89C695..0x89C6A9，末端 0x89CA25..0x89CA34 均计算 Q=P−w·outgoing_dir（标签 0 向量在 +4/+8），随后 prepend/append 并重新构造 Curve。补点高度直接取相应节点 +20、宽度取 +2C；起端补 bit=false（0x89C868），末端补 bit=true（0x89CBA9）。这是附加结构，不是重新对原先所有 u 做宽高插值。标志与 SubSegment 元数据也会调整，完整字段名称未知。

模块算例：首路径点 P=(3,5)、w=2、标签0向量d=(1,0)、相关标志开启，Q=(1,5) 被加入路径前端，水平长度增加2；其高度使用节点原高度。原始默认宽高数组先生成、后补段，重建 u 不意味着所有原高度重新插值。

compute 内 0x89CE34..0x89CE69 按相邻点求 s=abs(Δh)/|ΔXZ|；determine_segment_type 0x89B470 对整个输入切片首末点使用同式。对有限数：s<=.25 → 类别1；.25<s<=2.5 → 类别2；s>2.5 → 类别3。类别正式枚举名字未恢复，不能凭坡度就称它们为平台、楼梯、梯子。合并与整段判断存在后续规则，本报告只证明阈值与部分同类合并。

模块算例：水平距2，高差.4，s=.2 →1；高差1，s=.5 →2；高差6，s=3 →3。边界 s=.25 属1，s=2.5 属2。空输入在 determine helper 会 bounds panic；零水平距离/NaN 的全链政策不作一般断言。

compute 0x89D20B..0x89D2E4 输出 0x150B 载体（caller 0x380586/0x3805B6 等以该 stride 存储）：

| 偏移 | 已证实内容 |
|---|---|
| 0..30 | Curve：水平 points、normalized u、总长 |
| 38/40/48 | 高度 Vec 的 cap/pointer/length |
| 50/58/60 | 宽度 Vec 的 cap/pointer/length |
| 68/70/78 | 水平方向 Vec 的 cap/pointer/length |
| 80/88/90 | 初始空 Vec，消费者语义未闭合 |
| 98 | 初始 absent sentinel，类型未闭合 |
| D0..10F | 两锚点载体的64B拷贝 |
| 110/118/120 | BitVec 载体 |
| 128/12C | 图边两端标识 |
| 130/138/140 | StairSubSegment SmallVec 载体，inline/heap联合表示，非普通Vec布局 |
| 148 | 组装 dirty 标志；清理消费者的含义已在 14 进一步确认，全部生产条件仍未知 |

这里是字节使用推导，不是恢复的 Rust repr 契约，尤其不能把所有偏移机械当完整 struct。

## 未做、未知和风险

未运行或动态观察：本轮选择离线发行制品研究；没有验证实际交互效果、游戏坐标单位、存档参数或变换生产器所有分支。未实现或复制原游戏代码/资产。<true> 泛型 caller、非墙锚点正式标签、完整 NaturalCubic 边界条件、每种墙形采样、退化路径 fallback、所有 SubSegment 合并规则以及标准步高仍未知。本模块不支持宣称 Tiny Glade 用某个通用求解器或统一踏步间距。

风险是静态字段解释与 alias 的误标；已通过实际读写和调用链限制结论，并在 findings.json 留下函数范围、哈希及语义置信界限。完整字节解码不能替代运行验证。分析过程没有改变原游戏，未发现调查操作带来的制品修改风险。
