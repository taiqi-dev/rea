# Tiny Glade：窗户怎样开洞，灯具怎样附着和发光

资产总览及原模型静态叠合图见[64](64-tiny-glade-building-kit-and-asset-assembly.md)。本篇把模型、墙洞、碰撞与光源分别追到实际写端。原制品身份、方法和本轮核验见[67](67-tiny-glade-building-assets-and-assembly-ledger.md)；没有运行游戏。

## 1. 窗是独立对象，也是多个独立视觉部件

`generate_cottage_wall_windows 8C71E0`按modified DecoratorId生成蓝图，并不是在一堵固定墙mesh上选择“含窗版本”。同一蓝图分别包含视觉模型请求、CPU墙洞和精细裁剪记录。前轮[16](16-tiny-glade-window-placement-and-holes.md)确认它们的数组布局和按墙发布。

本轮核到模型key和shader写入，而非仅凭资源同名猜拼装：

| 部件 | 模型key/选择 | 实际写端与shader |
| --- | --- | --- |
| cottage主窗体 | 按选择值1..3选1x1/2x1/3x1 | `8C8273–8C82C9`，nani_solid_vertex_color_window |
| cottage窗格/玻璃 | 对应独立`_glass` key | `8C850E–8C856D`，nani_solid_vertex_color_window_glass |
| 楣梁 | decorators/setdressing_window_lintel | `8C6BD0–8C6C18`，window shader |
| gothic主框 | 按选择值选对应key | `8C4305–8C434C`；按raw分支使用window或bricks shader |
| gothic窗格/玻璃 | 独立glass key | `8C4161–8C41CF`，独立请求 |
| gothic帽部件 | hat/hat_full有条件选择 | `8C3D44–8C3DC3`，nani_gothic_window_bricks |

模型请求携带48B Transform，写入蓝图视觉数组的元素stride为`0x170=368B`。这是CPU请求表示，不是368B顶点或单个GPUdraw。主窗体、玻璃和楣梁可各自选择网格/着色路径；不要把“窗对象独立”误解为“每扇窗只是一份mesh”。

`_glass`资源也不全是玻璃：cottage1x1的1056个顶点中，只有6个is_glass=1，其余1050为0。原始几何投影能看到其中的窗格。玻璃在实际shader里怎样透明、反射或变形，本轮未完成语义核对，静态图的透明色只是观察辅助。

文件映射方面，本轮另核`B1DEC0`的选定loader通过格式参数组成`assets/meshes/{name}.json`并在`B1DF5B`调用JSON mesh loader。模型请求key到该loader、再到最终asset handle的全部中间枚举尚未强接，不能把路径规则直接冒称为每个当前请求都已实际加载的运行证据。

## 2. 放窗会产生洞，但“挖洞”有多层

已确认两条不同的数据流：

```text
窗对象 → 视觉模型请求 → 窗体 / 窗格玻璃 / 条件部件
      → CPU粗墙洞 → 砖局部切分、板区差集、木梁避让
      → 精细裁剪记录 → 相关构件的窗口列表及GPU形状处理
```

普通cottage会写一个中心/宽高的CPU region；gothic用三块矩形近似其粗轮廓。finalize才把中心/尺寸转成min/max。砖、木板和木梁各有自己的消费者，不是所有墙材质共用同一份任意三角网格Boolean：

- 砖：已核`144888A→815BE0 split_brick_by_holes`，相交后进入局部裁短/分割/移除。
- 木板：粗区域读取FinalizedWallHoles，再做二维矩形差集和重新排板。
- 木梁：有点排除与一维区间减法等资格。
- 精细显示：部分木板/曲梁附带窗口索引，GPU还处理洞内可见表面、洞边深度和法线。

详见[17窗洞重建](17-tiny-glade-window-wall-reconstruction.md)、[38木梁](38-tiny-glade-timber-layout-and-window-avoidance.md)、[43木板](43-tiny-glade-wooden-wall-board-layout.md)。因此可以确认“放窗后动态改变墙的生成结果”；不能扩大成“原作每次对完整房屋网格做三维CSG”。

## 3. 精细洞形还与真实窗组件资源相连

本轮补上此前未知的层号到模型输入：`19BA772–19BA795`按shape_id读取18项counts/paths表（`3361428 / 33614B8`）。`19BA7CA→1B25740 load_json_as_mesh`实际读取这些完整文件路径，`19BA842→A97AA0 Mesh.positions`取位置组成烘焙输入。

