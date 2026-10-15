# 沙堡：相机颜色临时纹理的格式选择

本篇追 [09](09-camera-color-depth-resource-provenance.md) 中 A 颜色附件和 opaque 副本共用的静态 `colorFormat`。输入仍是同一 Sandcastle Demo 安装版本的 `GameAssembly.dll`、IL2CPP metadata v39，以及只读查看的 `Sandcastle_Data/globalgamemanagers`；制品身份沿用 [01](01-artifact-and-method-map.md)，本轮未新算摘要。没有启动游戏。下面的 `HDR` 指代码传给 Unity 的**格式类别请求**，不是已观测的最终像素格式或显示输出能力。

## 唯一核到的静态赋值者

IL2CPP metadata 将 `BeachRenderPipeline.colorFormat` 列为该类型字段，`BeachRenderPipeline..cctor` 的 `0x180473091–0x1804730b2` 给出唯一核到的静态字段写入：

```text
0x180473091  ecx = 1
0x180473099  call 0x181c565a0        ; SystemInfo.GetGraphicsFormat(format)
0x1804730b2  [BeachRenderPipeline static +0x50] = eax
```

`UnityEngine.CoreModule.dll` 的 metadata token `0x6000c87` 和同模块 codegen 指针表把 `0x181c565a0` 定位为 `SystemInfo.GetGraphicsFormat(DefaultFormat format)`；同一 metadata 的 `DefaultFormat` enum 把 `HDR=1`、`LDR=0`。因此此版本的显式选择是 **`colorFormat = SystemInfo.GetGraphicsFormat(DefaultFormat.HDR)`**。该方法体只是通过 Unity internal call 转发到运行时（本地 `0x181c565a0–0x181c565ce`）；静态制品没有给出查询返回的 `GraphicsFormat` 数值。`HDR` 参数本身不能证明最终一定是浮点、某一通道位深或某个具体 D3D 格式。

为检查“还有没有另一处赋值”，使用既有 `codegen-map-all.json` 的 `.pdata` 边界，对 20 个有方法体的 `BeachRenderPipeline` 方法逐一有界反汇编。唯一可归属此静态区 `+0x50` 的 store 是上述 `0x1804730b2`；其他方法里出现的 `+0x50` 写入位于栈帧或另外的局部结构，不能算同一字段。这证明的是**此类已映射方法中的显式写入集合**；未将动态反射或 Unity native 内部状态当作已穷尽。

## 两次颜色描述符申请会进一步转换格式

`SetupColorDepthTarget` 先为 A 颜色附件创建 `RenderTextureDescriptor(width,height)`，在 `0x180471b6c–0x180471b74` 从静态 `+0x50` 读取上述值并调用 `set_graphicsFormat`。它随后在 `0x180471b88` 调 `QualitySettings.get_activeColorSpace` (`0x181c16200`)，将“返回值等于 1”的布尔值交给 `set_sRGB` (`0x180471b9d`)。metadata 的 `ColorSpace` enum 定义 `Gamma=0`、`Linear=1`。在 `CopyOpaqueDepth` 的 opaque 颜色副本上，`0x18046daf7–0x18046db28` 重复同一静态格式与色彩空间判断。两处 descriptor 之后分别传给 `CommandBuffer.GetTemporaryRT`：A 在 `0x180471c69`，opaque 副本在 `0x18046dbf8`。

`RenderTextureDescriptor.set_graphicsFormat` (`0x181c2e6f0–0x181c2e769`) 先写其内部 `+0x14` 的格式字段，再通过 `GraphicsFormatUtility.IsSRGBFormat` (`0x181c938f0`) 同步 descriptor `+0x2c` 的 sRGB 标志位。后续 `set_sRGB` (`0x181c2e770–0x181c2e807`) 不是仅翻转标志：它在传入 true **且** `activeColorSpace==Linear` 时调 `GraphicsFormatUtility.GetSRGBFormat` (`0x181c93580`)，否则调 `GetLinearFormat` (`0x181c93500`)，再回调 `set_graphicsFormat`。这些 API 名称分别由 CoreModule metadata token `0x6000798/0x600079f/0x6001415/0x6001416/0x6001417` 与同模块方法指针核到。

