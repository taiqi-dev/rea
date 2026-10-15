# 沙堡：水面所用相机颜色与深度纹理的静态来源

本篇闭合 [08](08-material-bindings-render-state-and-invalidation.md) 留下的两张相机纹理生产者断点。证据来自同一安装版本的 `GameAssembly.dll`、`Sandcastle_Data/il2cpp_data/Metadata/global-metadata.dat` 和 [06](06-surface-materials-and-effects.md) 已核的 Shader 587；文件身份沿用 [01](01-artifact-and-method-map.md) 的记录，本轮没有扩大输入或重新计算摘要。研究全程只读、未运行游戏。以下“调用”是静态原生指令事实；实际一帧的图像、显存和耗时仍需运行抓帧。

## 属性 ID 的字符串和句柄各有独立来源

`BeachRenderPipeline..cctor`（`0x180472c20–0x180473803`）先调用 `Shader.PropertyToID` (`0x181c1aa30`)，将结果写入该类静态区 `+0x2c/+0x30/+0x34/+0x38`，之后调用 `RenderTargetIdentifier..ctor` (`0x181c85760`) 构造静态区 `+0x80/+0xa8/+0xd0/+0xf8` 四个目标标识。字段名来自 IL2CPP metadata 的 `BeachRenderPipeline` 字段表，地址与赋值顺序来自 `.cctor` 指令。`+0x34` 和 `+0x38` 分别是 `cameraOpaqueTextureId`、`cameraDepthTextureId`；这不是根据 Shader 名称倒推的。

新增的 [有界字符串探针](tools/camera_texture_probe.py) 读取 `.cctor` 在各次 `PropertyToID` 前传入的文件支持 `.data` 槽。该版本槽内是 `0xa000xxxx` 使用编码；选中四项均满足 `xxxx=2×literalOrdinal+1`，再用 metadata v39 的 `string_lit` 偏移表和 `string_lit_data` 严格解 UTF-8，并用期望值校验。该等式是对此版本、这些槽的实际解码，不宣称适用于任意 IL2CPP 制品。

| 静态 ID 字段及偏移                 | `.cctor` 传入的槽 / 文件偏移 | 编码 → metadata literal 序号 → 真正字面量       | 目标标识所在静态偏移 |
| ---------------------------------- | ---------------------------- | ----------------------------------------------- | -------------------- |
| `cameraAttachmentATextureId +0x2c` | `0x182958b80 / 0x2957780`    | `0xa00030ff → 6271 → _CameraColorTexture`       | `+0x80`              |
| `cameraAttachmentBTextureId +0x30` | `0x182958b18 / 0x2957718`    | `0xa00030fd → 6270 → _CameraAttachmentBTexture` | `+0xa8`              |
| `cameraOpaqueTextureId +0x34`      | `0x182958c50 / 0x2957850`    | `0xa0003103 → 6273 → _CameraOpaqueTexture`      | `+0xd0`              |
| `cameraDepthTextureId +0x38`       | `0x182958be8 / 0x29577e8`    | `0xa0003101 → 6272 → _CameraDepthTexture`       | `+0xf8`              |

第一行也揭示字段名与真正属性字面量不完全相同：A 附件使用 `_CameraColorTexture`，不能把 `cameraAttachmentATextureId` 当作原字符串。水 Shader 587 的片元纹理表则直接声明 `_CameraOpaqueTexture→t1/s1`、`_CameraDepthTexture→t2/s2`，对应 [06](06-surface-materials-and-effects.md) 的 DXBC 取样与深度线性化。

## 两路资源的创建、拷贝和全局写入

`Render` 在 `0x180471638` 调用 `SetupColorDepthTarget`，之后是 `RenderSkybox`、`RenderOpaques`、`RenderBehind`，在 `0x1804716b9` 调用 `CopyOpaqueDepth`，再在 `0x1804716e1` 调用 `RenderTransparents`。`RenderBehind` (`0x18046ebf0–0x18046f056`) 内有 `CommandBuffer.DrawRendererList` (`0x18046effa`)，但未观察到它创建或全局设置这两张副本；它的绘制发生在拷贝调用之前。

