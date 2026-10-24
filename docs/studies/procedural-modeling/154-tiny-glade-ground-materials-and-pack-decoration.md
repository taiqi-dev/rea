# Tiny Glade：地表颜色、湿岸与资源实例装饰

2026-10-24，America/Los_Angeles。近处高度、远景资产与接缝见 [153](153-tiny-glade-ground-startup-grid-and-background-seams.md)，制作范围见 [152](152-tiny-glade-ground-layers-and-resource-pack-handoff.md)。身份和本轮 reader 同 153，未运行 shader 或游戏，也未读取用户 Unity 项目。

**地形轮廓、地表着色和装饰实例三者都需要。** 颜色噪声不会增加真实山坡；一片片草花灌木也不是地面网格上的随机三角形。用户的模型约束是资源包优先且禁止自行制作建筑/装饰模型，不影响已经明确要求的真实地形生成。

## 1. 近处地表与远景贴图不是同一个入口

`startup_glade_terrain` 实际取 `country_core/terrain_editing/floor`，并取得 `dirtpath_heightmap`、`dirtpath_1`、`dirtpath_2`、`dirtpath_grass`、`glade:grass_world_albedo_tint`、`mud` 等纹理引用，见 `0x140A5D7AE–0x140A5D899`。这是 CPU 端的实际查取，不等于每个引用在每个运行分支都影响最终像素。

另一个实际分支取 `country_core/distant_terrain`（`0x140A5DDB5`），随后查 `glade:terrain_texture`（`0x140A5DDE3`）。当前 `assets/glade/summer/textures.json` 将它映射为 `terrain_summer`，同时单独提供草 patch、花与 world albedo tint 的映射。因此不能仅看到一张叫 terrain 的贴图，就把近处地面、草、远景和湿岸全说成使用相同材质。

主题配置是静态映射事实；主题继承、运行时 override、实际 sampler 状态和每帧选择仍保留限制。这里没有读取或导出任何原作贴图像素。

## 2. 草地底色是调色板加空间变化

floor 主 fragment 模块始于文件 `0x25BE`，12,233 words。w3342/w3359 从 `color_library.data` 读成员 18/19，实际成员名为 `grass_1` / `grass_2`；w3396 起以世界位置相关输入计算一段空间噪声。选定普通分支在 w3859/w3873 得到：

```text
weight = clamp(noiseValue - 0.4, 0, 1)
grassColor = mix(grass_1.rgb, grass_2.rgb, weight)
base = 0.75 * grassColor
```

noiseValue 在此是原指令中 `130 * dot(...)` 的结果，不是已知属于 [0,1] 的随机数。完整噪声库名称和所有数值范围本轮不赋名。另有 theme raw ID=4 的分支调整空间尺度和颜色；不能把普通分支说成全主题统一表达式。后续还有道路、材质和颜色合流，base 不是最终屏幕色。

**独立构造例。** 给两种自选颜色 (0.2,0.35,0.1)、(0.3,0.45,0.15)，并假设该中间 noiseValue=.9，则 weight=.5，mix=(.25,.4,.125)，base=(.1875,.3,.09375)。这演示空间调色能打破大面积纯绿，但所有顶点位置保持原值；不能用它替代 [153](153-tiny-glade-ground-startup-grid-and-background-seams.md) 的真实起伏。

## 3. 湿岸同时影响颜色与部分几何

fragment 的 w8003–8062 实际采 `water_mask.tex.G`、`material_data.mud.rgb`，执行：

```text
wetWeight = smoothstep(0.4, 0.5, waterMask.G)
intermediateColor = mix(previousGroundColor, sampledMudColor, wetWeight)
```

泥土在此按另一套重复 UV 采样。后续还有泥土加深、garden、rock 和道路等分支，因此这是局部过渡，不是最终全部岸线公式。[07](07-tiny-glade-water-shape-and-banks.md) 已证明水域还可进入高度场复合；本轮补的是实际 floor vertex 的后续几何条件：

```text
slope = length(heightGradient)
waterFactor = smoothstep(0.2, 0.6, waterMask.G)
steepFactor = smoothstep(2, 3, slope)
shownY = mix(previousShownY, -0.8, waterFactor * steepFactor)
```

位置修改在 vertex w2290–2336，最后写出的是该位置，故它不是单纯把湿岸涂成棕色。此前还有岩石相关下沉以及背景接缝；不能把 shownY 直接等同于原始地形编码值，更不能据此断言 CPU/碰撞一定错位：原作另有 Terrain/VisualTerrain 两条高度链，其完整衔接是独立问题。

