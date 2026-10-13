# Tiny Glade 岩层单元网格、mask位移与地形落地

发行版有普通现成岩石网格，也有另一条rocky terrain路径：把已有单元网格转换成GPU记录，compute按地形、岩、水和道路mask位移三个顶点，重算三角形法线。已核路径没有增加单元邻接或新三角形；源单元网格最初怎样制作仍未知。

树木见[56](56-tiny-glade-tree-resources-growth-and-canopy.md)，地形高度见[31](31-tiny-glade-terrain-strokes-and-heightfield.md)，水域见[07](07-tiny-glade-water-shape-and-banks.md)，身份和范围见[58](58-tiny-glade-input-edit-and-natural-shapes-ledger.md)。CPU用RVA、shader用原precomp文件偏移。

## 1. 普通岩石和岩层各有输入

普通候选网格olden_glade_rock有396位置/588 indices，terrain_rocks有10,732位置/22,536 indices。另有60项岩石placement资源，但本轮未证明当前主题一定加载这份配置，不能直接称为当前场景数量。

`data/rocky_terrain.json`有148,794源vertex及49,598 triangle，vertex字段为position、cell_bby、cell_id、dir_to_centroid、is_corner；triangle字段为neighbours、is_top。字段/数量支持单元网格解释，没有证明其制作时是否由离线程序生成。

`1648C80 RockyTerrainMesh.load`实际反序列化同类结构并转换buffer，但具体filename caller未贯通。因此该JSON与load参数仍是强匹配候选；下面CPU转换与GPU绑定各自成立，不冒称完整文件调用已接通。

## 2. 源数据怎样变成GPU记录

`1648E20–1648E72`把36B源vertex转换为48B：rest_position和position最初均复制源position，保留单元属性。GPU布局为：

| Vertex字段 | 字节偏移 |
| --- | --- |
| rest_position Vec3 | 0 |
| cell_bby | 12 |
| position Vec3 | 16 |
| cell_id | 28 |
| dir_to_centroid Vec3 | 32 |
| is_corner | 44 |

Triangle记录为32B：neighbours在0、is_top在12、normal在16、pad在28。

`B39070 displace_rocky_terrain`实际在`B3926D / B39280`取得两种SSBO写资源，`B3932A`绑定`country_core/rocky_terrain/displace_rocky_terrain:main`，`B39399 / B393A4`完成两写端，另发布资源包。调用和字符串引用共同证明真实选择，不能只靠shader文件名。

compute LocalSize为64×1×1，`invocationX>=num_triangles`退出。第i个三角形处理`3*i+[0,1,2]`三个顶点。CPU把某原qword除3送入逻辑X和num_triangles，该qword上游归属未完全恢复，逻辑X不直接叫硬件group数。

## 3. 单元ID产生稳定小扰动

shader blob0从文件`0x90`开始。cell_id位转u32，固定hash H按u32运算：

```text
n += n<<10; n ^= n>>6; n += n<<3; n ^= n>>11; n += n<<15
u = bitcast_f32((H & 0x7fffff) | 0x3f800000)-1
pLS = rest_position + 0.001*dir_to_centroid*mix(-3,8,u)
pWS = 65*pLS
uv = pWS.xz/130 + 0.5
pWS.y = -2.5 + 26.5*terrain.R(uv)
```

`0x2104–0x249C`确认字段和算术。同cell的hash共享稳定输入，但没有由此推定cell_id的全局创建规则或邻接生成算法。

若abs(worldX)>65或abs(worldZ)>65，落地Y另减2，mask采样也有域内/域外分支。实际sampler边缘寻址未完整恢复，不能根据sampler名字补wrap规则。

## 4. 岩、水、道路共同决定Y偏移

用S表示正常递增边界的smoothstep。令：

```text
M = clamp(S(0.1,0.2,rock.R+rock.G) + S(0,0.2,water.G),0,1)
P = S(0.1,0.15,path.R)
B = rock.B
yOffset = mix(-0.4,0.2,clamp(M+B-10*P,0,1))
          -0.2*S(0.5,0.6,water.G)
```

