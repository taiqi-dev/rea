# Tiny Glade：官方 Mod、Workshop 与静态内容加载入口

调查日期：2026-10-21（Pacific Time）。本篇只调查 `C:/Software/Steam/steamapps/common/Tiny Glade` 的发行文件和公开官方资料；没有启动、附加或修改游戏，没有读取个人 Mod、存档或 Steam 订阅目录。目标为 Windows x64 PE `tiny-glade.exe`（65,612,184 B）及相邻 PDB `tiny_glade.pdb`（310,513,664 B），两文件修改时间均为 2026-10-08 07:21:34 本机显示值。`build-info/toolchain-info.json` 记录 `x86_64-pc-windows-msvc`、Rust 1.95.0、`DEBUG=true`，但本机 EXE 的 FileVersion/ProductVersion 为空；不能仅凭时间和符号推定它等于哪个公告版本。没有为本次研究计算摘要。

## 公开支持范围与用户流程

2026-09-23 的[开发者更新](https://steamcommunity.com/games/2198150/announcements/detail/692021394394841188)宣布 Workshop；[官方 Workshop 首页](https://steamcommunity.com/app/2198150/workshop/)分 `Clutter` 和 `Asset Replacement`。开发者的[官方 Mod 指南](https://pouncelight.games/tiny-glade/info/modding/)说明：前者新增可摆放物件，安装后进入各 glade 的选择器、由玩家摆放；后者覆盖纹理、网格等资产，默认关闭，须在每个 glade 的 Mod 菜单单独勾选并应用。一个 Mod 可兼具两类。这是基础内容支持，不能据此推定脚本或任意玩法接口。

[该游戏 Workshop About 页](https://steamcommunity.com/workshop/about/?appid=2198150)标记 Ready-To-Use，称订阅条目在下次启动时可用；这不等于替换类已对当前 glade 生效。作者可在游戏的 Mod editor 创建并发布，首次发布为私有条目，随后在网页完善并公开；更新沿用该条目。具体制作、文件夹布局、导入与发布步骤见官方指南，本次未实际安装或发布。

## 身份、覆盖、存档与预算

发布创建的 `workshop.json` 保存 Steam file ID，连接本地作品与平台条目；游戏生成的 `mod-id.json` 是另一个 GUID，供 glade 引用。GLB 物件名也进入存档。作者本地文件优先于自己订阅的副本；多个 Mod 覆盖同一纹理时，**后勾选者胜**，不外推到其他资源冲突。资源替换按相对路径查找，目录合并；JSON mesh 和纹理可热重载。官方还允许本地文件夹或 zip。详见上述官方指南。

官方单个 GLB 上限为 150,000 三角形、200,000 顶点、128 MiB，纹理最长边 4096；没有自动 LoD。这些不是整个 Mod 或 GPU 内存总预算。缺失 Mod 时的占位、警告、卸订后存档策略，以及运行时内存峰值仍 Unknown。

## 本机静态连接，及其边界

使用仓库现有只读 DbgHelp `pdb_probe.py` 对 `*tg_mods*`、`*workshop*`、`*mod_id*` 分别完整枚举 276、454、4 个符号，原始输出为 `.cache/procedural-modeling/mod-workshop-dlc/tiny-glade/pdb-mod-workshop-symbols.json`。其候选函数地址包括：`tg_mods::discovery::discover_mods` `0x140D953E0`、`tg_mods::overlay::build_overlay` `0x140D8B880`、`set_active_mods` `0x140D8F0D0`、`resolve` `0x140D929F0`、`country_core::systems::steam::workshop_mods::register_subscribed_workshop_mods` `0x1409D6EB0`、`workshop_clutter_hot_install` `0x140BD8750`、`missing_mods::subscribe_to_workshop_items` `0x140A28760`。名称和边界来自 PDB；**仅凭符号不能证明执行顺序或行为结果**。

现有只读 PE 调用候选扫描和 PDB 地址归属保存在同一 `.cache` 目录的 `candidate-calls.json`、`candidate-call-owners.json`。又用本机 VS `dumpbin` 14.44.35222.0 对关键地址局部反汇编复核：`load_nani_meshes` 的 `0x140B1E8A4`、`load_glade_texture_mappings` 的 `0x140A9E8E0` 都直接调用 `tg_mods::overlay::resolve`；证据为 `resolve-mesh.txt`、`resolve-texture.txt`。`ModSwapReloads::apply` 的 `0x140AB3B53` 和 `preactivate_boot_replacement_mods` 的 `0x140AB57F5` 直接调用 `set_active_mods`；证据为 `swap-replacement.txt`、`boot-replacement.txt`。`tiny_glade::mod_detection::build` 的 `0x1402B3CB5` 调 `discover_mods`；证据为 `detect-mods.txt`。另有 `set_active_mods` 内 `0x140D8F492` 调 `build_overlay`，证据为 `overlay-build-set.txt`。这些调用分别确认**三个静态片段**：游戏 build 调发现、激活入口经 `set_active_mods` 构造 overlay、网格/纹理加载调用 overlay 解析。发现结果怎样接到各激活分支、下载/错误处理和热重载完成时序仍未闭合；不能把片段拼成已验证的完整启动流程。

既有[屋瓦 atlas 研究](../110-tiny-glade-roof-atlas-budget-and-graph-views.md)在同一制品上把发行 `assets/nani_meshes.ron` 的 `RoofTile` 配置接到 `load_nani_meshes` 与 atlas add；它提醒覆盖和重载可能改变 atlas 部件槽号。[建筑资产装配研究](../64-tiny-glade-building-kit-and-asset-assembly.md)说明同一 JSON 网格可按 RON 请求进入不同渲染子类。因此 overlay 替换资源后不能假设旧 atlas 编号、LOD 或可见结果保持不变；这是基于两份静态研究的推断，未做运行验证。

## DLC 的独立边界与可借鉴设计

[Steam 游戏商店页](https://store.steampowered.com/app/2198150/Tiny_Glade/)当前列出的游戏附加内容只有 _Tiny Glade Soundtrack_；[DLC 分类页](https://store.steampowered.com/dlc/2198150/Tiny_Glade/)也将其描述为完整原声音乐。它不是可摆放内容包，也不能把 Workshop 订阅项称作付费 DLC。商店显示状态会变化，以上仅为 2026-10-21 查阅时的公开页面。

对自研产品可借鉴的是**分开设计**：创作者物件加入显式选择器，现有资产替换按每个存档独立启用；存档保存稳定 Mod ID 与内容 ID，加载时显示缺失、冲突和版本差异，并允许不破坏原记录的恢复路径；覆盖解析有唯一的路径与顺序权威，冲突可诊断；导入预算同时限制单文件和整个场景/显存占用。发布绑定本地 ID 与平台条目 ID，更新沿用同一身份；Steam 订阅、文件就绪、游戏安装、单存档启用分别记录状态。此段是**独立设计建议**，不声称 Tiny Glade 已实现这些全部机制。平台通用设计和与其他产品的比较接[跨游戏比较](../122-mod-workshop-dlc-comparison.md)、[自研方案](../123-steam-workshop-and-dlc-design-for-demo.md)。

**已回答**：官方开放的两类内容、作者发布和玩家启用路径、官方明确的纹理冲突规则、GLB 单文件限制、Mod 与 soundtrack DLC 的区别，以及本机关键 overlay 直接调用。**部分回答**：存档引用身份、热重载和作者本地副本优先级。**Unknown**：本机可见制品的精确语义版本、Steam 订阅下载后的完整时序、缺失 Mod 的 UI/存档行为、所有资源类型的覆盖冲突规则、实际内存峰值与运行失败路径。目标运行、安装/订阅、上传、私人存档检查、Ghidra 重试均 **Not Run**。
