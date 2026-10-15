# 四款游戏：BufferState 写端、引用传递与目标生命周期

接续[93](93-four-static-replacement-and-effect-gates.md)。本轮优先从实际字段写入和间接调用接续，而非再以函数名判断：**Tiny Glade 的同键图租约及图完成路径未提供指针替换，构造 vtable 的取句柄槽也只返回原地址；沙堡 `+0x88` 可见本体处理资源引用候选回填，没有补写末尾 `3`。** 两个优先问题仍未全闭合。掘地求财补上生成类的正常属性链接入口，SUMMERHOUSE 接通 TAA 历史目标的分配／关闭与销毁。运行验证 **Not Run**。

| 专题                                                                                    | 新确认的连接                                                                                                                                                                                   | 剩余静态边界                                                                                                         |
| --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| [Tiny Glade：BufferState 指针写端](94-tiny-glade-bufferstate-pointer-writers.md)        | 本类型 add_new 构造新项 `+0/+8`；同键 read/write/finish 改的是 `+0x28` 后状态。图完成遍历只清状态；具名get_mut两调用属于另一名称键。构造vtable `+0x28` → 纯返回地址 → 调用者读取原raw handle。 | 未发现接到本键的新raw handle；可变别名、内联／间接写端及所有shader未穷尽。最终容量、槽23四字段与执行顺序仍 Unknown。 |
| [沙堡：+0x88 引用传递](sandcastle/18-transfer88-and-tail-production.md)                 | 六个顶层调用的输入接到资源引用字段／数组；接口写栈候选，按context标志回填对象。末项allowed只内存自写，无可见额外tail写。                                                                       | 接口首槽实际实现和完整上层虚调用范围未知；构建writer及文件尾值3的字段来源仍 Unknown。                                |
| [掘地求财：生成类到属性链接](digging-a-hole/16-generated-class-property-link.md)        | 本作AVoxelWorld的134项属性表 → ConstructFProperty → 主枚举挂入类链 → StaticLink(false) → 实际UClass/UStruct虚分派 → 枚举LinkInternal。                                                         | 类缓存／实际调用与CDO最终值、actor复制分支和脚本后写入仍未观察。                                                     |
| [SUMMERHOUSE：TAA目标生命周期](summerhouse/17-taa-target-lifetime-and-disabled-cost.md) | CPU状态对象由追加数据构造；Init与分配分离，普通RenderSingleCamera进入启用门，false时释放／清空历史目标；销毁正常路径也清理。                                                                   | 原生准入、动态覆盖、其它入口、真实GPU释放和成本仍 Partial。                                                          |

## 优先问题的具体进展

Tiny Glade 的外层Box地址不变，本身不足以证明内部raw handle不变。因此94额外核对实际构造vtable：`0x14331C5E8+0x28 → 0x1406D0830`，实现仅 `mov rax,rcx; ret`，随后调用者读取首qword。这一租约取句柄步骤没有隐藏分配或替换；它仍不排除别的可变Any消费者。已定位的图完成状态跳表也未重写 `BufferState+0/+8`。与[89](89-tiny-glade-other-command-writers.md)的23条模板和[90](90-tiny-glade-command-capacity-and-lifetime.md)的460 B初建连接后，本轮仍没有新的≥480 B描述符或槽23生产者。后续有判别力的入口是同typed对象内部raw字段的其它可变别名写端，或其它CPU/GPU写者，而不是把状态更新当作容量增长。

沙堡本轮区分了运行时四字节资源引用值与文件十二字节引用表示。`+0x88` 的输入是defaultCursor、invalidatedPatternTexture、preloadedAssets元素、hmiLoadingImage及两个设备过滤资源引用；六是静态顶层调用点数，数组和嵌套成员会影响实际调用次数。末次接口调用后，仅对对象内存allowed成员自写并返回，没有显式流游标或尾成员写入。这个结果排除了可见本体末段补写3的解释；由于接口目标未接通，不能说整个间接路径无副作用。原来916/912字节差额和构建端未知继续保留，不给尾值改名。

## 局部更新和性能的限定结论

掘地求财15的一字节复制不再只依赖假设“正常LinkInternal已调用”：本轮从同类参数表和实际UClass虚表接到正确的 `StaticLink(false)` 分支，两个主枚举进入类属性链并通过字段类门。CDO值仍未知；文中的0x02只作构造演算，不能代入实际材质或handler选择。

SUMMERHOUSE 的TAA状态对象存在不代表纹理已分配。新增链表明Init可更新描述符并释放旧目标，独立AllocateTargets才创建历史纹理。按16的AA=None配置已被消费且未覆盖的前提，普通入口进入关闭／清空分支；若目标已空，跳过Release但仍重置状态。这个条件结论不等于所有相关CPU成本为零，也不证明真实帧时或GPU释放时刻。Init仅显式用三个尺寸和首目标存在性做early-return，不能将其概括为所有格式变化都会触发重建。

## 证据与验证

新原始记录位于 ignored `.cache/procedural-modeling/static-bufferstate-followup/`，按四款分目录；正文保存可复核偏移、调用门和例子。使用现有PDB／PE／CIL工具，沿用此前匹配身份，未重算目标制品摘要。REA native Ghidra超时状态未变，未重试；普通静态输出未冒称REA Evidence。

本轮定点复核包括构造vtable及共享返回函数、图状态跳表、引用字符串／指针、生成类属性表和虚分派、TAA类CIL复读及门控；另检查正式文档UTF-8、相对链接、围栏与空白。实际文件范围和结果在同轮 `focused-validation.json`、`document-validation.json` 与交付回执中。沙堡支线已通过仓库 `docs:check`；Git hooks按交付记录报告。游戏、附加、目标函数/GPU、私人存档、截图、Unity构建和性能测量均 **Not Run**；[运行用例](74-runtime-validation-cases.md)保持独立。
