# SUMMERHOUSE：继承的相机纹理需求来自哪里

[16](16-additional-camera-layout-and-effect-gates.md)读出两台相机的 depth／opaque option 均为2（UsePipelineSettings），但没有给 pipeline 的实际值。本轮从发行资源补上：**GraphicsSettings 和唯一的质量档均指向 URP-HighFidelity；其深度纹理和不透明颜色纹理开关都是1。** 在该资产仍为当前 pipeline 且未被动态改写的前提下，两台相机的相应 getter 都返回true。这个需求不等于某帧已创建、复制或刷新纹理，也不能直接折算显存和帧时。

## 原生设置与自定义资产的边界

只读同版安装 `C:\Software\Steam\steamapps\common\SUMMERHOUSE\SUMMERHOUSE_Data` 的 `globalgamemanagers`、`globalgamemanagers.assets` 与 `Managed/Unity.RenderPipelines.Universal.Runtime.dll`，沿用[00](00-evidence-and-scope.md)身份，未重算摘要。[新读取器](tools/pipeline_texture_prefix_probe.py)按精确2023.2.22f1 Release树完整消费 GraphicsSettings（class30/path7）、QualitySettings（class47/path12）及对应MonoScript；资源均为format22、无type tree。

GraphicsSettings 的 `m_CustomRenderPipeline=(1,2355)`；QualitySettings 的 `m_CurrentQuality=0`，其数组只有一项 `High Fidelity`，该项 `customRenderPipeline` 也是 `(1,2355)`。外部表把file1接到同目录 `globalgamemanagers.assets`。这比在对象任意位置搜索同一引用更精确，但仍是发行配置，不证明当前运行中的质量或pipeline状态。

该文件的path2355是 `URP-HighFidelity`，MonoScript实际类／程序集为 `UniversalRenderPipelineAsset / Unity.RenderPipelines.Universal.Runtime`。本作DLL（644608 B，MVID `441516f4-c7ab-401e-840b-a71a7013b536`）的字段签名及SerializeField顺序，核对到以下九个自定义字段。原生MonoBehaviour部分消费48 B，自定义选定前缀读至116 B；对象总长444 B，**其余328 B未解析**。

| 对象相对偏移 | 字段                                   | 实际值           |
| ------------ | -------------------------------------- | ---------------- |
| 48、52       | k_AssetVersion、k_AssetPreviousVersion | 12、12           |
| 56、60       | RendererType、旧RendererData           | 1、null          |
| 72…100       | RendererDataList，数量2                | 本文件2354、2353 |
| 100          | DefaultRendererIndex                   | 0                |
| 104          | RequireDepthTexture                    | **1**            |
| 108          | RequireOpaqueTexture                   | **1**            |
| 112          | OpaqueDownsampling                     | **0（None）**    |

布尔字段后实际padding为零；两个RendererData引用与[05](05-materials-pixelization-and-camera.md)独立旧投影一致。这里没有把局部前缀冒称为完整pipeline资产解析，也没有用Native QualitySettings中的抗锯齿值代替[16](16-additional-camera-layout-and-effect-gates.md)已核的追加相机AA模式。

## 配置到需求的消费

`UniversalRenderPipelineAsset.get_supportsCameraDepthTexture 0x0600004E` 和 `get_supportsCameraOpaqueTexture 0x06000050` 都只在 `IL_0001` 读上述各自布尔字段。16已核 `UniversalAdditionalCameraData.get_requiresDepthTexture 0x06000728`、`get_requiresColorTexture 0x0600072A`：option=2时读取这些pipeline getter；否则只在option=1时返回true。`UniversalRenderPipeline.get_asset 0x0600081F` 则从 `GraphicsSettings.currentRenderPipeline` 取得当前资产并作URP类型转换，不能仅凭历史资源引用跳过“当前资产仍相同”的前提。

构造演算：采用本资源的pipeline，遮罩相机option=2，pipeline的RequireOpaque=1，则颜色需求getter返回true；这与遮罩相机的后处理开关为0并不矛盾，因为两个开关控制不同的输入。若以后脚本把相机option改为0，则该getter返回false，不再继承pipeline。这个反事实输入仅演示分支，不是已观察到的覆盖。

`InitializeAdditionalCameraData 0x06000808 / IL_0133…0146` 把两个getter结果写入CameraData的requiresDepthTexture／requiresOpaqueTexture。该方法还有Overlay、后处理及后续条件，实际附件/复制还受renderer、pass输入和平台状态影响；本作两相机Base的配置见[15](15-mask-camera-order-and-render-admission.md)。`OpaqueDownsampling=None` 也是需求策略配置，不证明当前复制目标尺寸、实际复制次数或额外成本。pipeline的OnAfterDeserialize另有版本迁移，本轮保存完整CIL作后续入口，未将所有迁移／动态setter穷尽。

## 复算与状态

新 raw 位于 ignored `.cache/procedural-modeling/static-alias-followup/summerhouse/`：`pipeline-texture-options.json`、`pipeline-texture-prefix.json`、`downsampling-enum.json`、`current-pipeline-getter.json` 和 `pipeline-deserialize.json`。CIL由既有[离线工具](tools/ManagedCilProbe/Program.cs)读取，未加载目标程序集执行；没有新REA Evidence，Ghidra既有阻塞未变且未重试。

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/pipeline_texture_prefix_probe.py --game-data 'C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data' --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --metadata .cache/procedural-modeling/static-alias-followup/summerhouse/pipeline-texture-options.json --output .cache/procedural-modeling/static-alias-followup/summerhouse/pipeline-texture-recheck.json
```

读取器核对版本、对象／MonoScript身份、metadata字段顺序、引用及padding，拒绝覆盖输出。**Answered（静态配置）：** 完整原生设置的默认pipeline指向、选定资产前缀、两个纹理开关及继承getter。**Partial：** 资产剩余328 B、运行时当前资产／覆盖、最终附件/复制与成本。**Not Run：** 游戏、目标函数、相机／GPU、私人存档、截图和性能测量。
