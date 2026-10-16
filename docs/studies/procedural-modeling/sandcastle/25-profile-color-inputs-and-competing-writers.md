# 沙堡：场景配置初色、所选参数表与同名写端

后续[26](26-startup-configuration-and-setup-colors.md)已补Awake启动实参、Prepare的seed初始化及Setup的HSV改色/回写；本篇首次启动配置未知的范围由新文收紧。

## 结论与证据边界

`level0` 的 `Game` 组件内联 `Configuration` 把 `sand=0`、`water=0` 序列化下来，但组件里的六个参数 Color 本身全为 `(0,0,0,0)`。它引用的 `Refs` 资源在 `sands[0]`、`waters[0]` 保存了**非零的六种默认色**；`Game.New(configuration)` 和 `Game.ResetConfiguration(seed)` 的原生分支按选择值从这两张表复制参数。因而“场景里直接保存的颜色”和“选择值 0 经默认表复制后的颜色”是两个不同阶段。后者是可复核的静态配置输入，**不是某帧的 GPU 值**：`Ground.Setup`、`Water.Setup` 还会向同六个名字写 global，其中 Water.Setup 在写前改动当前配置的两个水色；`Ground.Run`、`Water.Run` 后续又写同名 global。

只读目标为 `C:/Software/Steam/steamapps/common/Sandcastle Demo` 的 `Sandcastle_Data/level0`（96,756 B）、`sharedassets0.assets`（76,135,784 B）、`GameAssembly.dll`（47,654,400 B）与 IL2CPP metadata v39（8,928,184 B）。身份摘要沿用 [01](01-artifact-and-method-map.md)，本篇未重算；文件长度不能证明本轮与历史制品逐字节相同。全部新增结果是本地静态解析与 `dumpbin` 指令回执，**不是 REA Evidence、运行观察、游戏函数执行或 GPU 抓帧**。条件未变的 Ghidra procedure 超时没有重试。

## 场景对象到默认参数

[level0/Refs 解析回执](../../../../.cache/procedural-modeling/static-config-followup/sandcastle/profile-inputs.json)使用固定版本 SerializedFile v22 对象索引，核对无 type tree、对象边界与外部表 `fileID=2 → sharedassets0.assets`。`Game` GameObject `pathID=11` 的组件 PPtr 指向 `pathID=476`（class 114，文件 `0x124d0`、552 B）；该组件 `+0x38` 的 `(2,8784)` 指向名为 `GameProfile` 的资源，`+0x5c` 的 `(2,8790)` 指向名为 `Refs` 的资源。`GameProfile` 是用户资料对象；六个游戏颜色不在这里，而在 `Refs` 的内联 `SandProperty`/`WaterProperty` 参数表里。metadata 的 `Game`、`Configuration`、`Refs`、`SandProperty`、`WaterProperty` 字段顺序见既有 [完整类型表](../../../../.cache/procedural-modeling/sandcastle/metadata-all-types.json)。

Game 组件的 `header` 从对象 `+0xdc` 起，读出版本 1 与五个空字符串；接续的 `Configuration` 从 `+0xf4` 起。七个连续 32 位值依字段顺序为 `seed=70255`（文件 `0x125c4`）、`layout=0`、`format=0`、`sand=0`（`0x125d0`）、`waves=0`、`water=0`（`0x125d8`）、`resolution=2`。其后 `sandParameters` 的四个目标 Color 位于组件 `+0x110/+0x120/+0x130/+0x140`，`waterParameters` 的两个目标 Color 位于 `+0x1c4/+0x1d4`，均为 16 字节的全零值。这个边界还与原生 `Configuration` 的对象内偏移吻合：对象头后，选择值位于 `+0x1c/+0x24`，沙参数从 `+0x2c`、水参数从 `+0xe0`、波浪参数从 `+0x10c` 开始。

**对 [24](24-global-color-writers-and-order.md) 的偏移勘误**：[Water.Run 指令](../../../../.cache/procedural-modeling/sandcastle/disasm/Water_Run_full.txt)在 `0x18048344e` 把 `Game.Instance+0xb8` 取为 `Configuration`；`0x18048345e` 从该配置 `+0x10c` 开始复制的是波浪参数块，落在栈 `+0x70`。`0x180483490` 另取当前配置，`0x1804834a0` 读取 `+0xe0` 的 `waterColor`，并在 `0x1804834b0` 写到栈 `+0x40`；`0x1804834a9` 读取 `+0xf0` 的 `waterScatteringColor`，在 `0x1804834cd` 写到栈 `+0x50`。`0x1804837a9` 从栈 `+0x40` 开始取 RGB 供颜色转换，最后在 `0x180483803` 写 `waterColor` global。因此 [24] 表中将 `Configuration+0x10c` 标作首水色来源是块起点误配；此处首水色的正确来源是 `Configuration+0xe0`，第二水色是 `+0xf0`。这也与下文 `Game.New` 和 `Water.Setup` 对相同字段的复制、回写相互吻合。

