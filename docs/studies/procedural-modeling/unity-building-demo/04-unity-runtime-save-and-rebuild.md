# Unity实现结构、状态所有权、重建与存档

本篇规定[最小demo](README.md)的独立工程结构。当前仓库是REA研究工具，尚无这个Unity工程；下面的目录和类名是实施目标，不是已存在文件。

## 1. 工程位置与依赖

后续源码工程目标放在本case study的`unity-building-demo/UnityProject/`，与规格同目录关联；不将Unity游戏代码接入REA CLI/MCP运行模块。

```text
UnityProject/
  Assets/BuildingSandbox/
    Runtime/Domain/        逻辑定义、命令、几何分格、火水与损坏规则
    Runtime/Unity/         Mesh/Collider/Prefab/Light适配与输入/界面
    Runtime/Persistence/   版本化JSON DTO、校验及文件读写
    Editor/                场景创建、程序占位和资产验收工具
    Tests/EditMode/        纯规则与几何测试
    Tests/PlayMode/        碰撞、生命周期、真实操作和读档测试
    Scenes/               BuildingSandboxDemo.unity
    Art/Approved/          通过验收的自有资源
    Art/Drafts/            未验收草稿，第一版不依赖
  Packages/               manifest与锁文件
  ProjectSettings/        完整编辑器版本及项目设置
```

实施前按Unity项目bootstrap工作流检查项目规范、asmdef和验证入口；复用已有可用编辑器。固定`ProjectVersion.txt`完整版本以及URP/Input System/Test Framework/Newtonsoft JSON依赖的实际锁文件；无法使用编辑器时保留具体阻塞，不在本轮装软件或把API文档版本当项目版本。

第一版普通MonoBehaviour/CPU Mesh，不引入ECS、GPU几何生成、第三方Boolean库或网络框架。Domain不引用UnityEngine；Unity适配层单向依赖Domain。数据传递使用小型数值结构/DTO，不为了四面墙增加通用插件框架。

Unity源码、场景文本和规格可纳入正式版本控制；Library、Temp、Obj、Build、用户存档和本机日志不提交。本次没有模型二进制或完整Unity项目。以后AI二进制资源的存储/分发需符合REA仓库规则和资产许可，不把研究原资产带入提交。

## 2. 最小场景与类职责

| 类/组件 | 职责 | 不拥有的状态 |
| --- | --- | --- |
| BuildingWorld | 建筑定义、附件、Piece和DamageCell的唯一权威集合 | 不存Mesh/Collider/Light |
| BuildingCommandService | 校验、命令序号、业务提交、dirty与诊断 | 不直接改场景Renderer |
| WallGeometryBuilder | 02的分格/占用/面/碰撞矩形纯计算 | 不创建GameObject |
| RoofGeometryBuilder | 双坡和山墙几何描述 | 不决定燃烧/损坏 |
| ElementSimulation | 03的0.1秒规则与状态事件 | 不从粒子数量推断火势 |
| RebuildCoordinator | 合并dirty、生成新结果、支持清理及统一发布 | 不把旧cache作为逻辑定义 |
| BuildingView / WallView | 生成Mesh、BoxCollider、房屋各子节点 | 不反写开口列表 |
| AttachmentView | 窗/灯外观、选择代理和Point Light | 不独立管理权威Cutout |
| DemoInput / DemoPanel | 工具选择、候选预览、命令发送与状态展示 | 不直接扣完整度 |
| SaveService | DTO校验、保存、两阶段加载和错误结果 | 不恢复GameObject InstanceID |

SceneRoot下放唯一World/Coordinator、CameraRig、Input/Panel、GeneratedBuilding、Effects。GeneratedBuilding下分Walls、Floor、Roof、Gables、Pieces、Attachments；每个根带owner ID和published revision，方便查旧产物。

## 3. 数据契约

