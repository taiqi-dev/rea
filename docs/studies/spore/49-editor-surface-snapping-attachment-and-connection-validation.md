# 49 编辑器表面吸附、安装与连接合法性

[目录](README.md) · [附着基础](02-skill-selection-and-editor-attachments.md) · [编辑事务](06-editor-input-and-rebuild.md) · [限制](34-editor-validity-complexity-and-runtime-cost.md) · [部件定义](37-part-definition-edit-controls-rigs-and-capabilities.md) · [安装与镜像](41-mirroring-mount-frames-and-action-coordinates.md) · [重建一致性](44-editor-rebuild-undo-and-animation-cache-consistency.md)。范围仍为登陆后、部落前的生物与编辑器。

本模块把“鼠标命中”“选连接对象”“对齐连接框架”“生成镜像伙伴”“提交合法配方”分开。原作公开表示给出了这些步骤的候选入口，但**原作精确吸附公式、父节点选择和校验顺序没有恢复**。下面的算法用于自己的拼装编辑器。

## 原作：接口与字段实际能证明什么

本轮重新读取固定SDK提交`2d71289adc71aa5c58f4516c6c835c99f5f9ca19`的四份头文件。文件摘要、原字节数和实际读取范围见[公开契约记录](evidence/public-editor-snap-connection-contracts.json)。这是社区声明，不是原作源码或本机ABI证明。

| 来源/行范围 | 公开表示 | 尚未确认 |
| --- | --- | --- |
| Editor.h 142–145、299–309 | 鼠标事件；hover、moving、selected、activeHandle；mouse-in-skin字段 | 拾取优先级、拖拽捕获、射线与皮肤求交 |
| EditorBaseHandle.h 13–23 | Active、Unselected、Rollover、Default状态 | 状态转换和交互事件消费者 |
| EditorRigblock.h 359–370 | 当前/历史位置、base/user/total orientation、surfaceNormal、snapType | 空间约定、朝向乘法和surfaceNormal真实意义 |
| EditorRigblock.h 417–449 | CSnap变换/骨索引、parent/children、triangle-pick表示、pinning、对称伙伴与球/套接头 | 连接骨选择、矩阵应用顺序、三角形到父的映射 |
| EditorRigblock.h 230–288、487–495 | orient/snapped/parent/picking及吸附/交互类型声明 | 哪些在陆地编辑生效；阈值、继承和合法性算法 |

[EditorRigblock固定声明](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/EditorRigblock.h)明确将`mCSnapBoneIndex`注释为模型内名为`csnap`的骨索引。它与父部件指针、变形骨索引、渲染palette索引不同；**名称不能确定它的轴向、哪组Transform是编辑/当前值，也不能推出原作矩阵公式。**

`mTotalOrientation`注释说由基础和用户朝向组合，但没有给出次序；`mSurfaceNormal`也保留“相对parent位置？”的疑问。`0xA`同时标UseSkin/HasSocketAndBallConnector并带TODO，不采用其冲突解释。CannotBeParentless的旧名称曾反向，不能直接将此标志作为已确认的陆地拒绝规则。fixed_vector容量也不是游戏连接上限。

[Editor.h](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/Editor.h)还包含滚轮操作结束和动画中断相关字段/注释，这支持继续追事件边界，不建立事务、单位或实际延迟。`cEditorSkin.h`在本轮有限关键词`pick/ray/snap/attach/mouse/HitTest/Intersect`查询中没有命中；没有据此宣布皮肤不会被拾取。

复用02的本机`editor_sym_snap/unsnap`、连接器/旋转操作名称和语境，37/41的配置与模型元数据、44的历史和动画世界声明；本轮未重新读取本机字节或新PROP/RW4。`modelHandle`模板键消费者、球/套接头实际载入连接及snapping属性消费者仍未知，不能由格式中的key推导执行算法。

## 自研结构：保存连接意图，不只保存世界位置

以下字段、公式、阈值和交互政策都是自研。延用41：列向量、右手框架，身体X左右、Y前后、Z上下；长度米。鼠标吸附距离单独使用屏幕像素。

