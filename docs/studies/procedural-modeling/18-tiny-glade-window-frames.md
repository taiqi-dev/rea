# Tiny Glade：普通窗框、楣梁与窗台标记怎样贴墙

窗体整体姿态、楣梁分段和模型局部标记是三种不同的贴合规则。洞口生产见 [16](16-tiny-glade-window-placement-and-holes.md)，墙体重建与 GPU 精细边界见 [17](17-tiny-glade-window-wall-reconstruction.md)，标记怎样变成装饰实例见 [19](19-tiny-glade-window-autoclutter.md)，证据范围见 [20](20-tiny-glade-window-evidence-ledger.md)。

本记录只讨论普通 cottage/gothic 墙窗的视觉生成。原游戏未启动、未附加、未修改；未读取私人存档，未安装或构建工具。证据是本会话已匹配 EXE/PDB 的离线 DbgHelp 符号范围、原 EXE 字节、Capstone 5.0.3 线性指令解码与独立算例；不是 REA Evidence，也不是运行时验证。完整线性解码不等于确认每个分支运行可达。符号只用于定位，下面公式均由实际浮点运算/分支/复制指令导出。

EXE SHA256：`4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`。本机 `tinyglade-windows-frames/*-decode.json` 保存函数原始范围、SHA256、调用地址与 listing；本机 `findings.json` 汇总 26 个范围、38,611 字节；具体链接见 20。默认 VA base=`0x140000000`；所有正文地址都是 RVA。当前 native `.text` 的文件偏移为 RVA−`0xC00`，常量 `.rdata` 的偏移为 RVA−`0x1000`；这来自 PE section mapping，不能推广到别的 section。

覆盖 26 个唯一符号函数范围，共 38,611B，全部 linear decode 完整，全部范围 SHA256 从原 EXE 重新读取后核对通过；附 6 个独立构造演算。没有将缺少非零 symbol size 的 CRT thunk 加入覆盖计数。

## 1. 真正的调用链与两层贴墙方式

`generate_cottage_wall_windows 8C71E0` 在 `8C75A7` 实际调用 `Decorators::iter_modified`。在 `8C7858` 从 DecoratorLibKey 查 DecoratorCollision；宽度存入 `[rbp+160]`，来自查得记录 `[rax+30]`，同一复制中的 `[rbp+168/+16C]` 给出上下 Y 边界。`8C8616` 明确计算 `height=upper−lower`。它不是随意写死窗宽再只平移。

本次恢复的两个贴合层次：

1. 窗体整体：根据窗口左右端点的弦确定中心、水平朝向，或从缓存读取已有 Transform。
2. 上方楣梁：把窗口水平宽度分成 N 段，每段独立取两点、中点、水平朝向，最后生成 N 个模型实例请求。

这里确认的是实例布局；不能据此承诺框体每个顶点都弯到墙上，也不能据此断言最终网格不会在 shader 中进一步变形。

## 2. 墙坐标到世界坐标

`PublicWallState::wall_space 92F860` 返回两个值：`mode=(wall.raw_tag_258!=2)`，`L=wall.float_290`。`project_clamp DEA610` 在 mode=1 时调用 RVA `2E32A70` 的 `fmodf`，负余数再加 L；在其他 mode 时 clamp 到 `[0,L]`。`project_unbounded DEA6C0` 对 mode=1 使用同样余数处理，对其他 mode 保持原 s。`fmodf` 名称有本会话 `tinyglade-stairs-anchors/callees.json` 的同地址公共符号补证；它不是有非零大小的本目录函数范围。

因此对合法 L>0：

`wrap(s)=fmodf(s,L); if wrap<0: wrap+=L`；`clamp(s)=min(max(s,0),L)`。

`WallSpaceCoord::to_world_space DEA260` 接收 `(s,y)`。必须区分投影长度 Lw=`wall+290` 与此函数实际读取的曲线长度 Lc=`curve+30`（`DEA296`）；本目录尚未证明二者恒等。本记录算例显式令 Lw=Lc。在 `0≤s≤Lc` 范围中，它先取 `u=s/Lc`，调用 `Curve::get_coord_at_u<Vec2,CurveCoordSemantic2D> 1E38DD0`，在有序 knot 数组中二分寻找区间 `[u_i,u_(i+1)]`，计算 `t=clamp((u-u_i)/(u_(i+1)-u_i),0,1)`，再以此 lerp 曲线的相邻 XZ 点。输出的世界 Y 是输入 y。

