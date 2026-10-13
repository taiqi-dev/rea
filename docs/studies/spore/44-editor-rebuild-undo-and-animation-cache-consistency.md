# 44 编辑重建、撤销与动画缓存的一致性

[目录](README.md) · [交互](06-editor-input-and-rebuild.md) · [配方](12-body-recipes-and-runtime-reconstruction.md) · [预算](34-editor-validity-complexity-and-runtime-cost.md) · [部件定义](37-part-definition-edit-controls-rigs-and-capabilities.md) · [执行者绑定](39-same-role-effectors-variant-binding-and-default-mixing.md) · [特殊身体](43-unusual-bodies-locomotion-modes-and-transitions.md)。只涉及登陆后、部落前Creature及编辑器。

重点是快速修改和撤销后，网格、参考骨架、能力、步态与局部动画不能出现不同版本。**原作已有编辑历史、更新标记、动画实例和bake管理声明；完整缓存/事务/过期结果协议没有恢复。** 后半篇是我们自己的实现规格。

后续[49：表面吸附与连接合法性](49-editor-surface-snapping-attachment-and-connection-validation.md)补拖拽命中、稳定安装锚与候选配方提交；其合法候选进入本篇编译发布流程。两篇的拾取/几何公式和事务均为自研，不表示原作已经恢复该调用顺序。

## 原作证据：有哪些实际入口

来源固定SDK提交`2d71289adc71aa5c58f4516c6c835c99f5f9ca19`。本轮读取原字节、记录摘要并检查下列范围，见[公开契约记录](evidence/public-locomotion-rebuild-contracts.json)。这些是社区声明，未确认本机ABI、方法体和调用顺序。

| 文件/范围 | 可确认的公开表示 | 不能推出 |
| --- | --- | --- |
| Editor.h 105–118、160–166 | 编辑历史状态含budget/mode/painted/modelDirty；CommitEditHistory、Undo、Redo | 历史是否保存完整配方；经济回滚；撤销原子性 |
| Editor.h 183–190 | GetSkin与GetAnimWorld分别返回皮肤、编辑动画管理 | 两者更新先后和线程关系 |
| EditorModel.h 53–56、81–96 | Load/Save/Dispose、部件列表、loaded/changed/skinNeedsUpdating | 增量失效规则或每次拖拽重建全部模型 |
| BakeManager.h 68–91 | queue、tag、cancel、BakeModel、GetBlockRuntimeModelKey | cancel一定阻止回调；输入版本；缓存容量 |
| cEditorAnimWorld.h 20–37 | 编辑器动画实例/控制器访问、销毁、目标设置、实例容器 | 编辑改动是否保留动画实例、重载频率 |
| IAnimWorld.h 38–43 | LoadCreature及实例析构触发DestroyCreature的社区注释 | 能任意手动销毁附属世界；真实清理链 |
| cCreatureDataResource.h 86–90 | 能力ID/等级及动画ID/value/weight向量 | 向量同步重建、默认继承及缓存关系 |

其中`cEditorAnimWorld.h`是本轮进一步核对的接口，1581 bytes，SHA256 `fb21faed5ee933bc722992f8c08b06fdfc7af7678d37703be60eb5b7ad302470`。`EditorModel.h`原字节不是严格UTF-8（含0x97），按显式cp1252读取并保留字节摘要；没有丢弃非法字符后继续解释。行数按此次`splitlines()`计，和旧记录的终止空行计数可差1，不代表提交内容变化。

开发团队论文§4/§4.1描述首次绑定动画到某身体、评估分支/查询/变体；复用39的第5页读取并本轮完整复核第6页。它说明绑定依赖身体，不说明编辑后缓存如何清除。[动画论文](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf) 37已有选定部件的模型元数据，39已有同角色执行者与默认参数表示，本轮没有重新导出资源。

因此，目前不能宣称原作采用revision、debounce、双缓冲或以下所有权协议。也没有用社区注释的地址直接当作本机函数定位。

## 自研表示：配方身份、内容缓存和运行状态分离

以下类型、伪代码、依赖和算例均是自研。

```text
EditorAuthority { recipe, monotonicallyIncreasingGeneration, historyCursor }
EditCommand { beforeRecipe, afterRecipe, expectedGeneration, operationId }
CompileInputKey {
    recipeContentDigest, partCatalogDigest, algorithmVersion,
    targetPlatform, quality, materialDigest
}
CompileTicket { editorInstanceId, generation, inputKey, jobId, lease }
CompiledContent {
    inputKey, skeleton, inverseBind, meshes, vertexWeights, bonePalette,
    capabilities, contactGeometry, ownRoleProfiles, diagnostics
}
PublishedBody {
    bodyInstanceId, generation, content,
    actionBindings, gaitBindings, localRigBindings, previewStatus
}
RuntimeState { rootPose, dynamicTargets, actionTokens, contactAnchors, timeline }
```

`generation`表示当前编辑的生命周期，永不因Undo回退。`inputKey`表示派生内容，可以允许同内容复用。动画加载资源可按资源摘要共享；动作实例时间线、正在使用哪只手、占用令牌、世界脚锚点不能按配方摘要全局共享。两只同款手共享定义，不共享运行Grip状态。

