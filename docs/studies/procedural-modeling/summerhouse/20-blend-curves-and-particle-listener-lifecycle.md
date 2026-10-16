# SUMMERHOUSE：分类曲线、粒子监听实例与退订边界

接续[19](19-palette-propagation-and-shared-state.md)。本轮完整读出实际分类曲线，并把共享变量接到发行场景中的监听组件：**四个环境manager共用同一个曲线资产；五份scene中找到14个SharedVariableListener，引用四种雨／水环变量。**另发现退订实现的具体分支：列表非空时直接返回，所见正常路径没有移除listener。这里是静态控制流事实，不是已观察到的运行故障。

## 身份、解析范围与实际配置

目标仍为 `C:\Software\Steam\steamapps\common\SUMMERHOUSE\SUMMERHOUSE_Data`。本作 `Assembly-CSharp.dll` 为186880 B，MVID `84569538-a19f-4c17-8ccf-f40b95e99253`；CoreModule的WeightedMode枚举另按本地metadata读取，MVID `f07e5f68-ed2b-4769-8d43-49b644099efa`。沿用[00](00-evidence-and-scope.md)身份与既有摘要授权，本轮没有重算摘要，也没有加载执行目标程序集。

新[只读读取器](tools/palette_curves_listeners_probe.py)逐件检查level0…4的MonoBehaviour脚本引用，再解析manager、曲线、listener和变量。自定义字段资格／类型来自实际DLL，原生布局来自精确2023.2.22f1 Release树；各资源format22、无type tree。AnimationCurve采用同树 `AnimationClip/m_FloatCurves/Array/data/curve` 的float曲线节点，Keyframe version3、每项28 B；未把四元数曲线的88 B项误套到此处。

`ColorManager`实例分别为level1/511、level2/433、level3/625、level4/471；它们的 `colorBlendingCurves` 均经外部表指向 `sharedassets1.assets/117`，其名称为ColorBlendingCurves，文件偏移4295280，总长752 B。本轮将该对象**完整消费752 B**。四个manager、14个listener、四个变量，以及引用的MonoScript、GameObject／Transform／例外Material均完整消费；ParticleSystem只确认同GameObject上的组件身份，未解析其全部模块。

## 九条曲线的真实关键帧

每条曲线均为两个关键帧、weightedMode=0；本地CoreModule的枚举常量将0对应到WeightedMode.None。表内斜率为第一帧outSlope和第二帧inSlope。原始float32完整值在raw；显示小数作四舍五入。

| 分类                                                                    | 第一个(time,value) | 第二个(time,value) | 所用两端切线斜率         |
| ----------------------------------------------------------------------- | ------------------ | ------------------ | ------------------------ |
| ambientColors、directionalLightSettings、skyboxSettings、postFX、sounds | (0,0)              | (1,1)              | 1、1                     |
| materialColors                                                          | (0,0)              | (1,1)              | 1、1                     |
| fogMaterialSettings                                                     | (0,0)              | (0.610900879,1)    | 1.636926770、1.636926770 |
| sharedVariables                                                         | (0.596234262,0)    | (1,1)              | 2.476683617、2.476683617 |
| exceptionMaterials                                                      | (0.5,0)            | (0.519999981,1)    | 0、1                     |

曲线同时保存 `m_PreInfinity=2`、`m_PostInfinity=2`、`m_RotationOrder=4`。本轮没有将序列化的2映射到本机native infinity枚举，故不据此保证首尾区间外的钳制／循环行为，也不将其误当为公开WrapMode枚举的同值。[Unity 2023.2 Evaluate说明](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/AnimationCurve.Evaluate.html)仅支持“按横轴输入取曲线值”的API解释；[preWrapMode说明](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/AnimationCurve-preWrapMode.html)明确首帧之前另有行为配置。公开说明不替代本机序列化映射或Evaluate实现。

