# SUMMERHOUSE：材质、像素化与相机的实际资源链

后续[22：像素网格与相机移动](22-pixel-grid-camera-motion-and-silhouette-stability.md)完整读取CameraController实际曲线及feature引用，补出150…300高度、整数截断与偶数目标量化；本文251仍是feature序列化初值，不是全程固定分辨率或轮廓稳定保证。

后续[19：调色板传播](19-palette-propagation-and-shared-state.md)完整解析三套Lake配色，将本篇Material57等共享引用接到实际颜色／发光写端，并补环境与粒子链。下文“三套配色尚未完整解码”保留为早期范围，不覆盖19的新证据。

**相机覆盖修订：** [12](12-mask-camera-filter-and-shader-data.md)确认主相机掩码759排除层8，feature471无法把它恢复；下文“层8落在feature范围”的事实不代表Mask进入主相机重绘。MeshRenderer启用字节也已从+14修正为+12，当前634个对象的旧投影值恰好不变。

**后续补证：** [07](07-pixel-blit-depth-and-local-render-route.md) 已按真实 LZ4 表解出 Shader 65，核实颜色/深度取样和 pass 混合状态。本篇“最终采样未知”保留为上一轮记录，以 07 的新增证据和剩余边界续接。

本篇续接[发行块与组合](04-packaged-blocks-and-combinations.md)和[保存及换色](03-save-palette-and-visuals.md)。目标是解释已发行资源怎样把方块变成可渲染对象，以及像素化是否接入相机。所有结论来自静态文件和托管 CIL；没有启动游戏或取得玩家画面。证据身份沿用[00](00-evidence-and-scope.md)：`Assembly-CSharp.dll` SHA-256 `f4e8bf23…8379de`、MVID `84569538-a19f-4c17-8ccf-f40b95e99253`；资源摘要和偏移以下逐项给出。本文的 Unity pathID、文件内字节偏移和 IL 偏移仅对本次包有效。

## 从预制块到表面材质

`sharedassets0.assets`（SHA-256 `6c82efff00e66f0655c17b4a7a79198116360c2cb02af0cf44b1a372539f4510`）的 `BuildingBlock` 根对象先经 Transform 子树到 GameObject，再经同一 GameObject 的 `MeshFilter`、`MeshRenderer` 找网格和材质槽。与上一章的 673 个 MeshFilter 相比，只有 634 个有对应 MeshRenderer；另外 39 个只有网格引用，例如某些碰撞或辅助几何，不能把 673 直接当作可见表面数。634 个 Renderer 的序列化材质槽均能解析到本文件的 class `21` Material；它们共使用 66 个不同 Material。**这是 prefab 集合的静态引用计数，不是任一帧的对象数、draw call 或 GPU 开销。** 完整逐对象连接见忽略目录 `.cache/procedural-modeling/summerhouse/visual-followup/visual-bindings.json`。