设 `F_HDR = SystemInfo.GetGraphicsFormat(DefaultFormat.HDR)`，且两次相邻的色彩空间查询在该调用期间保持一致，则本地代码的构造演算是：

| `QualitySettings.activeColorSpace` | 调用 `set_sRGB` 的布尔参数 | 交给 `GetTemporaryRT` 的颜色 descriptor 格式                              |
| ---------------------------------- | -------------------------: | ------------------------------------------------------------------------- |
| `Linear=1`                         |                       true | `GetSRGBFormat(F_HDR)`；`set_graphicsFormat` 再以 `IsSRGBFormat` 更新标志 |
| `Gamma=0`                          |                      false | `GetLinearFormat(F_HDR)`；同样重新更新标志                                |

这里的两个转换函数可能对不具备对应变体的具体 `F_HDR` 返回原格式；本轮没有运行时 `F_HDR`，所以表中是**准确调用关系**而非具体格式枚举值。A 和 opaque 副本两次执行相同表达式，静态代码没有针对 opaque 副本另设一个颜色位深。B 深度附件与 depth 副本则独立调用 `set_colorFormat(RenderTextureFormat.Depth=1)` 并设 `depthBufferBits=32`（[09](09-camera-color-depth-resource-provenance.md)），不使用 `colorFormat +0x50`。

## 资源配置输入能确定到哪一步

选定的无扩展名 `globalgamemanagers` 是 Unity `6000.4.10f1`、SerializedFile v22、19 个对象；class `129` 对象 `pathID=1` 位于文件 `0x4c0`、916 字节，class `47` 对象 `pathID=12` 位于 `0x17730`、824 字节。但文件没有内置 type tree；本轮未找到经该**精确版本**验证的字段布局，因此没有把任意 0/1 字节解释为 PlayerSettings 色彩空间，也没有据资源猜当前 `activeColorSpace`。实际代码查询的是运行时 `QualitySettings.get_activeColorSpace`，不是读取本篇已解出的固定常量。与之不同，`DefaultFormat.HDR=1` 是调用点立即数加 metadata enum 的直接证据，不需要项目配置文件猜测。

这也限定了可回答的问题：**已证实 HDR 类别请求、运行时格式查询、Linear/Gamma 条件转换、两次颜色 RT 使用同一规则**；**尚不能静态确定**本机实际分支、`F_HDR` 的数值、转换后 `GraphicsFormat`、最终 sRGB 标志、驱动支持与拷贝像素。独立实现可选择相同的“按设备请求 HDR 格式，再按色彩空间构造颜色目标”的决策结构，但应依据自己的目标平台、质量设置和画面验收决定具体格式。

## 复现与验证边界

新增原始证据位于 `.cache/procedural-modeling/static-submission-followup/sandcastle/`：`pipeline-method-audit/` 的 20 个有界方法切片、`GetGraphicsFormat.txt`、`SetGraphicsFormat.txt`、`SetSRGB.txt`、`SetColorFormat.txt`、`format-types.json`、`format-method-map.json`、`global-settings-index.json`。`.cctor`、`SetupColorDepthTarget` 和 `CopyOpaqueDepth` 的原始片段沿用 [09](09-camera-color-depth-resource-provenance.md) 所列缓存。方法范围来自同版本 `codegen-map-all.json`；CoreModule API 名称由 `metadata39.py` 和 `map_codegen.py` 映射；`DefaultFormat`、`ColorSpace` 数值由 [`enum_defaults.py`](tools/enum_defaults.py) 的 v39 默认值读取器核验；资源索引由共享 [`unity22-compute-probe.py`](../tools/unity22-compute-probe.py) 在严格对象边界内读取。

**Not Run**：游戏、GPU 抓帧、运行时系统格式查询、任何图形 API 的显存/像素验证及性能计时。未复制游戏资产或恢复代码到正式交付。
