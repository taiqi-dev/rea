# 沙堡：项目色彩空间配置与实际生效值

末尾四字节的对象边界、类型树反证和候选映射续查见[12](12-player-settings-tail-field.md)；字段名仍保持未唯一确定，不改本篇 Partial 状态。

本篇收束 [10](10-camera-color-format-selection.md) 留下的 `QualitySettings.activeColorSpace` 分支输入。对同一 Sandcastle Demo 安装版的 `globalgamemanagers`、IL2CPP metadata v39、`GameAssembly.dll` 与 `UnityPlayer.dll` 做静态只读检查；制品身份沿用 [01](01-artifact-and-method-map.md)，没有新算摘要或启动游戏。**已解出本作打包的 PlayerSettings 色彩空间配置为 `Linear=1`**；相机颜色格式决策仍读取 Unity 原生接口返回的**实际**色彩空间，不能仅凭配置断言运行时分支。完整 schema 消费还剩一个未映射的末尾四字节，下面保留 Partial 边界。

## 精确版本 Release 类型树定位配置值

`Sandcastle_Data/globalgamemanagers` 是 Unity `6000.4.10f1`、SerializedFile v22，共 19 个对象且 `type_trees=false`。class `129`、`pathID=1` 的对象在文件 `0x4c0`，长 916 字节；其相对 `+0x28` 和 `+0x3c` 的长度前缀字符串分别为 `BubblebirdStudio`、`Sandcastle`，可以核对它是本作的 `PlayerSettings` 对象。class `47`、`pathID=12` 的 `QualitySettings` 对象在 `0x17730`，长 824 字节。对象边界和身份来自本地资源记录，而非对字段位置的猜测。

