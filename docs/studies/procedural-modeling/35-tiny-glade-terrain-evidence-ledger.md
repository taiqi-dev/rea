# Tiny Glade 地形与建筑落地证据账本

本轮范围：地形笔刷、坡面与高度场、CPU高度采样、墙高与石基标量、石基面带/窗洞、地形读回及局部重建。取证时间锚为 **2026-10-12 20:43:51 PDT，America/Los_Angeles**，由时间工具 `2026-10-13 03:43:51 UTC` 换算；不用于推断游戏更新时间。

## 身份与方法

| 制品 | 路径 | SHA-256 |
| --- | --- | --- |
| EXE | `E:/Steam/steamapps/common/Tiny Glade/tiny-glade.exe` | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| PDB | `E:/Steam/steamapps/common/Tiny Glade/tiny_glade.pdb` | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |

GUID `d8d61d04-9e31-5b47-4c4c-44205044422e`、age1，首选image base `0x140000000`。native用RVA，shader用原文件偏移；PE按各section实际边界换算，不能混用对象字段偏移、RVA与文件偏移。

沿用REA MCP未连接、CLI缺少编译运行文件的既有阻塞；没有重复setup、安装引擎或构建REA。系统DbgHelp查匹配PDB，已有Capstone 5.0.3离线解码原EXE字节；SPIR-V按已保存grammar有界解析。记录属于普通本机静态证据，没有REA Evidence ID、提供者会话或原始源码恢复。

函数名用于定位，结论另核实际读取、分支、常数、调用和写入。工具扫描call候选后，必须以包含函数指令边界确认；共享地址的helper名字不能独立确定类型。已解析字节/模块不代表全部语义、可达性和运行行为。

## 原问题覆盖与阅读路线

| 问题 | 已确认 | 仍部分或未知 |
| --- | --- | --- |
| [31 地形笔刷与高度场](31-tiny-glade-terrain-strokes-and-heightfield.md) | 实际UI入口、末段改形/追加、p/H编辑、点/half记录、距离场、坡面核心、max合成、平滑与UNorm16接口 | 全UI模式/初始H覆盖、完整噪声库、零长度段防护、所有水/背景与附属mask分支 |
| [32 建筑地面采样与高度](32-tiny-glade-building-ground-sampling-and-heights.md) | 公共墙边界取样与地形差值、另列形状高度统计、指数状态平滑、石基offset与transition | 各字段完整编辑语义、完整底面扫描/自由形状、形状入口完整caller、所有上限分支 |
| [33 石基表面与窗洞](33-tiny-glade-foundation-surfaces-and-cutouts.md) | 木墙资格、上下边界/道路开口例外、两排顶点、32quad分块、实例/VS地址、纹理窗洞、旧产物所有权 | 全面类型、索引资产、完整材质接缝及延迟GPU释放消费者 |
| [34 地形读回与局部更新](34-tiny-glade-terrain-readback-and-local-updates.md) | 计数/type ID、调用次数延迟、两个同键buffer、8×8样点判差、dirty发布并集、两类墙筛选、事件顺序 | 底层GPU同步/映射刷新、完整scheduler、空间bucket维护和全部编辑操作覆盖 |

四篇均包含前置状态、输入、步骤和结果的构造例。核心局部算法有实际指令证据，但没有宣称整款游戏或每次地形操作的完整行为已经还原。

## 关键入口与实际作用

| 入口 | RVA | 选定范围/作用 |
| --- | --- | --- |
| `ui_draw_terrain` | C10580 | 2992B；实际画笔入口 |
| `TerrainEditingData.new_stroke` | B14280 | 245B；ID、首点、p/H初值 |
| `insert_or_morph_last_point` | A00140 | 370B；按已有末段改形或追加 |
| `edit_terrain_stroke` | A08D10 | 4638B；Set与增量分支及直接重算 |
| `terrain_stroke_changed` | BFBDA0 | 254B；UI改点事件汇聚 |
| `rasterize_terrain_stroke` | 9B16B0 | 8410B；GPU点/记录与实际绑定 |
| `TerrainHeightsData.sample_at_world_xz` | 19C1AC0 | 974B；u16端点解释和双线性采样 |
| 公共墙重采样实例 | 19AC6D0 | 1507B；参考曲线地面与下限 |
| 公共墙差值数组producer | 15EB960 | 303B；pointY−terrainHeight |
| `calc_shape_height_and_stone_foundation` | 92CF10 | 1502B；另一路形状统计与高度状态 |
| `time_continuous_lerp` | DE93B0 | 81B；指数混合 |
| `stone_foundation_y` | 92F940 | 197B；nominal高 |
| `clamp_stone_foundation_offset` | 92FCF0 | 272B；offset上限 |
| `stone_foundation_transition_y` | 92FF30 | 465B；transition高 |
| `maintain_stone_foundation_surfaces` | 840220 | 18274B；按墙清旧/重建表面 |
| `append_stone_foundation_surface_face` | 844990 | 2640B；两排顶点与quad分块 |
| `nani_update_stone_foundation_surface` | 2581D20 | 2720B；64B实例输出 |
| `despawn_stone_foundation_surface` | 83FF50 | 719B；墙→旧实体列表移除 |
| `StoneFoundationSurfaceBufferOwner.drop` | 13FD930 | 756B；tag3延迟回收 |
| `raster_visual_terrain_and_read_terrain_data` | 9AEDE0 | 3803B；两buf与读回管线 |
| `delayed_terrain_changed_msg` | A69900 | 663B；调用次数队列/读回事件 |
| 高度 `copy_from_gpu` | 19C0D50 | 按位比较、dirty与端点 |
| `Publisher.publish<DirtyTiles>` | 9C5460 | epoch/pending并集 |
| 地形dirty墙closure | A83260 | bucket路由与两类候选 |
| `publish_public_wall_state` | B9F450 | 复用前轮range，重读高度筛选/producer/事件子范围 |