| shape层 | 实际文件组合 |
| ---: | --- |
| 0 | cottage1x1主窗体 + cottage1x1_glass |
| 1 / 2 | 对应cottage2x1 / 3x1主窗体 + glass |
| 3 | gothic1x1主框 + glass + hat_full |
| 4 / 5 | 对应gothic2x1 / 3x1主框 + glass + hat_full |

这里不是仅把collision_outline当最终洞形。旧17已确认512×512 mask及反集、两次distance_transform、下包络计算及128×128输出；完整光栅化、重采样/偏置/特殊修正仍有缺口，不能用教科书SDF公式补成原作算法。

gothic的实际cut writer把同一个选择值加2：`8C4BCA–8C4C52`。因此选择值1的精细shape为3。但**当前可视帽仍在hat/hat_full条件间选择**，不能因为烘焙层3固定包含hat_full就声称所有gothic可视模型都使用full帽。

## 4. 窗框为什么能随墙移动、贴合弯墙

选定非缓存窗路径，先将窗中心沿墙坐标左右各移动半宽，采样两个世界点A/B，以弦中点作位置，以水平弦法线作yaw；raw墙tag<2另加0.14法线偏移。它不是仅复制鼠标位置。

楣梁则按选择值1/2/3分成相应段数，每段独立采样两个端点、放到中点并求yaw，首末段另有偏移/尺度。gothic请求还有左/中/右位置及法线等额外参数。以上是已核实例布局，不能据此保证所有顶点都以同一个spline贴墙。

花箱位置标记通过原mesh的position/normal变成局部Transform，再随窗父姿态转到世界；后续自动装饰有自己的稳定候选键和资格。窗框、楣梁、窗台/花箱和自动杂物不是同一个模型内部不可分割的部分。全部贴合公式和可选分支见[18](18-tiny-glade-window-frames.md)、[19](19-tiny-glade-window-autoclutter.md)。

### 构造例：实资源尺寸作为输入，放一个窗

选择普通cottage路径，selector=1、dstTag=0、wall+29F=1，中心墙坐标(5,3)，输入碰撞Rectangle宽0.78、Y范围[-0.8,0.8]。这些尺寸与所读collision局部包络匹配，但本例显式给定Rectangle，不冒称其完整派生链已恢复。

1. 主窗体选1x1网格（96顶点/32三角），窗格/玻璃选另一个网格（1056/352）。楣梁若满足该路径资格，会生成一个共享lintel模型请求。
2. 粗洞宽`0.78−0.05=0.73`、高1.6，finalize得`[4.635,2.2]..[5.365,3.8]`。
3. 精细cut为shape0；烘焙输入取主窗体和窗格/玻璃两份真实资源。
4. 对构造直墙(0,0)→(10,0)，左右采样点为(4.61,3,0)/(5.39,3,0)，整体yaw为identity；选定0.14偏移分支后窗位置为(5,3,0.14)。
5. 墙洞按宿主墙ID发布，砖/板/梁消费者改变相应产物；视觉部件另实例化。移动窗后新的位置、洞与modified/蓝图比较决定后续更新。

这里的ID和场景是构造参数，没有实际操作游戏。粗洞尺寸、组件外包络、精细SDF轮廓和最终可见边界不是相同几何。

## 5. 壁灯：灯壳、灯内发光与实际光源各有职责

发行资源有wall、terrain、flat_roof三组灯具，每组分别有主体和inside网格。inside三份都是72顶点/24三角，包络围在灯体内部，不能把inside解释成房屋内部空间。

`8490C0 generate_lanterns`实际写出三组model key，以及inside与`country_core/nani_lantern_emissive`的配对。墙灯选定布局先取p/q，再计算：

```text
p_lamp = p + rotate(q,(0,0,0.28))
```

依据常数`8493B4`及旋转/相加`84A35B–84A409`。特殊基础资格分支可在此之前减去旋转后的0.05偏移，触发依赖公共墙与石基比较；它不是每灯必执行。主体与inside共用同一个48B Transform，匹配静态原点叠合图。

两个builder已保存该变换之后，`84AA9A`又将后续蓝图基准的全局Y加0.5，并写payload+10..3F。这是另一个写端；不能把这0.5又加回刚保存的两个显示builder，也不能直接从它推出最终光源中心。

CPU还分别管理：

- 实际光源slot：世界XYZ、half强度、u16颜色，16B记录；维护路径更新light buffer。
- 可见发光实例：64B LanternEmissiveInstanceData，另一条实例更新路径；shader读取开关/半透明标志与颜色等。

