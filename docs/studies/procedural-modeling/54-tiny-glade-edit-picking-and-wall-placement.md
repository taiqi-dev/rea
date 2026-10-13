# Tiny Glade 编辑拾取、墙面投影与普通窗放置

本篇确认了相机射线、选定Rapier查询，以及普通装饰/窗放置的“UI命中记录→墙折线投影→墙坐标→放置写端”。不同命中记录的上游尚未全部连通，不能把它们按同一布局拼起来；最近点投影也不等于已恢复完整磁性吸附或普通窗尺寸限制。

轮廓生产见[53](53-tiny-glade-wall-footprint-input-and-curves.md)，窗洞/蓝图下游见[16](16-tiny-glade-window-placement-and-holes.md)，调度见[55](55-tiny-glade-edit-rebuild-stages-and-upload.md)，身份与字节范围见[58](58-tiny-glade-input-edit-and-natural-shapes-ledger.md)。CPU地址均为RVA。

## 1. 鼠标坐标怎样形成射线

`BF2630 camera_mouse_ray`真实调用`14C9450 Ray.from_mouse_ss`。其屏幕换算是：

```text
nx = 2*x/W - 1
ny = 1 + 2*(1-y)/H
```

Y表达式保留了1像素项，不能简写成`1-2*y/H`。设本体所读两组矩阵的乘积为M，分别对深度1和0.01做齐次变换/除法：

```text
P1  = divide_by_w(M*(nx,ny,1,1))
P01 = divide_by_w(M*(nx,ny,0.01,1))
origin = P1
direction = normalize(P01-P1)
```

输出ray为24B。两组矩阵的完整相机归属、实际像素中心约定尚未恢复；W/H=0和非有限输入也没有在这一本体中找到独立防护。不能只由上述数值命名近/远裁面或还原实际镜头。

## 2. Rapier查询和UI命中是两种记录

`B4D760 wall_under_cursor`调用`9F9030 Rapier.raycast_simple`，mask实参`0x643`、距离上限f32 MAX。选定查询按mask低17位选择subworld，逐个cast；成功t成为后续查询的t上限，最后还核对源记录索引与generation。

该结果是40B：前24B保存来源枚举，`+18..+20`保存位置`origin+t*direction`，`+24`保存t；miss的首byte为17。mask各位的业务对象类型、Rapier内核predicate/solid参数未完整恢复。

普通UI放置消费另一份64B hit：

| UI hit字段 | 已确认用途 |
| --- | --- |
| `+00..+0F` | 进入旋转算术的原始数据 |
| `+10 byte` | 4项jump-table分派的tag |
| `+18 u64` | 墙/屋顶关联ID |
| `+20..+28` | 世界Vec3位置 |

`ui_place_decorator`从160B RaycastResources包取得这份hit；`14CA550 calculate_decorator_interaction_intent`的tag0调用PublicWalls.get，tag1走屋顶关联查询。该包的命中生产者仍未知，不能把40B Rapier结果直接按64B hit偏移读取。RT屋顶raw标记`0x02000000`到UI tag1的转换也没有建立。

## 3. 普通墙候选怎样投影到折线

普通墙分支在`14CA6C1`取得PublicWall，经`148CA40 → 148CFC0`把hit的XZ投影到其二维折线。对每段A→B：

```text
t = clamp(dot(Q-A,B-A)/max(length_squared(B-A),1e-8),0,1)
nearest = (1-t)*A+t*B
distance = length(Q-nearest)
```

逐段比较，只有严格更近才替换，所以等距时保留较早段。`Curve.get_approx_u_from_pos`再用该段的节点u数组插值：`u=(1-t)*u_i+t*u_(i+1)`。u被clamp到[0,1]并乘PublicWall保存的L，得到墙弧长坐标s；普通路径保留命中Y。

这与[53](53-tiny-glade-wall-footprint-input-and-curves.md)中RDP的**不截断t**不同。这里是线段最近点，那里是无限直线偏差，两个投影契约不能混用。

碰撞宽度来自记录`+30`，高度来自`+3C - +38`，用于交互辅助计算。当前普通步骤没有证明它们被缩小、自动限制到墙内部，或用某距离阈值吸到另一个窗上。

## 4. 周期包裹、越界拒绝和clamp不同

最终普通墙分支重新取u、还原XZ，并调用WallSpace.project核对s：

- 周期tag1：`fmodf(s,L)`，负余数再加L，成功返回。
- 非周期tag!=1：要求`0<=s<=L`，通过后保留原s，失败生成intent外tag4。
- 另一个project_clamp helper：非周期明确截断到[0,L]，不能借给前一project分支。

