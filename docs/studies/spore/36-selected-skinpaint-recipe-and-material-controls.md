# 36 一份实际皮肤配方：主题、效果引用与区域分布

[目录](README.md) · [35 变形与接缝](35-skin-pattern-shape-edits-and-seams.md) · [07 基础皮肤](07-skin-texturing-and-patterns.md)。仍限定登陆后、部落前的生物与对应编辑器。此次从名称入口推进到了**本机PROP配置及效果引用图的局部解码**；没有运行游戏或恢复绘制调用。

## 原作证据：实际读了什么

沿用00的EXE身份；本轮重新散列并读索引的是Spore_Game.package与PatchData.package，摘要仍与00一致。两包各读三份明确`ce_skinpaint_`候选：长颈鹿主题、条纹ML细节、melt基础层，共六份完整小PROP。选择依据是固定注册表和实际描述字段，不把所有skin或flora名称当陆地生物。

两包效果目录数量分别为0与18。Patch的18个候选中，12个声明解压大小不超过本轮1MiB预算，只检查普通组件段边界；另外6个只保留索引，没有解压。再明确选定Patch中的两个目录，读取段表、全部Visual记录的引用/边界、导出与导入表、Sequence，以及完整Distribute段。Particle、Settings、其他组件和资源段的内容仍未解码，也没有导出原作笔刷或纹理。

| 本机候选目录 | 完整资源键：type/group/instance | 解压bytes | 读取覆盖 |
| --- | --- | ---: | --- |
| csa | `ea5118b0:40450200:2c978da4` | 57,862 | 84个Visual边界/引用、42个导出、26个Sequence、34个Distribute |
| editors | `ea5118b0:40450200:bafc5ca1` | 631,889 | 981个Visual边界/引用、485个导出、200个Sequence、282个Distribute |

这些是资源中声明的对象数，不是每只生物的粒子数、花纹数量或每帧调用次数。csa/editors/gameEffects_1~是社区注册名称，不证明本轮目录被陆地游戏实际加载。包与变体优先级也未恢复。

入口、偏移、压缩/解压摘要和实际值见[本机解码记录](evidence/local-selected-skin-recipe-resources.json)；索引筛选另见[候选盘点](evidence/local-skin-recipe-candidate-inventory.json)。

## 原作：长颈鹿主题真的保存了三组绘制与颜色

选定PROP键 `00b1b104:406a0200:05475ea3`，描述是`giraffeArmor Theme`。Game与Patch的四个解析属性相同，但每对解压载荷都有三字节差异，分别位于条纹88–90、主题72–74、melt74–76；这些字节尚未解释，原摘要与差异保留。因此解析值一致不等于字节相同，也不证明加载顺序。

| 属性 | 实际结构 |
| --- | --- |
| description `00b2ccca` | `giraffeArmor Theme` |
| parent `00b2cccb` | 指向同组PROP `91ad3433`，注册名TemplateSkinPaintTheme；未解析其继承应用 |
| paintThemePaints `b0e066a7` | 三个key值，type/group都是0，instance见下表 |
| paintThemeColor1s `b0e066a8` | 三个三分量颜色值，原始浮点值保留 |

| 数组槽 | 绘制instance及注册名 | 配置颜色，近似显示 |
| --- | --- | --- |
| 0 | `32fe45f6` skinpaint_base_zebroid | (0.443137, 0.364706, 0.203922) |
| 1 | `8ac01a79` skinpaint_coat_giraffe | (0.443137, 0.141176, 0.196078) |
| 2 | `203219f6` skinpaint_detail_giraffeLimbs | (0.443137, 0.141176, 0.196078) |

引用名与公开base/coat/detail概念吻合；**本机数组三个槽的读取顺序、颜色空间、颜色如何进入笔刷仍未恢复**。不能拿上述浮点颜色直接预测截图像素。

关键编号区别：这些type/group为0的绘制key并不是已定位的DBPF资源键。它们的instance实际匹配效果目录的导出名hash，再进入Visual对象。不能直接在包索引中找`00000000:00000000:32fe45f6`就认为资源丢失。

[注册标签证据](evidence/public-selected-skin-property-labels.json)固定FX提交与源码行。六个文件名的FNV-1确实等于相应ID；四个property名称使用显式登记编号，其名称哈希并不等于property ID。不能对所有名字统一套同一哈希推断。

## 原作：配方引用到分布器的完整局部链

两目录导出表中的五个目标均已匹配，所选路径上的引用检查通过：

```text
PROP绘制槽 instance
  → 匹配目录 export(group=0, nameHash)
  → Visual index
  → blockType=4：Sequence index
  → Sequence step：另一Visual index
  → blockType=0x23：Distribute index
  → Distribute.particleIndex：0x26 Particle段中的索引
```

