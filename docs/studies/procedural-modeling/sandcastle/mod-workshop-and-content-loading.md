# Sandcastle Demo：Workshop、Mod 与内容加载边界

截至 **2026-10-21** 的结论是：本机 Demo 已编入游戏自有的 Steam Workshop 创建、更新、查询与下载方法；公开商店和开发者公告却没有把 Workshop 或 Mod 作为 Demo 已开放功能来说明。方法名、Steamworks.NET 和 Steam DLL 不能替代玩家入口、Steam 后台配置、成功上传下载及内容实际加载的证据。现有字段更像沙堡作品／地图的分享候选，**不能据此认定可装载脚本、工具、模型或任意 Mod**。运行验证为 **Runtime Not Run**。

## 身份与公开发布状态

| 证据                                                                                                            | 可确认事项                                                                                   | 边界                                                        |
| --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 本机 `C:\Software\Steam\steamapps\appmanifest_4894830.acf`                                                      | `appid=4894830`、`name=Sandcastle Demo`、`installdir=Sandcastle Demo`、`buildid=24888454`    | manifest 是本机安装快照，不代表 Steam 线上当前 build。      |
| 本机 `Sandcastle_Data/app.info` 与[既有制品身份记录](01-artifact-and-method-map.md)                             | `BubblebirdStudio` / `Sandcastle`；Unity 6000.4.10f1、IL2CPP `Assembly-CSharp.dll`           | 确定调查对象，避免混入同名游戏。                            |
| [Demo 商店页](https://store.steampowered.com/app/4894830/Sandcastle_Demo/)                                      | 开发者 Bubblebird Studio、发行商 Future Friends Games；特性列为单人和 Demo，并预告完整版内容 | 页面未列 Workshop、创意工坊或 DLC，不等于证明未来不会加入。 |
| [完整版商店页](https://store.steampowered.com/app/3216520/Sandcastle/)                                          | 同一开发者的另一个 app `3216520`，截至观察时尚未发售；列沙型、布局等海滩自定义               | 自定义选项是游戏内功能陈述，不是外部内容导入承诺。          |
| [2026-07-28 Demo 预告](https://steamcommunity.com/games/3216520/announcements/detail/669497686129377951)        | 介绍 Demo 两款海滩：Base 和 Barrier。                                                        | 海滩选择不是外部地图导入。                                  |
| [2026-08-24 Demo 0.31.0 补丁](https://steamcommunity.com/games/3216520/announcements/detail/689766422328378962) | 写有“跨版本兼容系统”。                                                                       | 没有明确兼容哪些文件或是否涉及 Workshop。                   |
| [2026-10-19 Next Fest 公告](https://steamcommunity.com/games/3216520/announcements/detail/671757096278034084)   | 邀请玩家分享作品。                                                                           | 没有写明经 Workshop 分享或支持 Mod。                        |

本机的 `4894830` 与尚未发售的 `3216520` 要分开；名称相似的其他 Sandcastle 产品及其 Workshop 页面均不适用于这批文件。公开状态只按上述**精确 app** 的商店页和官方公告陈述。Steam 社区页与商店页未显示 Workshop 标签；直接 Workshop URL 在本次网页读取器中不可访问，因此 Workshop 后台配置、公开物品数量与账户权限仍为 **Unknown**，不能把 URL 错误写成“不存在”。

## 静态能力与加载边界

本次复用[既有 metadata/PE 映射](01-artifact-and-method-map.md)，从 `Sandcastle_Data/il2cpp_data/Metadata/global-metadata.dat` 的 `Assembly-CSharp.dll` 类型表选取 `Steam`，并与 `GameAssembly.dll` 的同一 `Il2CppCodeGenModule` 指针表对齐。当前文件 SHA-256 分别为 `AA4457307746C4552541B6CEDD4809FDACCF33EEF03964A9E2300DE5A09E1606` 与 `147030ECF9527A25250238120364EB761390B99688B1812C4EA555B3B04E56A0`，与既有记录相同。精简查询记录在本机忽略目录 `.cache/procedural-modeling/mod-workshop-dlc/sandcastle/workshop-metadata-and-map.json`；这不是 REA Ghidra 函数 Evidence，也不是运行调用记录。

| 本作类型／入口                                                              | 静态观察                                                                                                                                                                                                                                                                               | 能推到哪里                                                                                                      |
| --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `Steam`                                                                     | 有 `CreateWorkshopItem` (`0x060004C7` → `0x180498600`)、`UpdateWorkshopItem` (`0x060004C9` → `0x1804996F0`)、`GetWorkshopItems` (`0x060004CB` → `0x180498920`)、`DownloadWorkshopItem` (`0x060004CF` → `0x180498700`)；还有相应回调、安装事件、状态查询、下载路径及 `mapsFound` 字段。 | 方法对应本作 IL2CPP 代码地址，是项目级候选链；本次未追调用者、异步完成分支或 Steam API 返回，不能标成实际可用。 |
| `WorkshopItemState`                                                         | `NotTracked`、`Installed`、`Outdated`、`Pending` 四个状态名。                                                                                                                                                                                                                          | 只证明编入状态表示；不能证明状态在 Demo 中可到达。                                                              |
| `Steam.UpdateWorkshopItem` 参数                                             | `Header header, string contentDir`。`Header` 含版本、标题、作者、创建／保存时间与文件路径。                                                                                                                                                                                            | 存档元数据加内容目录是“作品分享”线索；目录内文件格式、校验和加载器仍未知。                                      |
| `Game.Save`、`Game.Load`、`Saves`                                           | 游戏自有保存／读取入口与本地存档列表。                                                                                                                                                                                                                                                 | 存档能力和 Workshop 订阅是不同契约；尚未闭合“订阅项 → 经验证的地图读取 → 场景实例”路径。                        |
| `ScriptingAssemblies.json`、`Plugins/Steamworks.NET.txt`、`steam_api64.dll` | 包含 Steamworks.NET 2025.163.0 与 Steam API DLL。                                                                                                                                                                                                                                      | SDK 与 DLL 本身不证明任一具体 Steam 功能已启用，也不表示支持通用 Mod。                                          |

因此，把能力分成三层最准确：**编入的项目级 Workshop 方法：Observed；实际发布／下载并采用玩家作品：Unknown；官方通用 Mod／外部资源加载契约：未找到公开声明，Unknown**。本次没有分析 `GameAssembly.dll` 中这些方法的完整控制流，没有检查外部目录注入，也没有读取玩家作品或私有存档。引擎自带 AssetBundle／ContentLoad 模块同样不能推出本作允许第三方内容加载。

## 对综合 Demo 的独立建议

若目标只是让玩家分享沙堡，先定义自研的**作品文件**：版本、地图尺寸、沙／水状态、摆件的自有 ID、作者可选展示信息；导入时验证尺寸、ID、资源预算和版本，再交给既有保存／重建路径。可把本地导入和 Steam Workshop 传输分层：Workshop 只取得一个候选文件，统一验证器决定它能否成为可加载作品。构造例：订阅项提供一个超出当前地图尺寸的作品时，下载成功仍应被内容验证器拒绝，并显示明确错误；不应把“Steam 下载完成”当成“游戏世界可安全加载”。这是**自研规格示例**，不是本作已观察到的行为。

如未来要开放 Mod，需另定允许扩展的类型、schema／版本、资源权限、加载顺序、冲突和失败隔离；不能直接把作品存档接口升级成任意代码或资源加载。对当前小型综合 Demo，作品导入／导出比通用 Mod 更贴近已知的玩家创作流程，也更容易按自研需要验证。

## 未决与验证状态

- **Answered**：本机 Demo／完整版 app 身份、公开商店特性、已编译的 Workshop 候选方法及其与作品字段的关系。
- **Partially answered**：方法是否用于实际作品分享；还缺调用者、UI、内容目录格式及读入链的有界证据。
- **Unknown**：Steam 后台 Workshop 配置与公开物品、上传／订阅权限、完整版最终功能、DLC 计划、通用 Mod API、外部代码／资源装载策略。
- **Runtime Not Run**：未启动／附加游戏，未登录 Steam，未上传、订阅、下载或导入作品；静态方法存在不证明可达或成功。未修改安装目录。

跨游戏结论见[对照表](../122-mod-workshop-dlc-comparison.md)，自研平台边界见[综合 Demo 设计](../123-steam-workshop-and-dlc-design-for-demo.md)。
