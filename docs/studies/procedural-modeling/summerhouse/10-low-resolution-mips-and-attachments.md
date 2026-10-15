# SUMMERHOUSE：低分辨率目标的 mip 与颜色/深度附件

外部遮罩目标与截图临时替换主相机 target 的具体分支续见[11](11-mask-target-and-camera-overrides.md)；下文普通相机推导仍以 target 未被替换为条件。

本篇继续 [09](09-lod-writers-and-pass-order.md) 的资源问题。**level0 主相机没有序列化 targetTexture，普通相机描述符默认 `useMipMap=false`、`autoGenerateMips=true`；像素化 feature 继承这两个标志。分配器把低分辨率颜色申请为 HDR 类别颜色目标，把带深度位数的另一申请转成 Depth 类别。复制和重绘明确使用这一颜色/深度对，回贴则恢复相机颜色/深度对，附件选择的 mipLevel 为 0。** 这些是创建请求和静态绑定关系，没有运行时纹理对象或 GPU 抓帧。

## 身份与新证据

游戏、URP、Core DLL 身份沿用 [08](08-filtering-and-lod-provenance.md)、[09](09-lod-writers-and-pass-order.md)。新增读取同一安装目录的 `SUMMERHOUSE_Data/Managed/UnityEngine.CoreModule.dll`：`1717496` B，MVID `f07e5f68-ed2b-4769-8d43-49b644099efa`，SHA-256 `e44b24a0f2c4c0545ee21b1da7197bb8f7e791f4c00f454538efd90e49409e62`。REA identity 父 Evidence `ev_02e6ca1a0e0bdef8fabcd2ecff4ed99c90a94d105bdfddff04a92addc47d4003`、summary `ev_e80eabf0414a2abc4d41dc26e2a5240825109e502f75a9f90034145ecaf07592`，metadata complete。选定 descriptor、RenderTextureFormat、Texture 成员 Evidence `ev_7466f488aae380b5ac488e7a517c26386dc7e5d99004147afd54bac6347ea2eb`；其中先按 CoreModule 查 ClearFlag 未命中，随后从实际 Core.Runtime 解该 enum，未将未命中解释成不存在。

新原始投影保存在 `.cache/procedural-modeling/static-resource-followup/summerhouse/`：`descriptor.json`、`rendertexture.json`、`rendering-utils.json`、`rt-handles-alloc.json`、`rt-system-alloc.json`、`core-set-target.json`、两种 enum、`texture-defaults.json` 和 `level0-camera-targets.json`。托管读取器仍只解析 PE metadata/CIL，不执行目标代码；本轮补充 exact type 的声明字段常量与方法参数名，枚举常量与参数位置不再靠记忆命名。

## 主相机确实走哪种 descriptor 入口

