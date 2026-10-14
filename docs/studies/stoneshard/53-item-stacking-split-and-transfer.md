# 53 物品堆叠、拆分与容器转移：数量提交与剩余量

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [45 装备属性](45-equipment-buff-attribute-pipeline.md)

实际拖拽与空白掉落接 [52](52-inventory-ui-drag-placement-and-dropping.md)，先堆叠再进行尺寸排格的整理动作接 [54](54-inventory-autosort-and-grid-packing.md)。这三个阶段的输入和退出分别拥有，不能互相替代。

本篇研究背包里同类物品如何合并、满栈如何保留剩余数量、拆分滑条如何生产新物品，以及运行实例和容器记录的区别。**已经恢复一条实际同类实例合并算法和它的源数量提交／销毁分支，拆分的数量扣除和新实例赋值；容器记录更新及上限选择也有局部算法。尚未恢复所有物品类型、所有所有权／特殊容器分支和失败回滚。**不能把“同图标就能堆叠”或“任何物品上限都是同一个数”当原作规则。

目标为本机Windows x64 GameMaker YYC制品，摘要与 [00](00-evidence-and-scope.md) 一致：EXE SHA256 `d45797505f04b9112c5fbb8e85c0f8cda2fa60aee954b4e108bad8a0dc514afa`，data.win SHA256 `84034525fcdef3c6fd9803628b8de6c43fea479c930e168a95906de37a2ae19c`。REA工具／提供者缺失沿用，本轮使用Capstone5.0.9静态读取，未运行、附加、修改游戏或存档、读取新存档或联网监测。下面规格为独立整理，不是恢复源码。

## 1. 三类数量及四个职责边界

| 表示／入口 | 真实用途 | 容易混淆的地方 |
| --- | --- | --- |
| 运行物品实例 `.stack` | 该实例当前数量 | 不等于格子宽高或物品质量 |
| 实例 `.stack_limit` | 本次合并的候选上限 | 不证明全类型统一配置 |
| 容器／保存数据键 `Stack` | 数据地图里的记录数量 | 与实例字段大小写不同；需显式同步 |
| `.charge` | 拆分入口的另一种数量分支 | 非can_stack分支不能直接改成stack |
| `scr_item_stack_same` | 找可接收同类实例并真正修改数量，返回剩余量 | 名字same不能当纯等价判断 |
| `scr_inventory_stack` | 调用合并器、提交源数量，再选择销毁／放置等分支 | 调用存在不证明任何输入都能成功 |
| `scr_item_stack_container` | 容器条目与实例数量协调，特殊类型／上限处理 | 与同类实例枚举算法并不完全相同 |
| `scr_item_stack_build` | 堆叠变化后的形态／索引重建，受size_can_change等门禁 | 不是复制一个数量的简单赋值，也不保证不改变占格 |

入口地址：合并 `0x1410ebaf0`，总编排 `0x1410e0ab0`，容器协调 `0x142033340`，重建 `0x140ac2070`。完整原始列表见 [本轮堆叠登记](../../../_reference/stoneshard-study/twelfth-stack-native.json)。拖拽点击分派与二维自动整理由同目录的独立研究覆盖，本篇不把数量合并算法当完整UI或矩形装箱算法。

## 2. 同类实例合并：真实筛选条件

合并器先记录当前调用物品的 id、owner和object_index，然后进入由当前object_index选择的实例集合（`0x1410ebf80–0x1410ebfc1`）。这是对象类型选择，**不是sprite相等、显示名相等或完整data地图相等**。资源选择器的派生类枚举细节未在本篇复原，因此不能把“当前object_index作为选择输入”升级为所有候选都进行了精确object_index==比较。

对每个候选的实际门禁：