```text
PickSnapshot { bodyInstance, generation, geometryRevision, cameraRevision }
SurfaceHit {
    ownerPartId, surfaceRegionId, triangleId, barycentric, pointBody, normalBody,
    sourceGeometryRevision, sourceMaterialRegion
}
MountAnchor {
    hostPartId, stableRegionId, shapeCoordinates, normalOffset,
    optionalCurrentTriangleAndBarycentric, sourceShapeRevision
}
ConnectorDefinition {
    stableConnectorId, localReferenceFrame, acceptsChildTypes,
    allowedHostRegions, localAxisRule, slotCapacity, mirrorCounterpart
}
ConnectionCandidate {
    childPartId, hostPartId, hostConnectorId, anchor,
    surfaceFrame, childConnectorFrame, userRotation,
    boneBindingByStableId, validity, rejectionReasons
}
DragSession {
    operationId, baseGeneration, immutableBeforeRecipe, capturedPartIds,
    currentSample, snappedCandidateId, validCandidateRecipe?, ghostPose, diagnostics
}
```

父是配方中的部件关系；骨绑定是派生映射；三角形是当前网格身份。它们不共用一串数组下标。命中眼球不意味着眼球能作肢体父节点；命中连续皮肤的融合区也不能仅选“权重最大的一根绘制骨”作为连接父。29生成表面时保留源材料区域与解剖来源，自己的连接定义决定该区域有哪些合法宿主/接头候选。

参考编辑阶段的拾取针对当前参考形体。若希望让待机动画持续播放，必须保存命中时的姿态版本并明确把碰撞点映射回参考表面；本规格首版在拖拽期间固定被编辑形体的参考拾取快照，动画预览是另一输出。原作是否冻结动画仍未知。命中数据的版本过期就重新拾取，不把旧三角形沿用到新网格。

## 自研算法一：命中与连接候选不是同一查询

```text
BeginOwnDrag(pointer, editor):
    choose active explicit tool and immutable reference/camera snapshot
    hit handle, existing part or palette item according to own UI priority
    capture pointer and stable edited part/subtree IDs
    snapshot beforeRecipe and baseGeneration
    do not change authoritative parent graph or charge budget

PickOwnMountCandidates(screenPoint, snapshot, movingSubtree):
    rayWorld = camera ray from the exact camera snapshot
    rayBody = inverse(bodyWorld) applied once to ray origin and direction
    query visible reference geometry, excluding moving subtree and its ghost
    choose nearest positive valid ray hit under declared front/back-face policy
    if front hit is incompatible: expose rejection; do not silently pick behind it
    retrieve host regions/connectors from hit provenance and own contracts
    reject self/descendant parents, stale geometry and unsupported host types
    return legal candidates plus all rejected reasons
```

摄像机射线、当前鼠标位置和当前宿主表面必须属于同一快照。显式允许“穿过前方物体选背后”时应是用户选用的工具模式，不默默跳过一个不兼容眼球，把肢体贴到其后的躯干。

自己的三角形求交演算：a,b,c为三点，e1=b−a、e2=c−a，h=d×e2、det=e1·h，s=o−a、q=s×e1；`u=s·h/det`、`v=d·q/det`、`t=e2·q/det`。仅当t≥0、u≥0、v≥0、u+v≤1才命中，点o+td，重心(1−u−v,u,v)。零面积三角形、非有限数和零方向射线有具名诊断；平行射线无命中。生产实现的误差阈值随尺度/精度设置，不能把检查脚本固定容差当成任意尺寸保证。

拾取可以用自己的BVH/简化hull加速，但最后吸附接触点必须对应所声明的实际参考表面或接头。粗代理误差大时应精化；不能把hull上的点当成已经证明贴合网格。

## 自研算法二：表面坐标、连接骨和安装框架

单脊柱圆截面例延用06：`C(u)`为中心线，n(u)/b(u)为截面基，半径r(u)：

```text
radial = cos(phi)*n(u) + sin(phi)*b(u)
anchor = C(u) + (r(u)+normalOffset)*radial
```

存u、phi、宿主区域ID和偏移，加宽后重新求anchor。分叉融合体用自己的区域参数化或带来源的表面重投影；没有可靠参数映射时返回MountReprojectionNeeded，不能拿旧triangleId继续读取新顶点。三角形重心可作当前几何的加速定位，稳定锚身份不只依赖它。

接头定义以稳定宿主骨/区域描述参考框架；该骨不是鼠标最近的任意骨。若来源有多个合适宿主则显示/选择候选，按明确规则决策并保存hostPartId/connectorId；不通过最大顶点权重暗中重连父。

自己的表面框架令局部Z沿外法线，X为偏好切线投影，Y=Z×X。偏好切线与法线平行时，选与法线最不平行的参考轴，并与合法历史切线保持连续；无有效法线则拒绝。需要绕法线的自由度由userRotation保存，不由表面重建抹掉。椭圆/非均匀缩放的法线来自真实当前几何或逆转置；已经烘焙的世界/身体法线不再重复乘形状缩放。

下面明确选定自己的安装顺序：

