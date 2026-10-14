# Tiny Glade 墙厚、外形扩张与转角收口

本篇继续[53的二维墙线输入](53-tiny-glade-wall-footprint-input-and-curves.md)，确认厚度怎样进入普通砖实例、预制墙怎样查询扩张外形，以及近直角转角怎样单独铺砖。当前证据没有贯通一个覆盖所有自由墙的内外 offset 轮廓求解器；自交修补、任意凹凸角和窄巷缝填补仍明确保留为未知。

所有地址为同一发行版EXE的RVA。EXE SHA256为`4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`，PDB匹配身份沿用会话记录。采用有界静态fallback，没有运行游戏。原字节范围、hash、实际call、指令边界和构造例见本会话`tinyglade-wall-thickness-and-joints/findings.json`与`native-range-manifest.json`：本目录23个完整native范围、60,634B；连同复用外层共24个去重范围、82,301B，另有16个关键细范围。完整线性解码不等于全部路径语义已恢复或实际可达。

## 1. 普通砖的横向尺度有圆半径输入

外层`808800 construct_walls`在`80AD25`实际调用`1446690 WallConstructor.from_curve`。圆形厚度资格及因子在这个caller产生：

- `80ABC6`查询合法shape；指针非空且其首byte为0的路径读取`shape+0C`的圆半径r。
- `80AC01–80AC36`用0.9和3作半径插值端点，生成M。
- `80AC6B`把资格flag写到caller栈`+90`，`80AC9E`把M写到`+98`。callee prologue给出`rbp=caller_rsp−5F0`，因此分别对应callee`+680/+688`。
- `1446F17–1446F32`以0.56为base；flag非零时先乘M。

正常有限输入的易读公式是：

```text
v = clamp((r-0.9)/(3-0.9), 0, 1)
M = 0.9*(1-v) + v
base = 0.56 * (circleFlag ? M : 1)
```

发行常量是float32近似：第一个0.9为`0.9000000358`，混合端点0.9为`0.8999999762`，0.56为`0.5600000024`。这是指令实参，不能从某个演示建筑的画面反推所有墙的厚度。

随后`1448100`实际调用`fastrand::Rng::f32`；`144810A–1448125`形成：

```text
d = max(0.05, base + 0.07*(u-0.5))
```

`E02880`的实际位操作产生23bit小数，u属于`[0,1)`；所以未触发下限时，扰动位于`[-0.035,+0.035)`。这里确认的是该选定构建循环中的横向轴尺度，不宣称每砖都独立重抽，或全部墙种类都用此式。

构造例：选择圆资格真、r=0.9、u=0.5，按理想小数有M=0.9、base=d=0.504；r≥3时M=1、d=0.56。资格为假也保持base=0.56。这一半径调制已经有caller到callee的实际桥，但不是对整个自由墙轮廓执行几何offset。

## 2. 厚度沿当前墙段的垂向进入实例

`14489BD/1448A0A`对墙曲线的两个参数位置采样。令选定水平端点为A、B，有限非退化路径在`1448A4B–1448A73`形成单位弦切线：

```text
t = normalize(B_XZ-A_XZ)
axisT = (t.x, 0, t.z)
n = (-t.z, 0, t.x)
```

`1448AA5–1448AD0`构造n，`1448B85/1448B8A`把它乘d作为第三轴。第一轴由当前piece的世界宽度及额外pad缩放axisT，第二轴为piece高度乘世界Y轴。两端弦方向不是每个顶点处曲线导数，也没有在这里用两侧offset直线求交点。

`1448ED5`把第三轴写入临时四列，`1448EF4→E07FE0`去掉每列padding，复制为四个紧凑Vec3，共48B。第三列对应CPU `BrickTransform+18..+20`。`1448FDA→94C790`实际编码，再以64B步长追加输出记录，见`1448B9B–1448BD4`。

因此局部仿射贡献可以写成：

```text
P = center + axisX*x + axisY*y + d*n*z
```

贯通构造例沿用上一节r=0.9、u=0.5，并显式给合法piece世界宽0.4、高0.3，A_XZ=(0,0)、B_XZ=(2,0)。有n=(0,0,1)，第三轴=(0,0,0.504)。人为选择两个局部测试点z=−0.5、+0.5，其相对center的垂向贡献分别为−0.252、+0.252；候选通过门槛后形成64B输出实例。

**这两个测试点没有证明原mesh的顶点包络恰为±0.5。** CPU尺度d也不能直接称为最终可见全墙厚度；[39](39-tiny-glade-wall-and-timber-rendering.md)已确认GPU还有种子缩放、XZ扰动、Y修正与洞裁剪。此处只恢复CPU局部几何生产桥。

## 3. 预制外形扩张和角点单位法线是不同表示

`930110 premade_wooden_wall_outer_shape`先检查：

```text
wall[+29F] == 1
shapeTag < 2
```

不满足时返回tag2，不产生该外形。满足后复制shape参数：矩形tag1的两个全尺寸W/H各增加0.6；圆形半径增加0.3，见`93013F–93017E`。

