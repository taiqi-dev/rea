# Tiny Glade 一次建筑编辑：状态提交、阶段图与实例上传

本轮补上两类证据：墙组移动实际提交WallState并标记WallID；全局GameSystemSet配置实际在阶段图中连边，能够解释生成职责的先后约束。再追到普通墙实例的清旧、64B写入和typed GPU范围写入口。完整“带窗建筑移动后同一帧显示”的时间线仍未恢复，尤其窗口全部通知、run条件、deferred屏障和GPU完成。

轮廓输入见[53](53-tiny-glade-wall-footprint-input-and-curves.md)，装饰放置见[54](54-tiny-glade-edit-picking-and-wall-placement.md)，屋顶消息见[50](50-tiny-glade-roof-edit-messages-and-regeneration.md)，共享栅格发布见[45](45-tiny-glade-shared-invalidation-and-rebuild.md)。身份、范围和验证见[58](58-tiny-glade-input-edit-and-natural-shapes-ledger.md)。

## 1. 墙组移动提交的是语义状态

`B47F40 WallGroupTransformCache.apply`按组成员和目标状态向前配对，记录步长分别为200B、112B。它对成员相关二维值应用缓存的变换，追加一条48B消息记录，随后在`B48246`实际调用`92F410 InnerWalls._try_update_state`提交该WallID的新状态。

消息队列的ID/长度增加与状态提交都是指令事实；其所有接收者与消息原因原名未恢复，不能把这条48B记录直接改名成OnWallChanged。后者来自公共墙生产者，是不同阶段的消息。

`92F410`按WallID查内部状态。成功路径：

1. `92F5CE–92F5DD`对InnerWalls的`+60`集合调用`3B05D0 HashMap.insert<WallId,()>`，记录变更键。
2. 释放旧状态所拥有的两份动态数组。
3. 从传入目标转移新状态字段。

该集合用WallID作为键，重复插入同一键不会产生两个不同键。找不到WallID时不进入替换路径，另有受日志级别控制的诊断分支及传入状态资源清理；不能把缺失对象当成新建。

已有墙绘制修改的`92E8E0`也有dirty入列/曲线替换，见[53](53-tiny-glade-wall-footprint-input-and-curves.md)。两路输入不同，最终都需要公共墙和显示产物进一步派生。

## 2. 公共墙变化消息是派生后的通知

沿用同身份`B9F450 publish_public_wall_state`的完整范围。之前已核对`BA0925–BA094E`追加OnWallChanged，随后才在同一函数内移除/重算选定旧PublicWall。消息记录已被写出，不意味着消费者能在这一函数中途执行。

屋顶消费者的真实typed桥已在[50](50-tiny-glade-roof-edit-messages-and-regeneration.md)建立：OnWallChanged→当前关联Roof→RecalculateRoofCmd→per-roof清旧和重新铺排。普通窗的粗洞/精细cut和蓝图变更有自己的发布、比较与finalize路径，见[16](16-tiny-glade-window-placement-and-holes.md)。本轮没有将它们都缩成一条相同dirty树。

不同层次应保持：内部WallState变更键、PublicWall派生状态、OnWallChanged消息、各产物allocation、GPU范围写。某一层已变更不证明下一层已经完成。

## 3. 45个阶段名称有明确数值来源

`93E620 add_stages`在`93E74F`调用专用from_iter（`15EB150`），从raw值0开始，0x2D是结束哨兵。正常枚举范围为0..44，共45项。

GameSystemSet的vtable同时关联type_id和fmt。fmt读u8值，查RVA `2F5BC38`的45个u64长度与`2F5BDA0`的45个相对地址，再格式化对应字符串。已按真实PE节表重读全部名称/长度/摘要，不只是从零散字符串猜顺序。

与此次编辑相关的名称表片段：

| raw值 | 原名称 |
| --- | --- |
| 0x08 / 0x09 | UiClientLogic / CameraUpdate |
| 0x0A | MainPreUpdate |
| 0x0E | HistoryStart |
| 0x0F / 0x10 | TerrainGenerators / PathGenerators |
| 0x11 / 0x12 | WallShapeUx / RoofUiSystems |
| 0x13 / 0x14 | WallGenerators / RoofSystems |
| 0x15 / 0x16 | RoofDeleteEntities / WallRoofHashmap |
| 0x17 | IntersectWalls |
| 0x18 / 0x19 / 0x1A | ElevatedShapesSupports1 / DecoratorSystems / ElevatedShapesSupports2 |
| 0x1B / 0x1C / 0x1D | Timberframe / WallVisualGenerators / RoofAssemble |
| 0x1E / 0x20 | InitRaycastAccel / Plaster |
| 0x22 / 0x23 | HistoryDeferredRecord / HistoryEnd |
| 0x28 / 0x29 | ReplaySystems / ReplaySystemsCleanup |
| 0x2B / 0x2C | SaveGame / PrepareRendering |

这些是原程序名称，不能仅凭名称为每个阶段补写实际算法或所有成员。尤其不能因为SaveGame存在，就声称每次编辑都立即写盘。