```text
T_partBody = T_hostMountBody * U_user * inverse(T_childConnectorLocal)
T_partBody * T_childConnectorLocal = T_hostMountBody * U_user
```

这里各T是合法刚体框架，U_user在宿主安装局部坐标作用，资产必须声明连接轴和允许旋转。不是将部件模型原点贴到表面；socket有本地偏移时，要让连接特征贴合。非均匀造型缩放已进入参考几何/连接特征，不放进这个刚体对齐再重复缩放。矩阵不可逆、非有限、含不支持剪切或轴映射缺失时拒绝。

## 自研算法三：吸附稳定性与合法性

先过滤非法候选再排序。示例屏幕距离进入阈值8 px、保持阈值12 px；已吸附的合法候选未越过12 px就保持，否则重新选≤8 px候选中距离最小者，平局按稳定连接ID。两个阈值是我们选择的滞回，不是原作symmetrySnapDelta。显示缩放、近远距离改变像素与米的关系；如果还要限制世界接合距离，作为另一米制资格检查，不能将两个数直接相加。

```text
EvaluateOwnConnection(candidate, recipe):
    validate all IDs, generation/geometry version and finite reference frames
    require host exists and is outside moving subtree
    require slot type, region and capacity accept this child definition
    apply the candidate to a copy of the complete parent graph
    require one legal body root, every parent exists and graph has no cycle
    validate mirrored candidates and partner relations as one set
    check positive nondegenerate chain lengths, declared joint/shape ranges
    check local connector alignment, permitted overlap and body/editor bounds
    check budget and derivation dependencies from34/44
    return valid candidate recipe or detailed rejected state
```

几何靠近不是连接合法性的充分条件。装饰眼可允许某种自有detailSocket却不允许limbSocket；移动上臂到自己手的下面会造成父图环，必须拒绝。有骨链肢体的极短/零骨段不能只是无声隐藏手柄：反馈具体段与合法范围。刚性装饰可以声明没有内部骨链，只校验合法安装框架，不能因没有内部骨就拒绝它；检查脚本的最短段0.01 m是肢体示例阈值。脚能否承重属于43的运行资格，不等同于部件能否安装；自己的产品可允许安装一只不承重侧足，同时显示相应预览诊断。

正常接合区域允许的几何重叠按29/32声明，不把任何穿身都判断为安装合法。编辑限制检查与实时网格生成是两步：合法配方也可能bake失败；非法候选更不能因ghost模型可以显示就得到提交许可。

## 自研算法四：镜像伙伴与交互事务

镜像伙伴按稳定部件ID保存且互相指向；不存在、非互逆或误指自己则诊断。处于对称平面的单件是单独产品规则，不通过“自己是自己的伙伴”伪装两件。

镜像点绕当前身体解剖平面转换，宿主也要有自己的对应区域/连接器。非对称躯干上不能把世界X取负后随便吸到另一根骨；找不到明确对应区域返回MirrorMountCounterpartMissing。两侧候选全部通过后才允许提交，不先扣/添加左侧再因右侧失败留下半个编辑。

旋转镜像沿41的规则，反射与四元数旋转分开。一般式为`R_partner=M_body*R_source*M_part`，两个M都为资产契约声明的反射，故结果仍为正行列式。对本圆截面框架，选择`M_body=diag(-1,1,1)`、`M_part=diag(1,-1,1)`；两侧重新计算的表面框架便满足该关系。该M_part是安装局部轴约定，不能无条件拿身体X反射当所有部件的局部轴。

自己的CanonicalMirror与SideSpecific仍二选一：左右资产已制作时不再次反射几何；使用canonical时按镜像profile处理本地特征与绕序一次。userRotation也按声明轴适配，不能直接复制所有Euler角或将整个矩阵乘负缩放。

```text
PreviewOwnDrag(session, pointer):
    clear commit eligibility of the previous preview sample
    require authoritative generation still equals session baseGeneration
    candidates = PickOwnMountCandidates(pointer, referenceSnapshot, movingSubtree)
    candidate = SelectOwnHystereticSnap(candidates)
    create own mirrored candidates if symmetry is enabled
    validation = EvaluateOwnConnection(all candidates, immutableBeforeRecipe)
    display ghost and precise failures; keep authoritative body unchanged
    if validation valid: save this sample's immutable candidate recipe
    else: leave commit eligibility empty, including older valid samples

EndOwnDrag(session, commitRequested):
    if cancelled: discard candidate/ghost and owned preview jobs
    else:
        recheck baseGeneration, latest sample and all affected pair/slot contracts
        if invalid: reject without changing either side of parent graph/history
        commit one own edit command and new generation
        rebuild/publish a current complete preview bundle through44
        retire superseded jobs under their owners
```

