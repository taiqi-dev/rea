# SUMMERHOUSE：监听列表写端与重复订阅的可达条件

接续[20：分类曲线与粒子监听](20-blend-curves-and-particle-listener-lifecycle.md)。**主程序集内只有四个方法直接使用监听列表，订阅时初始化和 Add 是所见正常写端；退订非空直接返回的分支没有被另一处清表抵消。**但这不等于已经找到玩家操作可触发同一实例重复订阅。本轮把启停入口、真实粒子配置、场景卸载与同一实例的区别分别核对，运行验证仍为 **Not Run**。

## 输入、覆盖与方法

输入仍为 `C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data`。主程序集186880 B，MVID `84569538-a19f-4c17-8ccf-f40b95e99253`。本轮另读本机 `UnityEngine.ParticleSystemModule.dll` 的枚举metadata：164600 B，MVID `93956983-c90b-42f9-b059-eaa61b9a8bfd`。沿用既有授权，没有重算摘要、加载程序集执行或操作前台。

[既有CIL工具](tools/ManagedCilProbe/Program.cs)对主程序集173个类型、1006/1006个方法完整解码后按已解析操作数筛选；每份输出保留覆盖计数。以下阴性结论仅适用于这些CIL方法的直接字段／方法引用，不覆盖反射、字符串调用、native、其他程序集、未扫描prefab或运行时创建对象。新[生命周期读取器](tools/listener_lifecycle_probe.py)重新经[20的实例探针](tools/palette_curves_listeners_probe.py)选择五份scene中的14件listener，再完整解析所选ParticleSystem及22个去重祖先GameObject，Transform层级沿用同次完整解析。其他MonoBehaviour只读到脚本引用前缀，未声称完整解析其自定义字段。所有原生布局均为精确2023.2.22f1 Release树。

新普通raw在 ignored `.cache/procedural-modeling/static-scheduler-followup/summerhouse/`，不是REA Evidence。旧native Ghidra超时条件未变、未重试；本轮不依赖它。

## 列表写端：没有找到额外的正常重置路径

`list-field-all-users.json` 对 `SharedVariable::listeners` 找到且仅找到以下方法：

| token      | 方法                  | 列表操作与边界                                                                  |
| ---------- | --------------------- | ------------------------------------------------------------------------------- |
| `06000266` | `set_Value`           | 读Count和索引，逐件作Unity对象非空检查，调用SetValue；没有清表或返回列表引用。  |
| `06000268` | `set_ColorValue`      | 同样遍历，不按listener.enabled过滤，不压缩失效条目。                            |
| `06000269` | `SubscribeListener`   | 引用为null时new List并写字段；随后无Contains去重地Add。                         |
| `0600026A` | `UnsubscribeListener` | 非null引用直接跳ret；Contains／Remove位于此前已核的不可获得正常非空列表的支路。 |

字段是private且NonSerialized，主程序集没有另外的字段替换／Clear引用；上述方法没有把列表作为返回值或可变列表参数交给其他业务方法。构造器未给它另设初始集合。这里“没有其他写端”是上述直接CIL范围，不是对反射、native或资产对象重新装载的全局排除。

`subscribe-all-callers.json` 只找到 `SharedVariableListener.SubscribeToVariable 0600026E`，`unsubscribe-all-callers.json` 只找到 `UnsubscribeToVariable 0600026F`。已知上层仍是 `OnEnable 0600026C → SubscribeToVariable → Add` 与 `OnDisable 0600026D → UnsubscribeToVariable → 非空直接ret`。不存在“其它普通业务调用反复Subscribe”这一已定位的第二入口。退订原始字节复核沿[20](20-blend-curves-and-particle-listener-lifecycle.md)：方法RVA `E719`，36 B IL，偏移6为`2D 1B`，目标35为`2A`。

## 实际14件粒子没有自停禁用配置

`listener-lifecycle.json` 的14个ParticleSystem记录全部消费到对象末尾，长度分别为7300、7356、7384或7636 B。它们均 `stopAction=0`、`looping=1`、`playOnAwake=1`；12件雨粒子 `prewarm=1`，两件水环为0。本地ParticleSystemStopAction枚举常量将0明确对应None，1为Disable、2为Destroy、3为Callback，不是凭数字猜字段语义。因此**没有从这些配置得到“粒子停止就禁用GameObject再重启”的触发链**。它们仍可能被其他代码控制；配置也不证明已在播放。

22个祖先GameObject的组件类型只包含Transform、ParticleSystem、ParticleSystemRenderer、SharedVariableListener和FollowTransform。所有所选祖先activeSelf均1，listener.enabled均1，没在这条祖先链找到Animation、Animator或UIElement组件。跟随脚本的完整CIL `FollowTransform.Awake 06000125`、`LateUpdate 06000126` 只取主相机并更新position，缺目标时记录警告，没有SetActive／enabled写入。不能由“跟随相机”推断每帧重订阅。

主程序集对 `UnityEngine.ParticleSystem::` 的直接调用只出现在 `SharedVariableListener.SetValue 06000270` 的模块访问，没有另一处Play／Stop／停止回调注册调用。这只排除了此操作数范围的直接调用，不排除native自动行为或其他程序集。

## 启停与切场景入口怎样收窄风险

