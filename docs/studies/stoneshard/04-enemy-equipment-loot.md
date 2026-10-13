# 04 敌人装备、弹药与掉落生成

[总目录](README.md) · [证据范围](00-evidence-and-scope.md) · [技能与协作](05-enemy-skills-cooperation.md)

本模块解释强盗弩手的创建配置，以及它绑定的掉落回调如何查询物品候选、生成物品和设置属性。结论来自已完成的静态调查，不代表已经观察到游戏运行。本页的伪代码是我们自行编写的行为规格表达；没有恢复原始 GML，也不用于替换游戏代码。

## 1. 模块职责与边界

需要区分三个职责：

1. **实体创建**：初始化弹药数量、上弦状态、敌人类别和弩箭类型，并绑定掉落回调。
2. **掉落候选生成**：从物品参数表或候选物品池取候选，结合共享规则决定是否生成物品。
3. **生成后的属性调整**：在获得有效生成结果后，给生成物写入 `Duration` 等属性。

创建阶段的战斗状态与死亡后的掉落生成不能直接合并。例如，`ammoCount=17` 说明单位的弹药状态是 17，不说明背包里存在 17 个可拾取物品；掉落回调查询生成一把弩，也不证明这就是敌人战斗时持有的同一个物品实例。

已验证 Create 绑定本对象的 `loot_script`。本轮没有恢复死亡入口到此回调的所有调用条件，因此下文“掉落流程”指已绑定回调及其内部规则，不宣称每种死亡方式都必然执行全部分支。

## 2. 输入、数据与状态

### 2.1 对象身份

研究对象是 `data.win` 中 OBJT 172：`o_bandit_arbalester`。继承链为：

```text
o_bandit_arbalester → o_Bandit → o_Grey_Army → c_human → o_enemy → o_unit
```

对象记录起点为文件偏移 **9400672**，父对象 ID 字段位于 **9400700**；父对象为 OBJT 3892 `o_Bandit`。Create 事件记录位于 **9400828**，动作位于 **9400840**，引用 code ID **18600**。这些是容器元数据中的关联，不是通过对象名称推测的继承关系。

### 2.2 已确认的创建状态

| 字段 | 弩手 Create 写入值 | 解释与边界 |
|---|---|---|
| `ammoCount` | 闭区间随机整数 14…20 | 战斗弹药状态；可拾取物品数量未验证 |
| `reload` | true | 原始字段值确认；该字段全部状态转换未恢复 |
| `crossbowIsLoaded` | false | 新建时未上弦；技能拒绝条件见下一模块 |
| `isCrossbowmanEnemy` | true | 启用共享检查中的弩手分支 |
| `arrowTypeUsed` | OBJT 5302 `o_leafshaped_bolt_used` | 使用的对象类型引用 |
| `arrowTypeDrop` | OBJT 4552 `o_loot_leafshaped_bolts` | 掉落类型引用；不证明数量等于 `ammoCount` |
| `loot_script` | 匿名回调入口 `0x1429916c0` | 对象专有掉落配置入口 |

`arrowTypeSprite` 另有数值 4789，但它处于 sprite 语义的位置，不能把这个数值当作 OBJT ID。资源编号的解释必须跟随参数和字段的所属资源类型。

### 2.3 共享物品数据

`scr_find_weapon_params` 实际读取 `weapons_csv`、`armor_csv` 和 `item_buffer`，迭代表行、建立候选 list。表数据驱动物品候选这一点已经确认；尚未恢复完整表值和每列的语义。

弩手对弩、剑、盾分别调用 `(4, 4, category)`，category 是 `"crossbow"`、`"sword"`、`"shield"`。两个 4 的确是调用参数；目前不能称它们为“物品等级最小值和最大值”。这类命名只有在表字段和比较路径一起验证后才能成立。

## 3. 创建算法：数量随机，状态显式初始化

### 3.1 范围随机的已确认算法

范围助手 `0x1451de280` 对本次整数输入的局部规则为：

```text
width = abs(a - b) + 1
offset = nonnegative_random_integer() modulo width
result = min(a, b) + offset
```

