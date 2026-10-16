# 四款游戏：容量、启动改色、碰撞盒与反射纹理生产者

接续 [111](111-four-static-config-overrides-and-budget-boundaries.md)，按本次四条静态入口续查。Tiny Glade 的容量已追到实际页数/字节请求及材质回调；沙堡已接启动状态机到 Setup 改色；掘地求财已接 invoker 到碰撞盒，并更正上一轮漏掉的 LOD 0 前置门；SUMMERHOUSE 补充反射纹理的缓存、失效和材质属性块绑定。**静态链有新增闭合，实际画面、时序和性能仍未验证。**

## 专题与当前边界

| 专题                                                                                            | 本轮新增事实                                                                                                                                                                                                        | 未决项                                                                                             |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [Tiny Glade 112：外部池与绘制绑定](112-tiny-glade-external-pool-producers-and-draw-bindings.md) | pool初始8页、65,536项、4 MiB请求；writer经可变别名翻倍页数，所见表长128页；flush创建成功后换raw并写容量。相同已存键接生成/flush/同步/cull/getter；kind6接屋瓦管线、raw+两纹理MaterialData。FORCE_FINE=0时选coarse。 | 变更类别到刷新实体的完整筛选、全部公共/vertex图视图及物理重映射、实际开关/容量、失败重试与帧预算。 |
| [沙堡26：启动到Setup改色](sandcastle/26-startup-configuration-and-setup-colors.md)              | level0 phase0对应Awake的非4分支：ResetConfiguration→Prepare；后续New取当时Game当前配置，再按Refs重拷所选颜色。Prepare按seed初始化随机源后进Beach.Setup。Ground改色只写global，Water改色还写回配置。                 | 异步续行实际时刻、其他写入者、真实随机序列、当帧最终global/GPU常量和像素。                         |
| [掘地求财24：碰撞盒与invoker](digging-a-hole/24-collision-box-producers-and-invokers.md)        | Simple构造三通道启用、半径1000世界长度；AutoCamera继承Simple。组件设置经世界坐标转换生成整数半开盒，再按世界注册/过滤到octree。MainLevel启用无invoker时的自动相机回退。                                             | Blueprint/实例最终半径、转换接口舍入枚举、实际自动组件/关卡/块状态、Chaos接触与性能。              |
| [SUMMERHOUSE25：反射纹理生命周期](summerhouse/25-reflection-texture-lifecycle-and-binding.md)   | 每组件按源Camera缓存反射Camera及RT；首次分配按源scaledPixel和双scale计算；所见失效门仅组件scale差值>0.02。每次合格回调用WaterObject的MaterialPropertyBlock绑定RT，然后渲染反射相机；禁用时释放/清缓存。             | 分辨率或URP scale改变后的实际效果、Shader采样、外部销毁异常、真实相机回调及GPU状态。               |

掘地求财需要明确更正：[23](digging-a-hole/23-mainlevel-mesher-lod-and-collision-config.md) 原保留“LOD3还可能经专用盒获得碰撞”的说法；新追到 `GetUpdates 0x143E7ACFD–0x143E7AD00` 的 **node.L==0** 前置门。专用盒不能在此函数给LOD3授予资格，可见块兜底又受MainLevel上限2限制，故在所查两支中LOD3都不获碰撞bit。旧文已加更正入口，未扩展为其他系统绝无碰撞或物理现场结论。

## 贯通算例与自研含义

Tiny Glade：假设writer令已分配页从8变16，只有8 MiB创建成功才使GPU池容量从65,536改131,072；失败分支保留旧handle/容量。后续getter执行时读取当时raw，材质刷新还有实体替换门。自研宜分别维护“CPU已准备范围、GPU有效容量、图访问版本、材质引用”，把容量提交与失败处理写成独立状态变化；不能仅用一个计数代表全部资源已就绪。

沙堡：同一组profile初色进入Setup，沙色的HSV扰动只留在global，水色扰动却回写当前配置；后续Run读取二者时，沙色回到配置原色、水色继续使用扰动后色。再次Prepare是否累积水色取决于是否先New/Reset重拷。自研可把原始配色与派生配色分开存放，并明确每个pass的写入顺序；这里没有证明原作有意制造覆盖差异。

掘地求财：即使一个专用盒几何上覆盖LOD3节点，该入口仍先因LOD非0跳过专用盒；可见且LOD<=2是另一条资格条件。自研应先标清几何相交前的层级/世界/启用门，再讨论碰撞成本，不能把“在盒里”直接等同于“生成碰撞”。

SUMMERHOUSE：假设源像素1920×1080、组件scale0.5、URP scale1，首次RT为960×540。同源只改分辨率不触发所见组件scale差值门；直接把scale改0.53则可能重建，但经SetQuality先同步记录值时需另看该分支。自研可用完整descriptor作为失效依据，避免把首次分配公式误当每帧重新计算尺寸。

以上均为控制流/构造演算和独立设计建议，不是运行观察，也不包含目标代码或资产的产品移植。

## 验证、来源和后续入口

本轮继续使用既有匹配制品、PDB/本地反汇编、CIL与格式感知资源读取。新原始记录和focused回执集中在 ignored `.cache/procedural-modeling/static-producer-followup/`；可复用读取器/校验器在相应专题的tools目录。Sandcastle本轮重新计算实际使用四文件的身份摘要，沿用用户对此游戏本次调查的明确授权；另外三款复用既有身份。普通本地记录均不冒充REA Evidence。

静态复核覆盖新PE锚点/分发表/容量算术、沙堡方法和字面量、碰撞资格与组件默认值、反射CIL及场景绑定，并检查文档链接、UTF-8和工具语法；父级9组focused检查通过；分专题回执另有掘地求财26项、SUMMERHOUSE11项通过，均无失败项（各回执覆盖有交叉，不相加为独立测试数）。14份Markdown的308个本地链接、5个Python文件AST检查通过。仓库文档门禁回执单独记录。游戏/Unity启动、附加、目标函数执行、私人存档、GPU/物理/Profiler、软件安装和旧Ghidra重试全部 **Not Run**。因此没有新增帧率、峰值显存、真实绘制量或画面稳定性的实测结论。

仍有具体静态入口可继续：Tiny Glade从维护里的变更类别队列追到材质刷新实体筛选，再核公共indirection绑定；沙堡追同一配置重复Prepare的调用者和覆盖门；掘地求财追世界坐标转换虚槽与CDO/实例半径覆盖；SUMMERHOUSE从 `_PlanarReflection` 的shader分支核采样/启用门与释放后属性块状态。若只剩真实帧问题，应维持Unknown，不对同一批静态候选重复扫描充数。
