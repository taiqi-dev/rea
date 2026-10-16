# 沙堡：湿沙到薄水的静态过渡链

后续[24：全局颜色写端与顺序](24-global-color-writers-and-order.md)已找到Configuration→GammaToLinearSpace→SetGlobalColor，并核对Shader声明属性与材质保存值的区别。本文以材质数值代入的例子继续只作构造演算，不能改称真实global或最终GPU颜色。

## 问题、制品与证据性质

本篇只问主地表在水量增加时，何时变成湿沙、何时出现可合成的薄水，以及颜色、法线和边缘各由什么控制。目标是 `C:/Software/Steam/steamapps/common/Sandcastle Demo`；本轮重读 `Sandcastle_Data/sharedassets0.assets`（76,135,784 B，Unity `6000.4.10f1`、SerializedFile 22、小端、无 type tree），并复用 `level0`（现为 96,756 B）及 `GameAssembly.dll`（现为 47,654,400 B）的既有链。身份范围和以前授权的摘要见 [01](01-artifact-and-method-map.md) 与 [04](04-gpu-simulation-and-brush.md)；本轮没有新算摘要，也不以相同长度证明制品逐字节未变。

新增的普通静态 raw 是 [本轮材质解析](../../../../.cache/procedural-modeling/static-art-followup/sandcastle/materials-current.json)（仓库忽略目录，**不是 REA Evidence**）。它由现成的 [Material 读取器](tools/material_binding_probe.py) 对当前文件的 pathID 20/41 重新解析产生；下述 DXBC、参数、pass 状态和原生调用片段均复用早先输出。此轮未再调用已超时且条件未变的 REA Ghidra procedure 搜索，因而没有新增 REA Evidence ID、运行态或抓帧证据。

## 资源到所选着色路径

`level0` 中 Ground 的组件 541 指向 `(fileID=2,pathID=20)`，Water 的组件 511 指向 `(2,41)`；外部表第二项是 `sharedassets0.assets`。[08](08-material-bindings-render-state-and-invalidation.md) 记录其原文件位置 `level0:0x14500+0x64`、`0x137b0+0x7c`。当前材质重读确认 `Sand 20 → Lit/Sand Shader 605` 与 `Water 41 → Lit/Water Shader 587`，前者绑定 Texture2D `sandMap → 232` 和 Texture3D `causticsMap → 932`，后者绑定 Texture2D `waterNormalMap → 307`。材质对象原文件起点分别为 `sharedassets0.assets:0x51c80` 和 `0x56fc0`；材质 JSON 的 `object_offset` 则是**对象内**坐标，不能当成文件偏移。

所选沙顶点 `shader-605-0-01` 和片元 `605-0-05`、水顶点 `587-0-01` 和片元 `587-0-03`，来自 [05 的 DXBC 范围账本](05-surface-mesh-and-water-rendering.md)。复用原始反汇编位于 `.cache/procedural-modeling/sandcastle/graphics/` 同名 `.asm.txt`；指令行的 `0x...` 是该 DXBC 指令流内偏移，不能当作 `sharedassets0.assets` 文件偏移。Shader 605 对象起点 `0x2fc0e80`、587 为 `0x2f34df0`；两者 LZ4 表起点及解出段范围见 `shader-605-index.json`、`shader-587-index.json`。现有解析解出 32/4 个 DXBC 记录，包括变体和 pass；本篇只对以上所选程序及其 [08 的 Forward 状态](08-material-bindings-render-state-and-invalidation.md)成立，实际帧选择仍需运行证据。

