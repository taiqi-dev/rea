# 12 身体配方、派生模型、运行实例与重建

后续[50：完整身体配方与运行映射](50-complete-creature-recipe-runtime-bones-and-bindings.md)取得有界三椎骨XML与编译数据候选、保留完整格式未建立的诊断，并给出独立四手六足双头的31部件/57骨编译映射。不是同一原作生物的端到端恢复。

[目录](README.md) · [编辑重建](06-editor-input-and-rebuild.md) · [灵魂关系](13-soul-body-contracts.md)。同一肉体被不同灵魂控制时，首先要知道哪些数据属于身体设计，哪些属于受伤的实例，哪些只是动画和渲染的派生状态。

## Spore 的证据支持哪些层

| 层 | 来源与具体入口 | 可确定的边界 |
| --- | --- | --- |
| 对外作品配方 | [官方 API samples，Static Data](https://www.spore.com/comm/samples) | 作品 AssetId 可取模型 XML；部件 PartId 查询类型信息，不证明永久部件实例身份 |
| 配方到模型 | [核心引擎开发者 Shalin Shodhan](https://www.shalinshodhan.com/projects.htm) | 层级/变换配方与 baking 生成可用模型有公开说明；未提供增量重建/缓存协议 |
| 保存资源 | [cEditorResource](https://modapi-docs.sporecommunity.com/class_editors_1_1c_editor_resource.html) | 已保存作品含 properties 与 blocks，不是战斗状态 |
| 配方块 | [cEditorResourceBlock](https://modapi-docs.sporecommunity.com/struct_editors_1_1c_editor_resource_block.html) | 资产 ID、parentIndex/symmetricIndex、变换、形变、涂装声明 |
| 编辑活对象 | [EditorModel.h](https://github.com/Spore-Community/Spore-ModAPI/blob/master/Spore%20ModAPI/Spore/Editors/EditorModel.h) | Load/Save/Dispose 与更新状态有接口；声明不是完整实现 |
| 能力/动画相关表示 | [cCreatureDataResource](https://modapi-docs.sporecommunity.com/class_editors_1_1c_creature_data_resource.html) | rigblocks、capability tags/levels、animation IDs/values/weights 等字段；不能直接当可删除缓存 |
| 物种摘要 | [SpeciesManager.h](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/master/Spore%20ModAPI/Spore/Editors/SpeciesManager.h) | 按 ResourceKey 管理 profile；失效协议未知 |
| 动画实例 | [IAnimWorld.h](https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/master/Spore%20ModAPI/Spore/Anim/IAnimWorld.h) | LoadCreature 创建实例；注释称 DestroyCreature 由实例析构调用，调用者不应手动调用 |

以上社区声明尚未逐项对齐本机 1.3.0.29。原游戏战斗断肢、灵魂切换、热换身体与稳定部件 UUID 都没有可靠证据。不能把资产 group/instance ID 或数组索引当成永久部件实例 ID。

## 用户游戏的独立保存结构

```text
BodyRecipe {
    recipeId, schemaVersion, partInstances[]
    each part: { partInstanceId, partDefinitionId, parentPartId,
                 connectorId, referenceTransform, morphParameters }
    skinRecipe, assetVersions
}
BodySaveState {
    bodyInstanceId, recipeId, perPartDamage[], currentAttachments[]
    bodyResources, bodyCooldowns, worldTransform
}
SoulSaveState {
    soulId, learnedAbilities, soulResources, soulCooldowns
    goals, policyProfile, validatedMemory
}
ControlSaveState { soulId, bodyInstanceId, generation }
DerivedBody {
    dependencyDigest, anatomyGraph, capabilitySummary
    renderModel, skeletonMapping, actionBindingCaches
}
```

配方模板可以共享，但每具肉体有自己的损伤和资源。它们是两份实例状态，不是复制一个灵魂到两个身体后共享同一伤口数组。每个 partInstanceId 在所属肉体/配方命名空间内唯一，复制生成新实例时保留可解释的身份映射。

一个身体里的两只同款手可以共用 partDefinitionId，但有不同 partInstanceId。删除数组第 1 项后，第 2 项的永久身份不应改变；数组下标只作为当前运行映射。

## 加载与重建

```text
LoadOwnEmbodiedActor(save):
    validate schema versions and referenced asset definitions
    recipe = LoadRecipe(save.body.recipeId)
    ValidateStableIdsAndParentGraph(recipe)
    body = InstantiateRecipe(recipe, save.body.currentAttachments)
    ApplyValidatedPartDamageAndResources(body, save.body)
    derived = DeriveGraphCapabilitiesAndModel(body)
    if derived.failed: return LoadFailed(with stage and reason)
    soul = LoadValidatedSoulState(save.soul)
    link = RecreateValidatedControlRelation(soul, body, save.control)
    plans = DeriveAvailableActions(body, soul, link)
    return Actor(body, soul, link, derived, plans)
```

不能因为找不到手部资产就悄悄删手继续读档。可以定义替代件或部分加载模式，但必须可见地报告行为变化。缓存摘要需要包括真正影响派生结果的资产版本和设置；仅 recipeId 相同不能证明缓存仍有效。

活动动作的保存是独立选择。建议首版只在没有未提交动作的安全点保存；如果玩法允许任意时点保存，则保存预约、已提交 effect ordinals、冷却、投射物身份和剩余时间，不能读档后重新播放完整伤害窗口。此处没有替你的游戏决定存档限制。

## 断肢与更换控制者的版本依赖

| 变化 | 自研应更新 | 不应默认重置 |
| --- | --- | --- |
| 仅换灵魂 | 控制关系、技能集合、AI 认知接入、旧行动许可 | 肉体损伤、身体冷却、配方和纹理 |
| 灵魂学习技能 | 灵魂动作目录与相关可用方案 | 肉体骨架和旧皮肤 |
| 手部损坏但未脱落 | 功能状态、能力提供者、依赖手的行动资格 | 永久 partId 和未受影响部件 |
| 手部脱落 | 拓扑、能力、碰撞、映射、相关动作/模型 | 灵魂技能知识和身体其他损伤 |
| 仅换皮肤颜色 | 材质结果 | 动作资格、灵魂和身体伤口 |

重建复杂时，冻结依赖已失效的数据消费者，构建新快照并验证，然后原子发布新的相关映射。旧动作如果依赖消失部件必须终止或按明确定义重新规划，不能继续用旧骨骼索引。

构造例：body B 有左手 P1、右手 P2，当前爪击方案用 P2。P1 脱落，P2 的身份不变；新的数组可以只有索引 0 对应 P2。旧“索引 1”必须失效；依赖 P2 的动作是否继续取决于映射重建和动作契约，不仅取决于数组是否缩短。

## 资源生命周期

配置资源、派生模型、动画播放实例有不同寿命。全局动画缓存清空不能替代身体绑定重建。控制关系解除也不等于身体消失；场景仍可持有失去控制的肉体。场景实体销毁才应按所属引用释放模型/实例，不能为每个控制切换手动调用共享资源销毁。

Spore 的析构注释只是一个 SDK 生命周期入口，不是我们可复用的释放实现。本规格需要在目标引擎里按实际引用关系设计。

未做：没有读私人存档或创建/修改游戏作品；没有恢复原游戏读写协议与断肢流程。风险：忽略永久部件身份、把派生模型当保存真值、或在读档时重复结算，会破坏拼装与灵魂交换后的状态一致性。
