# 本机路径、证据迁移与三款游戏对照

本次在 Windows 本机续查，起始时间为命令读取的 **2026-10-14 22:15 PDT（America/Los_Angeles）**。正式报告随 REA 仓库同步；安装文件、大型解码输出和当前机器路径保持本地。

## 这台电脑的目标

Steam common 根为 `C:\Software\Steam\steamapps\common`。

| 游戏        | common 下的目录   | 当前核对的入口                                                                             | Steam buildid |
| ----------- | ----------------- | ------------------------------------------------------------------------------------------ | ------------- |
| Tiny Glade  | `Tiny Glade`      | `tiny-glade.exe`、`tiny_glade.pdb`                                                         | 25804425      |
| 沙堡        | `Sandcastle Demo` | `GameAssembly.dll`、`Sandcastle_Data/il2cpp_data/Metadata/global-metadata.dat`、Unity 资源 | 24888454      |
| SUMMERHOUSE | `SUMMERHOUSE`     | `SUMMERHOUSE_Data/Managed/Assembly-CSharp.dll`、Unity 资源                                 | 20272848      |

buildid 取自这三个安装对应的 Steam appmanifest，不代表逐文件一致性。SUMMERHOUSE 包内版本文件为 1.2.12。各专题记录自己实际检查的程序集、资源或方法位置。

## Tiny Glade 可以接着用哪些旧资料

本机 EXE 为 65,612,184 B、PDB 为 310,513,664 B；两者 SHA256 与[原始证据身份](00-evidence-and-scope.md)完全一致：

- EXE：`4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`
- PDB：`ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2`

当前 EXE 的 PE CodeView 还读取到相同 GUID `d8d61d04-9e31-5b47-4c4c-44205044422e`、age 1、PDB 名 `tiny_glade.pdb`；首选 image base `0x140000000`。所以旧 EXE/PDB 上的静态地址和符号研究可继续对照。本轮没有重新核对每个 shader 或资源，也没有把旧电脑的解码产物冒称已迁移。

摘要由本次用户明确授权后，用 PowerShell `Get-FileHash` 对上述两个精确文件计算。授权仅用于本次三个指定游戏安装目录内取用制品的版本与证据身份，不是仓库或其它目录的摘要授权。

## 本机路径和大产物如何忽略

复用仓库已有 `.gitignore` 的 `.cache/` 规则；`git check-ignore -v .cache/procedural-modeling/local-targets.json` 已确认命中。无需在 Steam 游戏安装目录初始化 Git 或放置配置。

- 本机路径表：`.cache/procedural-modeling/local-targets.json`，记录唯一 Steam common 根、三个相对安装目录和本次观察到的 buildid。
- Tiny Glade 对齐回执：`.cache/procedural-modeling/tiny-glade-identity.json`。
- 新游戏原始结果：`.cache/procedural-modeling/sandcastle/`、`.cache/procedural-modeling/summerhouse/`。
- 正式解释与有用的可复现读取工具：当前 `docs/studies/procedural-modeling/` 下相应专题与 `tools/`，进入版本管理。

路径表是调查记录，不是 REA 运行配置；工具仍接收显式制品路径，不从旧报告中自动选择目标。换机只需重新定位安装目录，重新生成本机路径表和所需解码结果。历史报告中的 `E:\Steam\...` 和旧用户目录是当时来源，保留原样以避免重写历史。

## 三者在“程序化美术”上分别做什么

