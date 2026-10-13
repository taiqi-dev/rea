# Tiny Glade 屋瓦可见性、层级深度与屋面片元深度

本篇继续核对“建筑相交后的屋顶怎样消失”。选定shader中确认了屋瓦的局部裁片元、实例视锥筛选、前后可见性位与层级深度图筛选，另确认屋面材质会写FragDepth。它们各自成立，但还不能组合成已经恢复的完整建筑间网格布尔。

本屋顶边平面生产见[42](42-tiny-glade-roof-edge-planes-and-seams.md)，三角形与装饰查询见[48](48-tiny-glade-roof-trigger-mesh-and-attachments.md)，CPU重算选择见[50](50-tiny-glade-roof-edit-messages-and-regeneration.md)。固定身份、模块摘要和验证见[52账本](52-tiny-glade-roof-and-vegetation-followup-ledger.md)。

## 1. 先固定这次实际审计的范围

本轮完整结构解码并检查资源读取的是3个precomp、11个内嵌SPIR-V模块：

| 文件 | 内嵌模块 | 本篇用途 |
| --- | --- | --- |
| nani_instanced_roof.precomp | 4，vertex/fragment两个变体 | 瓦实例字段、wall identity、局部裁片元 |
| nani/cull_and_bucket_roof_tile.precomp | 3，compute | 先前可见筛选、HZB筛选、太阳视图级联筛选 |
| nani_roof_floor.precomp | 4，vertex/fragment两个变体 | 屋面、局部材质深度与输出 |

每模块的resource audit记录变量ID、storage、AccessChain及Load位置，不只搜索资源名字。某些变体声明了材质资源但没有实际Load，也保留为“声明但未读取”。

这11模块中没有找到全局墙形状、另一屋顶完整轮廓或RT加速结构的读取。瓦vertex的wall_identity_data读取是当前wall slot→identity的映射（原文件`10133–10313`），屋面vertex也有同类映射（`6421–6649`）。读取本对象身份不能直接解释成相交查询。

这是**选定11模块的有界否定结果**。CPU可以在生成实例时预计算某些相交信息，其他渲染模块也可能承担不同职责；本轮没有据此断言游戏完全不用建筑间几何关系。

## 2. 局部裁片元与全局遮挡分别在哪里

屋瓦fragment的两个变体各有两处 `OpDemoteToHelperInvocation`。本轮配合既有数据流确认其选定裁片元职责是本瓦clipping plane和匹配当前wall slot的dormer洞链。精确plane、边界和天窗距离场见[05](05-tiny-glade-seams.md)、[42](42-tiny-glade-roof-edge-planes-and-seams.md)，这里不重复或把它改名成建筑间Boolean。

demote表示该片元成为helper invocation，不应将其等同于CPU已经删除了瓦实例或修改了triangle拓扑。实例还可能通过下一节筛选；最终像素还受渲染pass的深度/附件状态影响。

屋面fragment另有三处demote及材质分支。审计没有发现scene depth采样；它下面读取的`depth_hit`来自本片元FragCoord.z。不能把名字中的hit解释成一条射线击中另一栋建筑。

## 3. 屋瓦compute的三个筛选模块

三个模块的local size均为`64×1×1`。它们读实例位置/尺度等字段构造包围球和相关metadata，再进行不同可见性处理。

第一模块（原文件start=208）读取current_view和prev_visibility_bitmask，通过视锥/包围球资格及先前可见位决定送入filtered instance/bucket。原文件`8300–8868`有位读取与相应bucket输出，**没有HZB纹理读取**。

第二模块（start=10981）增加globalParams中的HZB尺寸和hzb_tex，实际有四次OpImageFetch。原文件`20113–22005`确认：

1. 从投影包围范围构造纹理坐标，按尺寸clamp。
2. 以包围范围的最大像素跨度计算mip，使用`max(0,ceil(log2(max(极小正数,跨度))))`。
3. 把范围两端坐标转换并按mip右移，取四个角的HZB值。
4. 用FMin合并四个值，然后作下述倒数比较。

设四次读取为`h0..h3`、合并值`h=min(h0,h1,h2,h3)`。设当前视图的`clip_to_view`矩阵读取的第3列第2分量为`P3.z`，实例球心在view空间的z为`z`，当前包围半径为`r`。选定路径的保留判定是：

```text
d = 1 / (h * (-P3.z))
visible = (z + r > d)
```