`Refs` 是 `sharedassets0.assets` 的 class 114、`pathID=8790`，文件起点 `0x47e01e0`、长度 6428 B。[只读探针](tools/sand_profile_inputs_probe.py)在该**确切对象范围**内找到唯一 `count=7`、stride 216 B、类型号顺次 `0..6` 的 SandProperty 表（对象 `+0xe14`），以及唯一 `count=4`、stride 80 B、类型号 `0..3` 的 WaterProperty 表（`+0x15a8`）。每条记录的开头是类型值、两个缩略图 PPtr、解锁代价，默认参数 Color 从记录 `+0x20` 开始；字段顺序由 metadata 约束。两表其他条目的颜色、偏移和边界也保留在原始 JSON，不因只列第 0 项便视作未检查。

| 名称 / 来源字段                                | `Refs` 文件偏移 | 选中第 0 条的序列化 RGBA                     |
| ---------------------------------------------- | --------------: | -------------------------------------------- |
| `sandColor` / Sand.color                       |     `0x47e1014` | `(0.925490201, 0.886274517, 0.725490212, 1)` |
| `sandColor2` / Sand.color2                     |     `0x47e1024` | `(0.835294127, 0.807843149, 0.690196097, 1)` |
| `wetSandColor` / Sand.wetColor                 |     `0x47e1034` | `(0.789000034, 0.759226441, 0.647575498, 1)` |
| `sedimentColor` / Sand.sedimentColor           |     `0x47e1044` | `(0.800000012, 0.560784340, 0.407843143, 1)` |
| `waterColor` / Water.color                     |     `0x47e17a8` | `(0.898039222, 0.972549021, 1, 1)`           |
| `waterScatteringColor` / Water.scatteringColor |     `0x47e17b8` | `(1, 0.494117647, 0.262745112, 1)`           |

这张表是资源初值，不能拿 [23 的材质保存值](23-wet-sand-and-thin-water-transitions.md)替换它。例如 Material 20 保存的 `wetSandColor≈(0.906,0.810,0.633)` 与本表的 `Sand[0].wetColor` 不同；Material 41 保存的 `waterColor≈(0.960,0.986,1)` 也不同。[24](24-global-color-writers-and-order.md) 已证所选 Shader 不把这些名字声明为 Material Properties，且 Run 显式写 global。

## 配置复制、Setup 竞争与有界 PropertyBlock 核查

metadata 的 `Game.New` 参数确为 `configuration`。[Game.New 指令](../../../../.cache/procedural-modeling/sandcastle/disasm/Game_New_3cc.txt)在 `0x18048b906–0x18048ba18` 以传入配置 `sand(+0x1c)` 选 `Refs+0xa8`，把所选记录 `+0x2c..+0xdc` 复制到配置 `+0x2c..+0xdc`；在 `0x18048ba60–0x18048baa5` 以 `water(+0x24)` 选 `Refs+0xb8`，把记录 `+0x2c..+0x54` 复制到配置 `+0xe0..+0x108`。`0x18048bb2f` 再调用 `Game.Prepare`，后者 `0x18048bfe1–0x18048bffc` 设置 `Game+0xb8` 当前配置，`0x18048c1ef` 调 `Beach.Setup`。`Game.ResetConfiguration` 也在 `0x18048ce88–0x18048d0f1` 从相同选择表复制。`Beach.Setup` 对各层采用虚调用，故具体对象和每次运行是否经过该路径仍应与运行证据分开。`Game.New` **接收外部传入的配置**；静态代码没有证明某次调用一定把 `level0` 的内联零参数对象作为这个实参，也没有证明首次绘制前必执行 New。

若把 `level0` 的选择值 `sand=0/water=0` 作为一次 `New` 的实参，并且引用的 `Refs` 对象与本次解析相同，上述复制会把表中六色分别送至当前配置 `+0x2c/+0x3c/+0x4c/+0x5c` 和 `+0xe0/+0xf0`；随后 Run 以该配置取值，RGB 每通道经 `Mathf.GammaToLinearSpace`，alpha 保留。这是**实际资源值加已见分支的条件演算**，未代入未证明的启动路径。进一步构造 `W=0.0105`、沉积权重 `0.1`，若此时运行值恰好等于未被 Setup 改过的所选沙初色且没有其他覆盖，[23 的公式](23-wet-sand-and-thin-water-transitions.md)给出湿沙权重 `0.5`，首层颜色在每个 RGB 通道是 `0.9×[G(dry)+G(wet)]/2 + 0.1×G(sediment)`，其中 `G` 是上述转换。纹理、光照、Setup 改色和帧绑定均未纳入，故这不是最终像素值。

[精确直接调用扫描](../../../../.cache/procedural-modeling/static-config-followup/sandcastle/color-direct-calls.json)按该 metadata 的 CoreModule 方法表将 `Shader.SetGlobalColor(string,Color)` 映到 `0x181c1aca0`，在 `GameAssembly.dll` 文件支持的 `il2cpp` 节搜索 `E8 rel32` 到该目标，得到 16 个候选；所列站点均由原有或本轮定点 `dumpbin` 指令核为真正的 call。四个 `DayCycler.Update` 写的是 `sunColor`、`moonColor`、`backgroundColor`、`groundColor`，字面量槽分别为 `0x18295c480/0x18294a370/0x18296a218/0x18293bdf8`，与本篇六色不同。余下 12 个是两组同名调用：