1. 候选id不等于原调用物品id：`0x1410ec057 / 0x1410ec05e`。
2. 候选未装备而第5参数真时跳过；候选已装备时可绕过这一额外过滤：`0x1410ec064–0x1410ec0a1`。第5参数未提供／为undefined时，入口有设为true的默认处理。它不是“所有装备中物品永远不能合并”。
3. 候选 stack < stack_limit：`0x1410ec0a7–0x1410ec0f1`。不可比较−2及非负比较结果跳过，满栈不会先被加出溢出再无条件销毁源。
4. 第2参数真时，候选owner必须等于第1参数给定owner：`0x1410ec0f7–0x1410ec156`。
5. 候选owner等于原调用物品owner且第3参数真时跳过：`0x1410ec166–0x1410ec1b5`。
6. 候选data中 `delivery_time` 的查询结果必须通过“undefined或pointer_null”检查：键 `0x14986f0a0`，查询 `0x1410ec295`，检查结束 `0x1410ec5c0`。这里不是比较两个交付时间；有效数值0也不能自动当缺失。

第4参数送后续重建助手，第1／2／3／5参数控制上下文和过滤。本篇按参数位置描述，没有只凭布尔值猜UI模式名。主编排有多个六参数调用，其中第5参数既能为false也能由调用者提供，不能只使用默认值解释所有拖拽操作。

这些已选门禁中没有完整data键值等价比较；但上层可能已按物品家族分类，特殊容器还有其他算法。因此能确认的是**这个合并器采用类型选择、身份、装备、所有权、容量和交付字段门禁**，不能声称原作无条件忽略新鲜度、盗窃归属或所有品质字段。

证据：[实际同类合并器](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Script_scr_item_stack_same.txt)。

## 3. 数量转移：先加总、钳上限，再返回余数

令正常非负整数输入：候选数量S、上限L、待转移数量R，且已满足S<L和所有资格门禁。所选执行顺序如下：

```text
sum = S + R
候选.stack = sum
R = 0
如果 sum > L：
    R = abs(L - sum)
    候选.stack = L
重建这个候选的堆叠表现／索引
如果 R == 0：结束枚举
否则：继续找下一个可接收候选
返回 R
```

候选加总位于 `0x1410ec60e`，待转移参数0清零位于 `0x1410ec64e–0x1410ec655`；超上限比较 `0x1410ec68a`，计算 `L−sum` 在 `0x1410ec707`，取绝对值 `0x1410ec72e`，候选上限写回 `0x1410ec7c8`。重建调用 `0x1410ec884`；参数0==0的退出检查在 `0x1410ec8d7–0x1410ec91a`，最终返回该参数0的当前值 `0x1410ec960 / 0x1410ec967`。

**这里没有ceil取整。**绝对值助手 `0x1451de020` 对double做AND符号位掩码；掩码 `0x147c643c0` 为 `0x7fffffffffffffff`。本模块其他函数存在ceil／floor调用，不应把它们套到这条合并分支。对正常整数，`abs(L−sum)=sum−L`；分数、负数、NaN和不合法上限不是本例的有效库存模型，原入口的全部异常处理未恢复。

**具体部分合并例：**源待转移7，符合资格的A已有18／上限20，B已有4／上限10，按枚举先A后B。A先得25，再钳为20，R=5；B得9，不超10，R=0；立即停止。结果A=20、B=9、源剩余0，数量守恒 `7+18+4=20+9`。

**满栈失败例：**A原本20／20，就在容量门禁跳过；若没有其他候选，返回R=7。它不会仅因同类存在就把源改成0。候选顺序来源为运行时实例枚举，本篇没有证明它按背包坐标、创建时间或最小剩余空位排序。

证据：[绝对值助手](../../../_reference/stoneshard-study/twelfth-stack-abs-helper.txt)、[绝对值掩码](../../../_reference/stoneshard-study/twelfth-stack-abs-mask.json)。

## 4. 调用者负责源数量提交与退出

`scr_inventory_stack` 的一条真实分支在 `0x1410e3b27` 调用同类合并器，把返回值保存到局部；随后选当前物品的可写stack并赋返回值（`0x1410e3b4c–0x1410e3b71`）。然后通过正常数值≤0助手检查（`0x1410e3b93`），成立才在 `0x1410e3c5c` 请求 `scr_item_destroy`；大于0转其他后续路径。

