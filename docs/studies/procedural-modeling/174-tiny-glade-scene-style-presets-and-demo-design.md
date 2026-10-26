# Tiny Glade：场景风格怎样管理，以及综合 demo 可采用的分层

2026-10-26，America/Los_Angeles。配套 [172：地形随机性](172-tiny-glade-terrain-generation-and-randomness.md)、[173：建房/画水附带装饰](173-tiny-glade-context-decoration-and-local-regeneration.md)。本篇重点是主题数据到资源与表现的真实连接，不读取或修改用户 Unity 工程。

## 先回答整体机制

**Tiny Glade 的自然感来自作者资源、稳定程序化规则和统一风格配置的组合。** 地形负责起伏；建筑、道路和水域提供环境条件；不同装饰生成器选择合适的实例；场景配置再协调贴图、颜色、植物资源、天空、雾和调色。不能把这些合成一个“随机生成所有美术”的算法。

当前证据可以分成三层：

| 层           | 本机实际证据                                                                | 对用户问题的含义                                         |
| ------------ | --------------------------------------------------------------------------- | -------------------------------------------------------- |
| 大构图与资源 | 远景 terrain 网格、公开起始作品地形历史、树/植物 placement 配置和预制资源   | 部分形状与布局来自作者内容，不能全归因于运行时随机       |
| 程序化派生   | 低幅高度场、StrokeID 扰动、GPU 草/水生植物、门窗区域候选与冲突协调          | 编辑后可按环境重新求资格；稳定随机不保证对象最终总被接受 |
| 风格协调     | GladeType、语义贴图别名、公共色库加主题覆盖、settings/tod/grading及资源清单 | 同一类规则可以使用不同场景资源和表现参数                 |

172 已补高度噪声实际输入与作者起始作品，173 已区分 GPU 植被、CPU 小摆件、藤蔓和手放物。本篇不将旧研究中的地形/装饰公式重新称为新发现。

## 1. 身份与范围

工作项目 `C:/Data/WebProject/rea`；目标 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B）及匹配 `tiny_glade.pdb`（310,513,664 B），preferred image base `0x140000000`。沿用既有 GUID `d8d61d04-9e31-5b47-4c4c-44205044422e` / age1，本轮不计算新摘要。下文 native 为 preferred VA，JSON 是安装包的公开资源配置，未读玩家 Mod/存档或贴图像素。

REA native 的既有 Ghidra 300 s 超时前提未变，复用普通文件 fallback，不伪造 Evidence。新原始记录在 ignored `.cache/procedural-modeling/tiny-glade-style/`，包括精确函数反汇编、PDB caller 归属、配置摘要和 [glade_style_probe.py](tiny-glade/tools/glade_style_probe.py) 的实际读取结果。

## 2. 当前场景类型如何选择资源目录

`load_glade_texture_mappings`（`0x140A9E810`，8294 B）在 `0x140A9E837–E856` 读取输入资源所指对象的类型字节 `+0x98`，按两张 Qword 表取得名称长度和地址；再拼 `assets/glade/<name>/textures.json`。表位于 `0x143047838` / `0x143047860`，当前五项实际为：

| raw 类型 | 目录    | 当前地表/草 patch 映射               | 预置树配置条目 / 植物配置条目 | 调色 LUT |
| -------- | ------- | ------------------------------------ | ----------------------------- | -------- |
| 0        | summer  | terrain_summer / grass_patch_summer  | 9 / 4                         | lush     |
| 1        | olden   | terrain_summer / grass_patch_summer  | 12 / 0                        | cold     |
| 2        | flowery | terrain_flowery / grass_patch_summer | 9 / 1                         | candy-2  |
| 3        | autumn  | terrain_autumn / grass_patch_autumn  | 9 / 0                         | lush     |
| 4        | winter  | terrain_winter / grass_patch_winter  | 12 / 0                        | lush     |

四个 `GladeType::is_*` helper 也实际比较字节 1/2/3/4，分别是 olden/flowery/autumn/winter；不是根据目录排序补的 enum。条目数是 `trees.json` / `plants.json` 的顶层配置项数，**不是实际森林株数或全部植物总数**；plants 为空的主题仍可能有 GPU 草、灌木和其他派生装饰。

这里证实的是离散场景类型和加载资源。没有据此宣布原作有连续季节循环、自动跨季节插值或一个通用生物群系地图；[156](156-tiny-glade-sun-fog-and-weather-panel.md) 中用户要求的季节控件仍应按我方独立需求定义。

## 3. 语义贴图别名，让规则和具体美术资源分离

每个所读 `textures.json` 都有相同的十个语义键，包括 ivy_leaf_color、terrain_texture、grass_patch、canopy_color、flower1、lilypad_flower 等。材质侧实际查 `glade:terrain_texture`、`glade:grass_world_albedo_tint` 等，见 [154](154-tiny-glade-ground-materials-and-pack-decoration.md)；树材质消费见 [168](168-tiny-glade-tree-material-descriptor-producers.md)/[171](171-tiny-glade-tree-instance-to-draw-binding.md)。

