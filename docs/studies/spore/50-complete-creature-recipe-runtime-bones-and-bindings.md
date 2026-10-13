# 50 完整身体配方怎样编译成运行骨架与绑定

[目录](README.md) · [配方分层](12-body-recipes-and-runtime-reconstruction.md) · [皮肤与蒙皮](29-creature-mesh-joins-and-automatic-skinning.md) · [具体部件](37-part-definition-edit-controls-rigs-and-capabilities.md) · [动作绑定](39-same-role-effectors-variant-binding-and-default-mixing.md) · [重建](44-editor-rebuild-undo-and-animation-cache-consistency.md) · [多头注意力](52-gaze-head-orientation-and-multi-organ-attention.md)。范围仍是登陆后的Creature与编辑器。

**本轮取得一个完整XML的三椎骨模板和一个Creature组编译数据候选，但没有取得可完整解析、能够连到运行骨架/网格/能力/动作的原作整只生物样本。** 我们没有把37的手、38的角色和39的动作拼成同一原作生物。后半篇给出自己的四手六足双头配方、57个稳定骨骼及完整编译映射示例；它是独立设计，不是原游戏复制品。

## 原作：已有的三层表示

固定ModAPI提交`2d71289adc71aa5c58f4516c6c835c99f5f9ca19`公开声明以下结构。字段偏移是社区C++对象偏移，**不是包文件偏移或已经验证的本机ABI**。

| 表示 | 精确入口 | 能证明与不能证明 |
| --- | --- | --- |
| 编辑配方块 | `cEditorResource.h`31–58：group/instance、parent/symmetricIndex、scale/position、两组orientation、handle/paint数组 | 资产引用、结构和编辑参数分开；没有稳定部件UUID或完整序列化方法体 |
| 编译部件/能力 | `cCreatureDataResource.h`52–90：RigblockData、capability/morph起点、全局tag/level和animationID/value/weight向量 | 编译表示有多张表；不是已知的“配方数组索引直接就是骨骼下标” |
| 身体描述块 | `CreatureBlock.h`52–66：blockIndex、parentIndex、blockID、cal3DBoneName | 声明多个身份/索引空间；持久化关系和生成过程未知 |
| 身体描述与实例 | `anim_csd.h`34的blocks；`anim_cid.h`31–38、59–73的csd、creature和anim_block列表 | 描述与运行实例分开，运行块引用描述块/父块；生命周期算法未恢复 |
| 烘焙入口 | `BakeManager.h`68–86：队列、Cancel、BakeModel、GetBlockRuntimeModelKey | 有入口声明；输入契约、骨骼简化、缓存与发布顺序未知 |