例外材质数组也完整解析：`sharedassets0.assets`的59 Glass01、57 Glass01b、58 Glass01c、60 GlassHighlight01。`ColorPalette.Lerp 0x060000EE / IL_04A2…04C7` 对源记录的Material引用做Contains，例外引用使用例外曲线，其余用普通材质曲线。因而[19](19-palette-propagation-and-shared-state.md)的玻璃中点例所假设的有效权重，不能直接用普通材质时间因子代入。

## 反向过渡不是只交换两个端点

同一Lerp的 `IL_0000…0100` 对九类逐项使用以下关系，来自实际CIL：

```text
x = invertBlendingCurves ? 1 - t : t
w_group = Evaluate(curve_group, x)
if invertBlendingCurves: w_group = 1 - w_group
```

ColorManager的Sun／Night入口传true，Rain入口传false，见本作 `0x060000D4…D6`。在曲线关键帧处推导的对应关系如下；只使用已存节点，未执行原生Evaluate或重建全部区间插值。

| 分类               | false入口的0→1节点区间 | true入口按1-f(1-t)映射后的0→1节点区间 |
| ------------------ | ---------------------- | ------------------------------------- |
| fog                | 0…0.610900879          | 0.389099121…1                         |
| sharedVariables    | 0.596234262…1          | 0…0.403765738                         |
| exceptionMaterials | 0.5…0.519999981        | 0.480000019…0.5                       |

这些节点安排使雾、雨粒子与玻璃采用不同的变化时段。不能把全部分类概括为同一条线性淡变，也不能由两个节点声称每个中间值均线性；例外曲线两端斜率就不相等。若完整duration仍为1.5，且累计deltaTime按协程推进、无中断，那么玻璃true入口的两个节点对应累计约0.720000029…0.75秒；这是参数时间演算，不是实测墙钟或屏幕切换时间。

## 14个真实监听组件怎样接到粒子系统

每件已解析listener的m_Enabled均为1，所读GameObject及全部Transform祖先的m_IsActive均为1。同一GameObject各有一个class198 ParticleSystem；实际CIL `SharedVariableListener.SetValue 0x06000270` 的GetComponent到ParticleSystem模块写端与此静态组件连接相容。发行激活字节不证明当前场景已加载，也不证明对象现在处于播放／启用状态。

| 场景            | listener pathID → ParticleSystem pathID | 共享变量                                 |
| --------------- | --------------------------------------- | ---------------------------------------- |
| Lake / level1   | 514→494，521→491，531→492，539→493      | 依次113单雨滴、114雨滴、115雨丝、116水环 |
| Grass / level2  | 445→411，428→409，448→413               | 113、114、115                            |
| City / level3   | 642→606，639→609，640→607               | 113、114、115                            |
| Desert / level4 | 473→451，480→448，487→449，496→450      | 113、114、115、116                       |

场景名顺序沿[19的完整BuildSettings](19-palette-propagation-and-shared-state.md)。变量均在sharedassets1：113 RainDropSingleEmission、114 RainDropsEmission、115 RainStreaksEmission、116 WaterRingEmission，实际名称分别含空格；它们type=0，对应SetValue的emission.rateOverTime分支。此14件实例中没有type=1的startColor监听实例。level0没有该脚本实例；这些是五份选定scene的静态结果，不排除动态生成、其它脚本／prefab消费者或后来修改绑定。

Lake的Rain调色板把113/114/115/116目标分别设为200/30/70/200，Sun和Night中四项均为0，见[19](19-palette-propagation-and-shared-state.md)完整资产。例：若Lake的listener514已注册，变量113仍绑定到该实例，且有效sharedVariables权重到达Rain端点1，那么targetValue=200写入变量；setter通知514，后者对同GameObject的ParticleSystem494设置rateOverTime=200。这个参数不是每帧生成200个粒子；实际发射还受播放状态、模拟时间、模块和其它逻辑影响，本轮未运行。

