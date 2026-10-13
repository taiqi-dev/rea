# 53 动作事件、特效资源、声音配置与表现所有权

[目录](README.md) · [40事件来源](40-action-events-emitters-hit-windows-and-stale-callbacks.md) · [41安装坐标](41-mirroring-mount-frames-and-action-coordinates.md) · [48被动接管](48-secondary-motion-passive-appendages-and-active-takeover.md) · [51动作时间](51-ability-animation-clocks-and-gait-synchronization.md)。只涉及登陆后、部落前的Creature动作。以下第一至三节是本机资源和固定社区格式证据；后半节均为用户肢体拼装游戏的独立规格。

本轮把既有ANIM事件继续接到实际FX导出和audioProp字段。**动作事件ID、特效导出、效果中的声音组件、音频配置和伤害提交属于不同引用与职责。** 已找到具体资源路径，但没有恢复本机事件分发、音频加载或最终绘制消费者。

## 1 本机范围：六个效果目录和四个声音配置

复用40的八份ANIM JSON，不重新读取ANIM载荷。其中44条表现事件包括26个effect、18个sound；sound中8条置社区格式的disabled位，10条未置。保留这些条目用于资源定位，不把找到disabled条目的资源说成它一定播放。

重新散列Game/Patch并读取索引，只选择`EA5118B0:40450200:*`效果目录。Game该查询未匹配，Patch匹配六个；这是两包、这一group的有限结果，不能推成基础游戏没有特效。六目录总解压9,033,983字节，单目录研究预算8MiB；另外两个质量group不读取。遍历普通/资源段边界、Visual、导出和import，声音v1与Sequence v1作结构解码；Particle/Ribbon内容只保留类型、索引和段摘要，不导出效果资产。[本机读取记录](evidence/local-selected-action-presentation-resources.json)

相较36的一MiB前缀预算，本轮明确扩大到所选八MiB目录预算，使此前未读的两个大目录也能核对导出。不是原作支持容量变化；没有改变36历史覆盖。

## 2 实际特效路径与空间控制

10个唯一effect ID均在Patch目录`EA5118B0:40450200:4CF9B596`找到同ID导出，其Visual共追到20个组件叶。匹配ID证明静态候选连接，不证明当前语言/质量、加载优先级或native分发实际选择这个目录。

| ANIM中已有名称 | 实际导出/组件路径（零起始下标） | 本轮范围 |
| --- | --- | --- |
| CRG_fight_shared_footdust | Visual290 → type1/index515 | 组件段存在，粒子参数未解码 |
| CRG_fight_slashTest_rakeTrail | Visual379 → type2/index63 | 类型/索引存在，拖尾内部参数未解码 |
| CRG_fight_slashTest_groundRing | Visual381 → type1/index619 | Block offset原值z≈0.05，Transform flags=4 |
| CRG_fight_slashTest_hitSmall | Visual382 → type1/index620、621、623、622；type5/index449 | 一个效果包含四个粒子引用和一个声音组件 |
| CRG_fight_bite_hitExtraSmall | Visual303 → type1/index544、545、547、546 | 不能把四个视觉层当成四次伤害 |
| CRG_fight_slashTest_rakeIcon | Visual380，直接block数0 | 导出存在，所读Visual没有组件；不等于ID缺失，也不推断运行永远无显示 |

剩余四个匹配路径和精确偏移、段摘要、Block原值均在JSON。类型标签采用固定FX格式：Particle=1、Sound=5；type2保留数值，不能仅凭名称猜其运行形态。

