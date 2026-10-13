# Tiny Glade 屋顶表面三角形、RT几何与装饰附着

这一轮确认了 `RoofTriggerVolume` 的实际内容：它持有三角形、UV和法线数组，并提供从表面UV还原三维位置的查询。该查询真实用于装饰变换缓存和装饰分件显示，屋顶编辑也读取这份三角形。入口还生成RT几何，但目前不能将其解释为建筑间切瓦或完整网格布尔。

可见屋瓦的铺排见[41](41-tiny-glade-roof-tile-layout-and-clipping.md)，本屋顶边平面见[42](42-tiny-glade-roof-edge-planes-and-seams.md)，本轮shader边界见[49](49-tiny-glade-roof-gpu-visibility-and-depth.md)。身份和逐范围摘要见[52账本](52-tiny-glade-roof-and-vegetation-followup-ledger.md)。

## 1. 输入是当前屋顶的轮廓与剖面

`2809250 calculate_roof_trigger_volumes`按当前Roof的WallID查询WallRenderSlots，使用本屋顶的上下扩张轮廓、剖面和变换生成表面。选定生成段没有把另一屋顶的轮廓作为输入；函数名中的volume不能单独证明闭合体或相交差集。

实际细分与可见瓦密度不同：

| 选定路径 | 指令确认的规则 |
| --- | --- |
| 高度/剖面带数 | `2809583–2809595`：flat取4，nonflat取9 |
| 圆形剖面带 | `28098F6 / 2809929`：`q0=j/N`、`q1=(j+1)/N` |
| 圆形周向 | `2809D56–2809D8E`：固定15格，`u0=i/15`、`u1=(i+1)/15` |
| 矩形 | 使用本Roof上下Rectangle2d的as_curve2，沿当前边界生成；局部调用Triangle.normal |

因此该圆形采样网格不能用[41](41-tiny-glade-roof-tile-layout-and-clipping.md)中随周长变化的瓦片数量替代。额外表面、较低表面和退化分支尚未全部整理；`9×15`也不能直接当作整屋顶三角形总数。

`14737C0 Triangle.normal`在有限、非退化输入上等价于：

```text
n = normalize(cross(P1-P0, P2-P1))
  = normalize(cross(P1-P0, P2-P0))
```

局部真实call在`280B0BF`。这次没有建立所有分支的绕序和法线方向约定。

## 2. 噪声作用在生成后的顶点Y

`280BA81–280BAC6`以36字节步长遍历三角形，在每个三角形内以12字节步长处理三个Vec3。真实调用 `B76780 apply_roof_noise`，高度实参是 `vertex.y - Roof[+4C]`。

已确认的外层公式为：

```text
c = clamp(vertex.y - Roof[+4C], 0, 1)
S = c*c*(3-2*c)
vertex.y += 0.3*S*F(0.5*vertex.x, 0.5*vertex.z)
```

`B76790–B767E1`确认clamp、平滑多项式、坐标缩放和Y增量。`F`是实际call `17DDC70` 的返回值；本轮没有恢复它的完整内核，也没有把它当成已知Perlin/Simplex噪声。

这里的高度差按0到1截断，不能直接命名成归一化屋顶剖面参数。法线调用在该顶点噪声遍历之前，遍历中未见重算法线；保存的法线不一定是位移后每片三角形的精确法线。CPU表面和GPU瓦片各自的变形也不能默认逐点一致。

## 3. 三份属性数组的所有权和替换

生产者分别在`280BB1D / 280BB79 / 280BBD5`调用triangle、UV、normal setter。getter和setter实际字段读写确认：

| 属性 | capacity / pointer / length偏移 | 每项 |
| --- | --- | --- |
| triangles | `+00 / +08 / +10` | 36B，三个Vec3 |
| normals | `+18 / +20 / +28` | 36B，三个Vec3 |
| UVs | `+30 / +38 / +40` | 24B，三个Vec2 |

`A0A0F0 set_triangles`、`A0A1B0 set_uvs`、`A0A080 set_normals`在旧capacity非零时释放旧pointer对应的capacity字节，再转移新Vec的三字段。UV和normal替换之后检查entry count必须等于triangle count，失配进入panic。

这建立了属性同步的明确失败信号，却不构成几何有效性保证。相同项数不保证无零面积、无非有限坐标或UV唯一；替换顺序也没有表现为可回滚的整体事务。

## 4. RT输出拥有自己的顶点记录和标记

`280BC12`实际调用 `RtWorld.get_mut<RtMeshHandle>`。随后：

- 将WallRenderSlots的返回值与`0x02000000`按位OR，写到RT记录`+58`。
- 保存四组16字节raw记录：`(1,0,0,0)`、`(0,1,0,0)`、`(0,0,1,1)`、`(0,Roof[+4C],0,0)`。
- 将顶点数量`+50`清0；后半段经`+48`数据pointer追加Vec3，每个三角形增加三个顶点。capacity在`+40`。