**构造例。** G=.45 时，颜色混合权重=.5；自选前色 (.3,.4,.1)、泥色 (.1,.08,.04)，得到局部中间色 (.2,.24,.07)。另给 vertex G=.4、slope=2.5、前级 Y=2.8，则两个 factor 都约 .5，shownY 约为 1.9。输入是假设值，没有执行原 shader，也没有据此承诺原作实际岸宽或水深。

## 4. 装饰是有资格的资源实例

本轮按资源/指令覆盖区分：

| 对象         | 已有依据                                                                                                                                                                    | 不能外推的内容                                                                    |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 草           | [46](46-tiny-glade-land-vegetation-and-exclusions.md)、[51](51-tiny-glade-vegetation-counts-and-active-list-rebuild.md)：ID 可重算候选位置，活动列表/计数另管；高度取地形图 | 候选总数不等于当前可见草数，不能把所有 LOD 合成一个密度                           |
| 灌木与花     | 46 的 CPU 实际选择 garden / around-buildings 生成管线；typed 实例 buffer 接候选、密度与尺寸                                                                                 | 原作全部品种与资源离线制作方式未知，不将输出矩阵说成实时造出完整植物拓扑          |
| 部分预置植物 | 当前 summer `plants.json` 有四个 placement 引用，使用已有 `plant_thistle`、`plant_leafy` mesh 名                                                                            | 本轮只复核配置，未新接通该配置到每个运行实例的 loader；资源可用不等于当前必定显示 |
| 树           | [56](56-tiny-glade-tree-resources-growth-and-canopy.md)、[61](61-tiny-glade-tree-mesh-processing-and-publication.md)：现成网格经干冠加工、实例参数和展开/风动               | 不证明原树实时生成枝条，更不授权复制原网格                                        |
| 小石与岩层   | `startup_terrain` 实际加载 `assets/meshes/path_pebble.json`；[57](57-tiny-glade-rock-mesh-displacement-and-masks.md) 已证另一条岩层单元位移                                 | 道路碎石、普通岩石、岩层三者不合并成统一散布器；全部密度/清旧规则未恢复           |

其中灌木选定路径会拒绝道路、部分水域、foliage、建筑内部等样点；岩石存在且坡度超过门槛时也可排除。它不是“所有植被在所有陡坡都一律禁止”。花园与建筑周边的密度、尺寸规则各不相同，详式保留在 46。

草另用双通道 removal 图：R 控制排除，G 控制缩高。道路可先缩短草再形成留白，建筑相关图、花园、水岸和岩层又各有贡献。整体 culler 的五点采样与逐顶点资格不同，不把一个样点的 R=1 就说成整个 patch 已消失。

**已证公式的构造例。** 按 46 的选定输入，path.R=.15、water.G=0，其余建筑/花园/岩/foliage 条件为零：得到 removal.R=0、G=.65，草缩高但未被该 R 排除。只把花园邻样改为 .403，可令该 mask 样点 R=1；整体 patch 是否剔除仍需它自己的五点判断。

## 5. 对资源包制作的明确建议

以下是自己的制作规格，不是用户项目已经完成或现有代码出错的断言：

1. **先让地面轮廓成立。** 在正式地形中保留可建造缓平区域，并形成外围缓丘、小起伏和连续岸坡；使用同一地形给资源包模型贴地。不能只加颜色噪声。
2. **优先采用完整资源包组合。** 先选已有草土材质、树丛、花草、小石及作者搭好的场景组合，核对尺寸和风格再布置。缺资源记录缺口，不以基础体、自动拼模或自造 mesh 替代装饰。
3. **让规则服务构图。** 路边、建筑脚、水岸有明确留白，密度随区域变化；候选位置稳定，重编辑只影响必要区域。坡度约束按资源类型定义，不把地面全塞满等距实例。
4. **保持颜色与实例一致。** 地面草色、资源包植物和远景使用协调调色；噪声负责连续变化，贴图负责表面，实例负责轮廓与近景细节。不要重复叠多层同用途噪声后失去控制。
5. **分层控制成本。** 远处减少小草石密度/阴影成本，复用材质与实例批处理；静止时不重复生成整片地形与装饰。具体参数和性能结论需要项目侧实际证据，不能从原作 shader 操作数推定 FPS。

首批验收应能同时看到起伏剪影、可用建造区、资源包装饰层次及连续水岸；项目侧还须核对高度/碰撞/保存一致性和局部修改范围。本会话不执行这些验收。原作主/视觉地形完整同步、所有材质分支、sampler/filtering、运行主题与实际帧率仍未知。
