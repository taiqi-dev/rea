# Tiny Glade 石基表面：上下边界、面带、窗洞与重建

所选木墙石基表面由CPU建立上下边界和顶点带，再生成GPU实例；地形变化后的旧表面按墙清理。显示阶段只对XZ加小幅起伏，窗洞另用墙坐标和洞形纹理裁片元。这个模块不是任意建筑网格的统一布尔切割器。

高度取样与石基标量见 [32](32-tiny-glade-building-ground-sampling-and-heights.md)，地形更新见 [34](34-tiny-glade-terrain-readback-and-local-updates.md)，身份、范围和未知见 [35](35-tiny-glade-terrain-evidence-ledger.md)。全部是同一发行版的静态指令与构造演算。

## 1. 选墙条件与先清旧产物

`maintain_stone_foundation_surfaces`，RVA `840220`，一路事件在 `84046A` 清旧表面；另一路在 `840629` 先清旧，再按WallID查询当前PublicWalls。资格不成立时不会保留这次已经排队移除的旧实例。两路消息的完整产品名称和scheduler未恢复。

`8406E3–84071A` 核到：墙+29F满足 `is_wood`，原始类别+258≤1，石基偏移D(+294)>0。top helper返回Some才继续。该限定适用于此木墙石基表面入口，不代表所有石墙、桥墩或道路地基采用同一模块。

`8409DC` 的 `Roof.is_flat` 结果直接成为高度模式参数；没有屋顶时为0，传入top helper。它与逐点函数r9的插值开关分别保存，不能把两个布尔值混用。

**构造例。** 木墙条件成立、类别=1、D=1且top helper成功时继续生成；D=0跳过。若处于先清旧的重建路径，跳过意味着这次不创建替代面带，而不是继续沿用旧表面。

## 2. 上下边界的实际计算

`wooden_stone_foundation_surface_top_y(930190)` 在资格成功后返回 `transitionY+.08`，其中transition实际调用 `92FF30`，公式在32。逐点版本 `9301E0` 另作上限：

```text
插值开关非零：top=min(topBase,墙+E0高度数组在u处的线性插值)
另一分支：top=min(topBase,墙+10C)
```

缺失数据、索引越界有unwrap/bounds/panic路径，不静默当成功。

普通下沿在 `841375–8413CF` 从当前输入Vec3曲线Y插值得到：

```text
candidateBottom=lerp(baseY_i,baseY_(i+1),alpha)−.05
如果墙+284>0：candidateBottom=max(candidateBottom,墙+284)
```

另一条已确认路径把道路开口转换成AABB；当u严格位于 `u0+.0001` 与 `u1−.0001` 之间，可用开口记录第三float替换下沿。重叠记录有浮点total-order选择，完整业务顺序未恢复。最终 `bottom=min(candidateBottom,top)`，避免这一步的下沿高过上沿。道路开口的CPU边界修正与窗洞GPU裁剪属于不同阶段。

每个 `StoneFoundationSurfacePoint` 为24字节：u、bottom、top、Vec3 normal。矩形/圆形法线调用实际形状helper，其他所选分支从XZ切向求垂向并归一化。

**构造例。** topBase=2、局部墙高1.8，则top=1.8；baseY插值1、下限字段0、没有开口，下沿为.95，面带高.85。若道路开口将下沿覆盖成1.4，则面带高.4。此例使用已更新曲线作为前置，不能据此推断任意地形修改当帧完成重建。

## 3. 下沿跳变与面带顶点

相邻下沿在特定分支变化时，同一u可追加旧bottom与新bottom两点；`13EE820` 对相邻24字节点筛选，u相等但bottom不等时收集较高bottom，供后续分带。这里保留下沿跳变，未将所有基础边缘平滑成样条。

选定外侧面顶点：`position=worldSpace(u,y)+.28*normal`；另有零偏移和反向法线分支，不能概括为所有面都对称±.28。完整侧面、顶面、端面类型映射仍有缺口。

48字节顶点布局：

| 偏移 | 内容 |
| --- | --- |
| 0 | Vec3 position及填充 |
| 16 | Vec3 normal及填充 |
| 32 | Vec2 wall-space，选定分支为(u,y) |
| 40 | Vec2曲线UV |

选定UV含 `.3*y` 与 `uvScale*u`；形状raw tag0分支 `uvScale=max(round(wallLength*.3),1)/wallLength`，另一分支为.3。这使沿墙纹理尺度与整圈长度有联系，完整接缝材质规则尚未恢复。

