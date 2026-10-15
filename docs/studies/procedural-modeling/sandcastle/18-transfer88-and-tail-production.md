# 沙堡：`PlayerSettings +0x88` 引用传递与尾字节生产边界

后续[19](19-reference-interface-targets-and-tail.md)找到一个非空接口实例、首槽实际映射实现和传入+0x88的调用现场；动态接收者的class129身份尚未证明。下文的文件尾值生产者仍未知。

**本轮静态结论**：`PlayerSettings` 虚表 `+0x88 → 0x180e63540 → 0x180e67200` 的六处顶层间接调用，输入都来自对象内的资源引用成员或引用数组元素。函数把当前 32 位值交给 `context+0x38` 所指接口的虚表首槽；仅在 `context+0x6c` 非零时，把接口写到栈上的候选值回填给对象。这个函数本体没有向 SerializedFile 缓冲写入字段值，也没有在最后的 `allowedHttpConnections` 内存成员之后发起额外调用或尾字节写入。接口首槽的实际目标与所有可能的调用上下文仍未接通，因此不能把整个 `+0x88` 路径的间接副作用宣称为完全穷尽，更不能把它称为构建端 writer。

## 六个调用的对象输入

调用体来自原安装 `C:\Software\Steam\steamapps\common\Sandcastle Demo\UnityPlayer.dll` 的 `0x180e67200–0x180e67476`。下表的成员名由同 DLL 的字段登记函数 `0x180e637d0–0x180e652aa` 将内存偏移与字符串地址连接，再从该 PE 只读解码字面量；不是把文件偏移误当作对象内存偏移。

| 调用地址      | 输入对象位置                                | 字段登记中的名称                            | 回填地址及条件                      |
| ------------- | ------------------------------------------- | ------------------------------------------- | ----------------------------------- |
| `0x180e67238` | `+0x1b8`                                    | `defaultCursor`，登记类型 `PPtr<Texture2D>` | `0x180e67245`，`context+0x6c != 0`  |
| `0x180e672f8` | `+0x2c8`                                    | `invalidatedPatternTexture`                 | `0x180e67305`，同条件               |
| `0x180e6734a` | `(+0x418 指针)[i]`，步长 4；数量取 `+0x428` | `preloadedAssets`                           | `0x180e67357`，同条件；每个元素一次 |
| `0x180e673d9` | `+0x524`                                    | `hmiLoadingImage`                           | `0x180e673e6`，同条件               |
| `0x180e6740a` | `+0x4f0`                                    | `androidVulkanDeviceFilterListAsset`        | `0x180e67417`，同条件               |
| `0x180e6743b` | `+0x2f8`                                    | `d3d12DeviceFilterListAsset`                | `0x180e67448`，同条件               |

六处均从 `context+0x38` 取得接口对象，以 `rcx=接口对象`、`rdx=&栈上四字节候选值`、`r8d=当前成员值`、`r9d=context+0x68` 调用 `call qword ptr [接口虚表]`。这里的六是**静态调用点数**，不是每次执行恰好六次：`preloadedAssets` 可以逐元素重复调用，也可以为空。`0x180e67259` 还直接调用 `0x180e680e0` 处理对象 `+0x128` 的嵌套成员；该函数也对 32 位元素重复使用相同的接口首槽和条件回填模式。因而本轮没有把六处顶层调用误当成整个调用树的全部间接调用。

这些输入与读取侧的资源引用路径相合：本机 reader 在对象 `+0x2c8` 调 `0x180093fc0`，后者在可见分支中按 4 字节、再按 8 字节消费序列化引用；`preloadedAssets` 的 reader `0x1801c0d30` 先读数量，再对 4 字节步长的运行时元素逐个调用 `0x180093fc0`。这说明 `+0x88` 里的四字节对象成员值与文件中 12 字节的引用表示不能等同。此处只把该回调归为**对象引用值传递/候选回填路径**；接口首槽是映射、复制还是其它变换，需其实际目标才能定论。

## 末项与调用范围