下面把[窗户配方](04-packaged-blocks-and-combinations.md#一条真实配方的贯通算例)用到的真实 prefab 接到表面。`fileID=0` 均表示 `sharedassets0.assets` 内对象；外部 Mesh 保留其原始 fileID，不猜外部文件。Renderer 后括号为序列化材质槽数，表中所列 Renderer 的 `m_Enabled` 字节为 1。

| 块根 / 子 GameObject                          | MeshFilter → Mesh                                      | MeshRenderer（对象偏移）                       | 材质槽，按序列化顺序                                                                                                                    |
| --------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `7196` Window 07 / Mask                       | `5715` → fileID `2`, pathID `10210`                    | `4659`（`4865248`，1）                         | `12` Mask                                                                                                                               |
| `7196` / Model 01                             | `5266` → `432` Window 07                               | `4542`（`4841272`，6）                         | `92` White 01、`85` Wall Base 01、`57` Glass 01 b、`58` Glass 01 c、`60` Glass Highlight 01、`83` Wall Base 01 c                        |
| `7510` Window 07 w character / Mask、Model 01 | `5231` → 外部 `10210`；`5596` → `432`                  | `5088`（`4946496`，1）；`4986`（`4926680`，6） | 与普通窗相同的 Mask 和六种主体材质                                                                                                      |
| `7510` / Character Model                      | `5784` → `584` Character Window Man Looking Up 01      | `4750`（`4881536`，9）                         | `44` Accent 01、`51` Accent 05、`42` Accent 01 c、`78` Skin 01 b、`79` Skin 01、`64` Grey 03、`62` Grey 01、`52` Black 01、`63` Grey 02 |
| `7510` / Eyes                                 | `5238` → `586` Character Window Man Looking Up 01 Eyes | `5121`（`4952152`，1）                         | `53` Facial Features 01                                                                                                                 |
| `7432` Awning 04 / Model 01                   | `5518` → `479` Awning 04                               | `4908`（`4911704`，2）                         | `44` Accent 01、`92` White 01                                                                                                           |

`7632` Window 07 (1) 与 `7196` 另有不同的对象身份，但分别使用同一个本地窗体 mesh `432` 和同一组主体材质槽。这样，组合成功后将一扇普通窗替换为人物窗，资源差异具体表现为**增加 Character Model 和 Eyes 两个带 Renderer 的子对象**，并复用窗体与遮罩。若只比较被替换的那一扇窗，序列化 Renderer 数从 2 变成 4、材质槽总数从 7 变成 17；这不等于运行时 draw call 恰好增加 10，材质合批、可见性与实际镜头都没有测量。

这批主体材质并非单纯的纯色名称。`Accent 01`（Material `44`，偏移 `286848`）和 `White 01`（`92`，偏移 `398352`）都指向本地 Shader `622`（偏移 `3832256`，序列化名 `Shader Graphs/LitColorTriplanarNormalAnimatedShimmer5`），材质的 `RenderType=TransparentCutout`、自定义队列 `2450`、`_ALPHATEST_ON` 和 `_AlphaClip=1` 已写入资源。两者的 `_NormalMap` 都绑定 Texture2D `342`（`Normal Cut 02`，偏移 `546632`），`_ShimmerBorderNoise` 都绑定 `225`（`Blocky Noise 02`，偏移 `503752`）。`Wall Base 01`（`85`，偏移 `382080`）额外把 `_Color_Detail_Map` 指向 `293`（`Wall Base Detail 01`，偏移 `514440`）。`Mask` Material `12` 指向 Shader `621`（`Shader Graphs/Mask`），与主体着色路径分开。这里读的是材质属性及贴图**引用**，没有解码贴图像素或证明特定 shader 分支在一帧中被采样。

具体颜色也有包内初值：`Accent 01` 的 `_BaseColor=(1, 0.400943, 0.531377, 1)`、`White 01` 为 `(0.977691, 0.954282, 0.885511, 1)`；`Facial Features 01`（`53`）的 `_BaseColor≈(0.135009, 0.127344, 0.131306, 1)`，材质标记为透明、队列 `3000`。它们是材质序列化值，**不能当作某一天气和时间下的最终像素**：`ColorPalette::ApplyMaterialColors` (`0x060000DD`, `IL_0000..005B`) 会对其管理的材质写 `_BaseColor` / `_EmissionColor`，相机照明和后处理还会改变呈现。当前没有把 `sharedassets1.assets` 的三套 `ColorPalette Lake Sun/Rain/Night 01` 中每对材质与灯光参数完整解码，因此不报某场景的最终调色值。

## 实际接入的是低分辨率重绘 feature

这里有两条容易混淆的 CIL 路线。旧 `PixelizeFeature` (`0x02000004`) 的 `PixelizePass::Execute` (`0x06000012`, `IL_0037..00F2`) 在 Game camera 上向材质写 `_PixelSize`、`_BlockCount`、`_BlockSize`、`_HalfBlockSize`，再对 camera color target 作 blit。但本次检出的 renderer 配置连接的是另一条 `Rendering.PixelateRendererFeature.PixelateLayer` (`0x02000067`)。仅凭前者的类名不能把它说成发行场景实际使用的 feature。

资源连接如下：无扩展名的 `globalgamemanagers` 中 GraphicsSettings（class `30`、pathID `7`，文件偏移 `127300`）和 QualitySettings（class `47`、pathID `12`，偏移 `128240`）都含指向 fileID `1` / pathID `2355` 的引用；其外部文件表含 `globalgamemanagers.assets`。在 `globalgamemanagers.assets`（SHA-256 `f44591c487ce6f63a70ffeb8f5b3530dfeaddecd800cdd96cd2f3629c7a45e31`）中，`2355` 是 `URP-HighFidelity` pipeline asset，RendererData 列表依次为 `2354` (`URP-HighFidelity-Renderer`) 与 `2353` (`... No Pixelation`)，序列化默认 index 为 `0`。`2354` 的 renderer feature 列表包含 `2360` (`PixelateLayer`，对象偏移 `934000`)；该 feature 的 active 字节为 1。它的设置是 `_layerMask=471`（层 0、1、2、4、6、7、8）、`_pixelScale=1`、`_maxResHeight=251`、最终 blit Shader fileID `0` / pathID `65`。Shader `65` 的序列化名是 `noio/Blit AlphaBlend`；名字和 `_MainTex` / `_DepthTex` 属性只能证明接口，不能单独证明像素取样公式。

`level0`（SHA-256 `3cec3ec8810c4acc84f95deb2ecb269a9aac78b6292fcaf3d14419ef94f71554`）的 `Main Camera` 上 `UniversalAdditionalCameraData` pathID `7384`（偏移 `1131824`）记录 renderer index `-1`，即选择 pipeline 默认 renderer；`Masking Camera` 上对应对象 `8109`（偏移 `1284160`）记录 index `1`，选第二套无像素化 RendererData。这些是场景配置事实。没有运行时日志或画面，不能排除其它场景、质量档位或运行时设置改变选择。示例块的主体子对象在层 `6`，Mask 在层 `8`，人物及眼睛在层 `0`；这些层都落在 `471` 的位掩码里。因此默认 renderer 的 `PixelateLayer` **配置上覆盖这些部分**，而遮罩相机走单独的 renderer。

`PixelateLayer::Create` (`0x0600032D`, `IL_0000..004E`) 设三段 pass：copy depth 与 render objects 在事件值 `300`，blit back 在 `400`。`SetupRenderPasses` (`0x0600032F`, `IL_000C..0147`) 从相机 target descriptor 得到原宽高，取 `scale=max(_pixelScale, inputHeight/_maxResHeight)`；低分辨率宽、高分别为 `2*RoundToInt(0.5*inputWidth/scale)`、`2*RoundToInt(0.5*inputHeight/scale)`，再按此重建 `_lowResTex` 与 `_depthTex`。`RenderObjectsPass` (`0x060003E5`, `0x060003E7`) 以 LayerMask 过滤、按 URP 的四种 forward shader tag 重绘筛选对象；`BlitBackPass::Execute` (`0x060003E9`, `IL_001A..0076`) 把低分辨率颜色设为 `_MainTex`、深度设为 `_DepthTex`，用最终 blit shader 回写。代码没有在这里为每个块重新生成几何。

**构造演算，非实际分辨率或测量值。** 假设某次相机 target 是 1920×1080，且 feature 当时仍持有包内 `_pixelScale=1`、`_maxResHeight=251`，则 `scale=max(1,1080/251)≈4.30279`。按 32 位浮点运算，宽度半值约为 `223.1111`，高度半值为 `125.5`；Unity `RoundToInt` 对中点取偶数，故得到低分辨率 `446×252`。这个目标大小影响该 pass 的 render target 分配及重绘覆盖；不能从它推算实际帧时。另有 `CameraController::SetPixelation` (`0x060000C7`, `IL_0038..008A`) 会根据 zoom 区间、`pixelationCurve` 和 `minMaxPixelHeight` 更新 `_maxResHeight`，并由 `Start` (`0x060000C1`, `IL_0042`) 与缩放路径调用。因此 `251` 是发行资源的初值，不保证玩家进入关卡后仍为 `251`。

**最终采样未知。** 已见低分辨率重绘、颜色/深度输入和 blit 调用，但本轮没有可靠解出 Shader `65` 的平台子程序：其对象内一个 `DXBC` 字样不满足此仓库 DXBC 索引器的完整容器校验，不能把字样或 Shader 名当成 shader 反汇编。因此不宣称最近邻、双线性、边缘混合、深度判定或具体混色公式。可由静态 CIL 证明的像素化机制是**把指定层在较小 render target 重绘并回贴**；最终每个目标像素怎样读 `_MainTex` / `_DepthTex` 仍需有效 shader 子程序或受控画面证据。

## 对独立自研的可用结论与性能边界

可借鉴的结构是：预制块保存离散身份；每个 prefab 明确拥有网格与材质槽；组合成功用新增子网格表达局部惊喜；全局调色板统一写共享材质颜色；主镜头把选定层重绘至随缩放调整的低分辨率目标，辅助遮罩镜头选另一 renderer。自研时应使用自创网格、材质和纹理，按自家镜头及画质需求决定层、目标尺寸、滤波和透明物体处理，不复制该游戏资源。

性能上，证据只给**成本来源**：更多可见 Renderer/材质槽可能增加提交工作，低分辨率 pass 会额外重绘选定层并分配颜色/深度目标，同时降低该 pass 内部分像素覆盖。静态 prefab 计数、理论低分辨率和 shader 名称都不能给出运行帧时、CPU/GPU 占比、显存峰值或实际 draw call。下一步若允许受控运行，应在同一关卡、镜头和块数量下比较开关 feature、人物组合前后，并记录 Unity Profiler/Frame Debugger 的实测值；本轮保持 `Not Run`。

## 复核方法与剩余问题

正式只读解析器为 [tools/visual_assets.py](tools/visual_assets.py)。从仓库根目录以已缓存的索引运行：

```powershell
python docs/studies/procedural-modeling/summerhouse/tools/visual_assets.py --game-data 'C:\Software\Steam\steamapps\common\SUMMERHOUSE\SUMMERHOUSE_Data' --input .cache/procedural-modeling/summerhouse/resources --output .cache/procedural-modeling/summerhouse/visual-followup
```

它要求 Unity `2023.2.22f1` / format `22` / 无 type tree，并核对输入路径、局部 class、Renderer 材质引用、Material 字节完整消费、pipeline/feature 的预期对象连接；不支持的版本会报错。输出保留名称、参数、层、pathID、偏移和既有资源摘要；不输出游戏贴图或网格资产。解析器使用由 DLL 字段顺序及 Unity 序列化布局推断的窄格式，资源偏移虽可复核，仍不是 Unity Editor 原始作者数据。`globalgamemanagers` 的外部文件表身份和 Graphics/Quality 的引用本轮人工核对；脚本核对了相应对象的引用值。

本专题的结论状态：prefab→Renderer→材质→Shader/纹理引用为 **Answered**；默认 pipeline/主相机与 PixelateLayer 静态接入为 **Answered（配置层）**；运行中实际画面、最终 shader 采样、调色板逐场景值和性能为 **Unresolved / Not Run**。若继续追问具体像素色或预算，须取得有效 shader 子程序或受控运行证据，不能由当前资源名推断。