最新拖拽失败时可以保留之前完整身体作为背景，但不能把旧合法候选偷偷用于本次鼠标释放。重复preview从同一个事务起点取值，不把累计位移又加到上次preview上。Undo恢复配方/锚/伙伴内容为新generation；当前动态动作姿态不倒写成参考安装。

## 自研贯通演算：拖拽、加宽、镜像、拒绝与撤销

构造身体根未变，脊柱沿Z，C(u)=(0,0,u)，u=0.3 m，截面半径0.4 m。配方有body→arm→hand，另有mirrorArm和eye；eye只接受detailSocket。自有上臂socket在局部(0,0,-0.05) m，长0.5 m，镜像开启。

1. 鼠标射线示范输入o=(0.2,0.2,1)、d=(0,0,-1)，参考三角形a=(0,0,0)、b=(1,0,0)、c=(0,1,0)。得到t=1、命中(0.2,0.2,0)、重心(0.6,0.2,0.2)。这一步只演算拾取；具体圆柱安装候选由自己的表面/区域查询得到，不能将该平面命中误说成圆柱上的点。
2. 右侧安装phi=0的接触点是(0.4,0,0.3)，法线(1,0,0)，框架X=(0,0,1)、Y=(0,-1,0)、Z=(1,0,0)。socket对齐后模型原点为(0.45,0,0.3)；连接点仍在0.4。左右安装点距离0.8 m，而非模型原点距离0.9 m。
3. 鼠标距离候选7.9 px时吸附；抖到8.1 px仍保持，12 px也保持，超过12才离开。候选变非法即释放，不因尚在12 px内继续吸到错误父。
4. 用伙伴对应的区域生成左侧接触(-0.4,0,0.3)，重新计算合法右手框架，模型原点(-0.45,0,0.3)。两侧身份和骨长分别保存，全部合法后一次提交generation2；不会把一个左手模型的负尺度写到骨长。
5. 半径滚轮加宽0.4→0.7，生成generation3。锚的u/phi不变，右/左接触变±0.7，模型原点变±0.75；每侧外移0.3 m。上臂0.5 m保持，新的绑定/参考/接触一起重建，不能再通过父尺度把肢体额外拉长。
6. 新拖拽想把arm挂到hand，候选图出现arm→hand→arm，返回ConnectionCycle。想把mirrorArm接到eye的detailSocket，则ConnectorIncompatible；即使右侧候选合法也不提交任一侧。零长段或缺镜像伙伴同样具名拒绝，generation3与历史保持。
7. 如果一个合法preview之后又拖到非法位置，松鼠标返回NoValidPreview，不安装之前那份合法preview。取消保留现状。Undo加宽恢复0.4半径的内容但生成generation4，接触回±0.4、原点回±0.45；原generation3的拾取和bake结果失效，按44处理，不把动态摆臂结果当撤销位置。

上述是同一自研交互链的构造算例，拾取三角形与圆截面分别演算两个阶段；没有测量原作鼠标坐标、吸附半径或slot限制。

## 检查、未知与风险

[独立检查](checks/verify_editor_snap_connection_examples.py)30项覆盖射线/重心、漏射/退化、正交框架、socket偏移、加宽不拉长、镜像框架、声明局部镜像轴与用户旋转、逆转置法线、吸附滞回/平局、图环/缺父/连接类型/退化链、多侧验证、preview与权威配方分离、失效提交、取消、Undo新generation，以及最新非法样本不能提交旧preview。结果见[验证记录](evidence/editor-snap-connection-verification.json)。这些是数学/顺序状态测试，不是完整UI或原作执行验证。

已回答：公开表示中的拾取状态、连接骨/表面/朝向/父与伙伴区别。部分回答：候选吸附与连接约束入口。未回答：原作具体射线、表面映射、CSnap变换、选择父骨、镜像安装、非法连接反馈、modelHandle消费者及真正提交顺序。下一处原作证据应是OnMouseMove/Up读取TrianglePick/CSnap/Parent的调用链，或绑定准确部件的snap属性消费者。

未做：新本机资源/原生指令读取、运行/附加游戏、私人存档、完整资产导出、生产编辑器实现、三维连续交互与性能验证；REA缺口和静态授权沿用00，没有安装或改配置。风险：融合表面重投影、尖锐法线、非对称宿主和复杂分叉可能没有合法连接；本算法允许明确拒绝，不保证任意部件都能安装到任意位置。