M是组合mask，不是直接rock.R。`0x2B64–0x2C30 / 0x2EF8–0x3334`有实际采样、门槛及混合。

`0x343C–0x466C`还使用water.G的中心pulse、XZ×0.2的四格值噪声和`1-S(0.3,0.5,terrainHeight)`削低近低地Y。pulse以a=abs(water.G−0.5)计算，a>1取0，否则为`1-a²*(3-2a)`。完整噪声配置未恢复；不能因为高地例的系数为0就说这段对所有岩层无作用。

## 5. 贴坡、corner和附加挤出

`0x4804–0x4B44`从terrain四点gather估计梯度并构造法线N，顶点附加位移的选定式为：

```text
N*mix(-0.3,0.1*mix(0,3,u),cell_bby)*M*(1-P) - N*P
```

is_corner非零跳过另一段坡面extrusion；非corner且P==0可进入`0x4C14–0x5240`，读坡度、单层signed noise及rock.R/G作附加挤出。该分支不能简化成对所有点同一个固定岩高度。

既有单元内属性、共享扰动、组合mask、贴坡和条件挤出分别承担形状变化，不能全部命名为一个随机noise。

## 6. 激活、失活与法线输出

每个三角形先对三个rest顶点判断：任一点满足M>0或rock.B>0，就进入全部三点位移。全不合格时，`0x671C–0x6840`只把首vertex.position写为NaN向量，没有在该compute删除indices或重排邻接。最终renderer如何处理这种三角形未追，不能称为已经验证的硬件discard。

位移后的position写回，三角形法线按`normalize(cross(p1-p0,p2-p0))`重算；neighbours、is_top、pad保留。CPU finish_write只证明构图写端结束，不证明GPU或最终画面已完成。另有rocky_terrain渲染模块，本轮没有将其完整纳入消费链。

## 7. 构造例：已有岩层单元落到平地

以下为自造输入，采用已确认选定分支，未使用原资产顶点或执行shader。

给rest_position=(0.1,0.048,0.2)、dir=(1,0,0)、cell_id=0、cell_bby=1、is_corner=1。H(0)=0、u=0，pLS=(0.097,0.048,0.2)，worldXZ=(6.305,13)。假设域内平面terrain.R=0.2，落地Y=-2.5+26.5×0.2=2.8。

再给rock=(1,0,0)、water.G=0、path.R=0，得到M=1、P=0、B=0，yOffset=0.2。此高度大于0.5，使选定低地噪声削低系数为0；平面N=(0,1,0)、bby=1且u=0使该normal附加位移为0；corner跳过额外extrusion。最终position=(6.305,3,13)。

3个源vertex和1个triangle转换为144B VertexSSBO、32B TriangleSSBO；num_triangles=1时只有invocation0处理三个点。真实加载filename和硬件尾组调度仍是独立问题。

法线例p0=(0,3,0)、p1=(1,3,0)、p2=(0,3,1)，叉积为(0,-1,0)，法线向下；交换p1、p2则向上，不能擅自修正原绕序。失活例三个点rock全零、water.G=0，M=B=0，首position写NaN，最终可见结果未知。

## 8. 自研规格与边界

可独立采用带cell_id/centroid方向/corner属性的基底网格，按场景mask进行位移、落地与法线重算。自研若需可控失活，应另定义renderer消费契约或有效标记，不能直接把未实机验证的NaN机制当成可移植保证。

未做：未恢复具体load filename、源网格离线生产、普通岩placement加载、岩mask上游全部笔刷、完整渲染consumer和NaN最终行为。未运行GPU/游戏，未附加或读存档。

风险：源拓扑、CPU转换、GPU位移和最终可见几何不同；非corner分支、噪声配置、纹理边缘与退化法线仍部分未知。局部构造例不建立原场景或跨设备等价性。
