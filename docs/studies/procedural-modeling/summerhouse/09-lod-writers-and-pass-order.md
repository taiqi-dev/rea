# SUMMERHOUSE：LOD 写入者与回贴前的 pass 顺序

> 后续 [10：低分辨率 mip 与附件](10-low-resolution-mips-and-attachments.md)补主相机 target 配置、mip 标志构造/分配，以及 lowPair/cameraPair 的附件选择；下文调度条件保持原范围。

[08](08-filtering-and-lod-provenance.md)查到复制写 LOD 0、回贴继承共享属性块，但没有展开中间的调度。本轮把默认 renderer 的 feature、URP 队列和实际 Blitter 重载接起来：**在已读发行配置与正常复制成功的这条路径中，事件 300 写 0 后，到事件 400 的自定义回贴之间，没有找到另一处写非零 LOD 的直接调用。** 反射探针/灯光图集确实有可写非零 mip 的调用，但其已追入口在复制之前；不能把它们仅因共享 Blitter 就当作两次 pass 之间的覆盖。

这是一项配置和指令顺序的静态结论。复制因空源跳过、运行中更换 renderer/feature 或其它未覆盖入口时，仍不能保证回贴的绝对值；未运行游戏。

## 输入身份与读取覆盖

游戏 `Assembly-CSharp.dll`、Core DLL 和资源的身份沿用 [08](08-filtering-and-lod-provenance.md)。本次新增直接读取同一安装目录 `SUMMERHOUSE_Data/Managed/Unity.RenderPipelines.Universal.Runtime.dll`：`644608` B、MVID `441516f4-c7ab-401e-840b-a71a7013b536`、SHA-256 `3ddebd84e21c6a83ebe1c3806fe0838a86155abc2ce1546f3265c7fceb0c42fb`。REA identity 父 Evidence 为 `ev_9fbd35864e3f99cdae4649dbce2fd87c124648ce934d5d31fe93132efe0410ed`，summary 为 `ev_a8daf8333eab1726eb8ffd43bd378789c1020c48a851462d957b9eb3bcf16f92`；metadata complete。选定 `CopyDepthPass` 和 `RenderGraphGraphicsAutomatedTests` 的成员 Evidence `ev_cce2736c01adc536cd9e2232ac695a76024f9d8f563577e63a7c5872bfb1c69f` 也 complete。摘要仅用于已授权的游戏输入身份。

[离线 CIL 读取器](tools/ManagedCilProbe/Program.cs)增加显式 `*` 类型选择和 resolved operand 子串过滤，逐个解码选定 DLL 的有方法体成员，再只保留命中方法的完整 IL；不会只对原始字节搜索 token。过滤结果保留 examined/decoded 数，不把无方法体成员视为已检查 native 实现。

| 安装内程序集              | 本次检查 MethodDef / 解码方法体 | 含 `UnityEngine.Rendering.Blitter::` 操作数的方法 | 范围含义                                                                     |
| ------------------------- | ------------------------------: | ------------------------------------------------: | ---------------------------------------------------------------------------- |
| Assembly-CSharp           |                     1006 / 1006 |                                                 3 | 旧 PixelizePass 一处；当前 feature 的复制、回贴各一处                        |
| Assembly-CSharp-firstpass |                       390 / 390 |                                                 0 | 此程序集的该操作数过滤为空，不是所有插件的否定                               |
| Core.Runtime              |                     4381 / 3967 |                                                42 | 包括 Blitter 自身共享字段/内部调用及图集调用者                               |
| Universal.Runtime         |                     2520 / 2509 |                                                56 | 包括传统 Execute、RenderGraph delegate、后处理和图集等候选；不能全当默认队列 |
| Universal.2D.Runtime      |                       931 / 902 |                                                 5 | 包内能力；本次默认 UniversalRenderer 不使用这些 2D pass                      |

表中后列是“方法含目标操作数”，不是调用次数或 draw call；Core 行也包含字段操作。2D DLL 为 `230400` B、MVID `247ab1e8-3a4b-49cd-b9ae-9b5804f230c7`；firstpass 为 `59392` B、MVID `19ade40c-83a7-44e2-bba1-e2712558dde3`。其余方法体并未因过滤不命中而成为运行观察。

## 默认配置采用哪条调度路径

对实际 `globalgamemanagers.assets` 再读两套 RendererData：`2354` 位于文件 `931432`、长 `452` B，feature 数字段相对 `0xa8` 为 `1`，相对 `0xac` 的唯一 PPtr 是 `(fileID=0,pathID=2360)`；无像素化 renderer `2353` 位于 `930984`、长 `444` B，同位置 feature 数为 `0`。[05](05-materials-pixelization-and-camera.md)已接通默认 renderer index 0、Main Camera 使用默认、2360 active，以及另一 Masking Camera 使用 renderer index 1。因此旧 `PixelizePass.Execute 0x06000012` 虽有 Blitter 调用，不能插入这套唯一 feature 的队列解释。

