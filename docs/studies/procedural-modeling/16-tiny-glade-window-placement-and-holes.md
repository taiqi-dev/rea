# Tiny Glade：普通窗户放置、墙洞生产与变化发布

本篇追到已修改窗对象怎样生成洞描述、按墙发布，以及旧新蓝图怎样决定显示重建。后续 [17 砖与木板重建](17-tiny-glade-window-wall-reconstruction.md)、[18 窗框贴合](18-tiny-glade-window-frames.md)、[19 窗边装饰](19-tiny-glade-window-autoclutter.md) 分开解释各自的算法；范围与原始证据见 [20 账本](20-tiny-glade-window-evidence-ledger.md)。

## 结论与证据边界

普通窗生成器把同一 decorator 转成两种蓝图数据：CPU 的 `WallSpaceRegion + HoleType` 用中心与宽高描述洞；32B `WindowCutRecord` 另有形状、墙坐标、朝向和世界位置。发布阶段按墙 ID 归组，随后 CPU finalize 才把中心/尺寸转成真正的 min/max `Aabb2`。两份数据不能合称一种 WindowCutLists，也不能从共享泛型符号把生成时的四个 float 当成 min/max。

本次只读匹配发行 EXE/PDB。EXE SHA256：`4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`。地址均为 RVA；preferred image base 为 `0x140000000`。DbgHelp 提供范围，Capstone 5.0.3 解码；7 批共 33 个不重复范围、46,616 字节均完成线性解码。范围完整不代表全部可达、类型完整或全部语义恢复。每范围原字节摘要、文件偏移、指令和 SHA256 保存于 `*-decode.json` 与 `.asm.txt`，总索引为本机 `tinyglade-windows-placement/findings.json`，可选证据链接见 20。没有 REA Evidence ID，不能伪装为 REA provider 成功结果。

## 1. 已修改 decorator 是蓝图生成器的入口

`generate_cottage_wall_windows` RVA `8C71E0`，14,305B；`generate_gothic_wall_windows` `8C3060`，10,855B。cottage 的 `8C75A7 → C3BA10 Decorators.iter_modified` 构造迭代器。小函数 C3BA10 从 Decorators+60/+68/+78 取哈希集合控制区、边界和长度，输出 48B 原始迭代状态。随后 8C7636 取 ID，8C766A 附近查 decorator，8C773F/7741 只允许 `DerivedDecoratorInfo.subtype <= 1` 进入 cottage 分支。这个 subtype 与 `DecoratorInfo+59` 的窗型选择值不同。

生成器通过 `DecoratorInfo.dst_as_wall`（901130）取得墙坐标；通过 decorator collision 库取得 Rectangle3d：8C7858 为查表，8C786A/786F 把 collision+20..3F 复制至栈上 32B 区域。`Rectangle3d.extent` DF4150 明确返回 `(+10, +1C−+18, +14)`，对应该局部矩形的宽、高、深。尺寸并不是来自同名 OS `WindowSize`。后者的四个小函数只是检索误匹配，未作为建筑窗证据。

**构造例子**：若 modified 集合只有 ID 11，则本轮 cottage 从 ID 11 查相应目标、窗型、collision；ID 12 不由此入口重新生成。已有蓝图仍存在于后面的当前蓝图表中。鼠标射线、吸附、拖动怎样写这个集合和 dst 未在本次追踪。

## 2. 蓝图按 ID 更新，生成器不在旧洞数组上不断追加

cottage 在 8C79F3 调 `DecoratorBlueprints.insert` 8F3750（1,742B），得到 Arc 的 payload 指针。insert 有已有条目和新条目、唯一拥有与共享 Arc 分支：8F383F 的原子操作及 strong-count 条件决定能否原位复用。复用分支清理此前 builder/碰撞/附属对象并把洞、切口等数组长度归零；返回点 8F3C6B 为 Arc+10。

蓝图 payload 上可由读取/写入确认的两组 Vec 使用：

| 数据 | capacity | pointer | length | 元素使用跨度 |
|---|---:|---:|---:|---:|
| CPU wall region/type | C8 | D0 | D8 | 20B |
| window cut record | 110 | 118 | 120 | 32B |

发布函数拿 Arc 基址，因此同字段多 +10，例如 CPU pointer 为 Arc+E0。总分配大小 0x170 包含 Arc 前缀，不应宣称 payload 本身就是 0x170；生成器另一个 visual builder 元素也使用 0x170，并非同一种对象。

**构造例子**：同一 ID 原有一个洞，修改窗型后重跑 insert，CPU length 清零再写新洞。不会因拖动十次而积累十个旧洞。共享旧 Arc 可以作为前一版本比较基准；确切所有权对象生命周期没有在本报告全恢复。

## 3. Cottage：一个中心/尺寸 CPU 洞，以及有条件的一份形状切口

8C85F9 检查 destination tag，8C8616 得到 height=`rect[1C]−rect[18]`。宽度来自 rect+10。CPU 宽度修正如下（8C8621、8C8635、8C864A、8C9CB2、8C9CCF）：

