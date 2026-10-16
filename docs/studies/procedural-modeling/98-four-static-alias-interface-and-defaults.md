# 四款游戏：可变别名、引用映射与默认配置

后续[100](100-four-static-state-consistency-and-palettes.md)按建议转入读回时效、失败载入、单墙稳定seed和真实调色板传播；本篇槽23和尾值3的未知边界继续保留。

接续[95](95-four-static-bufferstate-and-reference-transfer.md)。本轮四款均有专题：**沙堡接到一个非空引用映射接口及其实际实现；Tiny Glade 定位了目标 typed 对象的 Any 表和 TypeId，但没有找到改写内部 raw handle 的消费者。** 掘地求财补上原生 CDO 的真实构造回调和初始化复制门；SUMMERHOUSE 补上相机所继承的管线纹理开关。运行验证仍为 **Not Run**。

| 专题                                                                                       | 本轮新增证据                                                                                                                                                   | 仍未回答                                                                                           |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [Tiny Glade：可变别名与 raw handle](96-tiny-glade-mutable-alias-and-raw-handle.md)         | 本类型 vtable 的两个 Any 槽返回同一对象地址和实际 Any 表；TypeId 表项、字面量及具名特化已定位。首 qword 已见写端仍属于新对象构造，图导入端读取原对象首 qword。 | 没有接到别名消费者→旧对象 raw store→新容量；槽23四个非动态计数字段、最终容量和真实提交仍 Unknown。 |
| [沙堡：接口实际目标与尾值](sandcastle/19-reference-interface-targets-and-tail.md)          | 调用现场把非空接口写入 context+0x38；首槽按有序 int32 键值表重映射内存引用；同一 context 传给动态接收者的+0x88。                                               | 动态接收者是否为 class129 未证；其它接口实例未穷尽；文件尾值3的构建 writer／准确字段仍 Unknown。   |
| [掘地求财：CDO构造与模式初值](digging-a-hole/17-native-cdo-construction-and-mode-state.md) | 本类注册构造回调→CreateDefaultObject→AVoxelWorld ctor 两个模式零写；本类 flags 选择关闭 CDO 普通 InitProperties 复制门，并核到 PostInitProperties 实际虚槽。   | 延迟／特殊初始化、外部后写入未穷尽；运行中的 CDO、关卡 actor 模式不能由条件零值代替。              |
| [SUMMERHOUSE：管线纹理需求](summerhouse/18-pipeline-texture-demand-and-settings.md)        | 完整原生 Graphics/QualitySettings 均指向选定 URP；资产前缀的深度、不透明颜色纹理开关均为1，接到相机继承 getter。                                               | 自定义资产剩余328 B未解析；当前管线、动态覆盖、最终附件／复制次数和真实成本仍 Partial。            |

## 两个优先悬案的证据边界

Tiny Glade 的 `as_any_mut` 确实能暴露同一 typed 对象，但**存在可变别名能力不等于已经发生替换**。本轮 Any 表、TypeId 和目标具名符号的直连扫描没有给出消费者 store；间接、内联、拆分比较与其它模块不在阴性结论内。初建仍为 `23×20=460 B`，槽23范围为 `[460,480)`；没有新的至少480 B资源描述符或同 handle 重绑定证据。因此既不能声称已扩容，也不能把条件范围演算写成实际越界。后续只在新具体写端、raw记录生命周期或设备范围处理产生新边时接续。

沙堡本轮的关键新增是**真实接口内容**。旧引用命中映射表就写替代值，未命中保留原值；此实现不读 SerializedFile 流。调用现场的动态对象来自输入记录查找，不能因为附近出现某个固定全局地址就归为 PlayerSettings。条件上，若该对象确为 class129，已证的+0x88链会使用此接口；具体身份还缺一边。该进展没有解释916字节对象中直接 reader 只消费912字节的差额，更没有给末尾3命名。构建端不同布局、额外零槽或后处理均只保留为可检验解释。

## 其它两款的具体收益

掘地求财将“构造函数会写零”推进到“本类 CDO 创建确实接到该构造，普通自身属性复制门在此静态选项下关闭”。它收紧了材质模式和处理器选择的默认源，但不排除后续覆盖。SUMMERHOUSE 则补齐了此前 option=UsePipelineSettings 的配置缺边：选定管线要求两类纹理。纹理需求、后处理开关及最终附件是不同门；不能由开关1推出额外显存或某帧复制成本。

这些结果分别回答默认状态和资源需求，均未升级为玩家画面或性能观察。新的研究顺序与各自第一片范围见[下一轮建议](97-next-study-recommendations.md)：优先沙堡读回快照到碰撞，其次掘地求财失败加载保护、Tiny Glade稳定重建、SUMMERHOUSE调色板传播。两项悬案继续保留Unknown，后续选择以能取得新数据流为依据。

## 证据、复核与交付范围

新原始文件位于 ignored `.cache/procedural-modeling/static-alias-followup/`，按四款分目录；正式专题保存地址、字段、条件与复算入口。本轮两个新只读工具分别复读沙堡PE接口指针及SUMMERHOUSE选定资产前缀；不执行目标代码。后者只完整解析原生设置与MonoScript，自定义pipeline对象明确只读116/444 B。沿用先前目标身份，没有重新计算摘要。

定点复核检查上述指针／指令、TypeId候选覆盖、CDO门和CIL／资源字段，并检查新工具的有效输入、拒绝覆盖及错误输入。文档验证覆盖本轮拥有文件的UTF-8、相对链接、围栏和空白；实际结果保存在同轮 `focused-validation.json`、`document-validation.json` 与交付回执。仓库文档检查和Git hooks按实际交付结果记录。

Ghidra原有超时未变、未重试；普通本地输出不冒称REA Evidence。游戏启动／附加、目标函数或GPU执行、私人存档、截图、Unity运行及性能测量全部 **Not Run**，[运行用例](74-runtime-validation-cases.md)继续独立。
