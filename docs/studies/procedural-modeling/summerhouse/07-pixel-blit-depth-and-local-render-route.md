# SUMMERHOUSE：像素化回贴、深度与局部修改的渲染连接

> 后续 [08：过滤与 LOD 来源](08-filtering-and-lod-provenance.md)补上 inline sampler 原始记录/格式解读，以及复制写 LOD 0、回贴继承共享属性的条件；下文保留前轮证据范围。

本篇补[05](05-materials-pixelization-and-camera.md)的最终 blit shader 断点，并把[06](06-local-updates-and-render-costs.md)的单块修改接到渲染消费者。**新闭合的是：配置中的 Shader 65 → 回贴材质 → 颜色/深度纹理槽 → 实际取样与输出 → 包内混合/深度状态。** 没有运行游戏，仍不把配置链当作一次真实帧捕获。

## 身份、压缩段与读取范围

安装输入仍为 `C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data`。本轮 REA 再读 `Managed/Assembly-CSharp.dll`，摘要视图 `ev_8551c8766a33f2f2133f3d948df2fb8cecd1a381ffde1ab83756afe1314114ed` 指向同一父 Evidence `ev_ff501d30ac54266f32022d519c34b5ab505213ac840d55d79e153ad1df6aa2cf`，文件摘要和 MVID 与[00](00-evidence-and-scope.md)一致。实际 `PixelateLayer` 成员 Evidence 为 `ev_80f414b2ff1b1b3f4ede70797fe0058fba29e7a8c47a538a8a7588c4f72eef27`；`CopyDepthPass/RenderObjectsPass/BlitBackPass` 为 `ev_0da20e6322b81391b14089e22399006f1559d82385396ac8730ced90dbd3d94d`，三类选择均命中、元数据解码 complete。首次使用带外层前缀的类型名未命中；改按此工具实际返回的三种类型名读取，没有把未命中当作功能缺失。

`globalgamemanagers.assets` 的 class 48、pathID `65` 位于文件偏移 `398544`，长 `3428` B。Shader 内相对 `0xa9c` 是完整压缩表：平台 `4`，单段 offset `0`、compressed `642` B、decoded `1244` B；压缩数据从原文件 `401308` 开始。现有[Shader 读取器](../tools/unity22-shader-probe.py)按此表展开后，定位到两份合法 DXBC：解压段偏移 `162`、长 `544` B 的 vertex，以及偏移 `786`、长 `448` B 的 fragment，Windows D3DDisassemble 均成功。

**对上一轮缺口的解释：** 05 直接看到的 `DXBC` 字样仍在 LZ4 数据中，不能当作原始容器。此次先按声明展开，才得到有效子程序。05 保留历史结论，本篇将该项升级为静态已回答。原始输出在 ignored `.cache/procedural-modeling/render-chain-followup/summerhouse/shader65/`，没有复制游戏 shader 到正式源码目录。

## 配置对象怎样进入实际取样

05 已核实：默认 pipeline renderer `2354` → active feature `2360` → `FinalBlitShader=fileID 0/pathID 65`；主相机选择默认 renderer。新的调用连接如下：

1. `BlitBackPass.Execute`（token `0x060003E9`、`IL_001A..0030`）取 `FinalBlitShader`，交给 `TryCreateMaterial`（`0x06000330`）。材质为空或当前 shader 不同才调用 `CreateEngineMaterial`；已有且 shader 相同则复用该材质字段。这里只证明所读方法的复用条件，未证明整个引擎的销毁策略。
2. `Execute IL_0032..0059` 把 `_sourceHandle` 绑定为 `_MainTex`，把 `_depthHandle` 绑定为 `_DepthTex`。`IL_005E..0076` 使用该材质、pass `0` 调 `Blitter.BlitTexture`。它不是为每件块分别创建一个回贴材质。
3. Shader 65 的名称表 `0x10`、fragment 参数表 `0x8a8`、纹理表 `0x880` 经[参数读取器](../sandcastle/tools/surface_probe.py)核对：`_MainTex→t0`、`_DepthTex→t1`，`$Globals→cb0`，`_BlitMipLevel→cb0[1].x`。两种纹理记录的 sampler 索引是原始 `0xffffffff`；fragment 使用单独的 `s0`，不能把此值解释成不存在 sampler。
4. fragment 只有四条带编号指令：`0` 在 UV `v1.xy`、LOD `_BlitMipLevel` 上从 `t0` 取 RGBA，直接写 `SV_Target`；`1` 以同一 UV/LOD/sampler 取 `t1`；`2` 将第二次取样的 X 分量写 `SV_Depth`；`3` 返回。没有在这份子程序中看到深度比较、轮廓检测、UV 像素取整或颜色修正分支。

vertex 的 `_BlitScaleBias` 位于 `cb0[0]`，参数表起点 `0x7e4`。它按 VertexID 生成全屏三角形并计算 `UV=(q.x,1−q.y)×scale+bias`，其中 `q=((id<<1)&2,id&2)`。fragment 接收该插值 UV，而非自己按屏幕像素重新量化；像素化首先来自较小 render target 的重绘。实际 `_BlitMipLevel`、inline sampler 的过滤/寻址编码及所有引擎覆盖尚未完整追踪，所以仍不宣称最终一定是最近邻过滤。

## 透明混合不会自动阻止深度写入

