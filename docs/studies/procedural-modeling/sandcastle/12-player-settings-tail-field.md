# 沙堡：PlayerSettings 末尾四字节的归属与字段歧义

[11](11-color-space-configuration.md) 的精确版本 Release 类型树把本作 `PlayerSettings.m_ActiveColorSpace` 解到对象 `+0xf8=1`，但仅解释 916 字节对象中的前 912 字节。本篇专门挑战末尾 `03 00 00 00` 的来源。**静态确定的是它属于 class 129 的对象载荷；尚不能给它唯一的成员名。** 公开项目配置中 `allowedHttpConnections: 3` 使它是一个有根据的候选，但本作自己的零值槽及类型树差异尚未消歧，不能把候选写成事实。此前色彩空间配置 `Linear=1` 的字段定位不受这段尾部歧义影响。

## 从对象表到最后两个四字节

原安装 `Sandcastle_Data/globalgamemanagers` 是 Unity `6000.4.10f1` 的 SerializedFile v22，内部 type tree 被剥离。对象表明确给出 `pathID=1`、class `129` 的 `PlayerSettings` 从文件 `0x4c0` 起、长 916 字节，所以其半开区间为 `[0x4c0,0x854)`。下一个 class `13` 对象从 `0x860` 起；两者之间另有 12 个零字节。由此，文件 `0x850–0x853` 的 `03 00 00 00` **位于 PlayerSettings 内**，不是相邻对象、AssetBundle 外壳或对象间填充。

