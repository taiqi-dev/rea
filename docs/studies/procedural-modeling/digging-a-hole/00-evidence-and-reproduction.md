# 本机证据身份与复核

调查目标：`C:\Software\Steam\steamapps\common\A Game About Digging A Hole`。记录时间为 **2026-10-14 Pacific Time**，Steam `appmanifest_3244220.acf` 的安装项与该目录对应，`buildid=22130236`。结论只适用于这批文件；另一台机器须重新对齐身份，不能只凭相同游戏名称复用地址。

## 文件与符号匹配

路径以下列安装根为起点。用户已明确授权本次对该根内实际取用的 EXE、PDB、配置和资源包计算摘要，仅用于版本与证据身份。

| 相对路径                                                    |       字节 | SHA-256                                                            |
| ----------------------------------------------------------- | ---------: | ------------------------------------------------------------------ |
| `DiggingGame/Binaries/Win64/DiggingGame-Win64-Shipping.exe` |  145180160 | `8356c03affeaa4a08fc92e52fdac6feb3a69cbd7b90fe96d67c3db9e83e6200a` |
| `DiggingGame/Binaries/Win64/DiggingGame-Win64-Shipping.pdb` | 1659662336 | `4c224da4242d2ace8a88cf156fe136f358b6b44f12b941d35419dfc202ade7d5` |
| `DiggingGame/Content/Paks/DiggingGame-Windows.utoc`         |     238780 | `3ac4ed2c5b5d827c31f86641cb1763f01d10c8c67591ec66d27035a3e89fedd6` |
| `DiggingGame/Content/Paks/DiggingGame-Windows.ucas`         |  150245088 | `860ebfd857bb82f489f6f73932c3ff21b9c3da11a3a231509277e974972c23b6` |
| `DiggingGame/Content/Paks/DiggingGame-Windows.pak`          |   48167563 | `4221bcca7b82012599319a3fa1da35a8ef5b9d9d8b383b3e31a52b1a1d153624` |
| `DiggingGame/Content/Paks/global.utoc`                      |        314 | `983e6ee51d2e850a8125b8c3a3e8d2930fed15b87f3c3cf1686b2f70e41b9447` |
| `DiggingGame/Content/Paks/global.ucas`                      |    2444240 | `1cb0c3fc970af317158ed20d2a2f30d4e43dbbf7cba2062205bca97359feaa9a` |

Shipping EXE 是 PE32+ x64，首选基址 `0x140000000`。Windows 版本资源仅给出 `UE5-CL-0`，不足以确认引擎补丁版本。解出的项目描述启用了 `VoxelPro`；该描述和原生 Voxel 符号支持技术栈身份，不代替世界实例的算法选项。

EXE 的 RSDS 记录位于文件偏移 `130928988`，记录 PDB 文件名 `DiggingGame-Win64-Shipping.pdb`。其 GUID 为 `b6f613a8-3359-3fae-499f-16304cd0e880`、age 为 `1`；PDB MSF7 信息流中的 GUID/age 相同。用 [pdb_identity.py](tools/pdb_identity.py) 实际比较通过，不是仅以文件名相同认定匹配。

## 工具、覆盖与保留位置

| 路线              | 实际操作                                                                                                                        | 能证明与限制                                                                                                                                 |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| REA MCP           | 以 Ghidra 提供者打开 Shipping EXE，确认路径、PE、x86_64 和摘要；结束时关闭会话                                                  | 本作没有执行 Ghidra 深度反编译；下文函数语义来自另一条独立静态路线                                                                           |
| Microsoft DbgHelp | [pdb_probe.py](tools/pdb_probe.py)，明确只用 EXE 所在目录的本地符号                                                             | 解析函数名、VA、大小；每个查询保留 exhausted/limited。函数存在不等于游戏运行时调用                                                           |
| VS 2022 dumpbin   | `14.44.35222.0`，按符号地址与大小有界反汇编                                                                                     | 复核数值、调用和分支；未执行目标 EXE 或加载游戏 DLL                                                                                          |
| 容器解析          | [package_probe.py](tools/package_probe.py)，本批 IoStore v8、PAK v11                                                            | 索引与精确条目提取；遇到其他布局或不支持的压缩会失败，不猜解                                                                                 |
| Oodle 解码        | 用户另行授权，固定 `powzix/ooz` 提交 `05038060aa68f9187ae9923b2388ca8db40e58d1`，用现有 VS v143 / Windows SDK 10.0.26100.0 构建 | 只在本项目 `.cache` 内，纯解码路径，不使用游戏内 Oodle DLL；编译成功，存在上游类型转换等警告                                                 |
| Zen 元数据        | [zen_probe.py](tools/zen_probe.py)，读取 name batch、import/export 表与序列化范围                                               | native import 用 global ScriptObjects 解析；外部包暴露精确包名和存储的 export 标识，成员仍须对目标 export 表匹配。元数据中的引用不是执行证据 |
| Blueprint 字节码  | [blueprint_probe.py](tools/blueprint_probe.py)，限定到选定 UFunction                                                            | 从唯一脚本范围连续解析；遇未知 token 停止，不猜测重新对齐。只有全部物理长度与逻辑长度吻合的输出才标 complete                                 |

