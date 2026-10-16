# Sandcastle Demo：沙、水与地表生成的静态研究

最新续查见[23：湿沙到薄水过渡](23-wet-sand-and-thin-water-transitions.md)：湿色0.001…0.020、水有效量基线0.05、片元裁剪与透明度接通；取样空间和实际全局参数保留边界，运行未做。

最新续查见[22：native读回请求等待与取消边界](22-native-readback-wait-cancel-boundary.md)：平行接口表接到请求节点、回调句柄和状态1等待门，Clear接到buffer回收；间接释放是否等待／取消仍未知，运行未做。

最新续查见[21：读回请求生命周期与碰撞消费](21-readback-request-lifecycle-and-consumers.md)：Load清理／重建及同步刷新接通，异步委托持有同一Readback接收者；同尺寸旧回调写新数组为条件风险。native等待／取消和实际消费版本仍未知，运行未做。

最新续查见[20：读回快照到碰撞时效](20-readback-snapshot-and-collision-age.md)：接通Update／FixedUpdate两条链，核对回调接受门和版本空缺；按轮换消费给出条件时差公式。0.2秒不是碰撞延迟上界，运行未做。

最新续查见[19：引用映射接口实际目标](19-reference-interface-targets-and-tail.md)：非空context接口接到有序int32引用重映射，但动态接收者是否为class129仍缺一边；接口不读资源流，末尾3的构建来源仍未知。运行未做。

最新续查见[18：+0x88引用传递与尾字节边界](18-transfer88-and-tail-production.md)：六个顶层调用接到资源引用成员／数组及条件回填，末段没有可见额外tail写。接口目标和构建生产者仍未知，运行未做。

最新续查见[17：尾值3的构建端证据边界](17-tail-build-writer-and-profile.md)：七份选定资源没有另一个class129或类型树，本机两个相关虚槽为空；尚未定位构建writer/profile到末尾3的生产链。运行未做。

最新续查见[16：class129 读取分支与尾值来源边界](16-class129-reader-branch-and-tail-origin.md)：无 type tree 的实际类型记录接到直接 reader；从对象首字节读取，912/916 差额进入不等长诊断。末尾 3 的构建 writer/成员与诊断实际后果仍未知，运行未做。

最新续查见[15：三值生产与外层长度门](15-tail-production-and-serialized-loader.md)：通用直接reader分支返回后核对消费量，并接通对象终点到上下文界限。class129实际分支和尾部3的构建生产者仍未知，运行未做。

最新续查见[14：尾部三值的处理边界](14-player-settings-tail-owner-and-loader.md)：class129注册、factory和构造写入接到真正虚表起点与reader槽。三值的构建生产者、外层loader调用和长度处理仍未闭合，运行验证未做。

本研究针对本机 `Sandcastle Demo` 的指定版本，回答地表怎样生成、铲子如何改动沙和水、每帧模拟怎样调度，以及这些状态怎样变成可见模型。它是对发行文件的静态行为研究，不是原工程源码；开发者公开说法与本地可执行文件证据分别标记。没有启动游戏，因此实际手感、性能、不同海滩的默认参数仍需另行验证。

阅读顺序：

1. [制品身份和方法映射](01-artifact-and-method-map.md)：版本、metadata 到 native 地址的证据链及可复查工具。
2. [CPU 模拟调度](02-cpu-simulation-orchestration.md)：游戏帧到沙、水和读回层的调用关系。
3. [挖掘、堆积与 CPU 网格](03-excavation-and-mesh.md)：刷子操作、铲子分支、规则网格和碰撞更新。
4. [GPU 沙水模拟与画刷](04-gpu-simulation-and-brush.md)：计算着色器里的具体数值更新，由同一研究的 GPU 分析记录。
5. [地表模型与水面渲染](05-surface-mesh-and-water-rendering.md)：顶点和像素着色器怎样将高度状态绘成画面，由 GPU 分析记录。
6. [湿沙材质、水体折射与光照](06-surface-materials-and-effects.md)：水量颜色门槛、流动纹理、深度回退、距离衰减与视角高光的实际公式。
7. [局部更新、读回与成本](07-local-updates-readback-and-costs.md)：模拟、画刷、读回与碰撞分别处理多大的范围，条件和未知参数如何影响开销。
8. [材质绑定、渲染状态与变化传播](08-material-bindings-render-state-and-invalidation.md)：实际场景组件、材质和贴图的引用，沙水 pass 状态，以及 CPU 全局参数生产者。
9. [相机颜色与深度纹理来源](09-camera-color-depth-resource-provenance.md)：从真实 property ID 字面量，追到颜色/深度附件、两种复制、全局纹理设置与释放。
10. [相机颜色格式选择](10-camera-color-format-selection.md)：HDR 类别查询、唯一核到的字段赋值，以及颜色附件/副本的 sRGB/Linear 转换。
11. [项目色彩空间配置](11-color-space-configuration.md)：精确版本 Release 布局读出的 Linear 字段、未映射尾部，以及配置与实际生效值的区别。
12. [PlayerSettings 尾字段](12-player-settings-tail-field.md)：末尾四字节的对象归属、类型树/对齐反证与仍未消歧的两种字段映射。
13. [尾槽的实际二进制读取对应](13-player-settings-exact-tail-mapping.md)：回调表接到本地reader，零槽映射allowedHttpConnections，三值仍是未消费尾载荷。

一手开发者访谈称，游戏在 Unity 中自研沙水模拟，将沙作为高黏性、强阻尼的流体处理，沙水采用不同分辨率，并考虑侵蚀与沉积；还称各海滩共用算法但地形和参数有差异。这些是**开发者陈述**，不是我们对每个本地公式的证明。来源：[80 Level 对 Sandcastle 开发者的访谈](https://80.lv/articles/creating-cozy-sandbox-sandcastle-with-a-focus-on-water-sand-simulation)。

**结论边界**：本地资源与 CPU/GPU 调用链共同支持“规则平面网格 + 网格单元的沙水状态 + GPU 高度位移”的模型；不能据此断言所有装饰、粒子或建筑模型也由同一网格生成。实际网格分辨率和各海滩序列化参数尚未在 CPU 调用链中确定。