因此上节7全部被接收的例子，在到达该调用者分支时，源stack被提交为0，源进入物品销毁请求。若合并后剩5，源提交为5并走保留／继续转移分支。**合并器本身返回剩余量，不直接证明原源实例已被删除；源的退出权在这个调用者。**销毁助手、保存条目替换、容器添加等还有各自上下文，不是“把图标删掉”这一个UI操作。

总编排还调用 `scr_item_can_add_to_container`、`scr_inventory_get_cell_free`、`scr_inventory_add_item`、`scr_inv_container_add` 等。容量不足时能否把剩余保留在手上、原格或外部容器，需要具体UI入口与相应分支一起解释；仅凭这些调用名称不能保证“放不进去自动丢地上”。本篇不补失败回滚原子性：机器指令显示候选先修改，再处理源，不能把它叫已证明的数据库事务。

证据：[总编排及源提交](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Script_scr_inventory_stack.txt)、[物品销毁助手](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Script_scr_item_destroy.txt)。

## 5. 拆分滑条：数值预览与正式扣除分开

真实对象 `o_split_stack_slider` 有两个相关事件：`Other11@0x1434dff90` 更新滑条与左右预览，`Other10@0x1434dce00` 执行拆分。

Other11先调用继承行为，然后把滑条自身value送 `math_round`（`0x1434e0087`）并写回。进入guiParent上下文后读取父valueMax与父value，计算：

```text
slider.valueLeft = parent.valueMax - parent.value + 1
slider.valueRight = parent.value
```

减法 `0x1434e016d`，加1 `0x1434e01b0`，左侧写回 `0x1434e01c4`，右侧写回 `0x1434e021e`。**这里真实有+1，不能把它改成普通N−k示意。**valueMax生产者／上限含义没有在本篇完整恢复，不能宣布valueMax一定等于原栈数量N。若构造父valueMax=9、父value=3，预览左7、右3；要把这与原栈N=10一致，需要调用者确实以N−1作为valueMax，此绑定仍需其他UI证据。

正式执行Other10先读取itemID，进入源物品上下文收集object_index、owner与data，读取Fresh、is_execute、HasOwner、Town、Stolen_Days、Stolen_Days_Timestamp等记录供后续处理。读取这些字段不等于已经逐字段与目标栈比较。

进入can_stack分支：在 `0x1434dd666` 取源stack，`0x1434dd695` 减滑条value，`0x1434dd6b0` 提交源字段；随后读回源数量并与0比较，选择重建／后续替换路径。另一分支操作charge，不能把可用次数拆分当普通stack堆叠。

后续创建交互物品代理，进入新实例上下文写owner，再按新实例can_stack选择写stack=value（`0x1434dded5–0x1434ddef6`）或charge=value（`0x1434ddf27–0x1434ddf48`），最后 `scr_item_select(true)` 调用 `0x1434ddfc5`。另外两段 `scr_item_crime_transfer` 请求说明来源／盗窃记录另有转移职责，本篇没有宣称新物品完全忘记原归属。

**具体拆分例：**构造源stack=10、执行时value=3、can_stack真、源与新实例选择成功。源先提交7，新交互实例后写stack=3并被选中，`10=7+3`。这与预览9／3例只有在valueMax真实绑定9时一致；不是已经运行观察的数字。创建新实例失败、源在期间被销毁、非法value以及容量不足的完整回滚尚未恢复，不能保证在所有错误路径都保持守恒。

证据：[拆分正式执行](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Object_o_split_stack_slider_Other_10.txt)、[滑条预览](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Object_o_split_stack_slider_Other_11.txt)。

## 6. 容器记录：数量地图修改与上限选择

容器协调助手有object名称／asset解析、容器条目data提取、金币与投石弹药类型分支，以及 `scr_stack_data_replace` 调用，不能等同于第2节实例枚举的同类资格。

`scr_stack_data_replace@0x142038c70` 对传入地图查询 `Stack`，再依次减第0参数、加第1参数，把结果通过ds_map_replace写回同一键。正常数值局部规则为：

```text
newMapStack = queriedMapStack - p0 + p1
```

键槽 `0x149893d40`，查询 `0x142038e1b`，减法 `0x142038efa`，加法 `0x142038f3f`。查询另带fallback槽 `0x149893d80`，该槽未固定成静态数值，因此例子只使用键确实存在的地图。

