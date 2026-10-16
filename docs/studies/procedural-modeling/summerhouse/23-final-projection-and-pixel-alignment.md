# SUMMERHOUSE：最终投影提交与像素对齐链

后续[24](24-other-projection-and-viewport-writers.md)核四关活动反射组件的独立相机写端，并补查URP阴影/viewport及PixelPerfectCamera的有限注册边界；最终native/GPU状态仍未验证。

接续[22：相机移动与像素网格](22-pixel-grid-camera-motion-and-silhouette-stability.md)。本轮将相机脚本之后的链补到URP矩阵生产、提交接口、所选主体顶点程序及低分辨率viewport。**所读普通路径传递连续相机矩阵，没有发现以低分辨率目标宽高重算像素偏移的对齐步骤；主体顶点最终用unity_MatrixVP直接输出clip坐标。**native矩阵读取、命令执行及实际GPU常量尚未恢复，不能把提交参数等同于一帧实测值。

## 身份、工具与范围

输入仍为 `C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data`。本轮REA静态读取 `Managed/Unity.RenderPipelines.Universal.Runtime.dll` 的CameraData和TemporalAA，Evidence `ev_466418762de9eae34cb889d2df56a392b21da99094bc542e02e374964f1c0640`：metadata complete、精确类型均命中，644608 B、MVID `441516f4-c7ab-401e-840b-a71a7013b536`。该目标的证据摘要授权沿用；完整Evidence单独保留，普通CIL输出不冒称REA Evidence。

同次普通读取还覆盖Core.Runtime（MVID `ffa9e7c4-c7b1-415b-b53a-4e040bb18df8`）、CoreModule（MVID `f07e5f68-ed2b-4769-8d43-49b644099efa`）和主程序集（MVID `84569538-a19f-4c17-8ccf-f40b95e99253`）的精确方法。新raw在ignored `.cache/procedural-modeling/static-consumer-followup/summerhouse/`。本轮[顶点投影读取器](tools/projection_shader_probe.py)只重读sharedassets0.assets/Shader622，完整消费50716 B，解析前向公共CB描述及两份vertex参数／DXBC；没有重新遍历全部场景材质，没有执行shader。

场景身份和配置复用[22](22-pixel-grid-camera-motion-and-silhouette-stability.md)：主相机2196是透视、FOV40、target空、完整viewport；关联AdditionalCameraData为Base、AA初值None，见[15](15-mask-camera-order-and-render-admission.md)、[16](16-additional-camera-layout-and-effect-gates.md)。这些是序列化初值，不是当前运行状态。旧native Ghidra timeout未变、未重试。

## 先确认走哪条渲染路径

本机URP `UniversalRenderPipeline.RenderSingleCamera 060007FF / IL_0234…027B` 按静态字段useRenderGraph分流：false走renderer.Setup／Execute，true走RecordAndExecuteRenderGraph。不能仅凭自定义pass存在就默认Execute一定被调。

本轮全URP按该字段扫描：492类型、2520方法，2509件有CIL，其余无body，只有构造器、Render、RenderSingleCamera三个直接用户。构造器 `060007F4 / IL_0111…0112` 写false；唯一所见写true在 `Render 060007F8 / IL_0000…0013`，受RenderGraphGraphicsAutomatedTests.enabled控制。而该类 `get_activatedFromCommandLine 06000034` 的完整CIL就是 `ldc.i4.0; ret`，`.cctor 06000036` 将其存入private static readonly enabled字段，getter直接返回。因此**在所见普通CIL初始化且没有反射／native或其它程序集改字段的前提下，useRenderGraph保持false**。以下继续这条Execute路径；不将另一条RenderGraph执行链视为已经研究。

## Camera矩阵到提交接口