这里每一步编号都有自己的容器，不能把Visual 642当Particle 642，也不能把type4直接当分布器。type4由固定社区源码确认是Sequence；它返回Visual类型0。某些路径另包含0x22材质Settings。路径是**资源引用图，不是已观察的运行调用图**。

### 长颈鹿主题的区域差异

| 绘制项 | csa中的路径摘要 | Distribute实际原值 |
| --- | --- | --- |
| base_zebroid | export→Visual16→Sequence3→多个Visual；另有Settings6/7 | torso记录3/4：spacing约0.08、ordered=true；limbs记录5/6：约0.05；parts记录7/8：约0.15，二者都引用Particle7 |
| coat_giraffe | export→Visual47→Sequence15→Visual46→Distribute24 | Particle30，region=-1，spacing约0.12，ordered=false |
| detail_giraffeLimbs | export→Visual60→Sequence21→Visual59→Distribute30 | Particle40，region=6（limbs与parts位），spacing约0.07 |

区域位来自固定格式：torso=1、limbs=2、parts=4、back=8、belly=16、joints=32。region=-1作为特殊原值保留，不能自行等同全身或所有位有效。共用Particle7也不能证明两次绘制完全相同，Visual变换和Particle内容没有解码。

这说明**同一主题的不同绘制项可引用不同区域与spacing配置**。spacing的米制/归一化单位、区域分类、ordered实际采样方式与最终图案密度仍未知。因此不能用0.05声称“每5厘米一条纹”。

### 单独的条纹细节

PROP `00b1b104:406a0200:00f3892f`的描述是`skinpaint_detail_stripesML`，paintThemePaints前三槽为`0,0,103691ce`；同槽颜色约(0.125490,0.125490,0.125490)。零引用的默认/继承行为未知，不把前两槽解释为覆盖成黑色。

其非零绘制引用在editors目录对应：

```text
export 103691ce → Visual642 → Sequence86
  → Visual640 → Distribute121 → Particle168
  → Visual641 → Distribute122 → Particle169
```

两分布器region都为2（limbs），spacing都约0.01，ordered/cover均为false。这是实际的区域组织例子，仍不证明两条记录对应左右镜像、两种笔刷方向或每条腿一个粒子。`stripesML`的界面名称、解锁条件及玩家预览效果没有核对。

另一份`skinpaint_base_melt`只在槽0引用`8c7aa8c3`；它在editors中进入Visual407→Sequence5，包含Settings2/3及Distribute2→Particle1，spacing约0.06、ordered=true。材质初始化与区域分布可以由同一效果引用组合表示，但初始化公式仍未知。

## 原作参数不能直接拿去当自研默认

某些未解释的浮点字段字节是`CD CD CD CD`，按IEEE float读成有限的约−431602080。读取器保留原始字节及数值，没有归一化或改成0。它可能是未使用字段/填充候选，但未恢复读取者，不能宣称原作一定忽略它，更不能作为身体范围参加计算。

所有所选Sequence的时间范围保留原值，常见为(-1,-1)。该值的执行语义、是否等待上一步完成、具体时间单位都未知。数组顺序不是调度发生的证明。

## 格式与读取器验证

[固定格式证据](evidence/public-selected-skin-recipe-container-format.json)核对容器v4、Visual v1、Sequence v1、Distribute v1–2及字段元数据。主要边界如下：

- 普通组件段、资源段各有type/version/size，未知类型按size保留摘要并跳过；不能按猜测的对象长度寻找下一段。
- Visual没有整段length；完整按字段布局检查后才能到导出表。每条基础49bytes加LOD与Block，Block基础109bytes加LOD比例项。
- Distribute含NUL字符串与可变选择表：`42+字符串内容bytes+8*selectCount`，不是每条都强制42。
- Sequence为`8+12*stepCount`；timeRange是LE float[2]，索引/计数是BE。Distribute的bodyRange也有LE例外。
- 32-bit长度前缀不是固定32个元素。完整消耗所选段、索引类型和范围、重复类型、循环引用及混端序都需要检查。

社区原reader某些未知type访问缺少保护；本研究自己实现有界读取器，没有把它当作原游戏代码照搬。读取器只面向已选资源，保留明确失败，不能宣称兼容所有EffectDirectory版本。

## 自研：主题是组合入口，表面分布与材质混合各自拥有状态

下面的结构和公式是我们的规格，未沿用上述原作颜色、间距或脚本资产。

