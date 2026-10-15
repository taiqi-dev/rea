# 掘地求财：生成类的两个模式属性如何进入正常链接

[15](15-property-copy-virtual-target.md)证明 `FEnumProperty::LinkInternal` 会为 `MaterialConfig` 与 `RenderType` 设置一字节元素大小和 bit30，但当时未把本作 `AVoxelWorld` 的生成类注册接到这次虚分派。本轮补出**静态连接**：`Z_Construct_UClass_AVoxelWorld → ConstructUClass → StaticLink → UClass::Link/UStruct::Link → FEnumProperty::LinkInternal`。所以第 15 篇的“一字节 `memcpy`”现在有本生成类的正常链接入口支撑；仍未观察游戏实际调用、CDO 最终值或关卡 actor 的初始化现场。

## 证据范围

沿用 [00](00-evidence-and-reproduction.md) 的安装 EXE/PDB 身份，不重算摘要。只读 `C:/Software/Steam/steamapps/common/A Game About Digging A Hole/DiggingGame/Binaries/Win64/DiggingGame-Win64-Shipping.exe` 和同目录 PDB；本地 `pdb_probe.py` 精确掩码定位，VS 2022 `dumpbin`（路径 `14.44.35207`，输出标头 `14.44.35222.0`）以 `0x` `/RANGE` 定点读 EXE。新原文在 ignored `.cache/procedural-modeling/static-bufferstate-followup/digging-a-hole/`：`link-entry-symbols.json`、`class-ctor-symbols.json`、`class-link-symbols.json`、`property-owner-symbols.json`、`ffieldclass-symbols.json`、`voxel-staticclass-symbols.json` 及对应的 `*.disasm.txt` / `*.raw.txt`。本轮没有执行目标函数、启动或附加游戏、读取私人存档。下列地址均为此 EXE 的首选映像 VA。

## 本类参数确实进入属性构造和链接

`Z_Construct_UClass_AVoxelWorld` (`0x143E22E10`) 在缓存为空时，于 `0x143E22E20–0x143E22E2E` 将本类 `ClassParams` (`0x14719FAD0`) 传给 `UECodeGen_Private::ConstructUClass` (`0x14138A750`)；返回时读取类缓存。`ClassParams+0x00` 的函数指针为 `0x143E0C5B0`，指令是 `AVoxelWorld::StaticClass → GetPrivateStaticClass`；`+0x28` 为 `PropPointers=0x14719F390`。`+0x38` 低 32 位 `0x04430182` 按 `ConstructUClass` 的 `shr 0xF; and 0x7FF` 解为 **134 个属性项**，与 PDB 中 `PropPointers` 大小 `1072=134×8` 对齐。第 [15](15-property-copy-virtual-target.md) 篇已逐项核过其中 `MaterialConfig` 的底层/枚举项 `42/43`、`RenderType` 的 `71/72`，此处沿用其描述符证据，不重列虚表数值。

`ConstructUClass` 在 `0x14138A843–0x14138A89F` 从上述 `+0x28` 取指针与编码项数，逐项调用 `ConstructFProperty`。它把新建 `UClass` 作为带标记的 `FFieldVariant` owner 传入。主 `FEnumProperty` 的 `FProperty` 构造在 `0x14131DD7F` 调 `FField` 构造，在 `0x14131DDDB` 调 `FProperty::Init`。`Init` (`0x141327E80`) 对 UField owner 在 `0x141327EC1–0x141327ED9` 走其虚表 `+0x2C8`；`UClass` 这槽的原始指针 `0x14125ABE0` 是 `UStruct::AddCppProperty`。后者在 `0x14125ABE0–0x14125ABEC` 将新属性挂到 `class+0x50` 表头，原表头成为属性 `+0x18` 的 next。枚举的底层 `FByteProperty` 是另由枚举属性拥有的内部属性；这里说的 `class+0x50` 链针对两个主枚举属性。

属性循环结束后，同一个 `ConstructUClass` 在 `0x14138A9BC–0x14138A9C1` 将新类作为 `rcx`、`dl=0` 调 `UStruct::StaticLink`。`StaticLink` (`0x1412753D0`) 把类、临时空 archive 与该布尔值传给对象虚表 `+0x2E0`。`UClass::UClass` 在 `0x14125903B–0x141259046` 安装 `UClass` 虚表；该表 `+0x2E0` 的原始指针是 `0x14126AAB0`，即 `UClass::Link`，其五字节跳转落到 `UStruct::Link` (`0x14126AB70`)。这一步用 EXE `.rdata` 实值核对了虚分派，并非只靠同名 PDB 符号推测。

## `dl=0` 实际走的属性链与枚举分派

`UStruct::Link` 在 `0x14126AB90–0x14126AB93` 因 `r8b=0` 跳到 `0x14126ADC8`，由 `class+0x50` 取链头；`0x14126AE1C` 沿属性 `+0x18` 迭代。对 owner 是本类且字段类 flags 第 15 位为 1 的项，`0x14126ADFD–0x14126AE16` 经属性虚表 `+0xB8` 调 `LinkInternal`。此前的 `enum-construct.disasm.txt`（`.cache/procedural-modeling/static-replacement-followup/digging-a-hole/`）显示，`FEnumProperty::StaticClass` 构造字段类时在 `0x141286EA0` 传入 flags `0x1000000008001`；本轮 `ffieldclass-ctor.disasm.txt` 显示 `FFieldClass` 构造在 `0x14127DC20` 将它写到 `+0x10`，所以这个 bit15 检查对主枚举属性成立。第 15 篇已从本作枚举虚槽和实现指令核实 `+0xB8 → FEnumProperty::LinkInternal (0x14129B070)`，以及它对底层 byte 的链接、尺寸读取与 bit30 OR；本轮新增的是生成类属性链**实际会调用这个槽的静态入口**。

**构造演算（静态，不是游玩观察）：** 缓存尚无 `AVoxelWorld` 类时，调用 `Z_Construct_UClass_AVoxelWorld` 使 134 项中第 43 项生成 `MaterialConfig` 主枚举属性并挂入本类链，随后 `StaticLink(false)` 遍历到它，分派到 `FEnumProperty::LinkInternal`。底层 byte 正常链接后尺寸为 1，主枚举 bit30 为 1；若稍后的 `InitProperties` 以 CDO `+0x47D=0x02` 为默认源、目标原字节为 `0x00`，且满足其余复制条件，目标在 `+0x47D` 变成 `0x02`。第 72 项 `RenderType+0x57C` 同理。这是指令与构造参数的条件演算；`0x02` 是假设值，不是 CDO 或 actor 的实测内容。

**Answered（静态）：** 本作生成 `AVoxelWorld` 的 134 项属性表、两枚举项进入 `ConstructFProperty`，主属性挂入类链，注册尾部 `StaticLink(false)` 经 `UClass::Link` 转到 `UStruct::Link` 的正确分支，并通过字段类 bit15 门调用枚举 `+0xB8` 槽。**Partial：** 若类缓存已存在，生成入口直接返回；本轮没有运行时调用记录或属性链内存快照。**Unknown / Not Run：** 原生 CDO 的最终两个模式值、实际 actor 初始化是否执行上述 `InitProperties` 条件分支、脚本后写入、运行帧与存档；游戏和目标函数均未运行。
