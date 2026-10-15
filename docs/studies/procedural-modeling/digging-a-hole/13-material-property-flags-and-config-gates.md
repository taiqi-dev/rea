# 掘地求财：材质模式属性与普通配置加载的边界

后续[14](14-other-mode-writers-and-default-copy.md)补出模板/CDO 的普通属性复制入口。它与本篇 Config 门是不同路径；普通 LoadConfig 跳过这两字段，不等于 ctor 后不存在其它写端。

[12](12-initial-material-authority-and-overrides.md)确认关卡 actor 使用原生 VoxelWorld CDO，并在创建/重建 renderer 时读取当时的 world。本篇继续核对“是否由普通配置加载改写默认值”。**MaterialConfig 和 RenderType 的本作反射描述符均不含 Config 位；同一 EXE 的 LoadConfig 属性循环明确跳过该位为零的属性。** 因而在保留这些构造标志的普通配置路径中，它们不会因同名 ini 项而被这个循环导入。其他代码改写值或反射标志、特殊加载钩子仍未排除。

## 两个实际属性描述符

目标身份沿用[00](00-evidence-and-reproduction.md)，不重算摘要；只读同版 Shipping EXE/PDB 和已有六个 Zen name 表。新原始记录位于 ignored `.cache/procedural-modeling/static-final-followup/digging-a-hole/`。新增[定点读取器](tools/voxel_property_config_probe.py)从 PE 节表换算 VA/file offset，读取描述符并核对名称、字段偏移及原生门控的实际机器字节；没有调用目标构造函数或 LoadConfig。

| 属性                         | generated 描述符 VA |  文件偏移 | params 的 flags / 成员偏移   |
| ---------------------------- | ------------------- | --------: | ---------------------------- |
| `AVoxelWorld.MaterialConfig` | `0x14719DC40`       | 119132736 | `0x10000000000005` / `0x47D` |
| `AVoxelWorld.RenderType`     | `0x14719E410`       | 119134736 | `0x10000000000005` / `0x57C` |

两者均为 64 B 描述符，名称指针指向精确 NUL 结尾字符串。`+0x10` 保存64位 flags，`+0x30` 的 ArrayDim 为1，`+0x32` 的成员偏移分别为上述值；不是从相邻属性的大小猜字段。generated `PropPointers` 的类归属沿用[07](07-material-slots-and-handler-selection.md)与[11](11-chunk-material-mode-selection.md)。本轮 PDB 对 `*NewProp_MaterialConfig*` 14/14、`*AVoxelWorld*MaterialConfig*` 2/2、`*AVoxelWorld*RenderType*` 2/2 均枚举完毕。另查 `*AVoxelWorld*Set*Material*` 无具名符号；这个负结果本身不能证明没有直接或间接写入。

同一 EXE 的 `FEnumProperty` 描述符构造路径在 `0x14127DA55` 令额外 flags 为 `0x8000000000000`，`0x14127DA6A` 调用 `FProperty` 构造。后者 `0x14131DDAA` 将此实参与 `params+0x10` 做 OR，`0x14131DDB1` 写到新 `FProperty+0x38`；`0x14131DDD0–DDD5` 把 `params+0x32` 的成员偏移写到 `FProperty+0x44`。在这个写入点，两属性 flags 都是 `0x18000000000005`，bit14、bit18、bit4 均为0。

[Epic 的 EPropertyFlags 定义](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/CoreUObject/EPropertyFlags)将 `0x4000` 称为 `CPF_Config`、`0x40000` 称为 `CPF_GlobalConfig`、`0x10` 称为 `CPF_BlueprintReadOnly`。公开 API 页面当前标为5.8，只用于解释这些名称，**不据其猜本作引擎补丁版或结构布局**；实际偏移、数值与 bit14 门来自本作指令。两属性未标 BlueprintReadOnly 也不能证明游戏蓝图实际写了它们，只说明不能借“找不到原生 setter”把模式称为不可变。

## LoadConfig 是先筛属性，再导入值

本作 `UObject::LoadConfig` VA `0x141308C50`、大小5799 B。其正常属性循环在 `0x141309470` 从当前 `FProperty+0x38` 取 flags，`0x141309474` 用 `bt rdi,0Eh` 检查第14位；`0x141309479` 在该位为0时跳到 `0x141309B42`。那里从当前属性 `+0x48` 取下一个属性，`0x141309B57` 回到同一筛选点。此跳转绕过该属性的配置项查找和导入体。bit18 则在 `0x141309490–94A4` 影响配置所属类选择，发生在 bit14 门之后；它不能替一个未通过 bit14 的属性打开导入。

**条件演算：** 保持 MaterialConfig 上述构造 flags，不另行改反射标志，即使某个 ini 中出现 `MaterialConfig=1`，`0x18000000000005 & 0x4000 = 0`，此循环仍直接处理下一属性，而不是把1写入 world。RenderType 同理。这个例子没有创建或读取玩家 ini；它解释该门的行为，不证明所有配置系统、CDO 初始化钩子或手写配置解析都不能写这两个字节。

因此，[12](12-initial-material-authority-and-overrides.md)中的配置未知现可拆为两类：普通 LoadConfig 属性循环按当前 flags 跳过，已得到直接证据；其他初始化、反射标志修改、手写配置解析和游戏脚本仍未穷尽。原生默认0、关卡实例不覆盖、renderer再采样的条件链可保留，但仍不能宣布运行中永远为0。

## 六个选定包的名称检查仅作入口覆盖

复用此前已完整解出的 MainLevel、角色、SaveExample、OreSpawner、Explosion 和 Dynamite 的 Zen name 表，分别有224、1150、89、272、74、100项。对 `MaterialConfig`、`RenderType`、`RecreateRender` 作不区分大小写的子串检查，均没有名称命中。完整结果记在 `property-config-gates.json`；这只说明这些既有包的 name 表没有提供同名静态入口，不是全部1338个容器条目的扫描，也不是全部蓝图语义的穷尽反编译。其他函数、原生代码、反射与间接调用仍可能改变状态，不能靠名称阴性升级为全程序无写者。

原始文件另有 `material-property-symbols.json`、`config-property-native-symbols.json`、`property-ctors.disasm.txt`、`enum-property-ctors.disasm.txt`、`object-loadconfig.disasm.txt`。本轮曾尝试按 DbgHelp 返回的两个 TypeIndex 读取成员类型，相关查询返回参数错误，未将其当成可用的结构布局；正式结论改由描述符字节和实际构造/加载指令建立。

```powershell
python -X utf8 docs/studies/procedural-modeling/digging-a-hole/tools/voxel_property_config_probe.py --binary "C:/Software/Steam/steamapps/common/A Game About Digging A Hole/DiggingGame/Binaries/Win64/DiggingGame-Win64-Shipping.exe" --metadata-root .cache/procedural-modeling/digging-a-hole --output .cache/procedural-modeling/static-final-followup/digging-a-hole/property-config-gates-recheck.json
```

输出须为新文件，已有文件会被拒绝。**Answered（静态）：** 两属性描述符和构造写入点的 flags、成员偏移、普通配置循环的 bit14 门及跳过路径。**Partial：** 其他属性标志/值写入、CDO/基类初始化与游戏脚本的完整覆盖。**Not Run：** 游戏、CDO实际内存、LoadConfig执行、真实材质/renderer切换、性能和私人存档。
