# SUMMERHOUSE：遮罩相机的层筛选与纹理内容

[11](11-mask-target-and-camera-overrides.md)已把遮罩相机接到 2048² 的 MaskingMap。本篇补上“哪些块有资格进入这张图”和“图里写什么”，同时修正[05](05-materials-pixelization-and-camera.md)只看 feature LayerMask 的覆盖推导。**主相机排除层 8，遮罩相机只选层 8；Mask 材质的 forward shader 则把世界 Z 归一化到 0–1，写入 RGB，alpha 写 1。** 这些是静态配置、调用与指令，仍没有游戏帧或实际像素。

## 当前文件与完整字段读取

沿用 [00](00-evidence-and-scope.md)、[05](05-materials-pixelization-and-camera.md)、[11](11-mask-target-and-camera-overrides.md)的安装身份。实际读取 `level0`、`sharedassets0.assets`、同一 Assembly-CSharp 和 Universal.Runtime DLL；没有重新计算摘要。原始输出在 `.cache/procedural-modeling/static-slot-followup/summerhouse/`。

新增[遮罩链读取器](tools/mask_render_route_probe.py)使用固定 [TypeTreeDumps 2023.2.22f1 Release 布局](https://github.com/AssetRipper/TypeTreeDumps/blob/20ba06e00e0625de0e49a502c6868d6cc86d0f0b/InfoJson/2023.2.22f1.json)，复用[对象读取器](../sandcastle/tools/player_color_space_probe.py)并补上 UInt16/SInt16 标量支持。它从当前对象表读取两个 Camera、634 个 MeshRenderer、各自的 GameObject 和 Shader621，逐对象要求完整消费。参考只提供格式，数值和对象引用来自本地文件。

这还找到了旧[visual_assets.py](tools/visual_assets.py)的一个字段定位问题：`MeshRenderer.m_Enabled` 在对象 `+12`，`+14` 是 `m_ReceiveShadows`。已修正 producing reader 的取值位置。对当前全部 634 个 Renderer，两字节恰好都为 1，所以旧报告的选定对象启用值和计数没有改变；修正后正式工具的完整 `visual-bindings.json` 与原投影逐项相等。新工具使用完整布局读取，不用这个偏移常量替代字段解析。

## 相机过滤先于像素化的层过滤

| 配置对象                          |             当前位掩码 | 与本篇相关的层                               |
| --------------------------------- | ---------------------: | -------------------------------------------- |
| level0 Main Camera，pathID2196    |            `759=0x2f7` | 包含 0、6，**不含 8**                        |
| level0 Masking Camera，pathID2197 |            `256=0x100` | **仅层 8**                                   |
| 默认 renderer 的 PixelateLayer    |            `471=0x1d7` | 包含 0、6、8，但不能重获相机未剔除保留的对象 |
| 主相机与 feature 的交集           | `759 & 471 = 215=0xd7` | 0、1、2、4、6、7；仍无层 8                   |

相机掩码来自 Camera 的 `m_CullingMask.m_Bits`，不是 GameObject 自身所在的 layer。主相机与辅助相机分别选择默认 renderer 和 renderer1 的配置沿用[05](05-materials-pixelization-and-camera.md)；后者没有该像素化 feature。

本地 URP 的 `UniversalRenderPipeline.RenderSingleCamera 0x060007FF / IL_0027..002A` 取得相机剔除参数，`IL_01C6..01CF` 调 `ScriptableRenderContext.Cull` 并保存结果。游戏 `PixelateLayer+RenderObjectsPass.Execute 0x060003E7 / IL_001E..0031` 从 `RenderingData.cullResults` 取同一类剔除结果，再交给 DrawRenderers，并传自己的 FilteringSettings。其构造 `0x060003E5 / IL_001B..002D` 取得 feature LayerMask 来建过滤设置。因此 layerMask=471 只是后级筛选，**不能证明主相机会绘制层 8**；上一轮按 feature 单独判断“配置覆盖 Mask”的结论到此被收窄。

URP 普通 DrawObjectsPass 的 `InitRendererLists 0x06000986` 同样经 RenderingUtils 建列表；后者 `0x0600061B / IL_0026..002E` 或 render-graph 重载 `0x0600061C / IL_0039..0041` 把 `RenderingData.cullResults`、drawing settings 和 filtering settings 一起交给 RendererListParams。这里没有恢复被上游相机排除对象的独立全场景扫描。最终仍会受 frustum、深度、renderer 层、队列、shader tag 和实际实例状态影响，不能把位掩码交集当作最终可见集合。

在当前 prefab 文件的 634 个 Renderer 中，完整读取的 GameObject layer 分布为：层6有465个、层0有54个、层8有115个。115个层8对象各只有一个材质槽，全部引用本地 Material12 `Mask`。这些对象的本地 active 和 Renderer enabled 都为1；没有由此证明父节点均激活，或这些 prefab 在同一场景全部实例化。

以已解析的 Window07 资源为例：

| prefab 条件          | 主相机层筛选保留的 Renderer                                            | 遮罩相机层筛选保留的 Renderer |
| -------------------- | ---------------------------------------------------------------------- | ----------------------------- |
| 普通 Window07        | Model01 `4542`，层6；6个材质槽                                         | Mask `4659`，层8；Material12  |
| Window07 w character | Model01 `4986`、Character `4750`、Eyes `5121`，层6/0/0；合计16个材质槽 | Mask `5088`，层8；Material12  |

这是 prefab 引用和层筛选的构造比较，不是 1→3 次 draw 的测量。原来整组 prefab 的 Renderer 数2→4仍成立；分到两台相机后，不能把全部 Renderer 都算进主相机像素化重绘。

## Mask 材质的实际 pass 与程序索引

Material12 在[05](05-materials-pixelization-and-camera.md)已完整解析，其 shader 指向同文件 Shader621。该 Shader 对象位于文件3814496、长17756 B，类型树完整消费17756 B；`m_ParsedForm.m_Name=Shader Graphs/Mask`。ParsedForm 长15548 B，随后平台表位于对象 `+15552`，实际平台为4；压缩数据在 `+15600`，压缩2122 B，声明展开7964 B，LZ4解码长度吻合。

全对象 schema 解析给出5个 pass，**不是在压缩字节中搜索 pass 名推断**：

| pass state 名     | LightMode 元数据 | 本篇使用边界                                                    |
| ----------------- | ---------------- | --------------------------------------------------------------- |
| Universal Forward | 未设置 LIGHTMODE | forward 颜色程序；不因 state 名叫 Forward 就假定 LightMode 的值 |
| DepthOnly         | DepthOnly        | 独立深度程序                                                    |
| MotionVectors     | MOTIONVECTORS    | Material12 的 disabled pass 列表禁用该项                        |
| DepthNormalsOnly  | DepthNormalsOnly | 独立法线/深度程序                                               |
| ShadowCaster      | SHADOWCASTER     | 阴影程序                                                        |

URP16 [官方 pass tag 规则](https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@16.0/manual/urp-shaders/urp-shaderlab-pass-tags.html#lightmode)把未设置 LightMode 的 pass 归入 SRPDefaultUnlit。当前 DLL 的 `DrawObjectsPass` 构造 `0x06000981 / IL_000A..0031` 确实列出 SRPDefaultUnlit、UniversalForward、UniversalForwardOnly；游戏重绘 pass 构造也列出这三个和 LightweightForward。因此这份颜色程序能匹配该类 tag 选择；这不取代相机和其它过滤条件。

forward pass 的 PlayerSubPrograms 明确把 vertex 指向 blob1、fragment 指向 blob3。展开段有15条 `(offset,length,segment)` 记录，全部范围校验通过：blob1 为 `(264,992,0)`、blob3 为 `(1308,496,0)`。各记录内相对+70分别有896 B和416 B的合法DXBC；本机 D3DDisassemble 成功。程序身份由 pass 索引接到记录，避免把别的深度/阴影程序当成颜色程序。

## 遮罩图写入的是归一化的世界 Z

vertex 的 UnityPerDraw 参数表把 `unity_ObjectToWorld` 放到CB1起点。实际指令0..3按该矩阵把输入位置转为世界坐标，指令7把结果送到 `o1.xyz`；fragment 的输入签名把它接到 `v1.xyz`，只使用 Z。forward fragment 的参数表把 `_MinMaskPosZ/_MaxMaskPosZ` 放到 `$Globals` 的字节2080/2084，即 `cb0[130].x/y`。六条指令的前五条执行：

```text
t = (worldZ - minZ) / (maxZ - minZ)
RGB = saturate(t)
A = 1
```

没有在该 fragment 内读纹理、discard、光照计算或写 SV_Depth。颜色 pass 的序列化状态为 source/destination blend=1/0、color mask=15、ZTest=4、ZWrite=1、Cull=2；fragment 不显式写 SV_Depth 不代表深度写入关闭，默认深度仍来自光栅化结果。设备、URP depth priming 或其它状态覆盖未观测。

[11](11-mask-target-and-camera-overrides.md)证明 MaskingManager 发布的两个全局范围值初始为 `-10/+10`，Material12 也保存同名初值；这里不声称任意后续材质/全局覆盖后的实值。取该初始范围演算，worldZ `-10/0/+10` 分别得到灰度 `0/0.5/1`；低于/高于范围时饱和到0/1。`minZ=maxZ` 时该指令序列没有显式防除零处理，实际配置中两者不同。黑色清屏、灰度编码、正交相机的映射参数与[11](11-mask-target-and-camera-overrides.md)的全局纹理发布合起来，才组成遮罩生产链；最终 shader 如何消费它仍是另一条待补的材质连接。

## 复现与验证状态

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/mask_render_route_probe.py --game-data "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data" --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --output .cache/procedural-modeling/static-slot-followup/summerhouse/mask-route-recheck
```

新工具拒绝已有输出目录，并校验版本、每个对象的完整消费、平台/解压长度、所有program记录范围与被选DXBC的chunk范围。输出是读取元数据和两份反汇编，不执行目标shader。原始结果为 `mask-route/mask-route.json`、该目录两份 `mask-forward-*.asm.txt`，以及上级 `render-single-camera.json`、`draw-objects-pass.json`、`create-renderer-list.json`、`pixel-render-objects.json`、`universal-renderer-ctor.json`、`visual-recheck/visual-bindings.json`。

定点失败检查还确认：截断Shader对象、MeshRenderer启用字节=2、错误参考版本和已有输出目录均被拒绝；结果在 `focused-validation.json`。新增UInt16/SInt16支持后，沙堡旧读取器仍消费912/916 B、返回Linear=1并保留末尾3的Partial状态，没有把标量扩展变成其它资源的布局修订。

**Answered（静态）：** 主/辅助相机和feature的层交集、实际prefab层/Mask材质引用、完整Mask shader pass→程序索引→DXBC→世界Z灰度公式；旧启用字段位置已修正并保持当前投影兼容。**Unresolved（静态）：** renderer配置的其余筛选、最终材质对全局遮罩的消费、加载/动态覆盖及退化范围。**Not Run（运行）：** 游戏、相机渲染、真实绘制集合、GPU目标/像素、同步与性能测量。
