# Tiny Glade：木框退出、成品生成与发布条件

后续 [136](136-tiny-glade-entity-upload-and-frame-publication.md) 已补具体 executor、末尾 deferred 开关及 App.update → render → 维护/图执行的正常路径；[135](135-tiny-glade-menu-tool-exit-and-timber-cleanup.md) 补所属木板槽的清理和 flush。最终 schedule 图、所有资源版本与首帧呈现仍未证明，下文统计保持本轮范围。

2026-10-22，Pacific Time。续接 [131](131-tiny-glade-placement-lifecycle-and-animation-handoff.md)，输入链见 [133](133-tiny-glade-confirm-cancel-input-mapping.md)。仍仅做静态文件分析。

**本轮从“有阶段名”推进到了“主程序实际注册 45 个有序阶段”，并把矩形 UI、矩形创建、屋顶创建、尖顶组装和屋瓦 flush 的注册连接补上。** 正式逻辑、ECS 实体、CPU 实例内容和 GPU 资源各有发布门槛。现有证据仍不足以把这一整套处理叫作木框与成品的原子替换，或保证确认后固定第几帧出现。

## 主程序确实配置了阶段依赖

`tiny_glade::run_game::run_game_thread` 的 `0x140654EF3` 实际调用 `StagesUtil.add_stages` (`0x14093E620`)；不能仅凭初始化函数存在就当作已使用。后者在 `0x14093E74D` 以枚举值 0 开始，经 `0x14093E74F` 调带类型的 `Vec.from_iter<Map<enum_iterator::All<GameSystemSet>,...>>`，再在 `0x14093E7A5` 把这些配置交给 `SubApp.configure_sets<Update,...>`。

迭代器 `0x1415EB150` 在 `0x1415EB179` 比较上界 `0x2D`，`0x1415EB30C–0x1415EB30E` 逐个加一并再检查。阶段名由 `GameSystemSet.Debug.fmt` (`0x140FE4230`) 的长度表 `0x14326E848` 和相对地址表 `0x14326E9B0` 解出，完整 45 项由证据 reader 核对。

更关键的是排序配置。`add_stages` 传入组配置的 chain 元数据来自 `0x143333D50`；它与普通 `IntoScheduleConfigs.chain` 经 `Chain.set_chained` (`0x140F23D60`) 写入的 `0x143400670`，都表现为非零空 map 控制指针、其余三个 qword 为零，所指控制区 16 B 全为 `FF`。对照该 setter 的“当前未串联才写入”分支，可确认这里是普通 **Chained(empty map)**，不是只列出一组无依赖的集合。