**记录更新例：**已存在map["Stack"]=12，p0=5、p1=2，局部结果9。它说明函数做数量替换，不证明一次背包拖拽必定传这两个参数，也不保证地图句柄失效时仍成功。

上限助手 `scr_item_get_stack_limit@0x142036fe0` 在第2参数缺失时生产候选数组 `[100,250,499]`（真实常量槽 `0x149553148/0x149553158/0x149553168`），按序检查每个bucket：正常数值第0参数≤bucket，且bucket≤当前第1参数时，把第1参数改为bucket，最后返回第1参数。后续bucket大于已经缩小的第1参数时不再替换。因此默认递增数组的正常模型是选择“满足第0输入且不超过当前cap的最小bucket”，无满足项则保留原cap。

例如构造p0=180、初始p1=499，100不足，250满足并把cap设250，499随后大于250不替换，返回250。构造p0=600、p1=499，无满足项，返回原499。**这不是说所有物品能堆499个**；caller类型门禁、第2参数自定义数组与实际stack_limit来源仍决定它用在哪里。`scr_item_stack_container` 的相关调用在 `0x142033a17`，投石弹药另走专用助手。

证据：[地图数量替换](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Script_scr_stack_data_replace.txt)、[上限选择](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Script_scr_item_get_stack_limit.txt)、[容器协调](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Script_scr_item_stack_container.txt)。

## 7. 堆叠容器候选排序与二维整理的区别

`scr_item_container_sort_by_stack@0x1410e9250` 收集候选，包括按匹配物品累加stack的过程（`0x1410e9c22–0x1410e9c38`），最后使用array_sort及专用比较器。比较器 `0x1410ed4e0` 取A[1]、B[1]并在 `0x1410ed66c` 计算 **B[1]−A[1]**；正常数值是第二字段降序。完整第二字段在所有候选家族中的生产与同分稳定性尚未恢复，因此这里只确认比较规则。

具体构造候选条目A第二字段8、B第二字段20，compare(A,B)=12，通常升序比较契约下B排在A前；等值返回0不证明其排序稳定。算法选择堆叠转移候选，**不能替代二维背包整理的按物品尺寸、类别、空格扫描和放置顺序**。同目录自动整理研究单独解释这些消费者。

证据：[候选构造及排序](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Script_scr_item_container_sort_by_stack.txt)、[比较器](../../../_reference/stoneshard-study/twelfth-stack-disassembly/gml_Script_anon_scr_item_container_sort_by_stack_gml_GlobalScript_scr_inventory_stack_13125402_scr_item_container_sort_by_stack_gml_GlobalScript_scr_inventory_stack.txt)。

## 8. 自研可借鉴的契约、覆盖与风险

独立实现可把结果显式定义为 `AcceptedQuantity`、`RemainingQuantity`、`SourceDisposition` 和 `FailureReason`：资格计算、容量计算、数量提交、源退出、表现刷新分别有明确所有者。把stack与charge区分为不同能力；类型匹配、品质／新鲜度／归属兼容性用自己的规则明确指定，不按图标判断。自研如果要求失败原子性，应先计算转移计划，确认新实例／格位有效后一次提交，失败保留原数据；这属于自己的改进，不是已证明原作使用事务。

已回答：一条真实同类实例合并器的主要门禁、部分合并公式、剩余量与源提交／销毁、拆分数字扣除与新实例选中、地图Stack局部替换、默认上限桶选择及候选第二字段比较器。部分回答：多种容器转移、形态重建／尺寸变化、盗窃归属转移。未回答：所有物品类型的完整可合并键、所有UI修饰键／容量失败后的精确位置、异常回滚／重入、全部上限配置、valueMax实际生产绑定。

未做：游戏操作、自动拖拽、修改或存档验证；没有带出原作代码或资产。风险：把局部类型选择当全局兼容规则、把返回剩余量当已销毁源、把地图Stack与实例stack混用、忽略拆分预览真实+1、或在缺失记录键时擅自将未知fallback当0。