关键地址：`DEA292..DEA337` 查曲线与 XZ 插值，`DEA46D..DEA475` 写出 X/Y/Z；`1E38E40..1E38ECD` 为二分及局部 t。curve normalized knots 如何初始生成不在本次范围；不能只凭 s/Lc 将它们断言为严格积分弧长。

`to_world_space` 还含端点切线外推路径（`DEA33E..DEA469`），不是一律 clamp；本记录不把负 s 分支的特殊符号处理泛化为标准外推。楣梁在 raw_tag_258=2 的墙上走 project_unbounded，若跨端点可能使用该分支，需单独验证其边界行为。

## 3. 普通窗体整体朝向、位置与固定出墙量

`8C78A1` 构建 wallptr=`r15−2A8`，因此随后 `[r15−50]` 即 `wall+258`，不是库配置。

- `wall.raw_tag_258==1`：`8C7A6B→CachedDecoratorTransforms::transform C45EC0`，按 DecoratorId 查表并复制 48B Transform；找不到会 panic。这不是在此处插值旧、新姿态。
- 其他 raw tag：`8C7DF2..8C7FEF` 手算以下布局。

给中心 `(s,y)` 与 collision-derived W：

`sL=project_clamp(s−W/2)`，`sR=project_clamp(s+W/2)`；

`A=wall_world(sL,y)`，`B=wall_world(sR,y)`；

`P=((A.x+B.x)/2, y, (A.z+B.z)/2)`；

`n=(-Δz,0,Δx)/sqrt(Δx²+Δz²)`，其中 `Δ=B−A`；

`q=xz_projective_rotation_bad(n)`，`scale=(1,1,1)`。

证据：投影 `8C7E48/8C7E98`；世界转换 `8C7EBB/8C7EE7`；中心 `8C7EFE..8C7F30`；弦法线 `8C7F36..8C7F87`；四元数 `8C7F9B→DE9AB0`。

`DE9AB0` / `DE88F0` 的实际运算先归一化 XZ 输入，构建水平 right 与 normal 基，转为 quaternion；合法水平 n 时是纯 yaw，local +Z 对齐 n、local +X 对齐 `(n.z,0,-n.x)`。这里没有从倾斜墙面取三维 normal 的操作。

对 `wall.raw_tag_258<2`，`8C7A82..8C7B22` 另加 `R(q)*(0,0,0.14)`，所以 `P'=P+0.14*n`。这是确认的固定局部出墙偏移，不能称为动态墙厚公式。raw tag≥2 跳过此偏移。Transform 之后进入模型请求 row；例如 `8C9131..8C9156` 写 blueprint+`B0` vector 的 `0x170` 字节 row，Transform 位于 row+`B0`，不是本段直接向 GPU 画一组顶点。

## 4. 楣梁分段及端头修形

N 的来源已贯通：`8C7812` 读取 `DecoratorInfo+59` subtype byte →`[rbp+2E0]`，`8C7A06..8C7A0C` 要求其为 1、2、3；`8C7B75..8C7B7C` 存到 `[rbp+1C0]`；`8C8A8D..8C8AA3` 用它除 W。不是本次发现的基于曲率自适应段数。

`8C8A80..8C8B9E` → `Vec<Transform>::from_iter 14997F0` → `TupleWindows::next 14EC5C0` → `add_lintels 8C6840`。

对 i=0..N，

`s0=project_unbounded(s−W/2)`；`s_i=project_unbounded(s0+i*W/N)`；

`V_i=wall_world(s_i,y)`；相邻 pair `(V_i,V_(i+1))` 生成一个 Transform。

每段平移 `P_i=(V_i+V_(i+1))/2`，方向由该段水平弦的 normal 决定，scale 初值 1。证据 `14EC63A/14EC65C` 与 `14998A5..14998E9`。在相同 y 的这条调用链中长度的三维归一化等同 XZ 长度。

`add_lintels` 给每段 Y 增加 `(k+1.43000018597)/2`。对 subtype≤1 保留输入 scaleX；对 subtype≥2：