`21725–21941`确认min、矩阵字段、取负、乘法、倒数和严格大于；`936`确为view z加半径。`ViewConstants`的member 1实际名为`clip_to_view`，即裁剪空间回到视图空间的矩阵，不能称为正向投影矩阵。这里的带符号view z和矩阵值不能直接换成正数世界距离，h也不能脱离投影约定当成米制深度。完整投影包围范围和所有退化分支本篇仅部分解释。

visible成立后，原文件`22033–22505`对next_visibility_bitmask做atomic OR。若同一位之前未可见，才在这一路追加filtered instance/meta及bucket histogram。因而“本次可见”和“本阶段新增到draw list”仍是两个条件；不能简单把每个visible结果计成一次独立新绘制。

第三模块（start=24642）读取sun_views的三个级联视图及HZB三个layer，对每层分别做相关范围/资格检查。它有12次OpImageFetch，即每layer四次；`34526–43218`的三个段均用**FMax**合并角值，选定保留比较为一个变换后的深度标量`q < max(h0..h3)`，并分别送入相应filtered bucket。

这里保留q为该模块产生的标量，不额外将其命名为世界距离。主镜头的min＋倒数比较与太阳视图的max比较不同，不能套成一个通用min规则，也不能由三个layer推导CPU实际提交顺序。

## 4. 屋面FragDepth是局部材质结果

`nani_roof_floor.precomp`主fragment从文件7330开始。ExecutionMode声明 `DepthReplacing`、`DepthLess`，输出变量有BuiltIn22（FragDepth）；`80758`实际OpStore写入最终选择的深度标量。

输入`depth_hit`在`23510–23546`从BuiltIn15（FragCoord）取z。之后石/木等材质路径读取自身height纹理、做局部高度/视差计算。两段代表性选择在`49486–49786`、`78450–78646`：比较材质计算的候选深度和输入z，候选较小时选候选，否则选输入z；再经Phi合流写FragDepth。

对这些选定分支，可以表达为：

```text
depthCandidate = 当前材质高度/视差路径的结果
depthOut = depthCandidate < FragCoord.z ? depthCandidate : FragCoord.z
```

不是把所有材质内核都简化成这一行，也没有恢复所有纹理步进。关键区别是：输入z来自自身片元，候选来自本地材质；该模块没有读取另一建筑的scene depth。

DepthLess是shader声明，不自动等于pipeline用了某个Less/Greater compare操作。CPU render attachment、深度compare state及pass先后还没有接通。因此“这条指令写了深度”成立，“最终与另一建筑谁遮住谁”仍需要实际pass状态或运行证据。

## 5. 构造例：HZB保留与材质深度

以下是选定公式的自造输入演算，没有运行shader，也不建立实机深度约定。

主镜头四角读值得`{0.6,0.5,0.7,0.55}`，min=0.5。构造`clip_to_view`字段`P3.z=0.2`，则`d=1/(0.5×-0.2)=-10`。view z=-8、r=0.5时，`z+r=-7.5>-10`，这段判定保留；改为view z=-12则`-11.5>-10`为false。严格相等不通过该比较。

若保留的瓦以前可见位为1，这一路仍写next位，但不进入“以前未可见”的追加分支；以前位为0时才在这一路追加。前一阶段是否已生成列表，需另外的调度关系，例子不补写。

太阳视图四角`{0.2,0.4,0.3,0.5}`合并max=0.5。构造q=0.3时`q<0.5`为true，q=0.6时为false。这不是把主镜头的倒数公式替换到太阳模块。

屋面自身FragCoord.z=0.6，当前材质候选深度=0.55，则该选择输出0.55；候选=0.65时保留0.6。这个结果没有使用任何另一建筑的轮廓或scene depth输入。

## 6. 自研可借鉴的职责划分

可以独立把几何规则、实例可见性和材质深度分成三个契约：几何规则生成局部构件与裁面；compute按镜头/深度层级缩小提交集合；fragment处理细节开洞和材质局部深度。最终对象间像素遮挡由明确的pass/深度状态决定。

这是独立设计建议，不能反过来证明原游戏的所有建筑相交都靠深度测试。要补全该问题，剩余关键是实例裁面是否另有CPU生产者，以及这些材质实际进入哪个pass、用什么depth compare和附件。

未做：未启动/附加、未GPU抓帧，未恢复整个renderer、HZB构建和跨pass同步，未执行SPIR-V语义验证器或实际shader测试。

风险：有界资源审计不能覆盖未选模块或CPU预计算；投影深度约定、特殊输入和shader声明不能替代运行pipeline状态。当前建筑间可见边界仍部分回答，未交付完整布尔或接缝重建算法。
