# 四款游戏：颜色覆盖、碰撞归属、绘制预算与投影消费

接续[107](107-four-static-art-transitions-seams-and-pixel-grids.md)的四个静态断点。**沙堡找到了配置到六次全局颜色写入，且排除了“材质保存同名键就优先”的推断；掘地求财证明条件成立时过渡索引进入碰撞输入；Tiny Glade把距离分类接到网格索引与间接命令，并补出单次命令上限实参；SUMMERHOUSE把矩阵接到native提交与主体vertex消费两端。**运行验证继续全部 **Not Run**。

| 专题                                                                                                 | 新闭合的静态链                                                                                                                                                                            | 剩余边界                                                                                                                   |
| ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| [沙堡24：全局颜色与覆盖](sandcastle/24-global-color-writers-and-order.md)                            | 当前Configuration的Ground四色、Water两色，RGB先GammaToLinearSpace再SetGlobalColor；两个运行门通过时Ground→Water。Shader605／587属性前缀均不声明这些颜色，同名材质保存值不能判为覆盖赢家。 | 场景配置初值、其他同名写端／PropertyBlock、跨FixedUpdate／Render的顺序及最终cb0上传值仍未知。                              |
| [掘地求财22：过渡三角形碰撞归属](digging-a-hole/22-transition-triangles-and-collision-ownership.md)  | GetMeshesToBuild分别挂普通／过渡buffer；Basic合并两套索引到同一ProcMesh主索引，碰撞section被cooker收集，CreateTriMesh从该索引读取三角形。                                                 | 要先满足结果令牌、有效材料／buffer、section碰撞位及cook提交门；实际mesher、Chaos最终形状与真实接缝接触未观察。             |
| [Tiny Glade108：距离分类消费者与命令预算](108-tiny-glade-distance-meta-consumers-and-draw-budget.md) | meta替换排序编码低10位成为mesh_index；生成器取atlas部件、写20 B间接命令与实例indirection。fine回调的单次最大命令参数为条件性1024，或表值向上对齐32。                                      | 跨graph物理绑定、RoofTile三份资源的atlas保序、表值生产者、实例池／列表容量和真实帧draw数仍未知。                           |
| [SUMMERHOUSE23：最终投影与像素对齐](summerhouse/23-final-projection-and-pixel-alignment.md)          | 所见初始化选择Execute路径；CameraData保存V/P/J，AA0使J=I，Base无Overlay m00修正；提交止于Injected接口。Shader622两个前向vertex读unity_MatrixVP并直接写clip位置；像素化pass本身不改矩阵。  | native矩阵／viewport／常量填充、其他pass或动态组件覆盖仍未穷尽。所读链没有找到像素锁，不等于全游戏不存在，也不是实测抖动。 |

## 四个条件演算的意义

沙堡不再用Material残留颜色假定global输赢。构造Configuration干沙蓝、湿沙绿、沉积红，运行门通过且无其他覆盖时，W=0.0105可先得干湿中点(0,0.5,0.5)，再以沉积权重0.1得(0.1,0.45,0.45)；这是CPU配置→global→所选片元公式的条件演算，不是实际场景RGB。

掘地求财沿用LOD2／LOD1正X例：方向mask0x02触发过渡构网后，若renderer接受且相同材料的过渡buffer有效，合并时过渡索引加输出顶点基数，与普通索引进入同一主buffer。组件section有碰撞位时，该buffer才进入Chaos输入。几何属于碰撞输入已答，是否在实际接缝保留并产生连续接触另证。

Tiny Glade两片瓦的旧编码102584／103822及meta0／1，被填充器改为102400／103425，生成器拆得原实例100／101和网格号0／1。若两atlas部件有效，可形成两条各一实例的命令；具体网格名不能只按RON顺序命名。另构造表值x=37时，所见fine分支的最大命令参数M=64；M不表示实际有64条命令，也不限制每条命令的实例数。

SUMMERHOUSE构造非XR、Base、AA0、普通矩阵／viewport且低目标444×250：相机矩阵直接传到native提交接口，所选vertex末段无clip像素取整。若绑定矩阵使某顶点clip.x从0变1/444且w=1，连续viewport映射会从222变222.5；是否跨越覆盖阈值或在屏幕上跳边仍未运行，不能用此例代替光栅结果。

## 如何继续而不重复已答部分

沙堡下一入口是profile／Configuration序列化布局和绘制常量上传；掘地求财只剩实际mesh配置、输入门和Chaos后态，普通／过渡索引是否合并这一点不需再重复追；Tiny Glade需要graph句柄和atlas建表的明确赋值，而不是再读70或1024常数；SUMMERHOUSE需要native矩阵／状态与其它真实覆盖者，不能再由相机脚本无Round就作全局否定。旧槽23、尾值3、等待／取消和调度悬案保持各自原范围，本轮未顺带重试。

## 证据与验证范围

新普通raw在ignored `.cache/procedural-modeling/static-consumer-followup/`，四游戏分目录；SUMMERHOUSE的REA managed完整Evidence另存，不混同普通CIL、DXBC或PE/PDB文本。四个精确安装输入与本次调查摘要授权沿用；本轮REA重新记录所用URP DLL身份，其余自有读取器没有新算目标摘要。公开API仅辅助解释契约，具体版本／引用和未知写在专题；原程序意图、画面及性能均不由名称推断。

本轮检查包括当前颜色字面量／属性前缀复读、过渡索引到碰撞的PE锚点、五份SPIR-V消费程序、单次命令参数ABI、矩阵CIL与当前50716 B Shader对象／两vertex重读，以及算例、拒绝覆盖／错误profile、UTF-8／围栏／链接／Python语法与仓库文档检查。实际结果以同轮`focused-validation.json`、`document-validation.json`和仓库／交付回执为准。没有游戏／Unity／GPU／目标函数执行、附加、私人存档、安装、鼠标或前台操作；真实颜色、碰撞、帧draw数量、像素稳定及帧时均 **Not Run**。
