# GPU：水、沙、挖掘与沉积实际怎样计算

沙堡的地表以二维格子保存高度、速度等压缩状态。笔刷先改这些状态，GPU 再根据邻格坡度、水量与流速继续更新。这里已有发行版指令证据；不是把常见流体公式套在游戏名字上。CPU 调度见[02](02-cpu-simulation-orchestration.md)，最终表面见[05](05-surface-mesh-and-water-rendering.md)。

## 证据位置与读取方法

源文件为本机 `Sandcastle_Data/sharedassets0.assets`，76,135,784 B，SHA256 `6dd7bb6bc7d926fd43c08d22c9c767b7edf531cf11a4a555fcd41830f2f9c721`。本次用户明确授权对指定游戏目录内取用文件计算摘要，仅作证据身份。文件是 Unity `6000.4.10f1`、SerializedFile 22、小端、无 type tree。对象表有 12,448 项，其中 ComputeShader 22 项；这个数量不是模拟系统数量。

使用[只读探针](../tools/unity22-compute-probe.py)按对象表定位 class 72，并对 DXBC 的声明总长、chunk 表和边界检查，再交给 Windows `d3dcompiler_47.dll` 的 [D3DDisassemble](https://learn.microsoft.com/en-us/windows/win32/api/d3dcompiler/nf-d3dcompiler-d3ddisassemble) 解码。没有执行游戏或 GPU 程序。Unity 容器布局参照 [AssetStudio 固定版本的读取实现](https://github.com/Perfare/AssetStudio/blob/d158e864b556b5970709c2a52e47944d53aa98a2/AssetStudio/SerializedFile.cs)，本探针只支持本次已观察的窄格式。

| 对象     | pathID / 原文件偏移 | 本轮解码                    |
| -------- | ------------------- | --------------------------- |
| Ground   | 640 / `0x311a080`   | 6 个 kernel，各有两份 DXBC  |
| Water    | 636 / `0x309ad60`   | 11 个 kernel，各有两份 DXBC |
| Readback | 646 / `0x313f590`   | 2 个 kernel，各有两份 DXBC  |

38 份输出对应 19 组；组内直接比较反汇编文本，19/19 相同。未把重复副本说成不同算法，也未推定实际运行选择了哪个副本。输出在仓库忽略目录 `.cache/procedural-modeling/sandcastle/dxbc/`；每条指令有编号和相对 shader 指令流的字节位置。下文编号均指第一份对应 kernel。普通输出会把极小浮点数打印为 `0.000000`，精确常数须读同名 `.hex.txt`，不能按显示零代入。

## 格子与两个分辨率

这些 kernel 使用 `StructuredBuffer/RWStructuredBuffer`，格子 stride 是 **16 B**，线程组为 **32×32×1**；不是每格一个物理沙粒。地址为 `y×resolution.x+x`，四邻访问夹到边界。

Ground 与 Water 有各自的 resolution。Ground kernel 将沙格中心先归一化，再映射为 `uv×waterResolution−0.5`，读取四个水格、取小数部分作双线性混合。`Ground-02` 指令 90–134 与 `Ground-03` 指令 19–92 建立了跨分辨率取样的实际路径。未从这条代码推定默认分辨率数值。

**构造演算。** 若水格分辨率是沙格的两倍，一个沙格中心映射到水网格坐标 `(20.25,8.75)`，就使用 `(20,8),(21,8),(20,9),(21,9)`，权重为 `0.1875,0.0625,0.5625,0.1875`。这里的分辨率比例与坐标是教学输入，不是读取的默认设置。

## 沙为什么能堆住，又为什么会塌

`Ground/VelocityIntegration` 的 DXBC 原文件范围为 `0x311c24c`、8,780 B。已读出的主链为：沙高的四邻差 → 坡度 → 水量相关粘着门槛 → 重力驱动与水流侵蚀 → 阻尼 → 小噪声 → 限速 → 邻速平滑。

常量缓冲字段名与位置在对象自身的 `$Globals` 参数记录中交叉核对。例如 `stickiness` 为字节偏移 `0x9bc` 即 `cb0[155].w`，`damping` 是 `cb0[155].z`，`noiseFactor` 是 `cb0[155].y`，`velocityKappa` 是 `cb0[156].y`。这是 GPU 收到的参数位置，不能冒称当前玩家设置值。

令 `W` 为四水格插值得到的水量，`s` 为收到的 stickiness，`g` 为 shader 计算的带方向坡度。指令 167–181 的门槛部分可重组为：

```text
stick = s × (1 + 19 × saturate(20W))
slopeDrive = saturate(length(g) − stick)
gravityDelta = g × slopeDrive × gravityForce × deltaTime
```

后续指令 192 对该重力增量再乘 **0.04**。水流作用另用 `pow(saturate(W−0.05), waterErosionAmountGamma)`，乘水速度与 `waterErosionFactor`，再加入速度；这条分支同时受水量与流向影响。指令 194–196 用 `v−v×damping×deltaTime` 衰减；197–219 用格索引和 frameCount 生成两个扰动分量后乘 `noiseFactor×deltaTime`。220–229 做模长限速，并用四邻速度和本格新速度进行 `(neighborSum+k×v)/(4+k)` 混合。

**门槛演算，非整帧模拟。** 取 `s=0.1`、`|g|=0.8`：`W=0` 时门槛 0.1，`slopeDrive=0.7`；`W=0.05` 时门槛 2.0，`slopeDrive=0`。这说明此处水量能增强保形，但不等于水越多全局越稳，因为水流侵蚀是另一项，最终结果还受输运、沉积与参数影响。

## 堆积、侵蚀与沉积不是同一个步骤

`Ground/HeightIntegration` 为 `0x311a2d8`、7,844 B。它先按四邻速度方向选择上风输入、更新沙高，随后读取水速和水量，比较当前悬沙量与可承载量。指令 172–178 实际执行速度模长的幂函数及容量缩放：

```text
wet = saturate(30 × max(W−0.05, 0))
capacity = wet × sedimentCapacity × pow(length(waterVelocity), sedimentWaterSpeedGamma)
```

指令 185–210 比较悬沙量 `S` 与 capacity：不足时从地表转入悬沙；超出时从悬沙转回地表。两方向分别乘 `sedimentSuspension` / `sedimentDeposition`，并乘由水格另一个 4 bit 通道插值得到的 `f=1−q`。这个通道的完整美术/物理语义尚未独立确认，不将它改名为孔隙率或压实度。GPU 公式中不能擅自再添一个 deltaTime，CPU 是否预缩放这些系数以[调度报告](02-cpu-simulation-orchestration.md)为准。

**构造演算，仅取局部交换分支。** 假定 `capacity=0.6,S=0.2,suspension=0.1,f=1`，交换量为 0.04，地表减少 0.04、悬沙增至 0.24。若 `capacity=0.2,S=0.6,deposition=0.25,f=1`，则沉积 0.1，地表增加 0.1、悬沙降到 0.5。这能解释流速变化造成搬运与堆积；不证明整张地图或长时间运行严格守恒，后面还存在限界、量化和输运。

## 挖掘与倒沙怎样改形

`Ground/Paint` 为 `0x311f69c`、8,916 B。它先把每格中心映到世界 XZ，再经 `brushWorldToObject` 映到模具坐标。可平铺坐标；采样模具纹理的 X/W 通道，分别参与高度目标与覆盖。形状分支计算圆形的欧氏距离、方形的最大绝对坐标、菱形的绝对坐标和。覆盖要求 `0<distance<1`；中心与边界的确有明确比较，不能擅自把端点改成闭区间。

距离变成 `t=1−min(distance,1)` 后，`brushEasing` 选择常量、平方、三次、圆弧或指数等边缘过渡。最终权重是纹理覆盖×形状资格×easing。后半按 `brushOperation` 处理状态，例如操作 0=Add 增加、1=Sub 减少、2=Blend 向目标插值、4=Smooth 向四邻均高插值，7=Min/8=Max 则向受 min/max 限制的目标靠近；不是所有工具都只调用加减。铲子实际用 6=Push 结合容量和输入分支，见[03](03-excavation-and-mesh.md)。

**构造演算。** 某格距圆心归一化距离 0.5，纹理覆盖为 1，选平方 easing，权重为 `0.5²=0.25`。模式提供正向幅度 0.2，操作 0 会把高度从 0.8 推到 0.85；操作 1 推到 0.75，之后仍有高度上下界与打包量化。这是单个 kernel 的演算，没有把实际工具速度或每秒操作次数写成已知。

## 水实际做了什么

| kernel              | 第一份 DXBC 原文件偏移 | 本轮确认                                                    |
| ------------------- | ---------------------- | ----------------------------------------------------------- |
| UpdateFloor         | `0x309afb0`            | 读取地表缓冲，建立水底输入                                  |
| BlurFloor           | `0x309bd84`            | 邻域平滑；不代表所有地表视觉也被该步骤平滑                  |
| HeightIntegration   | `0x309c7c8`            | 四邻、方向选择、输运差与 deltaTime，随后限界/打包           |
| VelocityIntegration | `0x309d8e0`            | 水面高度差驱动、阻尼、邻速混合、干湿边界条件与限速          |
| Advection           | `0x309ef28`            | 速度反向追踪坐标，四格双线性读取并更新速度                  |
| UpdateAmount        | `0x309fdf8`            | 涉及空气、蒸发、波浪与 level；完整来源/边界公式尚未逐支恢复 |
| SubtractFloor       | `0x30a1d40`            | 读取并减去底高后夹到非负，重新打包                          |

例如 Water/Advection 指令 9–18 的取样坐标为：`uvBack=(cellCenter/resolution)−(velocity/beachSize.xz)×advectionFactor×deltaTime`，再转回格坐标并双线性读取速度。**构造演算**：海滩宽 10，X 速度 1，因子 1，步长 0.1，取样 UV 的 X 向后移动 0.01；并非每步只把某个水粒子移动到一个格子。

## 已验证与边界

确认的是本机 shader 的实际操作数和状态写回；38 份 compute DXBC 都通过 Windows 反汇编，19 组副本内容一致。水沙双分辨率、笔刷改高、坡度粘性驱动、输运与悬沙交换都有直接指令链。尚未实测帧时序、参数预缩放全貌、长期守恒、不同机器表现、完整水量边界或玩家画面。

开发者的一手访谈作为补充来源见[总览](README.md)；它与本轮发现相符，但不是上述常数或公式的来源。对该版本不能用“每粒沙做刚体”“三维粒子流体”或“纯水面贴图动画”替代已经观察到的格网计算。