发行包 `build-info/Cargo.lock` 标明 `bevy_ecs 0.17.3`。官方同版本源码区分普通 `chain` 与附带 `IgnoreDeferred` 配置的 `chain_ignore_deferred`，并定义上述组与 chain 结构；这是解释二进制布局的库资料，不能替代本地注册证据。[Bevy 0.17.3 config.rs](https://raw.githubusercontent.com/bevyengine/bevy/v0.17.3/crates/bevy_ecs/src/schedule/config.rs)、[schedule.rs](https://raw.githubusercontent.com/bevyengine/bevy/v0.17.3/crates/bevy_ecs/src/schedule/schedule.rs)。

## 与木框交接有关的阶段及实际系统

下面是同一 Update 的相关有序子序列；中间省略的阶段仍在完整 45 项中，数字不是帧数。

| raw     | 阶段                                                                             | 本轮定位到的注册或实际处理                                                                                                |
| ------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `03–05` | InputReset → InputGather → InputTranslate                                        | 输入阶段名；translate 和状态转换的实际调用见 133；此表不自行断言所有后端在同一处采集                                      |
| `06–08` | ImuiUpdate → RmuiUpdate → UiClientLogic                                          | `add_ui` 的所选配置实际写 raw6 并入组；菜单生产者的完整入组关系未穷尽                                                     |
| `11`    | WallShapeUx                                                                      | `add_wall_shape_ux` 的 `0x140947109` 写 raw17，随后 intern、in_set、add_systems；矩形 UI 和矩形创建消费者均在其嵌套配置中 |
| `12–14` | RoofUiSystems → WallGenerators → RoofSystems                                     | 墙模块在 `0x1400CF885` 写 raw19；屋顶模块在 `0x1406C3230` 写 raw20；屋顶创建消费者接入后者的嵌套配置                      |
| `15–1A` | RoofDeleteEntities、WallRoofHashmap、IntersectWalls、两段支撑与 DecoratorSystems | 处于屋顶系统与木框之间；这里不为每个对象保证所有系统都实际运行                                                            |
| `1B`    | Timberframe                                                                      | `add_timberframe` 在 `0x1406C44AE` 组内 chain_ignore_deferred，`0x1406C44B3` 写 raw27，最终 add_systems                   |
| `1C`    | WallVisualGenerators                                                             | 墙模块 `0x1400CF9E2` 写 raw28；位于木框之后                                                                               |
| `1D`    | RoofAssemble                                                                     | `0x1406C32DD–0x1406C32DF` 将屋顶组装 tuple 入 raw29；其中接到尖顶实例消费者                                               |
| `22–23` | HistoryDeferredRecord → HistoryEnd                                               | 处于生成和组装之后；并不意味着此前所有 GPU 工作已经完成                                                                   |
| `2C`    | PrepareRendering                                                                 | 屋顶 `0x1406C3345–0x1406C3347` 将屋瓦池 flush 系统入 raw44；绘制图、GPU 执行和呈现仍有外层边界                            |

值得修正一个容易产生的误解：**矩形创建逻辑本身在 WallShapeUx 的嵌套配置里，不必等到名为 WallGenerators 的阶段才创建逻辑墙。** 不能按阶段名字替代具体系统的注册证据。

注册到实际消费者的五条连接如下。偏移 `+0x48` 是本轮实际检查的 System vtable `run_unsafe` 槽，不能套用于其他 trait 对象：

| 注册位置 → vtable                                   | run_unsafe → 实际调用                                                             |
| --------------------------------------------------- | --------------------------------------------------------------------------------- |
| 形状嵌套配置 `0x1417E6912` → `0x143048F78`          | `0x140AA8370`，在 `0x140AA9080` 调 `ui_create_rectangle`                          |
| 同组 `0x1417E69B0` → `0x143381AF8`                  | `0x141A73D80`，在 `0x141A74986` 调 `create_rectangle`                             |
| 屋顶 core 配置 `0x140FD526C` → `0x14342CCD0`        | `0x141F37C40`，在 `0x141F37F1F` 调 `create_roof`                                  |
| RoofAssemble 配置 `0x140FDEE73` → `0x143429620`     | `0x141F0FBE0`，在已核 `0x141F0FD41` 调 `place_spires`                             |
| PrepareRendering 配置 `0x140FE0CEE` → `0x14326DDC0` | `0x140FE08E0`，在 `0x140FE09F0` 调 `SparseInstanceBuffer.gpu_flush<RoofTileSsbo>` |

矩形两项来自 `0x1417E6370` 的嵌套配置，该 helper 由形状注册的 `0x14094702C` 调用；屋顶创建来自 `0x140FD5120`，由屋顶注册的 `0x1406C31AC` 调用。这里以实际 E8、RIP lea、vtable 内容和带类型 wrapper 联合定位，没有只凭被截断的超长泛型名称判定消费者。

## 木框退出不等于原地换一个模型

[131](131-tiny-glade-placement-lifecycle-and-animation-handoff.md) 已核：`construct_timberframe_rectangle` 每次实际进入，在 `0x141F4F284` 先清本消费者拥有的实例分配，再读取未消费 `ConstructTimberframeCmd` 并按载荷筛选、追加木板。现在可以把它放回 **Timberframe** 阶段，而不再只知道函数存在。

确认矩形的所选路径在 `0x140ADD67A` 发创建命令，后续音效后跳回公共收尾 `0x140ADCF19`；它不等价于“销毁一个预览 GameObject 并替换成成品”。模式退出路径则清 Preview、返回，不再由该 UI 产生本次木框消息。

因此可得的条件性结论是：**该木框消费者正常运行、没有本次可生成的候选消息时，清理路径会使它拥有的旧分配不再由本次处理重建。** 但不能进一步推出：

- 其他生产者没有发出候选消息，或此前排入的消息已全部失效；本轮没有找到通用“取消时清空整个木框消息队列”的保证。
- 成品实例准备失败时木框会自动保留。所选木框清理条件未见等待“成品已可绘制”的握手。
- 连续建造时之后的木框仍是刚才那一个候选；下一更新可能已经为下一个候选供给消息。
- 所有门禁、工具切换和历史打断都会在固定一次 Update 内清理。

所以可以解释“预览与成品由不同系统接管”，尚不能证明无论何种失败和打断都不会闪空。

## 三种发布边界

**逻辑边界。** 矩形消费者创建曲线并调用 `InnerWalls.new_wall`、设置属性和记录历史，见 131；墙状态修改、dirty 与带类型墙/屋顶消息沿既有 [50](50-tiny-glade-roof-edit-messages-and-regeneration.md) 和 [55](55-tiny-glade-edit-rebuild-stages-and-upload.md) 的链继续传播。消息写入不等于 ECS Commands 已应用，也不等于网格和实例已准备。

**ECS 边界。** `create_roof` 使用 deferred Commands 产生屋顶实体，动画两路初值为零；随后 query 必须在实体可见后才消费它。全局阶段使用普通 chain，局部多个 tuple 使用 chain_ignore_deferred，另有屋顶嵌套普通 chain。官方 0.17.3 默认开启自动插入 ApplyDeferred；其含义是在满足依赖和 deferred 条件时构建同步点，**不是每过一个阶段都无条件刷新**。本轮没有恢复最终构建的 schedule graph、所有 run_if 和所有 build-settings 写端，因此“此处同一更新一定已有屋顶实体”仍只能带条件解释。[同版本 ScheduleBuildSettings 与 Chain 定义](https://raw.githubusercontent.com/bevyengine/bevy/v0.17.3/crates/bevy_ecs/src/schedule/schedule.rs)。

**实例与 GPU 边界。** 尖顶在 RoofAssemble 的 `place_spires` 路径收集 RoofAnimation 的第二路进度，写 32 B 记录并在 `0x142801DFA` 调其普通 SSBO 更新；这条字段链见 131。屋瓦则是另一条稀疏池链，本轮把它的 `gpu_flush<RoofTileSsbo>` 明确放到 PrepareRendering。两者不能混成同一个提交函数。

屋瓦 flush 的容量成功门继续沿用 [112](112-tiny-glade-external-pool-producers-and-draw-bindings.md)：CPU 页已增长时，只有创建 GPU buffer 的结果 tag 为 `0x0B` 才替换 raw handle 并发布 `pool+0x50`；失败绕过这两次写入。内容上传按脏区间与页边界切分。外层维护再将容量同步到 GpuWorld，后续 cull、draw-list、图资源和绘制绑定使用它。**PrepareRendering 中执行过 flush 仍不代表 GPU 已完成、图已经采用新版本或屏幕已显示。** 外层维护与 Update、图导入和 present 的完整相对顺序仍未由本轮证明。

## 对综合 demo 的独立建议

可借鉴的核心是把工作拆成有依赖的阶段，使候选只消耗活动对象预算，正式建筑由既有世界、dirty 和实例池接管。实现中继续使用自己的几何和正式命令，避免另建一套施工世界或历史。

若产品要求“确认后绝不闪空”，应在自己的现有发布入口增加明确条件：正式命令已成功、结果代次仍有效、必要几何与实例可发布，才让对应候选退场；取消与撤销使旧代次失效，迟到结果不能接管。这个握手是独立建议，**不是已证明 Tiny Glade 有同样的协议**。动画只改变显示，不能用动画到 1 冒充玩法或存档提交成功。

静态算例：候选 P7 已确认并得到有效逻辑建筑 B3，网格任务 R8 尚未准备，此时保留 P7 的轻量显示；R8 准备且仍属于 B3 当前代次才接管。若期间撤销 B3，R8 即使完成也不发布，P7 按取消规则退出。GPU 分配失败应给出明确失败状态并保持可解释的旧显示，而不是发布新容量后才发现资源不存在。这是设计推演，不是游戏运行结果。

## 本轮证据与收口状态

制品身份、工具与授权沿用 [133](133-tiny-glade-confirm-cancel-input-mapping.md)。新证据 reader 同时核对 18 个直接调用、16 个锚点、5 条 vtable 连接与完整阶段名。关键原始文件保留于 `.cache/procedural-modeling/tiny-placement-input/`：`add-stages`、`set-iterator`、`set-chained`、各 `register-*`、嵌套 group、consumer wrapper 与 `verified-input-schedule.json`。公开库源码只是版本匹配的解释资料，不是目标的恢复生产代码。

| 问题                                                 | 状态                                                                         |
| ---------------------------------------------------- | ---------------------------------------------------------------------------- |
| 全局阶段是否只是命名列表                             | **已补**：主程序调用、45 项配置与普通 chain 元数据共同证实有序依赖           |
| 矩形逻辑、屋顶创建、尖顶与屋瓦 flush 在哪里注册      | **已补选定路径**：五条注册到实际消费者的连接                                 |
| 木框停止供给后如何释放                               | **已补条件链**：进入消费者先清本分配，再按本次消息重建；未证明等待成品的握手 |
| 最终 deferred 同步点与全部运行条件                   | **Unknown**：未恢复最终构建图，不能把库默认冒充最终运行图                    |
| flush、外层容量维护、图导入和首次 present 的完整顺序 | **Unknown**                                                                  |
| 完整设备交互、确认取消竞合和逐帧无缝显示             | **Not Run**                                                                  |
