# SUMMERHOUSE：遮罩纹理来源与截图相机的目标切换

[10](10-low-resolution-mips-and-attachments.md)已解释普通主相机的低分辨率目标，本篇补上两个具体例外。**Masking Camera 的外部目标确实是 `MaskingMap`：2048×2048、Point/Clamp、关闭 mip。ScreenshotTaker 绑定的则是主相机，静态代码会临时给它设置 1024×1024 的 RenderTexture。** 因而主相机的空 target 配置不能推广到截图调用内部；遮罩纹理也不是主相机低分辨率颜色目标。

## 证据范围与读取方法

仍只读取同一安装的 `SUMMERHOUSE_Data`。`Assembly-CSharp.dll` 为 186880 B、MVID `84569538-a19f-4c17-8ccf-f40b95e99253`，CoreModule 为 1717496 B、MVID `f07e5f68-ed2b-4769-8d43-49b644099efa`，与[08](08-filtering-and-lod-provenance.md)、[10](10-low-resolution-mips-and-attachments.md)身份一致，未重算摘要。新增原始投影在 `.cache/procedural-modeling/static-tail-followup/summerhouse/`。

新增[目标读取器](tools/mask_target_probe.py)使用同一固定 [TypeTreeDumps 2023.2.22f1 布局](https://github.com/AssetRipper/TypeTreeDumps/blob/20ba06e00e0625de0e49a502c6868d6cc86d0f0b/InfoJson/2023.2.22f1.json)，复用[通用对象读取器](../sandcastle/tools/player_color_space_probe.py)的边界/对齐检查。[SerializedFile 索引器](../tools/unity22-compute-probe.py)新增可选 external 表读取，按[AssetStudio 自身读取顺序](https://github.com/Perfare/AssetStudio/blob/master/AssetStudio/SerializedFile.cs)解析 objects 之后的 script identifiers、externals、reference types 和 user information；原有默认索引输出不变。它没有通过文件名猜测 PPtr 的 fileID。

`level0` 的 external 表明确为 `1=globalgamemanagers.assets`、`2=sharedassets0.assets`、`3=Library/unity default resources`。metadata 完整消费到文件 212583，等于扩展 header 48 B 加 metadataSize 212535 B；data 从 212592 开始。读取器只解析实际需要的同目录 external，拒绝越出该数据目录的路径。两个 Camera 各消费 184/184 B，两个选定 MonoBehaviour 各 52/52 B，目标 RenderTexture 消费 88/88 B；MonoScript 身份也从当前 external 文件解码核对。

## 遮罩目标的生产、配置和发布

资源连接为：`level0 Camera pathID2197 → targetTexture(2,765) → sharedassets0.assets RenderTexture pathID765`。该 RenderTexture 位于文件 4162128、长 88 B，名称为 `MaskingMap`。以下偏移均相对这 88 B 对象；它是配置对象，不包含一份预烘焙遮罩像素。

| 配置字段                                     |          偏移 | 当前值及解释                                                     |
| -------------------------------------------- | ------------: | ---------------------------------------------------------------- |
| 宽、高                                       |      +20、+24 | 2048、2048                                                       |
| AntiAliasing / MipCount                      |      +28、+32 | 1 / -1；后者不能单独代表启用 mip                                 |
| DepthStencilFormat / ColorFormat             |      +36、+40 | 94=`D32_SFloat_S8_UInt` / 8=`R8G8B8A8_UNorm`                     |
| MipMap / GenerateMips / SRGB                 | +44、+45、+46 | 0 / 1 / 0；请求关闭 mip，颜色非 sRGB                             |
| 动态缩放、显式动态缩放、BindMS               |      +47..+49 | 全为 0                                                           |
| CompatibleFormat / RandomWrite               |      +50、+51 | 1 / 0；允许兼容格式，最终设备格式仍未知                          |
| TextureSettings                              |      +52..+75 | FilterMode=0（Point），Aniso=0，MipBias=0，Wrap U/V/W=1（Clamp） |
| Dimension / VolumeDepth / ShadowSamplingMode | +76、+80、+84 | 2 / 1 / 2                                                        |

GraphicsFormat 的两个枚举值来自当前 CoreModule 声明字段 `0x04001204`、`0x04001254`，Point/Clamp 分别来自 FilterMode `0x040005A2` 和 TextureWrapMode `0x040005A7`，不是凭旧版本枚举表推测。资源过滤配置与[08](08-filtering-and-lod-provenance.md)的 shader inline sampler 格式解读属于不同证据。这些是序列化请求，尚无实际 GPU 格式、显存分配或 mip 层数观测。

MaskingManager 的 MonoBehaviour 为 `level0 pathID7819`，文件 1223352、长 52 B。当前 MonoScript `(1,2200)` 确认类名 `MaskingManager`、assembly `Assembly-CSharp`；自定义字段 `+32` 绑定 Camera `(0,2197)`，`+44/+48` 保存 Z 范围 `-10/+10`。

`MaskingManager.Awake 0x060001B3` 首先调用 `UpdateGlobalMaskParameters`，将相机清屏背景设黑，再设置一个约 0.01 度的 X 旋转，并发布 `_MinMaskPosZ/_MaxMaskPosZ`。`Update 0x060001B4` 每次调用同一参数更新函数；`UpdateGlobalMaskParameters 0x060001B5 / IL_00B6..00C6` 把 `maskingCamera.targetTexture` 交给 `Shader.SetGlobalTexture("_GlobalMaskTexture", ...)`。所以全局 shader 输入的资源身份已闭合到这个真实目标，而非只找到同名纹理。

该函数还计算 `tiling=(1/(2s),1/(2s))`、`offset=(0.5-x/(2s),0.5-y/(2s))`，其中 `s=orthographicSize`、`x/y=相机位置`，分别发布 `_GlobalMaskTiling/_GlobalMaskOffset`。构造演算取 `s=10,x=2,y=-4`，得到 tiling `(0.05,0.05)`、offset `(0.4,0.7)`；只是沿本地 CIL 的算式演算，不是游戏帧采样。遮罩实际绘制内容仍需结合[05](05-materials-pixelization-and-camera.md)的专用 renderer 与材质 pass，不能由 SetGlobalTexture 推断所有对象都被画进遮罩。

## 截图会临时改变主相机的入口条件

ScreenshotTaker 为 `level0 pathID6578`，文件 976784、52 B；MonoScript `(1,874)` 确认为 `ScreenshotTaker`。其 `+32` 的 `gameCamera=(0,2196)` 正是[10](10-low-resolution-mips-and-attachments.md)的 Main Camera，`+44/+48` 的截图宽高均为 1024。当前类 metadata 中 `0x04000275..277` 是依次声明的三个 public 字段；私有 `screenshot` 不属于这个 52 B 的序列化配置。

全游戏 Assembly-CSharp 的 173 个 type、1006 个 method 均成功解码；按 `Camera::set_targetTexture` 操作数筛选仅命中 `ScreenshotTaker.CaptureScreenshot 0x0600023D`，不是全引擎和动态调用的穷尽证明。同范围直接 `SetRenderer`、`RenderTexture.GetTemporary` 调用各为零；后者不能否认 URP/Core 分配器使用临时目标。

| `CaptureScreenshot` CIL | 静态操作与状态                                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------------------------ |
| IL_0000..001B           | `new RenderTexture(width,height,24)`，再把新对象设为 `gameCamera.targetTexture`                        |
| IL_0020..0049           | 读取原景深开启状态，按需关闭；调用 `Camera.Render`，再按原标志打开景深                                 |
| IL_004E..009D           | 令 RenderTexture.active 指向截图目标；创建 RGB24、mipChain=false 的 Texture2D；ReadPixels 全图并 Apply |
| IL_00A2..00B5           | `gameCamera.targetTexture=null`，`RenderTexture.active=null`，Destroy 临时目标                         |
| IL_00BA..010A           | EncodeToPNG，拼接 `ImagesDirectory/CurrentSlot.png` 并调用 File.WriteAllBytes                          |

RGB24 的值 3 由当前 CoreModule 的 TextureFormat 字段 `0x040005B1` 确认。三参 RenderTexture 构造 `0x06001902` 转入带格式参数的构造链，追加值 7 与 `Texture.GenerateAllMips`；截图方法本身没有设置 `useMipMap`。构造最终涉及引擎创建/格式选择，不能把截图请求的 depthBits=24 当成已经测得的 GPU 深度格式，也不能仅凭 mipCount=-1 推出 mip 开关。读回 Texture2D 明确关闭 mip，和临时 RenderTexture 的实际配置是两个问题。

调用来源也已缩到具体分支：`SaveSlotUIButton.RenderSlotImage 0x0600022A / IL_0000..0017` 先比较按钮 slotNumber 与 `SaveGameManager.CurrentSlot`，相等才调用 `Main.ScreenshotTaker.TakeScreenshot`；后者 `0x0600023C / IL_0001` 直接 CaptureScreenshot。返回图用于预览 Sprite。这里只读取调用代码，**没有执行截图、写 PNG 或读取玩家存档**。

正常返回路径把相机和 active 设为 null，未保存/恢复旧 target；整个方法的异常区域表为空，不能声称异常发生时一定执行清理。按序列化主相机原 target=null 的条件，正常返回后回到[10](10-low-resolution-mips-and-attachments.md)的普通入口。在截图的 `Camera.Render` 调用内部，URP 的 targetTexture 非空分支应取这张外部目标的 descriptor；具体 feature 是否在该次 Render 被执行及最终附件结果仍未观测。

成本也应按这两个分支区分：MaskingMap 的固定配置包含 `2048×2048=4194304` 个纹素，不是主相机约 251 高像素化目标的同义项；截图路径还包含整图 ReadPixels、Texture2D.Apply、PNG 编码和文件写入调用。单按 1024² RGB24 的紧密像素表示为 3145728 B（3 MiB），这只是构造数据量，不是 CPU/GPU 峰值内存或暂停时间。现有静态链支持查这些具体成本入口，尚不支持给出 FPS 或分配频率。

## 复现、验证与剩余边界

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/mask_target_probe.py "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/level0" --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --output .cache/procedural-modeling/static-tail-followup/summerhouse/mask-target-recheck.json
dotnet .cache/procedural-modeling/static-chain-followup/summerhouse/managed-bin/net9.0/ManagedCilProbe.dll "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/Managed/Assembly-CSharp.dll" MaskingManager "*" .cache/procedural-modeling/static-tail-followup/summerhouse/masking-recheck.json
```

输出拒绝覆盖；参考版本不匹配、截断对象、错误引用或未完整消费 metadata/对象均失败并保留错误。对 level0、sharedassets0.assets、globalgamemanagers.assets 的旧索引各字段与可选扩展结果逐项相等，三者 metadata 完整消费；短 header、错误格式、文件截断和 RenderTexture 对象截断均被拒绝。原始文件为 `mask-target-resource-final.json`、`masking-manager.json`、`screenshot-taker.json`、`target-texture-setters.json`、两种截图 caller、`graphics-format.json`、`texture-format.json`、`FilterMode.json`、`TextureWrapMode.json`、`rendertexture-ctors.json` 与两个零命中查询。

**Answered（静态）：** 遮罩 target 的 external/fileID/对象配置/全局发布；截图绑定主相机、尺寸、目标切换、正常清理和按钮分支。**Unresolved（静态）：** 原生 RenderTexture 创建默认标志、设备兼容格式、其他程序集或动态调用对相机的改变、实际遮罩可见对象。**Not Run（运行）：** 游戏、相机渲染、GPU/像素/性能验证、私人存档及截图文件写入。