## 4. 不只是枚举顺序：配置真正生成阶段图边

实际桥为：

```text
93E620 add_stages
  → C97EF0 SubApp.configure_sets<Update>
  → 1A12250 Schedules.configure_sets<Update>
  → 1A0C5B0 ScheduleGraph.process_configs
  → 17C65A0 Graph.add_edge
```

`93E760–93E767`把rdata中指向`3333D40`的非零值写入外层config的`+38`；process_configs把同一字段复制到本地，`1A0CD56`非零才进入跨子配置连边路径。正常枚举产生相邻配置的node列表，`1A0CEAD–1A0CEDE`分别将previous、next作为RDX、R8传给add_edge；后续把current更新为下一轮previous。

callee `17C65A0`也已完整解码：它按previous/next顺序构造边键、插入边集合，并向两端邻接表写对应节点，方向字节不同（首端0、另一端1）。这与专用`Graph.add_edge<true,NodeId,...>`共同支持按枚举相邻项建立阶段图约束，而非只有Vec保存次序。

因此可以把名称表当作**静态配置的阶段依赖骨架**。但还没有完整恢复每个具体函数归属、run_if、暂停/加载/重放条件及deferred同步语义。阶段图约束不证明某次运行全部阶段都有工作，也不证明GPU按同一时间顺序完成。

`6C32DF`的屋顶in_set raw值0x1D，现在能对应RoofAssemble；[50](50-tiny-glade-roof-edit-messages-and-regeneration.md)此前保留的阶段原名缺口得到补充。没有据此抹去其实际帧时间线未知。

## 5. 普通墙旧实例怎样被替换

`BD7C70 gpu_flush_brick_buffers`查所需buffer和ECS query，对选定InstancedWall在`BD7E9D / BD7EFB`调用`94C360 upload_to_storage_buffer`；末尾`BD7F74`真实tail jump到`1A76130 SparseInstanceBuffer.gpu_flush<BrickTransformSsbo>`。

upload取得本对象allocation并加锁，`94C471`实际调用共享clear；该clear清占用/位状态、清allocation索引长度并归还旧索引，机制与[50](50-tiny-glade-roof-edit-messages-and-regeneration.md)的稀疏回收一致。该入口地址的PDB最短别名含WoodenPlankSsbo，同址泛型不能据此把普通砖记录解释成木板。

随后`94C490–94C4C8`以64B步长读取待上传砖记录，`94C4C2`调用专用`1A77830 push<BrickTransformSsbo>`。原CPU数组被消费并释放；不是在此逐砖比较新旧位置后保留全部旧slot。push失败有诊断分支，本篇未恢复所有容量/预算规则。

gpu_flush再在`1A76DD3 / 1A76E69`实际调用typed `gpu_write_ranges_nonoverlapping<BrickTransformSsbo>`。本轮确认入口及范围写调用，未继续恢复整个staging/提交callback和渲染pass。因此“CPU记录进入上传流程”成立，“屏幕已经显示新墙”仍需要下游或运行证据。

## 6. 构造例：两面墙与一片屋顶的编辑

这是自造状态演算，不调用游戏函数。选择墙组中有效WallID 7、8，两份合法目标状态；组apply均进入成功状态替换。内部变更键集合为{7,8}。若此前已插入7，再次插入7仍只有该键，不当成两个独立墙对象。

假设两个PublicWall均通过本次派生资格和差异检查，公共生产者写出相应变化消息。又假设7关联有效Roof A、形状/样式变化触发已核重算分支：屋顶消息consumer核实体generation，回收A旧索引，再按当前形状生成。窗的所有位置/cut重新发布尚需其独立资格，不能从“墙7变了”就推定所有窗一定同时重建。

对普通墙显示，构造某InstancedWall本次有3条64B CPU记录，即192B。upload先clear本对象allocation，再push这3条；旧CPU记录数组被释放，随后进入typed范围写。物理slot不必等于编辑前的slot，WallID和随机身份也不由slot替代。

阶段配置中，WallGenerators=0x13、DecoratorSystems=0x19、WallVisualGenerators=0x1C、RoofAssemble=0x1D、PrepareRendering=0x2C，按已确认的枚举连边保持阶段约束。这是职责和依赖示意；本例没有断言每个函数都在该次执行、没有deferred延迟，或192B已经被GPU使用。

## 7. 独立实现规格与边界

自研可独立采用：语义状态按稳定ID提交；变更键集合合并重复请求；派生数据再发布消息；产物owner负责回收；阶段图明确定义生产/消费依赖；上传与GPU完成另有生命周期。对于异步工作，还应按自己的需求设计版本戳和旧结果拒绝，不能由本轮同步片段反推原游戏已有该协议。

未做：未运行带窗建筑移动场景，未完整恢复窗口通知、各函数stage归属、run条件、deferred屏障、上传callback和GPU完成，未测编辑延迟/性能。未启动、附加或读私存档。

风险：静态阶段图不是实际帧时间线；消息写入、语义状态替换、allocation清旧、范围上传与最终显示不能合并成一个“立即完成”动作。共享泛型别名和物理slot必须保持类型/身份边界。
