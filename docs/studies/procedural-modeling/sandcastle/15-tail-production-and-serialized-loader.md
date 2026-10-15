# 沙堡：尾部 `3` 的生产来源与 SerializedFile 对象长度门

后续[16](16-class129-reader-branch-and-tail-origin.md)已把本文件类型记录接到直接 reader 分支，并核对入口没有预读 4 B；本篇的长度门条件因此获得本资源分支依据。三值的构建来源与诊断实际后果仍未知。

[12](12-player-settings-tail-field.md)、[13](13-player-settings-exact-tail-mapping.md)、[14](14-player-settings-tail-owner-and-loader.md) 已把本作 `PlayerSettings` 的本地 reader 绑定到 class 129 对象：它从文件相对 `+0x38c` 读取 `allowedHttpConnections=0`，在 `+0x390` 返回；对象表长度却是 `0x394`，最后的 `03 00 00 00` 还属于对象。本轮找到了**通用对象读取路径中的虚调用与长度比较**，也接通了 reader 所用 `context+0x48` 的缓冲上界。构建时是谁写入尾部 `3`，仍没有生产者证据。

## 结论及适用条件

- **已证实的通用路径**：`UnityPlayer.dll` 在 `0x18121f197` 从对象首指针取虚表并调用 `+0x90`，传入读取上下文；随后 `0x18121f1a1` 取当前游标，`0x18121f1af` 比较已读字节数与对象记录长度。不相等时调用 `0x18121e400`，其中包含 builtin class 序列化长度不匹配的诊断文本。它并非“reader 返回后余字节自动视作 padding”的代码路径。
- **已证实的上界来源**：该路径把对象数据起点和对象记录长度传给 `0x1813d2cc0`；后者形成期望终点 `start+length`，`0x1813d2d60` 再用底层缓冲可用量收紧上界。reader 从相同上下文的 `+0x38` 取游标、`+0x48` 取这个缓冲上界，因此其 `0x180e671b8` 检查只证明末次四字节读仍在界内，**不证明消费了完整对象**。
- **class 129 的条件推导**：若注册的 `PlayerSettings` 对象由这条直接 `+0x90` 分支读取，资源记录长度 916 与已追出的 reader 消费 912 相差 4，将进入长度不匹配处理。此处没有把 class 129 factory 创建的对象一路追到这个调用点，也没有游戏运行证据；不能写成游戏已触发诊断。通用路径还有另一个 `+0x78` 分支，条件依赖运行时类型记录，当前不能断言本对象选哪一支。
- **生产来源未解**：`+0x390=3` 是安装资源中的直接字节事实；已检查的 class 129 注册、factory、typed reader 和相邻 callback 均未提供写入此文件字节的构建端 writer。不能把 `3` 命名为 `allowedHttpConnections`、padding、对齐标记或某个新字段，也不能断言可忽略。

## 外层对象记录、上下文和长度比较

原安装 `C:\Software\Steam\steamapps\common\Sandcastle Demo\UnityPlayer.dll` 的 PE `.pdata`/`dumpbin` 静态反汇编显示，`0x18121ec50` 起的通用函数在 `0x18121ec77` 取对象记录数组，`0x18121ece9` 比较查找键，`0x18121ecf2` 取记录 `+0x14` 的类型索引。直接读取分支在 `0x18121ef32/36` 算 `rdi = 数据段起点 + 记录偏移`，在 `0x18121f170` 从记录 `+0x10` 取长度作为 `r9d`，以 `r8=rdi` 调用 `0x1813d2cc0` 初始化局部流；`0x18121f18c/190/194/197` 则以 `rcx=对象 r12`、`rdx=[rbp-80h]` 调用 `call qword ptr [rax+90h]`。`r12` 在 `0x18121ed02` 来自该函数的对象参数。这个数据流说明此处确实是**对对象虚表**的调用，而非仅仅某个无关接口也用了偏移 `+0x90`。

局部流起于 `[rbp-48h]`，正是传给 reader 的上下文 `[rbp-80h]+0x38`。`0x1813d2cc0` 在 `0x1813d2cee/f2` 生成并保存对象期望终点；`0x1813d2d60` 在 `0x1813d2d93–a9` 把可用缓冲终点与期望终点取较小值写入局部流 `+0x10`，即 reader 上下文 `+0x48`。所以对本资源若底层缓冲足够，期望上界为对象末尾 `0x854`；若不足，则上界更早。reader 的 `0x180e671b8` 是单次四字节边界检查，不能代替对象长度校验。

