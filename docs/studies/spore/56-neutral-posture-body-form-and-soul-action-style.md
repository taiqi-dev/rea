# 56：身体默认姿态、形态识别与灵魂动作风格

本篇只研究陆地 Creature 编辑器与动画。本机已经读到普通闲置动作的TLSA→ANIM引用链，但仍没有取得“编辑身体后怎样计算默认站姿”的原生消费者。`modelCapabilityPosture=1/2`、`uprightSpine`条件、静态姿态配置名和默认deform值是不同证据，不能直接换算站立高度或性格。

来源与精确读范围见 [public-neutral-posture-style-contracts.json](evidence/public-neutral-posture-style-contracts.json)，新读记录见 [local-selected-idle-posture-metadata.json](evidence/local-selected-idle-posture-metadata.json)。[独立检查](checks/verify_neutral_posture_style_examples.py) 与 [验证记录](evidence/neutral-posture-style-verification.json) 只验证自研规格及静态证据一致性。五模块总记录由根代理维护：[editor-body-ai-five-topics-verification.json](evidence/editor-body-ai-five-topics-verification.json)。

## 原作证据：参考姿态不是统一的“站直模板”

重新完整读取 [开发团队动画论文](https://www.chrishecker.com/images/c/cb/Sporeanim-siggraph08.pdf) PDF第2、3、4、6页。历史设计把玩家创建身体时的身体位置与朝向称为rest pose，未假定统一骨架或固定标准姿势，只假设玩家没有把身体做成极端伸展/蜷曲状态。动作可以围绕rest使用相对坐标，也可按身体大小/肢体长度缩放，或相对地面/目标泛化；rest保持为这些运动模式的原点。UprightSpine是动画绑定的形态启发式，判定脊柱主要低伏还是直立；论文没给阈值代码。

这解释了不同姿态、不同安装方向的身体仍能使用同类动作的历史设计。它没有说明编辑器默认站姿一定等于rest、Posture能力改变骨架高度、警戒会改变造型，或性格通过哪个字段进入动作风格。作者描述的rest坐标原点和自研身体neutral stance也不能互换。[37部件参考/局部运动](37-part-definition-edit-controls-rigs-and-capabilities.md) 与 [41动作坐标](41-mirroring-mount-frames-and-action-coordinates.md) 提供既有上下文。

## 固定社区声明：形态、技能等级和播放状态分别表示

固定SDK提交 `2d71289adc71aa5c58f4516c6c835c99f5f9ca19`，FX提交 `a482c51d8d37fc8cf416acecc3c00a5b0723f2e5`。本轮读取10份SDK头/实现的指定范围和两份注册表的限定命中；哈希、行范围和阴性边界存于manifest。这些是社区声明或工具实现，不是 Maxis 原作源码。

| 来源 | 能确认的入口 | 边界 |
|---|---|---|
| [cSpeciesProfile.h 93–131](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Simulator/cSpeciesProfile.h#L93) | 角色统计、`mMeanness`、`mPoseLevel`、攻击/社交等级与偏好分别声明 | 没有Posture→neutral高度或性格→姿态函数体；不扩展其后其他阶段字段 |
| [cCreatureDataResource.h 54–90](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/cCreatureDataResource.h#L54) | 部件父/对称关系、位置/朝向/缩放，capability与animation ID/value/weight数组 | 没有默认站姿计算；不能把animation values称为性格参数 |
| [AnimatedCreature.h 51–74](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/AnimatedCreature.h#L51) | Play/Load文档输入为TLSA group；有SetAnimationIdle、BlendInTime。实例另存位置、朝向、cid指针 | idle播放标志不等于身体rest；未给默认片段选择消费者 |
| [anim_cid.h 31–74](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Anim/anim_cid.h#L31) | 实例block、compiled block、父实例、orientation和cid/csd连接 | 未命名字段不能改叫neutral缓存；ABI和执行顺序未验证 |
| [EditorCreatureController.h 26–59](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/EditorCreatureController.h#L26) | 当前动画、当前/目标位置、角度与look-at、smooth标志 | Update声明没有消费者；注释中的单位/语义疑问继续保留 |
| [cEditorAnimWorld.h 20–35](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/Spore/Editors/cEditorAnimWorld.h#L20) | controller、anim/model world及EditorAnimations引用；注释给editorAnims~组`40606300` | 本轮未新读该组PROP，也未恢复其默认动画列表 |

`cAnimWorld.h`为注释掉的stub；`EditorAnimations`只显示PropertyList容器；`cEditorResourceProperties`选定可见字段主要是模型/皮肤，另有padding。这些有界声明的缺项不证明原生程序没有姿态字段。

FX [reg_property.txt](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/reg_property.txt#L2249) 提供具体续查标签：`modelCreatureStaticPoseAnim=059348b4`、`modelCreatureStaticPoseTime=059348b5`、`modelCreatureStaticPoseWeight=06861c1e`；另有`editorCreatureIdleActivationTime=0525ea2e`。它们的实际配置值/原生消费者没有读取。泛用`modelRemainUpright`标签不能视作动画`uprightSpine`分类器。注册表横跨编辑器，查找stance也会误命中distance；这些误命中和UI/其他阶段标签没有作为姿态证据。

`reg_file.txt`中的`creature_rest_pose`、`idle_att_stance`、`idle_soc_stance`、`idle_neutral1..3`和lookaround标签只是入口，本轮只追了下面三个已具具体SDK group ID的普通lookat引用；没有用名称解释警戒、蓄力或静态默认姿态。

## 本机新读：普通闲置开始、循环和结束分别引用资源

沿用EXE身份 SHA256 `f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d`。本轮重新核验Game/Patch包完整摘要与旧身份相同，从已知两TLSA key只取三个普通group，再读它们同包引用的六份ANIM metadata。读取器为 [read_selected_idle_posture_metadata.py](checks/read_selected_idle_posture_metadata.py)；旧helper保持不变。

[社区明确分类代码](https://github.com/Spore-Community/Spore-ModAPI/blob/2d71289adc71aa5c58f4516c6c835c99f5f9ca19/Spore%20ModAPI/SourceCode/Anim/Animations.cpp#L26) 给出了group ID；新读取证明group与资源instance是两层ID：

| group ID | 实际ANIM instance，type`ee17c6ad`/group0 | TLSA idle原值 | endMode原值 | ANIM raw length |
|---|---|---|---:|---:|
| `04866d8e` start | `cb38a593` | false | 0 | 21 |
| `04866dab` loop | `cee6aab3` | true | 1 | 30 |
| `04866db9` stop | `0921d851` | false | 0 | 14 |

两TLSA是 `4aeb6bc6:00006f14:f8cc4670` v7 和 `4aeb6bc6:000082d0:142cba20` v10；三个group在两份目录均匹配，六组全部`allowLocomotion=true`、durationScale1、duration-1、blendInTime-1。后面三个数的原生含义仍沿用 [51时钟边界](51-ability-animation-clocks-and-gait-synchronization.md)，不按名字转换秒或声明其过渡策略。

Game每份ANIM11个通道，Patch每份6，共51个通道。Game除头眼耳等通道还有root、肩和左右手；Patch这些已选资源只保留头、眼、耳及带cell字样的三个通道。嵌入路径均标作`_final\creature\idle_walk_lookat_*`。这里保留跨角色标签的真实metadata，但没有扩展研究细胞阶段，也不把静态版本差异当成运行的idle算法变化。

六份整段predicate的两个LE32原值都是0：未选择upright/feet/grasper整段条件。它不说明实际身体是低伏、无脚、无手。通道context仍可选择`mout/eye/ear/grsp`等角色。没有读取曲线采样、事件表或执行这些context，因而也没有恢复头/手的最终闲置姿态。

复用 [46四部件贡献](evidence/local-selected-capability-contributions.json) 得到两只bird手Posture1/2；另两只嘴没有该直接选定字段。缺字段不补0。复用 [45条件记录](evidence/local-selected-animation-predicates.json) 的46个战斗资源版本whole mask全0；[39默认混合](39-same-role-effectors-variant-binding-and-default-mixing.md) 的PCTP默认value/weight不是neutral姿态消费者。这些静态事实不能推导站立高度、凶猛性格或警戒程度。

## 自研四层：造型、身体neutral、任务pose、灵魂style

下面全部是独立规格，米/度/秒和阈值不来自Spore。

| 层 | 所有者与状态 | 可以改变 | 失效条件 |
|---|---|---|---|
| 静态造型参考 | BodyRecipe：部件实例、形变参数、安装框架、rest、质量/关节描述、digest/revision | 只由编辑事务修改；不是逐帧姿态输出 | 换部件、改变造型、连接/限位描述更新 |
| 身体neutral stance | BodyPostureProfile：可达高度、支撑接触、neutral关节目标、质量投影、重力/地面版本 | 在当前身体和地面上选择可行静止姿态，允许直立、低伏、六足、偏心 | body revision、地面/重力/接触集改变 |
| 动态任务pose | ActionPlan：执行肢体与祖先、目标、时钟、命中窗口、输出租约 | idle/警戒/look-at/蓄力/挥击等目标；按租约与支撑约束混合 | 取消、目标失效、身体/控制代次改变 |
| 灵魂style | SoulStyle：姿态偏好、视线、步幅、动作准备时长、力度/权重预算 | 在身体可行域内提出目标与时序，不能新增肢体或覆盖支撑输出 | 灵魂generation、style definition revision改变 |

风格是目标提案，身体与任务协调器才决定最终输出。谨慎可以倾向降低身体、扩大观察、缩短步幅、增加准备时间；凶猛可以倾向前伸胸部、朝向目标、扩大步幅、缩短准备时间。这里这些是自定玩法规则，不能用原作Mean或Posture字段证明。

身体分类保存多个描述而不是单个“站直/趴着”布尔值：自己的spine方向与世界up的归一化绝对点积≥.75记Upright，≤.35记Prone，中间Mixed；轴缺失/退化为Unknown。六足数量与此分类独立，水平脊柱也可以由长腿抬得很高；偏心质量是另一个描述，不能自动镜像为居中。标签仅选择候选姿态/任务样式，不直接命令root高度。

自己的高度可行域从实际腿长、关节角范围与落脚点计算，支撑面用地面接触点形成的凸包，沿重力投影COM并留稳定余量；平面样例只用已知矩形。低伏短腿另算较低高度范围；没有脚的身体只有在产品声明腹部/滑行接触模型时才能走相应策略。没有有效支撑/质量/限位参数时返回具体诊断，不把未知默认成直立。真实地形、身体碰撞和多分叉共享关节需要自己的完整FK/IK，不能只凭角色数量判可行。

造型rest不被运行pose写回：角色低头、蹲低或握拳不改变配方digest，也不把肩安装位置永久移动。neutral可缓存，但缓存key须包括body、地面/重力与接触版本；灵魂不能通过把当前动画pose当新rest来逃避身体约束。

### 具体伪代码：风格经过约束与租约

~~~text
PlanOwnPosture(body, scene, soulStyle, task):
  require mass, lengths, limits, collision/contact descriptors; otherwise diagnostic
  derive spine classification with explicit Unknown; count actual foot instances separately
  compute reachable neutral candidates from rest, leg geometry and current contacts
  reject contact/COM/limit invalid neutral; do not modify BodyRecipe
  desired = style offsets around selected neutral + task target requests
  clamp advisory height/angles/stride to declared body intervals, record Clamp details
  verify complete pose, COM margin and trajectory peak speed
  choose actual existing executors; no missing role creation
  reserve only permitted DOF/ancestor outputs; support retains foot/contact authority
  if another active task owns required output: reject or choose another declared executor
  publish plan carrying bodyRevision, controllerGeneration, taskEpoch and groundVersion

SwapSoul(oldControl, newStyle):
  capture current authoritative joint/world pose AND velocities
  prepare new feasible style targets; verify ownership of outgoing leases
  for each scalar DOF build cubic Hermite(q0,v0,q1,v1=0,T)
  find derivative roots for position extrema and second-derivative root for peak velocity
  verify entire trajectory limits, support margin and velocity budgets
  if invalid: diagnostic; preserve old generation/leases/plan, no half swap
  atomic commit: advance controllerGeneration/ownerEpoch
  cancel old pending action; keep earlier committed effects; release unconsumed reservations
  transfer output leases; keep body support anchors and gait phase
  seed handoff curves with captured q/v and new identity ticket
  each result publication checks ticket, body revision and scene/contact versions
  at curve end continue new style; task timing is newly planned, not silently retimed
~~~

这里style的stand/stride阈值若被夹取，生产实现须返回原提案、接受值、约束和原因；检查脚本的简化plan只返回接受值和失败诊断，尚未实现完整诊断DTO。任务提出的必须命中目标不允许通过夹取目标后冒充命中，具体可达性与效果处理另见接触模块。

如果风格只对动作空闲DOF提案，活动任务的强约束保留；脚锚点输出不归灵魂style。共享胸部/肩时，将多个目标交给一个约束协调器，不能通过最后写入者覆盖。[42共享关节](42-branched-limbs-shared-joints-and-goal-conflicts.md) 与 [51时钟](51-ability-animation-clocks-and-gait-synchronization.md) 分别处理约束与已锁定的动作时序。

## 独立完整数值例：同一个六足身体，由两个灵魂控制

自己的身体B，bodyRevision3，recipeDigestA。六只脚的平面接触点为 `(-.6,±.4)`、`(0,±.4)`、`(.6,±.4)` m，髋在对应x、y=0处，水平髋足距离r=.4m。每条腿两段各.6m，膝屈曲角20–100°，关节模型只在各自平面求解。支撑髋保持同一水平面，以下pitch是**支撑髋上方胸部**的角度，不是把所有髋随root一起旋转；否则下面等髋高度计算不成立。

两段等长腿脚髋距离 `d=1.2*cos(kneeFlex/2)`，因而 `dmin=1.2cos50°`、`dmax=1.2cos10°`。允许髋高度 `h∈[sqrt(dmin²-r²),sqrt(dmax²-r²)]≈[.659525,1.112016]m`。胸部pitch限位[-15,15]°，头gazeYaw[-30,30]°，手A前伸坐标[0,.35]m；neutral为h=.9、pitch8°、gaze0°、hand=.1m。

假定自研全身COM投影 `x=.1+.5*sin(chestPitch)`、y=.12m：.5m是加权胸部质心杠杆，不是身体骨长被改变。支撑矩形余量 `min(.6−x,.6+x,.4−y,.4+y)` 需要≥.08m。这个简化质量模型与矩形只适用于本例。

| 同肉体的输入风格 | h | 胸pitch/头yaw | 手A前伸 | 步幅提案 | 下一次挥击准备时间 |
|---|---:|---|---:|---:|---:|
| 谨慎灵魂A | .82m | 4°/20° | .10m | .45m | .50s |
| 凶猛灵魂B | 1.00m | 12°/0° | .30m | .70m | .25s |

两种h都在同一身体可行域，膝屈曲分别约81.0188°和52.3301°；支撑余量均为.28m，脚锚点和造型不变。自己的挥击路径.4m、最小jerk时间曲线峰值因子1.875、速度上限5m/s：准备时间.5/.25s得到峰值1.5/3m/s，均可行；.1s的“更凶猛”提案产生7.5m/s而拒绝。步幅最多.8m，2m提案被夹至.8m，不是让腿变长。

偏心身体把原y改为.36m时，余量只.04m，无论换哪种灵魂都不能按本方案稳定站立；返回InsufficientSupportMargin，调整自己的落脚/中立姿态后重新规划。不能为了表现凶猛偷偷把质量居中。较短腿各.3m、r=.2m的另一个低伏身体需要自己的高度域，可接受h=.38m，不能复用六足高身体的h=.82或1.0m。身体分类与高度可行性仍分别验证。

### 中途换魂：保连续姿态，重建控制身份

旧灵魂A已开始Windup，动作总时长锁定.8s；换魂时尚未hit，捕获当前h=.82/pitch4/gaze20/hand.1，手速度.2m/s，其余速度0。六足gait phase=.37，支撑脚世界锚点有效。原控制generation7、output epoch2；新目标采用上述灵魂B。准备时验证手输出归旧控制，不可抢第三方任务的租约，foot/contact租约继续归身体支撑系统。

用自己.4s的三次Hermite交接，末速度全0：

~~~text
u=t/T
q(u)=(2u³−3u²+1)q0+(u³−2u²+u)T*v0
     +(−2u³+3u²)q1+(u³−u²)T*v1
v(t)=dq/du / T
~~~

| 交接时间 | h/胸pitch/头yaw/hand | h速度 | hand速度 | 权威状态 |
|---:|---|---:|---:|---|
| 0 | .82m /4° /20° /.10m | 0 | .20m/s | 新generation8、epoch3；旧Windup取消，当前位置/速度连续 |
| .2s | .91m /8° /10° /.21m | .675m/s | .70m/s | 同一脚锚点与phase=.37；新控制采样交接 |
| .4s | 1.00m /12° /0° /.30m | 0 | 0 | 交接结束，新style持续；随后才能新规划自己的下一动作 |

轨迹整段最高h速度.675m/s，胸角速度30°/s、头yaw75°/s；自己的预算分别.8m/s、45°/s、90°/s。手速度二次式在u≈.458333取得真正峰值.7041667m/s，低于1m/s；不能只看中点.70或端点。h/pitch/gaze/hand的整段极值与限位、COM余量全部验证。

原动作尚未提交hit，因此没有新伤害；未消耗预约按旧动作账本释放，已有其他效果不撤销。旧片段淡出可以显示，但其旧generation/epoch票据不能提交姿态或效果。新风格的.25s准备时间只用于新开动作，不偷偷修改旧.8s动作。若产品需要不中断地换魂续招，须明确授权接管原action ID及其执行者/已提交槽位/锁定时钟；本篇选择取消并重建，没有实现续招。

交接T=.08s会超速度预算，整个准备事务拒绝，generation、输出租约与旧状态保持不变。即使两个端点都合法，过大的入口速度也会让Hermite中途越限，必须用完整极值检查拒绝。身体revision在交接期间改变时，原curve的ticket失效，拒绝StaleHandoffBodyOrController；不能把旧手坐标直接送到新身体的不同关节。实际换体需要重编自己的neutral/支撑/角色映射，由新身体恢复控制器取得新输出权。

这种交接检验假设地面/重力/支撑接触在.4s内不变。生产实现若发生地形/接触变化须更新scene版本并重验轨迹，本脚本只验证body/controller版本，不声称覆盖动态地形。高入口速度/不可行地形时，产品可把换魂请求保持为Pending，交给身体安全恢复后再准备；不能在失败分支强行瞬移或静默接管。

## 验证、未做与剩余风险

36项实际通过：30项自研形态/姿态/风格/交接，6项原值与新资源一致性。包括腿长/限位高度演算、同肉体两style、低伏/直立/六足独立描述、偏心支撑拒绝、缺手/未知参数、步幅/速度限值、输出冲突、连续q/v、Hermite中间极值、无半换魂、旧job/旧curve、换体、交接中再次换魂、idle标志与group/resource ID区别、零predicate与Posture1/2原值、证据hash。读取器成功解析两已选TLSA及六ANIM metadata；它没有执行动画或恢复曲线结果。

未做：无目标启动/附加、私存档、完整模型/贴图/动画导出、扩大payload扫描、安装配置/provider setup或Git写入。没有新读静态Pose PROP实际值，也没有原生姿态消费者，REA缺口沿用既有记录。普通idle组与本机原值有证据，警戒、蓄力和性格驱动原作style的转换机制仍未回答。

风险：静态闲置通道存在不等于编辑器默认站姿；零upright mask不是身体形态false；能力Posture等级不能当高度或骨骼偏移。独立检查是平面腿、矩形支撑和标量曲线规格，未验证真实FK/IK、碰撞、地形变化、多人并发或完整姿态视觉效果。自研灵魂style没有原作对应实现声明。
