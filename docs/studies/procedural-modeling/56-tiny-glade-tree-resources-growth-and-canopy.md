# Tiny Glade 树木资源、展开动画与树冠造型

选定发行版树木由现成网格、资源中的age/appear_pos属性、实例放置参数及GPU加工组成。已确认树干展开、风摆/弯曲和相机相关树冠片扩展；没有证明这条路径实时生成树枝拓扑。配置中的extract_canopy/trunk处理器及其属性生产仍有缺口，不能把“树会长出来”直接解释为生成新枝节点。

地面植被候选见[46](46-tiny-glade-land-vegetation-and-exclusions.md)，计数/列表见[51](51-tiny-glade-vegetation-counts-and-active-list-rebuild.md)，岩层另见[57](57-tiny-glade-rock-mesh-displacement-and-masks.md)，身份与复核见[58](58-tiny-glade-input-edit-and-natural-shapes-ledger.md)。shader位置为原precomp文件偏移。

## 1. 现成几何与处理器各有证据

`assets/glade/summer/trees.json`的9项配置关联prefab与placements，例如branchy1和mid1。配置中的default.ron为canopy指定`extract_canopy`处理器和`country_core/clearing/tree_canopy`，trunk指定`extract_trunk`和tree_trunk。branchy1两部分使用branchy_tree_v1；mid1则分别使用中距离冠/干网格。

原资源网格的元数据：

| 网格 | 位置数 | index数 |
| --- | --- | --- |
| branchy_tree_v1 | 2,703 | 3,597 |
| mid_distance_tree_v1冠 | 1,740 | 1,740 |
| mid_distance_tree_v1干 | 234 | 1,329 |

这些网格已有Vertex_Position、Vertex_Normal、Vertex_Color、prim_center、appear_pos和age。树冠shader还读prim_normals，但该属性不在这三个原网格清单中，不能省略处理器生产环节。配置继承/覆盖、extract的实际算法以及原资产最初制作工具没有恢复。

本轮只保存schema、数量和摘要，不交付原顶点/index数据或游戏资产。

## 2. 预置数据转换尚不是完整发布桥

`A32F00 spawn_preplaced_trees`的实际路径读取Vec<PlacementConfigEntry>，按80B配置推进；再在`A33553`解析Vec<PlacementDataSsbo>，按48B记录推进，`A336B5`加入ConvertedPreplacedTree marker。

这延续[46](46-tiny-glade-land-vegetation-and-exclusions.md)的预置转换证据，尚未贯通ECS到renderer SSBO的发布及参数覆盖。因此不能将某条原JSON记录不经修改地直接等同于下面shader实例，也没有由9项配置推定森林实际密度或玩家树创建规则。

选定树干/树冠vertex实际经实例indirection读取PlacementData的position、scale、rotation_angle、id、anim_t_packed和bend_vector。字段消费成立，配置到这些最终字段仍包含上述发布缺口。

## 3. 树干的“生长”是两个已有位置之间展开

`tree_trunk.precomp`vertex blob0从文件`0x9D`开始，`0x1DF5–0x1F9D`解包anim_t_packed的第一half A，与网格age组合：

```text
t = clamp(2*clamp(A,0,1)-age,0,1)
q = sqrt(t)
p = mix(appear_pos,Vertex_Position,q)
```

age和appear_pos是网格输入，不能由名称补写成运行时分枝计时器。选定vertex消费已有顶点，没有写新的indices或枝连接。

后续`0x1F9D–0x2301`以p.y×0.02及四个sin改变XZ，时间分game_time_sec与game_time_frac处理，频率约0.823529、0.893617、0.792453、0.688525。x更新后参与后一z计算，不能用两个完全独立正弦替代。

再做uniform scale、rotation_angle转Radians的水平旋转和position平移。bend以原Vertex_Position.y记为Y0：

```text
b = 0.75*clamp(0.1*Y0,0,1)*mix(0.5,1,age)
worldXZ += bend_vector*b
```

