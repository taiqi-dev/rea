# 掘地求财：两个模式枚举的默认值复制宽度

后续[16](16-generated-class-property-link.md)把本作生成类注册、属性表与类链接到StaticLink(false)及实际LinkInternal虚分派。本篇的正常链接条件已有具体入口支持，CDO值与运行调用仍未知。

沿 [14](14-other-mode-writers-and-default-copy.md) 的 `FObjectInitializer::InitProperties` 继续追查，静态链条现可接到 **一字节 `memcpy`**：`AVoxelWorld.MaterialConfig` 和 `RenderType` 的 generated 描述符选择 `FEnumProperty`，各有一个 `FByteProperty` 底层属性。枚举属性完成正常 `LinkInternal` 后取得一字节元素大小和 bit30；`InitProperties` 据 bit30 走直接内存复制。**枚举虚表 `+0x100` 槽确实指向空实现，但在这个已链接条件下不走该槽。** 这修正了仅凭构造期 flags 把虚调用视为两字段最终复制方式的推断。

目标、身份和静态读取边界沿用 [00](00-evidence-and-reproduction.md)、[13](13-material-property-flags-and-config-gates.md)；本轮只读 `C:/Software/Steam/steamapps/common/A Game About Digging A Hole/DiggingGame/Binaries/Win64/DiggingGame-Win64-Shipping.exe` 及其同目录 PDB。没有重算摘要、执行目标代码或观察游戏。新增原始 PDB/PE/反汇编记录在 ignored `.cache/procedural-modeling/static-replacement-followup/digging-a-hole/`。

## 从两个描述符到一字节属性

| 字段             | enum 描述符 / 底层描述符 VA   | 对象偏移 | `AVoxelWorld` 的 `PropPointers` 项 |
| ---------------- | ----------------------------- | -------- | ---------------------------------- |
| `MaterialConfig` | `0x14719DC40` / `0x14719DC00` | `+0x47D` | 43 / 42                            |
| `RenderType`     | `0x14719E410` / `0x14719E3D0` | `+0x57C` | 72 / 71                            |

两个主描述符 `+0x18` 低六位都是 `0x1E`，两个底层描述符则为 `0`；四个描述符 `+0x30` 的数组维数均为 1。`UECodeGen_Private::ConstructFProperty` 在 `0x141389FCE–0x141389FF2` 以该低六位索引跳表；`0x1E` 项落到 `0x14138A477`，调用 `NewFProperty<FEnumProperty>`，并在 `0x14138A58B–0x14138A5A0` 递归构造随后的底层属性。`0` 项落到 `0x14138A4F4`，在 `0x14138A520` 调用 `NewFProperty<FByteProperty>`。上述 `PropPointers` 中两组都是底层描述符紧邻主描述符；这连接了本作的实际生成数据与构造分派，而非仅依据名称推测类型。PE 指针与跳表的定点核验见 `property-copy-bridge-anchors.json`，原始描述符和指令见 `selected-vtable-and-descriptor-words.json`、`codegen-construct-property.disasm.txt`；虚表符号来自 `property-vtable-symbols.json`。

`FByteProperty` 虚表 `0x1466AD1A0` 的 `+0xB8` 槽指向 `TProperty<unsigned char,FNumericProperty>::LinkInternal` (`0x14126B1E0`)；它在 `0x14126B1E6–0x14126B1EE` 以实参 1 调用 `FProperty::SetElementSize`。`FEnumProperty` 虚表 `0x1466B1980` 的同槽指向 `FEnumProperty::LinkInternal` (`0x14129B070`)：先在 `0x14129B081–0x14129B08D` 链接底层属性，再在 `0x14129B095–0x14129B09F` 从底层 `+0x34` 取元素大小设置到枚举属性。两字段因此在**正常链接完成后**各有一字节元素大小。指令原文分别在 `byte-linkinternal.disasm.txt`、`enum-linkinternal.disasm.txt`。

## InitProperties 选择复制分支

`FEnumProperty::LinkInternal` 在 `0x14129B0A9–0x14129B0B3` 将 `0x1040000200` OR 到该属性 flags (`+0x38`)；该常量含 `0x40000000`，即 bit30。构造期的 `0x18000000000005` 不含 bit30；按这里的正常链接路径，所得 flags 为 `0x18001040000205`，bit30 置位，Config bit14 (`0x4000`) 仍为零。[14](14-other-mode-writers-and-default-copy.md) 按构造期 flags 推到虚调用的条件，只适用于未加入链接标志的状态，不能用于已链接属性的分支判定。`InitProperties` 的 `0x1413935D4`、`0x141393674`、`0x141393769` 和 `0x1413937E8` 测试 bit30：置位走 `memcpy`，未置位才经属性虚表 `+0x100` 调用。`0x1413935AD–0x1413935E5` 的直接复制分支以属性 `+0x30` 数组维数乘 `+0x34` 元素大小作为长度。于是两字段在上述正常链接、属性链遍历、默认源与目标不同且其余边界检查通过时，长度是 **1 × 1 = 1 字节**，分别从默认源 `+0x47D`／`+0x57C` 写入目标同偏移。其余复制分支也按同一 bit30 和维数×元素大小规则处理，见 [14](14-other-mode-writers-and-default-copy.md) 的原始 `object-initproperties.disasm.txt`。

为排除“枚举虚调用自己复制字节”的另一种解释，直接读取两张虚表的 `+0x100`：`FEnumProperty` 指向 `0x140FC58F0` (`FProperty::CopyValuesInternal`，`ret`)，`FByteProperty` 指向 `0x14125F050` (`TProperty<unsigned char,FNumericProperty>::CopyValuesInternal`，逐字节循环)。这些地址与实现见 `selected-vtable-and-descriptor-words.json`、`property-construct-copy-symbols.json`、`enum-copy-slot.disasm.txt`、`byte-copy-slot.disasm.txt`。这里的关键不是空枚举槽本身，而是链接期 bit30 将普通初始化复制导向 `memcpy`。

**条件演算：** 假设初始化器选定的默认源 `MaterialConfig+0x47D` 为 `0x02`，目标原本为 `0x00`，并且属性已链接且 `InitProperties` 遍历到它，复制后目标该字节为 `0x02`；`RenderType+0x57C` 同理。这是对机器指令的构造演算，**不是**本作 CDO、子类默认对象或关卡 actor 的实测值。默认源仍由 `PostConstructInit` 的模板指针或类 CDO 分支决定，见 [14](14-other-mode-writers-and-default-copy.md)；本轮没有确定模板/CDO 最终值、子类覆盖来源，或实际 actor 是否经过该条件路径。

**Answered（静态条件）：** 两字段的反射类型、底层 byte 类型、链接后的元素宽度、复制分支及长度。**Partial：** 已知通用默认源选择，未解析这次 actor 构造实际所选对象及其值。**Not Run：** 游戏进程、实际 CDO 内存、actor 构造分支、运行中模式变化与私人存档。
