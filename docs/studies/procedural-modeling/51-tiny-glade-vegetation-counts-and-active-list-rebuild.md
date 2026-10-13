# Tiny Glade 植被计数、活跃列表与重新生成

本篇补上[46陆地植被](46-tiny-glade-land-vegetation-and-exclusions.md)的清旧缺口。灌木/花使用共享间接绘制计数和追加slot，草使用逻辑ID、活跃计数及活跃ID列表。已找到实际初始化生产者，但跨系统调度和某次编辑后的完整时间线仍未贯通；不能将它们称为已确认的逐地块局部补种。

身份、原始范围和独立验证见[52账本](52-tiny-glade-roof-and-vegetation-followup-ledger.md)。CPU地址为RVA，shader位置为原precomp文件偏移。下面分别注明指令事实、ABI推导和运行前提。

## 1. 灌木和花的旧计数在哪里重置

`9EA890 reset_indirect_args`实际取得两个写绑定：

- `9EA9C3`：DispatchIndirectBuffer。
- `9EA9D5`：DrawIndexedIndirectBuffer。

函数准备两份staging数据。`9EAA6F–9EAA91`将rdata的16字节`{0,1,1,0}`重复8次，形成128字节；`9EAB05–9EAB12`将rdata `3032538`的460字节复制进另一staging。

460字节是23条、每条20字节的DrawIndexedIndirectCommand模板。全部条目的instanceCount、firstIndex、vertexOffset、firstInstance为0。与本轮灌木/花有关的第9、10条五字段全为0，其他条目保留各自indexCount：

```text
indexCount序列：
300,96,57,36,6,60,6,48,174,0,0,2817,4716,66,180,15,
900,18,900,18,18,18,18
每条其余四字段均为0。
```

模板原字节SHA256为`2c6ad45a4b973c83a7c33b3d23f9435895a8ab7774decbc38f8a0954c100f31a`，文件偏移`3031538`，长度460B。128B模板使用的是8个16B块，不能未经核对当成8条12B Vulkan dispatch command。

随后`9EAD02 → 177B110`登记带捕获数据的graph callback，实际回调`1A88AC0`两次经backend vtable的`+388`槽提交staging源和目标buffer。临时三个qword依次来自`{capture[+28]的u32,0,capture[+10]的u64}`和`{capture[+2C]的u32,0,capture[+18]的u64}`；这符合`{srcOffset,dstOffset,size}`的copy参数形状。size来自staging descriptor，128/460是已确认的staging申请长度，不直接冒称已恢复descriptor的正式类型。**调用参数和数据流是观察；该ABI符合buffer copy是推导。**本轮没有独立恢复该backend槽的正式API名和全部提交屏障。

若模板copy按预期完成，对应目标的灌木/花instanceCount即归零。没有证据表明这个过程把灌木/花实例payload逐字节清0，也没有由单次函数解码证明它每帧都运行。

## 2. 候选通过后怎样追加实例

[46](46-tiny-glade-land-vegetation-and-exclusions.md)的真实绑定仍然有效：`9AE210`选择garden生成，`B32850`选择building周边生成，均写同类型BushInstanceSsbo/FlowerInstanceSsbo和DrawIndexedIndirectBuffer。

本轮重核四个候选生成模块：合格灌木对 `draw_commands[9].instanceCount`做atomicAdd(1)，合格花对第10条做同样操作，atomic返回的旧值作为实例写slot。因此计数是当前有效前缀的长度，并发执行时具体slot顺序不保证稳定。

两个spawn入口本身没有找到该计数clear；`write_rg_buffer`的实际行为是取得/缓存frame写绑定，不等于清零。旧计数初始化来自上一节独立的reset路径，不能把两个函数中某个名称含write的调用当作reset。

第9、10条模板的indexCount也为0。本轮关注instanceCount清旧与实例追加，没有据此声称完整的可绘制command建立已经恢复；其余字段怎样最终用于绘制仍需相应生产者和消费者。

## 3. 草单独清的是活跃计数

`B20F60 grass2_compute_main`在`B211F3`取得Grass2ActiveInstanceSsbo写端，`B21203`取得Grass2ActiveCountSsbo写端；`B2123A–B21248`复制的是ActiveCount绑定，`B2126A`实际调用 `E29980 GraphApi.clear_buffer`。

clear继续编排callback；选定 `E7D540` 回调经backend `+3B8`槽传入offset=0、size=`UINT64_MAX`、value=0。**全范围零填充是这些实参支持的ABI推导，正式API槽名未独立确认。**没有把同函数内的ActiveInstance绑定误认为clear目标。

之后同一个CPU函数选择 `grass2/build_draws` 主模块（`B21379`），`B21395`取literal `{tag=1,45056,1,1}`，`B213AF`登记dispatch。这确立了构图调用中的clear→producer连接；实际GPU依赖执行、同步和每次编辑调用频率还需要运行或完整graph证据。

没有看到该入口清整个Grass2ActiveInstanceSsbo或Grass2ClumpAttribSsbo payload。它们可以保留旧字节，活跃前缀决定本次哪些逻辑ID进入选定消费路径。

## 4. 45056个输入如何形成不同逻辑ID

`grass2/build_draws.precomp`主模块从文件偏移108开始，长度20836B。GPU入口先使`i>=45056`返回；选定正常分支的逻辑ID映射为：

