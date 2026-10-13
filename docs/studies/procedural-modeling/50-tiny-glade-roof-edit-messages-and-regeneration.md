# Tiny Glade 屋顶编辑消息与重新铺瓦

本篇把编辑与墙体变化接到[41屋瓦布局](41-tiny-glade-roof-tile-layout-and-clipping.md)。同一发行版中，可以确认铺瓦的执行对象由 `RecalculateRoofCmd` 选择，旧瓦通过该屋顶持有的稀疏索引回收，然后按当前形状重新生成。当前证据没有建立逐瓦差量更新，也没有建立全游戏固定帧顺序。

身份、原始记录及本轮验证见[52账本](52-tiny-glade-roof-and-vegetation-followup-ledger.md)。地址为相同EXE的RVA；匹配PDB中的类型签名用于解释参数，实际调用和读写用于证明连接。

## 1. 消息生产者和消费者怎样接上

已核对三个带类型的 `FunctionSystem::run_unsafe` 包装器及其实际调用：

| 包装器 → 实际入口 | 选定输入/输出 |
| --- | --- |
| `1F38770 → 280EC40 edit_roof`，call=`1F38B36` | PublicWalls、可写Roof、EditRoofCmd reader；SwitchRoofTypeCmd、RecalculateRoofCmd、gable-wall-height及声音writer |
| `1F45560 → 280E580 update_roof_spatial`，call=`1F45858` | Roof/Transform query、PublicWalls、OnWallChanged reader；RecalculateRoofCmd、RtWorld及UpdateRtWorldEvent |
| `FDE770 → 1F46490 assemble_roof_tiles`，call=`FDEA42` | RecalculateRoofCmd reader、可写RoofTiles/只读Roof query、AssetSsboLibrary、ArchSegments、PublicWalls、UiSignifierStream |

这比只看函数名多了一层证据：包装器确实从World资源槽取参数、组装reader/query/resource借用，再调用对应入口。没有将同址通用辅助函数的最短别名当成唯一类型身份。

编辑入口的第五参数是重算writer。`280ED8E–280EDB1`把它保存为本地指针；`280F6B0–280F715`实际向当前消息buffer追加32字节记录：消息ID在`+0`、屋顶实体在`+8`、另一u64关联值在`+10`、raw原因字节`1`在`+18`，再增加长度和消息总计数。关联值沿输入传递，选定路径与WallID对应；本篇不补写所有原因枚举的原名。

墙体变化入口先读16字节的OnWallChanged记录，其`+8`提供WallID，随后经PublicWalls的屋顶关联查询及实体资格检查选择屋顶（`280E724–280E7C3`）。检测到选定墙样式字节变化或墙形状变化后，分别在`280E986–280E9E6`、`280EAF1–280EB69`追加同样32字节的重算消息，raw原因字节为`2`。

高度变化还有另一职责：`280E87E–280E92A`比较Roof保存的高度值，更新RT记录并发UpdateRtWorldEvent。因此“墙变了”并不意味着每个分支都只发同一种消息。上述两个重算分支是本轮贯通的范围；未枚举全部编辑、创建和删除生产者。

## 2. reader读取的是尚未消费的两段消息

`1F46675–1F467B1`读取reader自己的计数游标和消息资源的两个buffer。用等价的算术表示：

```text
startA = max(cursor - baseA, 0)
startB = max(cursor - baseB, 0)
unreadA = max(lenA - startA, 0)
unreadB = max(lenB - startB, 0)
cursor = totalMessages - unreadA - unreadB
依次取A、B中未读的32B记录；每取一条，cursor增加1。
```

指针计算、减法借位后的条件移动、`shl 5`和游标写回都直接可见。这里是reader的消息生命周期，不能据此声称某个编辑立即在同一帧刷新显示。另一个reader是否读过同一消息，不由这个游标代表。

每条记录的实体值来自`+8`。`1F467E5–1F46860`不仅检查索引范围，还比较实体高32位的generation、实体是否存在及query的archetype membership；失效实体会跳过。因此实体索引被重用时，旧消息不能仅凭同一个低32位索引误选新屋顶。

本地循环未见对重复实体做集合去重：两条指向同一有效屋顶的未读记录都可能进入清旧/生成路径。这只是该入口的观察，不能外推为全局绝无合并或去重。

## 3. 旧瓦回收属于每个屋顶的RoofTiles

入口查AssetSsboLibrary中的RoofTile buffer，取得该屋顶的稀疏allocation。尚无allocation时创建描述记录；存在旧记录时保持引用计数及释放职责。它不是把所有屋顶瓦buffer整体清空。

`1F469AF–1F46A7C`更新组件tick、取得索引列表的写端，然后在`1F46A65`实际调用 `1F4A6C0 SparseInstanceBufferWriter.clear<RoofTileSsbo>`，接着才调用 `Roof.is_flat`。

clear内部也能说明“清旧”具体是什么：