一次拖拽的预览sample编号与提交generation也不同。采用06的“拖拽事务起点＋累计增量”；大量preview采样可合并，提交历史只产生该事务一条。开始新的已提交编辑、Undo/Redo、换体都生成新generation。旧job输入键相同也不代表它拥有当前发布资格。

## 自研算法一：依赖比较与完整版本发布

| 自研改动 | 需重建/重绑 | 条件保留 |
| --- | --- | --- |
| 替换、增删、重连部件 | 身体图、骨架/权重/索引、能力、角色、碰撞/支撑、动作与步态绑定 | 存在且定义兼容的稳定部件身份 |
| 拉长/加粗/移动安装 | 造型参考、表面、绑定、接触/可达、局部profile适配 | 能力语义不变时能力规则；仍须同版本封装 |
| 改参考弯法 | 参考骨架、弯曲偏好、绑定和相关目标 | 配方结构；几何依赖未变的材质 |
| 改花纹/颜色 | 材质/烘焙内容 | 身体结构与匹配的只读几何，可引用共享内容 |
| 动作播放 | 动态姿态/当前目标 | 永久配方、参考网格、绑定数据 |

“可保留”须由内容依赖摘要证明，不能仅看同一个部件名称。已共享的能力摘要若来自旧内容，可复用数据但创建当前版本的发布包装；禁止把旧generation能力直接接到新骨架。33的命中/AI版本与本模块一起切换。

```text
CompileOwnBody(snapshot, inputKey):
    validate part IDs, graph, assets, parameter ranges and budget
    build or reuse content nodes only when their dependency keys match
    derive edited reference body and each internal rig
    generate meshes, skin weights, inverse binds and exact bone palette
    derive capability providers, role profiles, contact and locomotion candidates
    validate all cross-references and manifest counters
    return immutable CompiledContent(inputKey, all required components)
```

发布之前核对骨索引有效、权重和palette同源、profile目标骨存在、能力提供者仍在、步态执行足仍在。不能先让新网格出现再晚一帧换inverseBind；不能先更新技能列表却仍让旧手执行攻击。

## 自研算法二：连续编辑、任务取消与过期结果

待执行队列只保留最新不可变输入；已执行任务请求取消，但不把取消返回当作终止证明。计算与发布分离：worker只产生内容，编辑权威对象独占发布决定。

```text
OnOwnCommittedEdit(command):
    require expectedGeneration and legal afterRecipe
    commit recipe/history and increment generation
    invalidate dependent active bindings with explicit reasons
    replace pending build ticket with latest immutable snapshot
    request cancellation of superseded owned running jobs
    show previous complete preview as Stale, or publish a current complete fast bundle

OnOwnBuildCompletion(ticket, result):
    resolve ticket and result ownership; reject unexpected or duplicate callbacks
    if result failed: record failure; settle owned resources without publishing
    if editor instance changed, generation differs or inputKey differs:
        record Superseded; retire result under its owning lease; do not publish
    if component manifests/cross-references mismatch:
        record MixedBundle or BodyContractMismatch; keep previous valid preview
    else:
        wrap content with current generation and rederive required runtime bindings
        swap one PublishedBody at a frame/transaction boundary
        retire old owned resources after readers finish
```

资源释放失败保留`CleanupFailedOwned`及资源ID，允许清理重试；不能丢引用后标记成功。任务的`completionDisposition`独立记录Installed/Superseded/Failed等一次性处置，清理失败不把它重新变成可发布任务。重复回调记录`DuplicateCompletion`，只能重试仍拥有的清理资源，不再次扣预算、发布或释放同一lease。成功模型的所有权转移到PublishedBody，与job输入/暂存资源的清理分别跟踪。持有旧bundle的读取者需通过引用计数/epoch等自有生命周期规则释放；本算例只验证单进程顺序状态，不建立真实多线程保证。

快预览也须有一份完整一致的骨架/网格/角色包，只降低细分或贴图质量；旧完整模型可以暂显但必须标记更新中，技能试放读取其明确版本而非把当前配方能力套过去。进入局内要求当前完整编译成功。详情见34，不重复定义经济事务。

## 自研算法三：撤销、重做与内容复用

撤销恢复配方内容，不恢复旧generation。当前世界位置、已提交伤害、外部奖励、任务状态、动作时间线不随配方历史倒退。编辑经济退差额沿34的独立账本规则执行，不能把旧钱包快照搬回来。

```text
UndoOwnEdit():
    require an earlier history entry
    targetRecipe = immutable content of earlier entry
    newGeneration = nextGeneration()
    perform normal validation/compile/publication for targetRecipe
    invalidate former-generation tasks and bindings

TryReuseOwnCompiledContent(inputKey, generation):
    content = successful immutable cache entry at exact inputKey
    if missing or incompatible: return CacheMiss
    validate cross-references and current asset/algorithm versions
    build fresh per-instance runtime bindings tagged with generation
    initialize/migrate compatible runtime state explicitly
    return current PublishedBody
```