本作 URP `UniversalRenderPipeline..ctor 0x060007F4` 在 `IL_0111..0112` 明确把静态 `useRenderGraph` 写为 false。`Render 0x060007F8` 唯一读到的另一处写入受 `RenderGraphGraphicsAutomatedTests.enabled` 控制；本制品该类 `.cctor 0x06000036` 调 `get_activatedFromCommandLine 0x06000034`，后者的整个方法体就是 `ldc.i4.0; ret`，所以此默认初始化也为 false。对 URP 中该字段的直接访问过滤只命中构造、Render 和 RenderSingleCamera；游戏程序集没有命中。这里未把测试名称推成实际命令行开关，也未执行其构造器。

在 false 分支，`RenderSingleCamera 0x060007FF` 的顺序是：`IL_022F AddRenderPasses` → `IL_0262 renderer.Setup` → `IL_027B renderer.Execute`。这点决定同事件的先后：feature 的三个 pass **先入队**，随后 UniversalRenderer.Setup 才追加内置 pass。`ScriptableRenderer.Execute 0x060003A3 / IL_00D7` 调 `SortStable 0x060003BC`；排序循环在 `IL_0032` 调 `ScriptableRenderPass.op_LessThan 0x0600034F`，其 `IL_000C clt` 只比较严格小于。故相等事件不会越过先入队项，不是仅根据 SortStable 的名称作判断。`ExecuteBlock 0x060003AB / IL_0036` 再按排好范围逐项调用 `ExecuteRenderPass`。

## 300 到 400 之间谁会改 LOD

游戏 `PixelateLayer.Create 0x0600032D` 给 copy/render/back 分别设事件 `300/300/400`；`AddRenderPasses 0x0600032E` 按相同顺序入队。URP 内置 pass 的事件和消费如下：

| 阶段                       | 当前指令依据                                                                                                                                                                                                                                                     | 与共享 `_BlitMipLevel` 的关系                                                                                                                                                                      |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 灯光/反射图集准备          | `ScriptableRenderer.Execute IL_017A SetupLights` 在执行各 block 前；`UniversalRenderer.SetupLights 0x0600078C / IL_000D` → `ForwardLights.SetupLights 0x0600090A`，后者 `IL_0037` 调 ReflectionProbeManager.UpdateGpuData，`IL_03C7` 调 LightCookieManager.Setup | 存在可写非零 mip 的候选，但此已追入口在 copy 300 之前                                                                                                                                              |
| 内置 opaque                | `UniversalRenderer..ctor 0x06000780 / IL_03DE` 等构造普通 opaque 为事件 250                                                                                                                                                                                      | 排在 copy 300 前；不能用其名称误排在 copy 后                                                                                                                                                       |
| 游戏 CopyDepthPass 300     | `Execute 0x060003E1 / IL_0064` 压入 float 0，`IL_006A` 调 Core `BlitColorAndDepth 0x06000B59`，后者 `IL_000C SetFloat`                                                                                                                                           | **成功复制分支把共享 LOD 写成 0**；空源分支跳过，见 08                                                                                                                                             |
| 游戏 RenderObjectsPass 300 | `0x060003E7` 使用 filtering/cull results 调 `DrawRenderers`，其整个方法体不调用 Blitter                                                                                                                                                                          | 不改该块 LOD；同事件保持 copy 之后                                                                                                                                                                 |
| 内置 skybox 350            | 构造 `IL_0478` 事件 350；`DrawSkyboxPass.ExecutePass 0x060004BA / IL_0034` 调 `DrawRendererList`                                                                                                                                                                 | 已读方法无 Blitter writer                                                                                                                                                                          |
| 可选内置 depth copy        | Setup `0x0600078B / IL_03F9..042D` 按是否需深度和最早消费者决定事件，另有 500 分支；`Internal.CopyDepthPass.ExecutePass 0x06000944 / IL_0271` 用 MemberRef `0x0A00001E` 调 BlitTexture                                                                           | 该签名第四参数为 Material、末项为 int pass；不是 float LOD 重载。Core RasterCommandBuffer 包装重载 `0x06000B5A` 只转发到不写 LOD 的 `0x06000B5B`。无论该 pass 排在区间内还是外，都不经此调用改 LOD |
| 可选 motion vectors        | `MotionVectorRenderPass.ExecutePass 0x060004DE` → `DrawCameraMotionVectors 0x060004E1`、`DrawObjectMotionVectors 0x060004E2`，实际用 `DrawProcedural` / `DrawRendererList`                                                                                       | 所读链不调用 Blitter；不把动态事件计算当作 LOD writer                                                                                                                                              |
| 游戏 BlitBackPass 400      | `0x060003E9 / IL_0076` → Core `0x06000B5B` → `DrawTriangle 0x06000B52`                                                                                                                                                                                           | 继承共享块已有 0，不重写 LOD，消费关系见 08                                                                                                                                                        |
| 内置 color copy 400        | 构造 `IL_0488` 设事件 400；在 renderer.Setup `IL_1007` 追加入队。`CopyColorPass.ExecutePass 0x06000932` 四个 blit 调用均是上述 Material/int 重载                                                                                                                 | 稳定排序使它位于先入队的游戏 back 400 **之后**；各分支也不写共享 LOD。分支中的 `Material.SetFloat(2)` 是另一材质属性，不能当作该共享块 LOD 2                                                       |