| 记录 | 最小字段 |
| --- | --- |
| BuildingDefinition | BuildingId，width/depth/height/thickness，roofRise/eave，stableSeed，revision |
| WallDefinition | WallId，BuildingId，side，material；O/e/n/L/H由建筑参数派生 |
| Attachment | AttachmentId，BuildingId，WallId，kind，assetKey，u/v，openingSize（Window/Door）或lampEnabled |
| PieceDefinition | PieceId，BuildingId，kind，wall-relative anchor/length，material |
| DamageCell | WallId，iu/iv，integrity，fuel，temperature，wetness，burning，destroyed |
| PieceCondition | PieceId及同样的火水/完整度状态 |
| Cutout（派生） | ownerId，kind，WallId，u0/u1/v0/v1 |
| GeneratedGeometry（派生） | ownerId，sourceRevision，vertices/normals/UV/indices，colliderRects |
| WorldControl | schemaVersion，lastProcessedCommandSequence，simulationTick，积累但未消费的simulationRemainder |

初始完好DamageCell可隐式存在，仅保存发生状态变化的稀疏记录；原点/格尺寸在schema中固定。Destroyed是权威状态，integrity必须为0、burning=false。浮点必须有限，湿度/燃料/完整度在范围内；重复ID、未知材料/类型、悬空宿主或越界窗不能通过加载校验。

逻辑ID是稳定字符串，Unity对象引用/InstanceID只作运行适配索引。宿主坐标与样式改变不会重新分配墙ID。第一版stableSeed预留给可重复美术布局，火水规则本身不使用随机数。

窗口净尺寸来自已批准类型目录；若存档带尺寸，则必须与对应类型契约一致。资源缺失可以使用标明诊断的程序占位；不以加载错误模型的bbox重写逻辑开口。

## 4. 命令顺序和一次更新

本地输入分配严格递增sequence。service只接受`lastProcessed+1`；较小/相同序号返回Duplicate，跳号返回OutOfOrder。已处理但被拒绝的命令也消费序号并记录原因，业务状态不变。保存包含lastProcessed，加载后输入分配器从下一号开始，旧输入队列清空。

这个规则用于单机重复输入/测试回放，不宣称是联网可靠投递协议。不能拿同一sequence换payload重试新操作。几何revision只因成功的业务变化递增，拒绝命令不标脏几何。

主循环选择：输入收集→按序处理命令→消费固定0.1秒仿真步→失效附件清理→合并dirty→重建/发布→刷新状态面板。仿真暂停时不积累仿真时间；实时渲染仍可继续。连续拖动预览不写World，松开才提交移动，减少不必要全墙重建。

首版全在主线程同步执行，一次生成没有跨帧yield。RebuildCoordinator按以下顺序工作：

1. 读取已提交World的确定快照和revision。
2. 派生开口，计算Solid；执行支持失效的有限移除循环，再计算最终几何。
3. 在未激活的staging节点创建新Mesh、collider、附件；校验索引、有限坐标、支持和owner。
4. 成功后禁用旧碰撞/选择节点，切换新节点与published revision，再释放旧产物。
5. 失败保留旧完整画面/碰撞，显示BuildFailed(owner,revision,reason)并阻止下一业务命令；可以Retry或Reset，不能假装新World已可互动。

首版若几何生成失败，Coordinator还保留提交前可回退的World快照并回退本次业务变化/仿真步，revision和simulationTick不前进；序号作为处理记录仍消费。失败原因必须可见。Retry用同一业务输入的新序号或重试构建当前有效状态，不能再次扣损伤。

因此成功回执CommandApplied在发布成功后才返回；前面“提交”指本轮候选状态，失败时不对外报成功。simulationRemainder也只在仿真步发布成功后扣除，失败暂停并保留待消费时间。纯温湿变化无需新几何，但同样验证状态后发布。WallView的Mesh/collider使用同一最后构建revision；其它未标脏owner可以保留旧revision，不因全局某处变化被误报过期。

