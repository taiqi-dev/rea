# 30 部件造型、参考姿态与局部动画怎样叠加

[目录](README.md) · [部件与姿态](01-body-parts-and-poses.md) · [姿态求解](05-particle-ik-and-rest-pose.md) · [动作协调](28-parallel-actions-channel-ownership-and-conflicts.md) · [网格与蒙皮](29-creature-mesh-joins-and-automatic-skinning.md)。范围仍为登陆后、部落前的生物及其编辑器。

核心问题有两个：**编辑后的形状怎样成为动画的新参考；动态动作怎样只施加一次。** 这次补到开发者关于造型烘焙后保留、适配运行时动画的说明，并局部读取了一条本机嘴部参数通道。原作合成公式仍未恢复，后半篇完整算法是我们的独立规格。

进一步追部件资产的具体字段与父链见[37：部件定义](37-part-definition-edit-controls-rigs-and-capabilities.md)。该篇新增手部件PROP、三轴编辑模板引用及一份模型的骨架/局部轨道数据；与本篇ANIM嘴部标量通道分开，不声称已经恢复两者的ID或执行映射。

## 原作：造型烘焙与运行时动画之间有适配

| 环节 | 开发者公开说明 | 限制 |
| --- | --- | --- |
| 编辑造型 | 手柄控制动画进度，多个造型轨道累计参考姿态增量 | 不等于按时间播放攻击 |
| 多造型叠加 | 分别累计平移、缩放、旋转，再形成变换；Multiblender处理运行时动画并施加deform | 未公布完整矩阵公式 |
| 烘焙 | 编辑deform生成新基础网格 | 不表示删除全部游戏动作 |
| 保留嘴等局部动画 | 可换成较少骨骼的运行时部件；网格与动画适配新参考骨架 | 骨骼简化、适配公式未知 |

