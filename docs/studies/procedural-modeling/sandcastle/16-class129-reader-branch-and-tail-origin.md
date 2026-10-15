# 沙堡：class 129 的实际读取分支与末尾 `3` 的来源边界

**静态结论**：本安装包的 `globalgamemanagers` 把 class 129/pathID 1 记为 type index 0、对象 `[0x4c0,0x854)`、长度 916。文件级 type tree 开关是 false；本机类型记录解析器在此开关为 false 时不构造 `record+0x30` 的类型树。通用加载函数用该指针选择分支，因此这份记录进入**直接 `+0x90` reader 分支**。该分支先把流置于对象起点，随后才调用 `PlayerSettings` reader；不存在外层预读 4 字节以把 912 字节 reader 消耗变成 916 字节的指令。普通界内路径仍在相对 `+0x390` 返回，通用加载函数会比较 `0x390 != 0x394` 并进入不等长诊断路径。这里是静态路径推导，游戏没有运行；诊断之后的实际玩家可见效果仍未知。

对象最后 `[+0x390,+0x394)` 的 `03 00 00 00` 确实是资源中的一个小端值 3。现有目标只证明**构建结果**，尚没有构建端 writer、资源内未剥离类型树或其他能把这个值唯一绑定到生产成员的证据。它不能被直接命名为 `allowedHttpConnections`、padding、对齐标记或新的具名字段。

## 从文件类型表接到本机分支

输入固定为原安装 `C:\Software\Steam\steamapps\common\Sandcastle Demo\Sandcastle_Data\globalgamemanagers` 和同目录 `UnityPlayer.dll`，不重算摘要。[工具](tools/player_reader_branch_probe.py) 的有界 v22 元数据读取结果见 `.cache/procedural-modeling/static-other-writers/sandcastle/class129-type-and-loader-calls-final.json`：文件是 `6000.4.10f1`、format 22、platform 19；元数据字节 `+0x45` 的第 0 项类型记录为 class ID 129、`isStrippedType=0`、`scriptTypeIndex=-1`，文件级 `enableTypeTree=0`。`isStrippedType=0` 与文件级无类型树是两个不同开关，不能混为一谈。元数据 `+0x200` 的第 0 项对象记录为 pathID 1、type index 0、相对数据偏移 0、长度 `0x394`。数据段起点和对象起点同为文件 `0x4c0`；终点文件 `0x854`。

本机 `UnityPlayer.dll` 的静态指令把上述元数据开关连到运行时类型记录：

| 边                 | 可复核指令和含义                                                                                                                                                                                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 文件头到运行时开关 | `0x18121c952` 默认置 `[r14+0x90]=1`；format `>=13` 时 `0x18121c960–966` 从文件读一字节覆盖。本资源为 v22，实际文件字节为 0。                                                                                                                                             |
| 类型表第 0 项      | `0x18121d602` 初始化记录，`0x18121d653/661` 以 `index*0xe8 + [r14+0x20]` 选当前类型记录，`0x18121d640` 把 `[r14+0x90]` 放入 `r8d`，`0x18121d685` 调 `0x181225740`。                                                                                                      |
| 记录中类型树       | `0x18121aaf0–ab28` 的记录默认值把 `+0x30` 置零；`0x181225763` 保存文件级开关，`0x181225861–864` 在零时跳过 `0x18121aeb0` 类型树解析，保持 `+0x30` 为零。该 parser 从记录头读 class ID，`0x1812257b3–7cd` 用它查本机类描述符。                                            |
| 对象到分支         | `0x18121ecf2` 从对象记录 `+0x14` 取 type index，`0x18121ed19/28` 算 `index*0xe8 + 类型记录数组基址`。`0x18121ef3a` 检查所选类型记录 `+0x30`；零值跳 `0x18121f0ef`，而非 `0x18121f076` 的 `+0x78` 类型树分支。                                                            |
| 对象到 reader      | 直接分支的 `0x18121f164–187` 以数据起点加对象偏移和长度初始化流；`0x18121f18c–197` 对传入对象虚表调用 `+0x90`。此前 [14](14-player-settings-tail-owner-and-loader.md) 已由 class129 注册、factory、构造写入证明其虚表 `0x181eb1a30 + 0x90 → 0x180e63530 → 0x180e652b0`。 |

这些是**资源记录、原生 parser、分支判定和对象 reader 的静态连接**；未声称观察到游戏执行。`0x18121ec50` 的三个 `E8` 字节候选位于 `0x180140fb9`、`0x181214ada`、`0x181215b4d`，均经定点反汇编确认为直接调用；它们是通用加载入口的调用点，不以调用点数量代表游戏运行次数。类型记录是否会被未知后续代码在运行时重写、以及启动时此对象何时加载，没有运行证据。

## 对入口 `+4` 假说的核对

