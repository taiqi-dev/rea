# SUMMERHOUSE：格点小屋拼装与视觉处理

本轮调查的是本机发行版 `SUMMERHOUSE` 1.2.12 的静态托管代码，聚焦与 Tiny Glade 可比较的建筑、邻接、层次、装饰和变体机制。先看[证据与边界](00-evidence-and-scope.md)，再按问题读：

1. [放置、格点与前后层次](01-placement-grid-and-depth.md)：一件建筑块从预览到落地如何定位、翻转和决定深度。
2. [构件抽取、邻接组合与解锁](02-picker-combinations.md)：候选如何选择，怎样用相对格点识别组合并替换构件。
3. [保存、重建与美术变体](03-save-palette-and-visuals.md)：保存何种结构，材质换色与全局调色如何作用。
4. [发行资源中的方块与组合](04-packaged-blocks-and-combinations.md)：真实预制件 ID、相对格点配方和网格引用如何与代码接合。

**已验证的主要区别：**这份程序集以 `BuildingBlock` 预制件为构造单位，使用格点吸附、Z 深度候选和相对位置组合规则。组合成功可以解锁新块，也可用另一块替换已放置块。调查中没有发现足以证明它像 Tiny Glade 那样从连续建筑轮廓生成墙、屋顶和接缝的代码路径；这个否定仅限于当前读取的 `Assembly-CSharp.dll` 与选定模块，不涵盖包内全部资源或其它代码。Tiny Glade 的相应证据见[建筑资产与拼装](../64-tiny-glade-building-kit-and-asset-assembly.md)。

研究用于独立理解机制。代码报告中的构造算例与第 4 篇的真实发行配置已分别标明；给真实配置填入的世界格点仍是演算，不是游戏实测。没有启动游戏、读取玩家存档，或复制其资产到自研工程。
