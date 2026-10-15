# 掘地求财：原生 VoxelWorld CDO 的构造入口与模式初值

[12](12-initial-material-authority-and-overrides.md)确认主关卡 `VoxelWorld` actor 指向原生 `/Script/Voxel.Default__VoxelWorld`，且实例属性没有序列化 `MaterialConfig`；[14–16](14-other-mode-writers-and-default-copy.md)说明普通对象可从模板/CDO 复制两个模式字节。本轮把**本类 CDO 自身**的静态构造链接到原生构造函数，并核对它是否在正常初始化中再从父 CDO 复制属性。结论是：本类注册的构造指针确实到达 `AVoxelWorld::AVoxelWorld`，它将 `+0x47D` 和 `+0x57C` 写零；按本类静态 flags 进入的 CDO 初始化选项令普通 `InitProperties` 复制门关闭。这比“原生 ctor 写零”多排除了一条 CDO 覆盖路径，但仍不是运行中 CDO 内存值的观测。

## 身份与原始记录

沿用 [00](00-evidence-and-reproduction.md) 已核过的同一安装身份；本轮只读 `C:/Software/Steam/steamapps/common/A Game About Digging A Hole/DiggingGame/Binaries/Win64/DiggingGame-Win64-Shipping.exe`（145,180,160 B）及同目录 PDB，不重新计算摘要。`pdb_probe.py` 从本地 PDB 枚举符号；VS 2022 `dumpbin` 14.44.35207（输出版本 14.44.35222.0）按 `0x` VA `/RANGE` 定点读取。新增原文和查询在 ignored `.cache/procedural-modeling/static-alias-followup/digging-a-hole/`，其中 `cdo-path-symbols.json`、`initialization-symbols.json`、`voxel-vtable-symbols.json` 记录完整掩码枚举；`getprivate-body.disasm.txt`、`create-default.disasm.txt`、`voxel-internal-ctor.disasm.txt`、`initializer-ctor.disasm.txt`、`initializer-dtor.disasm.txt`、`initializer-construct-internal.disasm.txt`、`actor-postinit.disasm.txt`、`object-postinit.disasm.txt` 及三个 `*.raw.txt` 是本轮定点原文。既有 `static-bufferstate-followup/digging-a-hole/voxelworld-getprivatestaticclass.disasm.txt` 和 `static-chain-followup/digging-a-hole/voxelworld-ctor.disasm.txt` 提供两端。下列地址均为此 EXE 的首选映像 VA；没有启动/附加游戏、执行目标函数或读取私人存档。

## 本类构造指针到 CDO

`AVoxelWorld::GetPrivateStaticClass` (`0x143E240E0`) 在缓存为空时于 `0x143E24147` 装入 `InternalConstructor<AVoxelWorld>` (`0x143E230E0`)，于 `0x143E2417D` 传给 `GetPrivateStaticClassBody` (`0x141266740`)。后者在 `0x1412667B3–0x1412667DE` 从对应栈实参取指针，存入新建 `UClass+0xB0`。这条本类注册路径与 [16](16-generated-class-property-link.md) 的 generated 属性注册是相连但不同的工作：前者提供原生对象构造回调，后者建属性并链接。

`UClass::CreateDefaultObject` (`0x14125F4C0`) 的本作 `UClass` 虚表 `+0x410` 原始指针为 `0x14125F4C0`（`uclass-create-default-vslot.raw.txt`）；父类缺少 CDO 时 `0x14125F532` 经该槽先创建父 CDO。本类随后在 `0x14125F610` 分配新默认对象，于 `0x14125F62E` 把它存到本类 `+0x110`；`0x14125F6B7–0x14125F6DF` 用新对象、父 CDO 和类 `+0xB0` 指针建立 `FObjectInitializer` 并调用回调；`0x14125F6E6` 析构初始化器。`InternalConstructor<AVoxelWorld>` 的 `0x143E230E0–0x143E230EC` 取 `initializer[0]`，非空即跳转到 `AVoxelWorld::AVoxelWorld` (`0x1441C88A0`)。该构造函数在 `0x1441C88BD` 令 `ebx=0`，`0x1441C8AD1` 将零 `word` 写到对象 `+0x47C`（覆盖 `MaterialConfig+0x47D`），`0x1441C8BD2` 将零字节写到 `RenderType+0x57C`。因此原生 CDO 的**构造函数写入点**有直接本类调用链，不仅是同名函数可能存在。