这里 `nonnegative_random_integer()` 表达已追到的底层取数和清除符号位流程，省略尚未恢复的完整 PRNG 实现。它不是原游戏函数名。

输入 14、20，得到 `width=7`，余数属于 0…6，因此结果属于 **14…20，含两端**。如果余数为 3，结果是 17；余数为 0 和 6 时分别得到 14 和 20。这个演算只说明边界和映射，不是观察到的某次随机结果。

底层以取模得到范围，未进行本轮已确认的拒绝采样验证，不能称数学上严格均匀。即使理论偏差很小，也应把“边界确认”和“分布确认”分开。

### 3.2 行为伪代码

```text
initialize_arbalester_state(unit):
    unit.ammoCount = random_integer_in_closed_range(14, 20)
    unit.reload = true
    unit.crossbowIsLoaded = false
    unit.isCrossbowmanEnemy = true
    unit.arrowTypeUsed = object_type(5302)
    unit.arrowTypeDrop = object_type(4552)
    unit.loot_script = arbalester_loot_callback
```

这只是已确认字段的局部规格。Create 还初始化技能、被动和其他属性；这里没有省略后再宣称已经完整表达 Create。

### 3.3 正常与边界情况

- 正常整数输入 14、20：得到上述七个整数之一。
- 范围助手计算 `min` 和绝对差，说明边界表达不只依赖参数先后顺序；本页只使用已核对的 14、20 和 30、60 输入。
- 非整数、负数、溢出、异常 RValue 类型没有完成验证，不给出通用随机库契约。
- 初始未上弦与初始 `reload=true` 是两个字段的并存状态；不能据字段名字自行认定两者矛盾或把其中一个改为 false。

## 4. 掉落生成：以一把弩为具体例子

### 4.1 逐步数据流

1. 回调先抽取整数 30…60，保存为本分支的属性值。
2. 调用 `scr_find_weapon_params(4, 4, "crossbow")`，取得候选查询结果。
3. 把候选、单位 x/y、参数 100、参数 1，以及若干 undefined 默认项传给 `scr_weapon_loot`，共 9 个参数。
4. 检查返回的对象/实例选择结果是否可进入后续处理。
5. 对有效生成结果调用 `scr_inv_atr_set`，键为 `"Duration"`，值为先前抽取的 30…60。

真实字符串槽通过静态构造核对：`0x1498aec30` 绑定 `"crossbow"`，`0x1498aec40` 绑定 `"Duration"`。不能仅靠字符串在文件中相邻就认为它们属于同一物品分支。

### 4.2 行为伪代码

```text
generate_one_equipment_branch(unit, category):
    duration_value = random_integer_in_closed_range(30, 60)
    candidates = query_item_parameters(4, 4, category)
    generated = shared_weapon_loot(
        candidates,
        position = unit.position,
        parameter_4 = 100,
        parameter_5 = 1,
        remaining_parameters = defaults
    )

    if generated_selects_valid_instances(generated):
        for each selected generated instance:
            set_inventory_attribute(instance, "Duration", duration_value)
```

`parameter_4`、`parameter_5` 的写法故意保留接口位置：本页已经追到第 4 参数被送入 chance 处理，但并未恢复第 5 参数及全部默认参数的最终含义。伪代码不能为了好读而给未知参数补上未经验证的名字。

### 4.3 构造演算

假设弩分支的范围余数为 12：宽度是 `60-30+1=31`，`Duration` 写入值为 `30+12=42`。再假设候选查询和共享生成返回一个有效物品实例，则该实例接收到 `Duration=42`。

这里无法确定最终是哪个弩型号，也无法断言 42 表示耐久百分比、绝对耐久点、时间秒数或其他单位。名称 `Duration` 和赋值范围已确认，**单位和归一化方式仍未知**。

### 4.4 剑、盾与生成边界

剑和盾重复相同结构，但分别重新抽取 30…60，不能把三个分支解释成共享一次属性随机数。各分支通过独立参数查询调用进入共享物品生成器。

`scr_weapon_loot` 还读取角色数据和属性、查询已有武器索引、检查库存武器数量，并处理品质、sprite、统计等。它不是只有“阈值抽签→生成一个对象”的简单函数。因此参数 100 即使在 chance helper 内走成功分支，也不能推出每次回调必落一把弩。