最后一处间接调用 `0x180e6743b` 对应 `d3d12DeviceFilterListAsset`，其候选回填最晚在 `0x180e67448`。之后 `0x180e67452` 从对象 `+0x2c0` 取 `allowedHttpConnections` 的 32 位值，`0x180e6746b` 把同一寄存器值写回同一对象地址，`0x180e67476` 返回；这一段没有接口调用、流游标推进或写入另一个尾成员。`+0x88` 函数可见的其它直接 stores 也写对象成员或 `context+0x6d` 状态位。由于间接接口和嵌套调用目标未全数还原，这个否定结论仅限**本函数可见指令及末项之后的路径**。

对 `0x180e63540` 与 `0x180e67200`，以已用过的 PE `.text` `E8 rel32` 扫描器逐字节找直接 call 候选，结果均为零；作为对照，同一扫描器找到了 `0x180e67259 → 0x180e680e0` 的唯一候选。再查 PE 各节中的精确 64 位绝对指针及 `.text` 全部 29,935,101 个四字节 RIP 位移窗口：`0x180e63540` 仅在 `.rdata` 的 `0x181eb1ab8` 出现绝对指针，正是已证虚表入口 `0x181eb1a30+0x88`；`0x180e67200` 仅有 `0x180e63545` 的位移候选，经已存反汇编核准是该 thunk 的 `jmp`。这些结果覆盖上述三种直接引用形态，不否认上层虚调用或其它编码。对 `.text` 的 `FF /2 [常见寄存器+0x88]` disp32 字节形态另得到 158 个**待反汇编候选**，未逐个验证，也不能据此声称穷举所有虚调用。定点检查的 `0x18122ba76` 虽然是实际的 `+0x88` 虚调用，但其上下文构造 `0x18120fb30` 把 `context+0x38` 初始化为零，调用前窗口没有为它赋接口值；它不能直接当作本 `PlayerSettings` 回调的已接通调用者。

以前篇已证的资源作具体算例：class 129/pathID 1 的文件区间是 `[0x4c0,0x854)`，长度 916；直接 reader 消费至 `0x850`，即 912 字节。`+0x88` 的可见末段即使执行，也只在**内存对象** `+0x2c0` 上自写；没有把文件 `[0x850,0x854)` 的 `03 00 00 00` 追加、读入或解释。这排除“`+0x88` 的可见末段补写尾部 3”这条具体路线，但不识别构建时生产该四字节的成员。直接 reader 的长度不匹配路径仍按[16](16-class129-reader-branch-and-tail-origin.md)的静态条件成立；游戏实际后果未知。

## 证据、覆盖与下一边界

新增本机 raw 位于 `.cache/procedural-modeling/static-bufferstate-followup/sandcastle/`：`transfer-field-literals.json` 记录字段字面量；`direct-call-candidates.json`、`callback-reference-candidates.json` 记录直接引用候选；`call88-byte-candidates.json` 记录有界虚调用字节候选；`UnityPlayer-transfer-nested-180e680e0.txt`、`UnityPlayer-reference-reader-full-180093fc0.txt`、`UnityPlayer-preloaded-array-reader-1801c0d30.txt`、`UnityPlayer-call88-near-loader-18122ba76.txt`、`UnityPlayer-transfer-context-init-18120fb30.txt` 是定点反汇编。此前 `.cache/procedural-modeling/static-owner-followup/sandcastle/UnityPlayer-PlayerSettings-slot2-body.txt` 和 `.cache/procedural-modeling/static-slot-followup/sandcastle/UnityPlayer-PlayerSettings-full.txt` 支持顶层六处调用、字段偏移与末项控制流。这些是本地静态文件，不是 REA Evidence ID。

**Passed（静态）**：六个顶层调用的参数来源、对应字段、条件对象回填、嵌套成员处理、末项之后没有可见尾写，以及上述精确直接引用形态的扫描。`npm run docs:check` 通过（含 5 项文档一致性测试）。**Partial**：接口首槽具体实现和完整上层虚调用范围。**Unknown**：构建端 writer、文件 `+0x390=3` 的生产成员及意图、游戏运行后的长度诊断效果。**Not Run**：游戏、目标函数、GPU、私人存档、Unity Editor 与超时状态未变的 Ghidra；未改目标安装、未访问其它 Unity 安装、未计算新摘要。