| 对照点     | Tiny Glade 既有研究                                  | 沙堡本轮发行版证据                                | SUMMERHOUSE 本轮发行版证据                   |
| ---------- | ---------------------------------------------------- | ------------------------------------------------- | -------------------------------------------- |
| 主要输入   | 墙线、建筑参数、道路/地形笔画                        | 笔刷/工具改格网状态，模拟持续演化                 | 选择预制块、格点位置、翻转与前后深度         |
| 形状来源   | 墙砖、屋瓦、梁、开口等专用构造器和实例显示           | 规则平面拓扑，GPU 解包高度后抬升顶点              | 现成构件实例化；相对位置组合可替换为其它构件 |
| 变化的关键 | 输入失效、局部重新生成及资源拼装                     | 沙/水高度速度、跨分辨率采样、粘性、侵蚀与悬沙交换 | 网格吸附、射线深度层、抽取袋、邻接配方       |
| 水与地形   | 已有水域笔画、河床、岸边与水面专题；物理河流仍有未知 | 已读实际流速、输运、侵蚀沉积与水面顶点/薄层裁剪   | 本轮聚焦建筑模块，不对水沙物理作结论         |
| 美术丰富度 | 参数几何与预置小件共同作用                           | 模拟产生形状；材质和道具另有职责                  | 构件库、换色、层次、组合奖励共同作用         |

这些是已读子系统的差异；不意味着任一游戏全包都只使用一种表示。Tiny Glade 对照分别依据[建筑拼装](64-tiny-glade-building-kit-and-asset-assembly.md)、[地形](31-tiny-glade-terrain-strokes-and-heightfield.md)及[水面](10-tiny-glade-water-render-pipeline-and-bank-transition.md)。

## 建议阅读顺序

1. 沙堡[总览](sandcastle/README.md) → [GPU 水沙、笔刷与沉积](sandcastle/04-gpu-simulation-and-brush.md) → [平面拓扑与最终模型](sandcastle/05-surface-mesh-and-water-rendering.md)。再用 CPU 调度和铲子专题补齐工具触发链。
2. SUMMERHOUSE[总览](summerhouse/README.md) → [放置和前后层次](summerhouse/01-placement-grid-and-depth.md) → [组合和变体](summerhouse/02-picker-combinations.md) → [发行包中的真实窗户/人物配方](summerhouse/04-packaged-blocks-and-combinations.md) → [保存和调色](summerhouse/03-save-palette-and-visuals.md)。

一个具体差异是：SUMMERHOUSE 包内确有“两个相邻、同 ID 的窗户满足配方后，原位换为带角色窗户”的配置；奖励预制件多出角色和眼睛网格。这是**配方选择已有美术**的证据，不能写成运行时生成了一套人物几何。沙堡则已从实际 GPU 程序确认，同一规则网格顶点的 Y 来自持续变化的沙高/水高。

官方 [Sandcastle 页面](https://store.steampowered.com/app/3216520/Sandcastle/)描述水沙交互和工具塑形；[SUMMERHOUSE 页面](https://store.steampowered.com/app/2533960/SUMMERHOUSE/)描述自由建造和小秘密。它们只提供产品背景，具体公式和调用链来自本机静态证据。

本轮没有启动游戏、操作鼠标、读取玩家存档或验证实际画面；构造算例不是运行测试。每篇保留其精确未知项，不能以“已反编译”代替真实交互和渲染验收。

## 本轮验证记录

- Passed：本次新增/修改的 14 份 Markdown，132 个相对链接，UTF-8 与代码围栏；7 份 Python 源文件和 1 份 PowerShell 语法检查。
- Passed：正式沙堡工具重建方法表，4 个关键 CPU 地址与报告一致，规则网格函数得到 16,182 B 有界反汇编；38 份 compute DXBC 与 36 份选定沙/水显示 DXBC 均完成结构检查和 Windows 反汇编。
- Passed：正式 SUMMERHOUSE 工具在独立输出目录复现 455 个块、123 条配方、242 个需求、213 个库 ID 和 673 个 MeshFilter；526 次本文件引用、141 次外部引用、6 次空引用分别保留。
- Passed：算例中的格点、插值权重、局部沉积交换、笔刷增量、水面高度和网格数量核算；本机路径表及解码产物命中已有 `.cache/` 忽略规则。
- 工具限制：沙堡 REA/Ghidra 首次全局 procedure 搜索超时；已改用有界 PE/metadata/Windows 反汇编，未伪造 REA native Evidence，目标会话已关闭。
- Not Run：游戏交互、画面、帧时序、长时间数值守恒、实际性能及各海滩默认参数；本轮未改 REA 产品运行代码，不以这些研究探针通过代替产品全量测试。