- destination tag 非 0：宽度不减。
- tag 为 0 且窗型选择值为 1：减 0.05。
- tag 为 0 且窗型选择值为 2：减 0.10。
- 其余此路径：减 0.15。

8C8690 调 dst_as_wall，8C86D7..86F8 按 20B 追加 `[s, y, width, height, typeByte=0]`，前四项均 f32。这个描述确实是 center/full dimensions，由下文 finalize 证明；grow_one 的 Aabb2 命名是共享模板别名，不能用它提前认定布局。

另一数组由 8C8706/870E 条件控制。该 helper 8FF980 只有 4B，读取 `byte[rcx]`。上游 8C7889 与 8C78A1 可沿地址算到 `PublicWallState+29F`。其值非 0 才写切口。该地址有 `ActiveInputMode.is_controller` / `StairMaterial.is_wood` 等同址别名，既不能把本调用说成手柄条件，也未仅凭符号最终命名 +29F 的类型。

窗型经 8C7A06 做 `selector−1`，8C7A09 验证 unsigned 结果 <3；失败去 panic 分支。32B 记录由 8C8829..8856 写入：+0/+4 为 dst.s/y；+8/+C 是从 quaternion 旋转局部 +Z 推导后取 X/Z 的分量；+10..18 为此前计算/缓存的世界位置；+1C 为 shape；+1D 为 `dstTag>=2`。朝向式由 8C873D..8810 的平方、两倍乘积和 shuffle 推得，对单位 quaternion 相当于旋转 +Z；是否所有实际输入已正规化未动态验证。

**贯通例子**：输入 dst=(5,3)，rect width=1.2，rect Y 范围 [0,2]，destination tag=0，selector=1。CPU 写 `(5,3,1.15,2,type0)`，finalize 得 Aabb `[4.425,2]..[5.575,4]`。若 wall+29F=0，则没有这条 32B cut，但 CPU region 仍生成。

**切口例子**：wall+29F=1、selector=2、tag=0、quaternion=(0,0,0,1)、已计算 world position=(10,3,20)，则 cut 的 float 使用字段为 `(5,3,0,1,10,3,20)`，shape=1、flag=0。这是对参数的构造计算，不是游戏帧观测。

## 4. Gothic：三块 CPU 矩形近似，一个 GPU 形状记录

8C49AC 起，用三组局部轮廓数构成三个 20B regions，8C4A09..4A22、8C4A80..4A99、8C4AF7..4B10 各追加一次。每个 center=`(dst.s, dst.y+offsetY)`，dims=`(w,h)`，type=0。三组常量是：

| 原始常量分支 | 三个 `(offsetY,w,h)` |
|---|---|
| A，8C4902..491A | (0.23,1.508,2.35); (1.58,1.243,0.38); (1.83,0.813,0.34) |
| B，8C4949..4961 | (−0.098,1.168,1.7); (1.002,1.093,0.53); (1.352,0.613,0.3) |
| C，8C498D..49A5 | (−0.2875,0.6992,1.334); (0.5405,0.5888,0.4945); (0.9085,0.35995,0.345) |

这些为舍入十进制表示，实际 float bits 在 listings 的 RIP 常量中。分支条件在 8C48BD..48D9：栈+1B0 的 byte 为1选 C；否则栈+1A0 的 dword 为2选 B，为3选 A，否则至 panic。完整枚举名未恢复，因此不把这些分支直接冠以玩家 UI 中的某种名称。

其 GPU 写入从 8C4C28..4C52 发生；shape 在 8C4BCA/4BD1 为**栈+1B0 保存值加 2**。此前摘要将其泛称窗型，但这里最终记录保留精确来源，不能把它与 stack+1A0 的轮廓分支字段混为一值。

**贯通例子**：选 B，dst=(5,3)，CPU regions 为 `(5,2.902,1.168,1.7)`、`(5,4.002,1.093,0.53)`、`(5,4.352,0.613,0.3)`。转 min/max 后分别为 `[4.416,2.052]..[5.584,3.752]`、`[4.4535,3.737]..[5.5465,4.267]`、`[4.6935,4.202]..[5.3065,4.502]`。它们构成逐渐收窄的分段墙洞描述；不能因此断言 GPU SDF 恰好是这三块矩形并集。

## 5. 蓝图发布：每轮按墙汇集，两种存储各走自己的 API

`instantiate_blueprints` 8F4090（7,828B）在 8F43F0..45B0 扫当前 blueprint hashmap。8F46DB/8F473E 调 `DecoratorStorageAddr.try_as_wall` C413E0，条件失败走错误路径；得到 wall ID 后：

- 8F471C → `WallHoles.extend` 14FCF70，输入 Arc+E0 pointer、Arc+E8 length，end=start+20*length。
- 8F477E → `WindowCutRecords.extend` 14FD210，输入 Arc+128 pointer、Arc+130 length，end=start+32*length。

