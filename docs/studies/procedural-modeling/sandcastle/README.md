# Sandcastle Demo：沙、水与地表生成的静态研究

本研究针对本机 `Sandcastle Demo` 的指定版本，回答地表怎样生成、铲子如何改动沙和水、每帧模拟怎样调度，以及这些状态怎样变成可见模型。它是对发行文件的静态行为研究，不是原工程源码；开发者公开说法与本地可执行文件证据分别标记。没有启动游戏，因此实际手感、性能、不同海滩的默认参数仍需另行验证。

阅读顺序：

1. [制品身份和方法映射](01-artifact-and-method-map.md)：版本、metadata 到 native 地址的证据链及可复查工具。
2. [CPU 模拟调度](02-cpu-simulation-orchestration.md)：游戏帧到沙、水和读回层的调用关系。
3. [挖掘、堆积与 CPU 网格](03-excavation-and-mesh.md)：刷子操作、铲子分支、规则网格和碰撞更新。
4. [GPU 沙水模拟与画刷](04-gpu-simulation-and-brush.md)：计算着色器里的具体数值更新，由同一研究的 GPU 分析记录。
5. [地表模型与水面渲染](05-surface-mesh-and-water-rendering.md)：顶点和像素着色器怎样将高度状态绘成画面，由 GPU 分析记录。

一手开发者访谈称，游戏在 Unity 中自研沙水模拟，将沙作为高黏性、强阻尼的流体处理，沙水采用不同分辨率，并考虑侵蚀与沉积；还称各海滩共用算法但地形和参数有差异。这些是**开发者陈述**，不是我们对每个本地公式的证明。来源：[80 Level 对 Sandcastle 开发者的访谈](https://80.lv/articles/creating-cozy-sandbox-sandcastle-with-a-focus-on-water-sand-simulation)。

**结论边界**：本地资源与 CPU/GPU 调用链共同支持“规则平面网格 + 网格单元的沙水状态 + GPU 高度位移”的模型；不能据此断言所有装饰、粒子或建筑模型也由同一网格生成。实际网格分辨率和各海滩序列化参数尚未在 CPU 调用链中确定。
