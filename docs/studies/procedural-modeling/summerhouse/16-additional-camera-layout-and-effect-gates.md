# SUMMERHOUSE：相机追加配置的完整布局与效果开关

后续[17](17-taa-target-lifetime-and-disabled-cost.md)补上TAA状态对象与历史纹理的分离：Init不直接分配，普通入口由启用门选择AllocateTargets或DeallocateTargets。本篇的CPU维护与真实成本未知边界继续适用。

[15](15-mask-camera-order-and-render-admission.md)只读到两个 `UniversalAdditionalCameraData` 对象的前 56 B，尚余 124 B。本篇通过同一发行 DLL 的字段类型、`SerializeField`／非序列化标志与嵌套 TAA Settings，把选定布局完整读取到 180 B：**主相机的后处理开关为 1，遮罩相机为 0；两者抗锯齿模式均为 None。** 保存的 TAA 参数不是 TAA 已启用的证据。对象原生准入、动态改写、实际 pass／GPU 成本仍未运行验证。

## 布局的证据与完整消费

只读输入沿用[00](00-evidence-and-scope.md)的 `C:\Software\Steam\steamapps\common\SUMMERHOUSE\SUMMERHOUSE_Data\level0`、`Managed/Unity.RenderPipelines.Universal.Runtime.dll` 与 `UnityEngine.CoreModule.dll`，不重算摘要。URP DLL 为 644608 B，MVID `441516f4-c7ab-401e-840b-a71a7013b536`。本轮增强既有[离线 CIL 工具](tools/ManagedCilProbe/Program.cs)，额外输出字段签名、类型名和 CustomAttribute 的构造器／原始值；用系统 SDK 解析 PE metadata，不加载目标程序集执行。

本作追加数据字段 `0x040007E2…0x040007FC` 中，24 个非静态序列化字段按 metadata 顺序被[新读取器](tools/camera_additional_data_probe.py)逐个核对。`m_Camera`、两个 persistent-data 引用带非序列化标志；私有 `m_VolumeStack` 没有 SerializeField，均不挤入载荷。嵌套 `TemporalAA+Settings` 的六个 SerializeField 成员位于 `0x04000777…0x0400077C`；两个 history 计数字段非序列化。CoreModule 的 `LayerMask` 单个 int32 与 `Vector4` 四个 Single 字段另作 metadata 交叉核对。

两份对象仍为 Main Camera2196 → Additional7384（文件1131824，180 B）、Masking Camera2197 → Additional8109（文件1284160，180 B）。标准 MonoBehaviour 前 32 B 由精确版 Release 树完整读取，追加部分按本作字段类型／属性验证的选定布局读取；全部结束于 180，余量为 0。这里是无自定义 type tree 时的资源与 metadata 交叉解释，不冒称恢复了原 Unity 工程序列化源码。

下表偏移均相对各自 MonoBehaviour 对象首字节；布尔值后按选定布局补齐到 4 B，padding 实际均为零。

| 偏移          | 字段或连续范围                                                    | 主相机                   | 遮罩相机      |
| ------------- | ----------------------------------------------------------------- | ------------------------ | ------------- |
| 32            | RenderShadows                                                     | 1                        | 0             |
| 36、40        | Depth／Opaque Texture Option                                      | 2、2                     | 2、2          |
| 44、48、52    | CameraType／stack 数量／RendererIndex                             | 0、0、-1                 | 0、0、1       |
| 56、60…72     | VolumeLayerMask／VolumeTrigger PPtr                               | 1／null                  | 1／null       |
| 72            | VolumeFrameworkUpdateModeOption                                   | 2                        | 2             |
| 76            | RenderPostProcessing                                              | **1**                    | **0**         |
| 80、84        | Antialiasing／Quality                                             | **0**、2                 | **0**、2      |
| 88、92、96    | StopNaN／Dithering／ClearDepth                                    | 0、0、1                  | 0、0、1       |
| 100、104、108 | AllowXR／AllowHDROutput／UseScreenCoordOverride                   | 1、1、0                  | 0、1、0       |
| 112…144       | ScreenSizeOverride、ScreenCoordScaleBias 两个 Vector4             | 均为零向量               | 均为零向量    |
| 144、148、152 | 旧 RequiresDepth／Color bool、Version                             | 0、0、**2.0**            | 0、0、**2.0** |
| 156…180       | TAA quality、frame influence、jitter、mip bias、variance、sharpen | 3、约0.1、1、0、约0.9、0 | 相同          |

