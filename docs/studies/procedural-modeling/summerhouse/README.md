# SUMMERHOUSE：格点小屋拼装与视觉处理

扩展内容专题：[Mod、Workshop、DLC 与加载边界](mod-workshop-and-content-loading.md)。当前官方页未列 Workshop/DLC；本地布局存档、缩略图与外部素材导入分开核对，运行未做。跨游戏对照及 demo 方案见[122](../122-mod-workshop-dlc-comparison.md)、[123](../123-steam-workshop-and-dlc-design-for-demo.md)。

性能续查：[26：稳态相机与配色回调](26-steady-camera-and-color-callbacks.md)，新增REA CIL证据，区分零位移仍做的相机工作、缩放早退与有限配色协程；未运行或测帧时。

最新续查：[25：反射纹理生命周期与绑定](25-reflection-texture-lifecycle-and-binding.md)，补源相机缓存、scale失效门、WaterObject属性块及禁用释放；真实Shader采样与画面仍Unknown。

最新续查见[24：其它投影与 viewport 写端](24-other-projection-and-viewport-writers.md)：四关的活动水体反射组件连接到独立反射相机，写镜像 view 与斜裁剪投影；另核阴影/后期 viewport 与 PixelPerfectCamera 的有限注册边界。主相机最终 native/GPU 状态仍未知，运行未做。

最新续查见[23：最终投影与像素对齐](23-final-projection-and-pixel-alignment.md)：V/P/J生产、所见Execute路径和native矩阵提交接通，主体两个前向vertex直接消费unity_MatrixVP；fixed RT与scaled viewport分开。native最终状态及全局像素锁仍未知，运行未做。

最新续查见[22：像素网格与相机轮廓稳定](22-pixel-grid-camera-motion-and-silhouette-stability.md)：实际四节点缩放曲线接到整数高度／偶数目标；相机移动连续写位置，当前层级未见像素对齐组件。像素尺度不等于轮廓锁定，运行未做。

最新续查见[21：列表写端与重复订阅可达性](21-listener-writers-and-repeat-subscription-reachability.md)：主程序集只有四个列表直接用户；14件粒子与祖先组件、debug／enabled／切scene支路已核，未找到同实例真实重复启用入口。旧条目残留与重复Add分开说明，运行未做。

最新续查见[20：分类曲线与粒子监听生命周期](20-blend-curves-and-particle-listener-lifecycle.md)：四环境共用实际曲线，五scene解析14件监听组件；玻璃用例外曲线，反向切换用1-f(1-t)。退订非空直接ret已复核，实际生命周期／重复回调仍未运行验证。

最新续查见[19：三套调色板与共享状态传播](19-palette-propagation-and-shared-state.md)：完整解析Lake配色与manager，接到材质、环境、天空、Volume及粒子；普通过渡跳过地形直接应用，并列出有条件的写入／分配次数。运行未做。

最新续查见[18：管线纹理需求的配置来源](18-pipeline-texture-demand-and-settings.md)：原生Graphics/QualitySettings均指向选定URP，资产前缀的深度／不透明颜色纹理开关均开启，接到相机继承getter。最终附件／复制与成本仍未验证。

最新续查见[17：TAA目标生命周期与关闭成本](17-taa-target-lifetime-and-disabled-cost.md)：CPU状态对象、Init、目标分配与释放分别接通；普通入口在AA=None条件下走释放／清空分支。实际相机准入、帧次和性能仍未验证。

最新续查见[16：完整追加配置与效果门](16-additional-camera-layout-and-effect-gates.md)：补完两对象原余124 B；主后处理开启、遮罩关闭，两者AA=None。接通初始化和版本迁移条件，实际pass／重绘频率及性能仍未验证。

最新续查见[15：遮罩相机排序与准入](15-mask-camera-order-and-render-admission.md)：实际父子层级、Base 类型和 depth 接到 URP 比较器；两台同时进入列表时遮罩先绘制。原生列表准入、截图调度及重绘频率仍未知，运行未做。