```text
OwnTheme { slots[Base,Coat,Detail], paletteLinear, styleSeed }
OwnPaintLayer { eligibleRegions, densityPolicy, surfacePattern, brushes, channelRules }
OwnBrushOutput {
  surfaceCoverage
  optional pigmentLinearRGB, colorAlpha
  optional heightDeltaMeters, heightAlpha
  optional specularTarget, specularAlpha
}
OwnMaterialSample { colorLinearRGB, heightMeters, specular }
```

主题负责选层和颜色；35的表面系统负责区域、坐标、条纹/斑点覆盖；材质层负责颜色/高度/高光合成。颜色刷不必写高度，湿润刷可以只改高光。骨骼权重不当成材质alpha；技能动作不直接改烘焙主题。

从结构层到材质的流程：

```text
compileOwnTheme(theme, body):
  resolve every declared layer; distinguish explicit Empty from MissingDependency
  validate all channel rules, units, colours and finite values
  for layer in explicit Base → Coat → Detail order:
    evaluate its eligible surface using current shape coordinates
    generate coverage using 35's relative/physical policy
    generate brush outputs from declared morphology curves
    compose only enabled material channels
  derive normal from final height and current surface metric
  publish with mesh/UV/material key from 35; keep old bundle on failure
```

自研形态曲线可用明确节点的分段线性插值，输入范围与端点clamp/wrap由每条曲线声明。例如用u∈[0,1]的肢体位置控制斑点大小，长度变更先按35决定用物理或归一化尺度。原作变量数组、笔刷ID和曲线求值还未解码，不能声称与这套曲线等价。

### 自研三通道演算

颜色输入均为线性RGB；高度用米，高光是本例0–1标量。Base设颜色(.2,.4,.6)、高度0.0002、高光0.3。

Coat覆盖0.8，三个通道alpha均0.5，有效alpha=0.4。色目标(.8,.2,.1)，高度增量+0.001m，高光目标0.8：

```text
color = lerp(oldColor, pigment, coverage*colorAlpha) = (.44,.32,.40)
height = oldHeight + coverage*heightAlpha*heightDelta = .0006m
specular = lerp(oldSpecular, target, coverage*specularAlpha) = .5
```

Detail覆盖0.5、alpha0.25，有效alpha=.125；色目标(.05,.05,.05)，高度增量−.0005m，高光使用独立声明的衰减因子0.7：

```text
color = (.39125,.28625,.35625)
height = .0005375m = .5375mm
specular = .5 * (1 + .125*(.7-1)) = .48125
```

这三个公式不同。不能把高度、高光和颜色都塞进一次RGB alpha混合。原作alpha/add/multiply等枚举名字没有恢复其色彩空间或实际公式。

### 与身体变形联动

加宽或拉长先更新35的表面坐标/覆盖，再重新计算材质样本；改变颜色只使对应通道失效；新增部件用自己的稳定ID与接合政策，不重新随机整个身体。若只改湿润高光，没有理由重建骨架或改变斑点色；若改高度，法线是下游依赖，必须一起更新。

Explicit Empty保留前面已有材质；缺少声明的笔刷/层返回MissingDependency；不拿一个黑色默认图继续宣称生成成功。应用前校验整层，避免错误到一半留下半张新皮肤。步态和灵魂策略不参与材质随机数，除非产品显式设计了行为外观层。

## 检查、未做与风险

16项读取边界检查通过，覆盖段范围、混端序、变长字段、未知段、索引类型、Visual/Sequence导出、循环、原字节保留等；10项独立材质算例通过。两包真实配置、两个目录的字段边界/末尾与五条选定导出路径另外实际读取并核对。见[本轮检查](evidence/selected-skin-recipe-verification.json)。这些不构成原作运行或渲染验证。

已答：选定主题/条纹的配置内容，以及PROP→导出→Visual→Sequence→Distribute→Particle索引的静态链。部分回答：区域控制、spacing原值与材质设置的组合入口。未知：Particle方向/笔刷/标量变量、Settings初始化、调度、单位、实际颜色与编辑后重绘。

未做：游戏启动/附加、私存档、Graphics/Content大包扫描、笔刷或完整皮肤资产导出、Particle/Settings数据解码、原生代码链恢复、原作像素/性能测试、用户生产实现和仓库构建。Particle包含多个可变结构，当前只确认格式和引用；本轮没有用不完整字段跳读冒充完整解码。

风险：社区格式与本机执行语义仍未对齐；配置名称不证明界面或阶段加载；两包相同记录不证明覆盖优先级；有限值不一定有效参数。下一步最有价值的是仅解码已定位的Particle168/169及长颈鹿对应Particle，查方向/尺寸/笔刷引用，再用最小陆地样本验证形态编辑的触发规则。