- 第一个段 `P_i -= R(q_i)*(0.0809999928,0,0)`，scaleX=`0.8199999928`（`8C6A30..8C6ADC`）。
- 后续中间段 scaleX=`0.6399999857`。
- 最后段 `P_i += R(q_i)*(0.0809999928,0,0)`，scaleX=`0.8199999928`（`8C6F8D..8C702B`）。

这是把端头伸出并用不同模型宽度覆盖间距的实例规则，不能只从数值推断具体木构件尺寸、接缝 UV 或碰撞厚度。调用 flags bit0 若置位，再乘传入 scalar/`0.9`。主调用 `8C8B85` 将该参数写 0；必须结合实际参数通路，不应把通用 helper 可选分支误写为普通主调用必执行。

可选 ceiling/tag 分支会逐段检查 raisedY；`tag==1 && ceiling>=raisedY` 时跳过该段。ceiling 来源涉及本轮其他墙基础/屋顶分支，不在此扩大复原。另有 HoleAabb2 输出，本目录不将它等同于已贯通的砖木切洞链。

模型 key 是 `decorators/setdressing_window_lintel`，shader key 为 `country_core/nani_solid_vertex_color_window`；分别由 `8C6BD0/8C6BEB` 的实际字符串引用与长度证明。可复核原常量 file `3015FE8`（36B）、`330CC96`（43B）。没有复制资产网格。

## 5. Gothic 对照：局部 normal 可以作为独立实例参数

`generate_gothic_wall_windows 8C3060` 在 `8C371F` 调用 `get_gothic_hat_bones 8C2BE0`，输入同样是 wall、DecoratorInfo、s、y、W。其宽度修正为：

当 raw_tag_258==0 时，令 `u=clamp((wall.float_264−0.95)/(1.6−0.95),0,1)`：subtype1 减宽 `0.05`；subtype2 减宽 `0.1+0.21*(1−u)`；subtype3 减宽 `0.15+0.158*(1−u)`。

raw_tag_258!=0 时：subtype1 不减；subtype2 减 `0.05`；subtype3 减 `0.1`。原始 float264 的几何语义未由本目录确认，因此不命名为厚度/半径。

随后取 effective width 的左右端点与中心位置；根据各位置投影到曲线得到的相邻节点，分别求左、中心、右处的局部水平 segment normal。`8C2DE7/8C2E46/8C2EB3→148CA40` 近似投影 u；`8C2E16/8C2E66/8C2ECD→148C300` 查区间；`8C2EE5..8C2FD6` 归一化 segment delta、swizzle/write。

输出结构 60B：leftNormalXZ@0、centerNormalXZ@8、leftPositionVec3@10、centerPositionVec3@1C、rightPositionVec3@28、rightNormalXZ@34。这些位置的 Y 仍取调用 y。native 主调用又用左右端点的整体弦在 `8C37CB..8C3828` 计算实例 yaw；局部 normal/positions 另写入模型请求 row+`124..158`（`8C3E61..8C3EDA`）。

因此已经证明 gothic 同时携带整体 transform 与多处贴墙参数；本次没有贯通专属 shader 顶点消费，不能声称它已将每个框/拱顶顶点按某种 spline 变形。`hat_bones` 名称也不证明屋顶或三维上沿高度采样。

## 6. 花箱/窗台标记局部变换桥接

`flowerbed_xforms 8C7060` 按 subtype/key 选库内 mesh，实际调用 positions_without_indices 与 normals_without_indices（`8C70D9/8C70E7`），zip 以两者较小长度迭代，经 `1498BD0→14E3200` 形成 Transform 数组。点/normal 是模型内标记输入；本目录没有提取资产。

`14E32C4..14E3400` 对每个 marker p/n：

`T_marker=T_parent+R(q_parent)*p`；

`q_marker=q_parent * rotation_helper(n)`；

`scale_marker=scale_parent`（原字段复制）。

其中位置运算没有再将 p 乘 parent scale：`14E3323..14E339D` 直接 quaternion-vector rotation，`14E33A0..14E33A7` 加平移。normal helper 为实际 `14E330D→DE8FD0`。该 helper 已补充解码 978B；完整任意三维 normal 到 quaternion 退化选择不在本记录推导，不能仅凭名称复原它。

