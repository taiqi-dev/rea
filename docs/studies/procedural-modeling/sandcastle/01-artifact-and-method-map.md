# 制品身份与 IL2CPP 方法映射

## 精确制品

本次只读对象是 `C:\Software\Steam\steamapps\common\Sandcastle Demo`。`Sandcastle_Data/globalgamemanagers` 标示 Unity `6000.4.10f1`；`Sandcastle_Data/app.info` 标示 `BubblebirdStudio` / `Sandcastle`。`Sandcastle_Data/il2cpp_data/Metadata/global-metadata.dat` 为 8,928,184 字节，magic `0xFAB11BAF`、版本 39、SHA-256 `AA4457307746C4552541B6CEDD4809FDACCF33EEF03964A9E2300DE5A09E1606`。`GameAssembly.dll` 为 47,654,400 字节，SHA-256 `147030ECF9527A25250238120364EB761390B99688B1812C4EA555B3B04E56A0`。摘要仅用于本次获授权的版本身份核对。

`ScriptingAssemblies.json` 列出 `Assembly-CSharp.dll`。对 metadata v39 的索引检查，在该 image 得到 516 个类型；解析 methods/fields/parameters 时逐项检查节大小、索引边界与 declaring type。`GameAssembly.dll` 的 PE32+ `.rdata` 中找到唯一与 `Assembly-CSharp.dll` 名称关联的 `Il2CppCodeGenModule`，其 `methodPointerCount=1986`，指针表文件偏移 `42,845,216`。按方法 token 的 RID−1 取指针后，1986 项中 1954 项映射到 `il2cpp` 可执行段、32 项为空；其中 1373 项又能在 PE `.pdata` 中找到入口范围。这里“有地址”不等于“完整还原函数体”，编译器可能有拆分代码块，`.pdata` 也不覆盖所有方法。

| metadata 方法             | token        | native VA     | 交叉验证                                      |
| ------------------------- | ------------ | ------------- | --------------------------------------------- |
| `Game.FixedUpdate`        | `0x060003CA` | `0x18048A930` | 检查 phase 后调用 `Beach.Run`                 |
| `Beach.Run`               | `0x06000015` | `0x180428010` | 按对象字段调用 Ground、Water、Air 等层的 Run  |
| `Ground.Run`              | `0x06000159` | `0x18044FF60` | 调 Compute 调度及 PlaneChunk 碰撞更新         |
| `Water.Run`               | `0x0600032A` | `0x1804832D0` | 多次 Compute 调度与水出生处理                 |
| `Shovel.OnAction`         | `0x060002BC` | `0x180478B20` | 构造 Brush 后调用地表、Beach、Bucket 相关方法 |
| `PlaneGenerator.Generate` | `0x0600048C` | `0x180493DB0` | 分配顶点/索引并构成规则网格                   |

交叉验证不是仅靠方法名：`Game.FixedUpdate → Beach.Run`、`Ground.Setup → PlaneGenerator.Generate`、`Shovel.OnAction → Beach.Raze` 等目标地址与同一指针表的映射吻合。其他方法见本研究的按模块文档及 `.cache/procedural-modeling/sandcastle/codegen-map-all.json`。有界原生指令在 `.cache/procedural-modeling/sandcastle/disasm/`，仅保存调查用片段，不包含发布资源。

复查入口：[`tools/metadata39.py`](tools/metadata39.py) 读取 metadata；[`tools/map_codegen.py`](tools/map_codegen.py) 读取 PE/module/指针表；[`tools/enum_defaults.py`](tools/enum_defaults.py) 检查单字节 enum 默认值；[`tools/disassemble_mapped.ps1`](tools/disassemble_mapped.ps1) 用本机 `dumpbin /DISASM /RANGE` 截取已映射方法。解析布局参考固定版本 `24d8241b76ae79bbca92abc64aca00f66b3f11ce` 的 [Il2CppDumper metadata 结构](https://raw.githubusercontent.com/vmpprotect/Il2CppDumper/24d8241b76ae79bbca92abc64aca00f66b3f11ce/Il2CppDumper/Il2Cpp/MetadataClass.cs)与 [IL2CPP native 结构](https://raw.githubusercontent.com/vmpprotect/Il2CppDumper/24d8241b76ae79bbca92abc64aca00f66b3f11ce/Il2CppDumper/Il2Cpp/Il2CppClass.cs)；地址绑定是对**本地文件**再次验证的派生结果。`/RANGE` 参数见 [Microsoft 文档](https://learn.microsoft.com/en-us/cpp/build/reference/range?view=msvc-170)。没有把第三方解析器当作 Sandcastle 算法的证据。

REA Ghidra provider 可以打开 DLL，但本次首次全局 procedure 搜索 300 秒超时，未产生可引用的 REA 函数 Evidence；因此 native 结论依赖上述可复算的 token/PE 映射与有界反汇编，不声称已有 Ghidra 反编译或运行时证据。工具未修改游戏文件，也未执行游戏。
