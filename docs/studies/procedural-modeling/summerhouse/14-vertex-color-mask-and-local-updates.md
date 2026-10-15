# SUMMERHOUSE：顶点色 alpha 如何进入遮罩裁剪

**结论（静态）：** 一个实际打包墙块把 `Maskable` 挂在根对象，把带 COLOR0 的网格和 Shader622 材质挂在子对象。该网格保存的 412 个顶点 alpha 字节全为 255；`Maskable.Awake` 的 CIL 在实例初始化时逐顶点把 alpha 写成 0。已在[13](13-global-mask-material-consumers.md)验证的 Shader622 Alpha Test 变体把这个 alpha 加入全局遮罩比较结果，故包内颜色初值不能直接代入运行中片元公式。这是资源加 CIL 的静态连接，没有观察游戏实例、实际帧或像素。

## 身份、覆盖与写入端

沿用[00](00-evidence-and-scope.md)和[13](13-global-mask-material-consumers.md)的 SUMMERHOUSE 1.2.12 安装及程序集身份，不重算摘要，也不执行目标。新原始记录在 ignored `.cache/procedural-modeling/static-final-followup/summerhouse/`。正式[网格颜色读取器](tools/mesh_color_probe.py)用实际 `sharedassets0.assets` 对象索引和固定的 Unity 2023.2.22f1 Release 类型树完整消费选定 Mesh，检查顶点通道、数据长度和颜色字节；本篇只用 Mesh427、614 的定点读取，不把它们推广到所有网格。格式值 `2=UNorm8` 由同版打包的 `UnityEngine.CoreModule.dll` 内 `UnityEngine.Rendering.VertexAttributeFormat` 枚举字段核对，原始元数据在 `vertex-format-enum.json`。

离线 CIL 定点扫描覆盖 `Assembly-CSharp.dll` 全部 173 个 TypeDef、1006 个 MethodDef：直接调用 `UnityEngine.Mesh::set_colors` 的方法只有 `Maskable.Awake` (`0x060001B1`) 与 `SetVertexColors.Start` (`0x06000262`)；直接调用 `Mesh::SetColors`、`Mesh::set_colors32` 均为 0。这个否定范围限于当前程序集的直接已解析操作数，不排除其它程序集、Unity 原生侧、反射或后续版本。

`Maskable.Awake IL_0000..00A7` 的分支很明确：

1. 对自身子层级的 MeshFilter 逐个读取 `MeshFilter.mesh` 与 `Mesh.colors`。
2. 若颜色数组为空，按该 Mesh 的 `vertexCount` 创建数组，逐项填 `(0,0,0,0)` (`IL_001E..005F`)。
3. 无论新建还是已有数组，逐项把 `Color.a` 设为 `0` (`IL_0066..0091`)，然后调用 `Mesh.set_colors` (`IL_0093..0095`)。

因此它保留已有颜色的 RGB，但重写 alpha；为空时也补齐零 RGB。该方法没有 `Update` 或再次执行入口，不能把它说成逐帧网格重算。[06](06-local-updates-and-render-costs.md)已区分 `MeshFilter.mesh` 的实例网格语义；这里写入的是该 getter 返回的 Mesh，不应由代码直接推断它修改所有引用同一资源的对象。

子层级范围还有一个明确过滤条件：Awake在 `IL_0001` 调无参泛型 `Component.GetComponentsInChildren`，本作 CoreModule 的该包装器 `0x06001ED6 / IL_0002..0003` 传入 `includeInactive=false` 再调用布尔重载。新 `component-children-overloads.json` 保留六个重载及实参；不能将其写成无条件遍历全部inactive子树，具体返回集合仍受层级激活状态约束。

`SetVertexColors.Start IL_0020..0099` 在已有颜色数组非空时，依据 `channelTarget` 的三个分支只写 `Color.r/g/b` 之一，最后 `set_colors`；它没有写 alpha。资源索引在 `sharedassets0.assets` 识别到 49 个 `Maskable` 和 30 个 `SetVertexColors` 组件：49 个 `Maskable` 均与一个 `BuildingBlock` 组件同挂根 GameObject；30 个 `SetVertexColors` 与这些根对象没有同一 GameObject。这个同对象计数不证明其它层级或资源文件没有间接关系，也不证明全部 prefab 实际在场。

## 一条具体的资源到 Shader 链

下面的 pathID 均指 `sharedassets0.assets`。`GameObject`、`Transform`、`MeshFilter`、`MeshRenderer` 和 Material 引用按当前对象表读取；根与模型之间还有 `Cursor Pivot` Transform 层。

| 层级或数据                  | 实际引用及配置                                                                                                                                                   |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 根 `Wall Parapet Arched 01` | GameObject2440，`m_IsActive=1`；含 BuildingBlock7397、Maskable6782，后者序列化 `m_Enabled=1`                                                                     |
| 子 `Model 01`               | GameObject1460，层6、`m_IsActive=1`；MeshFilter5483 指向本文件 Mesh427；MeshRenderer4873                                                                         |
| 可见材质                    | Renderer4873 三个槽分别是 Material85、82、92；三者均引用本文件 Shader622 且保存 `_ALPHATEST_ON`                                                                  |
| 网格 COLOR0                 | Mesh427，文件偏移1127432、长23912 B；`m_VertexCount=412`，顶点流21424 B = 412×52 B；第四通道（COLOR0）为 stream0、offset40、UNorm8×4；412 个 alpha 字节全部是255 |