## 配置怎样进入渲染状态

同版 `AntialiasingMode` enum 常量为 None=0、FXAA=1、SMAA=2、TAA=3。`get_antialiasing 0x0600073A` 和 `get_renderPostProcessing 0x06000738` 直接读各自字段。`InitializeStackedCameraData 0x06000807 / IL_00D7…00EA` 在存在追加数据的普通分支，将抗锯齿及质量写入 `CameraData`；`InitializeAdditionalCameraData 0x06000808 / IL_010C…0113` 把后处理 getter 写入 `CameraData.postProcessEnabled`。同方法 `IL_0118…012E` 在 RenderShadows 为 false 时把 `maxShadowDistance` 置零。这些是配置到本次渲染数据的条件连接，不证明某帧执行或所有后续 debug／平台门都保持不变。

`CameraData.IsTemporalAAEnabled 0x0600084D / IL_000E…0015` 首先要求 `antialiasing==3`，不等直接走 `IL_005E` 返回 false；之后还要检查 persistent data、MSAA=1、非 Overlay、空 stack、动态分辨率及后处理。可复算例：在本场景配置已被以上初始化代码消费且未被改写的条件下，两台相机输入 AA=0，第一道门即失败；即使载荷保留 TAA quality=3 和 frame influence≈0.1，也不使该门变真。

这不等于 TAA 参数完全没有 CPU 处理。`UpdateTemporalAAData 0x0600080F` 仍可取得 persistent data，调用 `Init` 并复制 Settings；本篇没有穷尽此入口的全部调用条件或底层分配。因此不能由 AA=None 推出完全没有历史数据维护、零分配或某项精确性能收益。

## 两个旧 bool 为什么不覆盖当前纹理选项

`CameraOverrideOption` 的 2 表示 `UsePipelineSettings`，不是 On。`get_requiresDepthTexture 0x06000728` 和 `get_requiresColorTexture 0x0600072A` 在选项=2时，分别读取当前 pipeline asset 的 `supportsCameraDepthTexture`／`supportsCameraOpaqueTexture`；`get_requiresVolumeFrameworkUpdate 0x06000734` 对 option=2 也转向 pipeline asset。不能把这里的 2 当作强制开启，更不能拿尾部两个旧 bool=0 判定当前纹理需求为 false。

`get_version 0x0600071A` 直接返回 `m_Version`；`OnAfterDeserialize 0x06000752 / IL_0000…000B` 只在 version<=1 时，把旧 bool 转为 0/1 选项并写 version=2。两对象实际版本均为 2.0，静态演算跳到 `IL_003C` 返回，**此兼容迁移本身不会用旧零值覆盖当前 option=2**。其它 setter、动态 pipeline 选择和渲染特性后续修改仍另证。

## 复算、原始记录与状态

新普通静态输出位于 ignored `.cache/procedural-modeling/static-replacement-followup/summerhouse/`：`additional-camera-fields.json`、`taa-settings.json`、`vector4-fields.json`、`layermask-fields.json`、`additional-camera-layout.json`、`additional-deserialize.json`、`version-getter.json`、三个 enum JSON、`aa-getters.json`、`post-getter.json`、`texture-requirement-getters.json`、`initialize-additional-data.json`、`aa-getter-consumers.json`、`taa-update.json` 和 `taa-enabled-gate.json`。没有新 REA Evidence ID；REA native Ghidra 的既有阻塞未变且未重试。

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/camera_additional_data_probe.py --scene 'C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/level0' --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --metadata .cache/procedural-modeling/static-replacement-followup/summerhouse/additional-camera-fields.json --taa-metadata .cache/procedural-modeling/static-replacement-followup/summerhouse/taa-settings.json --output .cache/procedural-modeling/static-replacement-followup/summerhouse/additional-camera-recheck.json
```

metadata JSON 由上述正式 CIL 工具对相同 DLL 的精确类型导出；工具参数和选定类型见 JSON 内 `input/type/coverage`。读取器拒绝覆盖输出，核对字段顺序／类型／序列化标志、对象边界、padding、有限浮点和旧前缀一致性；当前只接受所选空 stack／null trigger 形状，不推广到任意场景。**Answered（静态）：** 原先剩余124 B的字段对应、完整180 B消耗、后处理／AA初始化与旧版本迁移门。**Partial：** pipeline 当前需求、其它覆盖、原生准入／截图入口、真实渲染频率和性能。**Not Run：** 游戏、目标函数、相机绘制、GPU、像素与性能测量。
