# 掘地求财：挖掘、存档与性能

扩展内容专题：[Mod、Workshop 与 DLC](mod-workshop-and-content-loading.md)。区分官方故事读物、引擎资源包能力与尚未建立的用户内容加载链；运行未做。跨游戏对照及 demo 方案见[122](../122-mod-workshop-dlc-comparison.md)、[123](../123-steam-workshop-and-dlc-design-for-demo.md)。

性能续查：[25：空闲Tick与LOD准入](25-idle-tick-and-lod-admission.md)，补空完成/提交队列的早退、invoker时间门与变化比较；静止仍有轮询，未运行或测帧时。

最新续查：[24：碰撞盒来源与invoker](24-collision-box-producers-and-invokers.md)，补组件半径、坐标盒及自动相机条件；明确更正23：专用碰撞盒有LOD 0前置门，不能据此给LOD 3碰撞资格。

最新续查见[23：MainLevel 网格、LOD 与碰撞配置](23-mainlevel-mesher-lod-and-collision-config.md)：正常初始链选择 Marching Cube、开启过渡和碰撞，关卡把可见块碰撞上限改为 LOD 2；该门与专门碰撞盒分支分开。实际 chunk 和物理接触仍未运行验证。

最新续查见[22：过渡三角形与碰撞归属](22-transition-triangles-and-collision-ownership.md)：普通／过渡索引条件性合入同一输出buffer，被碰撞section的cooker读取；实际mesh配置、Chaos后态与接缝接触仍未运行验证。

最新续查见[21：LOD相邻块与过渡接缝](21-lod-seams-and-transition-mesh.md)：六方向邻块／层级门接到mask、过渡任务及条件构网；过渡三角形的碰撞归属和实际算法配置仍未闭合，运行未做。

最新续查见[20：部分恢复后的LOD、网格与碰撞](20-partial-restore-lod-mesh-collision.md)：变化盒补正为旧树终端盒＋匹配恢复的新叶盒，接到默认LOD／renderer任务及mesh／Chaos碰撞接受门；placeable独立通知与实际动态类型仍未闭合。运行未做。

最新续查见[19：清旧后的失败与回滚边界](19-post-clear-failures-and-rollback-boundary.md)：所见恢复链没有置错字节的生产者，部分资源跳过仍可true；旧根已销毁，上层无条件请求LOD变化盒更新。畸形输入的异常／后态仍未运行验证。

最新续查见[18：加载失败与旧世界保护](18-failed-load-and-old-world-protection.md)：空压缩数据／明确解压失败／所见序列化错误重置可被-1深度门挡在清旧前；有效深度进入载入后先换根，后续失败未见回滚。运行未做。

最新续查见[17：原生CDO构造与模式初值](17-native-cdo-construction-and-mode-state.md)：本类构造回调接到两处模式零写；静态flags关闭CDO自身普通属性复制门，并补核PostInitProperties。最终值仍有条件，运行未做。

最新续查见[16：生成类属性链接入口](16-generated-class-property-link.md)：本作134项属性表接到主枚举类链，StaticLink(false)经实际虚表分派到LinkInternal，为一字节复制提供正常链接依据。CDO最终值与actor实际初始化仍未观察。

最新续查见[15：模式枚举的复制宽度](15-property-copy-virtual-target.md)：描述符接到Enum/Byte属性，链接后置bit30并确定一字节memcpy；Config位仍为零。默认源最终值和actor实际分支仍未运行验证。

最新续查见[14：其它模式写端与默认复制](14-other-mode-writers-and-default-copy.md)：模板/CDO 到 InitProperties 的属性复制补上 ctor 之后的状态来源；所查同偏移候选经接收者与指令边界筛选。实际最终 CDO 值与所有写者仍未穷尽，运行未做。

最新续查见[13：材质属性与配置加载门](13-material-property-flags-and-config-gates.md)：两个模式属性的本作flags不含Config，普通LoadConfig在bit14门跳过；其他主动写入仍未穷尽，运行未做。

最新续查见[12：初始材质权威与覆盖](12-initial-material-authority-and-overrides.md)：关卡actor模板精确指向原生VoxelWorld CDO，首次创建和重建renderer均从当时world状态取值。基类/CDO配置与其他脚本写端尚未穷尽，运行未做。

本机《A Game About Digging A Hole》走的是 **Unreal + Voxel Pro 的三维体素路径**。目前已从匹配的 EXE/PDB 和解码后的游戏资源确认技术栈，逐项追到值场编辑、受影响区域筛选、网格与碰撞任务，以及保存快照和队列。游戏的实际资源调用与插件本身的能力在各页分别标明；未运行游戏或测量 FPS。

最新续查见[09：碰撞结果接受门](09-collision-result-acceptance.md)：旧 cook 即使已入队，仍须通过当前 cooker 编号相等等检查，再进入 BodySetup 交换与物理状态重建。[08 的 Mixed 分派](08-mixed-handler-submission-chain.md)和[07 的初始配置条件](07-material-slots-and-handler-selection.md)继续适用；实际加载、覆盖与物理时序未运行验证。