新[状态前缀读取器](../tools/unity-shader-state-probe.py)从 Shader 65 相对 `0x7c` 读取状态名、8 个 RT 的 blend 和 depth/raster 前缀，止于 `0x584`，没有把后面的 stencil、tags、program 表当作已解析。实际 RT0 为 `src=5,dst=10,op=0`，alpha 对应同样的 `5/10/0`，color mask `15`；`separate_blend=false`。深度/剔除为 `ZClip=1,ZTest=8,ZWrite=1,Cull=0`，offset 与 alpha-to-mask 为 0。

按 Unity [2023.2 图形枚举](https://github.com/Unity-Technologies/UnityCsReference/blob/2023.2/Runtime/Export/Graphics/GraphicsEnums.cs)，对应 SrcAlpha、OneMinusSrcAlpha、Add、全颜色写入、Always 测试、深度写入开、Cull Off。字段布局参照 [AssetStudio 固定提交](https://github.com/Perfare/AssetStudio/blob/d158e864b556b5970709c2a52e47944d53aa98a2/AssetStudio/Classes/Shader.cs)，并由上述本地记录核对；它仅帮助识别表结构，不代替当前驱动状态。

**推导。** 当该状态被应用且有相应目标 attachment 时，颜色为 `Cout=Cs×As+Cd×(1−As)`；alpha 同样使用 source alpha 因子，`Aout=As²+Ad×(1−As)`。深度则由 `_DepthTex` 的 X 分量输出，既没有 fragment discard，也不因 alpha 为 0 自动关闭写入。这解释了为什么回贴同时需要深度纹理；不能把它简化成只有透明颜色叠加。

**构造演算，非屏幕采样。** 取源色 `(0.8,0.2,0.1)`、源 alpha `0.25`，目标色 `(0.2,0.4,0.6)`、目标 alpha `1`，则颜色变为 `(0.35,0.35,0.475)`、alpha 为 `0.8125`。若深度取样 X 为 `0.7`，并且当前 pass 有可写深度 attachment，则输出深度是 `0.7`。若只把源 alpha 改为 0，颜色保持目标色，shader 仍输出同一深度值。真实 attachment、颜色空间和其它覆盖需要受控运行验证，这里只计算已读状态。

## 单块更新与整层重绘的接口

`SetupRenderPasses`（`0x0600032F`）先根据相机 descriptor/缩放求低分辨率，再对 `_lowResHandle`、`_depthHandle` 调 `ReAllocateIfNeeded`（`IL_0080..00D3`）；不是从调用名称推定每次实际都重新分配。随后把相机颜色/深度来源及这两个目标交给 `CopyDepthPass.Setup`，将低分辨率颜色/深度交给 `RenderObjectsPass.Setup`，最后将同样两个句柄交给 `BlitBackPass.Setup`（`IL_00E5..0142`）。

`CopyDepthPass.Execute`（`0x060003E1`）对所需源 RT 作非空检查后调用 `BlitColorAndDepth`，失败分支不复制。`RenderObjectsPass.Execute`（`0x060003E7`）则把当前 `cullResults`、drawing settings 和该 pass 的 filtering settings 交给 `DrawRenderers`。05 已证 layer mask 为 `471`；本方法没有读取 BuildingBlock 的 dirty 集合。`Create` 设 copy/render 为事件 `300`、blit 为 `400`；`AddRenderPasses` 依次 enqueue 三个 pass。所选 `CopyDepthPass.OnCameraCleanup` 仅返回，不能据此推出其它所有者绝不回收句柄。

因此局部刷色/替换先改一个块的 Renderer/材质引用，而像素化消费者在它执行时，按当前剔除结果与层筛选重绘候选，再统一回贴；它不把单块 dirty 直接当成一块屏幕矩形缓存。实际哪些候选可见、透明排序、目标 attachment 和执行频率没有帧证据。本机托管类型内也未见另一个 dirty-screen 合成入口，但这不是对其它程序集或所有场景的全局否定。

## 复现与结论状态

```powershell
python -X utf8 docs/studies/procedural-modeling/tools/unity22-shader-probe.py "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/globalgamemanagers.assets" --object-id 65 --table-offset 0xa9c --output .cache/procedural-modeling/render-chain-followup/summerhouse/shader65
python -X utf8 docs/studies/procedural-modeling/tools/unity-shader-state-probe.py "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/globalgamemanagers.assets" --object-id 65 --state-offset 0x7c --output .cache/procedural-modeling/render-chain-followup/summerhouse/shader65-state.json
python -X utf8 docs/studies/procedural-modeling/sandcastle/tools/surface_probe.py "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/globalgamemanagers.assets" --object-id 65 --names-offset 0x10 --buffers-offset 0x8a8 --textures-offset 0x880 --output .cache/procedural-modeling/render-chain-followup/summerhouse/shader65-parameters.json
```

后两种输出文件已存在时显式拒绝覆盖；复跑可改输出文件名。该轮局部 CIL 投影为 `.cache/procedural-modeling/render-chain-followup/summerhouse/pixelate-cil.txt`，来自同一身份的离线完整 CIL，与 REA 成员锚点交叉核对；不冒称由 shader 解码器产生。

**Answered（静态）：** 配置 Shader 65 到材质/全局纹理、纹理槽到实际 sample/深度输出、blend/depth 前缀、单块修改到层筛选渲染接口。**Unresolved（静态）：** inline sampler/实际 LOD、引擎最终 attachment 及所有状态覆盖、所有场景和清理所有者、完整主体 shader。**Not Run（运行）：** 画面、过滤边缘、透明深度互遮、缩放时句柄复用/分配、CPU/GPU 帧时间。运行验收另见[统一验证清单](../74-runtime-validation-cases.md)。自研可独立制定颜色/深度合成和局部缓存契约，不携带本作素材或恢复代码进入产品。
