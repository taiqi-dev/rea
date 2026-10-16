# 下一轮建议：优先补玩家效果、状态一致性与实际更新范围

本页前四项已按顺序开展下一轮静态研究，结果见[100：四款状态一致性与调色传播](100-four-static-state-consistency-and-palettes.md)。各专题保留明确Partial／Unknown；下文是当时的选题依据，不作为研究完成或运行验证的回执。

以下是**研究建议，不是本轮已经确认的游戏机制**。排序依据是现有发行证据里是否有明确入口、问题能否回答自研建模／美术／性能设计，以及是否能用一个有边界的专题取得新结论。本轮结果见[98](98-four-static-alias-interface-and-defaults.md)。没有因为提出建议而启动游戏、读取私人存档或实施自研代码。

## 建议顺序与第一片范围

| 顺序  | 建议专题                                              | 已定位入口                                                                                                                                                                                                                                        | 第一片只回答什么                                                                                         | 可交付结果与限制                                                                                       |
| ----- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **1** | **沙堡：GPU读回快照到碰撞的时效与背压**               | [07](sandcastle/07-local-updates-readback-and-costs.md)的Readback.Draw、`Readback.<Draw>b__11_0`、Ground.UpdateColliders、PlaneChunk.UpdateMeshCollider                                                                                           | 上一次请求未完成时是否还会发新请求；失败／迟到结果能否覆盖新快照；四块碰撞轮换究竟消费哪个版本           | 请求创建→完成→缓存→碰撞消费的状态图、在途上限和年龄公式。实际延迟/FPS仍需运行，静态只能给条件界限。    |
| **2** | **掘地求财：坏档解压失败是否会先清空当前体素世界**    | [保存研究](digging-a-hole/02-save-load-and-consistency.md)；`AVoxelWorld::LoadFromCompressedSave 0x1441A3D20`、DecompressVoxelSave、`FVoxelData::LoadFromSave 0x143E8268E`                                                                        | 对压缩数据失败、版本不符、空保存三种入口，核对返回值怎样传播，以及清空／替换旧数据发生在成功之前还是之后 | 精确成功／失败分支和现有世界保留条件。构造参数只做静态演算，不打开玩家保存或宣称已做故障运行。         |
| **3** | **Tiny Glade：撤销／读档后的程序化细节能否稳定重建**  | [62](62-tiny-glade-history-snapshots-and-regeneration.md)的快照恢复、带ID创建`0x140B0E300`、回放修改到[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)的dirty发布，以及[61](61-tiny-glade-tree-mesh-processing-and-publication.md)的实例发布 | 先选一种对象和一个回放分支，追逻辑ID、随机seed和重建输入是否沿原身份恢复；不一次追所有墙／屋顶／树木     | 保存权威与派生网格的对应、重建时seed／ID输入及未知项。GPU槽位和画面逐像素一致性仍不由静态链保证。      |
| **4** | **SUMMERHOUSE：晴／雨／夜调色板到共享材质和环境参数** | [03](summerhouse/03-save-palette-and-visuals.md)的ColorPalette.ApplyMaterialColors `0x060000DD`；[05](summerhouse/05-materials-pixelization-and-camera.md)已定位`sharedassets1.assets`内Lake Sun/Rain/Night三套palette                            | 先完整读一套palette的材质／颜色引用，再比较另外两套，接到_BaseColor、_EmissionColor、雾和环境光写端      | 参数对照表、共享材质影响范围和切换的局部／全局边界。参数不等于最终像素，后处理和真实场景激活仍需另证。 |

第一项最贴近“挖完以后画面和碰撞多久一致、是否堆积后台请求”；第二项直接关系保存恢复是否保护已有世界；第三项关乎程序化美术在撤销／重载时是否稳定；第四项能解释少量共享参数怎样形成整场景的美术差异。这是我的优先级判断，不表示原作存在延迟、坏档或随机变化故障。

## 后续第二梯队

- **沙堡湿沙与薄水层的连续过渡。** [06](sandcastle/06-surface-materials-and-effects.md)已核湿沙权重和可见水层的不同阈值，[08](sandcastle/08-material-bindings-render-state-and-invalidation.md)有真实材质绑定。下一片可补真实场景参数／shader变体到这些阈值，区分湿边、极薄积水、可见水面；不要再由一个公式直接推最终画面。
- **Tiny Glade快照的写盘完成与失败收据。** [62](62-tiny-glade-history-snapshots-and-regeneration.md)中`ShadowFile.mark_dirty`、`save_game 0x140B81310`、AsyncSaveCmd队列与pending对象已定位；后续可只追线程消费→flush/sync或替换→pending成功／错误channel，回答请求被接受和数据完成保存之间的界线。
- **掘地求财重复挖掘的任务令牌。** [05](digging-a-hole/05-task-lifetimes-growth-and-performance.md)相关 `ProcessMeshUpdates 0x143EED1F0`、`CheckPendingUpdates 0x143ED3770` 有入口，但task+0x68及待处理首字段的确切生产语义仍待连接。先追一个令牌从创建到接受／拒绝，才能进一步讨论旧结果过滤或队列增长，不能凭字段样子命名“时间戳”。

公开技术背景仅作选题参考：Epic的[保存说明](https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine)将SaveGame对象准备、写入请求和完成回调分别描述，异步完成回调携带成功／失败值。这支持把这些阶段分开调查；所读页面为UE5.8文档，本作精确引擎补丁未固定，不能据此替代本机二进制或保证断电原子性。普通来源记录为本轮raw的`public-recommendation-reference.json`，没有计算摘要。

## 两个悬案如何继续才有信息增益

**Tiny Glade槽23**保留[96](96-tiny-glade-mutable-alias-and-raw-handle.md)的三个明确触发入口：新可变别名消费者／首qword store；raw记录+0x320的实际重绑定；槽23消费到设备接口的范围解释。没有新的地址、数据流或不同制品时，不建议重复相同Any、TypeId、PDB名字和RIP引用扫描。它仍是Unknown，不因降低重复调查优先级而被当成已解决。

**沙堡末尾3**保留[19](sandcastle/19-reference-interface-targets-and-tail.md)的动态接收者身份、其它接口实例，以及构建writer／同次构建未剥离类型树等决定性输入。新的引用映射实现不能给构建尾字段命名；继续只搜索值3或沿同一消费reader重复推长度，信息增益很小。

以后若单独安排运行验证，最有判别力的是局部编辑到碰撞的快照年龄、保存失败后的旧世界是否保留、撤销／重载的稳定外观，以及同镜头的调色切换。它们继续留在[运行用例](74-runtime-validation-cases.md)范围，**本轮均Not Run**。静态研究能收紧执行条件，真实像素、帧时、显存峰值与失败时序仍须独立证据。