表是定位入口，不等于全部语义覆盖；完整range、子范围与常数摘要见本机记录。

## 跨阶段身份和校正

同一笔画以StrokeID关联GPU高度竞争，不保留每个像素的独立地形物体；winner ID与高度同步替换，平分不保证按ID排序。坡度p、H、normalized height、encoded texture R、u16和CPU世界高度分别保持语义，不能把 `.05H` 当世界高度。

公共墙producer `19AC6D0` 与形状高度入口 `92CF10` 是两条不同上下文；没有看到B9F450直接call后者，不能因名称相近拼成每次地形更新统一路径。石基nominal/transition/表面top与道路初始lift也不混用。

消息分为UI改点汇聚和参数/点数组编辑直接重算。读回顺序核到 **Terrain CPU更新→写OnTerrainChange→Visual CPU更新**，事件写入不等于消费者即时执行。原子计数、bool、倒计时、dirty图、epoch、WallID与图buffer状态各有独立归属。

本轮补齐TerrainHeightsData的dirty直接发布与未消费区域OR合并；前轮道路WorldRaster的flush仍未找到，不能因共用DirtyTiles类型而替它补链。石基旧实体排队删除与GPU buffer延迟释放同样不是一个即时动作。

## 本机原始记录

根目录：`C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/`。

| 路径 | 内容 |
| --- | --- |
| `tinyglade-terrain-input/` | UI、编辑、GPU记录/绑定、六shader/十模块格式记录和公式 |
| `tinyglade-terrain-base/` | 世界采样、两类墙高度producer、石基标量、12段细范围与12组常数 |
| `tinyglade-terrain-foundation/` | 石基CPU几何、所有权、实例与一shader/四模块；选定VS/FS解释 |
| `tinyglade-terrain-updates/` | 读回/发布/墙筛选，45段细范围与6组身份/端点常数 |
| `terrain-validation.json` | 根agent对摘要、重新线性解码、子范围、常数、链接和构造算例的独立复核 |

记录可在本机复查，跨机器需要另行迁移。正文保留公式、位置和限制，不用不可访问的本机文件替代解释。独立产品应按自己的需求定义参数、资源和退化策略；研究不提供原游戏资产或恢复代码作为生产实现。

## 独立复核结果

`terrain-validation.json` **440项通过，0项失败**：

| 范围组 | 记录数 | 记录字节合计 |
| --- | ---: | ---: |
| 笔刷与高度场 | 11 | 21,564 |
| 建筑采样与石基标量 | 20 | 18,548 |
| 石基表面与所有权 | 11 | 27,392 |
| 地形读回与更新 | 14 | 16,228 |

56个记录包含共享top helper；按RVA去重为 **54个native范围、83,243字节**。复核每段原EXE摘要、保存listing和记录长度，并用Capstone重新线性解码；重复RVA长度/摘要一致。线性解码通过不证明全部指令可达或全部函数语义已解释。

重新核对EXE/PDB完整摘要、**7个shader文件与14个内嵌模块**摘要和词数范围；底部/石基12段与读回/更新45段合计57段细范围均核文件偏移、SHA与重新线性解码长度；18组常数/身份原字节及section偏移匹配。floor/拾取/cache等所选模块的格式覆盖不自动提升为完整行为确认。

独立构造演算复核：末段改形、Set/增量区别、count/ID/half、像素中心、坡面/核心max、双轴模糊、世界编码与量化误差、CPU双线性高度、参考曲线/地形差值、目标采样取整、形状高度/指数混合、石基上下界、面带分块/地址、显示位移/窗洞、延迟队列、dirty tile与范围变化、publication并集和墙高度二次筛选。没有执行原函数，不能建立运行等价性。

正式目录 **37份Markdown、178个相对链接**，UTF-8、围栏、相对链接目标及31–34构造例存在检查通过。前轮覆盖数字保留历史范围，不与本轮相加宣称整款游戏恢复。

## 未做与风险

未做：没有运行、附加或修改游戏，没有私人存档、GPU捕获、性能测试或原函数执行；没有REA项目构建/测试，因为本轮只新增研究文档和可再生成的本机验证产物。

风险：half与u16量化、采样分辨率、空间噪声和分支缺口限制逐位复现；完整GPU同步未恢复，调用次数延迟不能当两帧保证；地块标dirty还有墙级筛选。各局部公式不支持对所有材料、地形操作和最终画面作统一结论。
