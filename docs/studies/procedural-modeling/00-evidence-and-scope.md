# 程序化模型研究的证据身份与范围

调查时间为本机命令取得的 2026 年 10 月 12 日 01 时 26 分起，America/Los_Angeles，PDT。目标是用户选定安装包中的程序化模型生成，重点为 Tiny Glade 的建筑；未将其他游戏或用户存档纳入目标。

## 制品身份

| 制品 | 字节数 | SHA256 |
| --- | ---: | --- |
| `E:\Steam\steamapps\common\BadNorth\BadNorth_Data\Managed\Assembly-CSharp.dll` | 2862080 | `e7e3f74711209b65fce685eaa9a532450773a47b162692341d1053c95ac8d2bf` |
| `E:\Steam\steamapps\common\Tiny Glade\tiny-glade.exe` | 65612184 | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| `E:\Steam\steamapps\common\Tiny Glade\tiny_glade.pdb` | 310513664 | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |

Tiny Glade EXE 的 PE Debug Directory 记录 RSDS GUID `d8d61d04-9e31-5b47-4c4c-44205044422e`、age 1；PDB 的 MSF Info stream 具有相同 GUID 和 age，身份匹配。EXE 首选 image base 为 `0x140000000`，下文 RVA 不等于现场进程地址。

其 `build-info/toolchain-info.json` 声明 Rust 1.95.0、LLVM 22.1.2、`x86_64-pc-windows-msvc`、优化等级 3 且 debug 为 true。这是包内构建声明；版本名称不替代上述字节身份。

## 本地解码与覆盖

Bad North 使用已有 .NET SDK 的 `System.Reflection.Metadata` 离线读元数据与 IL。没有加载或执行目标程序集。完整解码涵盖 2846 个类型；研究聚焦生成相关对象，整体解码数量不等于整款游戏已研究。

Tiny Glade 使用 Windows `dbghelp.dll` 官方符号 API 枚举本地匹配 PDB，再筛选建筑相关入口。该方式提供符号名、地址和部分源行映射，不提供原始源码或可靠完整类型字段。未执行游戏、附加进程或请求远程符号下载。

Tiny Glade 的 17 个选定 `compiled-shaders/country-core/compiled/*.precomp` 文件包含 32 个 SPIR-V 模块。以魔数定位候选，再核对前置 word count、边界、保留字段、所有指令长度及 opcode，并要求 MemoryModel 和 EntryPoint 记录。依据 [Khronos 官方语法](https://github.com/KhronosGroup/SPIRV-Headers/blob/main/include/spirv/unified1/spirv.core.grammar.json) 解码。此处验证是结构验证，未运行官方 SPIR-V validator，也未覆盖编译包全部成员或全部语义合法性。

上述输出为本地分析记录，不冒称 REA Evidence。当前没有连接的 REA MCP 工具；`node scripts/rea.mjs --help` 返回 compiled runtime missing。本轮保留这个限制，没有反复 setup 或修改工具配置。

直接引用公式的着色器身份如下。路径相对于 Tiny Glade 的 `compiled-shaders/country-core/compiled`。

| 文件 | 字节数 | SHA256 |
| --- | ---: | --- |
| `wall/wall_brick_lod0.precomp` | 88849 | `024c457a5680956f8c1aa4c726ee0dfaa76b2c902a9dfbfca26a9ce0e28ac7b8` |
| `nani_instanced_roof.precomp` | 114565 | `1eb428a8262ac739b4353771acf8219e9def853808fe32c2d40afdc77e522672` |
| `roof_tiles_gravity.precomp` | 10428 | `07b699617e7b1d24b7264d01929792065ef20de8960e33199d4f9e43a7845abb` |
| `paths/combine_path_exclusions.precomp` | 2075 | `b29eaea1a090dbe15b2b79ddc46fc481baebadc67deba7aa3e9d6aed245d76c3` |
| `wall/prefix_brick_chunks.precomp` | 6307 | `549aed46572aa9d91e72ee7a32e2e765e7bfe61b47b2a64ad8caa6eaf4959468` |

第二轮补充：已使用固定 Capstone 5.0.3 离线解码同一 EXE 的选定函数，以及新增 4 个 shader 文件的 15 个 SPIR-V 模块。它们提供了屋顶剖面、局部相交与接缝算法的指令证据；详细覆盖、地址规则与验证见 [第二轮账本](06-tiny-glade-evidence-ledger.md)。这不改变 REA MCP/CLI 缺失的记录，也不代表取得了原始私有源码。

第三轮补充：继续使用同一 EXE/PDB 与包内 SPIR-V，研究水域绘制、上传、遮罩、河床、水生植物和水面。当前公式与未知见 [水域与河岸](07-tiny-glade-water-shape-and-banks.md) 及 [水体账本](09-tiny-glade-water-evidence-ledger.md)；没有将公开原型用作这轮发行版水体公式的来源。

## 公开原型身份

作者的 [country-slice](https://github.com/anopara/country-slice/tree/3f6a459c0424ed9177a0dceec4d72a380cbd80c2) 固定提交为 `3f6a459c0424ed9177a0dceec4d72a380cbd80c2`。读取范围是曲线铺砖、墙顶点变形、墙片元裁剪、路径笔刷、掩码模糊、拱段选择、拱线铺砖，以及相关渲染调度。源码中的实验、注释块和当前活动逻辑分开处理。

它是作者公开的 Rust、Bevy ECS、OpenGL 小项目。不能将它标为用户本机 Tiny Glade 的源码；发行版符号、着色器和原型之间没有建立逐函数等价关系。

## 本机分析产物

完整产物位于本聊天授权目录：

`C:\Users\81553\.codex\visualizations\2026\10\12\01a12f36-6ef5-7a13-a524-0ffafe4443f7`

- `badnorth/assembly-il.json` 与 `generation-il.json`：元数据及指令记录。
- `tinyglade-symbols/identity.json`、`symbols.json` 与 `broader_symbols.json`：制品身份和符号记录。
- `tinyglade-shaders/summary.json` 与各 `.precomp.json`：源文件摘要、嵌入模块范围和解码指令。
- `tinyglade-shaders/prototype-commit.json`、`prototype-tree.json` 与所选公开源码：固定提交的研究输入。

这些本机大文件不是报告的唯一解释来源，也未拷贝进 Git 仓库。报告正文保留关键公式、位置和证据边界，后续可以依据相同摘要重新取得对应制品。