| 环节                         | 当前CIL锚点                                           | 实际数据与分支                                                                                                                                          |
| ---------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 像素矩形／比例               | InitializeStackedCameraData `06000807 / 017C…01B6`    | 读取camera.rect、pixelRect、pixelWidth／Height，保存aspectRatio；不是PixelateLayer低分辨率宽高。AA字段从AdditionalCameraData继承。                      |
| 原投影与局部修正             | InitializeAdditionalCameraData `06000808 / 0229…026C` | 先读camera.projectionMatrix；仅Overlay、非正交且pixelRect不同的分支改m00，公式为旧m00×camera.aspect÷CameraData.aspectRatio。普通Base分支不作这项修正。  |
| view／projection／jitter保存 | 同方法 `027D…028F` → CameraData `06000839`            | J来自TemporalAA.CalculateJitterMatrix；V来自camera.worldToCameraMatrix；P是上一行局部矩阵。三者分别存m_ViewMatrix、m_ProjectionMatrix、m_JitterMatrix。 |
| 普通矩阵getter               | CameraData `0600083B/83C/83D`                         | 非XR时view取V，普通projection取J×P，无jitter版取P；XR另从XRPass取矩阵，不能套此公式。                                                                   |
| 实际提交参数                 | ScriptableRenderer `0600036F / 0023…0036`             | 取上述V与J×P，调用RasterCommandBuffer.SetViewProjectionMatrices。它不是按Wlow／Hlow构造的像素偏移矩阵。                                                 |
| 委托到native                 | Core.Runtime `06000274` → CoreModule `06002BA9/2D3C`  | 前者转交wrapped CommandBuffer；后者把两矩阵按引用传给SetViewProjectionMatrices_Injected。Injected无CIL body，native执行是本轮终点。                     |

Camera.get_projectionMatrix `CoreModule 06000663` 也终止于无CIL的Injected getter；所以P的**数值生产**仍有native边界，不能只用FOV40推断所有项，更不能保证不存在native覆盖。

`TemporalAA.CalculateJitterMatrix 060006CC`先取identity，`CameraData.IsTemporalAAEnabled 0600084D`为false就直接返回它。后者首要门要求antialiasing==3；若主相机AA保持已读初值0，则必在此门返回false，J=I。启用TAA时还需persistent data、MSAA=1、非Overlay／无stack、禁止dynamic resolution、postProcess等条件；本篇不宣称该分支实际运行。GPUProjection有两个重载、各自经过GL.GetGPUProjectionMatrix及jitter相关乘法，具体IL保留于`camera-data.json`；这里只在**非XR、J=I**的前提下归约为native图形约定转换后的P，不将两种重载在J非identity时强行写成同一公式。

## 提交时机与低分辨率viewport

`ScriptableRenderer.Execute 060003A3`先执行BeforeRendering块，然后于 `IL_01DB` 调SetPerCameraProperties，再执行主opaque／transparent块。`RenderBlocks..ctor 060003CE`的四个事件界限为150、300、600、int.MaxValue；像素化copy／render事件300、blit事件400在前150界限之后，见[09](09-lod-writers-and-pass-order.md)。Base路径的 `SetPerCameraProperties 060003A2`先SetupCameraProperties，再SetPerCameraShaderVariables；后者 `06000371 / IL_0306…030A`以setInverseMatrices=true进入上表提交函数。因此有了**普通相机准备到像素化pass之前的提交路径**，但尚未穷举它们之间所有其他pass的状态改写。

PixelateLayer.RenderObjectsPass.Setup `主程序集060003E6`只ConfigureTarget；Execute `060003E7`只创建drawing settings、按cullResults／filtering DrawRenderers及执行／归还命令缓冲，没有SetViewProjectionMatrices或相机矩阵写入。BlitBackPass也没有按目标尺寸校正P。低分辨率宽高是在[22](22-pixel-grid-camera-motion-and-silhouette-stability.md)的descriptor计算里改变，**没有在这些方法中同时写CameraData.aspectRatio或P.m00**。

附件经renderer.SetRenderPassAttachments `060003AE`、SetRenderTarget `060003B1…3B4`到CoreUtils。CoreUtils.SetViewport `06000BBA`只有target.useScaling为true时，取currentViewportSize→GetScaledSize并设置 `(0,0,w,h)`。本次像素化颜色／深度走固定宽高Alloc；Core `RTHandleSystem.Alloc 06000A78 / IL_01D1…01D2`明确写useScaling=false，所以不能用这段scaled分支声称本作已做像素对齐。fixed attachment传到native SetRenderTarget；实际native viewport重置与后续覆盖未读到。整数附件尺寸、scaled viewport和世界投影对齐是三种不同操作。