其余三项Lake共享变量没有出现在本次14件此类scene监听实例中；不能将这个阴性范围扩成“它们没有消费者”。14是跨四个环境的配置总数，不是一个场景同时注册14件或某帧的回调数。

## 生命周期的新发现：正常非空列表没有退订

`OnEnable 0x0600026C` 先SubscribeToVariable，再SetValue；`OnDisable 0x0600026D` 调UnsubscribeToVariable。Subscribe最终进入 `SharedVariable.SubscribeListener 0x06000269`：列表为空时new List，随后直接Add(listener)，**没有Contains去重门**。

`SharedVariable.UnsubscribeListener 0x0600026A` 则有值得单列的实际分支：

| IL        | 已复读指令                                          | 后果                                                     |
| --------- | --------------------------------------------------- | -------------------------------------------------------- |
| 0001      | ldfld listeners                                     | 取列表引用                                               |
| 0006      | **brtrue.s 0023**                                   | 非空直接跳到ret                                          |
| 0009…0014 | 再取listeners并callvirt Contains，随后brfalse.s0023 | 只在前一引用为空时可到达；不能据此获得正常有效的移除路径 |
| 0017…0022 | callvirt Remove，pop                                | 所见正常非空状态被前一跳转绕过                           |
| 0023      | ret                                                 | 返回                                                     |

该结果已用当前DLL第二次CIL读取核对，并独立按PE节表读取方法RVA `0xE719`、文件偏移51481的tiny body。36 B IL中偏移6为原始字节 **`2D 1B`**，即目标`6+2+27=35`，偏移35为ret的`2A`；不是名称推断或展示器把brfalse显示成brtrue。完整原文见raw `unsubscribe-recheck.json` 和 `unsubscribe-il-bytes.json`。

因此[19](19-palette-propagation-and-shared-state.md)此前“OnDisable退订”的概括应收窄为“调用了退订入口”，**没有证明实际移除**。正常非空列表这条分支反而直接返回。setter遍历时有Unity对象非空检查，会跳过被判空的条目；这不等于从List删掉条目，也没有给仍非空但已禁用的组件建立过滤门。是否实际触发生命周期、列表是否被其它入口替换、原生对象的当前有效性仍需运行或新写端证据。

构造演算：从空列表和一个可用listener A开始，执行一次OnEnable后为[A]。按所见OnDisable→非空列表ret，仍是[A]；若同一实例再次OnEnable，Add后为[A,A]。一轮ApplyVariables先写float、再写color；两setter各遍历一次，于是对A的SetValue由2次变为4次，前提是A在遍历时仍通过Unity非空门。没有实际启停游戏对象，也没有观测重复回调、粒子数量或内存增长。由此只能标出生命周期／成本风险，不能宣布玩家已经遇到某种故障。

## 复算与验证范围

新raw位于 ignored `.cache/procedural-modeling/static-lifecycle-followup/summerhouse/`：四类metadata/CIL、`curves-listeners.json`、`weighted-mode-enum.json`、退订复读及原始IL，公开API资料范围见`public-reference.json`。资源读取器拒绝不匹配schema／metadata、未完整消费对象和覆盖输出；完整曲线、实例引用与计算可复算。

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/palette_curves_listeners_probe.py --game-data 'C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data' --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --metadata-dir .cache/procedural-modeling/static-lifecycle-followup/summerhouse --output .cache/procedural-modeling/static-lifecycle-followup/summerhouse/curves-listeners-recheck.json
```

Answered：四个manager共用的完整分类曲线／例外材质、九类反向关系、五scene内14个实例及雨粒子目标、订阅／退订实际CIL与重复条目的条件算例。Partial：serialized infinity到native枚举、原生Evaluate的全部区间行为、动态listener集合和对象有效性、其它变量消费者、实际发射与性能。游戏、目标函数／GPU、私人存档、截图、声音、Profiler和运行验证均 **Not Run**；旧Ghidra超时未变、未重试，普通静态文件不是REA Evidence。