这里的Y0没有直接替换成展开后p.y。所查路径的法线做旋转；未把位置弯曲自动解释成完整法线重算。

## 4. 树冠展开系数可以超过1

`tree_canopy.precomp`vertex blob0从`0x9F`开始，`0x2537–0x27C7`使用不同的展开函数：

```text
t = clamp(2*clamp(A,0,1)-age,0,1)
r = clamp(1-t,0,1)
f = 1-r*r+r*sin(3.140000104904175*r)
p = mix(appear_pos,Vertex_Position,f)
expansion = bitcast_f32(custom0)*f
```

f没有再clamp到1。它能使中间展开超过目标位置，不能概括成简单线性长大。f<0.01的分支向clip输出写四个NaN并提前退出；实际GPU/renderer怎样处理这些NaN仍未验证。

树冠风摆系数是p.y×0.03，随后也执行实例变换。`0x3013–0x30CB`实际读prim_center、prim_normals；`0x39A7–0x3A23`把Vertex_Color.xy映射为2×color−1，做二维旋转、经view_to_world方向变换并乘expansion，追加到变换后的点。这是相机相关的冠片扩展，不能据此说增加了树枝拓扑。

## 5. 冠片朝向和纹理决定细轮廓

选定facing计算令D=center−eye、d=length(D)、c=dot(transformed_prim_normal,D/d)：

```text
g = c-abs(c)*clamp((5-d)/5,0,1)
```

g>=0.3时同样提前输出NaN clip值。之后有GLSL SmoothStep(0.3,-0.199999988,g)，再算`1-(1-S)^2`并做远近缩放。本轮保留这一反向门槛的原调用及后续指令，没有实机确认其设备结果，不把它改写成有跨设备保证的自研函数。

fragment blob1从`0x5937`开始，实际读取canopy_alpha_texture的R。选定花朵替代flag成立时有效值取1，否则取纹理R；有效值<0.2则demote。名称含alpha不能单独证明GPU采用何种blending状态。另有相机圆锥see-through取消分支，完整花朵/see-through资格未恢复。

## 6. 构造例：展开、弯曲与冠片门槛

以下是自造输入与局部公式演算，没有使用原资产顶点、没有运行shader。

先取A=0.5、age=0.5、appear_pos=(0,0,0)、Vertex_Position=(0,2,0)。树干t=0.5、q≈0.70710678，风摆前Y≈1.41421356。树冠r=0.5、f≈1.24999984，展开Y≈2.49999968，超过目标2；custom0位模式代表0.5时，expansion≈0.62499992。

单独隔离树干弯曲步骤：完全展开、age=1、原Y0=5、scale=2、rotation=0、position=(10,0,20)，构造风位移为0、bend=(2,-1)。b=0.375，原变换位置(10,10,20)附加XZ=(0.75,-0.375)，结果(10.75,10,19.625)。风条件与实例值是构造前提，不代表真实树记录。

facing门槛g=0.3进入提前退出，g=0.2不从这一门槛退出；后续反向SmoothStep不在此例中作设备数值保证。纹理门槛例另假定不走花朵替代及相机圆锥取消：R=0.1取消，R=0.3通过该门槛，R恰为0.2也通过。

## 7. 独立实现规格与边界

可以独立设计带appear_pos/age等展开属性的资源，配合实例动画、弯曲和冠片扩展，让现成拓扑表现出长出、风动和视角变化。是否需要程序分枝，需按自研要求另建骨架/拓扑生成器；本轮不能提供原游戏L-system或实时枝连接算法。

未做：未恢复extract_canopy/trunk、prim_normals生产、ECS→GPU发布、玩家树全部规则、资源离线制作方式、完整冠片facing/see-through及最终pass。未运行游戏/GPU、未附加或读私存档。

风险：资产属性加工、实例展开与拓扑生成不同；NaN输出和反向门槛未有设备验证。所选模块未生成枝拓扑的有界结果不能外推成全产品绝无程序树。