虚调用之后，`0x1813d2e40` 返回流的当前绝对位置；`0x18121f1a9–af` 从中减去本对象起点、与记录长度比较。等长跳过诊断；不等长走 `0x18121f1d1` 的 `0x18121e400`。后者引用的内建类格式字符串位于 PE VA `0x181f635b0`：`Mismatched serialization in the builtin class '%s'. (Read %d bytes but expected %d bytes)`。另一个已有类型树的分支在 `0x18121f076` 调 `+0x78`，其 `0x18121f08b` 对超读做检查；这两个分支不能混为一个对所有资源均适用的规则。`0x18121e400` 的下游包含条件诊断/日志路径；本轮未证明它对本游戏返回错误、强制终止，或自动跳过剩余字节。

以已解析的 `globalgamemanagers` 对象作**条件算例**：对象表给 class 129/pathID 1 `[0x4c0,0x854)`，长度 `0x394=916`；本地 reader 的已追普通路径从对象起点消耗 `0x390=912`，末次读落在 `0x84c–0x84f`。若上述直接分支接到该 reader，长度比较得到 `912 != 916`，未消费区间是 `0x850–0x853`，值为小端 `3`；下一对象从 `0x860` 开始。四字节在对象区间**内部**，并非两个对象之间的 12 字节间隙。这个例子不替代实际分支选择或运行观察。

## 末尾 `3` 的生产边界

class 129 描述符 `0x1821755b0` 的名称、ID、native size `0x530` 和 factory `0x180e63550` 已由 [14](14-player-settings-tail-owner-and-loader.md) 核实；factory 构造出的虚表 `0x181eb1a30` 使 `+0x90 → 0x180e63530 → 0x180e652b0`。这证明**读取者身份**，不证明制作 `globalgamemanagers` 的 Unity 构建端如何写文件。相邻 `+0x88` callback 可见的末项只做同一内存成员 self-copy，且其它六次间接调用的效果未穷尽；也不是已定位的文件 writer。

搜索边界作了收紧：对本 DLL 可执行节中 `FF /2 [reg+0x90]` 的 disp32 字节形态扫描得到 244 个候选位置，按 `.pdata` 函数反汇编后有 216 个精确地址上的可读指令，分属 205 个函数；这只是**一种虚调用编码形态**，不等于全体调用穷举。附近多种 `+0x90` 调用可明确排除为本对象读取：`0x180e2e1b8` 是引用计数归零的虚调用；`0x180bc96a4` 从另一 callback 表调用；`0x180d0def4` 把返回值当字符串对象使用。上文的 `0x18121f197` 因对象记录长度、上下文和返回游标三条边才被保留为通用加载证据。安装包静态检查仍没有 writer 的入口、写入指令或未剥离的 class 129 资源 type tree；负结果只限这些已审查路径。

## 证据与未决点

新原始记录在 `.cache/procedural-modeling/static-final-followup/sandcastle/`。`UnityPlayer-loader-object-prefix.txt`、`UnityPlayer-call90-000000018121f197-focused.txt` 记录对象查找与两条分支；`UnityPlayer-length-00000001813d2cc0.txt`、`...2d60.txt`、`...2e40.txt` 记录上下文和游标；`UnityPlayer-mismatch-handler-full.txt` 记录不等长诊断；`player-outer-length-evidence.json` 对关键 VA、指令文本、内建类诊断字符串和资源对象字节做了逐项复核。`UnityPlayer-call90-candidate-windows.json` 保留有界搜索与候选窗口。它们是本地静态文件证据，不是 REA Evidence ID；没有重复此前超时且状态未变的 Ghidra 分析。

**Answered（静态）**：通用直接读取分支确有对象 `+0x90` 虚调用、`context+0x48` 的上界构造、返回游标与对象记录长度比较，以及不等长诊断。**Partial**：class 129 在本游戏是否实际选该分支，诊断后的运行效果，以及跨对象的调度处理。**Unknown**：构建端生产 `+0x390=3` 的成员、版本规则或 writer。**Not Run**：游戏、原生目标函数、GPU 和私人存档；未修改目标安装目录，未计算新的摘要。

要解决生产来源，需要能与此 Unity 版本和构建选项对应的构建端序列化 writer 或未剥离的 class 129 type tree；要解决实际分支与后果，需要 class 129 类型记录如何进入此通用函数的静态连接或受控运行证据。当前安装包和本轮授权的只读静态范围没有这些证据。