Core 中能写其它 LOD 的具体例子不是假设：`BlitCubeToOctahedral2DQuadWithPadding 0x06000B6E / IL_002A` 把 int mip 实参转为 float 并写相同属性。URP `ReflectionProbeManager.UpdateGpuData 0x060005B3` 的 `IL_0845` 传局部 mip 循环索引、`IL_0855` 调它，`IL_0869` 按 `mipCount` 继续循环；若有多个 mip，此路可以写非零值。但它通过上表 SetupLights 进入，随后成功 copy 300 会重设 0。其它后处理、RenderGraph 和 2D 候选没有仅凭“调用存在”就并入当前区间。

## 构造演算和剩余边界

按实际入队顺序构造最小序列：`[copy300, objects300, back400, opaque250, sky350, color400]`。严格小于的稳定排序得到 `[opaque250, copy300, objects300, sky350, back400, color400]`。即使在前期图集更新后共享 `M=2`，copy 成功令 `M←0`，objects/sky 不写、可选 depth copy 的 Material 重载也不写，因此 back 读 `M=0`。这解释的是**包内路径的静态状态流**，不是一张实际帧日志。

若 copy 的空源分支跳过，上述重设前提消失；不能把本轮顺序证明扩大为所有相机和错误分支的常量。运行中切 renderer/feature、未覆盖 native/反射入口、真正 attachment、有效 mip 和最后的 GPU 取样仍没有运行证据。Main Camera 与 Masking Camera 的配置不同；`RenderCameraStack 0x06000800` 的 base/overlay `RenderSingleCamera` 调用为 `IL_03A1/04AA` 的顺序调用，未在此链看到另一个相机插入当前两个 pass 之间，但这不是所有引擎回调的全局不可重入证明。

## 复现与验证

```powershell
dotnet build docs/studies/procedural-modeling/summerhouse/tools/ManagedCilProbe/ManagedCilProbe.csproj --disable-build-servers -p:RestoreSources= -p:NuGetAudit=false
dotnet .cache/procedural-modeling/static-chain-followup/summerhouse/managed-bin/net9.0/ManagedCilProbe.dll "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/Managed/Unity.RenderPipelines.Universal.Runtime.dll" "*" "*" .cache/procedural-modeling/static-submission-followup/summerhouse/urp-blitter-recheck.json "UnityEngine.Rendering.Blitter::"
```

工具兼容原四参数 exact type 模式；第五参数只过滤已解码的 resolved operand，合法空匹配输出显式 coverage，而错误 exact type、未知方法选择和已有输出仍失败。它不加载目标 DLL 或依赖执行，JSON 为新建模式。新原始投影集中在 `.cache/procedural-modeling/static-submission-followup/summerhouse/`：五个程序集的 caller 投影、`universal-pipeline.json`、`universal-renderer.json`、`scriptable-renderer.json`、`scriptable-pass.json`、`pixelate-feature.json`、`pixelate-renderobjects.json`、`urp-copydepth.json`、`urp-copycolor.json`、`motion-pass.json`、`skybox-pass.json`、`forward-lights.json`、`rendergraph-test-flag.json` 和 `renderer-feature-check.json`。字段写入与 Blitter 内部重载沿用 08 的 Core 完整 CIL。

方法体边界、匹配覆盖、关键分支/相等事件、重载类型和构造序列均静态复核；读取器构建和必要失败检查通过。游戏、抓帧、实际执行顺序及性能测量为 **Not Run**。独立实现仍宜每次回贴显式设置 LOD，让正确性不依赖上一次共享块写入或另一个 pass 是否成功。
