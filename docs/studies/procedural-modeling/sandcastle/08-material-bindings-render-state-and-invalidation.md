# 沙堡：场景材质绑定、渲染状态与局部变化传播

> 后续 [09：相机纹理来源](09-camera-color-depth-resource-provenance.md)已接通颜色/深度附件、复制目标、真实全局 ID 字面量与水 Shader 取样；下文保留前轮范围。

本篇补 [06](06-surface-materials-and-effects.md) 留下的“实际材质和最终混合状态”断点，并与 [07](07-local-updates-readback-and-costs.md) 的全域 GPU 调度区分。只读输入为同一 Sandcastle Demo 安装版本的 `Sandcastle_Data/level0`、`sharedassets0.assets`、`GameAssembly.dll`，身份沿用 [01](01-artifact-and-method-map.md) 与 [04](04-gpu-simulation-and-brush.md) 的制品记录。未运行游戏或修改原文件。

## 场景组件确实指向这两份材质

`level0` 是 Unity SerializedFile v22、652 个对象，类型树未内置。用现有 `unity22-compute-probe.py` 的严格对象范围索引，场景 metadata 在 `0x4738` 给出三个外部文件；第二项的路径名位于 `0x477c` 附近，为 `sharedassets0.assets`，所以该场景 PPtr 的 `fileID=2` 指向这份资源文件。这里按外部表顺序解析，未从任意字符串出现位置猜 fileID。

| 直接链                                                              | 原文件证据                                                                                                                                                                  |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ground GameObject `pathID=72` → MonoBehaviour `541` → `Material 20` | GameObject 名称 `Ground`；组件位于 `level0:0x14500`、其对象内 `0x64` 为 PPtr `(fileID=2,pathID=20)`                                                                         |
| Water GameObject `pathID=44` → MonoBehaviour `511` → `Material 41`  | GameObject 名称 `Water`；组件位于 `level0:0x137b0`、对象内 `0x7c` 为 PPtr `(2,41)`                                                                                          |
| `Material 20` → `Shader 605`                                        | `sharedassets0.assets:0x51c80` 的 Material 名为 `Sand`，对象内 `0x08` 起的 PPtr 为 `(0,605)`；Shader 605 实际名 `Lit/Sand`，见 [05](05-surface-mesh-and-water-rendering.md) |
| `Material 41` → `Shader 587`                                        | `sharedassets0.assets:0x56fc0` 的 Material 名为 `Water`，对象内 `0x0c` 为 `(0,587)`；Shader 587 实际名 `Lit/Water`                                                          |

上述 MonoBehaviour 的未命名字段位置只按实际 PPtr 数据陈述；`Ground`/`Water` metadata 各有 `material` 字段，与引用位置和对象归属吻合，但本篇不把缺失 type tree 的整份组件布局宣布为已还原。

新增的有界 [Material 读取器](tools/material_binding_probe.py) 对选中的两个 class 21 对象逐项读取字符串、PPtr、纹理/标量/颜色属性，要求 Shader 与纹理 PPtr 在同一文件解析到相应 class，检查计数、边界、重复属性名与尾部字段。它没有扫描猜测全项目的 Material schema。实际绑定如下：

| Material → 属性 → 对象                              | 资源类型与对象偏移               | 同份 Material 的数值                                                                                               |
| --------------------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `Sand 20` → `sandMap` → `232 Sand`                  | Texture2D class 28，`0x24b6e60`  | `sandColor=(0.92549,0.88627,0.72549,1)`                                                                            |
| `Sand 20` → `causticsMap` → `932 Caustics`          | Texture3D class 117，`0x32f1140` | `wetSandColor=(0.90600,0.81038,0.63329,1)`                                                                         |
| `Water 41` → `waterNormalMap` → `307 WaterNormal2D` | Texture2D class 28，`0x27649a0`  | `refractionFactor≈0.01210`；`waterColor≈(0.96034,0.98580,0.99954,1)`；`waterScatteringColor≈(0.56838,0.35686,0,1)` |

对象名和 PPtr 是资源事实；沙片元实际声明一个 2D 采样槽及一个 3D 采样槽，水片元的纹理参数表把 `waterNormalMap` 直接放在 `t3/s3`（[06](06-surface-materials-and-effects.md)）。沙的 `sandMap/causticsMap` 与 2D/3D 槽维度、取样路径相符，但没有单独解析其符号化 slot 表，因此不把 `t1/t2` 的名称配对称为已经直接证实。Material 中另存的 `_Surface`、`_SrcBlend` 等通用属性不代替实际 pass 状态。