借助 AssetRipper TypeTreeDumps 固定提交 `20ba06e00e0625de0e49a502c6868d6cc86d0f0b` 的精确 [2023.2.22f1 布局](https://github.com/AssetRipper/TypeTreeDumps/blob/20ba06e00e0625de0e49a502c6868d6cc86d0f0b/InfoJson/2023.2.22f1.json)，新增[相机读取器](tools/camera_target_probe.py)用 Camera class 20 的 **ReleaseRootNode** 解释实际 `level0`。该参考只作为格式依据，没有安装软件或计算参考文件摘要；结果仍由当前对象长度、字段与引用校验。

Main Camera 的 Camera 对象 `2196` 位于文件 `468720`、长 `184` B。布局对齐后完整消费 184 B；不是把 root 的未对齐 ByteSize 175 当作实际长度。`m_TargetTexture` 在对象 `+148`（`0x94`）为 `(fileID=0,pathID=0)`，`m_HDR=1`、`m_AllowMSAA=1`、`m_AllowDynamicResolution=0`。GameObject 引用解析到真正名称 `Main Camera`，viewport 为 `(0,0,1,1)`，near/far 为约 `0.3/1000`，均作为独立邻接校验。Masking Camera 对象 `2197` 同为 184 B，却有非空 target `(2,765)`，与 [05](05-materials-pixelization-and-camera.md) 的另一 renderer 分开，不能将两台相机混用。

URP `UniversalRenderPipeline.CreateRenderTextureDescriptor 0x06000823` 在 `IL_0016..0022` 判断 `camera.targetTexture`。空值分支于 `IL_0032` 调 CoreModule `RenderTextureDescriptor..ctor(width,height)`，设宽高、兼容颜色格式、深度位数 32 和 MSAA；非空分支于 `IL_0080` 取外部 target 的 descriptor。**因此按此主相机序列化配置、且未在运行中替换 target 的条件，可沿普通构造分支推导；不能把外部 RenderTexture 的任意 mip 设置套进来。**

## mip 标志从构造到分配

CoreModule 的两参数 descriptor 构造 `0x060019D1` 经 `19D2/19D3/19D5/19D6` 到 `0x060019D9`，后者 `IL_0009..000E` 写 `_flags=130=0x82`。`get_useMipMap 0x060019DB / IL_0007` 测 bit 0；`get_autoGenerateMips 0x060019DD / IL_0007` 测 bit 1。于是初值分别为 **false / true**。`Texture..cctor 0x060016DF` 还把 `GenerateAllMips` 设为 `-1`，descriptor 保存该 mipCount；这不是启用 mipmap 的开关，不能由 `-1` 或 autoGenerateMips=true 推成已经申请整条 mip 链。

URP 的这个普通 descriptor 创建路径没有改这两个 mip 标志。游戏 `PixelateLayer.SetupRenderPasses 0x0600032F` 复制 `cameraTargetDescriptor`，只改颜色格式、深度位数与缩小的宽高，未调用 mip 标志 setter。其颜色格式 setter 最终进 CoreModule `set_graphicsFormat 0x060019BD`，只按 IsSRGBFormat 修改 flag `0x4` 并重算深度格式，不会打开 bit 0。

实际分配链为：游戏两次 `ReAllocateIfNeeded` → URP `0x0600062D / IL_00A8` → Core `RTHandles.Alloc 0x06000A4D` → `RTHandleSystem.Alloc 0x06000A77/0x06000A78`。`A4D / IL_0052/0060` 分别读出这两个 descriptor 标志，`A78` 的两种创建分支在 `IL_0096/009E` 或 `0153/015B` 把它们分别交给 RenderTexture 的 `set_useMipMap` / `set_autoGenerateMips`。`RTHandleNeedsReAlloc 0x0600062B / IL_00EC..0115` 也检查已有目标的两个标志，不能只因句柄复用就忽略它们。

这条静态申请链的含义是**不开启 mip 链**，而不是“自动生成关闭”。实际 native mip 数、分配成功与 GPU 对象未查询。若另一相机提供外部 target descriptor，或运行代码另改 descriptor/target，须重新检查继承值；本篇不把主相机初值泛化到所有相机。

## 两个句柄最终是什么资源

`SetupRenderPasses IL_000C..0018` 先设 `depthBufferBits=0`、`colorFormat=9`。CoreModule 常量表把 `9` 定义为 `RenderTextureFormat.DefaultHDR`；它是兼容 HDR 类别请求，不是某个固定像素位深。缩小后，该 descriptor 在 `IL_0096` 以 `_lowResTex` 名称申请 `_lowResHandle`。随后 `IL_009C` 复制同一 descriptor，`IL_00AE..00B3` 把深度位数改为原相机 descriptor 的位数，再在 `IL_00CE` 以 `_depthTex` 名称申请 `_depthHandle`。

关键转换在 Core `RTHandleSystem.Alloc 0x06000A78`：`IL_001D..0023` 判断 isShadowMap 或 depthBufferBits 非零；在此深度分支，`IL_002C` 选择常量 `1=RenderTextureFormat.Depth`，`IL_004F` 调 legacy RenderTexture 构造，**不再使用原先的 HDR graphicsFormat 作为颜色申请**。颜色分支则在 `IL_010C` 用传入 graphicsFormat 构造。两个分支都继续设置上述 mip 标志，再在 `IL_01BD` 调 `RenderTexture.Create`。

因此不能只见 `_depthTex` 在游戏局部 descriptor 中继承过 DefaultHDR，就断言它最终是另一张 HDR 颜色纹理；实际分配器在非零深度位数时改走 Depth 请求。具体兼容 GraphicsFormat/depthStencilFormat 仍经过 Unity 的设备查询与 native 创建，未静态指定为某个 D3D 格式。若原相机深度位数为零，则此深度分支前提不成立；普通主相机入口上游明确请求 32，仍须保留设备/外部 target 覆盖边界。

## 复制、重绘和回贴的 attachment 身份

| 阶段                  | 实际句柄传递                                                                                                                                                                                       | 静态附件与清理状态                                                                                                                                                                                                                                                         |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CopyDepthPass 300     | 游戏 `SetupRenderPasses IL_00E5..0103` 把相机 color/depth **来源**与 lowRes/depth **目标**交给 `CopyDepthPass.Setup 0x060003E3`；后者 `IL_0000..0004` 对目标调用 ConfigureTarget，并把来源存为字段 | URP `ScriptableRenderPass.ConfigureTarget 0x0600033A` 设 overrideCameraTarget=true，把 `_lowResHandle` 写 color[0]、`_depthHandle` 写 depth，并清空其余 color 槽；游戏配置 ClearFlag.All=7。来源有效时 Core BlitColorAndDepth 向这对附件输出颜色与深度，来源为空则跳过复制 |
| RenderObjectsPass 300 | `SetupRenderPasses IL_0119..012B` 将同一 lowRes/depth 对传给 `RenderObjectsPass.Setup 0x060003E6`，后者直接 ConfigureTarget                                                                        | 同样明确覆盖目标。ClearFlag.Color=1，因此重绘前清颜色，不在这项配置中请求再清 depth；重绘的 fragment 深度写入受各材质状态约束                                                                                                                                              |
| BlitBackPass 400      | `Setup 0x060003EA` 只保存这两个输入句柄；Execute 把它们绑定 `_MainTex` / `_DepthTex`，见 07                                                                                                        | 此类没有 ConfigureTarget。基类构造 `0x0600032E / IL_00BD` 令 overrideCameraTarget=false；`ScriptableRenderer.SetRenderPassAttachments 0x060003AE / IL_03D1..03F4` 在事件≥150时改取当前相机的 color/depth target。故 back 是**读取低分辨率对、写相机对**                    |

URP 单颜色附件绑定分支经 `SetRenderTarget 0x060003B2 → 0x060003B3`，后者 `IL_0038..003B` 向 CoreUtils 传选择值 `0/-1/-1`。CoreUtils 的 `0x06000BB6` metadata 参数名明确依次为 `miplevel/cubemapFace/depthSlice`；`IL_0063..0069` 把这些值转交实际目标设置。因此本链附件选择为 **mip 0、默认 cube face/depth slice**。同一目标已绑定时，URP 可跳过冗余设置；这不是每帧每 pass 必然新建或重绑的计数。

Shader 65 的 `_DepthTex→t1`、写 `SV_Depth`、ZWrite 开已在 [07](07-pixel-blit-depth-and-local-render-route.md)解码；本轮补上它的输入确为上述 depth 句柄，以及回贴的目标 depth 来自相机。Shader 输入取样 LOD 与附件 mipLevel 是两种独立选择：[09](09-lod-writers-and-pass-order.md)证明成功 copy 后回贴继承 LOD 0，本篇证明资源/附件创建和选择，不能将其中一个自动代替另一个。

## 构造演算、复现与边界

取普通主相机目标 `1920×1080`、feature 初始最大高度 251，则按 [05](05-materials-pixelization-and-camera.md)得到 `446×252`。颜色申请为该大小、depthBits 0；深度申请为同大小、上游请求 32 位深度，再经分配器选 Depth 类别。两者 `useMipMap=false`、`autoGenerateMips=true`，附件 mip 0。复制→清颜色重绘→回贴的句柄为 `cameraPair → lowPair → cameraPair`。这是沿实际公式的构造输入，不是本机分辨率、最终格式、分配结果或屏幕观测。

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/camera_target_probe.py "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/level0" --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --output .cache/procedural-modeling/static-resource-followup/summerhouse/camera-targets-recheck.json
dotnet .cache/procedural-modeling/static-chain-followup/summerhouse/managed-bin/net9.0/ManagedCilProbe.dll "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/Managed/UnityEngine.CoreModule.dll" UnityEngine.RenderTextureDescriptor "*" .cache/procedural-modeling/static-resource-followup/summerhouse/descriptor-recheck.json
```

参考 JSON 必须从上述固定 URL 单独只读取得；相机读取器核对精确版本、class、全部字段消费及 GameObject，不自动下载或执行。输出新建、拒绝覆盖。静态资源解析、关键 CIL 参数/常量、构造演算与工具失败边界已复核。仍未知其它场景与运行替换、设备兼容格式、实际 MSAA/resolve/附件覆盖及真实 mip 数；游戏、GPU 抓帧、像素与性能验证均为 **Not Run**。自研可把颜色和深度目标显式分开定义，并独立固定 mip/采样契约。