最新续查见[14：顶点alpha与遮罩裁剪](14-vertex-color-mask-and-local-updates.md)：实际墙块的包内alpha=1，Maskable.Awake在实例子网格写为0，接到Shader622消费；与全局参数更新分别解释，实际帧和成本仍未测。

最新续查见[13：全局遮罩的材质消费](13-global-mask-material-consumers.md)：逐变体压缩参数接到Shader622的实际纹理槽、动画世界坐标、透明度和提前裁剪。12个前向变体中8个消费遮罩，其他shader逐变体覆盖与运行性能仍未验证。

本轮调查的是本机发行版 `SUMMERHOUSE` 1.2.12 的静态托管代码与发行资源，聚焦与 Tiny Glade 可比较的建筑、邻接、层次、装饰和变体机制。先看[证据与边界](00-evidence-and-scope.md)，再按问题读：

1. [放置、格点与前后层次](01-placement-grid-and-depth.md)：一件建筑块从预览到落地如何定位、翻转和决定深度。
2. [构件抽取、邻接组合与解锁](02-picker-combinations.md)：候选如何选择，怎样用相对格点识别组合并替换构件。
3. [保存、重建与美术变体](03-save-palette-and-visuals.md)：保存何种结构，材质换色与全局调色如何作用。
4. [发行资源中的方块与组合](04-packaged-blocks-and-combinations.md)：真实预制件 ID、相对格点配方和网格引用如何与代码接合。
5. [材质、像素化与相机](05-materials-pixelization-and-camera.md)：预制块到材质/纹理引用、主相机与低分辨率重绘的实际配置链。
6. [局部更新与渲染成本](06-local-updates-and-render-costs.md)：放置组合扫描、单目标材质切换、网格实例与条件性的格线重画开销。
7. [像素化回贴、深度与局部修改](07-pixel-blit-depth-and-local-render-route.md)：Shader 65 的实际取样、透明混合和深度输出，以及块级修改怎样被层重绘消费。
8. [回贴过滤与 LOD 来源](08-filtering-and-lod-provenance.md)：inline sampler 原始记录、Point/Clamp 格式解读，以及复制写 LOD 0、回贴继承共享属性块的条件。
9. [LOD 写入者与 pass 顺序](09-lod-writers-and-pass-order.md)：默认配置、稳定事件排序、图集 writer 与回贴之间的实际静态先后。
10. [低分辨率目标的 mip 与附件](10-low-resolution-mips-and-attachments.md)：主相机 target、默认 mip 标志、颜色/深度分配，以及重绘与回贴的附件身份。
11. [遮罩目标与截图相机切换](11-mask-target-and-camera-overrides.md)：MaskingMap 的外部引用、过滤/mip 配置与全局发布，以及主相机截图的目标替换和正常清理。
12. [相机层筛选与遮罩内容](12-mask-camera-filter-and-shader-data.md)：相机剔除与feature层掩码交集，Mask材质的完整pass/程序索引，以及世界Z灰度编码。

**已验证的主要区别：**这份程序集以 `BuildingBlock` 预制件为构造单位，使用格点吸附、Z 深度候选和相对位置组合规则。组合成功可以解锁新块，也可用另一块替换已放置块。调查中没有发现足以证明它像 Tiny Glade 那样从连续建筑轮廓生成墙、屋顶和接缝的代码路径；这个否定仅限于当前读取的 `Assembly-CSharp.dll` 与选定模块，不涵盖包内全部资源或其它代码。Tiny Glade 的相应证据见[建筑资产与拼装](../64-tiny-glade-building-kit-and-asset-assembly.md)。

研究用于独立理解机制。代码报告中的构造算例与第 4 篇的真实发行配置已分别标明；给真实配置填入的世界格点仍是演算，不是游戏实测。没有启动游戏、读取玩家存档，或复制其资产到自研工程。