```text
rectangle: W_out=W+0.6, H_out=H+0.6
circle: r_out=r+0.3
```

这证明存在一个受资格控制的扩张shape查询，但本轮没有把其完整渲染caller贯通；不能推广到所有木墙、任意材质或所有自由墙。

另一个`92FA30 corner_pos_and_normal_xz`只支持矩形tag1。它实际调用`DF3E10 get_point`取得角点，再调用`DF1DC0 get_corner_normal`：后者将二维轴a及其垂向b组合为`±a±b`并归一化。正常单位轴情况下：

```text
cornerNormal = normalize(±a ± b)
```

尺寸扩张不能等同“角点沿单位法线偏0.3”。构造a=(1,0)、中心(0,0)、W=4、H=2：正角点原为(2,1)，外形扩张后为(2.3,1.3)，位移长度为`0.3*sqrt(2)≈0.424264`。单位角点法线为(1/√2,1/√2)，若仅乘0.3则到达约(2.212132,1.212132)，不是实际尺寸扩张的角点。

这两个helper没有为非法或非单位输入轴提供已证统一修复规则。算例的单位轴是显式前提。

## 4. 近直角收口另铺交错砖，未证通用miter

外层`80A2B0→14299B0 add_wall_corners`是独立转角砖生产者。[37](37-tiny-glade-brick-corners-and-noise.md)已解释纵向band、宽度和洞反馈；本轮重点复核转向与厚度边界。

`1429B32→24BBFA0 find_corners`用连续边归一化点积d，传入80°和100°。有限非零边的选定条件为：

```text
d = dot(e_in,e_out) / (length(e_in)*length(e_out))
cos(100°) <= d < cos(80°)
```

这一选择不使用signed cross。prev=(0,0)、corner=(1,0)，next=(1,1)或(1,−1)，两种转向都给d=0并入选；所以它不能单独证明“凸角/凹角分类”。零长边导致非有限d而不入候选，也不等于UI必拒绝这条输入曲线。

纵向band parity交替选择出边/入边切线，沿墙空间中心偏移：

```text
u_center = project(corner_u + sign*(w/2-0.28-0.0385))
```

选定w=0.92时偏移量为±0.1415。`142B166→DEA260`将中心映回世界，`142B17E→DE9410`建立水平基；`142B1B7/142B1D0`用0.637缩放第三轴。此处是选择一侧边方向并交错摆砖，不是将两侧offset线交点当miter，也没有在这一段实现统一bevel/圆角选择。

每次emit还写20B tag2墙空间占用区，`142B5AA`把这些记录extend进洞storage。它说明转角砖能反馈排砖避让范围，不是全局XZ轮廓完成了布尔合并的证明。

## 5. 闭合投影与小碎片门槛各有作用域

`DEA610 project_clamp`对rawtag1用`fmod(u,L)`，负余数加L；其它正常L≥0分支夹到`[0,L]`。L=4、u=−0.1/4.1时，前者为3.9/0.1，后者为0/4。转角caller还按`wall+258!=2`启用首点接续检查；结合前37的±L洞副本，这是已证的墙空间首尾处理，不能替代完整闭环offset验证。

普通piece在`1448C3B–1448C61`要求宽、高为正，世界宽小于0.03时跳过。raw`4F7=false`另有小于0.184跳过，以及height>width时缩高并移动Y中心的分支，见`1448D9D–1448DD6`：

```text
H_new = W
centerY_new = centerY - 0.5*(H-W)
```

构造W=0.2、H=0.5、centerY=1，得到H_new=0.2、centerY_new=0.85，下沿仍为0.75。W=0.025则在普通0.03门槛被跳过。转角piece另有严格width>0.1及原band height>0.1条件；不能把这些数统一命名为“墙最短边限制”。

转角`142A834/142A8DD/142A987`实际调用`146C450 resolve_hole_overlap`操作40B MyBrick deque；本轮仅核到正尺寸gate、contains分类及局部处理，完整分类表与变形字段插值仍部分未知。这是墙空间u/Y洞处理，不能据此宣称会消除世界XZ自交，或填平两栋建筑之间的任意窄缝。

## 6. 更新边界、未做与风险

同一普通墙外层`80A54A`实际调用`SparseInstanceBufferWriter.clear<BrickTransformSsbo>`，随后本轮producer编码并追加新记录。完整局部失效与上传职责沿用[45](45-tiny-glade-shared-invalidation-and-rebuild.md)。clear和append存在不保证所有失败分支原子替换，也不证明GPU已在同一帧消费。

本轮未做：启动或附加游戏、读取私人存档、修改原制品、安装/config/Git写、构建及场景验证。独立算例没有证明float32逐位复现或性能等价。

剩余风险是覆盖边界：完整中心线到内外offset轮廓、miter/bevel/round join、offset自交消除、窄巷缝规则、所有形状资格与最终mesh包络均未恢复。现有证据能解释局部墙厚和近直角收口；不能用常见offset算法补成发行版事实。
