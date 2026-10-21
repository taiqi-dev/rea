# 掘地求财：官方 DLC、Workshop 与外部内容边界

截至 **2026-10-21**，本作 Steam 商店列有**一项官方 DLC**：`A Tale About Digging a Hole – The Official Story Novel`。它是 PDF 小说和独立动画翻页 EXE，不是挖掘关卡、体素内容包或 Mod 加载 API。商店功能列表与本作官方公告未宣称 Steam Workshop 或官方 Mod 支持。本机有 Unreal 和 Voxel 插件及 cooked 容器，但它们只说明发行包如何装载游戏自身内容。运行验证为 **Runtime Not Run**。

## 精确身份与发布物

| 证据                                                                                                        | 观察                                                                                                                                                   | 解释边界                                                             |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| 本机 `C:\Software\Steam\steamapps\appmanifest_3244220.acf`；[既有身份记录](00-evidence-and-reproduction.md) | `appid=3244220`、`name=A Game About Digging A Hole™`、`buildid=22130236`；Shipping EXE 为 PE32+ x64、145,180,160 字节，同目录 PDB 已核 GUID/age 匹配。 | 只适用于这批本地文件。                                               |
| [本体商店页](https://store.steampowered.com/app/3244220/A_Game_About_Digging_A_Hole/)                       | DoubleBee 开发；功能列单人、成就、Steam Cloud；“Content For This Game”显示一项小说 DLC。                                                               | Steam Cloud 是存档同步，不是 Workshop；页面未列 Workshop 功能。      |
| [官方小说 DLC 页面](https://store.steampowered.com/app/4210530/_/)                                          | DLC app `4210530`，2025-12-09 发行，要求本体；官方说明下载物为 PDF 和动画翻页 EXE，位于游戏 Steam 安装目录，并可从库中选择启动。                       | Steam 的“DLC”商品类别不意味着游戏中新增矿物、地图、工具或体素规则。  |
| [2026-09-29 续作公告](https://steamcommunity.com/games/3244220/announcements/detail/683014577767580230)     | 宣布 `A Game About Digging A Hole Together` 是另一个多人续作，开发者称其代码需要从头重建。                                                             | 续作有独立 Steam app `4018610`，不是本体 DLC 或当前版本的 Mod 平台。 |

本机安装根顶层未见 PDF 小说文件；这只描述当前被查看的目录，**不能推定账号未拥有 DLC**。Steam 商店“同捆包”可能合并别的游戏的功能标签，不能据此把别的产品的 Workshop 特性归给 `3244220`。

## 本机静态边界

从匹配 EXE/PDB 用本仓库 [`pdb_probe.py`](tools/pdb_probe.py) 以精确 `*SteamUGC*` 掩码查询：结果 0，`exhausted=true`、`limited=false`，记录于本机忽略目录 `.cache/procedural-modeling/mod-workshop-dlc/digging-a-hole/steamugc-symbols.json`。这只表示该 PDB 的此一名称模式无匹配；接口可内联、动态绑定或使用不同名称，**不能当成不存在 UGC 调用的证明**。

复用此前已完整解码的 [IoStore／PAK 路径索引](00-evidence-and-reproduction.md)：IoStore 1,338 个文件条目、PAK 4,475 个路径条目；对路径组件 `Mod`、`Mods`、`Workshop`、`DLC` 做有界筛选，均无匹配。本轮重算 Shipping EXE、`DiggingGame-Windows.utoc` 与 `.pak` 的 SHA-256，分别为 `8356C03AFFEAA4A08FC92E52FDAC6FEB3A69CBD7B90FE96D67C3DB9E83E6200A`、`3AC4ED2C5B5D827C31F86641CB1763F01D10C8C67591EC66D27035A3E89FEDD6` 和 `4221BCCA7B82012599319A3FA1DA35A8EF5B9D9D8B383B3E31A52B1A1D153624`，与既有索引身份记录相同。筛选回执在 `.cache/procedural-modeling/mod-workshop-dlc/digging-a-hole/package-path-check.json`。这能说明**当前已发行容器目录**未按这些名称组织额外包，不能证明引擎没有运行时挂载能力、其他命名方案或将来的内容包。安装清单中的 Unreal `Engine/Plugins/...` 和 Voxel 插件是引擎／发行依赖，不是作者交付的 Mod SDK 或外部创作入口。

此前的[保存与一致性研究](02-save-load-and-consistency.md)追到本作体素快照、物件与玩家状态，再到 slot 写入；这是一条**游戏自身存档链**。未发现公开作品格式、导入 UI、第三方资产命名空间或订阅项到体素世界的调用链。社区可能存在对发行文件的非官方修改或注入，但本次不研究、不运行，也不能把这类途径写成官方支持。

## 对综合 Demo 的独立建议

先把可扩展点放在自研的数据契约，而非依赖 Unreal 容器或 Steam DLL 是否存在：可分享的地形作品定义生成器种子、经过验证的编辑块、摆件 ID、格式版本及资源上限；加载前验证，失败时保留原世界。Steam Workshop 如后续接入，只做发现、下载和来源标识，内容仍走同一导入验证。构造例：一份作品声明体素块长度为 4,096，却实际只给 3,900 个值时，验证器拒绝该作品并报告长度错误；不会因为它来自订阅目录就直接交给网格与碰撞重建。这是**自研规格示例**，不是本作实测行为。

如果计划卖 DLC，应先明确商品是独立阅读载体、游戏内解锁，还是新关卡数据。小说 DLC 的 PDF／EXE 发布方式只可借鉴“Steam 商品与游戏运行内容可以分离”的产品边界；不能借它推断体素地图热加载流程。自研作品包不包含本作代码或资产。

## 未决与验证状态

- **Answered**：本机 app/build 身份、已发布官方 DLC 的商品类型与文件载体，以及公开页面未宣称 Workshop 的状态。
- **Partially answered**：当前包的外部内容能力；仅检查了指定符号掩码、已解码路径索引和既有存档链。
- **Unknown**：所有可能的运行时挂载分支、私有／未公开 Mod 契约、Steam 后台配置、未来 DLC 的游戏内数据格式。
- **Runtime Not Run**：未启动或附加游戏、未读取玩家存档、未安装 DLC、未测试注入或载入外部文件；未修改安装目录。

跨游戏结论见[对照表](../122-mod-workshop-dlc-comparison.md)，自研平台边界见[综合 Demo 设计](../123-steam-workshop-and-dlc-design-for-demo.md)。