这给出**实际资源初值**：该网格若未经写入，COLOR0 的归一化 alpha 对应 1。`Maskable.Awake` 对此子 MeshFilter 的静态可达路径会把实例的 alpha 改为 0。另一个同样挂在 `Maskable` 块上的 Mesh614（`Wall Base 01`）有 44 个顶点，保存 alpha 也全为255；这只是第二个定点核对，未声称所有网格初值相同。根对象和材质的存在、启用字段不能代替实际实例化与生命周期观察。

[13](13-global-mask-material-consumers.md)已从 Shader622 的 vertex2 输入签名确认 `v5=COLOR0`，复制到片元 `v4`；其 fragment18（`_ALPHATEST_ON`）的遮罩前段可表示为：

```text
b = abs(sample(GlobalMask).r - normalizedAnimatedWorldZ) >= materialDepthCutoff ? 1 : 0
a = b + vertexColorAlpha + 1 - sign(sample(GlobalMask).r)
```

片元后续还有导数、`_AlphaToMaskAvailable` 和裁剪处理，不能把 `a` 直接当屏幕透明度。以构造数值 `mask=0.5`、`normalizedAnimatedWorldZ=0.5`、`cutoff=0.01` 为例，`b=0`；若直接代入包内 alpha=1，得到 `a=1`，而在这个 `Maskable.Awake` 路径写成 alpha=0 后得到 `a=0`。这说明写端会改变裁剪输入，不是已观测帧的裁剪结果。Shader622 的四个 Alpha Test 前向变体均有遮罩纹理绑定；材质关键词只建立可用路径，当前帧选择与最终 GPU 输出仍未知。

## 更新、失效和成本的可证边界

| 条件                                    | 静态可见动作                                                                                                                                                  | 边界                                                                                   |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 活跃的带 `Maskable` prefab 实例初始化   | `Awake` 遍历该组件子 MeshFilter，并将各自颜色 alpha 写 0；若原数组为空，先按顶点数补齐                                                                        | 范围是该实例的子层级；一次遍历成本随实际子 MeshFilter 顶点数求和。没有由此证明每帧调用 |
| 带 `SetVertexColors` 的对象执行 `Start` | 对已有颜色数组按选定通道写 R/G/B                                                                                                                              | 不写 alpha；数组为空时跳过。其真实执行对象与先后关系需要场景/运行证据                  |
| 放置或组合替换                          | [06](06-local-updates-and-render-costs.md)的 CIL 会实例化单个预制块或奖励块、更新放置列表；新实例若符合上面的启用条件，进入自己的生命周期                     | 本次路径没有整栋建筑 Mesh 重建。组合匹配仍可能线性扫描列表，不能称全部更新为常数成本   |
| `MaskingManager.Update`                 | [11](11-mask-target-and-camera-overrides.md)每次发布全局遮罩纹理引用、投影与 Z 范围；[12](12-mask-camera-filter-and-shader-data.md)的遮罩相机读取层8 Renderer | 这些全局参数更新不改 Mesh.colors；遮罩相机何时、是否完整重绘及真实像素仍未知           |
| 画刷命中一个块                          | [06](06-local-updates-and-render-costs.md)所读 `PaintBlock` 改该块子 Renderer 的 `sharedMaterials` 槽                                                         | 不在已读代码中改 COLOR0；换材质可改变消费路径，具体新材质关键词需按实际映射核对        |

这条链把局部的**网格属性初始化**和共享的**遮罩纹理消费**分开：前者在单实例生命周期中改顶点 alpha，后者在材质片元程序中读取 alpha 与全局遮罩。它不建立遮罩相机的重绘频率、所有 prefab 的 alpha 分布、任何实际帧的 variant 选择或帧时/FPS。

## 复算与验证状态

`mesh-color-writers.json`、`maskable-all.json`、`setcolors.json`、`colors32.json`、`vertex-format-enum.json` 是离线 CIL/元数据投影；`mesh427-colors.json`、`mesh614-colors.json` 是完整资源读取结果。重做选定 Mesh 时给读取器一个不存在的输出文件：

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/mesh_color_probe.py --game-data "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data" --index .cache/procedural-modeling/summerhouse/resources/sharedassets0.assets.json --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --mesh 427 --output .cache/procedural-modeling/static-final-followup/summerhouse/mesh427-recheck.json
```

读取器拒绝目标索引/文件或版本不一致、非 Mesh、对象未完整消费、颜色通道布局不符、顶点字节长度不符及覆盖已有结果；不运行游戏或 shader。**Answered（静态）：** 一个实际 Maskable 块的包内 COLOR0 初值、Awake 写 alpha、Shader622 Alpha Test 消费、直接写端的有界全集和局部调用条件。**Partial：** 其余 mesh/文件颜色分布、其它写入渠道和场景实例化。**Not Run：** 游戏、相机/GPU 绘制、真实像素、运行成本和私人存档。