- `1F4A720–1F4A758`遍历该allocation保存的u32索引，把对应占用字节写0，并用原子AND清相应位。
- `1F4A787–1F4A79B`取旧索引数组，先把实体索引列表长度写0。
- `1F4A7CF–1F4A8E8`把旧索引逆序追加到受锁保护的公共回收列表，保存新的列表长度。

没有在该clear范围看到逐条64字节瓦payload全部置零。旧记录内存、占用状态和可重新分配的slot是三件事；回收不要求马上擦除payload。GPU何时收到相应占用/实例更新仍需上传与提交证据。

因为clear发生在flat检查之前，当前屋顶变为flat时可以清掉原有瓦而不再走矩形/圆形铺瓦。PublicWall查找失败也发生在clear之后；本篇不把这个局部分支扩展成所有异常状态的统一恢复规则。

## 4. 重建读取当前形状和当前关联数据

非flat路径经 `PublicWalls.get` 取得Roof关联墙，读取PublicWall的`+274` wall slot。之前未命名的另一个map，现在由真实包装器确认是 `ArchSegments`：入口按WallID查map，测试该墙对应segment列表是否非空，并把结果作为布尔实参传给布局函数（`1F46A7C–1F46BD5`）。

最后根据Roof的形状判别字节分派：

```text
非零形状判别 → 2812C70矩形布局
零形状判别   → 2816BA0圆形布局
两路都携带wall slot、ArchSegments列表是否非空和本实体writer。
```

实际calls在`1F46BCD`和`1F46C05`。详细瓦层、随机、64B输出和边平面仍以[41](41-tiny-glade-roof-tile-layout-and-clipping.md)、[42](42-tiny-glade-roof-edge-planes-and-seams.md)为准。这里确认参数来源，不把“列表非空”自动解释成完整石拱/屋瓦相交算法。

## 5. 注册提供什么时序证据

`6C2B90 add_roof_systems`中，`6C32CF–6C32E4`实际调用专用 `IntoScheduleConfigs.in_set`（`FDED70`），传入raw set判别值`0x1D`。该专用签名含铺瓦reader/query、另一屋顶重算消费者及屋顶尖顶显示query。

同一注册入口另外存在 `chain`、`chain_ignore_deferred`、`run_if`调用，但不能把这些调用统称为“全部屋顶功能有严格链式顺序”。当前没有完整解释`0x1D`对应的阶段名、所有链中函数身份、跨插件先后以及deferred barrier。消息生产→消费的类型和指令连接已建立；具体帧时间线仍未知。

后续[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)通过全局GameSystemSet名称表确认0x1D为RoofAssemble，并补阶段图实际连边；完整函数归属、run条件、deferred barrier及实机时间线仍保留缺口。

## 6. 构造例：消息游标、失效实体和改成平顶

这是按已确认规则演算的自造状态，没有调用发行版函数。

前置：reader游标为10。旧buffer base=8、len=3；新buffer base=11、len=2，总消息数13。于是旧buffer从索引2开始，尚有1条；新buffer从索引0开始，尚有2条。reader本次共取3条，结束游标为13。

其中一条有效消息指向屋顶A，另一条的实体generation不匹配，第三条指向另一有效屋顶B。失配记录仍是被读取的消息，但不产生屋顶重建。

假设A原有索引`[7,12,25]`，当前形状已经改成flat：A的三个占用状态被清除，原索引列表长度变0，公共回收列表增加逆序`[25,12,7]`；随后flat分支不铺新瓦。B的allocation独立，只有B的消息才使B进入清旧/重新布局。

如果A仍非flat且对应ArchSegments列表非空，矩形/圆形布局收到的布尔值为true；具体生成瓦数仍取决于[41布局输入](41-tiny-glade-roof-tile-layout-and-clipping.md)。新瓦也不保证复用同样物理索引；几何随机和slot身份要分别考虑。

## 7. 独立实现可以借鉴的规格

自研可以独立采用：对象级重算请求携带稳定实体身份；消费时核generation和组件资格；各产物持有自己的allocation；回收旧索引后，从当前语义状态生成新输出。消息reader保存自己的游标，渲染池保存slot占用，建筑状态保存形状，三者各自拥有明确生命周期。

这是按证据重组的设计规格，不是恢复代码。是否用全对象重建、逐构件差量或异步版本号，要根据自己的性能和一致性需求选择。

未做：未启动/附加游戏，未抓帧，未验证真实编辑延迟，未穷尽创建/删除生产者或全部调度关系。文档及静态范围检查不构成运行测试。

风险：重复消息可能导致该入口重复清旧/生成；精确运行频率尚未观察。静态回收不证明GPU同步已经完成。屋顶间可见相交仍需结合[48触发几何](48-tiny-glade-roof-trigger-mesh-and-attachments.md)与[49可见性](49-tiny-glade-roof-gpu-visibility-and-depth.md)的边界，不能由消息链补写。
