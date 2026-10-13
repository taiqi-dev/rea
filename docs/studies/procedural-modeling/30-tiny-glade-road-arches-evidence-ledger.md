# Tiny Glade 道路穿墙石拱证据账本

本轮范围：道路与墙的覆盖采样、洞口连续区段和多开口接续、石拱轮廓、拱砖实例与墙洞显示、道路变化后的局部重建。时间锚为 **2026-10-12 19:12:05 PDT，America/Los_Angeles**，来自时间工具 `2026-10-13 02:12:05 UTC`，仅记录取证时间，不推断游戏更新时间。

## 身份与方法

沿用相同本机制品：

| 制品 | 路径 | SHA-256 |
| --- | --- | --- |
| EXE | `E:/Steam/steamapps/common/Tiny Glade/tiny-glade.exe` | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| PDB | `E:/Steam/steamapps/common/Tiny Glade/tiny_glade.pdb` | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |

匹配GUID `d8d61d04-9e31-5b47-4c4c-44205044422e`、age1，首选image base `0x140000000`。native地址是RVA，shader地址是原文件偏移；PE文件偏移按所在section转换，不用一个减数跨section。

REA MCP未连接、本地CLI缺少编译运行文件的既有阻塞未变化。本轮复用系统DbgHelp查询匹配PDB、已有Capstone 5.0.3离线解码，以及包内SPIR-V格式解析，没有安装引擎、编译REA或改变工具配置。结果属于普通本机静态证据，没有REA Evidence ID、原生反编译会话或运行捕获。

PDB名称只提供候选位置；正文另核实际读取、分支、常数、直接调用和写入。完整线性解码不证明控制流可达或实际执行；同址泛型别名不建立唯一callee身份。早期公开原型只保留为历史研究，不用其砖长或GPU调度替代发行版。

## 原问题覆盖

| 问题 | 已确认 | 部分/未知 |
| --- | --- | --- |
| [洞口范围](26-tiny-glade-road-openings-and-merge.md) | 四u8栅格、512/130映射、中心与四对侧采样、平滑、.05边界、指数抬升 | 栅格类别字段、运行采样对齐字节、墙点距、抑制数组语义及重采样全分支 |
| [多个开口合并](26-tiny-glade-road-openings-and-merge.md) | 连续正值run、邻样本扩张、周期首尾合并、评分和均匀细分 | 未见通用内部interval union；标志位对应可见柱体的全部规则未恢复 |
| [拱形](27-tiny-glade-stone-arch-profiles.md) | 立方冠形、端部二次混合、H/B选择、节点高度式及类别≤1后续上限 | D/optional参数完整上游、端部裁边全分支、枚举名称及退化防护 |
| [拱砖和洞口显示](28-tiny-glade-arch-bricks-and-rendering.md) | .56目标步长、折线分砖、.1尾阈值、矩形实例轴、CPU/GPU字段、普通墙局部拱高与片元裁剪 | 原砖网格楔形细节、普通墙三拱高全部上游、支柱全链及所有LOD/RT/shadow |
| [局部重建](29-tiny-glade-road-arch-local-rebuild.md) | dirty写入、道路订阅、地块关联墙集合、有效状态过滤和消息、按墙缓存替换、旧实例清理、墙ID去重 | dirty累计mask发布flush、所有道路材质订阅、完整scheduler及GPU提交时序 |

每个模块都有来源和构造输入/步骤/结果。已确认核心局部规则，但没有宣称整个道路建模系统完整恢复，也没有把静态算例冒称为运行观察。

## 关键入口

| 入口 | RVA | 选定字节数/职责 |
| --- | --- | --- |
| `draw_path` | BFAFE0 | 2993；道路绘制分支入口 |
| `PathRastersResources.as_float_grid` | BFABF0 | 214；四份活动栅格view |
| 栅格双线性采样实例 | A7D8D0 | u8/255、512行步长与对齐分支 |
| `sample_wall_path_intersections` | 7FD360 | 10211；覆盖、侧采样、平滑及抬升 |
| `calc_path_wall_segmentation` | 801390 | 3177；连续run和周期接续 |
| `process_segment` | 7FFF70 | 3439；标记及精确内部坐标 |
| `score_split_candidate` | 800CE0 | 832；局部轮廓评分 |
| `add_splits_in_empty_range` | 801020 | 878；XZ长度均分 |
| `calculate_wall_path_segments_impl` | 13FB850 | 6701；104字节子段与精确端点 |
| `create_stone_arch_profile` | 811D10 | 4190；profile选择与改写 |
| `ArchFunction.remap_t` | 811820 | 248；立方/二次混合 |
| profile节点fold | 141FDE0 | 1130；高度式 |
| `ArchWalker.walk` 石拱实例 | 1402590 | 1880；三维折线分砖 |
| `construct_arches.closure3` | 14046E0 | 852；砖变换和编码输出 |
| `BrickTransform.encode` | 94C790 | 260；96字节CPU到64字节GPU |
| `WallConstructor.from_curve` 选定实例 | 1446690 | 14852；复用旧范围，重读普通墙参数输出 |
| 道路/地形订阅初始化wrapper | 1A2B230 | 601；两来源订阅与资源插入 |
| `publish_public_wall_state` 内部lazy路径 | B9F450 | dirty地块、关联墙、过滤与墙变化消息 |
| `calculate_path_wall_segmentation` | 802000 | 1001；按消息墙ID替换缓存 |
| `construct_arches` | 7F0120 | 23384；按墙去重、清旧及重建 |
| sparse writer clear | 13F7BD0 | 清byte标记、bitset位和旧索引列表 |
| 旧ArchSegments析构helper | 49D240 | 三类内部数组与104字节record容器释放 |

