# 沙堡：PlayerSettings 尾部 `3` 的处理边界

[13](13-player-settings-exact-tail-mapping.md) 已把安装包内二进制 reader 的末项读值定位到对象 `+0x38c`。本篇继续问：**对象 `+0x390` 的 `3` 是否被相邻 typed 回调或外层加载器接管，谁在构建时写入它？** 新静态证据把 reader 接到 `PlayerSettings` 对象的实际虚表及 class 129 注册表，但仍没有接通通用加载器的虚调用或对象长度门。末尾四字节不能据此称为无用、padding 或可丢弃字段。

## 对象虚表和类注册的直接连接

先前仅从 `0x181eb1aa0` 附近的三个相邻函数指针寻找表头，得到的“没有表头引用”是错误边界：它是更长代码指针序列的**内部槽**。对本作 `UnityPlayer.dll` 的 `.rdata` 逐个读取 64 位值，`0x181eb1988–0x181eb1ae0` 连续 **44** 项均指向可执行节；之前的 `0x181eb1980=0x1b0000001a` 不是代码指针，之后的 `0x181eb1ae8` 从 ASCII `AndroidDeviceFilterData` 开始。连续区段内部没有可见的 MSVC RTTI CompleteObjectLocator 分隔符；这不能单独证明 44 项是一张表。

实际 `PlayerSettings` 虚表入口由对象代码给出：`0x180e61dba: lea rax,[0x181eb1a30]`、`0x180e61dc4: mov [rcx],rax`；另一路 `0x180e61f13` 同样取 `0x181eb1a30`，`0x180e61f24` 把它写到对象首指针。全 `.text` 对这个精确入口的四字节 RIP 位移扫描得到两个命中，经反汇编核准正是这两条 `lea`。因此，从**已实际写入的虚表入口**起算，字段包装器 `0x180e634e0` 位于 `+0x80`（slot 16），另一 typed 回调 `0x180e63540` 位于 `+0x88`（slot 17），二进制 reader thunk `0x180e63530` 位于 `+0x90`（slot 18）。入口后代码指针连续至 `0x181eb1ae0`（相对 `+0xb0`，slot 22）；由于缺少 RTTI 分隔符，不能仅凭连续性给每个后续槽命名。

类身份又有独立连接：初始化代码 `0x1816980e7` 把 factory `0x180e63550` 取到 `rax`，`0x1816980ee` 写入描述符 `0x1821755b0+8`，`0x1816980f5` 把描述符交给随后在 `0x18169813b` 调用的 `0x181690d10`。描述符静态数据的 `+0x10` 指向字符串 `PlayerSettings`，`+0x28` 为 class ID `0x81=129`，`+0x2c` 为 native object size `0x530=1328`。登记函数在 `0x181690d23` 取名称指针、`0x181690d2a` 取 class ID 后调用 `0x181690ed0`。factory 自身在 `0x180e63580` 申请 `0x530` 字节，`0x180e6359b` 直跳构造路径 `0x180e61f10`，其 `0x180e61f24` 写入上述虚表入口。这才把注册描述符和实际对象接成直接调用链；native size 不是资源对象长度 916，不能混用。至此可证 **class 129 注册 → factory 描述符 → 对象构造 → PlayerSettings 虚表入口 → `+0x90` typed reader**；仍缺“上层 loader 如何选择、调用此槽并处理返回游标”的实际指令边。

## 相邻 typed 回调和 reader 尾段

`0x180e63540` 先把上下文 `[rdx+0x6d]` 置零，再直跳 `.pdata` 函数 `0x180e67200–0x180e67477`。该函数对其它成员发出六次 `call qword ptr [r10]` 虚调用，所以它的整体语义和间接副作用仍未确认；不能因槽位相邻就称它为 postprocess 或 writer。

但对末项的可见指令很窄：`0x180e67452` 取内存 `[rdi+0x2c0]` 到 `eax`，`0x180e6746b` 把同一个 `eax` 写回同一地址，`0x180e67476` 返回；二者之间没有针对这个成员的虚调用或来自文件游标的标量读取。整个第二槽函数没有直接 `add/inc/sub qword ptr [rbx+0x38]` 的游标推进指令。其早期的六次虚调用可能由各自 handler 处理其它成员；`[rbx+0x38]` 在此被当作接口对象取得虚表，**不能**仅因第三槽里同数字偏移是读游标，就把两种上下文视为同一类型或断言间接调用绝不读字节。因此，本轮只排除“第二槽的可见末项代码又从 `+0x390` 取四字节赋给 `allowedHttpConnections`”这一具体解释；不能排除外层调用或这些虚接口的其它作用。

第三槽 `0x180e63530` 是无后续指令的直跳到 reader `0x180e652b0`；reader 在 `0x180e671c9` 把最后四字节读值写入内存 `+0x2c0`，`0x180e671ff` 直接 `ret`。末次界限分支在 `0x180e671b8` 比较“当前游标+4”与 `[rbx+0x48]`，用于保证本次读取有四字节；没有在 reader 尾段检查“消费量恰等对象表长度”。**`[rbx+0x48]` 是哪个上层边界、返回后谁接手游标，仍需上层调用者才能判定。**

