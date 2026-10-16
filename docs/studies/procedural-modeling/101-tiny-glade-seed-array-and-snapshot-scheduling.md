# Tiny Glade：普通砖 seed 数组生产与快照后的重建候选

本篇续查[99：墙身份和底 seed](99-tiny-glade-wall-identity-and-stable-rebuild.md)留下的两个缺口：`PublicWallState+0x48` 的数组由谁产生，以及快照恢复的墙怎样成为公共墙与普通砖的重建候选。历史/快照格式见[62](62-tiny-glade-history-snapshots-and-regeneration.md)，区域候选见[45](45-tiny-glade-shared-invalidation-and-rebuild.md)，静态阶段图的边界见[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)。

## 身份和证据

目标仍是 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B）及相邻 `tiny_glade.pdb`（310,513,664 B）；沿用已核 PE/PDB RSDS GUID `d8d61d04-9e31-5b47-4c4c-44205044422e`、age 1，本轮没有重算摘要。下文地址是 RVA，首选 VA = RVA + `0x140000000`。符号由本仓 `digging-a-hole/tools/pdb_probe.py` 读取本地 PDB；指令由现有 VS 2022 `dumpbin 14.44.35222.0` 对 PE `.text` 按 VA 范围只读取得。新查询与原始指令位于本机忽略目录 `.cache/procedural-modeling/static-lifecycle-followup/tiny-glade/`，旧清理与 seed 片段位于 `.cache/procedural-modeling/static-state-followup/tiny-glade/`。这些是**普通 PDB/PE 静态证据，不是 REA Evidence，也不是游戏运行观察**。REA native Ghidra 先前 timeout 状态未变，未重试。

## `+0x48` 是重采样曲线的点数

本轮直接E8候选使用[只读调用探针](tiny-glade/tools/pe_direct_call_probe.py)，仅扫描选定PE的`.text`范围，并要求PE／节表落在其4KiB头窗口内；输出拒绝覆盖。候选经指令边界和目标反汇编核准后才用于下文调用边，扫描不覆盖间接／内联调用。

`B9F450 publish_public_wall_state` 为选中的墙重算 Public 状态时，在 `BA1058–BA10C9` 组装一个曲线输入，并在 `BA10CD` 调用 `Curve::crashy_resample_remap_per_segment_2`（`19AC6D0`），输出到局部 `rbp+268h`。在这一调用点，`xmm3` 来自 `xmm14=0.5f`（`BA05C0`）；`r8b` 来自墙记录的一个模式字段是否为 1（`BA1092–BA109F`）。该函数先读输入曲线节点数：不大于 1、采样间距为 0 等分支会 panic，不能用正常采样公式覆盖这些输入（`19AC730–19AC75C`）。

正常分支先按输入节点数分配每元素 12B 的输出容量（`19AC762–19AC7AF`），写首个三维点（`19AC7CD–19AC851`）。每段按两个二维端点的距离算一个细分数：`19AC8EA–19AC930` 计算距离、用 0.5f 间距形成比例并调用 `roundf`；`19AC930–19AC97A` 做非负/上限转换、加一和至少 2 的限制，随后 `19AC97A–19AC97D` 还把上述模式位 OR 进这个数。`19AC9C0–19AC9DD` 与 `19ACA28–19ACAA5` 对段内插点做二维插值、地形高度采样、三维点写入并增长长度；容量满时增长。于是长度会受**输入曲线的节点/段距离、0.5f 采样间距、模式位及有效分支**影响；地形采样值参与点坐标，但现有指令不能单凭高度值推出长度改变。源曲线如何由所有编辑输入形成，仍以[53](53-tiny-glade-wall-footprint-input-and-curves.md)的边界为准。

成功后，`crashy_resample_remap_per_segment_2` 调用 `Curve::try_new_from_points`（`19AA3F0`），其成功支在 `19AA59A–19AA5E1` 将原 12B 点 Vec 的容量、指针、长度移入返回 Curve 的前三个 qword；失败支另行释放/标错，不算正常输出。`BA10CD` 的返回 Curve 到 `rbp+268h`，`BA1E5B–BA1E7F` 把前 `0x38` B 搬入新 Public state 的 `+0x38` 起始位置；`BA2275–BA22AD` 将完整新 state 复制并插入 Public map。结合[99](99-tiny-glade-wall-identity-and-stable-rebuild.md)旧值清理时以 12B 元素释放 `+0x38/+0x40`，此处可确认参与 seed 的 `+0x48` 正是这条重采样三维曲线的**点数组长度**。邻近 `BA1168` 的另一个 `Vec::from_iter`（`15EB960`）逐个调用地形高度采样、产出 4B `f32` 数组；它不是这个 12B seed 数组。