首版不做异步Jobs。以后若引入异步，结果sourceRevision不等于当前revision时必须释放而不发布；需要新增并发测试后才能切换。

## 5. dirty范围与重复重建

| 变化 | 必须更新 |
| --- | --- |
| 移窗/删窗/新增窗 | 宿主墙Mesh+碰撞+支持、对应附件视图 |
| 挂灯/开关灯 | 灯视图、Light、选择代理；通常无墙几何 |
| 温湿/部分完整度 | 状态/材质/火焰表现；不每0.1秒重建整墙 |
| 单元首次Destroyed | 宿主墙与支持、被移除附件、相关表现 |
| 梁Destroyed | 梁视图/碰撞/火焰；不自动坍塌屋顶 |
| 屋顶升高 | 屋面/山墙；墙永久damage不变 |
| 房屋宽深高 | 四墙、楼板、屋面/山墙、梁布局、挂点与支持 |
| 加载/Reset | 全部生成产物，分别使用恢复或初始逻辑状态 |

dirty为集合，同一轮多命令合并一次。可从整栋重建做出正确版本，再实现上表局部范围；局部优化不得改变生成结果和损坏身份。

临时生成Mesh、材质实例、GameObject和运行Light由创建它的View拥有。删除前先禁用碰撞/Light；Destroy的实际释放可能延后，不能在同帧射线里留下有效旧collider。共享导入mesh/material不由某个附件删除；颜色优先用属性参数，避免实例无界增长。测试按完成帧检查存活数量，不仅数Hierarchy名字。

## 6. 存档与两阶段加载

保存文件为demo自己在`Application.persistentDataPath`下的`building-sandbox/world-v1.json`，不读其它游戏目录。该路径用途由[Unity persistentDataPath](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Application-persistentDataPath.html)说明。首次保存先显示实际目标路径；测试用独立测试目录，保护已有demo存档。

使用版本化DTO和列表，不序列化UnityEngine.Object、Mesh或scene object引用。Persistence选用锁定的[Unity官方Newtonsoft JSON包](https://docs.unity3d.com/Packages/com.unity.nuget.newtonsoft-json@3.2/manual/index.html)，在同一边界以JSON树检查必需字段存在、类型、重复属性及版本，再转为DTO；数值/引用和Destroyed不变量继续校验。Domain不依赖该包。本方案不使用自动默认缺字段的结果代替有效存档，也不维护第二份JsonUtility存档表示。

保存过程：捕获一致World快照→验证DTO→写同目录临时运行文件→完整读取/校验→在平台支持条件下替换目标并保留上一份备份。失败报告操作和路径，不覆盖已验证旧存档；替换方式须在目标文件系统验证，不宣称跨平台事务保证。

加载过程：读文件→检查schema/字段/引用/范围→构造候选World→准备所有新几何与附件→全部成功后发布。任一步失败保留当前World和视图，不能先清空场景再尝试读档。加载后不自动跑一次仿真步；恢复simulationTick及remainder，第一次Resume才继续。

保存DamageCell包括冷却/燃烧中的状态和域外历史损坏；保留已毁Piece记录。Cutout、World空间姿态、Mesh、碰撞和Point Light全部由逻辑数据重新派生。移除的灯/窗不再在Attachment列表里，加载不会重新出现。

### 构造例：破洞存档后改屋顶

保存中north:(8,3)为Destroyed、integrity=0、lamp-01已移除。加载先形成候选World，再生成该墙破洞及当前窗，灯集合为空。将roofRise从1.2改为1.5只增加屋顶revision/dirty，不触碰DamageCell；north破洞与无灯状态保持。

## 7. 未做与风险

未做：没有Unity项目、asmdef、场景或实际JSON保存器；这些都是待实施契约。没有运行Editor/Test Runner或REA项目构建。风险：同步重建耗时、Unity物理发布时机、序列化缺省值和资源释放需按05验证；未承诺帧率、视觉等价或跨平台原子文件替换。