参数来源必须分层：沙 Shader 参数表将 `sandColor/wetSandColor` 接到 `cb0[127]/cb0[129]`；水 Shader 参数表将 `waterColor/waterScatteringColor` 接到 `cb0[131]/cb0[132]`，`refractionFactor` 是水 `UnityPerMaterial cb1[0].x`。所选水纹理表把法线 `waterNormalMap` 接 `t3/s3`，相机颜色/深度接 `t1/s1`、`t2/s2`，见 [06](06-surface-materials-and-effects.md)。材质重读提供序列化候选值：`Sand.sandColor=(0.925490,0.886275,0.725490)`、`wetSandColor=(0.906000,0.810376,0.633294)`；`Water.waterColor=(0.960344,0.985799,0.999542)`、`waterScatteringColor=(0.568383,0.356864,0)`、`refractionFactor≈0.01210`。颜色位于 `$Globals`，本轮没有完整追到每帧绑定值及覆盖顺序，故这些值用于**代入演算**，不称当前 GPU 寄存器读数。`sedimentColor` 也在 `$Globals`，但当前两份材质表没有相应键，实际来源未闭合。

本轮直接核对当前 JSON 中 `refractionFactor=0.01209999993443489`；旧 `render-chain-followup/sandcastle/materials-20-41-v2.json`、`materials-final-recheck.json` 也是此值。下文计算取 JSON 原始精度。

## 同一区域的两道门：湿色、可见水层

格网并非一格同分辨率。Ground、Water 各自保存 stride 16 B 的 packed cell；沙顶点 `605-0-01` 指令 44–105 将当前沙顶点 XZ 映到水网格，读取四邻 Water cell 并双线性插值，令结果为 `W_s`，送 `o4.z=W_s`、`o4.w=max(W_s−0.05,0)`。沙片元收到线性插值后的 `v4.z`，指令 40–49 形成：

```text
q = saturate((saturate(W_s) − 0.001) / 0.019)
wetWeight = q²(3−2q)
sandBase = lerp(sandColor, wetSandColor, wetWeight)
```

因此 `W_s≤0.001` 仍取干沙底色，`0.001<W_s<0.020` 平滑过渡，`W_s≥0.020` 第一层底色完全取湿沙；阈值是 shader 的无量纲 packed 水量解码后数值，本轮未建立它与世界米数或物理含水率的换算。`605-0-05` 指令 50–52 还按 `saturate(20×v5.w)` 向 `sedimentColor` 混合，53–64 又把纹理项、法线 Y、有效水量及高度覆盖项合成。因此第一层底色不等于输出 RGB。

水顶点 `587-0-01` 指令 13–60 在水网格读取四邻样本，分别构造 `floorHeight+max(W_i−0.05,0)` 并平均成顶点 Y；指令 70–78 又从当前水格独立解出 `h=max(W_c−0.05,0)` 送 `o4.w`。水片元 `587-0-03` 指令 0–2 在插值后的 `h<约1e−5` 时丢弃，其指令 117 写 `alpha=saturate(100h)`。所选 Water Forward RT0 用 `SrcAlpha/OneMinusSrcAlpha/Add`，ZTest LEqual、ZWrite On，见 [08](08-material-bindings-render-state-and-invalidation.md)。所以水在覆盖门打开后还经过透明度渐变；平均的水面高度与覆盖判断不是同一个取样量，岸边可出现混合/裁剪边缘。真实边缘三角形内的 `W_s`、`W_c` 与 `h` 会各自插值，**不能把下面的对齐输入误认为实际同一 cell 逐像素完全一致**。

**贯通构造演算。** 设某处两条路径恰好都收到相同 `W`、四邻底高均为 `0.20`、四邻有效水量相同，沉积混合先置 0，且只看首层底色和水 pass 的 alpha：

| 对齐输入 `W` | 沙的 `wetWeight` | 用本轮材质值计算的沙底色 RGB   | 水有效量 `h`、顶点 Y | 水片元与混合权重  |
| -----------: | ---------------: | ------------------------------ | -------------------- | ----------------- |
|     `0.0105` |            `0.5` | `(0.915745,0.848325,0.679392)` | `0`、`0.20`          | discard           |
|     `0.0300` |              `1` | `(0.906000,0.810376,0.633294)` | `0`、`0.20`          | discard           |
|     `0.0550` |              `1` | 同上                           | `0.005`、`0.205`     | 保留，`alpha=0.5` |
|     `0.0600` |              `1` | 同上                           | `0.010`、`0.210`     | 保留，`alpha=1`   |

