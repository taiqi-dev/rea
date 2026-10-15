# SUMMERHOUSE：回贴过滤与 LOD 的静态来源

[07](07-pixel-blit-depth-and-local-render-route.md)已经确认颜色、深度各取样一次并回写颜色/深度。本篇补两个上游：**包内 inline sampler 的原始记录为 `0x54 / s0`，按固定版本格式解读是 Point + Clamp；LOD 则来自引擎共享属性块，复制 pass 明确写 0，最终自定义材质回贴重载沿用其当前值。** 因此“该路径先写入 LOD 0”有指令依据，“所有帧回贴必定 LOD 0”仍需要额外的调度条件。

## 证据身份与边界

资源仍为 `C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/globalgamemanagers.assets` 的 Shader 65，Unity `2023.2.22f1`、SerializedFile 22、无 type tree；对象文件偏移 `398544`、长 `3428` B，与 [07](07-pixel-blit-depth-and-local-render-route.md)同一输入。游戏程序集 `Managed/Assembly-CSharp.dll` 为 `186880` B、MVID `84569538-a19f-4c17-8ccf-f40b95e99253`。

本次新增读取同一安装目录内 `Managed/Unity.RenderPipelines.Core.Runtime.dll`：`734208` B，MVID `ffa9e7c4-c7b1-415b-b53a-4e040bb18df8`，SHA-256 `1a547dbe27b3426a569e9f61180e5fdca05c1e6415e0aea4dda343143f61aaf0`。摘要仅用于用户已授权的游戏证据身份。REA 对 `UnityEngine.Rendering.Blitter` 的成员 Evidence 为 `ev_8d6a21bc0f8f6e21be17167a58c5d720192a5984de466265dc747b7ec0780eb8`；40 个自有方法完整选中，无解码问题。新增[离线 CIL 读取器](tools/ManagedCilProbe/Program.cs)再读方法体和 metadata token，未加载目标程序集执行，也未执行其中的静态构造器。

## 过滤：原始记录和格式解读分开

Shader 65 的名称表相对 `0x10`、fragment 纹理表 `0x880`、constant buffer 表 `0x8a8`，三者在 [07](07-pixel-blit-depth-and-local-render-route.md)已交叉核对。参数表结束位置为 `0x8e4`；新增[定点读取器](tools/sampler_probe.py)继续读取以下字段：

| 对象相对位置 | 实际值       | 原始含义或读取边界           |
| ------------ | ------------ | ---------------------------- |
| `0x8e4`      | `0`          | UAV 参数数目                 |
| `0x8e8`      | `1`          | inline sampler 记录数        |
| `0x8ec`      | `0x54`（84） | sampler 编码，uint32         |
| `0x8f0`      | `0`          | bind point，即 `s0`          |
| `0x8f4`      | 表结束       | 本探针止于这里，不猜后续结构 |

两张纹理的参数记录仍是 `_MainTex→t0`、`_DepthTex→t1`、sampler index `0xffffffff`。fragment 的两个 `sample_l` 指令实际都用 `s0`，所以这个 sentinel 不表示“没有采样器”。它们共享上述独立 inline sampler。