## 沙和水的实际 Forward pass

共用 [Shader state 读取器](../tools/unity-shader-state-probe.py) 对调用者选定的 Shader 对象内状态前缀读取 8 个渲染目标的 blend 项和深度/剔除项。起点来自 `Forward` pass 名称的长度前缀：Shader 605 对象内 `0x24c`，587 内 `0x340`；记录按固定宽度与名称、状态尾端和原 DXBC 对象范围交叉检查。以下仅是**所选 Forward pass** 的实际序列化值：

| 状态                     |                      Lit/Sand 605 |                                     Lit/Water 587 |
| ------------------------ | --------------------------------: | ------------------------------------------------: |
| RT0 颜色 src / dst / op  |   `1 / 0 / 0`（One / Zero / Add） | `5 / 10 / 0`（SrcAlpha / OneMinusSrcAlpha / Add） |
| RT0 alpha src / dst / op |                       `1 / 0 / 0` |                                      `5 / 10 / 0` |
| ZTest / ZWrite / Cull    | `4 / 1 / 2`（LEqual / On / Back） |                 `4 / 1 / 2`（LEqual / On / Back） |
| ColorMask / AlphaToMask  |                          `15 / 0` |                                          `15 / 0` |

因此水 Forward pass 确实按其输出 alpha 与已有颜色混合；[06](06-surface-materials-and-effects.md) 所得 `alpha=saturate(100h)` 在薄水边界会影响合成权重。水 pass 同时启用深度写入，这一点不能从 `Transparent` tag 或 Material 的通用 `_ZWrite` 属性替它推断。Shader 587 的序列化 tag 确有 `QUEUE=Transparent`；实际 `BeachRenderPipeline.Render` 原生调用顺序为 `RenderOpaques` (`0x18046F890`) → `RenderBehind` → `CopyOpaqueDepth` (`0x18046D9F0`) → `RenderTransparents` (`0x180470BB0`)，位于 `0x18047167B–0x1804716E1`。水片元取 `_CameraOpaqueTexture`、`_CameraDepthTexture` 的槽在 [06](06-surface-materials-and-effects.md) 已验证。`CopyOpaqueDepth` 的方法名与顺序只能证明透明绘制前存在此调用，尚不能单凭它断言两张输入纹理均由该方法生产、句柄相同或分辨率/过滤方式；具体资源生产者与每帧拷贝耗时仍未证实。

## CPU 写入如何进入 shader，而局部刷子不必改材质

`Game.Run` (`0x18048D110–0x18048D14C`) 明确先调用 `Game.SetGlobals` (`0x18048DEA0`)，再调用 `Beach.Run`；后者驱动 Ground/Water。`Game.SetGlobals` 在 `0x18048DF67` 写入 `Game.playTime`（实例 `+0x24`）到全局 float setter，且在 `0x18048DFF4–0x18048E14A` 从 Beach 范围生成最小值、最大值和双倍范围向量，经全局 vector setter写入。Shader 参数表有 `time`、`beachSize` 等相应名字；**静态字符串 ID 本轮尚未逐一反解**，因此这些同名关系保留为由类型、算式和消费槽支持的匹配，不声称每个写入的属性名都已直接绑定。

`Ground.Init` (`0x18044FDC4–0x18044FDD3`) 把本层 `+0xC0` 的 GPU cells buffer 交给 shader 全局 buffer setter；`Water.Init` (`0x18048305E–0x180483074`) 对 `+0xF8` 的水 buffer 做同样操作。该 setter 的原生包装 `0x181C1AC40–0x181C1AC8F` 先将属性字符串转为 ID，再转发 buffer 原生句柄。沙顶点 Shader 605 的 `t0/t1` 和水顶点 Shader 587 的 `t0/t1` 均是 stride 16 的结构化资源，取样地面与水状态（[05](05-surface-mesh-and-water-rendering.md)）；Shader 名称表实际包含 `groundCells`、`waterCells`。这建立了“模拟 GPU buffer → 全局绑定 → 表面顶点位移/湿色”的生产和消费桥，但两个静态属性字符串的字面值仍需再解码才能把每个 slot 的 ID 链称为完全闭合。