已核对的边界包括：物品存在性检查失败则退出；抽签返回 false 则跳过掉落；返回实例选择结果无效则跳过 `Duration` 写入。候选为空、物品表缺失以及所有生成错误返回的处理仍未完整恢复。

## 5. 其他掉落候选与阈值

| 候选/候选池 | 已确认内容 | 回调内调用点 | 不能推出的内容 |
|---|---|---|---|
| 远程技能书 | OBJT 1634 `o_loot_treatise_ranged4`；阈值 3 | `0x1429938f1` | 不能称准确掉率为 3% |
| 食品池 | apple、pear、carrot 等真实传递的物品候选；阈值 5 | `0x142993035` | 不能称所有食品逐个独立掉落 |
| 补给池 | bandage、splint 等候选；阈值 5 | `0x142993456` | 不能称已恢复完整补给分布 |
| 弩箭袋池 | 三种箭袋候选；阈值 10 | `0x142993b57` | 不能由候选数量推出等概率 |
| 材料碎片 | 回调读取 ArmorDurability 后进入相关处理 | `0x142993c4a` 后；loot 在 `0x142993eca` | 不知道全部护甲到碎片的映射和最终数量 |

技能书是很小且明确的例子：回调将静态常量 1634 作为物品类型候选传递，第四参数 3 送入 `scr_loot`。这证明了候选与阈值的关系；完整掉落率还取决于运行时状态和所有上游条件。

## 6. “阈值 3”为什么不能直接写成“3%”

### 6.1 已确认的 helper 规则

`scr_loot` 先检查 `object_exists`。对象有效后将第 4 参数传给 `scr_chance_value`，成功结果为 1，失败结果为 undefined；false 路径退出，不进入掉落阶段。

`scr_chance_value` 的正常有限数值路径可以表达为：

```text
chance_result(threshold, success_value, failure_value):
    if success_value is omitted:
        success_value = 1
    if failure_value is omitted:
        failure_value = 0

    if threshold >= 100:
        return success_value

    effective_threshold = max(threshold, unresolved_floor_slot)
    draw = random_integer_in_closed_range(0, 100)
    if ordered_less_than(draw - effective_threshold, -epsilon):
        return success_value
    return failure_value
```

这是行为表达，不是异常类型与 NaN/undefined 完整契约。`ordered_less_than` 还排除了比较 helper 的 unordered 返回；它不是对任意异常输入都成立的普通数值 `<`。

### 6.2 条件化演算

在以下条件全部成立时：floor 槽不提高阈值、阈值为正整数 3、epsilon 足够小且为正常正值，则 0…100 中成功的整数为 **0、1、2**。理想等概率模型是 `3/101≈2.9703%`，不是 `3/100`。

这个数只是对 helper 的条件化演算，**不是已确认的技能书最终掉率**。没有解决 floor 槽、没有恢复所有上游条件，而且 PRNG 取模实现也不能自动假定严格等概率。

### 6.3 floor 槽的证据限制

槽 `0x149874248` 在 PE `.data` 的未承载区域，属于 .bss 状态。文件未包含其运行时内容，不能仅凭文件中没有值宣称运行时一定为 0。

补查完整 `.text` 的 88,972,288 字节，搜索 `48 8d 0d` 所表示的 `lea rcx,[rip+disp32]`，共找到 226,733 个候选，没有精确指向该槽的匹配。附近槽存在匹配，但不构成目标槽初始化证据。这是限定指令形式的负结果，不排除其他初始化或间接写入；**floor 的运行时语义仍未确认**。

## 7. 关键证据位置

VA 为 EXE image base `0x140000000` 下的静态地址，不能直接作为某次 ASLR 后进程地址。容器位置为 `data.win` 文件偏移。