| 阶段与原生地址                                  | 资源事实                                                                                                                                                                                                                                                     | 对应 Unity 方法的 metadata→codegen 映射                                                                                                             |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SetupColorDepthTarget 0x180471b31–0x180471ccd` | 以同一输入宽高创建 A、B 两个 `RenderTextureDescriptor`，分别用 ID `+0x2c`、`+0x30` 调用 `GetTemporaryRT`。A 设置 `depthBufferBits=0`、使用静态 `colorFormat`；B 设置 `colorFormat=1`、`depthBufferBits=32`。metadata enum 的 `RenderTextureFormat.Depth=1`。 | `RenderTextureDescriptor..ctor 0x181c2dfc0`，各 setter `0x181c2e6f0/0x181c2e540/0x181c2e680`；`CommandBuffer.GetTemporaryRT 0x181c67120`            |
| `SetupColorDepthTarget 0x180471ce0–0x180471d86` | 把 A 目标标识 `+0x80` 作为颜色、B `+0xa8` 作为深度传给 `SetRenderTarget`，在条件分支中 `ClearRenderTarget`。                                                                                                                                                 | `CommandBuffer.SetRenderTarget(color,depth) 0x181c78900`；`ClearRenderTarget 0x181c60970`                                                           |
| `CopyOpaqueDepth 0x18046dac4–0x18046dd6e`       | 再用同一宽高与 `+0x34/+0x38` 两个 ID 分别申请 opaque、depth 临时目标。第一个从 A `+0x80` 向 opaque `+0xd0` 调用 `Blit`；第二个从 B `+0xa8` 向 depth `+0xf8` 调用 `CopyTexture`。                                                                             | `GetTemporaryRT 0x181c67120`、`CommandBuffer.Blit(source,dest) 0x181c5fda0` (`0x18046dc7f`)、`CopyTexture(source,dest) 0x181c61390` (`0x18046dd6e`) |
| `CopyOpaqueDepth 0x18046dd81–0x18046de14`       | 以 `cameraOpaqueTextureId +0x34` 及 opaque 目标 `+0xd0` 调一次 `SetGlobalTexture`；再以 `cameraDepthTextureId +0x38` 及 depth 目标 `+0xf8` 调第二次。ID 的字面名称在上表已解码，因此两张纹理的 **CPU 全局写入 → Shader 587 对应名称取样** 形成静态闭环。     | `CommandBuffer.SetGlobalTexture(nameID,value) 0x181c738e0`，调用点 `0x18046ddc1`、`0x18046de14`                                                     |
| `Release 0x18046e453–0x18046e4a7`               | 依次对 ID `+0x2c/+0x30/+0x34/+0x38` 调用 `ReleaseTemporaryRT`；`Render` 在透明/后续效果和最终合成之后才调用 `Release` (`0x180471878`)。                                                                                                                      | `CommandBuffer.ReleaseTemporaryRT 0x181c6e230`                                                                                                      |

两次 `GetTemporaryRT` 的过滤参数也不同：颜色附件/opaque 副本均传 `1`，B 附件/depth 副本均传 `0`；同一 metadata 的 `FilterMode` 枚举把 `1` 定义为 `Bilinear`、`0` 定义为 `Point`。这里报告的是申请参数，不能据此推断每个图形 API 下 `Blit` 或 `CopyTexture` 的实际像素结果。特别是深度路径调用 `CopyTexture`，并非颜色路径的同一次 `Blit`，两个资源在代码中拥有不同的临时 RT ID 和目标标识。

由此可精确回答 [08](08-material-bindings-render-state-and-invalidation.md) 的疑问：水面 `_CameraOpaqueTexture` 来自透明物体之前 A 颜色附件的 `Blit` 副本；`_CameraDepthTexture` 来自 B 深度附件的 `CopyTexture` 副本。`RenderBehind` 排在副本之前，所以它的绘制调用也位于快照之前；其具体像素是否进入颜色副本仍取决于被绘制对象和渲染条件。水片元先用偏移 UV 取深度并判断折射遮挡，再取颜色的公式见 [06](06-surface-materials-and-effects.md)。

## 复现与证据边界

原始切片和派生映射仅保存在 `.cache/procedural-modeling/static-chain-followup/sandcastle/`：`PipelineCctor.txt`、`SetupColorDepthTarget.txt`、`RenderBehind.txt`、`Release.txt`、`camera-literal-bindings.json`、`unity-render-types.json`、`unity-render-method-map.json`；`CopyOpaqueDepth`、`Render` 原始切片沿用 `render-chain-followup/sandcastle/Pipeline_CopyOpaqueDepth.txt` 和 `Pipeline_Render.txt`。选中函数范围来自已有同版本 `codegen-map-all.json`，按本机 `dumpbin /DISASM:NOBYTES /RANGE` 截取。对 Unity 托管 API 名称则先用 `metadata39.py --image UnityEngine.CoreModule.dll` 读取方法 token，再用 `map_codegen.py` 对该模块指针表映射到调用目标；不是凭地址命名。

字符串复现（输出必须为新路径）：

```powershell
python -X utf8 docs/studies/procedural-modeling/sandcastle/tools/camera_texture_probe.py "C:/Software/Steam/steamapps/common/Sandcastle Demo/GameAssembly.dll" "C:/Software/Steam/steamapps/common/Sandcastle Demo/Sandcastle_Data/il2cpp_data/Metadata/global-metadata.dat" --binding cameraAttachmentATextureId:0x2c:0x182958b80:_CameraColorTexture --binding cameraAttachmentBTextureId:0x30:0x182958b18:_CameraAttachmentBTexture --binding cameraOpaqueTextureId:0x34:0x182958c50:_CameraOpaqueTexture --binding cameraDepthTextureId:0x38:0x182958be8:_CameraDepthTexture --output .cache/procedural-modeling/static-chain-followup/sandcastle/camera-literal-recheck.json
```

**静态已答**：两张资源各自的临时 RT ID、颜色/深度附件、`Blit`/`CopyTexture` 方向、全局纹理设置与水 Shader 属性名称。**仍未知**：运行时实际相机宽高与 render scale、颜色图形格式的最终值、特定 GPU/API 下复制后的像素和性能、该帧哪些 `RenderBehind` 对象实际进入副本。**Not Run**：游戏、渲染抓帧、GPU/CPU 计时和跨 API 运行验证。独立实现可借鉴先固定颜色/深度快照再绘制折射水面的数据流，应自行设计资源、材质参数和效果。