`DayCycler.Update` (`0x180446880–0x1804470F0`) 从对象 `+0xEC/+0xFC` 的两个颜色值分别调用全局颜色 setter (`0x180446DB0–0x180446DEB`)，再从日/月光物体求方向并调用全局 vector setter (`0x180446DF0–0x180446ECD`)。DayCycler metadata 的末两字段为 `sunColor/moonColor`，沙/水 Shader `$Globals` 都有 `sunDirection`、`sunColor`，沙 Shader 还有 `moonDirection`、`moonColor`。这说明光色和方向由运行状态提供；其调度时刻和所有静态属性字符串未逐一恢复，不能用 Material 的静态颜色替代昼夜变化。

局部 Brush 修改的是 Ground/Water cells。材质上的贴图 PPtr、颜色常数和 pass blend state 在资源里独立保存；表面顶点/片元重新读取变化后的全局 buffer，湿沙色和水面形状随之改变。由此可推导，**一次局部刷子不必重新创建 Material 或改写贴图资源**；但 [07](07-local-updates-readback-and-costs.md) 已验证 GPU Dispatch 是整域，CPU 读回和碰撞另有周期，不可将“局部可见变化”说成整个更新链只访问局部。

**带真实材质参数的构造演算。** 沿用 [06](06-surface-materials-and-effects.md) 的湿色公式，设某格原始水量 `W=0.0105`、沉积混合因子为 0，平滑权重为 0.5，则此 Material 的第一层沙色约为 `(0.91575,0.84833,0.67939)`；之后仍会受到纹理、光照和其他混合。对水片元距离衰减，只人为令可见背景距离 `d=0.5`，将本 Material 的 `waterColor` 与 `waterScatteringColor` 代入 [06](06-surface-materials-and-effects.md) 的 `exp2(−8.656170×d×S)×waterColor`，所得 RGB 透射乘子约 `(0.17454,0.33794,0.99954)`。这不是场景中实际 d、最终 RGB 或截图取色。

## 复现、已答与边界

原始可复核输出仅置于 `.cache/procedural-modeling/render-chain-followup/sandcastle/`：`materials-20-41-v2.json`、`sand-forward-state.json`、`water-forward-state.json`、`DayCycler_Update.txt`、`Pipeline_Render.txt`、`Pipeline_CopyOpaqueDepth.txt`、`Pipeline_PerFrame.txt`。Material 探针调用示例：

```powershell
python -X utf8 docs/studies/procedural-modeling/sandcastle/tools/material_binding_probe.py "C:/Software/Steam/steamapps/common/Sandcastle Demo/Sandcastle_Data/sharedassets0.assets" --material-ids 20 41 --output .cache/procedural-modeling/render-chain-followup/sandcastle/materials-recheck.json
python -X utf8 docs/studies/procedural-modeling/tools/unity-shader-state-probe.py "C:/Software/Steam/steamapps/common/Sandcastle Demo/Sandcastle_Data/sharedassets0.assets" --object-id 605 --state-offset 0x24c --output .cache/procedural-modeling/render-chain-followup/sandcastle/sand-state-recheck.json
python -X utf8 docs/studies/procedural-modeling/tools/unity-shader-state-probe.py "C:/Software/Steam/steamapps/common/Sandcastle Demo/Sandcastle_Data/sharedassets0.assets" --object-id 587 --state-offset 0x340 --output .cache/procedural-modeling/render-chain-followup/sandcastle/water-state-recheck.json
```

输出文件须是新路径，工具拒绝覆盖。原生函数依据同版本 `codegen-map-all.json` 及本机 `dumpbin /DISASM:NOBYTES /RANGE` 有界截取。**已答**：实际场景组件到 Material、Shader、纹理的 PPtr，材质颜色/折射值，所选 pass 的 blend/depth/cull，CPU buffer 与颜色/时间生产者，以及管线透明绘制之前的调用顺序。**仍未串**：全部静态属性字符串到精确 slot、两张相机输入纹理各自的生产者与实际句柄、所有 Shader 变体/pass、实际场景摄像机副本参数与每帧帧耗。**Not Run**：游戏、渲染抓帧、屏幕截图、GPU/CPU 计时、跨图形 API 验证。独立项目可借鉴状态与渲染材质分离的原则，参数和素材应自行设计，不复制原游戏资产或恢复代码。
