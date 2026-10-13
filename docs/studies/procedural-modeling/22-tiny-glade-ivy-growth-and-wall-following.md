# Tiny Glade 常春藤：生长与贴墙

常春藤使用沿墙距离和高度组成的局部坐标推进，再转换到墙的一侧；空间方向噪声、跨墙检测、窗洞排除和末点动画分别约束这一过程。它没有在本轮证据中表现为完整寻路或植物物理模拟。

起点和状态见 [21](21-tiny-glade-ivy-roots-and-state.md)，完成事件后的枝叶消费见 [23](23-tiny-glade-ivy-leaves-and-rendering.md)，变化后的修剪见 [24](24-tiny-glade-ivy-pruning-and-updates.md)。制品身份、覆盖和复核见 [25](25-tiny-glade-ivy-evidence-ledger.md)。

## 证据与范围

只读分析发行版 `tiny-glade.exe` 与匹配 PDB；没有运行、附加或修改游戏，没有读取存档。证据是 DbgHelp 符号范围与 Capstone 5.0.3 x86-64 静态线性解码，不是源代码或 REA 反编译结果。下文地址均为 RVA。EXE SHA256 为 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`。16 个唯一范围合计 14,064 字节，全部完成线性解码；完整解码并不保证恢复全部运行路径或类型。

入口范围：ivy_grower BB28C0/7723B；closest_segment_index BB46F0/635B；get_wall_double_sided_normal BB4970/443B；intersect_ivy_growth_w_wall_segment BB4B30/805B；IvyDirectionProposer.get_direction A76040/1051B；WallCoord.into_world_space C67380/659B。范围 SHA、调用与常量引用在四份 `*-decode.json` 和对应 `.asm.txt`；findings.json 汇总该账本。算法表达式是指令归纳，算例都是构造输入，不是运行游戏测量。

## 1. 方向不是每帧随意抽取随机向量

get_direction A76040 先令 Q=P/2.8，并调用噪声入口 14A2190：

```
a = N_this(Q + (-23, -40, -32.5))       // A760C9
b = N_this(Q + (12.03, 67, 785))        // A760FC
c = N_this(Q + (-12.03, -.82, -785))    // A7612F
g = b + (1-c)*.35 + c*.6 = b+.35+.25*c
h = clamp(3*Q.y, 1, 8)
v = normalize((a*h, g))
```

g 运算见 A76142..A7615F，h 见 A762AD..A762E4，首次归一化见 A762E9..A76307。因此高度控制水平扰动倍率，g 有向上偏置，但不能保证始终向上。

另一噪声对象位于 this+78。A76170..A7628C 将传入 64 位标量经过乘法/旋转等确定性整数运算，构造三个浮点数 u0/u1/u2∈[0,1)，构造方法是把整数高位装入 `0x3F800000` 的尾数再减 1。增长调用 BB3229 的该标量来自 Ivy+20；创建与修剪消费者已核该字段是 IvyID，不能叫 WallID。

```
n = N_this+78(Q + (-24-100*u0, 7+100*u1, 5.5-100*u2))
alpha = clamp(n+.5,0,1)
theta = (alpha*80-(1-alpha)*80)*pi/180
d = normalize(Rz(theta)*v)
```

噪声调用 A7629C；角度运算 A7631A..A7633E；A7634B/A76358 调用 sinf/cosf 形成半角四元数，最后 A76402..A76423 再归一化。这是 −80°..+80° 的旋转。尚未分析噪声对象构造配置与 14A2190 内部算法；不能从名字确定噪声类型、频率或给定 IvyID 的真实输出。

构造算例：P=(0,2.8,0)，假设四个噪声输出 (a,b,c,n)=(.3,.4,.2,0)，则 h=3、g=.8，v≈(.747409,.664364)，theta=0；一次 .21 步给出墙坐标增量≈(.156956,.139516)。这些噪声值是演算假设。

## 2. 附着候选的评分与限制

closest_segment_index BB46F0 读取 56B WallSegment 记录：A/B 在 +0..+C，两个标量 sA/sB 在 +10/+14，端点限制量 hA/hB 在 +18/+1C，WallID 在 +28。限制量来源未追，不直接命名为地形高度。

BB47AC..BB47B5 先跳过两端都超过阈值的线段；BB47BB..BB4807 计算：

```
D=B-A
t=clamp(dot(P-A,D)/max(dot(D,D),1e-20),0,1)
h=(1-t)*hA+t*hB
N=(-D.z,D.x)/length(D)
score=abs(dot(N,A-P)) + 100*length(D)*abs(t-t)
```

若 h 超过阈值，BB4815..BB4828 跳过。第二个评分项在发行版指令 BB4833 `mov xmm5,xmm2`、BB4836 `sub xmm5,xmm2` 中确实相减同一个值，有限 t 时为零；不能擅自改为未夹紧参数减夹紧参数。评分因此接近无限直线距离，而不是有限线段端点的欧氏距离。初始最佳评分 100（BB476D），只接受严格更小评分，平分保留先前记录。返回记录包含 index、score、lerp(sA,sB,t)。

grower 在 BB2F82 传入 .5 阈值，并要求 score<.365（BB2F92..BB2FA5）。投影分母有 1e-20 下限，但法向量除以 length(D) 没有看到对应零长度保护。

普通算例：A=(0,0)、B=(10,0)、P=(4,.2)、sA=0、sB=10、hA=hB=0，则 t=.4、score=.2、s=4，可过 .365 附着门槛。边界算例 A=(0,0)、B=(1,0)、P=(10,.1) 时 t=1、score=.1；虽然 P 离端点约 9.00056，仍有很小评分。这是该函数实际评分的限制，不能宣传为精确最近线段算法。

## 3. 墙坐标映射与双面法向

WallCoord.into_world_space C67380 输入墙坐标 (s,y)、曲线与 side。曲线长度来自 curve+30。C673B6..C673EB 检查长度非零、s≤L、u=s/L∈[0,1]，不合法进入 panic 路径。get_coord_at_u 19A9060 返回段索引与局部插值 t；C6742C..C67447 求 Q=(1-t)A+tB，C6748B..C674CA 求 T=normalize(B-A)、N=(-Tz,0,Tx)。C674DB..C674F1 的 .63*.5 给出 .315。

```
side=false: world=(Q.x,y,Q.z)+.315*N
side=true:  world=(Q.x,y,Q.z)-.315*N
```

没有沿法向改写 y。算例：曲线 (0,0)→(10,0)，s=4、y=2，side=false 得 (4,2,.315)，true 得 (4,2,-.315)。这是游戏坐标中的浮点数，不确定物理单位。这里的 world 是该 CPU 转换函数输出的三维生成坐标；枝条顶点程序还会给两端 Y 加地形采样高度，不能直接把这里的 y 当最终可见世界高度。

get_wall_double_sided_normal BB4970 同样取得当前曲线段 Q/T，计算 cross=T.x*(P.z-Q.z)-T.z*(P.x-Q.x)；BB4A8A..BB4A8D 在 cross<0 时输出 −N，否则 +N。横向直墙的正 z 一侧返回 (0,0,1)，负 z 一侧返回 (0,0,-1)，中心线上选择 +N。局部零长度段仍属于未验证退化情况。

## 4. 单个生长步与窗洞避让

grower 中 r10=Ivy+90。Ivy+20 为 IvyID，+60 为 WallID。BB2DB3..BB2DB7 在 deque 点数≥Ivy+50 上限时跳过；这不是总长度上限。Ivy+88 为独立延迟量：大于 .001 时 BB2D00 减去资源 +28 的帧增量再跳过。blocked 字节 +8C 为真时，仅匹配当前 WallID 的墙变化事件才能解除（BB2D6E..BB2DA3）。

普通候选的方向来自末点 P 调用 BB3238→A76040。BB32A3 调用 get_approx_u_from_pos；令 s=uApprox*curveLength。方向 (dx,dy) 是墙面二维方向：BB338D..BB339F 计算 Δs=.21*dx、newY=P.y+.21*dy。若末点对当前段的 cross<0，则 BB3416..BB3433 反转 Δs；否则保持。newS 超出 [0,L] 时 BB344D/BB3457 跳过；此路径没有看到闭合曲线周期绕回。

高度门槛来自 PublicWallState 原始字段，必须保留分支而不能凭字段猜屋顶类型：

```
if wall[+2A0] byte == 1: threshold=wall[+288]+.2
else if wall[+258] dword < 2: threshold=wall[+288]-.79-.1
else: threshold=wall[+288]-.46
```

见 BB3465..BB34AA 与 BB399D。普通候选先允许等于门槛；最终候选 BB3CF6 则要求严格小于门槛。BB34E4 调用 WallCoord.into_world_space；BB34F1 取 PrevWallHoles。

窗洞测试点值得注意：BB3519 读取 wall+290，BB352F 乘前面的 uApprox，BB3534 取末点 y；BB353D 的目标 7EE60 已解码为一个 `ret`，不会改写输入。查询点是 `(uApprox*wall[+290],lastPoint.y)`，不能自动等同候选 newS/newY，也不能把 +290 与 curve+30 认为同一长度。洞记录步长 20B，仅 +10 类型字节为 0 才测试（BB3569）；bbox 四边扩张 (-.1,-1,+.1,+1)（BB3580），调用 DEEC60.contains（BB359D）。包含时 BB35C6 将 Ivy+8C=1 并跳过新增点。

普通贯通算例：长 10 的直墙，末点 (4,2,.315)，方向 (.6,.8)，当前侧 cross≥0，则 newS=4.126、newY=2.168，世界候选 (4.126,2.168,.315)。假设高度门槛足够且无洞命中，3D 位移 .21，小于最终 .42 上限。洞算例：bbox=[3.8,1.5,4.2,2.5]，扩张后 [3.7,.5,4.3,3.5]；若当前查询点 (4,2)，生长被阻塞。这里要另假设 wall+290 使查询 s=4。

## 5. 跨墙检测、沿角转向和退回

BB3649 用起点 P 与普通候选 E 查询 WallSpatialHash。15E0E90 retain 比较每段 +28 的 WallID，去掉当前墙。15F9560 调用 BB4B30（15F95E0/15F96D4），只保留相交结果，形成 24B 原始记录：+0/+4 为交点 XZ、+8 为到 P 的距离、+10 为 WallID。符号里的逻辑 tuple 字段顺序不等于内存顺序。grower 在 BB3E83 或 BB3E9C 排序，再读取首条（BB36EB）；比较器未恢复，因此不能确认距离升序。

intersect_ivy_growth_w_wall_segment BB4B30 把每段当作有厚度的矩形带。M=(A+B)/2，T=(B-A)/|B-A|，N=(-Tz,Tx)，局部坐标是 `(dot(X-M,N),dot(X-M,T))`；bbox 范围为法向 ±.315、切向 ±|B-A|/2（BB4C38..BB4C85）。DEE740 以逐轴 slab 法求线段进入/离开参数：

```
tEntry=max(axisMinRatios); tExit=min(axisMaxRatios)
拒绝 tExit<tEntry 或 tEntry>1
tEntry>=0: hit=P+tEntry*(E-P)
tEntry<0: 只有起点严格处于 box 内才返回 P
```

起点在边界不属于严格内部（DEE7FC..DEE810）。平行方向依赖 IEEE 除法行为，未见专门退化分支。BB4C95 将 hit 转回世界，BB4D47..BB4D5D 投影至段中心线得到 Q，生成 Q±.315N；BB4DAB..BB4DDE 选择更靠近起点 P 的面，距离平分选择加号面。算例：A=(0,0)、B=(10,0)，P=(5,.5)、E=(5,0)，得到上侧交点 (5,.315)；E=(5,.4) 时不进入墙带。

目标墙查找成功后，用目标墙法向 N 及旧曲线投影 Qsrc 修正剩余运动：BB39DB 调用 Curve.project_point，BB3A88..BB3B14 实际执行两次叉积与归一化：

```
V=normalize(Qsrc-H)             // 只用水平分量
W=normalize(N cross (N cross V))
r=max(length(E.xz-P.xz)-length(H.xz-P.xz),0)
finalXZ=H.xz+r*W.xz
finalY=E.y
```

这是负的切平面投影方向，不是看到名字就推断的寻路器。剩余距离见 BB3B2D..BB3B73，合成见 BB3B76。目标/旧墙查找失败，以及修正候选 3D 距离≥.42（BB3BB3..BB3BC6），都退回普通 E（BB3BD2）。最终还有 u∈[0,1]、高度严格门槛、总位移<.42 的检查（BB3C7E..BB3DDD）。未恢复 degenerate cross/zero vector 的处理，不能保证各种尖角均能通过。

局部公式算例（不声称所有上游空间查询都能产生此组合）：N=(1,0,0)，Qsrc-H=(0,0,-1)，所以 W=(0,0,1)。P=(0,2,0)、E=(.1484924,2,.1484924)、H=(.1,2,.1)，普通水平距离≈.21，已走≈.141421，剩余≈.068579；转角结果≈(.1,2,.168579)，总位移≈.196<.42，可通过距离门槛。若同样的几何修正超过 .42，则使用 E。

## 6. 新点以短动画展开，再发布脏段事件

BB3DDF..BB3DED 把旧起点 P 作为 add_point BB3E07 的位置，而不是立即写最终候选；BB3E1E 设置 Ivy+68=1，将起点保存 +6C/+70/+74，目标保存 +78/+7C/+80。因此新增点最初与起点重合，再移动到完整一步的终点。

Ivy+68==1 且点数>1 时 BB384A..BB387A 更新：`a=clamp(Ivy[+84]+delta/.075,0,1)`，把 a 写回 +84；BB3880..BB38ED 将最后点位置改为 `lerp(start,target,a)`。delta 来自资源 +28，具有帧增量行为但资源完整类型未恢复。a>.99 时 BB38F9..BB390E 清零 +68 与 +84。剪枝端写零这两个字段的意义与该动画状态相符。

完成时 BB391D 调用 Ivy.last_segment_point_ids，随后 BB3960..BB3984 追加一个 32B 事件，实际四个 64 位字段为：+0 资源 +40 的值，+8/+10 两个末段 point ID，+18 IvyID（Ivy+20）。BB3988 递增资源 +40。事件完整类型与 +0 的业务名字未恢复，不能仅凭同址模板名字称为历史记录或渲染命令。

算例：delta=.025，动画初值 a=0，则三次更新的 a 为 1/3、2/3、1。上文直墙候选最后点依次约 (4.042,2.056,.315)、(4.084,2.112,.315)、(4.126,2.168,.315)；第三次超过 .99、清零动画并追加末段事件。该算例假定没有外部剪枝/墙变化。

## 未知、未做与限制

未运行游戏，也没有动态验证可见生长速度、真实随机方向、闭墙表现或窗口特例。没有安装新工具或改任何游戏文件。缺失：FastNoise 对象构造配置/内部算法；跨墙排序比较器方向；PublicWallState+258/+288/+290/+2A0 的完整业务语义与 +290 来源；端点限制量 +18/+1C 来源；delta 资源类型；32B 事件完整类型；零长段、平行 slab、两次叉积归零等退化处理。符号同址 alias 只用于线索，不据此确定真实 callee。没有证明最短路径、全局求解器、恒向上生长或真实物理单位。风险是静态语义与完整运行条件之间仍有缺口；已明确保留这些边界。

已回答：方向的局部公式、附着评分、墙坐标变换、步长和墙侧、洞口阻塞、跨墙余步修正、展开状态与枝段事件。部分回答：噪声实际输出、转角候选优先级及退化情形；完整调度和运行画面未回答。