资源本身不含 type tree，因此本轮使用公开 [AssetRipper/TypeTreeDumps 固定提交中的 `InfoJson/6000.4.10f1.json`](https://github.com/AssetRipper/TypeTreeDumps/blob/20ba06e00e0625de0e49a502c6868d6cc86d0f0b/InfoJson/6000.4.10f1.json) 作**布局参考**：其 `Version=6000.4.10f1` 与资源一致，`Classes` 中 `Name=PlayerSettings`、`TypeID=129` 唯一，取 `ReleaseRootNode` 的 174 个顶层字段，未用 `EditorRootNode`。该树把 `m_ActiveColorSpace` 标为紧随 `m_StereoRenderingPath` 后的四字节 `int`。按字段顺序、变长字符串/数组长度与 `0x4000` 对齐标志逐项读取，本作对象内该字段位于相对 `+0xf8`，即文件 `0x5b8`，小端 `01 00 00 00` → **`Linear=1`**（枚举值见 [10](10-camera-color-format-selection.md)）。

| Release 字段                                                                               |                  对象相对偏移 |                            读取值 |
| ------------------------------------------------------------------------------------------ | ----------------------------: | --------------------------------: |
| `companyName` / `productName`                                                              |             `+0x24` / `+0x38` | `BubblebirdStudio` / `Sandcastle` |
| `defaultScreenWidth` / `defaultScreenHeight`                                               |             `+0xe4` / `+0xe8` |                    `1024` / `768` |
| `defaultScreenWidthWeb` / `defaultScreenHeightWeb`                                         |             `+0xec` / `+0xf0` |                     `960` / `600` |
| `m_StereoRenderingPath` / `m_ActiveColorSpace`                                             |             `+0xf4` / `+0xf8` |                     `0` / **`1`** |
| `unsupportedMSAAFallback` / `m_SpriteBatchMaxVertexCount` / `m_SpriteBatchVertexThreshold` | `+0xfc` / `+0x100` / `+0x104` |             `0` / `65535` / `300` |

两处身份字符串的**字段起点**分别是 `+0x24/+0x38`，其 UTF-8 字节从四字节长度之后的 `+0x28/+0x3c` 开始，与原先的独立字节定位一致。读取器还越过数组和 PPtr，复核靠近对象尾部的 `qualitySettingsNames=[Low, Medium, High, Ultra]`、`projectName=Sandcastle`、`organizationId=fweibel`。这些独立邻接锚点支持前段 `+0xf8` 的字段定位，结论不是从众多 `0/1` 字节中挑一个。

**布局限制**：Release 树解析到相对 `+0x390`，共 912 字节；对象实际 916 字节，末尾 `+0x390–+0x393`（文件 `0x850–0x853`）为 `03 00 00 00`。类型树最后的 `allowedHttpConnections` 已按树读于 `+0x38c`，值为 0。不能把末尾的 3 随意归给它或当作 padding；确切含义未解。读取器显式输出 `schema_status=Partial`、912/916 和未映射尾部，不宣称全对象 schema 匹配。这个末尾差异不改变已由前后字段及远端字符串交叉校验的 `+0xf8` 读数。

## 运行时读取链

[10](10-camera-color-format-selection.md) 已把 `SetupColorDepthTarget` 的 `0x180471b88` 和 `CopyOpaqueDepth` 的相应调用映射至 `QualitySettings.get_activeColorSpace`。本轮进一步核对 `UnityEngine.CoreModule.dll` metadata token `0x6000457` 对应的 IL2CPP 方法体 `0x181c16200–0x181c1622a`：

```text
0x181c16204  读取缓存的原生函数指针 [0x182af0f78]
0x181c16210  缓存为空时传入 0x1820e2040 的 internal-call 名称
0x181c16217  调 0x18036dd00 解析，随后缓存结果
0x181c16227  跳转至解析所得的原生函数
```

`0x1820e2040` 落在 `GameAssembly.dll` 的 `.rdata`，文件偏移 `0x20e1440`，字面字符串为 `UnityEngine.QualitySettings::get_activeColorSpace()`。这是本作调用 Unity 原生运行时查询的直接证据；IL2CPP 外壳没有内联固定的 Gamma/Linear 值。静态文件也没有给出这个原生函数在运行时解析到的函数指针或其返回值。

Unity 对同一 API 的说明区分了项目请求与实际结果：[PlayerSettings.colorSpace](https://docs.unity.cn/6000.0/Documentation/ScriptReference/PlayerSettings-colorSpace.html) 是项目设置，[QualitySettings.desiredColorSpace](https://docs.unity3d.com/cn/6000.0/ScriptReference/QualitySettings-desiredColorSpace.html) 反映请求值，而 [QualitySettings.activeColorSpace](https://docs.unity3d.com/kr/6000.0/ScriptReference/QualitySettings-activeColorSpace.html) 还取决于硬件支持。这里引用的是 Unity 6000.0 公开 API 语义，不把网页当作本作 `6000.4.10f1` 序列化字段的偏移表。本轮 `m_ActiveColorSpace=1` 证明打包的**项目配置**为 Linear；本作两处格式分支查询的是**实际生效值**，该值仍未通过静态安装包得到。

## 对颜色目标的可构造影响

沿用 [10](10-camera-color-format-selection.md) 的 `F_HDR = SystemInfo.GetGraphicsFormat(DefaultFormat.HDR)`：

| 运行时实际 `activeColorSpace` | 两处颜色 descriptor 的转换调用                       |
| ----------------------------- | ---------------------------------------------------- |
| `Linear=1`                    | `set_sRGB(true)`，最终调用 `GetSRGBFormat(F_HDR)`    |
| `Gamma=0`                     | `set_sRGB(false)`，最终调用 `GetLinearFormat(F_HDR)` |

本作的配置确为 Linear。**仅作为假设演算**，若某目标硬件使实际值退到 Gamma，则本作调用链会走 `GetLinearFormat(F_HDR)`，不能凭打包配置推断一定走 sRGB 分支。转换函数对给定 `F_HDR` 是否返回另一具体枚举值还需知道 Unity 原生 `SystemInfo.GetGraphicsFormat` 的运行结果。硬件回退的设定不是对本作当前机器画面的观测。

## 证据边界与复现

本轮原始记录在 `.cache/procedural-modeling/static-resource-followup/sandcastle/`：`player-settings-release-validated.json` 保存 174 字段布局读取结果、邻接字段、数组数目与末尾差异；`resource-preflight.json` 是取得精确版本 schema **之前**的资源索引，里面的 `color_space_field_offset: null` 是历史预检状态，已由本篇新证据更新；`QualitySettingsGetActiveColorSpace.txt` 保存 `dumpbin` 的有界函数反汇编；`icall-string.json` 保存 PE `.rdata` 内该名称的 VA→RVA→文件偏移演算。精确版本布局缓存于 `.cache/procedural-modeling/static-resource-followup/reference/6000.4.10f1-InfoJson.json`；正式 [`player_color_space_probe.py`](tools/player_color_space_probe.py) 需显式指定资源、schema 和新的输出路径，拒绝覆盖，遇到截断或版本不符失败。资源索引沿用共享 [`unity22-compute-probe.py`](../tools/unity22-compute-probe.py) 的 `resource_index`，metadata/token 和旧方法映射沿用 [10](10-camera-color-format-selection.md) 所列同版本缓存。

复跑时在仓库根执行 `python docs/studies/procedural-modeling/sandcastle/tools/player_color_space_probe.py --resource "C:\Software\Steam\steamapps\common\Sandcastle Demo\Sandcastle_Data\globalgamemanagers" --schema .cache/procedural-modeling/static-resource-followup/reference/6000.4.10f1-InfoJson.json --output <新的缓存 JSON 路径>`。定点负例已证实：截断四字节字段时报 `Object truncated`、换成 `2023.2.22f1` 类型树时报版本不符、输出路径已存在时拒绝覆盖；没有用失败结果写入正式证据。

**仍未知**：对象末尾 4 字节的语义、Unity 原生 `QualitySettings.activeColorSpace` 在当前设备返回的值、`F_HDR` 的具体 `GraphicsFormat`、颜色目标的最终位深与呈现效果。要证明实际值需另有授权范围内的运行时查询或抓帧；本轮只做静态分析。

**Not Run**：游戏、Unity 原生色彩空间查询、GPU 抓帧、任何运行时显示/性能验证。没有复制游戏资源或恢复代码到正式文档。