## 资源对象终点与尚未接上的 owner

资源 `Sandcastle_Data/globalgamemanagers` 的 SerializedFile v22、Unity `6000.4.10f1` 对象表给 class 129/pathID 1 的起点 `0x4c0`、长度 916（`0x394`）及终点 `0x854`；`+0x38c` 是零，`+0x390` 是三。本地 reader 的已解普通路径从组织名后的 `+0x354` 计算到 `+0x390` 后返回，所以此时距对象表终点还有 **`0x394 - 0x390 = 4` 字节**。这个长度差是载荷内差额，而非两个对象之间的对齐填充（下个对象从 `0x860` 起）。

虚表入口和类登记虽已闭合，还不能从“存在 `+0x90` 槽”推出通用 loader 调用它。定点复核的其它 `+0x90` 虚调用候选至少有两类不相干路径：`0x180e78800` 处是另一虚表/分配器对象，`0x1804de6e0` 处把返回值用作集合计数；它们不能充当本对象的加载器。全体间接调用没有穷举证明，因此这里的**最小未闭合边**是：class 129 注册项/factory 选择的对象如何进入通用 SerializedFile loader，其对虚表 `+0x90` 的实际 call、传入游标，以及返回后游标 `+0x390` 对对象终点 `+0x394` 的处理。当前不能判断上层报错、跳过、保留还是另行读取余下四字节。

构建时 writer 也未从这条运行时注册与回调链识别。[12](12-player-settings-tail-field.md) 的同版本公开 Release 树消费 912 字节，本地 reader 也停在 912，而本作对象为 916。`+0x390=3` 的生产可能涉及构建侧附加成员、平台差异或外层载荷约定；这些都只是候选，没有对应写入指令或未剥离的 class 129 type tree。不能以 reader 未消费就推断游戏运行时一定忽略它。

## 可复算证据和状态

新 raw 均位于 `.cache/procedural-modeling/static-owner-followup/sandcastle/`：`UnityPlayer-PlayerSettings-constructor-vptr.txt`、`UnityPlayer-PlayerSettings-class-factory-registration.txt`、`UnityPlayer-class-registry-insert.txt`、`UnityPlayer-PlayerSettings-factory-to-vptr.txt` 支持虚表和类注册；`UnityPlayer-PlayerSettings-slot-thunks.txt`、`UnityPlayer-PlayerSettings-slot2-body.txt`、`UnityPlayer-PlayerSettings-slot3-tail.txt` 支持两槽控制流。`player-tail-owner-vftable-factory.json` 记录连续代码指针边界、真正入口、描述符、槽偏移、对象终点和未闭合的 loader 门。旧 `UnityPlayer-PlayerSettings-vtable-reference.txt` / `player-tail-owner.json` 保留先前错误表头假设的检查原始记录，**不可用作新的无引用结论**。定点正式工具 [`player_tail_owner_probe.py`](tools/player_tail_owner_probe.py) 只读输入，要求新 `--output`，拒绝覆盖。复算时给输出换一个未存在的文件名：

```powershell
python docs/studies/procedural-modeling/sandcastle/tools/player_tail_owner_probe.py --binary 'C:\Software\Steam\steamapps\common\Sandcastle Demo\UnityPlayer.dll' --resource 'C:\Software\Steam\steamapps\common\Sandcastle Demo\Sandcastle_Data\globalgamemanagers' --thunks .cache/procedural-modeling/static-owner-followup/sandcastle/UnityPlayer-PlayerSettings-slot-thunks.txt --second .cache/procedural-modeling/static-owner-followup/sandcastle/UnityPlayer-PlayerSettings-slot2-body.txt --third-tail .cache/procedural-modeling/static-owner-followup/sandcastle/UnityPlayer-PlayerSettings-slot3-tail.txt --constructor .cache/procedural-modeling/static-owner-followup/sandcastle/UnityPlayer-PlayerSettings-constructor-vptr.txt --registration .cache/procedural-modeling/static-owner-followup/sandcastle/UnityPlayer-PlayerSettings-class-factory-registration.txt --registry .cache/procedural-modeling/static-owner-followup/sandcastle/UnityPlayer-class-registry-insert.txt --factory .cache/procedural-modeling/static-owner-followup/sandcastle/UnityPlayer-PlayerSettings-factory-to-vptr.txt --output .cache/procedural-modeling/static-owner-followup/sandcastle/player-tail-owner-vftable-factory-recheck.json
```

**Passed（静态）**：实际对象虚表入口及其构造写入、class 129 注册描述符、相邻槽身份、第二槽末项 self-copy、reader 直接返回、对象末尾余四字节。**Partial**：另一 typed 回调六个虚接口的间接副作用、通用 loader 的 `+0x90` call 与对象长度门、构建时尾项生产者。**Not Run**：游戏、Unity runtime、原生回调、玩家存档；未改动游戏或安装软件。