14FCF70 为 `Copied<Iter<tuple<WallSpaceRegion,HoleType>>>` 版本，按 wall ID 找/创建 WIP storage，调用 C2B5E0 add。14FD160 中 type==5 是 iterator 终止条件，未见跳过后继续。C2B5F2..B5FA 复制输入四 float 与 type，C2B604 → BBB520 对 raw bit-pattern 数组与 type 哈希；C2B609/B60D 把 hash 加到 sum、异或到 xor；C2B62D/B631 按 20B 原样保存。因此这个阶段无 min/max 转换。直接 API `WallHoles.add C2BB20` 不是普通窗当前发布链的调用。

8D35EA 的维护 wrapper tail-call `WallHoles.clear_for_next_frame C2B650`；8D35FC 对应 `WindowCutRecords.clear_for_next_frame A69BA0`。未完整恢复 ECS 调度次序，不能由这两个名字宣称任意帧时序已运行验证。

**构造例子**：墙 ID7 有两个窗蓝图，各有1个 CPU region、1个 GPU cut，则发布从两条蓝图分别 extend 到 wall7 的两种 WIP 存储。即使某窗视觉复用，其洞仍进入本轮汇集。GPU 资源在本报告的边界是 CPU `WindowCutRecords`；它尚不是最终 GPU 数组或 `WindowCutLists`。

## 6. CPU finalize：明确 center/dims→min/max，按周期边界补副本

`WallHoleStorage.finalize` C2B060（1,357B）比较当前/此前两对 u64 累积哈希，C2B129..139 相同走复用旧 finalized 分支。不同则开始转换。C2B1AF..1C7 读取20B输入的 `(centerX,centerY,width,height)`，C2B1D1 调 `Aabb2.from_center_dims DEEAD0`（97B）；非周期路径 C2B339 调同一 helper。

DEEAF7 乘 0.5，DEEB04 做 center−halfDims，DEEB07 做 center+halfDims，DEEB0D 写 16B：`[minX,minY,maxX,maxY]`。该 helper 没有取 abs 或独立验证 w/h 为正；它先计算 w²+h² 再与0比较，NaN 的 unordered 路径会到断言。不能据函数名增补更强的尺寸合法性保证。

finalize 的入参 xmm1 保留至 xmm6，记为 L；r8b 记为 wrap。原 bbox 存 type 和 origin=0（C2B200/205）。wrap 非0时，C2B212..C2B260 检查：

1. `minX<0`：bbox 两个 X 都加 L，append origin=1。
2. 否则 `maxX>L`：bbox 两个 X 都减 L，append origin=1。
3. 否则不补。

条件是严格不等；恰好碰边界不补。它是 if/else，超大 bbox 同时跨两端时此路径也只按第一个满足条件补一次；没有本体证据支持任意跨度平铺。入参 L 的上游来源和 wrap 全枚举未追，故这里将周期解释标为实际算术行为，没宣称恢复全部墙闭合判定。

n>=2 时调用排序（n<21 走 C2B4B9 insertion-sort，其他走 C2B4F6 stable driftsort）；本轮未恢复比较器。返回 byte 来源 C2B132，表示哈希对是否不同。相同哈希可能理论碰撞，因此不是逐记录一致性证明。

**贯通例子**：region=(0.2,3,1.2,2)，L=20、wrap=1。原 bbox=[−0.4,2]..[0.8,4]，origin0；因 minX<0 再产生 `[19.6,2]..[20.8,4]`，origin1。若 wrap=0，只有原 bbox。普通 region=(5,3,1.15,2) 位于周期内部，只生成一条。

## 7. 视觉 dirty 与洞汇集相互独立

8F4677 比较当前与旧条目 Arc 地址。相同跳 8F52CA 将 compareflag=0，然后返回 8F4689；仍先执行两种洞发布。后到 8F4A6B，flag 为0才跳下一蓝图。

Arc 不同则比较新旧 blueprint 的字段。CPU regions 长度在8F4B44/4B4B比较，逐元素在8F4B80..4BFA对四 float 做 `ucomiss`，`jne` 或 `jp` 都到重建；type byte 也需相等。GPU cuts 在8F4D47调用14FD4C0数组相等。其他 visual builders、storage ID、flags、collider 等还参与判断。失败到8F4E50，8F4E95移除 persistent visual entry，随后8F4F26向旧实体发出命令调用；本体未完整恢复全部命令语义，因此不以函数名替代其具体生命周期证明。

**构造例子**：同 Arc：洞重新汇集，视觉无需深比。不同 Arc，center 从5改为5.1：CPU region 比较失败到重建。+0 与−0在这里数值相等；NaN触发 unordered 分支并判变。不同 Arc 完全相同的 regions 可以通过该部分比较，但要复用视觉还需其他数组和字段也相等。

## 未做与风险

没有运行/附加/修改游戏，没有私人存档、动态帧、交互测试；没有系统安装或配置变更。玩家输入命中到 decorator mutation 的上游、完整 enum/unit/结构类型、+29F 的确切语义、finalize 周期参数 caller、排序/去重详情及全 ECS 顺序均仍未知。此报告给出发行程序的局部数据流与公式，不声称开发者意图，不交付可复制销售的恢复源码。主要风险是静态字段解释与同址 alias；已用实际参数地址、消费转换、指令 RVAs 和 raw bytes 区分，尚未确认的语义留作 unknown。