成功墙intent的`+20`为1，`+28/+2C`为(s,y)，`+18`为WallID；另存原始朝向与三个标志。上游merge、corner、balcony等辅助分支可能改候选，本轮没有将普通成功路径称为所有装饰通用吸附规则。

## 5. 墙坐标怎样提交为放置目的地

`86D66F`真实调用`14CCB30 calculate_move_dst`，该helper按intent tag1读取(s,y)、WallID，调用`92FB60 get_wall_attachment_height(s,y)`，将返回值记作H(s,y)。目的地字段为：

| destination偏移 | 内容 |
| --- | --- |
| `+00 / +04 / +08` | s、y、WallID |
| `+10` | `y-H(s,y)` |
| `+14..+1F` | WallSpaceCoord.to_world_space得到的XYZ |
| `+20 / +21 / +22` | 复制的三个raw标志 |

高度helper含常量/曲线分支，不能一概命名成terrain height；三个raw标志也不擅自称磁吸或碰撞状态。

`86D6A8–86D7CD`复制目的地构造操作，随后`14C40F0 apply_decorator_op`的place分支在`14C452A`调用`C3F110 DecoratorStorage.apply_decorator_place`。后者复制DecoratorInfo、取得容器并交给插入helper，已连到真实放置写端。插入后的modified集合、history和蓝图全生命周期本轮没有重查，下游已确认部分见[16](16-tiny-glade-window-placement-and-holes.md)。

## 6. 屋顶目标选择与表面查询

UI hit tag1经`PublicWalls.roof_entity(hit[+18])`查当前关联Roof实体，再核索引、generation、存在状态与query membership，读取Roof.is_flat继续资格判断。

`865C70 ui_move_decorator`中`86748F`实际调用`RoofTriggerVolume.get_position_from_mesh_uv`。这把[48](48-tiny-glade-roof-trigger-mesh-and-attachments.md)的未单独解码caller候选升级为真实call，但没有补通RT标记到UI hit的生产链，也没有证明普通窗允许放在任意屋顶。

## 7. 构造例：普通窗沿墙放置

下面使用自造状态，选定普通成功分支并假定其它merge/corner/balcony辅助分支不改候选，没有运行原游戏。

UI选定一扇普通窗，hit tag0、WallID=7、position=(3,4,0.2)。墙折线A=(0,0)、B=(10,0)，节点u=[0,1]、L=10。投影t=30/100=0.3，最近点(3,0)，距离0.2；u=0.3，s=3，y=4。非周期范围资格通过，墙intent tag为1。

再构造H(3,4)=1.2，目的地保存(s=3,y=4,WallID=7)、相对高度2.8及世界位置(3,4,0)。UI构造place操作进入storage写端。窗口宽1.2、高2可以作为碰撞输入，但这些已核步骤没有把它自动缩放或吸到另一扇窗。

独立周期例L=10、s=-0.2：周期包裹得到9.8；非周期project拒绝；非周期project_clamp得到0。三种结果都能保留，不能都叫吸附。

独立射线例W=400、H=200、x=200、y=101，构造M=单位矩阵，得到nx=ny=0、P1=(0,0,1)、P01=(0,0,0.01)，ray原点(0,0,1)、方向(0,0,-1)。实际相机M未确认，这不是游戏画面重放。

屋顶例关联ID7映射实体generation3/index42：当前记录generation3且组件资格通过才能继续；generation4会失败。这证明当前对象身份检查，不证明命中producer的来源。

## 8. 自研规格与剩余问题

可独立把屏幕ray、物理命中、UI目标记录、墙坐标、操作提交分开建模。普通墙用线段投影和弧长定位；周期包裹、范围拒绝与clamp各用明确契约；尺寸约束与磁性吸附另设规则，避免一个helper隐式承担所有职责。

最小续查入口为`637110`的typed UI参数包装器、`24CC460`的相邻装饰资格、`14F7500`的merge proposal和`C8F970`的插入/modified桥。它们目前只是下一步定位，不冒称算法已恢复。

未做：未运行拖动/放置场景，未恢复UI hit producer、所有磁性吸附/尺寸限制、相机完整约定、Rapier过滤和存档/history。未启动、附加或读取私存档。

风险：40B/64B hit、raw tag、墙坐标和高度偏移混用会造成错误解释；已分别保存归属。L<=0及非有限输入的上游保护仍未知，构造例不建立设备或游戏运行等价性。