26个effect事件中10个置updatePosition、10个置updateRotation；updateScale、updateParticleScale与applyScale在这组样本均未置。**选择位置、选择方向、选择缩放和是否持续更新是不同字段。** 社区格式还区分当前生物缩放、目标生物缩放、参数缩放与不缩放，并注释普通scale与粒子尺寸参数、general effect scale的区别。这些是固定格式和注释，原作具体参数合成未知。[AnimationEvent固定源码](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/anim/AnimationEvent.java#L39)

Visual Block另有本地Transform、emit/size/alpha因素、timeScale和LOD范围。Transform存储为BE flags/scale、LE矩阵/offset；本轮记录编码和原值，没有将它直接当成本机最终世界矩阵顺序。事件源与效果内部Transform必须分别解释。[固定Block源码](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/effects/VisualEffectBlock.java#L82)

## 3 声音有两条入口，样本数组不等于多次播放

上述hitSmall的Sound449是v1、28字节记录，引用pair为group0/instance`D05B58ED`，固定文件注册名匹配`sfx_crg_rip`。其flags=0、invSample≈0.05、length=0、volume=0；**volume值为0不能直接推成无声音**，社区格式只有FLAGS_VOLUME置位才把该字段输出为volume选项。音量默认/继承和真正播放仍未读。[SoundEffect字段与输出](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/effects/SoundEffect.java#L50)

ANIM的直接sound事件没有作为这六目录中的同IDFX导出命中。按同instance查询两包索引，另取得四份Patch `02B9F662:021407EE:*`资源，86/134/110/206字节。固定PropConverter确实把audioProp/soundProp当PropertyList读取，本轮才据此复用有界PROP读取器，完整检查字段边界。[格式连接](https://github.com/Spore-Community/SporeModder-FX/blob/a482c51d8d37fc8cf416acecc3c00a5b0723f2e5/src/sporemodder/file/prop/PropConverter.java#L58)

| 配置名 | gain直接float32 | samples直接数组 | 其他本轮直接值 |
| --- | ---: | ---: | --- |
| scom_charge_rush_hit | 1 | 1个key | is3d=true，islooped=false |
| sfx_crg_mucus_launch | 1 | 4个key | pitch=1 |
| sfx_crg_strike_lvl1_swish | ≈0.65 | 2个key | 一个未注册整数字段=4，不猜含义 |
| scom_bite | 0.5 | 8个key | polyphony=4.0(float32) |

四个配置都直接保存is3d=true/islooped=false。gain是否线性、空间衰减、polyphony的作用域、样本数组如何选取、缺省/父配置和音频bank的解析均未知。**四个samples不表示四个嘴，也不能断言同时发四声或均匀随机。** type/group0的key保留为原值，不自动改造成某个波形类型。

固定reg_property中`5F6317D5`同时登记musicTemplate与parentAudio，本轮同时保留别名，不按名字强选语义；文件名注册中两个引用分别匹配`_crg_sfx_base`和`_crg_fight_sfx_base`，名称提供候选，未执行继承。reg_file大多是name-only，按小写FNV1计算，少数explicit ID覆盖；首次只搜hex无匹配的查询已更正。19个引用ID查得21行（包含Block大小写/重复别名），具体行位置与摘要见[公开证据](evidence/public-action-presentation-contracts.json)。没有读Audio包或播放/导出任何波形。

## 4 自研表示：表现请求与权威效果分开

以下结构与参数均为我们的设计。灵魂选择意图和执行部件；动作执行器确认发射/接触后产生带来源的表现请求。伤害逻辑不等待粒子或声音播放成功。

```text
PresentationCue {
  bodyLifeId, actionInstanceId, cueSlotId, repetitionIndex,
  bodyId/revision, bindingEpoch, sourcePartId,
  origin: EmitterSocket | ConfirmedHitPoint | TargetSocket | TerrainPoint,
  role: Muzzle | Trail | Impact | Voice | FootContact,
  attachment: FollowCurrentSocket | SnapshotWorld | FollowWorldProjectile,
  shapeScalePolicy, recipeVersion, timestamp
}
LivePresentation {
  cueIdentity, owner, sourceGeneration, emitterHandle,
  poseDependency, worldSnapshot, retirePolicy
}
AudioRequest {
  cueIdentity, actorLifeId, category, worldPosition,
  baseGain, sampleChoiceRule, priority, maxAge, loopOwner
}
```

EmitterSocket来自已绑定的具体嘴/手，ConfirmedHitPoint来自确认过的碰撞结果。拖尾、枪口闪光、命中火花和目标上的效果不能无条件共用一个位置。各角色允许不同缩放：几何随身体整体尺度、粒子半径可限幅、世界速度和伤害范围用技能自己定义；不能把身体scale连乘到所有参数。

## 5 自研生成、跟随、打断与去重

```text
HandleOwnCue(cue):
  check exact body life, action lifetime, current body revision and binding epoch
  resolve declared source part/socket or confirmed world hit; reject missing source
  key = (bodyLifeId, actionInstanceId, cueSlotId, repetitionIndex)
  if ledger already owns key: return DuplicateCue
  reserve key inside sequential actor update
  build frame from current versioned pose or authoritative world snapshot
  enqueue visual/audio requests with explicit owner and expiry
  on unavailable recipe/device/budget: retain diagnostic; do not undo gameplay

UpdateOwnFollowEffect(effect):
  check source lifetime and current output permission
  if source removed/action retired: stop its new emission and retire owned follow handle
  else read current matching socket pose and update declared position/rotation fields

CancelOwnAction(action):
  reject future uncommitted cues and stop owned trails/loop voices
  retain previously committed world projectiles and impacts under their own owner
  retire already-emitted cosmetic particles according to their explicit lifetime
```

同一技能的多个动画通道映射到一个LaunchSound槽时只交付一次。双嘴齐射若产品要求两个声音/闪光，应显式声明两个repetitionIndex及对应嘴。不能按名字全局去重，否则两个敌人的同名声音会互相抑制；一个impact配方里的四个视觉层也应共同交付而非错误去重。

表现账本和伤害账本分开。声音队列满、特效未加载、远处不绘制都不得改变已确认伤害。编辑/断肢使旧绑定失效，已在世界中的投射物按照40的效果生命周期继续，不要求其发射嘴保持存在。这里的预约/去重是单进程顺序规格，尚未实现生产并发和持久化。

## 6 自研多足声音与预算

每只脚只在“未接触→有效落地”的转换产生`(actorLifeId,footId,contactSerial)`，持续站立不逐帧发声。先消除同一个contactSerial的重复报告，再允许同一actor、同一40ms桶内的多个不同脚合成一个声音请求；不同actor和不同桶分别处理。

本例用自研线性增益：`g_i=baseGain/(1+(distance/radius)^2)`，合成`g=min(groupMax,sqrt(sum(g_i²)))`。这是构造能量合成，不是Spore的音频公式；选择何种样本、空间位置和频谱仍由自有音频设计决定。

```text
SelectOwnVoices(requests, budget):
  remove expired/invalid requests with reason; validate finite gain/position
  collapse exact duplicate cue IDs
  combine declared foot-contact buckets without touching contact or damage state
  sort by priority descending, audibility descending, stable cue ID ascending
  select within category/actor/global voice policy
  expire omitted one-shots; preserve/virtualize owned loops by declared policy
```

不把被省略的脚步声积压成靠近后的一次爆发。循环声需要持续所有者与停止路径；不能只保留“曾经播放过”的布尔值。上面预算检查脚本只验证排序/增益与全局cap；完整分类预算、空间混音、设备失败重试和循环声实现仍未做。

## 7 自研贯通演算：双嘴、六脚与断嘴

1. 身体B/revision12、bindingEpoch4；根位置(10,5,0)，绕Z轴90°，整体scale2。技能选嘴M1，部件位置(2,0,1)，socket局部(.5,0,0)，前方X。统一按`root * bodyScale * editedPart * socket`的自有坐标规则，发射点为(10,10,2)，单位方向(0,1,0)。同一尺度只应用一次。
2. 权威动作提交一次发射，发MuzzleFx和LaunchSound两个不同槽；动画两个通道回报同一LaunchSound，第二个被表现账本拒绝。若声明双嘴volley，则M1/M2分别使用ordinal0/1，合法交付两个声音。
3. 已生成投射物世界速度8m/s，0.1秒后位置(10,10.8,2)；这里速度不额外乘身体scale。命中点效果由实际碰撞报告给出，不从嘴部当前坐标伪造。
4. 六脚同一桶落地，各baseGain=.3、距离2m、radius4m，单脚g=.24；六脚合成sqrt(6×.24²)≈.587877，按自研groupMax .55限幅。一个脚的重复contactSerial不计两次；另一生物脚步独立成组。
5. 本次音频预算2：Impact priority3、Launch priority2、FootContact priority1；选择Impact/Launch，省略脚步表现但六脚接触状态与已提交伤害不变。相同优先级按可听程度和稳定ID确定，避免每帧随机抢声。
6. M1断开后revision13/epoch5，旧cue拒绝。依附M1的未完成拖尾停止新发射；已存在投射物和世界命中效果继续各自寿命。灵魂改选M2需新的动作/绑定，不把旧cue换个嘴后复活。
7. 若只是造型修改把M1移到(3,0,1)，新版本发射点为(10,12,2)。所有新cue读取新绑定；旧版本不沿用原骨索引。声音sample数组是否随机仍是音频配方自己的规则，不能由嘴数量推出。

## 8 验证、未知与风险

[研究读取器](checks/read_action_presentation_resources.py)复核两包摘要、六FX目录与四audioProp，保留候选键、偏移、存储/解压摘要、原始Transform和Sound记录。FX import mask是`7F000000`，不是最高符号位；路径循环、无效下标、未知版本、截断、非有限参数均诊断。没有修改旧helper或原游戏文件。

[38项检查](checks/verify_action_presentation_examples.py)覆盖格式边界、引用命名空间、声音flags、实际导出/字段、alias、空间缩放、cue去重、显式双嘴、旧版本、断嘴效果所有权、六脚能量合成与声音预算。检查记录见[本篇记录](evidence/action-presentation-verification.json)及[五项总记录](evidence/land-runtime-five-topics-verification.json)，不叠加此前117项。

已回答：10个特效静态导出路径、20个组件引用、一个声音组件及四个直接声音配置。部分回答：事件空间/更新编码与资源引用。未回答：native事件分发、实际发射框架/缩放、声音sample选择/继承/bank解析、真实衰减/并发上限、取消与完成回调。

未做：游戏运行、附加、音频播放、波形/粒子/模型完整导出、用户游戏实现或真实混音/性能测量。固定公开资料经正式只读网络流程取得；普通DNS限制和首次registry查询方法纠正保留在记录。

风险：静态候选ID匹配不保证实际加载；共享字典别名和历史注释不能替代消费者。自研空间、增益、预算与取消规则需在用户产品中验证，尤其是多头/多足、移动音源和设备生命周期。
