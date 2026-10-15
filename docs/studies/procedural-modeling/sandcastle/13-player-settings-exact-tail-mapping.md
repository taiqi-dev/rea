# 沙堡：PlayerSettings 尾槽能定位到哪一步

[12](12-player-settings-tail-field.md) 已确认本作 `globalgamemanagers` 的 class 129 对象长 916 字节，而精确版本公开 Release 类型树只消费 912 字节。本篇沿本作 `UnityPlayer.dll` 的字段路径追到**相邻的实际二进制读取回调**：在普通读取分支、目标资源两个零长设备列表和三个空 PPtr 的条件下，回调把对象 `+0x38c` 的 `0` 读入内存字段 `+0x2c0`，随后游标结束于 `+0x390`。因此，**安装包内 reader 对 `allowedHttpConnections` 的静态绑定是 0，`+0x390` 的 3 在该 reader 路径之后尚未消费。** 额外三值的构建时生产成员、是否有更外层尾处理及游戏实际运行时值仍未知；未运行游戏。

## 本地字段路径与 Release 树逐项对齐

输入是原安装 `C:\Software\Steam\steamapps\common\Sandcastle Demo\UnityPlayer.dll`、`Sandcastle_Data/globalgamemanagers`，以及固定提交 `20ba06e00e0625de0e49a502c6868d6cc86d0f0b` 的 [Unity `6000.4.10f1` Release 类型树](https://github.com/AssetRipper/TypeTreeDumps/blob/20ba06e00e0625de0e49a502c6868d6cc86d0f0b/InfoJson/6000.4.10f1.json)。[12](12-player-settings-tail-field.md) 的 `.pdata` 范围与字符串 RIP 引用已限定一个本地函数；本轮把整个 `0x180e637d0–0x180e652aa` 反汇编，不只截末尾几条。工具从 PE 初始化节还原 `lea` 所指的 NUL 结尾 ASCII 字段名，再和 Release `PlayerSettings` 的 174 个顶层节点比对。152 处匹配名称引用按序排列，Release 中另有 22 个没有以本轮所捕捉的 `lea` 形式匹配到的字段：splash screen 一段 18 项、`mobileMTRenderingBaked/AID/playerMinOpenGLESVersion` 三项、`metroInputSource` 一项。**已恢复名称的相对顺序与 Release 一致。**匹配已知名称不是新增字段的穷尽扫描，也不代表 152/174 的注册覆盖率完整；其它辅助函数和编码方式仍可能处理未捕捉项。关键的末 35 项（Release 索引 139–173）则在此函数内全部可捕捉且同序。

下面列出尾部 11 项。`本地节点大小` 仅指代码中能直接看见的 `mov dword ptr [rdx+rcx+0Ch],N`；其它类型通过列出的 helper 处理，不能把空格理解成未序列化。`Release 消费` 来自资源经精确树读取，包括 bool 后的四字节对齐。原生地址是本作 `UnityPlayer.dll` 的 VA；资源偏移从对象 `0x4c0` 起算。

| Release 字段                         | 本地字段名 `lea` VA | 本地处理/大小证据                                                                    | Release flag |      资源相对偏移/消费 |
| ------------------------------------ | ------------------: | ------------------------------------------------------------------------------------ | -----------: | ---------------------: |
| `cloudEnabled`                       |       `0x180e65065` | bool helper `0x180092500`                                                            |          `0` |           `+0x354` / 1 |
| `legacyClampBlendShapeWeights`       |       `0x180e6507e` | bool helper 后 `0x18120f8f0` 对齐调用                                                |     `0x4000` |           `+0x355` / 3 |
| `hmiLoadingImage`                    |       `0x180e650ab` | PPtr helper `0x180094440`，子项 4+8 字节                                             |          `0` |          `+0x358` / 12 |
| `platformRequiresReadableAssets`     |       `0x180e650e4` | 直接登记节点大小 1                                                                   |          `0` |           `+0x364` / 1 |
| `virtualTexturingSupportEnabled`     |       `0x180e65125` | 大小 1，随后对齐调用                                                                 |     `0x4000` |           `+0x365` / 3 |
| `insecureHttpOption`                 |       `0x180e6516e` | 直接登记大小 4                                                                       |          `0` |           `+0x368` / 4 |
| `androidVulkanDenyFilterList`        |       `0x180e651a3` | vector helper `0x180e67a30`                                                          |     `0x8000` |           `+0x36c` / 4 |
| `androidVulkanAllowFilterList`       |       `0x180e651b9` | 同一 vector helper，随后对齐调用                                                     |     `0xc000` |           `+0x370` / 4 |
| `androidVulkanDeviceFilterListAsset` |       `0x180e651e3` | PPtr helper `0x180094440`                                                            |          `0` |          `+0x374` / 12 |
| `d3d12DeviceFilterListAsset`         |       `0x180e6521c` | 同一 PPtr helper，随后对齐调用                                                       |     `0x4000` |          `+0x380` / 12 |
| `allowedHttpConnections`             |       `0x180e6525b` | `0x180e65247` 读内存 `[rsi+0x2c0]`，`0x180e6527e` 登记大小 4；`0x180e652a9` 函数返回 |          `0` | `+0x38c` / 4；读取值 0 |

原生路径里，`legacyClampBlendShapeWeights`、`virtualTexturingSupportEnabled`、允许列表、D3D12 PPtr 等 `Release flag` 带 `0x4000` 的尾项后有 `0x18120f8f0` 对齐处理；末项没有另一个对齐或具名字段调用。两个设备过滤资产 PPtr 都走相同的 `0x180094440`，其子节点为 4 字节 `m_FileID` 加 8 字节 `m_PathID`，无法从本地函数为 D3D12 单独补四字节。这里的 `Release flag` 数值取自公开树，调用顺序是本地二进制证据；尚未把所有 helper 的分支逐项逆向为这些 flag 的等价实现。

`0x180e65247` 的 `[rsi+0x2c0]` 是**运行时内存对象**地址，而表中的 `+0x38c` 是**文件对象**地址；二者并无可直接相加或相等的关系。此函数传入字段名和节点大小，操作节点表，同时读写内存成员。它单独只证明本地运行库认识该字段的顺序与类型。以下另从相邻二进制读取回调及其游标操作建立文件到内存的连接，而不是把类型树函数误称为 reader。

## 相邻回调表接到实际二进制 reader

对字段函数入口 `0x180e637d0` 的 PE 数据指针做精确扫描，在 `.rdata/.data` **没有**它的 64 位绝对指针；文件中相同的 32 位 RVA 仅在 `.pdata` 函数边界记录。扫描 `.text` 的可解析相对位移，唯一指向它的是 `0x180e63517` 的 `call`。该调用者位于 `.pdata` 函数 `0x180e634e0–0x180e6352e`，自己的指针在 `.rdata` VA `0x181eb1ab0`（文件 `0x1eb04b0`）。这个表的连续槽是：`+0x00 → 0x180e634e0`（包装字段路径）、`+0x08 → 0x180e63540`（状态/后处理路径，具体外层职责不作推断）、`+0x10 → 0x180e63530`；第三项是直接跳到 `0x180e652b0` 的 thunk，而非先执行别的尾读指令。后者 `.pdata` 范围 `0x180e652b0–0x180e67200`，开头从 `[rdx+38h]` 指向的游标取单字节、写入目标内存，并递增 `[rdx+38h]`，因而是可检查的**二进制读取路径**，不是凭表槽名字臆测。表后仍有共用函数指针；这里只解释经反汇编验证的三个槽，不给整个 vtable 命名。

同一内存成员联接了两条路径：字段路径在 `0x180e65247` 取 `[rsi+0x2c0]` 并用 `allowedHttpConnections` 名登记；二进制路径末尾 `0x180e671a7` 先取 `[rdi+0x2c0]`，在 `0x180e671c2` 从游标处读取 4 字节，`0x180e671c4` 将游标加 4，`0x180e671c9` 把读值写入 `[rdi+0x2c0]`，`0x180e671ff` **直接 `ret`**。两次设备列表在 `0x180e6714d/15c` 调同一 vector reader `0x180e67fc0`；其零元素路径读四字节计数、立即跳过元素循环。两次设备过滤资产 PPtr 在 `0x180e6717f/18e` 调同一 `0x180093fc0`；helper 的上下文 flag 两支均先把游标加 4，再加 8（第二支在 `0x180094218/243`），没有 D3D12 专属的四字节垫片。末项前的 `0x180e67193–a3` 只把游标四字节对齐。尾段读码没有按 SerializedFile 版本或平台分叉；本资源 header 的版本为 Unity `6000.4.10f1`、格式 22，设备列表计数确实为零，PPtr 值全零。上下文 flag 的两条可见、正常界内 PPtr 路径都消耗 12 字节；界外错误处理与更外层对象逻辑不在本结论内。

二进制 reader 在 `0x180e66fd2/e1` 连续调用字符串读取器，目标内存 `+0x60/+0x88` 与字段路径中 `projectName/organizationId` 的内存成员一致。资源中两字符串分别按 Release 树在 `+0x338/+0x348` 解出真实文本，组织名结束于 `+0x354`。从此独立锚点计算尾段普通读取游标：

| reader 处理                                             | 读取前对象偏移 |            消费及对齐 |   读取后 |
| ------------------------------------------------------- | -------------: | --------------------: | -------: |
| 两个 bool、首个 PPtr、再两个 bool、`insecureHttpOption` |       `+0x354` | `4 + 12 + 4 + 4 = 24` | `+0x36c` |
| 两个零长 vector                                         |       `+0x36c` |           `4 + 4 = 8` | `+0x374` |
| Android/D3D12 两个 PPtr                                 |       `+0x374` |        `12 + 12 = 24` | `+0x38c` |
| 写入内存 `+0x2c0` 的末项 int32                          |       `+0x38c` |                   `4` | `+0x390` |

这条序列来自 reader 的实际调用、游标加法和两辅助函数的零元素/12 字节 PPtr 路径；名称对应来自先前字段路径，共同内存偏移 `+0x2c0` 把末项绑定为 `allowedHttpConnections`。本资源的 `+0x38c` 确实是 `00 00 00 00`，`+0x390` 才是 `03 00 00 00`。它回答了**安装包内 reader 会从何处给此内存字段取值**，并且 reader 的本体在 store 后直接返回；不等于证明游戏已经运行该路径、外层 loader 不会继续处理剩余字节，或 Unity build writer 为何多写四字节。

## 文件字节与历史两假说的收敛

同一正式读取器从对象表确认对象区间 `[0x4c0,0x854)`。`organizationId=fweibel` 在 `+0x348`，含长度、UTF-8 内容及对齐共 12 字节，结束 `+0x354`。从此至 `+0x390` 的 **60 字节全零**；`+0x390–+0x393` 是小端 `03 00 00 00`。算式是 `0x4c0 + 0x354 = 0x814`（组织名后的边界），`0x4c0 + 0x38c = 0x84c`（本地 reader 的末项），`0x4c0 + 0x390 = 0x850`（未消费三值），`0x4c0 + 0x394 = 0x854`（对象表终点）。仅凭原始字节，零槽此前可藏在全零区任一点；本轮追加的 reader 游标轨迹才将其对**本地读取语义**消歧。

| [12](12-player-settings-tail-field.md) 的历史候选 | `+0x38c`                     | `+0x390`                                                | 本轮状态                                                                                   |
| ------------------------------------------------- | ---------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| A：公开 Release 树对应本地 reader                 | `allowedHttpConnections=0`   | reader 未消费的四字节尾载荷                             | **已由本地 binary reader 的共同内存成员、helper 消费和游标前移支持**；尾载荷生产者仍未知   |
| B：构建 writer 在末项之前插入零槽                 | 未命名的四字节字段或布局差额 | 若另有 writer 规则，可能是其 `allowedHttpConnections=3` | 作为构建侧假说尚未排除，但**不等于本地 reader 的字段映射**；需构建 writer/资源内类型树验证 |

原资源内 type tree 被剥离，构建 writer 也未定位，因此**额外三值为何在对象中，以及构建侧是否另有成员，仍是最小剩余阻点**。本地 reader 对末项的静态映射已经闭合，但它是否在游戏执行、是否由更外层逻辑处理剩余四字节，以及最终运行时状态均未验证。先前 [11](11-color-space-configuration.md) 的 `m_ActiveColorSpace=1` 位于多组非零边界校验的前段，不受这段末尾差异影响。

## 可复算证据与边界

正式工具 [`player_native_field_sequence_probe.py`](tools/player_native_field_sequence_probe.py) 要求 `--binary`、`--disassembly`、`--schema`、`--resource` 和新 `--output`，会拒绝覆盖。另一正式工具 [`player_callback_table_probe.py`](tools/player_callback_table_probe.py) 扫描直接/包装函数指针与可执行位移，验证保存的原生指令、`.pdata` 边界及实际资源尾段，再以新 JSON 输出拒绝覆盖。新 raw 位于 `.cache/procedural-modeling/static-slot-followup/sandcastle/`：`UnityPlayer-PlayerSettings-full.txt` 为字段函数完整反汇编；`native-field-sequence-and-payload.json` 保留 152 个本地名称 VA/PE 字符串文件偏移、与 174 节点的差异段及最后 35 项本地调用/大小；`UnityPlayer-PlayerSettings-direct-caller.txt`、`UnityPlayer-PlayerSettings-adjacent-callbacks.txt`、`UnityPlayer-PlayerSettings-binary-read.txt`、`UnityPlayer-PPtr-binary-read-helper-corrected.txt`、`UnityPlayer-PPtr-reader-flag-branch.txt`、`UnityPlayer-vector-binary-read-helper.txt` 是定点原生控制流。`player-callback-binary-read-verified.json` 保留表槽、唯一 call 位移、读/游标指令、格式/版本、资源边界与静态映射。旧 `native-field-sequence-anyreg.json` 是纯名称阶段结果，不作为末项映射依据。字段比对可复算为：

```powershell
python docs/studies/procedural-modeling/sandcastle/tools/player_native_field_sequence_probe.py --binary 'C:\Software\Steam\steamapps\common\Sandcastle Demo\UnityPlayer.dll' --disassembly .cache/procedural-modeling/static-slot-followup/sandcastle/UnityPlayer-PlayerSettings-full.txt --schema .cache/procedural-modeling/static-resource-followup/reference/6000.4.10f1-InfoJson.json --resource 'C:\Software\Steam\steamapps\common\Sandcastle Demo\Sandcastle_Data\globalgamemanagers' --output .cache/procedural-modeling/static-slot-followup/sandcastle/native-field-sequence-recheck.json
```

回调链复算为：

```powershell
python docs/studies/procedural-modeling/sandcastle/tools/player_callback_table_probe.py --binary 'C:\Software\Steam\steamapps\common\Sandcastle Demo\UnityPlayer.dll' --resource 'C:\Software\Steam\steamapps\common\Sandcastle Demo\Sandcastle_Data\globalgamemanagers' --schema .cache/procedural-modeling/static-resource-followup/reference/6000.4.10f1-InfoJson.json --caller .cache/procedural-modeling/static-slot-followup/sandcastle/UnityPlayer-PlayerSettings-direct-caller.txt --adjacent .cache/procedural-modeling/static-slot-followup/sandcastle/UnityPlayer-PlayerSettings-adjacent-callbacks.txt --reader .cache/procedural-modeling/static-slot-followup/sandcastle/UnityPlayer-PlayerSettings-binary-read.txt --pptr .cache/procedural-modeling/static-slot-followup/sandcastle/UnityPlayer-PPtr-binary-read-helper-corrected.txt --pptr-alt .cache/procedural-modeling/static-slot-followup/sandcastle/UnityPlayer-PPtr-reader-flag-branch.txt --vector .cache/procedural-modeling/static-slot-followup/sandcastle/UnityPlayer-vector-binary-read-helper.txt --output .cache/procedural-modeling/static-slot-followup/sandcastle/player-callback-binary-read-recheck.json
```

上述输出名每次需换为**尚不存在**的新文件。**静态已核**：对象边界、末 35 项名称顺序、回调表及唯一 call、二进制 reader 的尾段游标前移、`allowedHttpConnections ← +0x38c=0` 的本地读取绑定，以及余下 `+0x390=3`。**仍未知**：构建 writer/更外层 loader 对尾载荷的作用、三值的生产成员和游戏实际运行时 `allowedHttpConnections`。**Not Run**：游戏、Unity runtime、原生函数、玩家存档；没有安装软件、修改游戏或计算公共参考的摘要。