同版本 [AssetRipper/TypeTreeDumps 固定提交 `20ba06e…` 的 ReleaseRootNode](https://github.com/AssetRipper/TypeTreeDumps/blob/20ba06e00e0625de0e49a502c6868d6cc86d0f0b/InfoJson/6000.4.10f1.json) 从对象开头依次读到最后字段，尾段计算为：

| Release 节点                         | 对象相对起点 | 树中大小/对齐                       | 本地读取              |
| ------------------------------------ | -----------: | ----------------------------------- | --------------------- |
| `insecureHttpOption`                 |     `+0x368` | int32 / 无额外对齐                  | `0`                   |
| `androidVulkanDenyFilterList`        |     `+0x36c` | 数组计数，零元素                    | `0`                   |
| `androidVulkanAllowFilterList`       |     `+0x370` | 数组计数，零元素；`MetaFlag=0xc000` | `0`                   |
| `androidVulkanDeviceFilterListAsset` |     `+0x374` | PPtr 12 字节                        | 全零                  |
| `d3d12DeviceFilterListAsset`         |     `+0x380` | PPtr 12 字节；`MetaFlag=0x4000`     | 全零，结束于 `+0x38c` |
| `allowedHttpConnections`             |     `+0x38c` | int32                               | `0`                   |
| **Release 树无节点**                 | **`+0x390`** | **仍有四字节**                      | **`03 00 00 00`**     |

这里 PPtr 的 12 字节已经从 `+0x380` 结束于 `+0x38c`，结束位置本来就是四字节对齐；`0x4000` 的对齐标志**不会**再产生四字节 padding。对象起点 `0x4c0` 也已 16 字节对齐，而对象末尾 `0x854` 后才有通往下一个对象 `0x860` 的 12 字节零填充。把 `+0x390` 的值当对象对齐同样与对象表冲突。构造演算：`0x4c0 + 0x380 + 12 = 0x84c`，即 `+0x38c`；再读树的末字段四字节到 `0x850`，仍距对象终点 `0x854` 四字节。

**专门核查八字节对齐候选**：Android PPtr 起于 `+0x374`，其 `m_FileID` 后的 `m_PathID` 在 `+0x378`，碰巧八字节对齐；D3D12 PPtr 起于 `+0x380`，按 4+8 子字段布局其 `m_PathID` 在 `+0x384`，未八字节对齐。若凭空在这里补四字节，D3D12 才会结束于 `+0x390`，并把末尾三值排作 `allowedHttpConnections`，算术上确实吻合 **916 字节**。但精确参考树的 D3D12 PPtr 是 `ByteSize=12`，其 `m_FileID/m_PathID` 的 `MetaFlag` 都是 `0x800001`，不带 `0x4000` 对齐位；外层 PPtr 的 `0x4000` 仅在节点结束后做四字节对齐。更强的同对象反例是 `defaultCursor`：它从 `+0x48` 开始，`m_FileID=1` 后的 `m_PathID` 从**未八字节对齐**的 `+0x4c` 立即写入 `6`，随后 `cursorHotspot` 从 `+0x54` 开始，后续颜色值也正常。若有通用的 pathID 八字节对齐，`+0x4c` 会是四字节 padding，却实际非零。因此不能拿这个算式建立通用格式规则；D3D12 独有的特殊 padding 仍需独立证据，本轮未找到。

## 类型树与读取器的交叉反证

固定参考的 `PlayerSettings` Release 树有 174 个顶层节点、Editor 树有 659 个；两树最后 19 个节点的名字、类型、大小及对齐标志相同，均以 `allowedHttpConnections` 结束。将 Editor 树强套本作对象会在开头就把 `AndroidProfiler` 读成无效布尔值 `4`，故不能用 Editor 树补这四字节。Release 树的 `m_StackTraceTypes` 在 `+0x12c` 读到六个元素；其后的 `cloudProjectId`、四个质量档名称、`projectName=Sandcastle` 和 `organizationId=fweibel` 都能按边界解出。早期数组长度整体偏移四字节而碰巧保持这些远端字符串和末端字段对齐，缺乏证据。

为排除 SerializedFile 通用尾规则或读取器的通用对齐错误，用同一份精确版本 Release schema 与同一 `ObjectReader` 读取三个相邻类别：

| 对象类别                    | 对象表长度 | 类型树消费 |  差额 |
| --------------------------- | ---------: | ---------: | ----: |
| `QualitySettings` class 47  |        824 |        824 |     0 |
| `GraphicsSettings` class 30 |        748 |        748 |     0 |
| `InputManager` class 13     |       2580 |       2580 |     0 |
| `PlayerSettings` class 129  |        916 |        912 | **4** |

本作 `UnityPlayer.dll` 的 `ProductVersion` 为 `6000.4.10f1 (feeafc12a938)`；其静态字符串区含 `allowedHttpConnections`（文件 `0x1eb1610`）和相邻两种设备过滤资产字段名。字符串存在只说明运行库知道该字段名，无法给本作字节定位。精确版本号相同也不等于外部导出的类型树与此 Windows player build 的 class 129 布局逐字节相同；原资源 type tree 已剥离，不能直接对比它的节点列表或确认额外平台成员。

## 原生字段注册路径的最后一项

继续对 `UnityPlayer.dll` 做了只读 PE 定点扫描：三种末端字段名以及 `m_ActiveColorSpace`、`qualitySettingsNames` 各仅有一处可解析到其字符串 RVA 的 `.text` 四字节 RIP 位移候选。总共检查 29,935,101 个可执行段四字节窗口；没有在 PE 中找到这几处字符串的绝对指针或直接 RVA 常量。用本机 `dumpbin` 复核后，它们都是实际 `lea rdx,[rip+disp32]` 指令，而不是偶然相等的四字节数据；五处均落在 `.pdata` 所界定的**同一函数** `0x180e637d0–0x180e652aa`。这把尾部字符串连接到本地原生字段处理路径，而非只凭字符串出现推测。

该函数开头 `0x180e63801` 将根节点版本设为 `0x1c=28`，与参考 `PlayerSettings.ReleaseRootNode.Version=28` 相合；中段还处理 `m_ActiveColorSpace` 与 `qualitySettingsNames`。末段调用顺序为：`0x180e651e3` 取 `androidVulkanDeviceFilterListAsset` 名，`0x180e6521c` 取 `d3d12DeviceFilterListAsset` 名，`0x180e65247` 从内存对象 `[rsi+0x2c0]` 取一 `int32`，`0x180e6525b` 取 `allowedHttpConnections` 名并在 `0x180e6527e` 登记四字节大小，`0x180e652a9` 返回。两次设备过滤资产字段都调用同一个 `0x180094440` 辅助函数；其有界反汇编登记 `m_FileID` 为 4 字节、`m_PathID` 为 8 字节，支持 **12 字节 PPtr**，没有给本作额外四字节 PPtr 布局提供证据。`rsi+0x2c0/+0x2f8/+0x4f0` 是原生**内存对象**偏移，不能充当 SerializedFile 中的 `+0x38c/+0x390` 偏移。

这段代码的字段名、顺序及节点大小与公开 Release 树末项相符，且在 `allowedHttpConnections` 后无其他具名字段调用。共用的 `0x18120f4f0` 辅助函数还操作字段节点表及其 flag，支持把这段视为**player 运行库的字段注册/类型树处理证据**，不是已证明的文件写入调用。本轮没有执行该函数，也没有恢复 `globalgamemanagers` 的构建时写入逻辑。它不能反推目标对象末尾的三值一定来自这个末字段，更不能把对象表里确实存在的额外四字节消掉。

## 两种仍相容的映射

| 映射                             | `+0x38c` 的零值              | `+0x390` 的三值                   | 尚缺证据                                 |
| -------------------------------- | ---------------------------- | --------------------------------- | ---------------------------------------- |
| **A：照公开 Release 树**         | `allowedHttpConnections=0`   | 另一个未在树中出现的 int32/尾载荷 | 末尾成员名、为什么公开树没有它           |
| **B：player build 多一零值字段** | 未在公开树中出现的四字节字段 | `allowedHttpConnections=3`        | 额外字段名和它在最后几项中的准确插入位置 |

[Unity 官方维护的公开示例项目配置](https://github.com/Unity-Technologies/arfoundation-samples/blob/main/ProjectSettings/ProjectSettings.asset) 也把 `allowedHttpConnections: 3` 写在设备过滤资产字段之后；它支持映射 B 的**合理性**，却不是本作的序列化记录，不能凭值相等把 `+0x390` 直接命名。映射 B 需要构建该资源时的 writer 比当前 player 注册路径多写一个四字节零槽；其确切字段仍未找到。原生 PPtr 辅助函数与参考树均支持 12 字节，因此“PPtr 自身多四字节”的解释缺少支持，不作为优先结论。

最后一个可证的生产边界是 Unity build 写入 `globalgamemanagers` 的 class 129 对象载荷；**构建时哪一个成员产生了 `+0x38c/+0x390` 组合仍未恢复**。现在已恢复 player 运行库的末端字段注册顺序，却仍缺实际构建 writer 或未剥离的 class 129 **资源内**类型树；其一才能判定当前资源是否带有 player 注册路径会忽略的尾字段、或某个零槽在 writer 侧插于 `allowedHttpConnections` 前。不要把运行库中的内存对象偏移和目标 SerializedFile 偏移混为一谈。

## 证据与修订建议

定点原始结果在 `.cache/procedural-modeling/static-tail-followup/sandcastle/`：`tail-audit.json` 列出对象边界、尾段字段偏移/flag、其他三类完整消费对照和 Editor 树失败；`pptr-alignment-check.json` 保存八字节对齐假设及同对象反例；`unity-player-field-xrefs-final.json` 保存 PE 字符串 VA/RVA、候选扫描和引用位置；`UnityPlayer-tail-xrefs-disasm.txt`、`UnityPlayer-tail-function-end.txt`、`UnityPlayer-PPtr-helper-94440.txt`、`UnityPlayer-field-helper-120F4F0.txt` 保存原始定点反汇编；`native-xref-summary.json` 汇集 `.pdata` 方法范围与关键指令。读取工具为 [`unity_player_xref_probe.py`](tools/unity_player_xref_probe.py)，需显式指定 `--binary` 与未存在的 `--output`，拒绝覆盖。资源与参考的来源见 [11](11-color-space-configuration.md)。建议后续修订原读取器时继续返回 `schema_status=Partial`、`schema_consumed_bytes=912`、对象总长 916 和原样四字节；**不要**自动把末尾 `3` 绑定到 `allowedHttpConnections`、作为 padding 忽略，或把只因字节总数读尽而称为 schema 完全匹配。[11](11-color-space-configuration.md) 的配置值结论可保留，同时从本篇链接到尾部原因核查。

**Not Run**：游戏、Unity runtime、原生序列化函数执行和玩家存档。没有安装工具、修改游戏或计算公开参考摘要。