直接来源：[配方块](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/cEditorResource.h#L31)、[编译数据](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/cCreatureDataResource.h#L52)、[CreatureBlock](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/CreatureBlock.h#L52)、[anim_csd](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/anim_csd.h#L34)、[anim_cid](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/anim_cid.h#L31)、[BakeManager](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/BakeManager.h#L68)。完整文件摘要及窄行段保存在[本轮证据](evidence/complete-creature-recipe-observations.json)。

29已有开发者历史机制：形状来源帮助生成皮肤权重，主体和附着细节分开；37实际读取一只手的PROP、骨架与局部通道；39取得同角色选择和变体表示；44取得重建接口。**这些证据分别成立，缺少同一个完整身体的交叉引用链。** 本轮只核验这些既有证据文件摘要，没有重新读取手模型、PCTP或动画曲线。

## 本机：限定索引及四个小资源

调查锚点为2026-10-13 00:00:49 PDT；证据最后读取的本机PT时间另存JSON。重新读取Data七包全部DBPF索引，精确匹配公开类型表的`crt=0x2b978c46`和`creaturedata=0x0f43029a`。[固定FX类型表，第50、96行](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/reg_type.txt#L50)

| 包 | CRT索引项 | creaturedata索引项 |
| --- | ---: | ---: |
| Spore_Game / PatchData | 各47 | 各0 |
| Spore_Content | 0 | 1022 |
| Graphics / Pack03 / Audio1 / Audio2 | 各0 | 各0 |

Content的1022项分为：Creature组`40626200`758项，flora组`40666200`153项，palette组`406b6200`67项，cell组`40616200`44项。组别来自固定注册表标签，不能证明某项在Creature Stage如何实例化。注册表以小写FNV1匹配name-only行，保留显式ID覆盖与全部别名；不是只搜索hex字符串。

只读取/内存解压四个资源版本，共6801 decoded bytes：

| 包/资源键 `type:group:instance` | 文件offset / stored / decoded bytes | 取得的元数据 |
| --- | --- | --- |
| Game `2b978c46:40626200:135ff099` | 12462817 / 787 / 2421 | `A_13`，XML sporemodel、formatversion16、3 blocks |
| Patch同键 | 7995779 / 787 / 2421 | 与Game存储/解压摘要相同；不决定有效加载顺序 |
| Content `0f43029a:406b6200:2a56398b` | 556639159 / 272 / 386 | palette/`FE_assembly_taproot`，排除为陆地完整身体证明 |
| Content `0f43029a:40626200:067b1055` | 322373162 / 809 / 1573 | magic`ABB455B7`、version9、三count words为8/16/23；实例名未在固定词表匹配 |

`A_13`完整XML共56个节点。三块均引用资产`40626000:d05c53a3`，注册名称`ce_vertebra`；childlist构成0→1→2。scale原值分别0.666074/0.824338/0.591213，position等编辑变换分开保存。这是可解析的三椎骨模板，**没有嘴/手/足/眼，不能称为完整多器官生物**。childid是该XML块数组索引，不能升级为永久部件ID。没有导出原XML全文。

Creaturedata的固定FX实验读取类接受此magic及version9–10，之后跳过每块`0x8c`，再读角色tag/level和morph数组；然而其属性缓冲期待68字节，所选两个本机候选的首chunk按控制token计数均产生128字节；字面路径还读取`currentBuffer[0]`。本轮保留不匹配诊断，没有“修复”该社区读取器后声称恢复原格式。[CreatureData.java，第12–77行](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/creaturedata/CreatureData.java#L12)

作为**条件性对齐线索**，若首71字节chunk整体结束属性区，则1573字节候选的后续布局可从93起容纳8×140字节块、16×4字节tag、16个level字节、23×12字节morph数组与末字，恰好到1573。候选tag字节在1213起出现spin、mout、bite、eye等可读标签。它是可继续验证的入口，不是完整解码结果；没有解出各块资产身份、原始编辑配方、顶点权重或此次运行绑定。两份候选均明确`complete_decode_status=not-established`。

Game/Patch完整SHA256本轮复核为`9d085118c649d211a86723d363592fd66ad655fd24497289b3eab96bb07db329` / `cadbff237076b441e6981503f80538705aefa5863bb4c8d1b869f9db98d1adff`。其他五包只记录实际文件长度、96字节头和完整索引摘要，**不声称重新计算整个大包摘要**。EXE固定身份`f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d`复用45，本轮未读或运行EXE。资源原值和摘要见[本机记录](evidence/complete-creature-recipe-observations.json)。

## 自研完整配方：四手、六足、双头

以下全部是我们的自有样本。单位为米，+Y前、+Z上，样本参考旋转均为单位旋转；通用编译器必须另支持经过验证的旋转/非均匀尺度。自有定义、关节名和稳定ID不对应原作资产。

| 稳定部件 | 定义与数量 | 父节点/socket | 参考安装与内部关节 |
| --- | --- | --- | --- |
| S0/S1/S2 | torso×3 | S0根；S1→S0.root；S2→S1.root | 根(0,0,0)，两次局部(0,1,0)；每段1骨 |
| H0/H1 | head×2 | S2.root | (±0.4,0.4,0.5)；每头1骨 |
| M0/M1 | mouth×2 | 对应H.head | (0,0.25,-0.12)，jaw→tip，tip增量(0,0.2,0) |
| E0–E3 | eye×4 | 每头左右各1眼 | (±0.12,0.2,0.1)；每眼1骨 |
| A0–A3 | arm×4 | 前对S2.root，后对S1.root | 左右(±1,0,0.3)；shoulder→elbow→wrist，增量横向±0.6/±0.5 |
| G0–G3 | grasper×4 | 对应A.wrist | (±0.1,0,0)；palm→finger，横向增量±0.2 |
| L0–L5 | leg×6 | 每脊柱段一对 | (±0.6,0,-0.3)；hip→knee→ankle，两段各向下0.5 |
| F0–F5 | foot×6 | 对应L.ankle | (0,0.15,0)；每足1骨 |

左右“±”按下标偶数为左负、奇数为右正。合计31部件、57骨：3+2+4+4+12+8+18+6。完整31条自有配方与57条骨映射均在[可执行样本记录](evidence/creature-recipe-and-gaze-verification.json)，不是仅给一个省略号树。

```text
PartInstanceId = stable ID within body instance namespace
BoneId = (PartInstanceId, definitionPersistentJointId)
BodyRecipe = { schema, recipeId, assetVersions, parts(parentPartId,
               connectorSocketId, referenceTransform, ownMorphParameters) }
CompiledBody = { recipeDigest, bodyRevision, skeleton, inverseBind,
                 bonePalette, logicalMesh, renderCorners, skinWeights,
                 sockets, capabilityProviders, actionRoleBindings, contacts }
RuntimeBody = { bodyInstanceId, compiledBody, injuries, resources,
                currentPose, contactAnchors, actionReservations }
SoulLink = { soulId, soulRevision, bodyInstanceId, permittedActions }
```

灵魂换人不改变配方或蒙皮；身体受伤不删除灵魂的技能知识。永久ID与palette下标分开：同一骨骼在重建后下标可变，BoneId保持不变；asset definition ID表示同款部件，不表示这只手的实例。

## 自研编译：每张映射都可校验

```text
CompileOwnBody(recipe, partCatalog, bodyRevision):
    validate unique part IDs, single root, parent DAG, asset versions
    validate transforms/morph domains and named connector compatibility
    traverse parents before children
    for each part:
        evaluate its authored shaping profile into reference internal joints
        map each persistent joint to BoneId(partId, jointId)
        first joint parent = exact host socket bone; later parents = internal rig
        B_global = B_parent * socketBind * partTransform * jointBind
        validate finite invertible transforms; save inverse(B_global)
        record socket anchor frame independently from morph-control handles
    create bone palette and BoneId→index map for this compiled generation
    generate continuous surface from own eligible shape sources and join regions
    derive weights from explicit source ownership; verify referenced BoneIds
    normalize/prune with stated tolerance; pack indices through current palette
    split render corners for UV/material/hard normals while retaining logical ID
    compile detached organs with explicit rigid or deforming attachment mode
    derive current capability providers; compile role profiles and local deforms
    bind authored action channels to stable body instances and output DOFs
    validate all tables against this same generation; return complete bundle
```

网格的具体轮廓采样与接缝算法继续采用29的自有规格，不把手模型里的一个bone count当整个身体的生成数量。本样本脚本实际编译配方、骨/socket/能力映射和蒙皮数值例；**没有实现完整等值面三角化、通用旋转蒙皮或产品资源加载器**。说明性网格生成阶段仍需生产实现和形状验收。

| 从稳定身份到运行输出 | 此自有样本 |
| --- | --- |
| G2的palm参考位置 | A2安装(-1,1,0.3)，内部再横向-0.6、-0.5，安装G2再-0.1，得到(-2.2,1,0.3) |
| G2.socket | 明确引用A2.wrist，不能替换成造型把手位置 |
| 原palette | G2.palm→27；A2.elbow→6 |
| 本次攻击方案 | 执行者G2，辅助A2，通道写G2局部握合和A2肘/腕；同一动作版本 |
| 足动作 | F0–F5分别绑定对应L0–L5链；6足不是6个独立整身体动画 |
| 眼/嘴动作 | E0/E1属H0；E2/E3属H1；嘴局部变形不等于头方向或玩法咬击 |

能力提供者明确是4个G、6个F、2个M。样本G等级为1/2/1/3，聚合采用自有max政策得到Grasp3；provider数仍为4，不能把等级相加为7或解释成一次打4次。Bite和Walk的动作资格另查具体可用执行部件、授权与状态。动作通道可绑定多个对象，但效果实例仍按40的自有去重及提交边界处理。

## 自研蒙皮与加载的数值贯通

一个自有逻辑接合顶点`v=(-0.4,1,0.3)`有原始来源贡献S1.root=2、A2.shoulder=3；归一化得到0.4/0.6。参考位置、权重和palette都属于同一编译包。UV拆出的两个render corner引用同一个logical vertex，复制相同权重，不能分别重算得到接缝。

通用LBS规格为`v' = Σ w_i * M_i(current) * inverse(B_i(reference)) * v`，权重非负且和为1。本样本只验证平移子情况：S1不动，A2肩骨向上0.2米，顶点升高`0.6×0.2=0.12`，结果`(-0.4,1,0.42)`。零运动时顶点保持参考值。这里的权重是蒙皮贡献，不能拿动画blend/variant weight代替。

```text
LoadOwnBody(save):
    validate recipe and asset versions; verify body/soul IDs independently
    retrieve a cached compiled bundle only if every content dependency matches
    otherwise compile a new immutable bundle and check all cross-references
    apply injury/attachment state by stable part IDs; unknown IDs are diagnostics
    reconstruct active body capabilities and legal action roles
    create new runtime pose/contacts/reservations; no saved stale palette pointer
    reconnect authorized soul; rebuild bindings against current body/soul revisions
    publish atomically or return stage-specific failure without partial actor
```

断开A0时，其子G0也脱离当前肉体；原配方模板可另存，不把活动附件图与模板混为一张可变表。重建后有29部件、52骨、3个Grasp provider。G2.palm仍是同一BoneId，但palette从27变22；旧27不能拿来继续写新骨架。已经存在的损伤和身体资源按稳定ID保留，换魂不清空它们。删除手的蒙皮影响必须重算或按显式断面规则建立新网格，不能把无效骨索引改为0掩盖问题。

异步编译保留44的generation/inputKey/资源所有权：旧结果不能发布到新身体。缺资产、父环、非法socket、不可逆矩阵、零权重、缺执行者、未知保存部件分别返回带ID与阶段的诊断；没有偷偷删件继续加载。关节简化如果加入，必须输出显式oldBoneId→newBoneId/权重/动作迁移映射并验证；不推测Spore的简化算法。

## 验证、未做与风险

[专项读取入口](checks/read_creature_recipe_and_gaze_metadata.py)实际检查七包索引、四份小资源及45元数据引用，不修改旧helper。[独立样本检查](checks/verify_creature_recipe_and_gaze_examples.py)共42项测试通过，其中本模块22项覆盖31/57计数、socket、参考位置、父环/缺父/缺定义/缺socket、非法尺度/变换、权重与参考姿态、断肢身份、provider政策、XML计数与声明、编译数据截断。另20项属于52，不把42全部算为配方测试。[研究检查记录](evidence/creature-recipe-and-gaze-verification.json)

**未做：** 没有启动/附加游戏、读取私人存档、导出原模型纹理或完整XML，未解出完整Creaturedata属性区与原生bake消费者。未建立同一原作身体从编辑配方到实际运行模型的链，因此原作端到端仅部分回答。

**风险：** 社区内存声明与格式实验代码存在覆盖限制；条件性数组对齐不能当稳定序列化协议。自有示例验证了结构和数值，不等于已经实现全部网格、动画、碰撞和热加载。下一步应先取得可靠完整格式或原生解析调用，围绕同一个公开发行样本验证所有引用，避免再把不同样本的字段连成假证据链。