公开[Camera.projectionMatrix说明](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/Camera-projectionMatrix.html)区分相机矩阵与GPU图形约定转换；它不提供本作当前矩阵值。[SetViewProjectionMatrices页面](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/Rendering.CommandBuffer.SetViewProjectionMatrices.html)说明设置命令的语义，同时对外部SRP使用有限制。本文以**当前本机URP DLL实际调用**为证据，不拿公开API页代替该包实现或证明GPU已正确执行。

## 主体顶点是否另有clip像素取整

Shader622当前属性／程序身份沿[13](13-global-mask-material-consumers.md)。新读取完整Shader对象的前向公共参数：

- `$Globals`的unity_MatrixVP字节偏移1248，对应 `cb0[78…81]`，四行矩阵。
- UnityPerDraw的unity_ObjectToWorld偏移0、unity_WorldToObject偏移64，对应当前vertex的 `cb1` 数据。
- 两个前向vertex分别是blob2／blob3，DXBC长5868／5652 B；解压段内记录位置1012／7016，参数记录亦完整消费。

blob2指令130先把动画偏移加到本地顶点，131…134经ObjectToWorld得到世界位置，135…138只以cb0[78…81]作mul／mad／add并写o0=SV_POSITION。blob3的对应最终段为135…139。两份该段都没有clip.xy÷w×目标大小→round→逆变换的重量化，也没有依据Wlow／Hlow校正投影原点。程序前部有动画／噪声计算，不能把那里的取整误称为屏幕像素对齐。此结论只覆盖Shader622两个前向顶点变体，不覆盖所有Shader／pass。

至此，矩阵生产→native提交接口与vertex常量→clip输出两端均有位置证据；**native如何把命令状态填进这一帧的unity_MatrixVP、实际flip／viewport以及其它状态覆盖仍未逐位核实**。公式 `clip=VP_bound×ObjectToWorld×animatedPosition`描述所选消费程序，VP_bound不伪装成一份已经读取的GPU矩阵。最终Shader65的全屏三角形、Point取样与颜色／深度回贴复用[07](07-pixel-blit-depth-and-local-render-route.md)至[10](10-low-resolution-mips-and-attachments.md)，也没有新增clip对齐环节。

## 贯通构造演算与答案边界

**条件演算，非运行帧。** 假设普通初始化、无反射／native字段改写，主相机保持Base、AA0、非XR、target未替换，目标为此前构造的444×250。RenderGraph开关按所见初始化为false，TAA门返回false，J=I；InitializeAdditionalCameraData取native返回的P0和V，不走Overlay m00修正，SetCameraMatrices将V／P0传向native。RenderObjectsPass仍仅换附件，不以444×250构造校正矩阵。若native最终绑定的矩阵把同一顶点先后变为clip `(0,0,z,1)` 和 `(1/444,0,z,1)`，再**假设**viewport为 `(0,0,444,250)`，则连续viewport映射的x分别为222和222.5；所选vertex末段没有把后者取整为某个固定像素中心。真实光栅覆盖、像素跳变与最终屏幕格宽未在这个演算中验证。若native矩阵／viewport或其他pass不同，这个具体数值例就不适用。

**Answered（静态）**：所见RenderGraph开关生产／消费、V/P/J初始化、AA0的identity jitter门、Base／Overlay修正区别、相机准备到矩阵提交接口、像素化pass未改矩阵、fixed RT不走scaled viewport、Shader622两个前向vertex的VP消费与最终clip输出。**Partial／Unknown**：Camera native矩阵数值生产、Injected命令／渲染上下文的实际状态、native viewport／GPU常量填充、其他程序集／pass和动态组件是否追加对齐。没有从这条链找到像素锁，亦没有证明全游戏绝不存在它。

复算新顶点读取：

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/projection_shader_probe.py 'C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/sharedassets0.assets' --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --output .cache/procedural-modeling/static-consumer-followup/summerhouse/projection-shader-recheck
```

新raw还保留按主题命名的Initialize／CameraData／renderer／CoreUtils／native-wrapper CIL、完整REA记录及public-reference。验证包括同文件复读、50716 B完整消费、矩阵参数／指令配对、CIL身份及分支、输出拒绝覆盖与错误profile、相对链接和构造算术。游戏／Unity／GPU执行、附加、原函数执行、私人存档、画面稳定性和性能测量全部 **Not Run**。