例如 `W=0.055`、水片元已通过深度测试且下面正是沙面时，所选 RT0 状态给出 `C_out=0.5 C_water+0.5 C_behind`。`C_water` 仍由法线、屏幕空间颜色/深度、距离衰减、视角和高光产生；不能直接取表中湿沙色代替 `C_behind` 的真实渲染结果，更不能据此预测截图。实际四邻不齐、两网格分辨率不同、材质全局色被覆盖或片元插值时，表中 Y 和权重也会变。

## 湿沙法线、薄水法线与岸线特效范围

沙顶点 `605-0-01` 指令 28–41 从 Ground packed 字节构造法线 `o2.xyz`，沙片元 `605-0-05` 直接用 `v2.xyz` 做日/月方向光（75–82）；水量 `v4.z/w` 没有在该片元中改写法线。它另在 0–39 以世界 XZ、时间、流向两次采样 3D 纹理，34–64 按水量、法线 Y 与高度因子给沙面加亮度项。所选路径可确认**湿色先于可见水出现，沙面亮度随水/流动改变**；没有证据说湿色阶段就切换为另一张沙法线图。

水片元 `587-0-03` 指令 3–41 使用 `waterNormalMap` 的三次 2D 取样、流动分量和 `time×0.8` 构造扰动法线；42–59 以 `refractionFactor` 偏移屏幕 UV，并在偏移深度更靠近相机时回退原 UV。63–75 读取相机深度和背景色，以重建的水面至可见背景距离 `d` 计算 `exp2(−8.656170×d×waterScatteringColor)×waterColor`。以本轮材质序列化值、**教学假设** `d=0.5` 代入，RGB 透射乘子约 `(0.17454,0.33794,0.99954)`；随后还有视角背景色混合和太阳高光，不能把它叫最终水色。`refractionFactor≈0.01210` 是该材质读取值，不是屏幕像素偏移量；实际位移还取决于法线与 `_ScreenParams` 等。

对“泡沫”只做有界判断：所选 Sand/Water 材质属性、两份所选 Shader 参数表无 `foam/shore` 命名项，且 `587-0-03` 所选片元的透明度来自 `h`，其取样资源限于法线、深度、相机颜色、阴影；这里未找到独立的泡沫贴图或泡沫分支。可见岸缘仍可能由水量门、透明混合、深度、法线和沙面加亮共同形成。该阴性结果**不排除**其他 Shader/pass、粒子或场景对象做泡沫，也不证明游戏画面没有泡沫。

## 结论与验证边界

**Answered（所选静态路径）：** 场景材质引用；材质中两色、水色、法线贴图和当前折射值；水量从格网进入湿色与薄水覆盖的两条取样路径；`0.001/0.020` 湿色区间、`0.05` 水有效量基线、片元 discard 与 alpha 混合；沙/水各自法线和折射的消费链。复用 [04](04-gpu-simulation-and-brush.md) 的模拟生产与 [08](08-material-bindings-render-state-and-invalidation.md) 的 buffer setter/绘制状态，故局部笔刷改 cell 后有进入这两种外观的通路，但时延未测。

**Partial：** 材质序列化颜色到 `$Globals` 每帧寄存器的覆盖顺序、沙 2D/3D 纹理符号槽的直接配对、具体 Forward 变体的运行选择、沙与水网格在真实岸线的逐片元对齐、相机纹理格式/采样细节与最终深度合成。

**Unknown / Not Run：** 独立泡沫系统是否存在于未选范围；默认实际水量与速度、世界单位换算、玩家画面中何时可见、色彩管理后的像素值、运行时材质修改、帧耗时。游戏运行、进程附加、GPU/Unity、私人存档及截图均 Not Run，不能把上面的构造演算当作玩家观察。

本轮静态复读核对所选四份 DXBC 的上述指令编号及内偏移、两份 Shader 参数表、材质重读和 Forward RT0 状态；演算按公式复算。文档相对链接、目标/缓存路径和新增文件仅在本专题核查；未修改共享索引或旧报告。