表列定位入口，不等于全部范围或完整语义覆盖。具体record保留长度、地址、常数、SHA-256与listing。

## 本机原始记录

根目录：`C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/`。

| 路径 | 内容 |
| --- | --- |
| `tinyglade-arches-openings/` | 覆盖/平滑、门槛、run/周期、评分、补分割与子段；26个选定范围及发现 |
| `tinyglade-arches-layout/` | profile、walker、砖轴、默认字段/编码、常数原字节和独立SIMD算例 |
| `tinyglade-arches-rebuild/` | 道路写入、subscriber、dirty地块关联墙、事件与按墙清理的范围和子范围记录 |
| `tinyglade-arches-display/` | 两个shader/五模块格式记录，普通墙producer复用范围及显示发现 |
| `arches-validation.json` | 根agent独立复核的摘要、范围、常数、链接和构造演算结果 |

这些是本机可选证据，跨机器需另行迁移。正文保留可读机制与位置；交付不包含原游戏资产，也不将恢复代码包装为独立生产实现。

## 校正及职责区分

本轮把首轮的符号线索提升为实际局部算法：发行版石拱使用 `.56` 而非公开原型 `.2` 的分砖参数；端部混合权重为 `clamp(2−Ledge,0,1)`；多个扩张候选接触并不自动执行内部并集。

道路覆盖、初始lift、profile改写高度、拱圈砖、普通墙三拱高、最终片元裁剪依次区分。拱圈closure输出朝向弦的矩形实例，默认三拱高−100与flags0；没有证据补成CPU石券楔角算法。shader字段名含sin但消费段是双线性Y插值；flag 0x20还会复用half参数，不能只凭字段名字解释全部分支。

局部重建是受影响墙的产物替换，未证明每砖几何差量或内容比较跳过。道路线程、事件与GPU上传的完整运行顺序仍未知。

## 独立复核结果

`arches-validation.json` 复核 **368项通过，0项失败**：

| 范围组 | 记录数 | 记录字节合计 |
| --- | ---: | ---: |
| 洞口与分段 | 26 | 32,060 |
| 轮廓与铺砖 | 16 | 33,711 |
| 道路变化与重建 | 23 | 45,559 |
| 普通墙显示producer复用 | 1 | 14,852 |

66个范围记录存在共享函数；按RVA去重后为 **63个native范围、124,497字节**。重复范围的长度和摘要一致；逐范围重新读原EXE核SHA-256、完整线性解码记录长度及listing存在。选定的大函数仅对正文涉及的分支作语义结论，字节覆盖不能当完整算法覆盖。

同时重新核对EXE/PDB完整摘要、两个shader原文件及五个内嵌SPIR-V模块的摘要与词数长度；轮廓/砖轴七组常数的原始字节与section文件偏移；重建专题35段子范围的长度、文件偏移、摘要和已记录指令边界。两个shader的全部模块被格式解析，正文仅解释所选消费/裁剪，不把其余模块自动视为已恢复。

独立构造检查覆盖：两侧归一化、栅格夹紧、沿墙平滑、指数抬升、门槛插值、连续run与周期索引、评分、均匀补点、立方/二次混合与五节点高度、float32分砖取整、尾段严格门槛、砖轴、GPU双线性Y位移与拱高插值、两个pass的严格裁剪边界、墙ID去重、旧slot失效、dirty地块关联墙及当前/旧footprint并集。没有调用发行版函数。

正式目录 **32份Markdown、152个相对链接**，UTF-8、围栏和相对链接目标检查通过，26–29每篇包含构造算例。前轮覆盖数字保留历史范围，不与本轮相加宣称全游戏覆盖。

## 未做与风险

未做：没有启动、附加、修改游戏或读取私人存档；没有运行原函数、性能测试或GPU帧捕获；没有执行REA仓库项目测试，因为本轮只新增研究文档和可再生成本机验证产物，没有修改生产代码。

风险：符号、分支和局部公式不能证明全部用户操作覆盖；同一实例布局可被flags复用；静态构造演算不能建立发行版运行等价性。实际补齐需要分别追dirty发布、参数生产、特定网格与运行调度，不用常见拱门算法填空。