**构造例。** 外侧分支世界位置(0,1,0)、法线(1,0,0)，CPU顶点变为(.28,1,0)。同u=1的bottom分别.5、1，分带候选收集1。它不是给所有墙定义同一厚度的证据。

## 4. 两排顶点与最多32个quad分块

`append_stone_foundation_surface_face(844990)` 要求两排顶点数量相同且N≥2，range指针/数量一致。把两排48字节顶点拼成2×N，buffer字节数96N。真实GPU buffer创建有Result检查，失败进入诊断路径。

指定quad范围或默认[0,N−1)按最多32个quad切块。每块40字节CPU描述符保存剔除用包围球、顶点地址、quad数量、row stride和原始面类型：

```text
address=bufferAddress+48*start
quadCount=min(rangeEnd−start,32)
rowStride=N
```

包围球中心是所查顶点均值，半径取最大距离；它用于显示范围，不生成球形地基。

**构造例。** N=70，共69个quad，分32/32/5三块，起点0/32/64，地址偏移0/1536/3072字节；第二排相对第一排偏移70×48=3360字节。

## 5. 显示实例如何找到面带顶点

`nani_update_stone_foundation_surface(2581D20)` 把描述符及墙/cutout关联数据转换成64字节实例，`2582435` 调 `OwnedGpuWorldSubset.update_instance_data(952650)`。实例包含包围球、wall slot、wall length、接缝开关、quad数量、顶点GPU地址、row stride、cutout地址/数量和面类型。

`nani_stone_foundation_surface.precomp` 所选顶点模块在原文件 `18ED–1CD5` 核到：

```text
gridX=(vertexId−baseVertex)&65535
gridY=(vertexId−baseVertex)>>16
addr=verts+48*(gridX+gridY*rowStride)
```

gridX>quadCount时输出无效顶点；正常路径三次16字节读取48字节顶点。完整索引资产未恢复，但实例到两排顶点的地址桥已确认。

**构造例。** 上节第二块，gridX=2、gridY=1，读取原buffer偏移1536+48×(2+70)=4992；gridX=33超过该块quadCount=32，走无效分支。

## 6. 可见起伏与窗洞裁剪

所选顶点尾段 `4B7D–4CBD` 对空间噪声作：

```text
d=clamp(2.5*(noise2−.5),−.5,.5)
P_visible=P_cpu+.06*(d.x,0,d.y)
```

本步骤单个XZ分量最多偏移.03，Y不变，也没有在该步重新采地形图。完整噪声配置未恢复，不保证独立实现能逐位重播。

片元模块 `7912–7F1A` 遍历32字节cutout记录，其center/size在墙坐标中：

```text
q=(fragWallSpace−center)/size+(.5,.5)
q在[0,1]盒内时，采window_cutouts纹理数组的指定层
R>.5时demote片元
```

因此石基的窗洞还依赖GPU洞形纹理，不等于CPU已经切出每种完整窗轮廓。记录生产与窗框详见 [普通窗专题](17-tiny-glade-window-wall-reconstruction.md)。

**构造例。** noise2=(.8,.1)，CPU顶点(.28,1,0)显示为(.31,1,−.03)。cutout中心(1,1)、size(2,2)、墙坐标(1.5,1)，q=(.75,.5)；若纹理层R=.8，剔除，R=.2则保留；超出盒的点跳过该cutout。

## 7. 旧实体与buffer所有权

`despawn_stone_foundation_surface(83FF50)` 按WallID移除旧实体列表，逐个排队despawn并释放CPU列表。新几何资格成立后创建 `StoneFoundationSurfaceBufferOwner`、表面实体，并把新列表insert回墙映射。

BufferOwner的drop `13FD930` 持锁取走buffer列表、清长度，将handle放入全局延迟队列，tag=3。没有恢复队列消费者、GPU栅栏或后端释放时刻，不能说排队despawn后GPU内存即时释放。

**构造例。** 墙旧实体[10,11]被移出映射并排队移除；资格成功则生成新组，失败仍不恢复旧组。owner若持2个buffer，drop产生2个tag3延迟项；实际释放时间仍未知。

未做：没有运行坡地、道路穿石基或不同窗型场景，未恢复完整面带枚举、所有shader变体、索引资产与延迟释放消费者。

风险：地形取样、上下界分支、局部开口和显示起伏分别影响视觉；这一木墙表面模块不能外推成所有建筑基础的统一算法。