缓存命中必须覆盖部件目录、生成算法、渲染质量等依赖。同内容可以重用已验证只读几何；迟到的旧任务必须先通过生命周期处理，不能绕过ticket检查直接安装。若要把其内容加入缓存，那是独立的验证/容量策略，不等于允许它覆盖当前身体。

Undo后新编辑截断Redo分支；旧分支编译回调仍按generation拒绝。被删除部件重新出现时，其稳定ID是否由编辑历史恢复由配方契约定义；无论ID是否相同，新动作绑定都从当前骨映射重建，不能恢复旧数组下标。

## 自研算法四：骨骼、能力与动作缓存重绑

39的绑定键至少含`bodyInstance/generation/partInstance/definitionVersion/role/output`。逻辑执行者沿稳定部件身份重新查骨映射。对应部件丢失返回ExecutorMissing；定义换成翼后原打击手角色丢失返回RoleRemoved，不自动切另一只手继续伤害窗口。

```text
RebindOwnActions(currentContent, savedIntent):
    for intent in savedIntent:
        require target still valid and effect/phase policy allows restart
        resolve stable executor and helper IDs against current body
        verify capabilities, own local profiles and all needed bones
        rebuild slot indices from current palette
        re-reserve all outputs using a new ownership token
        return current binding or explicit invalidation reason
```

保留动态状态分两种：同一实例、拓扑/空间兼容的局部平滑参数可显式迁移；不兼容的动作与脚锚点重置并记录。编辑器可重新播放动作预览，但不能把预览重新播放规则用于局内已提交命中。相位连续保持也是迁移政策，不是“缓存里有phase所以直接复制”。43模式候选和31接触要重新验收。

## 自研同一贯通例：A→B→C→Undo→Redo

沿43的六足A：F1–F4长0.9 m、F5/F6长0.6 m，H1/H2两手。自研编辑器初始generation1，A内容摘要A，完整包包含骨/能力/步态/接触。

1. 加宽为B：generation2、内容键B，提交J2。骨/表面/接触重建，H1实例仍在；新palette将H1槽0改为1，动作按稳定H1重绑，而非仍写旧槽0。43的短腿落点需重评。
2. J2尚未完成又替换H1为W1并删除足，得到C：generation3、键C。待排只保留C，取消J2是请求。C能力提供者变为H2/W1，足集合为空、准备Crawl；不先把“能滑翔”摘要发布给旧H1身体。
3. 撤销恢复B内容，得到generation4、键B，不退回2。J2在此时完成，虽然内容键B相同，generation2不拥有generation4发布资格，记录Superseded、释放自己的资源。合法已缓存B内容可重新包装为generation4并重新绑定，旧动作令牌仍失效。
4. 再Undo恢复A内容，generation5；Redo恢复B内容，generation6。历史内容可共享，运行身体世代不可复用。J4或J3的旧完成/失败均不改变generation6。
5. 若generation6网格与能力是B，但inverseBind或footBinding来自A，返回MixedBundle。只有B的完整结构、参考、权重、palette、能力、role和接触全部通过才发布。
6. 正确发布B后，H1从当前映射取得槽1；对原generation1动作请求返回StaleActionBinding。若当前C中请求H1则ExecutorMissing；不会选择H2作为替代继续旧动作。
7. 在一次Undo后继续新编辑D，则截断Redo分支。旧分支任务即使完成也只是退休资源，不把已截断历史自动恢复。失败bake保留当前配方/错误，可重试或撤销，绝不静默安装旧模型并声称编辑成功。

本检查脚本使用两个手的缩小映射验证重排/替换，不含六足3D模型；generation2→3→4的关键场景和旧内容键相同仍拒绝的分支分别核对。完整贯通步骤的世界接触/模式转换仍需产品实现。

## 检查、未知与风险

[独立脚本](checks/verify_locomotion_rebuild_examples.py)的15项重建检查覆盖待排合并、编辑迟到、Undo/Redo新generation、同键旧回调、混包、取消后仍回调、重复回调、清理失败保留所有权、稳定骨重排、删除执行者、Redo分支截断与当前完整包发布；另明确拒绝空/缺组件包，成功或过期处置后的清理重试均不重新发布。简化脚本要求四个必需组件快照；生产包按上述全部组件的具名manifest验证。总脚本加43的9项，共24项。结果见[验证记录](evidence/locomotion-rebuild-verification.json)。

原作部分回答：编辑历史/动画实例/变化标志/bake入口。未回答：本机Undo存储、拖拽合并、同步发布点、缓存键、队列/取消回调、真正骨/能力/动画更新顺序。下一步应追EditHistory或skinNeedsUpdating的消费者，以及bake完成交付给编辑动画世界的调用，不是继续把声明字段扩写成算法。

未做：原作运行/原生函数追踪、新DBPF解码、私人存档、生产实现、线程/崩溃恢复/压力测试；因为本轮交付静态研究和独立规格。风险：历史与社区声明未对齐本机，实例迁移需要资产契约，单进程示例不证明异步生产系统原子性或清理并发安全。
