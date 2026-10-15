# 沙堡：末尾 `3` 的构建端证据边界

后续[18](18-transfer88-and-tail-production.md)追查本篇未闭合的+0x88：可见本体处理资源引用候选回填，末段未补写尾值；接口首槽和构建writer仍未接通。

**结论**：本轮没有在获准的发行安装范围内定位写入 class 129/pathID 1 对象末尾 `+0x390=3` 的构建端 writer，也没有找到可把它唯一归于某个 build profile 或字段的类型树。新证据收紧了边界：安装包七份可解析的 SerializedFile 中，只有 `globalgamemanagers` 含这一个 class 129 对象，七份均关闭 type tree；本机 `PlayerSettings` 虚表另一个 `+0x78` 槽是直接返回的空函数，而已证的 `+0x90` reader 只消费对象前 912/916 字节。这些结果排除了“在发行资源里找另一份 class 129 对照或未剥离树”和“该虚表 `+0x78` 槽补上末尾四字节”两个具体路线；**不能反推构建时三值的字段名或意图**。

## 对象与写入端问题

只读目标是 `C:\Software\Steam\steamapps\common\Sandcastle Demo`，核心资源为 `Sandcastle_Data\globalgamemanagers`，运行库为同目录 `UnityPlayer.dll`。资源自报 SerializedFile format 22、`6000.4.10f1`、platform 19；对象表的 class 129/pathID 1 从文件 `0x4c0` 开始，长度 `0x394=916`，结束于 `0x854`。前篇 [16](16-class129-reader-branch-and-tail-origin.md) 已用文件 type index、原生 type 记录和加载分支确认：本对象从 `0x4c0` 交给 `0x180e652b0`，最后从文件 `[0x84c,0x850)` 读出 `allowedHttpConnections=0`，于相对 `+0x390` 返回；余下 `[0x850,0x854)` 为小端 `03 00 00 00`。这仅是读取端和构建结果，不是 writer 证据。本篇没有重复执行目标或用消费端给三值命名。

## 发行资源和构建 profile 可见范围

新工具 [tail_build_surface_probe.py](tools/tail_build_surface_probe.py) 对安装目录中七个明确命名的 SerializedFile 逐一用 v22 索引解析器验证头、类型表和对象表，记录于本地 `.cache/procedural-modeling/static-replacement-followup/sandcastle/build-surfaces-and-tokens.json`：

| 文件                                | 自报版本 / platform | 对象数 |      class 129 | 文件级 type tree |
| ----------------------------------- | ------------------- | -----: | -------------: | ---------------- |
| `globalgamemanagers`                | `6000.4.10f1` / 19  |     19 | pathID 1，一件 | 关闭             |
| `globalgamemanagers.assets`         | `6000.4.10f1` / 19  |   1616 |              0 | 关闭             |
| `level0`                            | `6000.4.10f1` / 19  |    652 |              0 | 关闭             |
| `resources.assets`                  | `6000.4.10f1` / 19  |   1979 |              0 | 关闭             |
| `sharedassets0.assets`              | `6000.4.10f1` / 19  |  12448 |              0 | 关闭             |
| `Resources/unity default resources` | `6000.4.0b12` / 5   |     97 |              0 | 关闭             |
| `Resources/unity_builtin_extra`     | `6000.4.10f1` / 19  |     42 |              0 | 关闭             |

`unity default resources` 的自报版本/platform 与目标对象所在文件不同，这是**另一份资源的头信息**；其中没有 class 129，不能用版本差给末尾四字节指定来源。另有 `.resS`、`.resource` 原始流，但它们不是上述已解析的 SerializedFile 对象索引；本轮没有把任意二进制中碰巧出现的 `03 00 00 00` 当作同类 writer 对照。安装目录可见的是播放器、游戏程序集、原生依赖及数据文件，没有在此目录清单中发现 Unity Editor 构建程序或工程的 build profile 资产。`boot.config` 含 `build-guid` 和几项运行配置，没有 class 129 字段布局或 writer 身份。