编码解释参照 AssetRipper 的 ShaderRecoveryPlugin 固定提交 `da11bd56bc4b149f63ee6c55520c328489d07055`：[ResourceBindingChunk.cs](https://github.com/AssetRipper/ShaderRecoveryPlugin/blob/da11bd56bc4b149f63ee6c55520c328489d07055/ShaderTextRestorer/Resources/ResourceBindingChunk.cs#L70-L91)、[SamplerFilterMode.cs](https://github.com/AssetRipper/ShaderRecoveryPlugin/blob/da11bd56bc4b149f63ee6c55520c328489d07055/ShaderTextRestorer/Resources/SamplerFilterMode.cs)、[SamplerWrapMode.cs](https://github.com/AssetRipper/ShaderRecoveryPlugin/blob/da11bd56bc4b149f63ee6c55520c328489d07055/ShaderTextRestorer/Resources/SamplerWrapMode.cs)。这套解读取低 2 位为 filter，随后每 2 位分别为 U/V/W wrap，bit 8 为 comparison；Point=0、Clamp=1。因此：

```text
filter = 0x54 & 3        = 0 → Point
wrapU  = (0x54 >> 2) & 3 = 1 → Clamp
wrapV  = (0x54 >> 4) & 3 = 1 → Clamp
wrapW  = (0x54 >> 6) & 3 = 1 → Clamp
comparison = false
```

**结论层级：** `0x54`、slot 0 与 `sample_l s0` 是当前包内直接事实；Point/Clamp 是有来源的格式解读。上述恢复器自身在 sampler 重建处保留 `#warning Needs work`，所以不把它升级为 Unity 官方 ABI 保证或驱动实测。仅阅读了固定版本源码，没有安装或构建该恢复器。

05 中低分辨率 RT 申请时的 Point 参数与这个结果相符，但两者属于不同对象：RT 的过滤申请不能代替 Shader 的 inline sampler 证明。像素化也首先来自低分辨率重绘，再由回贴取样保持块状边界；这份 fragment 内没有另一套 UV 像素取整公式。

## LOD：复制明确写 0，回贴继承共享值

下表 token 均相对于所列本地 DLL；不同程序集中的 MemberRef 不能直接按 token 数字等同。调用签名、所属类型、参数数目和实际方法体一起核对。

| 环节                          | 静态指令                                                                                                                                             | 状态影响                                                                                          |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| ID 创建，Core DLL             | `Blitter+BlitShaderIDs..cctor` `0x06001089`，`IL_003C` 载入字面量 `_BlitMipLevel`，`IL_0041` 调 `Shader.PropertyToID`，`IL_0046` 写字段 `0x04000997` | 后续属性写入对应 Shader 声明的同名 LOD                                                            |
| 属性块创建，Core DLL          | `Blitter..cctor` `0x06000B71`，`IL_0000` new `MaterialPropertyBlock`，`IL_0005` 写静态字段 `0x0400060E s_PropertyBlock`                              | 是 Blitter 各重载共享的块，不是每个 pass 新建一份                                                 |
| 游戏复制调用，Assembly-CSharp | `CopyDepthPass.Execute` `0x060003E1`，`IL_0064 ldc.r4 0`、`IL_0069 ldc.i4.1`、`IL_006A call 0x0A0003D2`                                              | 成功复制分支调用 `BlitColorAndDepth(cmd,color,depth,scaleBias,0,true)`；无有效源的分支跳过它      |
| 真正 LOD writer，Core DLL     | `BlitColorAndDepth` `0x06000B59`、RVA `188108`，`IL_0000..000C` 对共享块执行 `SetFloat(_BlitMipLevel,arg4)`                                          | 上一行的 `0` 被写进共享属性块；再设 scale/纹理并绘制                                              |
| 游戏回贴调用，Assembly-CSharp | `BlitBackPass.Execute` `0x060003E9`，`IL_0076 call 0x0A0003DE`                                                                                       | 调用五参数自定义材质重载 `BlitTexture(cmd,RTHandle,scaleBias,material,pass=0)`                    |
| 回贴重载，Core DLL            | `BlitTexture` `0x06000B5B`、RVA `188234`、47 B IL；`IL_0000..0020` 只写 `_BlitScaleBias`、`_BlitTexture`，`IL_0029` 调 `DrawTriangle`                | **没有写或清除 `_BlitMipLevel`**，也没有新建属性块                                                |
| 交给绘制，Core DLL            | `DrawTriangle` `0x06000B52`，低 shader level 分支 `IL_0017`、其余分支 `IL_002D` 都载入 `s_PropertyBlock`，随后调用 `DrawMesh`/`DrawProcedural`       | 自定义回贴材质收到共享块当时持有的属性；Shader 的 `_BlitMipLevel→cb0[1].x` 被两个 `sample_l` 消费 |

40 个 Blitter 自有方法的本次 CIL 投影中没有 `MaterialPropertyBlock.Clear` 调用。其它重载确实会修改同一 LOD 字段，例如 `BlitTexture 0x06000B55` 在 `IL_000B` 把它的 float 参数写入，再调用自定义材质重载；这排除了“共享块是私有且只可能取 0”的错误理解。此搜索范围不涵盖所有程序集的反射或外部访问。

**已证条件式：** 复制成功写 0 后，若最终回贴前没有其它调用改写同一个块的 `_BlitMipLevel`，回贴使用的 LOD 为 0。若复制被空源检查跳过，则这个写 0 的前提也不成立。当前未展开所有 renderer feature 和相机之间的交错，不能由 enqueue 的相对顺序推成所有帧的绝对值。是否有 mip 链、驱动对可用 mip 的限制及最终有效取样仍不属于这段 IL 的证明。

## 可复核的构造演算

过滤位演算见上式。再令 `M` 表示共享块中的 LOD：成功复制使 `M←0`；自定义回贴重载只改 scale/texture，因此保留 `M=0`。假设在两者之间插入一次接受 float LOD 的 Blitter 调用，实参为 2，则该调用使 `M←2`，后续自定义重载仍保留 `M=2`。这是根据实际 writer/non-writer 的**静态反例构造**，不是声称游戏帧中存在该插入调用，也不声称没有 mip 链时能实际取到第 2 层。

按上述 Point/Clamp 格式解读，在指定 mip 的 4×4 纹理上取 UV `(0.37,0.62)`，非边界点对应整数纹素 `(1,2)`，不计算相邻四个纹素的双线性平均；越出 `[0,1]` 的坐标被约束到边缘。该算例说明恢复出的状态语义，不是屏幕像素验证。

## 复现、验证和保留项

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/sampler_probe.py "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/globalgamemanagers.assets" --output .cache/procedural-modeling/static-chain-followup/summerhouse/shader65-sampler-recheck.json
dotnet build docs/studies/procedural-modeling/summerhouse/tools/ManagedCilProbe/ManagedCilProbe.csproj --disable-build-servers -p:RestoreSources= -p:NuGetAudit=false
dotnet .cache/procedural-modeling/static-chain-followup/summerhouse/managed-bin/net9.0/ManagedCilProbe.dll "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/Managed/Unity.RenderPipelines.Core.Runtime.dll" UnityEngine.Rendering.Blitter "*" .cache/procedural-modeling/static-chain-followup/summerhouse/blitter-cil-recheck.json
```

读取器使用已安装的 .NET 9 SDK，无额外 package；构建中间件和产物写入 ignored `.cache`。输出 JSON 使用新建模式，已存在时拒绝覆盖。游戏类的 exact type 分别是 `Rendering.PixelateRendererFeature.PixelateLayer+CopyDepthPass`、`Rendering.PixelateRendererFeature.PixelateLayer+BlitBackPass`；Core 内 ID 类是 `UnityEngine.Rendering.Blitter+BlitShaderIDs`。

本轮原始投影保存于 ignored `.cache/procedural-modeling/static-chain-followup/summerhouse/` 的 `shader65-sampler.json`、`blitter-cil.json`、`blit-property-ids.json`、`copy-depth-cil.json`、`blit-back-cil.json`。静态解析、构建和字段演算通过；仍保留采样器格式的跨版本解释边界、完整交错写入、有效 mip/attachment 与引擎覆盖。游戏、抓帧、过滤画面和性能测量均为 **Not Run**，依本次要求不执行。独立实现可显式为每次回贴设置 LOD 和 sampler，避免依赖共享可变属性的历史值。