IoStore 目录完整解析 **1338** 个文件条目；压缩表共 **4545** 块，其中 **1675** 块无压缩、**2870** 块为 Oodle，逻辑块上限 262144 字节。PAK 完整目录为 **4475** 个文件。只选择与本题有关的角色、地图、爆炸、保存结构与配置，不导出模型或贴图作为自研资产。

解码输出检查与条目声明长度相同。global 的 ScriptObjects 单一 chunk 长度为 2444229；正式工具与首次独立提取逐字节比较相同。此项检查不等于整个容器的密码学完整性认证；没有重新计算容器内 name hash、export hash 或存储块 hash。

原始记录在本机忽略目录 `.cache/procedural-modeling/digging-a-hole/`：

- `identity*.json`、`pdb-identity.json`：文件身份与 EXE/PDB 匹配。
- `digging/`、`save/`、`performance/`：有界符号查询与反汇编原文。
- `iostore-*.json`、`pak-probe.json`、`global-probe.json`：容器索引、条目范围与提取记录。
- `packages/`、`config-decoded/`：选定的研究输入，不进入 Git。
- `*-zen.json`：解析后的资源身份、名字、导入和导出范围。
- `save-class-link.json`：角色主存档类的外部包名与存储 export 标识匹配；字节码记录在 `save/`、`digging/` 与 `explosion-blueprint.json`。
- `tools/ooz/`：获准获取的固定源码与本地构建，不进入 Git。

跨机器只同步本目录的说明与自写读取工具；原制品、恢复资源、PDB、反汇编缓存和工具二进制不随报告提交。根 `.gitignore` 已忽略 `.cache/`；[本机路径映射约定](../68-local-targets-and-three-game-comparison.md)沿用，无需把安装目录写成通用工具的固定路径。

## 最小复核

以下是当前 Windows 机器上的可复核入口；另一台机器修改输入根并自行提供已获准的解码器。读取工具本身不计算摘要。

```powershell
$gameRoot = 'C:\Software\Steam\steamapps\common\A Game About Digging A Hole'
$studyTools = 'C:\Data\WebProject\rea\docs\studies\procedural-modeling\digging-a-hole\tools'
$evidenceRoot = 'C:\Data\WebProject\rea\.cache\procedural-modeling\digging-a-hole'
$shipping = Join-Path $gameRoot 'DiggingGame\Binaries\Win64\DiggingGame-Win64-Shipping.exe'
python "$studyTools\pdb_identity.py" $shipping ([IO.Path]::ChangeExtension($shipping, '.pdb')) --output "$evidenceRoot\pdb-identity.json"
python "$studyTools\pdb_probe.py" $shipping --mask '*Voxel*Sphere*' --output "$evidenceRoot\sphere-symbols-recheck.json"
python "$studyTools\package_probe.py" (Join-Path $gameRoot 'DiggingGame\Content\Paks\DiggingGame-Windows.utoc') --output "$evidenceRoot\container-recheck.json"
```

提取须显式给 `--select` 完整逻辑名称、`--extract-to` 输出目录与需要的 `--ooz` 路径；输出文件已存在时拒绝覆盖。`global.utoc` 的精确选择名为 `ScriptObjects`。Zen 读取再以 `--script-objects` 指向该解压后的 chunk。各专题保留关键 VA、文件名和构造例子，便于不携带原游戏代码的情况下核对结论。

本次完整解码的角色主图为物理 **167815/167815**、逻辑 **115747/115747** 字节；爆炸主图为 **2852/2852、1936/1936**；炸药主图为 **6488/6488、4560/4560**；为闭合主存档回调而读取的矿物管理主图为 **129075/129075、88931/88931**。还完整读取有关事件跳板及 SaveExample 的 Save/Load 函数。这是所选函数的解码覆盖，不代表全部 1338 个资源已恢复，也不证明这些分支在游玩时必定发生。角色导入 `-23` 的包名、编号和存储 export 标识与 SaveExample 类精确匹配，存档连接见 [02](02-save-load-and-consistency.md)。

## 格式参考与未运行项

容器与 Zen 结构参考的是解析器维护者的[PAK entry](https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/Pak/Objects/FPakEntry.cs)、[IoStore resource](https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/IO/Objects/FIoStoreTocResource.cs)、[Zen package](https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/Assets/IoPackage.cs)和[name batch](https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/Objects/UObject/FNameEntrySerialized.cs)实现；操作码另核对 [Epic EExprToken](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/CoreUObject/EExprToken)。这些是格式参考，本报告中的对象、偏移与计数来自实际安装文件。解码器身份见[固定提交](https://github.com/powzix/ooz/tree/05038060aa68f9187ae9923b2388ca8db40e58d1)。

**Not Run**：游戏启动、进程附加、真实玩家存档读取、一次挖掘前后对比、FPS/帧耗、保存锁等待、磁盘写入完成、强制退出恢复、长时间深挖与云存档冲突。静态代码和包内配置不能替代这些验证。交付的自研规格是独立建议，不包含可直接商用移植的原作代码或资产。

最终静态复核 **Passed**：5 份 Python 源码语法解析、5 页 Markdown 编码/代码围栏与 18 个本地链接、EXE/PDB GUID/age 和主存档类身份对齐；按冻结的读取工具重新解析选定的 11 个 Blueprint 函数，全部物理/逻辑字节数吻合。收据为本机 `.cache/procedural-modeling/digging-a-hole/validation/receipt.json`。这不扩大上述 Not Run 范围。