为检验可直接识别的 profile 线索，工具对本安装的 `UnityPlayer.dll`、`GameAssembly.dll` 和 `global-metadata.dat` 搜索精确 ASCII 与 UTF-16LE 字面量；三者均没有 `BuildProfile` 命中。相同搜索可命中 `PlayerSettings`、`UnityEditor` 等一般字面量，所以“文件含 UnityEditor 名称”也不能证明其中有 Editor writer。这个负结果只覆盖三个文件、两个编码和这个精确词，不排除无该名字的构建配置、压缩数据或编译后代码。Unity 的[官方构建说明](https://docs.unity3d.com/6000.0/Documentation/Manual/build-command-line.html)中“Build with a build profile”一项指出，通过 `-activeBuildProfile` 构建需要工程中的 profile 资产；它是通用流程说明，版本为 6000.0，**不能证明本作采用了该方式**，更不给出 `+0x390` 的映射。所读范围为该页构建方式表，普通来源记录为本轮 raw 的 `public-build-reference.json`，没有计算摘要。

## 本机其他 transfer 槽的定点核查

[14](14-player-settings-tail-owner-and-loader.md) 已由构造写入确认本机 class 129 对象虚表入口 `0x181eb1a30`。本篇依据其已记录的表项逐槽复查：入口 `+0x78`（slot 15）和 `+0x98`（slot 19）均指向 `0x180081070`；`dumpbin` 在该地址只见 `ret 0`，没有从对象或流读写的指令。原始定点输出见 `.cache/procedural-modeling/static-replacement-followup/sandcastle/UnityPlayer-PlayerSettings-empty-vslots.txt`。因此，对于**这个实际构造的 PlayerSettings 虚表**，`+0x78` 不能作为末尾三值的额外消费或生产分支。此结论不扩展到其它对象、构建 Editor 的虚表或未见的调用约定。

同表 `+0x80` 是已追的字段登记包装器，登记路径按本机内存字段顺序以 `allowedHttpConnections` 结束；`+0x90` 是读取器。[14](14-player-settings-tail-owner-and-loader.md) 的 `+0x88` 回调有六次间接调用，但其可见末项只把内存 `+0x2c0` 的值写回本身；没有定位到针对资源 `[0x850,0x854)` 的写入。不能因为它邻近 reader 就把它叫作构建 writer，也不能从尚未穷尽的间接调用证明整个发行包绝无其它传输函数。精确版本本机缓存 `6000.4.10f1-InfoJson.json` 的 Release/Editor class 129 树都在 `allowedHttpConnections` 结束；该外部树不是本资源的未剥离类型树。[12](12-player-settings-tail-field.md) 和 [13](13-player-settings-exact-tail-mapping.md) 的本机字段与字节演算仍适用。

## 可复核例子与下一证据

以本资源为例，文件头的 type tree 开关为 0，七文件清单中也没有另一份 class 129 对照。把 `PlayerSettings` 对象从 `0x4c0` 交给本机直接 reader，末次 int32 位于 `0x84c` 且为 0，reader 停在 `0x850`；对象表继续至 `0x854`，该四字节为 3。尝试将同对象的 `+0x78` 槽作为第二 reader，实际只会调用 `0x180081070: ret 0`，不会解释这个差额。这个演算是文件与指令的静态结合，不是一次游戏运行或构建观测。

**最有判别力的缺失证据**是本作对应构建的 Unity Editor/构建端 class 129 序列化 writer 及其输入（工程 `ProjectSettings.asset`、实际 build profile 资产或构建记录），或同一次构建保留的 class 129 资源类型树。writer 需给出从配置成员到文件 `[+0x38c,+0x394)` 的写入顺序与长度，才能区分额外尾字段、末项前插槽、平台专用布局或其它规则；仅获得配置文本中的一个值 3 仍不足够。当前授权范围仅是发行安装和已有本机参考，不能自行去别的 Unity 安装、下载 Editor 或启动目标求证。

**Passed（静态）**：七文件 v22 索引及 type tree/class 129 覆盖、三个发行二进制/metadata 的限定字面量搜索、两个具体虚表空槽。新工具语法和原始 JSON 断言通过；仓库 `npm run docs:check` 通过（含 5 项文档一致性测试）。**Partial**：`+0x88` 间接 transfer 的所有作用和其它可能的发行端序列化入口。**Unknown**：实际构建 writer、profile 选择、三值对应的成员、诊断在游戏运行中的效果。**Not Run**：游戏、原生目标函数、GPU、私人存档、Unity Editor 构建、Ghidra 重试；未修改目标安装、未安装工具、未计算新摘要。
