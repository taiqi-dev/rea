# 沙堡：湿沙颜色、水体折射与光照

后续 [08](08-material-bindings-render-state-and-invalidation.md) 补齐实际场景组件到 Material/Shader/纹理的引用，以及所选 Forward 的 blend/depth 状态；本篇公式证据保留，运行表现仍未验证。

本篇补[表面网格研究](05-surface-mesh-and-water-rendering.md)没有展开的美术表现。新证据来自同一安装版本的 Shader 参数表、沙面顶点/片元和水面片元指令；没有启动游戏。可以确认湿沙过渡、随流动变化的纹理、屏幕空间折射、随距离衰减的水底颜色和方向光高光。实际材质数值、最终混合状态、玩家画面与帧耗时仍未测得。

## 证据身份和参数连接

输入为 `C:/Software/Steam/steamapps/common/Sandcastle Demo/Sandcastle_Data/sharedassets0.assets`，身份沿用[04 的文件记录](04-gpu-simulation-and-brush.md#证据位置与读取方法)。Shader 605 是 `Lit/Sand`，587 是 `Lit/Water`；两者的 LZ4/DXBC 范围和解码见[05](05-surface-mesh-and-water-rendering.md#复现入口和验证范围)。本篇使用其既有反汇编中的 `shader-605-0-01`（沙顶点）、`605-0-05`（沙片元）、`587-0-03`（水片元）。下述指令编号为文件内编号，不是原工程源码行。

新增[参数读取器](tools/surface_probe.py)读取**调用者指定的对象内表边界**：605 的名称表 `0x98`、常量缓冲表 `0xbe0`；587 分别为 `0xb0`、`0xca8`。名称索引、参数数组计数、16 字节参数记录、CB 大小和绑定相互核对。两个 `$Globals` 都声明 2304 B、绑定 slot 0；水的 `UnityPerMaterial` 是 16 B、slot 1。没有把任意字节中的同名字符串直接当成 uniform 绑定。布局参考 [AssetStudio 固定提交中的 Shader 表结构](https://github.com/Perfare/AssetStudio/blob/d158e864b556b5970709c2a52e47944d53aa98a2/AssetStudio/Classes/Shader.cs)，仅对本机选定表验证，不声称完整支持 Unity 6 Shader schema。

| 语义来自本地名称表                             | 原对象参数记录偏移           | GPU 位置                         |
| ---------------------------------------------- | ---------------------------- | -------------------------------- |
| 沙 `time`                                      | 605：`0xc10`                 | `cb0[113].y`                     |
| 沙 `sunDirection / moonDirection`              | `0xc20 / 0xc30`              | `cb0[123] / cb0[124]`            |
| 沙 `sunColor / moonColor`                      | `0xc40 / 0xc50`              | `cb0[125] / cb0[126]`            |
| 沙 `sandColor / wetSandColor / sedimentColor`  | `0xc60 / 0xc70 / 0xc80`      | `cb0[127] / cb0[129] / cb0[130]` |
| 沙 `unity_AmbientSky`                          | `0xc00`                      | `cb0[40]`                        |
| 水 `backgroundColor / sunDirection / sunColor` | 587：`0xd38 / 0xd48 / 0xd58` | `cb0[121] / cb0[123] / cb0[125]` |
| 水 `waterColor / waterScatteringColor`         | `0xd68 / 0xd78`              | `cb0[131] / cb0[132]`            |
| 水 `refractionFactor`                          | `0xda0`                      | `cb1[0].x`                       |

这些是参数名称与寄存器位置，不是实际海滩当前的颜色或可调范围；CPU 如何选择全部参数仍未贯通。

水的纹理表另从 `0xc60` 读取 4 条记录：`_ShadowMap→t0/s0`、`_CameraOpaqueTexture→t1/s1`、`_CameraDepthTexture→t2/s2`、`waterNormalMap→t3/s3`，都是二维纹理。它与水片元的资源声明及取样槽一致；实际纹理图像和相机副本生产仍未验证。

## 湿沙颜色与可见水面采用不同门槛

**观察。** 沙顶点指令 44–105 从四个水格插值，输出 `v4.z=W` 和 `v4.w=max(W−0.05,0)`。沙片元 40–49 则用原始水量分支混合颜色：

```text
q = saturate((saturate(W) − 0.001) / 0.019)
t = q² × (3 − 2q)
base = lerp(sandColor, wetSandColor, t)
```

**推导。** 在这条片元路径中，`W≥0.02` 已完全选择湿沙色，而可见水层使用的有效量要到 `W>0.05` 才为正。地面可以先显湿，再出现可见水面；两者不能用同一个布尔“有水”替代。这里说明的是着色器机制，未观测游戏实际过渡速度或默认水量。

沙片元 50–52 又执行 `lerp(base, sedimentColor, saturate(20×v5.w))`。其 `v5.w` 由沙顶点 29、35 从 Ground 格子的第四个 uint 提取 bit 4 起的 22 位量并缩放而来。这个连接已确认；此打包通道与模拟中的悬沙量如何精确对应，尚未闭合，因此没有把它写成“沙粒浓度乘 20”。

**构造演算 1。** 只考察第一层颜色混合，取 `sandColor=(0.8,0.7,0.5)`、`wetSandColor=(0.4,0.35,0.25)`：`W=0.0105` 得 `q=t=0.5`，颜色为 `(0.6,0.525,0.375)`；`W=0.03` 已完全选湿沙色，但有效水量仍为 0。输入是教学值，尚未加入沉积色、纹理或光照，不是游戏截图取样。

## 流动纹理与沙面光照

**观察。** 沙片元 0–33 从世界 XZ 乘 `0.3` 的二维纹理取样出发，引入 `time×0.5` 的相位；另以世界 XZ、流动分量和时间组成两组立体纹理坐标。两次 3D 取样按往返相位混合。34–39 对该项乘 `length(sunColor)×exp2(−1.731234×h)`，其中 `h=max(W−0.05,0)`；53–64 再按法线 Y、水量和覆盖平滑项调制并夹到 `[0,1]`。

这证明存在由流动、时间和水量驱动的**附加亮度纹理**，不能简化为一张静止沙色贴图。属性表有 `sandMap` 和 `causticsMap`；本篇没有完整解析其纹理槽与实际 Material 资源绑定，因此不把每次取样直接命名为已证实的焦散图，也未恢复其真实图像。

**观察。** 沙片元 65–82 对得到的颜色 `C` 计算：

```text
L = max(dot(N, −sunDirection), 0) × sunColor × shadow
  + max(dot(N, −moonDirection), 0) × moonColor
RGB = C × (unity_AmbientSky + L)
```

阴影来自一次比较采样；变换后 Z 不在 `(0,1)` 时使用 1。这里恢复的是所选变体的直接光照，不包含对所有 shader keyword、全局光照或其他 pass 的承诺。输出第四分量是沙的世界高度（指令 83），不能把它解释成沙的透明度。

## 水面法线与折射怎样避免拉进前景

**观察。** 水片元 3–41 先在世界 XZ 上取 `waterNormalMap`，用 `time×0.8` 形成相位，再根据限制在 `[-0.5,0.5]` 的流动分量取两组偏移法线纹理、混合、从 `[0,1]` 映到 `[-1,1]`，最后与几何法线相加并归一化。它使用流向来改变纹理运动，不要求每个细波纹都重建顶点。

42–59 以扰动法线 XZ 乘 `refractionFactor` 偏移屏幕 UV，并作屏幕比例修正。随后先取偏移位置的 `_CameraDepthTexture`，用 `_ZBufferParams` 转为线性深度，与当前水片元深度比较：若偏移位置更靠近相机，就退回未偏移的 UV。63–64 再取选定位置的深度和 `_CameraOpaqueTexture` 颜色。

**推导。** 这条回退用于限制折射把前景对象的颜色拖进水面；它是深度比较与 UV 选择机制，不表示已验证所有岸边漏色、遮挡或相机角度都没有瑕疵。完整渲染顺序和相机深度/颜色副本的实际成本还需抓帧。

## 水底距离衰减、视角变化与太阳高光

**观察。** 水片元 60–75 通过逆 VP 和所采深度重建背景世界坐标，求它与水面位置的欧氏距离 `d`，然后逐 RGB 通道执行：

```text
T = exp2(−8.656170 × d × waterScatteringColor) × waterColor
transmitted = opaqueRGB × T
```

`8.656170×ln(2)≈6`，所以指数项近似 `exp(−6×d×waterScatteringColor)`。名称确实叫 `waterScatteringColor`，但在所选代码中它进入的是**乘法衰减**，没有在此处另加体积散射积分。距离来自屏幕空间可见背景，不是沿折射光线真正穿越完整三维水体的长度。

令 `c=saturate(dot(viewDirection,N))`。76–106 先将透射色乘 `0.9+0.2c⁶`，再以 `0.75×(1−c)⁵×min(shadow+0.25,1)` 向 `backgroundColor` 混合。这是随视角变化的背景色混合；在所选片元中没有看见环境立方体贴图或反射射线，不能把它称为真实场景倒影。

107–116 计算 `H=normalize(viewDirection−sunDirection)`，用 `pow(saturate(dot(N,H)),1500)×sunColor×shadow` 加上很窄的太阳高光。输出 alpha 为 `saturate(100h)`；`h<约1e−5` 的片元先被丢弃。Shader tag 是 Transparent，但本篇未完整恢复 blend/depth state，不能仅凭 alpha 推断最后的像素合成方式。

**构造演算 2。** 取 `d=0.5`、`waterScatteringColor=(0.2,0.5,1)`、`waterColor=(1,1,1)`：衰减约为 `(0.548812,0.223130,0.049787)`。仅表示该公式对不同通道的削弱；尚未乘背景色、视角项和高光。`c=0.5` 时背景混合系数在完全受光处为 `0.0234375`、阴影比较结果为 0 时为 `0.005859375`，也不是原作默认材质参数。

## 局部性与性能含义

美术变化与模拟成本要分开。已确认：湿色、纹理流动、法线扰动、屏幕空间折射在 shader 中完成，不能据此说每次水色变化都在 CPU 重建网格。沙顶点会读 Ground 并跨分辨率读取 Water；是否只更新局部模拟或碰撞另见[07](07-local-updates-readback-and-costs.md)。

所选沙片元有 1 次二维取样、2 次三维取样、1 次阴影比较取样；所选水片元在通过 discard 后有 3 次法线纹理取样、2 次深度取样、1 次背景色取样和 1 次阴影比较取样。它们是静态路径中的取样指令数，**不等于显存实际访问次数、GPU 时长或绘制次数**。水面覆盖面积、重叠、分辨率、贴图缓存、深度副本和其他 pass 都可能改变成本，未测量。

## 复现与验证

```powershell
python -X utf8 docs/studies/procedural-modeling/sandcastle/tools/surface_probe.py "C:/Software/Steam/steamapps/common/Sandcastle Demo/Sandcastle_Data/sharedassets0.assets" --object-id 605 --names-offset 0x98 --buffers-offset 0xbe0 --output .cache/procedural-modeling/sandcastle/art-followup/sand-parameters.json
python -X utf8 docs/studies/procedural-modeling/sandcastle/tools/surface_probe.py "C:/Software/Steam/steamapps/common/Sandcastle Demo/Sandcastle_Data/sharedassets0.assets" --object-id 587 --names-offset 0xb0 --buffers-offset 0xca8 --textures-offset 0xc60 --output .cache/procedural-modeling/sandcastle/art-followup/water-parameters-v2.json
```

输出只含表记录和位置；为保留证据，输出文件已存在时显式拒绝覆盖，复跑需换新的文件名。DXBC 复现命令见[05](05-surface-mesh-and-water-rendering.md#复现入口和验证范围)。本轮已通过两个选定参数表的计数/边界/CB 名称及绑定检查，并逐项核对上文指令和两组演算。Not Run：运行画面、完整材质绑定、所有变体、GPU 抓帧、实际帧时间和长期模拟表现。上述公式用于解释行为与独立设计，没有把恢复的 shader 作为可分发产品代码。