全主程序集找到28个直接SetActive调用方法；此数是方法数，不是调用次数或对象数。未将28个方法的所有序列化／动态GameObject目标做全图解析，不能据此宣布粒子层级不可被启停。下列具体支路已进一步核对：

- `DebugActivator.Activate 06000113` 确实执行 `targetToToggle.SetActive(!activeSelf)`。五scene内三件DebugActivator均在level0，完整消费56 B；目标分别为GO1357 Version Info、473 FPS Counter、1462 Console Output，均为该scene内UI对象，不是level1…4的粒子祖先。原文 `debug-activation-targets.json` 与 `debug-activator.json`。
- 对 `Behaviour.set_enabled` 的直接引用只有两种接收者：InputManager.ControlsChanged写其 `virtualMouse` 字段，metadata类型为VirtualMouseInput；StartUpManager的CloseSequence写协程捕获的StartUpManager自身。没有在这两处得到SharedVariableListener接收者。原文 `setenabled-all-callers.json`、`input-manager.json`、`start-up-manager.json`。
- `DontDestroyOnLoad` 的主程序集直接调用只在 `UtilityBasic.get_Runner 06000320`，对象为它创建并加组件的runner；没有从这处把14件场景粒子变成持久对象。原文 `persist-all-callers.json`。

`SceneLoadManager+<LoadSceneCoroutine>d__15.MoveNext 06000399` 则提供实际场景切换分支。它枚举已加载scene，只对名称既不是mainSceneName、又不是本次目标的scene调用UnloadSceneAsync。循环只保留最后一个卸载操作引用并等它isDone，不能改写为逐项全部等待。`IL_0148…015C` 检查目标scene.isLoaded，为真直接跳 `01C2`，为假才于 `0181` 调 `LoadSceneAsync(target, Additive=1)` 并等待；之后清isLoadingScene和undo历史。

因此，**重复选择已经加载的同一环境，并不通过这条协程主动卸载／重新启用它**；换环境走卸载／加载，不能直接套用同一listener A的禁用→再启用模型。[Unity 2023.2卸载说明](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/SceneManagement.SceneManager.UnloadSceneAsync.html)描述卸载会销毁scene所属GameObject，同时说明不会自动卸载资产。它支持把“旧场景对象销毁”和“共享资产是否继续存活”分开；不能替代本机native销毁实现或证明某一ScriptableObject实例的实际寿命。主程序集未找到直接Resources.UnloadUnusedAssets调用，但其他程序集、引擎和资产引用生命周期仍未穷尽。

[OnEnable说明](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/MonoBehaviour.OnEnable.html)和[SetActive说明](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/GameObject.SetActive.html)只用于解释启用且层级激活时的回调条件；它们不证明这些粒子在玩家流程中实际发生了同实例启用循环。

## 两种增长模型必须分开

以下均为**构造演算，不是运行记录**：

| 条件                                                                      | 列表与通知后果                                                                                                                                       |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| 同一变量V、同一可用listener A存活，存在尚未定位的真实启用→禁用→再启用入口 | 首次为[A]；退订不移除，第二次Add成[A,A]。一次float setter和一次color setter共遍历4项并可调用A四次，前提是A均通过Unity非空门。实际启停入口仍Partial。 |
| 环境A卸载，旧listener A被销毁；共享变量V及列表存活，环境B新listener B订阅 | 列表可成[A旧,B新]。若Unity判A为null，两个setter共遍历4项，但只对B调用2次。这是旧条目残留，不是B重复注册，也不是已证的重复粒子发射。                  |
| n次加载后同一V一直存活，每次留下一个旧条目，只有最新listener有效          | 列表可有n项，两个setter共检查2n项、有效SetValue仍2次；没有静态实测n、耗时或内存。                                                                    |
| V在中途实际被卸载并重建                                                   | 新对象listeners初始null，上述跨场景累积前提中断；不能仅凭资源pathID相同断言对象身份相同。                                                            |

已回答：主程序集列表直接用户及初始化／Add边、调用者范围、14件粒子stopAction和祖先脚本、已定位debug／enabled／切scene支路。Partial：其余SetActive目标全图、所有动态或字符串调用、共享变量实例的跨scene寿命、实际同实例重启触发。没有找到这一触发不等于证明不可达；同样，静态退订缺陷不等于玩家已遇到重复通知。

## 复算与后续入口

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/listener_lifecycle_probe.py --game-data 'C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data' --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --metadata-dir .cache/procedural-modeling/static-lifecycle-followup/summerhouse --output .cache/procedural-modeling/static-scheduler-followup/summerhouse/listener-lifecycle-recheck.json
```

读取器拒绝覆盖输出、错误版本／metadata和未完整消费的所选原生对象。CIL覆盖、资源复读、枚举值、退订原始IL及上述条件计数分别验证；不把读取成功当成生命周期运行证据。目标启动／附加、Unity回调执行、实际订阅次数、粒子画面、Profiler、玩家存档均 **Not Run**。

下一片静态工作可从剩余SetActive调用者的序列化目标／动态查找，以及卸载协程持有的共享资产引用边入手，回答“同实例启用循环的实际入口”和“旧变量是否能保留列表”两个不同问题。不要再只重复读取Add和退订分支。