生成结果通到 cottage 的 80B WindowAutoClutterCandidate 等价 row：`8C97BC..8C980C` 在 blueprint+`128/130/138` 的 Vec append；+`10..3F` 写 48B marker Transform，+`40` 写 `hash(DecoratorId,'flower_bed',index)`（`8C9884`），+`48` 写当前 wall identity。[+0 tag1、+8 resource随机索引] 的消费语义由 clutter 分工记录继续核对。增长函数地址有不同泛型 alias，不依其误导性的 CartCandidate 名称认定类型。

这是一条模型局部标记随窗变换移动的实际桥接，不等于已恢复主窗台主体的所有建模算法。

## 7. 独立构造演算

演算使用上述数学自行计算，不运行原始代码，不假定某个实际存档含这些墙。

1. 直墙 curve `(0,0)→(10,0)`，L=10，knots=(0,1)，raw_tag=2，中心(s=5,y=3)，W=2。两端 A=(4,3,0)、B=(6,3,0)，中心=(5,3,0)，n=(0,0,1)，q=identity，scale=(1,1,1)。tag=2 不加 .14；如相同曲线输入 raw_tag=0 且投影没有 wrap 边界变化，位置为 (5,3,.14)。
2. 对同直墙，subtype2 所以 N=2，点 s=4、5、6。每段中点 (4.5,3,0)/(5.5,3,0)；选择 k=0、flags=0、无 ceiling 跳过，楣梁结果 (4.419,3.715000093,0)/(5.581,3.715000093,0)，yaw identity，scaleX=.82。subtype3/N=3 时中段使用 .64。
3. 斜直墙取端点 A=(4,3,0)、B=(6,3,2)，那么 n=(-1,0,1)/sqrt2，弦中点=(5,3,1)。raw_tag<2 的出墙偏移后=(4.901005051,3,1.098994949)。整体仍是单一 yaw，不产生 pitch/roll。
4. 对 piecewise 墙 `(0,0)→(1,0)→(1,1)`，L=2、knots=(0,.5,1)，选择 s=1,W=2,N=2，两段中点 (.5,y,0)/(1,y,.5)，normal +Z / −X，所以楣梁两段分别转向。这是输入折线的局部段跟随，不能把 fold 处效果称为精确光滑曲线拟合。
5. Gothic raw_tag0、float264=1.275、subtype2、W=2：u=.5，effective width=1.795；同一条直墙 s=5,y=3 得左右 X=4.1025/5.8975，三个局部 normal 均 +Z，中心 X=5。仅算法数值演算，不表示 float264 的物理单位或语义已确认。
6. 标记 parent T=(5,3,.14)、q=identity、scale=(2,2,2)，marker p=(.2,-.5,0)：输出位置=(5.2,2.5,.14)，scale仍(2,2,2)；这显示位置 marker 没有另外乘2。normal rotation 的具体 q 保留为 helper(n)。

## 8. 旧状态变化与未决

已确认：producer iter_modified；cached Transform 48B 查表；非缓存分支使用传入当前 wall curve /当前 collision width，故这些输入一旦改变并进入生成，会改变端点、弦中点、yaw、N 段楣梁位置。函数没有在所述范围计算 old/new transform lerp。

未确认：所有 dirty 传播条件、缓存刷新 producer、raw wall tag 的枚举语义、float264 语义、主窗台主体网格、gothic 特殊 shader 的每顶点消费、所有 optional k/ceiling 分支在实际玩法条件下的触发、非法/退化宽度和 wrap seam 的最后视觉效果。不要用“取了旧缓存”直接推断存在动画、惯性或延迟更新。

风险：静态恢复覆盖了选定范围与一组确实相连的调用，仍缺最终渲染/运行时验证。上述动态墙厚与三维倾角算法未在本段发现；这不等于整个游戏没有这些机制。原游戏和存档未修改；本篇仅补充正式研究文档。

第十五轮补充：[64](64-tiny-glade-building-kit-and-asset-assembly.md)直接解析选定窗资源并显示原坐标叠合图，[65](65-tiny-glade-window-holes-and-lantern-components.md)核对主窗体、glass、楣梁及gothic帽的实际请求配对。普通窗台资源存在，但其当前主体生成路径仍未完整确认；不把资源存在当成每窗必生成。
