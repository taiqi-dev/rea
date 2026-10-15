# SUMMERHOUSE：全局遮罩到材质采样、透明度与裁剪

[12](12-mask-camera-filter-and-shader-data.md)已追到 MaskingMap 的灰度生产。本篇把其中一类实际材质的消费端接通：**Shader622 的前向片元程序有 12 个变体，其中 8 个通过逐变体参数记录绑定 `_GlobalMaskTexture`，4 个普通不透明变体不绑定它。透明变体将比较结果用于 alpha；Alpha Test 变体在主要光照计算之前执行裁剪。** 这不是全部材质的覆盖结论，也没有实际帧、GPU 或性能测量。

## 输入、范围与参数表的关键区别

沿用[00](00-evidence-and-scope.md)、[05](05-materials-pixelization-and-camera.md)和[12](12-mask-camera-filter-and-shader-data.md)的同版安装身份；未重算摘要。新增[材质消费读取器](tools/material_shader_inputs_probe.py)读取 `globalgamemanagers.assets`、`resources.assets` 和 `sharedassets0..4.assets`，按固定 [2023.2.22f1 Release 布局](https://github.com/AssetRipper/TypeTreeDumps/blob/20ba06e00e0625de0e49a502c6868d6cc86d0f0b/InfoJson/2023.2.22f1.json)完整消费每个选定 Material/Shader 对象，合计 **250 个 Material、71 个 Shader**。按字面 external path 可直接解析的材质 shader 引用是 170/250；其余引用没有在本篇强行归一化为本地对象。

七文件的公共 `m_NameIndices` 中没有 `_GlobalMaskTexture`，250 个材质的保存纹理属性也没有这个名称；但**公共名称表不是全部变体的输入全集**。Shader622 的 `m_ParameterBlobIndices` 指向同一展开段内的独立参数记录，名称直接写在这些记录内。90 个材质保存 `_GlobalMaskTiling`、40 个保存 `_GlobalMaskOffset`、110 个保存 `_MaskingDepthCutoff`，也不能单靠保存值判断编译后的程序使用了它们。本篇对 Shader622 解开逐变体参数后才建立消费关系；对另外 70 个 Shader 只统计公共表，不能宣布它们不用全局遮罩。

实际 Shader622 是 `sharedassets0.assets` 的 pathID622，文件偏移 3832256、长 50716 B，完整布局读取同样消费 50716 B。解析名称为 **`Shader Graphs/LitColorTriplanarNormalAnimatedShimmer`**；以此替代[05](05-materials-pixelization-and-camera.md)字符串候选扫描中的尾随 `5`。旧篇的材质 PPtr 身份不变，精确名称以本篇 ParsedForm 为准。Accent01 Material44 和 White Material92 均引用该 Shader，保存 `_ALPHATEST_ON` 关键词；这证明存在游戏材质连接，不证明某一实际帧采用了哪个光照关键词组合。

## 从 pass 到逐变体参数、DXBC

Shader622 有 UniversalForward、ShadowCaster、MotionVectors、DepthOnly、DepthNormals、Universal2D 六个 pass。本篇只解释第一个 pass 的两个 vertex 和十二个 fragment 程序。实际平台表为 `[4]`，单一 LZ4 段压缩 23279 B、展开 260112 B，包含 51 条范围合法的 `(offset,length,segment)` 记录。不能把 51 条全部称为代码：其中包含参数记录。

`progFragment.m_PlayerSubPrograms` 与 `m_ParameterBlobIndices` 按相同二维组及组内位置配对，得到以下精确关系。表中 S/C 分别表示 `_MAIN_LIGHT_SHADOWS` / `_MAIN_LIGHT_SHADOWS_CASCADE`，K 表示 `_LIGHT_COOKIES`；其余关键词写全。

| fragment blob | 参数 blob | 关键词                            | 遮罩绑定 | 可见消费   |
| ------------: | --------: | --------------------------------- | -------- | ---------- |
|            16 |         4 | S                                 | 无       | 无遮罩采样 |
|            17 |         5 | S、`_SURFACE_TYPE_TRANSPARENT`    | t4 / s4  | 输出 alpha |
|            18 |         6 | S、`_ALPHATEST_ON`                | t4 / s4  | 提前裁剪   |
|            19 |         7 | C、K、`_ALPHATEST_ON`             | t5 / s5  | 提前裁剪   |
|            20 |         8 | C、K、`_SURFACE_TYPE_TRANSPARENT` | t5 / s5  | 输出 alpha |
|            21 |         9 | C、K                              | 无       | 无遮罩采样 |
|            22 |        10 | S、K、`_ALPHATEST_ON`             | t5 / s5  | 提前裁剪   |
|            23 |        11 | S、K、`_SURFACE_TYPE_TRANSPARENT` | t5 / s5  | 输出 alpha |
|            24 |        12 | S、K                              | 无       | 无遮罩采样 |
|            25 |        13 | C、`_ALPHATEST_ON`                | t4 / s4  | 提前裁剪   |
|            26 |        14 | C、`_SURFACE_TYPE_TRANSPARENT`    | t4 / s4  | 输出 alpha |
|            27 |        15 | C                                 | 无       | 无遮罩采样 |

十二份参数记录均完整消费，长度依次为 328、592、644、1192、1140、876、856、804、540、980、928、664 B；两份 vertex 参数记录也完整消费。读取器保留头部未释义字和成员未释义字，不将其猜成通用格式字段；它只接受本对象实际的 header、名称/填充、成员和两类资源记录，并要求精确结束。参数资源中的 tag0 记录可与 DXBC 的纹理/采样器槽交叉核对；tag1 的 `UnityPerMaterial,index=3` 与 CB3 使用相合。资源维数字原值保留，二维纹理身份以实际 `dcl_resource_texture2d` 为准。

格式线索参考了工具作者的[参数记录研究](https://github.com/Andreansx/casualties-unknown-apple-silicon/blob/0c0bfaca506331d8e4fac2d7f6f300a6bfcb9b65/tools/rewrap/paramblob.py)，但没有运行其代码或采用其“记录尾部全部是纹理”的假设；本对象末项实际是不同长度的 CB 绑定记录。本地记录的完整消费、配对和 DXBC 才是本篇事实依据。

## 全局投影、世界 Z 和材质阈值落到不同常量缓冲

以 fragment18 / parameter6 为完整示例：参数记录位于展开段 `+13732`、长 644 B。与公共绑定合并后，下列字节位置直接对应 DXBC 寄存器：

| 输入                    | 记录中的缓冲/字节偏移    | DXBC 对应     |
| ----------------------- | ------------------------ | ------------- |
| `_GlobalMaskTiling`     | `$Globals +2112`，float2 | `cb0[132].xy` |
| `_GlobalMaskOffset`     | `$Globals +2120`，float2 | `cb0[132].zw` |
| `_MinMaskPosZ`          | `$Globals +2132`         | `cb0[133].y`  |
| `_MaxMaskPosZ`          | `$Globals +2136`         | `cb0[133].z`  |
| `_AlphaToMaskAvailable` | `$Globals +72`           | `cb0[4].z`    |
| `_MaskingDepthCutoff`   | `UnityPerMaterial +196`  | `cb3[12].y`   |
| `_GlobalMaskTexture`    | 纹理4、sampler4          | `t4 / s4`     |

因此，虽然某些材质保存了同名投影属性，这份消费程序的投影和 Z 范围实际列在 `$Globals`，裁剪容差列在 `UnityPerMaterial`。这与[11](11-mask-target-and-camera-overrides.md)的 `MaskingManager.Update → SetGlobalTexture/Vector/Float` 发布链形成静态连接；不能只看材质保存值就把全局参数解释为每个材质各自的值。

vertex2 的输入签名将 `v5` 标为 `COLOR0`；指令154（`0x140C`）将其复制到 `o4`，fragment18 接到 `v4`。vertex2 指令130先把动画偏移叠到本地位置，131–134（`0x1128..1198`）再经 `unity_ObjectToWorld` 转换，143（`0x12D8`）把结果送 `o6.xyz`，对应片元的 `v6.xyz`。所以比较使用的是**经过该 vertex 动画后的世界坐标**，而不是未变形资源顶点；颜色 alpha 也参与遮罩判断，其 mesh 写端和运行值尚未追到。

fragment18 的指令0–14（`0x15C..328`）可写成下列行为式，属于对实际指令的演算说明：

```text
uv = animatedWorldXY * globalTiling + globalOffset
m = sampleBias(globalMask, uv, globalMipBias).r
z = (animatedWorldZ - minZ) / (maxZ - minZ)
b = abs(m - z) >= materialDepthCutoff ? 1 : 0
a = b + vertexColorAlpha + 1 - sign(m)
```

这里对 `z` 没有显式 saturate；[12](12-mask-camera-filter-and-shader-data.md)的生产 shader 对写出的灰度有 saturate，不能将两者混为一处。黑色背景 `m=0` 和正灰度 `m>0` 的附加项不同。若仅作构造演算，取 vertexColorAlpha=0、m=0.5、z=0.5、cutoff=0.01，得到 `b=0,a=0`；把 z 换为0.6则 `b=1,a=1`。这是数学例子，未证明实际 mesh 的 alpha 恒为0。

Alpha Test 变体随后用导数、0.9 门和 `_AlphaToMaskAvailable` 形成硬裁剪或导数平滑的 alpha；fragment18 的指令30（`0x4F4`）执行 `discard_nz`。`_AlphaToMaskAvailable=0` 时上述 a=0/1 的构造例分别被裁掉/保留；另一分支同时影响输出 alpha，不能概括成单一固定阈值。透明变体17将同一类遮罩比较放在指令388–402（`0x32FC..34C8`），最终 `add_sat o0.w`，没有 discard。其输出透明度还受 pass 混合状态影响，本篇不把一个 alpha 值直接等同于屏幕可见程度。

## 局部更新与性能含义的边界

已经连通的静态链是：层8 Mask Renderer → 遮罩相机/2048² MaskingMap → 世界 Z 灰度 → 全局纹理与投影发布 → Shader622 的选定变体 → 颜色 alpha 或片元裁剪。当前链通过辅助纹理影响表面显示，**没有在这些消费指令中重建墙面网格**。这仍不能证明整个游戏在编辑时没有其他网格更新。

8 个带遮罩的前向变体各有一条对应的遮罩纹理采样。Alpha Test 的裁剪位于大量材质/光照计算之前，透明变体则在程序后部计算 alpha，说明二者具有不同的静态成本路径；实际纹理带宽、提前深度、overdraw、分支和帧时均未测量。不能把程序指令数或资源计数换算成 FPS，也不能由每帧 SetGlobal 调用推断遮罩相机一定每帧完整重绘。

## 复算、验证与剩余断点

原始记录在 ignored `.cache/procedural-modeling/static-owner-followup/summerhouse/material-consumers/`：`material-inputs.json` 包含完整范围、逐变体参数和引用，另有12份 fragment、2份 vertex 反汇编。正式目录不保存目标资产或恢复 shader 源码。复算必须给一个尚不存在的输出目录：

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/material_shader_inputs_probe.py --game-data "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data" --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --output .cache/procedural-modeling/static-owner-followup/summerhouse/material-consumers-recheck
```

读取器校验版本、对象完整消费、LZ4长度、记录范围、参数配对、DXBC chunk 范围和输出不覆盖。原 Mask 工具只抽出共享的记录/DXBC读取函数；重跑后的旧 `mask-route.json` 和两份反汇编与历史证据相同。参数截断、非法资源 tag、记录尾部残留、错误版本和已有输出均以显式失败处理，定点结果见本轮 `focused-validation.json`。

**Answered（静态）：** Shader622 的完整名字、逐变体参数与代码身份、8/12 的遮罩绑定、投影/Z/容差的缓冲对应、动画世界坐标/颜色传递、alpha 与裁剪位置。**Partial：** 其余 Shader 的逐变体覆盖、其他材质外部引用、实际关键词选择、mesh 颜色写端、全局值后续覆盖、遮罩相机更新频率。**Not Run：** 游戏/原生或GPU程序执行、截图、真实像素、帧时、私人存档。