## CDO 初始化复制门

本类 `GetPrivateStaticClass` 在 `0x143E24165` 传 class flags `0x10000004`；`GetPrivateStaticClassBody` 于 `0x1412667F6` 设置 bit7 并在 `0x1412667FA` 存入 `UClass+0xD4`，得到此处静态值 `0x10000084`。`CreateDefaultObject` 在 `0x14125F6A8` 测试 `class+0xD4 & 0x10000080`，本类结果非零，故 `0x14125F6CB` 将初始化器选项 `r9d` 从 2 选为 0。`FObjectInitializer` 构造 (`0x141383230`) 在 `0x141383296–0x14138329D` 将 `(r9 >> 1) & 1` 写入初始化器 `+0x11`，本类为 0。`Construct_Internal` (`0x14138B330`) 的已读本体没有重写 `+0x11`；初始化器析构在 `0x141384A54–0x141384A57` 进入 `PostConstructInit`（有明确的延迟初始化分支，未将延迟路径当作已执行现场）。正常进入时，`PostConstructInit` 在 `0x141396191–0x141396195` 检查 `initializer+0x11`，零值跳至 `0x1413961D5`，跨过 `0x1413961D0` 对**对象自身**的 `InitProperties` 调用。它后面仍有子对象复制/实例化及配置逻辑；不能把此门扩成“整个初始化器不工作”。

接着 `PostConstructInit` 于 `0x141396301` 有条件调用普通 `UObject::LoadConfig`；[13](13-material-property-flags-and-config-gates.md)的本作属性 bit14 门在链接后仍对两个模式属性为零，因此那条普通配置循环不会导入它们。`0x141396438` 虚调对象 `+0x50`；`AVoxelWorld` 主虚表 `+0x50` 的实值为 `0x143219120`（`voxel-postinit-vslot.raw.txt`），即 `AActor::PostInitProperties`。它先调 `UObject::PostInitProperties`，再处理 actor `+0x5B/+0x60` 和组件；本体没有两个模式偏移的写入。`UObject::PostInitProperties` 中类虚槽 `+0x3B8` 在本作 `UClass` 虚表上为 `0x140FC58F0`（`uclass-postinit-inner-vslot.raw.txt`，三字节空返回），也未形成已见的模式覆盖。

**静态条件演算：** 若本类按上述未缓存的正常注册/创建路径建 CDO，且初始化器未进入另一个延迟或外部后写入路径，则原生 ctor 后两字段为 `0`；当前已读的本类 `InitProperties`、普通 `LoadConfig`、`PostInitProperties` 路径没有把它们改成非零。随后主关卡 actor 若以该 CDO 为默认源、没有其他写入，按[15](15-property-copy-virtual-target.md)的一字节复制，两个模式仍为零。这是机器指令上的条件链，**不是**一次游戏加载的观测，也不证明蓝图、特殊加载钩子、反射写入或运行时逻辑永远不能改值。

**Answered（静态）：** `AVoxelWorld` 原生构造回调由本类注册并进入 CDO 创建；CDO 原生构造的两处零写；本类静态 flags 所选 CDO 初始化选项及普通属性复制门；本类 `PostInitProperties` 虚分派。**Partial：** 不同注册/延迟初始化状态、特殊加载和外部后写入未穷尽，CDO 最终内存仍只能作条件零结论。**Not Run：** 游戏、实际 CDO/关卡 actor 内存、存档、可见材质和性能。