加载函数的两条解析路径在 `0x140A9EAB7 / ECF5` 都实际调 `GladeTextureMappings::create_mappings`（`0x140A9DDF0`，2592 B）。后者有十处 `try_create_name_mapping` 调用。第一项将 PE 中的16 B前缀与4 B立即数组成完整 **`glade:ivy_leaf_color`**，对应输入配置中的实际纹理名。

`AssetTextureLibrary::try_create_name_mapping`（`0x140A2EAD0`，403 B）先查目标纹理条目，命中后在 `0x140A2EBE3–EC05` 取已有值、插入别名表；未命中有 false 返回。这段是名称映射，无新建纹理调用。分析器没有执行其中的 NameHash 计算或自行生成内容摘要。

**具体例。** 同一 ivy 语义槽在 summer 使用 `summer_ivy_leaf_color`，在 autumn 使用 `autumn_ivy_leaf_color`，winter 使用 `winter_ivy_leaf_color`。同一生成器无需把各主题纹理名写进每个候选规则。`black` 也是当前多项的真实映射值，但不能只凭这个名字声称所有相关实例都被关闭；资格、材质与其他开关仍需共同判断。

加载还经过 `tg_mods::overlay::resolve/read_json_config`。这与 [既有 Mod 研究](tiny-glade/mod-workshop-and-content-loading.md) 的资源覆盖片段一致。本轮没读实际启用的玩家 Mod，**bundled JSON 不能被冒称为当前运行最终值**；overlay 的完整冲突优先级和热切换完成时序未在这里重新恢复。

## 4. 公共色库先加载，再按主题覆盖命名颜色

公共 `assets/colors.json` 有37个唯一命名颜色；当前 autumn 和 winter 各有4个覆盖，另外三个主题没有独立 colors.json。覆盖项是 canopy_color_1/2、grass_1/2，而不是再复制全部37项。

`update_color_library`（`0x1417CF790`，1422 B）的实际顺序是：

1. `0x1417CF8C6–F8DA` 以公共文件加载颜色到局部 palette `&[rbp+0x210]`。
2. 由当前类型构造主题 colors.json 路径，经过 overlay resolve 和文件 metadata 分支；有相应文件的支路在 `0x1417CFA33–FA41` **仍对同一个 palette 地址**调用 deserialize。
3. 两种路径 helper（`0x1416484C0` / 531 B、`0x1416486E0` / 403 B）保存传入palette指针，再在 `0x14164856A / 874A` 把同一指针交给 `ColorLibrarySsbo::deserialize_from`（`0x1417CE930`，3678 B）。后者按输入名字选择目标颜色字段并写 RGB/alpha；本轮未将输入数组位置误当成固定 shader 成员索引，也未恢复所有未知名字/错误的策略。
4. `0x1417CFA85` 复制0x250 B到CPU色库；检查目标buffer容量后，`0x1417CFAF9` 调 `update_buffer_bytes`，本次范围长度为 **592 B**。这是共享palette发布请求，不是 GPU 已更新完成的观察。

`configwatch` 在 `0x140A4E72A` 也会调用同一更新函数，另外有实际 ECS 系统包装入口。可以证明不只有离线导入入口，不能据调用存在声称每帧重新读配置。完整触发条件、加载失败通知与图发布时序仍未穷尽。

**构造例。** 自己的一份37项基础色库，只对其中4个已存在名字赋新值，其余33项保持基础值；这演示命名覆盖。例子的数量来自当前配置，但颜色与实际最终画面没有运行验证。

一个有用的反例是：**本机 autumn/winter 的这四项 name/color 数据逐项相同，整体场景仍不能解释为同一种风格。** 两者的 terrain、grass patch、ivy、canopy 映射以及主题分支不同。154 的 floor shader raw4 专门分支，现在可以由目录表/helper 接回 winter；本轮仍不宣称四项颜色在冬季最终像素中的全部权重已解。

## 5. 风格还包含生成能力、环境和资产组合

settings.json 的以下内容是实际包内配置，不是推测的产品开关：

| 主题    | 选定显式配置                                                                                                 |
| ------- | ------------------------------------------------------------------------------------------------------------ |
| summer  | butterflies=true                                                                                             |
| olden   | rain=true、wind_strength=.2、weather_fog=.02、默认自由墙颜色3/屋顶颜色1                                      |
| flowery | ivy_flowers=true、leaf_particle_count=400、butterflies=true、默认屋顶颜色3                                   |
| autumn  | leaf_particle_count=800、butterflies=true、weather_fog=.05、默认建筑颜色5                                    |
| winter  | vegetation_around_buildings=true、ivy_leaves=true、weather_fog=.04、fog_relative_extinction=1、默认建筑颜色4 |