因此“模型上一个发光部分”和“照亮周围表面的光源数据”要分开。发光shader有原始bit30开灯、bit31半透明的消费；bit30关闭时发光输出为零。完整灯光pass、影响范围/阴影和材质同步尚未贯通，不能仅凭emissive效果说明全部场景照明。

### 5.1 光源身份与上传

`84BEC0 maintain_lantern_lights`构造带DecoratorId的28B列表；`149B480`按ID归并旧/新列表。`149B6B0`在相等项复用旧u16 GPU灯ID，新项从空闲池取ID；只有位置、颜色或强度变化才重写。

`149B97F–149B993`的16B槽为XYZ f32x3、intensity binary16、color u16。更新维护dirty最小/最大槽，`84C850–84C8F6`把半开区间`[min,max+1)`乘16后上传。容量检查和ID耗尽失败分支存在，不把它解释为无限灯池。

构造slot7，其偏移为112B；强度1编码为half `0x3C00`。若改变slot7..9，上传区间为`[112,160)`共48B。这是字段与算术检查，不是实机照明测量。

### 5.2 inside的发光几何与shader

三份原inside属性只有Position/Normal/Color，没有UV。Uber配置声明补UV是资源加工的另一层，LanternEmissive组没有同样声明，不能将其写成原inside已有UV。

`257D750 nani_update_lantern_emissive`写64B实例：48B affine、8B半精度局部光中心/强度、flags u32、gpuID u32。顶点shader解包中心后用affine转成世界坐标；gpuID与时间参与强度闪动，其结果再供片元读取。builder里的局部中心原值分别为wall=(0,0,0.3670000136)、terrain=(0,3.02,1.23)、flat_roof=(0,0.4,0)，但builder到ECS发布桥仍未完整恢复，不据此补造最终世界光源位置。

所选发光片元还根据眼睛到当前片元的射线，计算光中心离这条射线的平方距离`d²`，输出：

```text
E = on ? ev_mult * C[color] * 1.4 * I * 3
         * (0.8*exp2(-50*d²) + 2*exp2(-200*d²)) : 0
```

构造color0=(1,0.8,0.1)、I=1、on=true、ev_mult=1、d²=0，E=(11.76,9.408,1.176)。关闭则E=0，但选定shader仍可写gbuffer，不能把关灯说成删除灯内模型。bit31的半透明处理在所选模块按屏幕/帧奇偶取消部分片元，并未读墙形状或房间占用；这只限定该模块，不用于否认游戏其它模块。

on的CPU选择还涉及按DecoratorId初始化随机数与未唯一命名的context字段；没有将这些raw字段直接叫昼夜参数。光源buffer、可见发光和环境照明的完整同步、阴影及tone mapping仍未知。

## 6. 加灯会不会像窗一样给墙挖洞

本轮对选定灯生成链给出正向证据，而不是只做名称负面搜索：

1. `84972A`调用`DecoratorBlueprints.insert 8F3750`取得payload。
2. reuse路径在`8F3970/8F3991`清两个洞数组长度；新分配路径在`8F3B46/8F3B7F`将它们置零。
3. 完整generate_lanterns范围11764B中，模型、collider等写入没有再向CPU粗洞Vec或32B精细cut Vec追加。

所以**这个灯蓝图输出的两类窗洞列表为空**。可以说选定壁灯通过附着、可视模型和光源拼入建筑，不采用上述普通窗的开洞产物；不能扩大为其它系统绝不可能增加任何开口。

构造p=(7,2,0)、q=identity，特殊石基修正不成立：两个builder保存的位置均为(7,2,0.28)，保持相对局部位置；后续蓝图基准Y为2.5，两种窗洞数组仍为零。光源和发光有各自更新入口，但本例不补造完整ECS发布桥。本例不把0.28解释为读取任意当前墙厚的结果，也没有证明其它灯类型共用同一偏移。

## 7. 自研意义、未做与风险

自研可以独立把“装饰对象”设计为一个逻辑owner，输出模型部件、宿主切口、附着姿态和可选光源等不同产物。窗需要切口；普通挂灯可只要附着和光源。宿主变化后，由owner重新发布它负责的产物，不能让旧洞或旧光源无人清理。这是独立规格建议，不是原作完整事务实现。

未做：没有放窗/拖灯实机验证、私人存档、游戏启动或原文件修改；没有完整恢复所有窗台、corner/dormer、玻璃shader、灯光pass和加载器中间链，也没有验证房间内腔/导航。

风险：把多个资源压成一个窗mesh、把粗洞和精细形状混为一体、把inside当房间或emissive当全部光照，会误导自己的资产与更新系统。正文保持这些职责和证据边界。