如果外层预读了对象前四字节，reader 的 912 字节消费将把游标带到 `+0x394`，正好等于对象长度。但实际直接分支在 `0x18121f164–187` 以对象首址和 `0x394` 初始化流，紧接着在 `0x18121f18c–197` 调 reader；两者之间没有游标读取或 `+4`。流初始化 `0x1813d2cc0` 把传入首址保存为起点，`0x1813d2d60` 只构造缓冲上界。reader 的首个调用 `0x180e652cb–d2` 把流送至 `0x18008e6a0` 并写入对象内存 `+0x20`；该 helper 逐次取四个 int32，共 16 字节。文件对象开头 16 字节是非零 GUID 数据 `e6 f3 29 4f 2c 46 4f 43 8f a2 53 9a 2b ae 1e 56`，对应公开 Release 树的首项 `productGUID`，不支持“前四字节另作基类/ObjectHideFlags 而 reader 从 +4 开始”的布局。`PlayerSettings` 的公开树首项不是 `m_ObjectHideFlags`。

尾部还有独立锚点：reader 在 `0x180e66fd2/e1` 读取 `projectName/organizationId`，资源内 `organizationId` 到 `+0x354` 结束；其后已核的 bool 对齐、两个零长 vector（各取 4 字节计数）及两个 PPtr（各取 4+8 字节）把末项读取位置推到 `+0x38c`。`0x180e671c2–c9` 从这里读 0 并写入内存成员 `+0x2c0`，`0x180e671ff` 返回于 `+0x390`。同一内存成员在字段登记路径名为 `allowedHttpConnections`。[13](13-player-settings-exact-tail-mapping.md) 给出辅助函数和对齐逐项证据。已检查的 bool/PPtr 对齐不产生四字节位移。这里没有把外部 Release 树单独当作本机分支证明，而是用本机 reader 与资源锚点交叉核对。

可复算算例：流从文件 `0x4c0` 开始，末次 int32 读文件 `[0x84c,0x850)` 的 0，reader 返回文件 `0x850`；外层期望文件终点为 `0x854`，所以 `0x18121f1a9–d1` 的已读长度 `0x390=912` 与记录长度 `0x394=916` 不等，进入 `0x18121e400` 的内建类不等长诊断。`[0x850,0x854)` 存在小端 3，下一对象始于 `0x860`；该 3 属于当前对象，而非对象间隙。[15](15-tail-production-and-serialized-loader.md) 对通用长度门原先只作条件推导；本篇补上**这份类型记录在文件解析时选直接分支**的依据。该更正不把未知的诊断后果写成运行结论。

## `3` 的生产证据到哪里为止

资源对象表、数据字节和本机读取路径能确定：构建产物在该对象尾部保留 4 字节 3，而本机普通 reader 读到前一个 4 字节零值。安装包 `UnityPlayer.dll` 的注册/factory/reader 与通用 loader 是**消费侧**证据；相邻 `+0x88` callback 的可见末项只是内存成员 self-copy，未见从此文件位置写入产物的构建端 writer。公开精确版本 Release 树也只给消费到 `+0x390` 的结构，不能反推本游戏构建 writer 的成员。有限负证据只覆盖上述函数、资源和公开树，不证明其它发行文件或 Unity Editor 构建端不存在 writer。

因此，`3` 的最后可证生产边界是**已发行 `globalgamemanagers` 的四个原始字节**。若以后取得同构建选项的 Unity Editor writer、构建工程配置/日志，或未剥离的 class129 资源类型树，才可把它绑定到具体成员或版本差异。仅靠 `allowedHttpConnections` 这个字符串、另一项目配置中的值 3、或本机 reader 读出的零值，均不能确定它的构建来源。

## 复算与状态

先用 [工具](tools/player_reader_branch_probe.py) 从原安装只读解析类型表并列出通用 loader 的候选调用点；它拒绝覆盖输出，需换一个新文件名：

```powershell
python docs/studies/procedural-modeling/sandcastle/tools/player_reader_branch_probe.py --resource 'C:\Software\Steam\steamapps\common\Sandcastle Demo\Sandcastle_Data\globalgamemanagers' --binary 'C:\Software\Steam\steamapps\common\Sandcastle Demo\UnityPlayer.dll' --output .cache/procedural-modeling/static-other-writers/sandcastle/class129-type-recheck.json
```

本轮 raw 还包括 `UnityPlayer-header-tree-flag.txt`、`UnityPlayer-type-loop.txt`、`UnityPlayer-native-type-default.txt`、`UnityPlayer-type-record-parser.txt`、`UnityPlayer-branch-and-reader-call.txt`、`UnityPlayer-base-read-18008e6a0.txt` 及三个 `loader-caller-*.txt`，均位于 `.cache/procedural-modeling/static-other-writers/sandcastle/`。这些是本地静态反汇编，不是 REA Evidence ID。可用指定的 `dumpbin.exe` 加 `/DISASM:NOBYTES /SECTION:.text /RANGE:0x起点,0x终点` 对上表 VA 定点再取；`/RANGE` 必须带 `0x` 前缀。

**Passed（静态）**：文件 class129 类型索引/flags、文件级 type tree 开关、原生类型记录对该开关的分支、直接 reader 路径、reader 入口绝对游标和对象末尾差额。**Partial**：游戏实际执行后的诊断与后果。**Unknown**：构建端写入 `3` 的成员、writer 和意图。**Not Run**：游戏、目标函数、私人存档及 Ghidra 重试；未改目标目录、未安装软件、未计算新摘要。
