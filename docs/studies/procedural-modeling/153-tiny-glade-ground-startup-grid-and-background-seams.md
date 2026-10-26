# Tiny Glade：初始地面、规则格网与背景接缝

后续 [172](172-tiny-glade-terrain-generation-and-randomness.md) 已补近处高度 shader 的低幅基础噪声、StrokeID 扰动和公开起始作品地形历史；它与本篇远景资产/格网分工共同解释自然起伏，不代表完整世界 seed 随机山体生成器已恢复。

2026-10-24，America/Los_Angeles。供 [152 地面制作交接](152-tiny-glade-ground-layers-and-resource-pack-handoff.md) 使用，表面颜色与资源包装饰见 [154](154-tiny-glade-ground-materials-and-pack-decoration.md)。本篇只读发行制品，所有 native 地址为 preferred VA，image base 为 `0x140000000`。

**新接通的链不是“先随机生成一整座山”。启动代码分别创建可变形的近处格网、加载现成远景地形，并由后者生成背景高度图；可编辑高度和水域继续改变近处顶点。另有从发行包起始作品进入会话的分支。** 初始内容、渲染载体和玩家编辑是不同阶段。

## 身份与证据范围

目标为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`，65,612,184 B；相邻 `tiny_glade.pdb` 为 310,513,664 B。本轮用 [pdb_identity.py](digging-a-hole/tools/pdb_identity.py) 读取 PE CodeView 与 PDB information stream，GUID 同为 `d8d61d04-9e31-5b47-4c4c-44205044422e`、age 1。GUID/age 是制品内标识，没有计算新摘要。

当前会话未暴露 REA MCP；既有 native 全程序分析超时没有已知前提变化。本轮沿技能的有界静态 fallback，使用本地 DbgHelp、VS dumpbin 与现有 SPIR-V reader，不安装、重注册或重复长分析。结果是普通文件/PDB/指令证据，不是新 REA Evidence。

新原始记录位于 ignored `.cache/procedural-modeling/tiny-ground/`，包括 `pdb-startup-and-session.json`、`pdb-background-helpers.json`、`startup-glade-terrain.asm.txt`、`background-terrain-maps.asm.txt`、`load-game-session.asm.txt`、`floor-spirv.json` 与 `ground-layers.json`。[ground_layers_probe.py](tiny-glade/tools/ground_layers_probe.py) 从当前输入复核实际调用、字面量、模块边界及关键 shader 操作。报告不输出原网格顶点、索引或贴图。

## 1. 启动代码区分近处地面与远景资产

`startup_glade_terrain`（`0x140A5D5D0`，5,011 B）有以下实际数据流：

| 对象         | 生产或加载                                                                             | 选定消费者                                                                                      |
| ------------ | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 近处 floor   | `0x140A5D6B1` 调 `grid_gen_cw`（`0x140A5C690`）；该调用传入三个 `0x5C=92` 参数及零偏移 | `0x140A5D740–0x140A5D791` 注册 `floor` 并实际取得 `country_core/terrain_editing/floor` pipeline |
| 远景 terrain | `0x140A5DB5E–0x140A5DB72` 取 `assets/meshes/terrain.json` 并调用 `load_json_as_mesh`   | `0x140A5DD82–0x140A5DDCC` 注册 `terrain`，实际取得 `country_core/distant_terrain` pipeline      |
| 背景水域足迹 | `0x140A5DBEB–0x140A5DBFF` 加载 `assets/meshes/water_plane.json`                        | `0x140A5DCA4` 调 `water_plane_footprint_ws`（`0x140B0B280`）                                    |

加载的 terrain Mesh 先保存在 `rbp+0x20`，`0x140A5DCDE` 把其地址作为第四实参，`0x140A5DCEC` 调 `generate_background_terrain_maps`（`0x140B0B460`）。该函数在 `0x140B0B4D4` 保存第四实参，`0x140B0B680–0x140B0B683` 再把它交给 `rasterize_heightmap`（`0x140B09020`）。因此“现成地形网格参与背景图生成”有连续传参证据，不只是函数名相近。

后者还有第二次 rasterize 调用（`0x140B0BA03`），以及两次 `upload_r16f_texture`（`0x140B0C2E0`、`0x140B0C32C` → `0x140B0A710`）。全部背景图通道、两次栅格化各自的过滤回调与 CPU 光栅器完整填充规则尚未展开；不将它们直接称为同一个最终可编辑高度图。

**资源观察。** 当前 `terrain.json` 有 1,078 个位置、6,099 个索引，原始 Y 范围约 `[-25.322, 27.011]`，1,071 个不同 Y；它本身不是全平源网格。原始 XZ 约覆盖 ±450，但这是资源坐标统计，不是本轮测得的可建造范围或最终场景边界。近处 floor 则是另一条格网路径，不能把两者合并成一个网格数量。

## 2. 近处格网怎样成为真实起伏

`terrain_editing/floor.precomp` 的主 vertex 模块始于文件 `0xA1`，2,372 words。CPU 已实际选择该 pipeline；以下是该模块真实运算，不是用名称推测它会位移。

shader 从顶点索引差取得 `i`（w1164–1173），再计算：

```text
gx = i % 93
gz = i / 93
XZ = (2 * ((g + 0.5) / 93) - 1) * 67.16666412353516
uv = XZ / 130 + 0.5
h = mix(-2.5, 24, terrainHeightmap.R(uv))
```

最后一式在 w1299 采样、w1311（文件 `0x151D`）执行 FMix，写入位置的 Y（w1319）。这会改变 clip position 和真实轮廓，绝不是 fragment 里只改颜色。格网间隔约 1.44444 世界单位；高度图分辨率与几何格网密度是两个量，不能把 512×512 高度样本说成 512×512 显示顶点。

**构造例，未执行 GPU。** 对内侧格点、无后续岩/水位移且高度图 R=.2，h=2.8；改为 R=.3，h=5.45，顶点 Y 真实增加 2.65。只改变草地 RGB 或法线纹理不会得到这一高度差。完整主/视觉高度图的生产、读回仍见 [31](31-tiny-glade-terrain-strokes-and-heightfield.md)、[34](34-tiny-glade-terrain-readback-and-local-updates.md)。

## 3. 两圈边缘不是简单硬拼

令 `d=min(gx, gz, 92-gx, 92-gz)`。w1325–1401 只在 d≤1 且背景高度 bounds 有效时进入特殊衔接：

- **内一圈 d=1：** 以缩放后的 XZ（乘 `0.9384615421295166`）采背景高度，Y 取 `max(h, bgHeight + 0.1)`，见 w1515–1599。
- **最外圈 d=0：** 采背景高度后，Y 取 `max(bgHeight - 0.05, h - 3)`，见 w1421–1505。

这里实际是 GLSL 指令 **FMax（40）**，不是 FMin。背景采样使用另一套尺度/轴变换，与近处 `XZ/130+.5` 不同；不要直接把一张图按另一张的 UV 使用。

**构造例。** gx=1 的 X 约为 −65，gx=0 的 X 约为 −66.44444，构成外围延伸。令近处 h=3：内圈采到背景 3.2 时取 3.3；外圈采到背景 2.2 时取 `max(2.15,0)=2.15`。这说明它有实质高度重叠/下沉处理。是否在所有相机、地形和 GPU 上完全无缝仍未运行验证；不把这个局部规则包装成通用无缝保证。

## 4. 坡面法线也取自高度

w1981 和 w2142 对高度图 gather。对四个编码高度 `h0..h3`，所选梯度为：

```text
d = (h2+h1-h3-h0, h0+h1-h3-h2)
gradient = (0.5 * 26.5 * d) / (130 / heightmapDims)
tx = normalize((1, gradient.x, 0))
tz = normalize((0, gradient.y, 1))
normalOut = cross(tz, tx)
```

叉乘在 w2101，法线和位置分别在 w2364/w2367 写出。这里两个切向量各自归一化，不能把该 cross 结果未经检查就称为单位长度。后续 fragment、岩石与水岸还会修改显示；没有声称所有最终法线都等于 CPU 三角形叉积。

**构造例。** 四个样本相等，则梯度为零，tx=(1,0,0)、tz=(0,0,1)，输出方向为 (0,1,0)。改变相邻高度会改变坡面梯度；这不同于在水平面上仅加一张“看起来有坡”的 normal map。

## 5. 初始作品、空世界与玩家编辑要分别解释

`load_game_session`（`0x140915620`）的所选缺省/回退路径在 `0x14091642B–0x140916497` 按 demo override 选择 `assets/starting-builds/full` 或 `demo`，继而读取目录；另一条件支使用 `intro`。本轮没有完整恢复每种 NextSession 变体、首次游玩判断、作品选择策略和所有回退，所以不把该分支描述成“每次新建都随机选一个模板”。

本轮只解析发行包里的三个公开 `history.json`，没有读取用户存档：

| 公开起始作品   | Terrain 标签编辑记录数 | Water 标签编辑记录数 | 可以说明什么                                                                         |
| -------------- | ---------------------: | -------------------: | ------------------------------------------------------------------------------------ |
| intro          |                      0 |                    0 | 所读 history 的编辑链只有 13 条 WallNewSystem 标签；不等于已证明最终场景地形处处为零 |
| 05-rocky-lake  |                      6 |                   29 | 预置内容可以携带地形/水编辑历史                                                      |
| 17-two-islands |                      8 |                   33 | 另一份内容也带地形/水历史，不需要由一张固定平面表达两岛                              |

**记录数不是山丘数、实例数或当前活跃笔画数。** intro history 引用一份 snapshot，但当前该公开目录没有 snapshots 子目录；本轮未臆造或读取不存在的内容，不以 history 的标签缺席外推其最终快照。

已证玩家编辑仍沿 [31](31-tiny-glade-terrain-strokes-and-heightfield.md) 的折线、坡面参数、高度候选最大值、复合和平滑链。**在本轮检查的启动函数、四个 floor 模块和三个公开配置中，没有恢复出一个可据此宣称为原作统一“新世界随机山脉生成器”的完整入口。** 背景资产、起始作品和后续编辑的存在已经清楚；全产品是否另有随机初始分支仍未知。

## 6. 可独立实施与验证边界

用户已明确要求真实地形生成。可在自己产品现有地形权威中实现初始高度及后续编辑，统一给显示、采样、碰撞、保存和联机消费；初始缓丘/建造区/水岸的参数自行定义，不能把研究中未恢复的初始配方当作原作事实。

远景应优先采用已有资源包地形或场景，用明确重叠/边缘过渡衔接；草木石头和建筑继续采用资源包，不能借“程序地形”自行制作装饰模型。几何起伏、低成本表面细节、实例装饰分别预算。所选格网、shader 和局部更新方式只能解释工作结构，不能代替实际 GPU 时间或保证 60 FPS。

已答：近/远地面分工、已加载资产到背景图的传参、规则格网读取高度、边缘两圈和高度梯度法线。部分：起始作品加载分支、背景通道和后续完整发布。未答：所有空世界初始化条件、全主题初始配方、最终采样绑定/碰撞一致性与实际视觉接缝。运行、画面、性能、项目编译和测试均 **Not Run**。