| 写端           | 六色中对应名字的 setter VA                              | 取值阶段与限制                                                                                                                                                                                                                                                                                                                                                       |
| -------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Ground.Setup` | `0x180451386 / 0x1804513e1 / 0x180451444 / 0x18045149f` | [片段](../../../../.cache/procedural-modeling/static-config-followup/sandcastle/Ground_Setup_colors.txt)及[前置取值](../../../../.cache/procedural-modeling/static-config-followup/sandcastle/Ground_Setup_color_inputs.txt)：从当前配置 `+0x2c` 起复制到栈，并经 `Color.RGBToHSV` / `HSVToRGB` 的 Setup 计算再写 global；不能将它的四次输出直接等同于表中四个原值。 |
| `Ground.Run`   | `0x18045049e / 0x1804504fd / 0x18045055c / 0x1804505bb` | [24](24-global-color-writers-and-order.md) 的当前配置四项，经 RGB 转换写 global。                                                                                                                                                                                                                                                                                    |
| `Water.Setup`  | `0x1804846d3 / 0x180484742`                             | [片段](../../../../.cache/procedural-modeling/static-config-followup/sandcastle/Water_Setup_colors.txt)及[前置取值](../../../../.cache/procedural-modeling/static-config-followup/sandcastle/Water_Setup_color_inputs.txt)：从当前配置 `+0xe0/+0xf0` 做 HSV 计算；`0x18048459d` 将新 `Color` 写回 `+0xe0`，随后计算另一色并写回 `+0xf0`，再向 global 写这两个名字。  |
| `Water.Run`    | `0x180483803 / 0x180483862`                             | 当前配置 `+0xe0/+0xf0` 两项，经 RGB 转换写 global；来源链见上文偏移勘误。                                                                                                                                                                                                                                                                                            |

[Setup 字面量回执](../../../../.cache/procedural-modeling/static-config-followup/sandcastle/setup-global-color-literals.json)逐项验证六个 Setup setter 的 `.data` 槽、metadata literal 与 Run 使用的六个名字相同。`Ground.Setup`/`Water.Setup` 与 Run 之间存在同名写入竞争，但静态路径只给各方法内顺序、`New → Prepare → Beach.Setup` 的条件调用和 [24 的 Run 顺序](24-global-color-writers-and-order.md)；不能据此宣称任一真实 draw 的最后写者。

同一直接调用扫描还映出 `MaterialPropertyBlock.SetColor(string,Color)` 的 `0x181c0e9b0` 和 `SetColor(int,Color)` 的 `0x181c0e940`：在 `il2cpp` 节分别找到 1 和 2 个 `E8 rel32` 站点，均在本作 `Assembly-CSharp` codegen 指针范围 `0x180426240..0x1804c8d10` **之外**；三个[定点指令片段](../../../../.cache/procedural-modeling/static-config-followup/sandcastle/MPB_SetColor_string.txt)及同目录 `MPB_SetColor_int_1/2.txt` 核实它们确实调用对应重载。这个阴性边界只覆盖两个精确重载的**直接相对调用**及本轮映射的游戏方法区，不能排除间接调用、其他 API、引擎原生属性块、绘制时 MaterialPropertyBlock 或整数 ID 与六色同名的碰撞；没有获取六色最终 `$Globals cb0` 上传值。

## 复核与剩余问题

**Passed（静态）**：新[配置探针](tools/sand_profile_inputs_probe.py)在固定身份的两个 SerializedFile 上核 GameObject→组件→两个资源 PPtr、header/配置边界、唯一 7/4 条 profile 表、六 Color 的有限 float32 与对象范围；修订后重读的 [回执](../../../../.cache/procedural-modeling/static-config-followup/sandcastle/profile-inputs-recheck.json)和首次结果逐字相同。[调用探针](tools/sand_profile_writer_probe.py)映出三个确切重载和 19 个直接调用候选（16 global、3 PropertyBlock），相关 16 个 global 及 3 个 PropertyBlock 均有定点反汇编。两份探针的 Python AST 解析、报告本地链接与表/调用计数断言通过；没有修改目标或运行函数。这些都是**普通本地静态证据，非 REA Evidence**。

**Partial / Unknown**：`level0` 内联配置是否作为首次 `Game.New` 实参、Setup 的随机/场景依赖 HSV 输出、所有间接与引擎层同名写入、属性块是否附着到所选 Sand/Water draw、变体选择、实际帧顺序和 GPU 寄存器值。**Not Run**：游戏/Unity、进程附加、目标函数、GPU/Profiler、私人存档、Ghidra 重试、全项目构建。后续若允许帧取证，最小观察量是一次所选 Ground/Water draw 的 shader 变体、属性块和 `cb0[127/129/130/131/132]` 实值，并记录该 draw 前的配置与 Setup/Run 顺序。