| 问题 | 位置 | 证据含义 |
|---|---|---|
| 弩手对象/继承 | OBJT 172，偏移 9400672；父字段 9400700 | 父对象是 3892 |
| Create 事件关联 | 9400828 / 动作 9400840 | code ID 18600 |
| 原生 Create | `0x142994d30`；EXE file offset 43598128 | 创建配置入口 |
| ammoCount 写入 | 字段取得 `0x142994f57`；随机调用 `0x142994f73`；写入 `0x142994f97` | 14、20 的参数及返回值数据流 |
| 使用/掉落箭类型 | `0x14299512e` / `0x142995170` | 5302 / 4552 |
| 回调绑定 | `0x142995b51` / `0x142995b63` | loot_script 与实际函数指针 |
| 掉落回调 | `0x1429916c0`；EXE file offset 43584192 | 对象专用配置入口 |
| 弩候选查询/生成/赋属性 | `0x142991c72` / `0x142991d9d` / `0x142991eb2` | 三阶段数据流 |
| 弩与属性键静态构造 | `0x1429961fb` / `0x14299621a` | crossbow / Duration 槽绑定 |
| 参数表读取 | `0x1410d96d9` / `0x1410d9781` | weapons_csv / armor_csv |
| 技能书候选/阈值 | `0x142993741` / `0x1429938f1` | OBJT 1634 / 第 4 参数 3 |
| loot chance 调用/拒绝 | `0x1416f155f` / `0x1416f156e` | 阈值判定及退出 |
| 正常 chance 随机路径 | `0x1413e58ee`…`0x1413e5991` | max、随机、相减、比较、返回分支 |
| 范围随机助手 | `0x1451de280`…`0x1451de2c7` | 含两端范围映射 |

本地证据：[第二轮调查记录](../../../_reference/stoneshard-study/second-loot-skill-findings.md)、[原生解码索引](../../../_reference/stoneshard-study/second-native-loot-skill-analysis.json)、[对象元数据](../../../_reference/stoneshard-study/enemy-object-metadata.json)、[静态构造](../../../_reference/stoneshard-study/second-native-loot-skill/arbalester-static-init.txt)、[floor 定位扫描](../../../_reference/stoneshard-study/second-native-loot-skill/chance-floor-constructor-scan.json)、[随机助手与感知调查](../../../_reference/stoneshard-study/second-perception-findings.md)。这些 `_reference` 文件是本地未版本化证据；其他机器可能没有这些文件。本页已写入必要的步骤、输入和位置，不能把链接存在误认为证据已公开发布。

## 8. 可以独立借鉴的设计

可以借鉴“战斗状态、物品候选生成、属性后处理”分开负责的结构。我们的产品可以独立定义：

- 战斗装备与掉落产物是否共享身份；共享时如何避免属性不一致，不共享时如何解释给玩家。
- 使用明确的 `conditionPercent` 或 `durabilityPoints` 字段，避免单位不明确的 `Duration`。
- 将候选查询参数定义成有名字的条件，例如类别和自有品质范围；不能把原游戏未确认的两个 4 原样解释成等级。
- 明确约定百分概率与随机整数的边界；如果产品要求准确百分概率，可选择自己的无偏范围采样和 0…99 判定。
- 为物品表缺失、空候选、生成失败保留诊断结果，并记录随机种子以复现实验。

这些是我们自主设计的建议，**不是已经证明 Stoneshard 采取的具体实现**。独立实现应使用自己的物品表、参数、算法代码和合法资产，不复制目标中的函数、表或资源。

## 9. 未完成内容与风险

未验证：完整物品表和列定义、4/4 语义、`Duration` 单位、掉落物与战斗装备的身份关系、死亡调用全链、floor 槽、最终物品分布、弩箭掉落数量、异常参数契约。本页不能作为完整掉落模拟器的精确规格。

后续 [34 敌人自救](34-enemy-self-treatment-and-survival.md) 已独立找到弩手Create尝试生产绷带/夹板、绑定owner并加入consum_list的证据，因此“战斗时有无治疗资源”现可由实际生产链解释；不能只从本页掉落候选反推携带。真实武器表中Drifter Sword行见 [32](32-physical-attack-damage-resolution.md)，仍未据此补齐本页4/4过滤或最终掉率。

本轮未执行游戏、未读取存档、未做随机分布实验、未修改安装目录。主要风险是把阈值当百分比、候选当必出、资源 ID 类型混用、局部 helper 结果当最终产出。文档对这些分别保留边界；没有发现需要改变游戏文件的理由。
