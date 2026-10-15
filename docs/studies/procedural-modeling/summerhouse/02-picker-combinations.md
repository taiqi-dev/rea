# 构件候选、相对位置组合与奖励

本篇依据[固定程序集与工具边界](00-evidence-and-scope.md)。REA 成员 Evidence 为 `ev_dbf130a1797c92e37522986abf7c5c20d073a126086d567887d76411e92c7ddf`（Picker/Placer）和 `ev_54b382ffc96c6759d706f9d8a92e4a47dfef51824cb2864da333334241793076`（Combination/Requirement）。这种邻接是**预制块 ID 加二维相对位置**的模式匹配；不能由它推断连续几何接缝自动长出新的窗、瓦或墙皮。

## 下一块如何来

`BuildingBlockPicker` (`0x02000011`) 保存块集合、忽略集合、解锁集合、普通/标签筛选抽取队列、上次选择、随机顺序开关与有限块集合。`GetNextBuildingBlock` (`0x0600007F`, `IL_0014..00D1`) 按三种 `SelectMethod`：普通袋队列、按标签筛选的袋队列、指定单块。队列耗尽会重建再出队；指定块未设置或方法值非法会记录错误并返回 null。普通/筛选出队若取到锁定块会继续尝试，循环上限为 1000；上限后的返回值仍取决于最后候选，因此不能把该守卫解释为绝对“永不返回锁块”。

`ResetDrawQueue` (`0x06000082`, `IL_0000..00A3`) 从候选中移除 `ignoredBlocks`，然后按 `randomOrder` 随机抽取到队列，或保留现有顺序；`EnsureNoMoreThanTwoOccurrences` (`0x06000083`, `IL_0000..006F`) 用计数字典只把每个块的前两次出现重新入队。`ResetFilterByTagDraw` (`0x06000081`, `IL_00A4..0178`) 按 `categoryTags.Contains(filterTag)` 且未忽略组候选，还维护按标签的队列。`priorityInPicker` 字段参与该路径的降序排序（lambda `0x06000341`）；[资源补证](04-packaged-blocks-and-combinations.md) 已读取 `sharedassets0.assets` 中块的序列化优先级，但未解析各场景实际候选袋，不能给出游戏真实分布概率。

**构造演算，非实际候选清单。** 若普通候选按顺序为 `[A,B,A,A,C]`，忽略集合为空且随机顺序关闭，计数上限处理后队列为 `[A,B,A,C]`；连续两次取块返回 A、B。若 A 在第一次出队时仍锁定，方法继续取 B；这不表明真实游戏中 A、B、C 是哪些资产。队列的重建和解锁状态会改变后续序列。

## 如何判定相邻组合

`BlockCombination` (`0x0200000A`) 包含多个 `Requirement`，每个需求有 `blockPrefab`、`relativePosition` 与 `replaceThisOnSuccess`，组合还有 `blockToUnlock` 和 `hasBeenUnlocked`。`BuildingBlockPlacer::PlaceBlock` 在实例加入 `allPlacedBlocks` 后调用 `CombinationManager::OnBlockPlaced` (`0x060000A6`, `IL_0146..0163`)。管理器先跳过按当前状态不应再触发的组合；命中后调用 `CombinationSatisfied`，可选 `maxOneCombo` 让一次放置最多处理一个匹配（`0x060000F6`, `IL_000E..009D`）。

`CombinationSatisfied` (`0x060000F7`, `IL_0034..0215`) 先找与刚放置块 `saveID` 相同的需求作为锚候选；对每个锚，把另一需求的相对格点减锚相对格点，叠加本次放置的二维格点，得到目标格点。它遍历 `allPlacedBlocks`，把每个实例的世界位置吸附到整数格点，再同时比较格点和 `saveID`；每个需求都找到才通过。重复 `saveID` 可以作为不同锚候选；已匹配 GameObject 被 `blocksInCombo` 记录，避免同一对象重复加入结果。当前已读分支没有旋转或任意尺度归一化；相对位置按定义原样平移。

**构造演算，非发行组合配置。** 假定一个定义要求 A (`saveID=12`) 位于相对 `(0,0)`，B (`saveID=21`) 位于相对 `(1,0)`。玩家刚把 A 放在 `(10,4)`，已有 B 在 `(11,4)`：锚 A 使目标 B 为 `(10,4)+(1,0)-(0,0)=(11,4)`，两处 ID 与格点均对，组合成立。若 B 在 `(10,5)`，本定义失败；定义中另有朝上的镜像/旋转版本才可能匹配，当前算例没有这种配置证据。[第 4 篇](04-packaged-blocks-and-combinations.md)另给出了发行资源中的一条真实配方，并与同一算法贯通。

## 组合后发生什么

`OnCombinationSatisfied` (`0x060000F8`, `IL_0000..0107`) 播放奖励粒子、震动和声音，标记组合已解锁；若配置了仍锁定的 `blockToUnlock`，调用 Picker 解锁并保存进度。若某需求标记 `replaceThisOnSuccess` 且有 `blockToUnlock`，它通过 `FindBlockToReplace` 选中一个已参与的实例，再调用 `BuildingBlockPlacer::ReplaceBlock`。后者先核对两个块非空且待替换块确实存在于 `allPlacedBlocks`；随后保留旧世界位置和翻转状态，移除/销毁旧对象，在原位置实例化奖励块并登记撤销（`0x060000A7`, `IL_0000..00DB`）。这给出了“拼出特定小组合后出现另一构件”的静态路径；[资源补证](04-packaged-blocks-and-combinations.md)已取得该文件的 123 条组合配置，但替换前后图像、其它资源和隐藏内容仍需运行观察。

对上例再作构造延伸：若奖励是 C，且 A 的需求有 `replaceThisOnSuccess=true`，成立后可将 A 原位换成 C，B 仍留在场景；这只是该分支规则示意。[第 4 篇](04-packaged-blocks-and-combinations.md)提供发行版中一条另有具体 ID 的配方。