代表指令为`280BC33–280BC90`及`280CAD8–280CB79`。后半段还处理另一组边界/较低表面。因此RT顶点数组与前述CPU triangle cache不能未经核对就认作同一份完整几何。

raw标记的命中类型解包尚未贯通，保留`0x02000000`原值，不命名为原程序某个RoofHit枚举。四组记录也不按普通齐次Mat4解释，其w布局已经与普通单位矩阵不同。RT上传、加速结构提交及命中结果是否控制瓦可见性仍未知。

## 5. 表面UV怎样还原三维位置

`A0A130 RoofTriggerVolume.get_position_from_mesh_uv`读取triangle与UV数组，实际调用 `1B45E90`。选定非退化UV三角形的数学等价是：

```text
D = det(U1-U0, U2-U0)
b = det(Q-U0, U2-U0) / D
c = det(U1-U0, Q-U0) / D
a = 1-b-c
若a、b、c均>=0：P = a*P0 + b*P1 + c*P2
```

函数逐三角形查找，接受第一个命中。未命中返回tag=0；命中返回tag=1。外层getter再把传入的Y偏移加到结果的Y上（`A0A16F–A0A192`）。它是参数化表面位置查询，不是三维闭合体inside测试。

全.text的E8扫描只提供候选，随后完整解码的实际消费者才升级为事实：

| 实际caller | 已确认连接 |
| --- | --- |
| `8E25A0 cache_decorator_transforms` | `8E2D05`调用UV位置getter，检查tag并用位置继续变换缓存 |
| `14C8680 try_display_roof_decorator_parts_and_get_hovered_part_id` | `14C8B86`调用同getter并使用位置 |
| `1F3D0A0 ui_edit_roof` | `1F3D77A`调用`A0A220 triangles`，传入Roof的`+4C`作为Y参数；getter返回slice与偏移，空集会panic |

另有`86748F ui_move_decorator`直call候选，本轮没有单独解码该caller，不将其加入已确认使用链。上述消费者支持附着/显示位置缓存与编辑访问职责，没有提供“另一建筑在这里裁掉瓦片”的证据。

第十三轮[54](54-tiny-glade-edit-picking-and-wall-placement.md)已完整解码ui_move_decorator并核对`86748F`实际call，将此候选升级为事实；RT raw标记到UI hit的上游转换仍未知。

## 6. 构造例：细分、替换与装饰附着

以下是按已确认公式演算的自造输入，没有运行游戏。

非flat圆形路径取9个剖面带、每带15个周向格，即135个采样格。带`j=2`覆盖`q=[2/9,3/9]`，周向格`i=3`覆盖`u=[3/15,4/15]`。135表示采样格数，未推定全屋顶最终三角形数量。

令一个顶点相对`Roof[+4C]`高0.5，构造输入`F=0.5`。则`c=0.5`、`S=0.5`，Y增加`0.3×0.5×0.5=0.075`。F值是人为指定，不是原噪声的采样结果。

假设旧triangle capacity=2、旧UV capacity=2，替换时分别释放72B和48B。新triangle、normal、UV各3项能通过数量检查；若新UV只有2项，替换后触发断言panic，不能宣称自动回滚。

再取UV三角形`[(0,0),(1,0),(0,1)]`，查询`Q=(0.25,0.25)`，得到权重`(0.5,0.25,0.25)`。三维顶点取`[(0,0,0),(2,1,0),(0,2,2)]`，插值得到`P=(0.5,0.75,0.5)`；传入Y偏移10后返回`(0.5,10.75,0.5)`。

若Q改为`(1,1)`，权重为`(-1,1,1)`，这片三角形不接受；只有这片时返回tag=0。UV三角形重叠则保留首命中语义，不能假设唯一面。

最后，RT墙slot=7时raw tag为`0x02000007`；已有6个顶点再追加一个三角形后为9。标记和数量是输出身份/存储状态，不能从中推断最终瓦片保留侧。

## 7. 自研规格与边界

可以独立借鉴一个低密度表面cache：语义屋顶生成triangle+UV，装饰保存表面坐标，建筑变化后重新通过UV取位置。可见瓦、表面查询和RT几何各有自己的表示与生命周期；它们可以来自同一屋顶状态，而无需把所有用途都绑定到可见瓦网格。

未做：未运行交叠建筑、装饰移动或屋顶编辑场景，未附加进程，未验证GPU/RT同步和性能；没有恢复全部拓扑、第二组RT表面及噪声内核。

风险：UV退化、非有限数据和重叠UV的所有异常分支仍不完整；数组数量断言不能取代有效几何检查。建筑间接触、保留侧和接缝机制仍部分回答，本篇没有证明RoofTriggerVolume控制瓦片可见范围。