新增[10：地形材质到可见 section](10-terrain-material-to-sections.md)：区间选择、LOD2/3/4 演算、材质包装与 Mixed 的 Clustered 提交已接通；每个 chunk 的实际模式、LOD 和最终 shader 仍未观测。

[11：chunk 材质模式](11-chunk-material-mode-selection.md)进一步补上配置到网格模式字节的生产者，约束主关卡初始条件下的单材质分支，并区分插件的索引分组能力。

| 要回答的问题                     | 阅读入口                                                              | 已有证据与边界                                                             |
| -------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| 铲子怎样改变地形，洞怎样变成模型 | [挖掘与局部重建](01-excavation-and-local-rebuild.md)                  | 体素编辑公式、脏区、mesh 与碰撞链；游戏具体工具分支另列                    |
| 挖了之后怎样存下来、怎样恢复     | [保存与一致性](02-save-load-and-consistency.md)                       | 修改叶块快照、zlib、加载重建、游戏保存请求队列；持久化保证不由异步名称推断 |
| 为什么能持续挖，哪里可能变慢     | [性能与独立设计](03-performance-and-independent-design.md)            | 局部更新、距离优先级、后台任务和提交预算；实际耗时与长时间挖掘为 Not Run   |
| 矿物外观与地形是什么关系         | [矿物网格、摆放与移除](04-mesh-materials-and-ore-presentation.md)     | 实际蓝图布点、组件、网格选择与煤网格包身份；材质槽和露出判定未知           |
| 连续挖掘如何处理任务与增长       | [任务生命周期与性能增长](05-task-lifetimes-growth-and-performance.md) | 续查任务替换、失效和数据保留边界；与实际游戏配置及计时分开                 |
| 换电脑后如何重新核对             | [证据身份与复核](00-evidence-and-reproduction.md)                     | Steam build、摘要、PDB 匹配、容器范围和自写读取工具                        |

最值得借鉴的是**保存逻辑地形、重建派生网格**。插件保存的是被修改的体素叶块及附加对象，单叶块值/材质各有 4096 个元素；未编辑部分继续依赖生成器。它每次整理当前全部已修改状态，属于稀疏快照，不是每次铲击追加一条日志，也不能据此认定磁盘增量写入。快照期有全域数据锁，随后序列化和压缩；异步入口不会让这个锁消失。

实际游戏连接已恢复：`Dig` 在一个条件分支中进入表面候选筛选、强度与衰减处理，再异步编辑体素；两种爆炸蓝图调用球形挖除。主存档采用 `VoxelComplexController_SaveExample`，其 `Save` **同步**抓取并压缩体素，再经矿物管理对象回调补入物件位置、种子和玩家状态，之后走异步 slot 写入。因此本作“异步写盘”和“异步体素快照”需要分开理解。具体分支、参数来源及一致性边界见 01、02。

局部重建则把“改变地形”和“显示新洞”分成不同阶段：编辑值场后，以影响盒找重叠 chunk，后台计算 mesh，再消费结果和更新组件碰撞。原生实现还有 invoker 距离优先级和提交截止时间；具体游戏参数、长尾成本与最坏帧耗需运行证据。

```mermaid
flowchart LR
    A[编辑体素逻辑状态] --> B[按影响盒筛地块]
    B --> C[后台生成网格]
    C --> D[消费完成结果与碰撞更新]
    A --> E[修改叶块的完整快照]
    E --> F[序列化与 zlib 压缩]
    F --> G[游戏保存对象与存储调用]
```

图中上游编辑、重建与快照是原生路径概要；游戏资源如何接入及存储调用的具体分支以 01、02 为准，不表示所有阶段同步或每次挖掘都保存。

与前面三款的区别可按“状态是什么”理解：

| 游戏                                    | 本轮相关研究中的状态                       | 适合借鉴的模块                         |
| --------------------------------------- | ------------------------------------------ | -------------------------------------- |
| [Tiny Glade](../README.md)              | 连续建筑轮廓、构件关系、地形高度与派生几何 | 墙屋顶、开洞、接缝与局部构件重建       |
| [Sandcastle](../sandcastle/README.md)   | 规则网格单元的沙水状态与高度表面           | 流动、侵蚀沉积、铲挖与堆积、水面显示   |
| [SUMMERHOUSE](../summerhouse/README.md) | 预制建筑块、格点、前后层次和组合规则       | 小件拼装、邻接替换、解锁与调色         |
| 掘地求财                                | 三维体素密度/材质、修改叶块和派生网格      | 地下空洞、局部重建、保存恢复与性能调度 |

对自研 Unity 沙盒，建议把地形数据所有者、网格/碰撞任务和保存队列分开：连续编辑合并脏块，任务提交前校验版本，保存记录请求版本与完成版本，并保留可恢复的旧快照。这是独立设计建议；原作是否具有所有这些保障，仍以已恢复证据为限。
