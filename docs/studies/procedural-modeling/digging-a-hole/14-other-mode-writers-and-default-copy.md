# 掘地求财：模式字段的通用默认值复制与直接写入边界

后续[15](15-property-copy-virtual-target.md)补出链接期标志：正常LinkInternal将bit30置位，两个字段各走一字节memcpy。本篇按构造期flags演算的虚调用条件不代表链接后的实际分支；通用模板选择与遍历证据继续适用。

在[12](12-initial-material-authority-and-overrides.md)已确认的主关卡 `VoxelWorld` 原生 CDO 模板、实例未序列化 `MaterialConfig`／`RenderType`，以及[13](13-material-property-flags-and-config-gates.md)已确认的普通 `LoadConfig` 跳过门之外，本轮找到一个**正向的默认值复制机制**。对象初始化可从模板或类 CDO 向新对象逐属性复制；两字段现有属性 flags 不触发这个函数的跳过门。因此原生构造写零并非实例值的最后一道静态写入。模板 CDO 的实际值和本关卡加载时是否经该分支执行仍未观察，不能据此宣称实例后来改为非零。

## 从模板到实例的属性复制

证据为同版 Shipping EXE/PDB 的 `FObjectInitializer::PostConstructInit`（`0x141395FF0`）和 `FObjectInitializer::InitProperties`（`0x1413934C0`）指令，原文分别在 ignored `.cache/procedural-modeling/static-other-writers/digging-a-hole/object-postconstruct.disasm.txt`、`object-initproperties.disasm.txt`，符号枚举在 `init-copy-symbols.json`、`postconstruct-symbols.json`。`PostConstructInit` 的 `0x1413961AE` 从 initializer `+0x8` 读取模板指针；为空时 `0x1413961BE` 从选定类 `+0x110` 取得类默认对象；`0x1413961C5–0x1413961D0` 将模板作为第三实参、目标对象作为第一实参传给 `InitProperties`。已有发行包证据将主关卡 actor 的模板标为 `/Script/Voxel.Default__VoxelWorld`，但这里没有观察一次实际构造调用。

`InitProperties` 将第一实参目标对象保存在 `r14`、第三实参默认源对象保存在 `rbp`（`0x1413934D5–0x1413934DB`），从目标 `+0x10` 读取类（`0x1413934F1`），沿类属性链迭代。对被访问的属性，`FProperty+0x44` 是成员偏移，`+0x30/+0x34` 是数组维数／元素大小：例如 `0x1413935AD–0x1413935CB` 计算 `default+offset` 与 `target+offset`，再在 `0x1413935D4–0x1413935F8` 选择 `memcpy` 或 `FProperty` 虚调用；另两条分支在 `0x141393667–0x141393698` 与 `0x141393758–0x141393793` 做同类复制。`PostConstructInit` 因此提供了无需同名 setter、无需直接把 `0x47D`／`0x57C` 写死在指令中的写入路径。

属性 flags 门也有实际指令：循环在 `0x141393590–0x14139359C`、`0x141393630–0x14139363C` 或 `0x141393736–0x141393748` 检查 `0x800000202000` 与 `0x8000080000`，满足特定组合时才跳过或选择别的路径。[13](13-material-property-flags-and-config-gates.md)从本作描述符及构造指令得到两字段各自 flags `0x18000000000005`；它与这两个掩码均无交集，bit30 也为零。**条件演算：** 当 `InitProperties` 的属性链访问 `MaterialConfig` 或 `RenderType`，且默认源为上述原生 CDO 时，这些 flags 本身不阻止它用 `FProperty` 虚复制路径把 CDO 对应偏移的值写入目标。具体虚槽实现、CDO 内存值、目标 actor 是否走到这次调用，仍未由本轮证明；这是一条通用机制及适用条件，不是运行时值报告。

## 精确偏移直接写入候选

新[读取器](tools/voxel_field_writer_probe.py)在本作 PE 的 `.text` 内扫描 `+0x47C`、`+0x47D`、`+0x57C` 的 disp32 写码形状（普通 ModR/M 与 SIB），使用 `.pdata` 界定函数并从本地 PDB 枚举函数起点；最终原始清单为 `field-store-final.json`。它读到 135 个**候选**（`+0x47C` 77、`+0x47D` 0、`+0x57C` 58），枚举 854811 个本地符号并匹配 73 个候选函数起点。候选数不是已解码指令数，更不是 `AVoxelWorld` 写者数；数据中的相同字节、指令中部、其他类的同偏移都会命中。

在 `.pdata` 有边界且 PDB 精确归属为 `AVoxelWorld::AVoxelWorld` 的候选里，仅有[11](11-chunk-material-mode-selection.md)已证的 `0x1441C8AD1` **16 位**零写 `world+0x47C`（覆盖 `+0x47D`）和 `0x1441C8BD2` 零写 `world+0x57C`。其他具名候选包括 `FPostProcessSettings`、`TVoxelGraphGeneratorInstanceHelper` 等不同接收者，不能按相同偏移归属到 world。一个容易误判的 `0x143E22310` 在 `voxel-adjacent-47c.disasm.txt` 中明确是 `Z_Construct_UClass_AVoxelWorld_Statics::NewProp_bConstantLOD_SetBit`，执行 `mov byte ptr [rcx+47Ch],1`，只写相邻布尔字节，**不触及** `MaterialConfig+0x47D`。

此前编码宽松扫描的两处 `+0x47D` 命中，经 `offset-47d-compare-verified.disasm.txt` 定点反汇编为 `0x1441899C8` 与 `0x144189A24` 的 `cmp byte ptr [r13+47Dh],3`，属于读取比较而非写入。最终写码扫描将它们排除。无精确同偏移写码不排除 `memcpy`／虚属性复制、其他起点的宽写、反射解释器、寄存器索引寻址、脚本或本次扫描未覆盖的编码；本轮不宣布全程序无其他写者。

验证：读取器对目标 PE 长度、PE32+ 头、`.text/.pdata` 边界做检查；输出新文件时拒绝覆盖。定点 `dumpbin /DISASM /RANGE` 核对上述比较、相邻布尔写入和通用初始化指令；所有操作仅离线读取 EXE/PDB，没有启动、附加游戏或调用目标函数，也没有重算制品摘要。**Answered：** 通用模板／CDO 属性复制路径及两个属性 flags 对此门的条件影响。**Partial：** 精确 disp32 直接写候选未给出新 `AVoxelWorld` 写者。**Unknown／Not Run：** CDO 最终值、实际 actor 构造及脚本写入、运行帧和存档。