未给出的字段不直接解释成 false 或零；`GladeSettings::load`（`0x140C5D220`，688 B）拼 settings.json 后经 overlay read/serde 解析，读取失败及所选解析错误路径进入与 Default（`0x140C5DB10`）相同的字段赋值。各缺省字段的全部名称/单位尚未逐项对应，不把上述显式项说成完整配置表。“默认建筑颜色”也不等于已证切主题会重刷所有已有建筑。

其他入口有实际消费证据：

- `load_glade_tod_and_weather`（`0x1408F9A30`，1303 B）读取主题 tod.json；所选读取失败分支在 `0x1408F9B05` 调 `load_default_tod`。summer 包内缺少该文件，其他四主题有文件，但这不代替运行默认值观察。
- `load_glade_grading`（`0x1417043B0`，2169 B）构造主题 grading.json 并解析；当前 LUT 选择见上表，不只是统一全局加一个 saturation。
- `load_glade_particles`（`0x140BCE8C0`，863 B）实际取 `glade:leaf_particle_colors`。雪粒子加载入口（`0x1408F9760`，717 B）在 `0x1408F978E/9795` 要求 raw4，否则跳过该加载路径。
- `apply_glade_foliage_pack`（`0x140C25320`，860 B）有读取 Grass2 runtime config、rebuild_texture_names、load textures、populate SSBO、清该草subset atlas并重载LOD0 mesh的连续调用。这是另一个资源包应用入口，不是“仅换颜色”；尚未恢复它与每个主题选择/Mod切换的全部执行资格。

因此统一风格管理至少跨资源映射、色库、实例品种、生成能力和环境。它们不是可随意混搭而永远保持性能/轮廓一致的独立滤镜。

## 6. 我方综合 demo 的最小可借鉴规格

以下是自己的产品设计，不是 Tiny Glade 恢复代码，也不是已经对用户项目实施：

1. **主题只保留一个正式入口。** 在既有场景/世界配置所有者中增加稳定的风格身份，数据包含地面/岸边材质、植物和小摆件目录、命名palette、生成规则参数、天空/雾/调色默认值。不要让水、房屋、草各自偷偷决定当前季节。
2. **地形配方、装饰规则、风格资源分开。** 若要随机新地图，保存自己的world seed和生成器版本；已有地形编辑沿原状态保存。风格更换默认只换对应表现和候选资源；若产品确需改变地形配方，作为显式世界编辑处理。
3. **先做三种高价值自动装饰。** 房屋脚边小簇、门窗少量点缀、浅水/水岸植物；每类明确候选域、权重、坡度/水域/占用资格、owner和稳定随机输入。素材来自已有适当授权资源包，不为缺模型自动拼出原作形状。
4. **局部更新按真实成本拆分。** 修改时包含旧新覆盖与规则邻域；CPU摆件只重采相关区域，必要的冲突协调另计；GPU大域重筛可用有效前缀/计数，但不能把它包装成“全部局部”。远景、密草、小摆件的LOD/阴影预算分开。
5. **手放与自动派生有不同保护规则。** 程序装饰保留来源owner和规则身份，不能顺便删除玩家手放物。交互/玩法摆件需要保存其真实变化；纯表现实例可在明确版本契约下从世界状态派生，不建立第二套世界权威。
6. **先把一套风格组合做完整。** 先验收一套地形、草土、水岸、树花、小物和光雾，再做第二套主题验证映射/配置是否足够。只随机换色或每次拖动重抽全部装饰，会破坏构图和稳定性。实际FPS与生成耗时必须由用户项目的正式性能流程另行取证。

首批制作不需要复刻原作全部花草、噪声常数和五种主题。优先保留“稳定世界输入→有资格的候选→有owner的派生实例→统一风格资源”这条关系，再按自己资源包补美术内容。

## 7. 验证与保留缺口

正式 probe 实读 **29处 native锚点、6个 direct-call目标、五项目录表/四个类型helper、五份主题配置组、37项公共palette及两份4项覆盖**，Passed。原样值只保留在本地证据摘要，正式报告不导出模型、贴图或完整颜色资产。

已回答当前主题目录选择、十个语义映射入口、公共色库与主题覆盖的顺序和GPU发布请求、部分实际环境/粒子/foliage资源消费者。未穷尽所有主题切换状态、所有settings默认语义、实际启用Mod覆盖、资源热替换事务、保存/联机兼容和全部最终shader权重。172/173各自的初始作品选取、CPU环境grid身份与最终装饰发布缺口继续保留。

游戏、GPU、附加、私人配置/存档、Unity、画面、真实季节切换、性能与声音验证均 **Not Run**。没有修改原游戏、安装软件或把当前制品版本推成商店公告版本。