```text
i < 14336：k = i + group*14336，最多4个group
i >= 14336：k = i + 43008
```

主区域可能覆盖`k=0..57343`四组逻辑记录；背景部分对应`57344..88063`，共30720个输入。**88064只是这些映射的逻辑ID范围上限，不能当本次实际活跃数量。**候选仍经过mask、类型及资格选择。

这也接上[46草位置序列](46-tiny-glade-land-vegetation-and-exclusions.md)：多个主区group共享模14336的位置序列，背景使用独立30720序列。位置序列ID、逻辑clump ID与活动slot不同，不能合并成一个“草的编号”。

合格k在模块文件偏移`3180 / 4068 / 5118`附近的实际输出链为：

1. 将packed属性写到 `clump_attribs[k]`。
2. 检查debug isolate为`UINT32_MAX`或等于k。
3. 成立时atomicAdd `active_count[0]`，取得旧count作为slot。
4. 写 `active_instances[slot]=k`。

debug筛选在clump属性写入之后。隔离一个k不等于禁止所有其他合格k更新属性，只是限制进入本条活跃列表的ID。并发atomic建立唯一slot，但不建立稳定列表顺序。

## 5. 旧payload为什么可能保留而不被读取

选定LOD0实例筛选consumer（`nani/cull_and_bucket_grass2_lod0.precomp`）已核对如下入口逻辑：

```text
count = active_count[0]
若i >= count：return
k = active_instances[i]
使用clump_attribs[k]
```

所以在ActiveCount清零完成、producer完成、consumer读取同一资源且执行依赖正确的前提下，只有本次活跃前缀能从这个实例筛选入口进入属性读取。尾部旧活动ID和未再次入选的旧clump字节不必立即擦除。这建立的是计数/列表失效，未建立逐株删除事件或稳定实体缓存协议；它也不能单独证明所有最终绘制入口都遵守同一前缀。

本轮另解码 `active_cull_dispatch_args` 模块，它写：

```text
dispatch.x = (activeCount + groupSize - 1) UDiv groupSize
dispatch.y = 1
dispatch.z = 1
```

这是独立GPU模块的指令事实，但未确认该模块在上述主草CPU路径中的实际绑定，不用它补写整条调用链。groupSize=0和u32加法溢出也没有额外保护证据。

## 6. 局部补种还有什么未接上

garden资源`+29B`的清除属于garden raster状态分支，不能当成Bush/Flower实例清理。[45共享发布](45-tiny-glade-shared-invalidation-and-rebuild.md)与[46](46-tiny-glade-land-vegetation-and-exclusions.md)的PlantSample copy/publish/upload是另一条链；已有发布不证明植物消费者按DirtyTiles逐地块生成。

当前核对的两个spawn仍扫描整个90×90或150×150候选域，主草dispatch仍覆盖45056个输入。它们可能由变化条件决定何时执行，但本轮没有完整恢复条件、跨系统顺序、每帧频率和一次编辑到最终绘制的时间线。

可以确认“全域候选重新筛选＋有效前缀重建”的机制片段，尚不能确认“只清修改地块中的旧植被并逐地块补种”。阴影草模块和其他consumer也没有一律归入主列表生命周期。

## 7. 构造例：计数重建与活跃前缀

这是自造状态演算，明确前提是初始化完成、producer完成、consumer按正确依赖读取同一资源；没有运行发行版。

灌木旧instanceCount=7、花旧instanceCount=12。460B模板使两计数为0。假设garden新增2个灌木、building新增1个，atomic共分配slot0、1、2；假设新增4个花，分配slot0..3。结果计数分别3、4，尾部旧payload可以残留。两spawn并发时slot分配先后未知；如果reset晚于spawn，此结果不成立。

草旧ActiveCount=5，clear使其为0。假设合格逻辑ID为`{17,14353,57344}`，debug=`UINT32_MAX`：各自先写clump属性，再分配slot0..2并登记k。consumer仅在`i<3`读取，旧slot3、4不进入该入口。活跃列表可以是这些ID的不同排列；逻辑k仍保持其映射身份。

若debug改为17，只有17进入列表，但另两个合格k仍可能先写属性。由此可见“属性更新过”和“本次成为活跃对象”不是同一个条件。

独立dispatch模块再取activeCount=130、groupSize=64、无溢出：`(130+63) UDiv64=3`，输出`{3,1,1}`；count=0时输出`{0,1,1}`。这个算例不证明CPU实际调用该模块。

## 8. 独立实现规格与限制

自研可以采用固定逻辑候选ID＋属性数组＋紧凑活跃ID前缀，使全域重新筛选时无需逐项擦除大payload。另用明确的graph读写依赖保证计数初始化、生成、消费顺序。若需要严格局部更新，则应独立设计每地块allocation或版本协议，不能从本轮全域路径推导原游戏已有这种结构。

未做：未启动/附加游戏、未读取存档，未测真实重建频率、GPU屏障和性能；没有完成跨系统scheduler或树/森林全系统调查。本次仅补研究文档，不改变REA生产行为，未运行项目实现测试。

风险：buffer copy/fill槽仍保留ABI推导；尾部payload安全依赖消费者遵守计数/ID规则，本轮只核选定LOD0入口。调度前提未观察，构造例不能作为实机帧顺序或最终可见数量的证明。