### 一个构造过程

以下是按指令分支构造的算例，未运行游戏。假设一面墙的输入曲线只有两个二维节点，相距 1 个世界单位，模式位为 0，其余成功资格均满足。间距为 0.5 时，细分计算为 `round(1/0.5)+1 = 3`；首点先写入，单段再写两个点，故新 Public 曲线长 3。若 WallId 为 7，则普通砖底 seed 的所选输入是 `7 × 0x4B28021 + 3 = 551,649,514`（`8096CC–8096DA`）。若相同 ID 的曲线段改为 1.5 单位且模式位仍为 0，细分结果为 `round(1.5/0.5)+1 = 4`，数组长 4，底 seed 增加 1。若模式位为 1，这一段的数还经过按位 OR；例如 4 OR 1 得 5。算例只解释所选正常分支，不能代替其它几何、洞口、材质或最终像素验证。

## 快照使用创建候选集合，随后以消息进入普通砖

快照入口 `1BF3100 init_game_state_from_snapshot` 在 `1BF3572` 调用 `B0DA60 InnerWalls.load_state`。后者对非空 120B `(WallId,WallState)` 记录逐项取原 ID，`B0DB20–B0DB30` 插入新 ID map，`B0DB51–B0DB98` 将其写入 `InnerWalls+0x30`；主 WallState map 与最大 ID counter 也被恢复，见[62](62-tiny-glade-history-snapshots-and-regeneration.md)。这一路没有通过编辑函数写 `InnerWalls+0x60`。

公共墙函数随后在 `BA0523–BA0549` 同时读取 `InnerWalls+0x30` 与 `+0x60` 两组键；`BA061A–BA0675` 分别遍历两组候选，`BA06D6–BA08D0` 按 WallId 查当前主 map 再做资格判断。选中时 `BA0925–BA094E` 写 `OnWallChanged`，之后才移除旧 Public state 并计算新值。处理后 `BA2305–BA2399` 将这两组集合的控制字节置空并清长度。由同一对象布局和字段写/读/清，可复核一条**快照 ID → `+0x30` 创建候选 → Public 重算**的资源边；`+0x60` 是另一条编辑 dirty 来源，快照本身不必伪装成编辑。

普通砖消费者 `808800 construct_walls` 在 `808C02` 实际调用 `FC81A0`。匹配 PDB 专门类型明确是把 `MessageIterator<...OnWallChanged>` 映射为 `WallId` Vec；后续 `808D05` 按候选 ID 调用 `PublicWalls.get`，只有存在的墙才进入下一轮，更多墙洞资格见[99](99-tiny-glade-wall-identity-and-stable-rebuild.md)。这给出**Public 发布消息 → 普通砖候选**的具体类型/调用边，而不是从阶段名称猜测的连线。

`1BF3100` 的唯一所见直接 `E8` 调用候选在 `19274FA`，指令复核确为调用。Public 发布与普通砖构造各有独立系统包装调用处（`1E440C/5C2B57` 与 `1C4830/67BDB9`）；这里没有证实快照函数直接同步调用它们。上述资源和消息边说明恢复后的下一次相应系统执行**能够**处理这些 ID，仍须满足系统实际运行条件、Public 资格和后续显示流程。阶段图只给约束，不证明同帧运行、deferred 可见性、GPU 提交或所有快照墙均通过筛选。

## 稳定性和未答项

快照保留 WallId，只固定底 seed 的一项。若恢复后曲线重采样得到相同点数，且 ID 相同，所选底 seed 相同；点数受上述曲线与模式输入控制，故“同 ID”不能保证 seed 数组长度或其点坐标相同。即使底 seed 相同，普通砖还受其它几何/行输入与清旧重建路径影响，[99](99-tiny-glade-wall-identity-and-stable-rebuild.md)的局部确定性边界继续适用。

已答：12B 数组的生产者、成功移入地址、长度的主要分支；快照创建键通过 `+0x30` 被公共墙生产者消费，Public 消息再由普通砖构造器的专门迭代器消费。部分回答：快照装载后系统何时运行、同次更新的阶段/deferred 屏障、所有候选的资格结果。未答：不同历史方向的完整调度、跨版本/浮点等价、GPU 物理槽位和画面像素。没有启动或附加目标、执行目标函数/GPU、读私人存档、安装工具或运行项目构建测试。