来源：[Rigblocks演讲，第17–24页](https://www.cs.cmu.edu/~ajw/s2007/0248-Rigblocks-slides.pdf)。第18页描述合成器，第20–24页描述烘焙转换；不能把它们压成“每帧先蒙皮再造型”的唯一发行版顺序。论文还说明运行时旋转以四元数组合，与Maya的Euler增量相加不同，不能保证旋转顺序无关。[Rigblocks论文，§3](https://www.cs.cmu.edu/~ajw/s2007/0248-Rigblocks.pdf)

动画论文另外区分身体变换与标准化标量deform，后者驱动嘴、手、眼等局部动作；参考姿态参与动作适配和求解。Rest Relative与Absolute是不同运动语义，腿长缩放可参与动作目标，参考姿态不是每帧最终角度的硬锁。[Hecker等，§1.2、§3.2.2、§4.3](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

因此，“保留玩家造型”不等于禁止动作改变姿态。摆腿时关节当然会离开玩家摆出的参考角度；要保留的是参考数据、结构和造型，不能把当帧摆腿结果永久写回它们。

读取与摘要见[演讲记录](evidence/public-rigblock-deformation-slides.json)、[论文记录](evidence/public-part-local-animation-design.json)。演讲26页文本已检查；示例图片未作视觉核验。公开设计没有与本机函数逐项对齐。

## 原作：编辑把手、动作deform与blendshape是三条表示链

固定提交的社区资料给出以下入口，不能把同名morph合成一个ID空间：

| 链 | 可核对表示 | 尚未回答 |
| --- | --- | --- |
| 编辑造型 | EditorRigblock的handles/weights/channels；RWMorphHandle的起终点、defaultTime与动画引用 | 拖拽映射、多把手精确合成 |
| 动作局部deform | ANIM RigblockComponent逐关键帧value、weight、两套Interpolator | 参数语义、采样与最终权重规则 |
| RenderWare形状数据 | RWBlendShape的shapeIDs、RWBlendShapeBuffer原始数据块 | 绝对形状还是差值、与前两者的映射 |

CreatureBlock声明八个deform槽，但槽内多个数值仍未知；旧ANIM的六槽兼容转换是工具处理规则。**八槽声明、六槽旧格式与某嘴的四个映射ID不是同一个数量契约。** 未知浮点不能命名为“编辑值/动态值”。固定URL、摘要和行范围见[格式记录](evidence/public-part-deformation-contracts.json)。

社区工具按capability映射deform ID，例如`mout`有四个、`grsp`有两个；ID没有给出“张嘴、宽度、握拳”的名称。`defaultTime`是把手默认进度，也不能直接等同整只生物的rest pose。

本机复核38条完整字面量，含`deformHandle`、`deformSpec`、`remap`以及`Anim/deformdesc`。描述标签没有可靠DBPF键映射，不能当成已经找到配置脚本。完整的`BDeformBoneBaseJoint`保留前导B，没有把后缀冒充独立字符串。偏移与范围见[本机入口记录](evidence/local-part-deformation-entry-observations.json)。

## 本机具体例子：冲撞动画中的嘴部曲线

从28已有动画选取链沿同键资源继续读取：`ANIM 0xEE17C6AD / group 0 / instance 0x0AF13430`，内嵌路径标记为陆地`com_charge_rush.animation`。

旧Game版本21的mouthMorphs保留六个原始组件ID 1–6；Patch版本25有四个deform ID。本轮**只对Patch版本25、channel index 3、capability mout、五个关键帧**解释标量字段；没有执行旧版本修正，也不宣布Patch一定是运行中最终选用的版本。

| 原始time | ID `0x89E06A31` value | 同ID weight |
| ---: | ---: | ---: |
| 0 | 0.302573 | 0.844668 |
| 4 | 0.892073 | 0.844668 |
| 10 | 0.293503 | 0.844668 |
| 14 | 0.892073 | 0.844668 |
| 20 | 0.302573 | 0.844668 |

另一ID `0x5D8D0055`的value恒为1、weight约0.742647；另外两ID在所选关键帧的value/weight都是0。**不能把首列时间解释成秒，把第一组解释成开口角，也不能把value×weight当成最终部件形变。** 插值器因素与mode也保留原值，未求值；资源值不证明具体哪张嘴在局内如何运动。

20个标量样本与覆盖见[本机局部曲线记录](evidence/local-selected-part-deform-keys.json)。读取器按固定社区格式检查边界、版本、40字节组件、有限值和选定通道；不导出完整动画、模型或贴图。PatchData摘要和所选存储/解压内容摘要再次与28一致。

## 自研：四种数据不能共享一个“当前变形”数组

以下全部是自研结构、公式和合成政策。

| 数据 | 所有者 | 更新时机 |
| --- | --- | --- |
| ShapeParameters | 编辑事务/肉体配方 | 拉长嘴、加粗肢体、变更部件造型 |
| ReferenceBody与PartReference | 配方重建/烘焙器 | 改造型、连接、参考关节方向 |
| PoseGoals/PoseSolution | 动作协调与IK | 摆腿、伸手、转头，每帧变化 |
| LocalSemanticTargets | 部件动作控制器 | Open、Grip等局部请求，每帧变化 |

灵魂和技能提出动作意图，通过11/28预约具体部件和通道；不直接改ShapeParameters。一次“手到目标”与“该手握紧”是两个输出。若“握手”指两只生物接触，末端接触目标仍交给全身求解，手指握合仍属于局部动画。

```text
PartRecipe { stablePartId, shapeValues, referenceMount, restJointEdits }
PartReference {
    revisionKey, shapeDigest, mode: Baked|LivePreview,
    verticesShape, internalBind, inverseInternalBind, weights,
    featureFrames, ownRuntimeProfiles, ownNeutralValues
}
LocalActionRequest { partId, semantic, target, strength, priority, sourceAction }
ResolvedLocalTargets { valuesBySemantic, ownershipToken, revisionKey }
LocalPoseResult { internalMatrices, optionalVertexDeltas, diagnostics }
PoseSolution { absoluteModelMatrices, revisionKey, residuals }
```

每个资产显式声明造型参数与动态语义的合法范围、默认值、中性值、骨骼/特征目标和合成模式。我们的Open可选0–1，不宣称原作都是这套端点；某部件的中性值也不必为0。

## 自研算法一：造型先生成新的参考

建议局内用Baked模式：从不可变的自有资产和配方生成参考几何/骨架，运行时不再重复执行编辑造型轨道。编辑器LivePreview可保留造型轨道用于快速预览，但要通过明确模式切换，不能对烘焙网格再次执行同一把手。

多个自研造型手柄从共同中性资产取增量。例如平移增量相加；正缩放使用我们选定的log比例合成；旋转使用固定顺序的四元数乘积：

```text
translation = baseTranslation + sum(ownTranslationDelta(handle))
scale = baseScale * exp(sum(log(ownPositiveScaleRatio(handle))))
rotation = baseRotation * OrderedProduct(ownRotationDelta(handle))
```

这是自研政策，不是Maya或Spore的精确公式。比例1.5与1.2得到1.8，而不是两种形状取平均；零/负比例返回诊断。三维不同轴旋转不可交换，顺序作为资产契约保存，不依赖容器遍历顺序。需要其他合成方式时由资产声明，不能混用。

```text
CompileOwnPart(asset, recipe, currentRevision):
    ValidateOwnParameterRangesAndCompositionOrder(recipe)
    reference = EvaluateEditTracksFromImmutableAsset(asset, recipe.shapeValues)
    reference = ApplyOwnRestJointEdits(reference, recipe.restJointEdits)
    runtimeRig = InstantiateOwnAuthoredRuntimeRigTemplate(asset)
    PlaceRuntimeBindFromEditedFeatureLandmarks(runtimeRig, reference)
    weights = BuildOrRemapOwnLicensedWeights(reference, runtimeRig)
    profiles = RetargetOwnLocalProfiles(asset, reference, runtimeRig)
    RequireNeutralProfilesPreserveReference(profiles)
    return ValidateOwnPartReferenceBundle(reference, runtimeRig, weights, profiles)
```

我们的初始实现使用自有资产预先声明的小骨架模板：下颌铰链、手指根等按造型后的特征点定位。不是写一个通用算法自动猜所有器官的骨架简化。映射缺失或模板无法表达形状时返回`RuntimeRigMappingMissing`，不要静默删除骨骼。连续躯干/肢体的表面、权重与附件重建沿29处理。

## 自研算法二：动态轨道去掉旧参考，再放入新参考

这是避免动画把部件拉回默认造型的关键。对自有运行时骨骼轨道，`A_source(q)`表示源部件在局部参数q处的局部变换；qNeutral是该轨道的中性采样位置：

```text
D_source(q) = inverse(A_source(qNeutral)) * A_source(q)
D_target(q) = C * D_source(q) * inverse(C)
L_target(q) = B_targetLocal * D_target(q)
```

这里C只用于明确的源/目标局部坐标框架转换；采用正交旋转基，**不把非均匀造型缩放直接塞入C**。有平移曲线时另按所选特征长度适配动态位移：例如源嘴长10、目标嘴长12，原动态位移2变成2.4；新参考嘴长12不能再乘一次1.2。

这个式子只适用于声明为局部参考增量的自有轨道，不能套在IK已经输出的绝对模型矩阵上。不同骨骼拓扑的适配须先有模板映射；共轭公式本身不是万能重定向算法。

另一种更直接的自研方式是为每种自有部件定义`EvaluateDynamicProfile(shapeFeatures, semanticValues)`：以新下颌铰链转动，以新手指根弯曲，按新嘴长计算局部位移。它保留语义、重新生成部件动作；不需要把全部造型缩放乘进动画骨骼矩阵。

```text
EvaluateOwnLocalAnimation(reference, resolvedTargets):
    RequireMatchingRevisionAndOwnership(reference, resolvedTargets)
    output = FreshNeutralLocalPose(reference)  // 每帧从参考生成
    for profile in reference.ownRuntimeProfiles in declared order:
        q = ValidateOrDiagnoseSemanticTarget(profile, resolvedTargets)
        delta = profile.EvaluateOwnReferenceDelta(reference.featureFrames, q)
        ApplyToOwnedLocalOutputsOnce(output, delta)
    return ValidateOwnLocalPoseAndLimits(output)
```

不能以上一帧已经变形的顶点作为下一帧造型输入，也不能不断`currentAngle += delta(q)`；上一帧可供动作平滑和动力学使用，但绝对目标须重新求值，永久造型与当前姿态不能因此漂移。

## 自研算法三：局部蒙皮和身体安装变换只走一条路线

选定独立部件分层实现时，参考顶点Vshape位于部件空间，内部绑定骨矩阵为Ck、内部动态姿态为Mk，身体求解给出模型空间安装框架Gmount：

```text
V_local(q) = sum_k w_k * M_k(q) * inverse(C_k)
                       * (V_shape + ownDynamicVertexDelta(q))
V_world(t,q) = creatureWorld * G_mount(t) * V_local(q)
```

动态顶点差值在我们的部件参考空间定义，中性时为零；几何拓扑改变后不得沿用旧顶点序号。口沿或手根的接合区域使用29的共享点/锚定契约，同一逻辑点的修正也要一致。

也可以把内部骨骼并入全身palette，统一做一次蒙皮。两种路线必须二选一：若顶点已经通过全身矩阵变成模型空间，不能再乘Gmount。若骨骼已包含局部deform，也不能另一个形变器再把同一手指弯一遍。每个输出声明唯一拥有者，与28的冲突策略连接。

这里明确的是**我们选定的先后顺序**，没有把本机RWBlendShape数据断言为“先morph再skin”。存在其他空间的修正时必须声明输入/输出空间及顺序。

## 拉长嘴之后张嘴：完整演算

沿01自研参数：基准嘴长10 cm、宽4 cm；长度手柄u=0.25，增量范围8 cm；宽度手柄v=0.75，增量范围2 cm。烘焙得到长12 cm、宽5.5 cm。安装参考角20°，动态Open=0.5，自研上限30°，因此局部增量15°。

为简单演算，下颌根在原点，尖端参考点是(12,0) cm；正确结果是旋转到35°：`(9.829825,6.882917)` cm，距根仍为12 cm。角度变化不把嘴长改回10。

| 错误 | 结果 | 原因 |
| --- | --- | --- |
| 动画写默认网格 | 嘴恢复10 cm | 将源参考几何当成动态输出 |
| 把15°直接写成最终姿态 | 丢掉20°参考安装方向 | 混淆局部增量与绝对姿态 |
| 已得到35°，又叠加20°参考 | 变成55° | 参考应用两次 |
| 12 cm烘焙后再执行1.2造型缩放 | 变成14.4 cm | 编辑变形执行两次 |
| 将源轨道中性10°与采样25°直接覆盖新参考 | 参考姿态丢失或角度多加 | 应先提取15°增量，再适配新参考 |

Open回到自己的中性值时，恢复编辑后的参考嘴和20°安装方向。只有形状参数被编辑事务改动，才重新生成参考；播放/结束动作不改配方。

## 加粗肢体、弯曲参考姿态，再握合与摆腿

**加粗肢体：**自研半径从0.08 m改成0.12 m，骨段长度仍为0.5 m。这需要更新表面与必要的权重/附件，不能据此把摆腿幅度或步长也乘1.5。动作目标可以按骨链长度适配，但粗细是另一种输入；碰撞/通行、技能接触几何的更新分别连接25/26，不能仅改显示网格。

**握合：**手根随伸手姿态到达目标；Grip只控制手内部声明的关节或形状。不同手型用自己的同语义profile，不把所有手指写成一组默认角度。手掌宽度已经进入Vshape和内部绑定；握合只执行新的动态增量。若用户指角色间握手，接触双方末端还要重查可达性，不由Grip参数代替。

**弯曲参考姿态：**保存参考弯曲平面与骨长，不保存一个永远不变的膝角。自研两骨链各0.5 m，足目标从距根0.6 m移到0.7 m；选择参考的正向弯法，膝点为`(0.35,0.357071)` m，而非负向分支。IK求解后的绝对矩阵直接进入身体姿态，不能再乘一遍参考弯曲矩阵。目标不可达或接近伸直奇异点时保留05的诊断与方向连续性政策。

## 同时走、张嘴、握合：逐帧完整流程

```text
UpdateOwnCreatureFrame(creature, intentions, dt):
    refs = GetImmutableCurrentReferenceBundle()
    claims = PlanAndReserveActionsAgainstCurrentBody(intentions, refs)
    bodyGoals, localRequests = SampleOwnActions(claims, dt)
    bodyGoals = CombineWithOwnGaitAndHeadTargets(bodyGoals)
    bodyPose = SolveOwnAbsolutePose(refs.body, bodyGoals)
    ApplyOwnPassiveSubtreeMotionWithinDeclaredOwnership(bodyPose)
    localTargets = ResolveLocalSemanticConflicts(localRequests, refs)
    for part in refs.parts:
        localPose = EvaluateOwnLocalAnimation(part.reference, localTargets[part.id])
        RenderPartUsingExactlyOneDeclaredSkinningPath(part, bodyPose, localPose)
    PublishPoseDiagnosticsWithoutWritingBackRecipe()
```

自研组合：六脚继续落脚求解，一只手伸向目标并Grip=1，一张嘴Open=0.5。其他手不因同为Grasper就同步握紧；具体部件来自行动方案的稳定ID。两个技能争用同一张嘴的Open时先按28的所有权/混合组规则仲裁，不让两条局部曲线直接各写一次下颌。

自研局部参数若选择混合，可按明确的基准和强度得到目标；不能默认采用`value*weight`。造型参数不参与动作层crossfade。被动耳/尾跟随也不能回写嘴部造型或抢占正在主动控制的内部关节；原作论文的Jiggles是无反馈的次级运动，但本段部件输出规则仍是自研。[Hecker等，§4.4](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf)

## 编辑、换体与动作结束的失效规则

| 事件 | 自研处理 |
| --- | --- |
| 拉长嘴、加粗肢体 | 新参考几何/骨架/权重、特征框架、局部profile适配，更新相关碰撞 |
| 仅改关节参考弯法 | 更新rest、参考方向、绑定与动作适配；是否重网格由几何依赖判定 |
| 动作开始/结束 | 创建/释放动态占用，回到该部件声明的中性目标；不恢复源资产默认造型 |
| 同体换魂 | 重新选技能/目标/风格；若形体未变，不重建造型 |
| 断肢/换肉体 | 旧部件请求失效、旧映射失效，重新绑定并触发16能力评估 |
| 后台旧编译完成 | 版本不符则记录并释放旧结果，不能覆盖当前参考包 |

局部控制器自身有平滑或弹性状态时，可在同部件、兼容新框架下转换历史状态；不兼容时显式重置并记录原因。将旧骨骼索引原样交给新嘴、把旧模型的参数槽搬到新手，都需要拒绝或明确适配。

## 验证与剩余未知

[局部字段读取器检查](checks/verify_part_deform_reader.py)8项通过，覆盖40字节载荷边界、版本、能力、索引、NaN和真实所选样本；[独立合成检查](checks/verify_part_deformation_examples.py)22项通过，覆盖造型保留、中性值消除、参考增量、轴重映射、旋转顺序、重复烘焙、逐帧漂移、安装变换与写入冲突。详细结果见[验证记录](evidence/part-deformation-verification.json)。

尚未回答原作：具体嘴/手的动态ID语义、插值求值、weight含义、编辑与运行时ID映射、简化骨架适配、内部morph/skin次序及碰撞限制。没有实际生物配方，不能把资源曲线等同局内某张嘴的可见变化。

未做：启动/附加游戏、原生反编译、私人存档读取、完整模型/动画提取、生产代码实现与三维渲染验证；REA/provider缺口沿用00。新增读取仅限一个已选Patch ANIM的嘴部标量通道，没有扩查水中、部落或文明玩法。

风险：历史共享Rigblock技术不保证本机每种陆地部件采用同一链；自研模板需覆盖自己的资产与参数范围，极端嘴长、厚手掌、关节翻转和动态接缝仍需三维测试。
