# Tiny Glade 水体：证据账本与复核边界

本轮调查时间锚点由本机取得：**2026-10-12 14:19:19 PDT，America/Los_Angeles**。沿用 [总身份](00-evidence-and-scope.md) 中匹配的 EXE、PDB。问题范围为水域笔画、遮罩、河床/河岸、水生植物和水面；屋顶与建筑报告的覆盖没有被当作本轮水体证据。

## 方法与身份

本机 REA MCP 未连接，本地 CLI 缺少编译运行文件，沿用原阻塞记录。使用本地 DbgHelp 查询已匹配 PDB 的符号，Capstone **5.0.3** 离线解码选定 EXE 字节，按已留存 Khronos SPIR-V grammar 解析包内 shader。没有执行游戏或 GPU，也没有伪造 REA Evidence/session。

- EXE SHA256：`4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`。
- PDB SHA256：`ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2`。
- EXE 首选基址：`0x140000000`；CPU 表中的地址为 RVA，不是文件偏移。
- SPIR-V 表中的 offset 是原 `.precomp` 容器字节偏移；按 grammar 验证指令边界，不等于官方语义 validator。

符号名称只提供候选位置。文中的参数/数据流结论还依赖调用指令、字段读写、实参、纹理绑定或 shader 算术。共享地址的最短符号别名、私有编译源路径和共享 TypeIndex 都没有被当作原始源码/完整类型。

## 关键 CPU 位置

| 职责 | RVA | 已确认/限制 |
| --- | --- | --- |
| 水域输入入口 | `0x2053590` | 有效模式、笔刷尺寸、边界绘制状态、地形失效调用 |
| 当前笔画绘制 | `0x2878E40` | composite/scratch/staging 直接调用；所有提交/撤销分支未知 |
| 点列平滑入口 | `0xBD60F0` | 10 轮、非闭合标志；进行中点段重采样未完整恢复 |
| 均匀邻点平滑 | `0x19A60D0` | 端点保留、内点 1/4、1/2、1/4 权重 |
| CPU 栅格化 | `0x2879E70` | XZ 世界到 512 像素映射、Zeno blend 调用；全部 coverage 回调未恢复 |
| 栅格送 staging | `0x2879920` | 上传 ready 标志；细节见本机 CPU render 记录 |
| CPU 数据上传 GPU | `0x5E5700` | `WaterRasterStagingSsbo` → `country_core/upload_cpu_raster`；设置待模糊标志 |
| 上传调用者 | `0xF9F00` | `render_world` 的 `0xFA110` 传入 preset `0x12`，`0xFA113` 直接调用上传；完整渲染函数语义未恢复 |
| 水域纹理处理 | `0xB31C80` | 四次 blur 的 uniform、交替纹理与水域纹理发布 |
| 水生植物调度 | `0xB31710` | 睡莲、花朵、芦苇实例缓冲及独立计算入口 |
| 水面 pass | `0xB025A0` | 水面资源与绘制入口；第四轮补充固定状态和 attachment 传参链，见 10 |
| 初始化水体 | `0xC5AEB0` | 选定初始化范围已解码，不等于初始化全部语义恢复 |

CPU 线性解码的完整字节覆盖只说明选定范围能被解释成指令，不说明可达性、每条指令都运行过或整个函数都已理解。函数哈希、大小、完整字节数、调用及 RIP 常量保留在对应 `*-decode.json`。

## 四次模糊的交叉证据

CPU 原始 uniform 连续数据分别为：

```text
0x4120000000000001 + byte 1  → output_channel=1, sigma=10, horizontal=1
0x4120000000000001 + byte 0  → output_channel=1, sigma=10, horizontal=0
0x41F0000000000002 + byte 1  → output_channel=2, sigma=30, horizontal=1
0x41F0000000000002 + byte 0  → output_channel=2, sigma=30, horizontal=0
```

分别在 `0xB32185`、`0xB32277`、`0xB3234D`、`0xB3242D` 周围确认 preset `0x12` 与临时纹理的输入/输出交替。shader 同时确认水平读 R、垂直读 G。因此 [水域报告](07-tiny-glade-water-shape-and-banks.md) 的 `G=V10(H10(R))`、`B=V30(H10(R))` 是联合推导；不忽略半精度写入，不改写为常见的双向 σ30。

上传的纹理身份由调用者补证：`render_world` 的 `0xFA110 mov r8b,0x12` 与 `0xFA113 call 0x1405e5700` 指令建立同一 preset。扫描 `.text` 得到的 E8 候选还经完整指令解码核对，避免把指令内部字节误当直接调用。扫描不建立间接调用的完整性。

`upload_cpu_raster` 每个 invocation 从一个 u32 拆四个 u8，除 255 后向相邻四像素写 `(value,0,0,0)`。**上传清零 G/B/A**，随后 blur 重建软通道；这与只替换 R 并保留旧软通道不同。CPU 的 128×512 是逻辑 invocation 范围，实际按 shader 元数据的每轴局部尺寸向上取整成工作组，上传的 8×8×1 对应 16×64×1 组。

工作组换算已沿 `ComputeNode::dispatch_impl`（`0xE28810`）到保存的 render callback（`0xE7C7D0`）确认：`0xE7D0C3–0xE7D0E4` 各轴整数除法及余数生成 `q+(remainder!=0)`，`0xE7D0F3` 再调用后端。睡莲 225×225 因而为 29×29 组，芦苇 150×150 为 19×19 组；不能把取整后的所有 invocation 都称作成功生成的植物。

## 关键 SPIR-V 位置

| 职责 | 文件、模块 | 原文件 offset / 支持内容 |
| --- | --- | --- |
| 栅格上传 | `upload_cpu_raster.precomp`，3 个模块 | 模块 0：`0x54E–0x816` 寻址和拆字；`0x8DA–0x95A` 相邻像素写入；另两格式变体按本机记录区分 |
| 模糊 | `gauss_blur_mask.precomp`，0 | `0x586–0xCE6`，核/边界/读写通道 |
| 河床地形 | `terrain_editing/rasterize_terrain_stroke.precomp`，0 | `0xCD14–0xCDD4` 高度；`0xE340–0xE3BC` 中央与边带分支；`0xFC18–0xFC9C` 编码 |
| 泥土混合 | `terrain_editing/floor.precomp`，1 | `0xA296–0xA3D6`，water G 到泥土颜色 |
| 坡度 | `terrain_derivative.precomp`，0 | `0x788–0xCC0`，中心差分与 rocky.r |
| 两个位图 | `water/read_water_mask.precomp`，0 | `0x426–0x70E`，严格阈值、32 位打包 |
| 包内 GPU 画水入口 | `water/draw_water_mask.precomp`，0 | 已解析算法；未建立其在当前 CPU 笔画链的调度 |
| 水/路径交叠 | `water_x_paths.precomp`，0 | `0x1009–0x183D`，遮罩资格及 Y 变形；输入网格未知 |
| 芦苇 | `water/spawn_reeds.precomp`，0 | `0xF3E–0x350A`，候选/噪声/资格/实例 |
| 睡莲与花朵 | `water/spawn_lilypads.precomp`，0 | `0x1C24–0x76CC`，候选、主题域、动画及输出 |
| 水噪声 | `lut/water_noise.precomp`，0 | `0x6DA–0x3376`，45 次源取样及差分通道 |
| 水面 | `water_plane.precomp`，0/1 | 顶点 `0xACD–0xBD1`；法线 `0x509A–0x6906`；最终颜色 `0x10A56–0x10ABA` |

详读与全文解码不同：水面复杂片元的法线、涟漪、mask 消费和最终输出已追踪，反射/折射、阴影与光线查询的全链尚未恢复。第三轮只确认中央地形水域分支；第四轮的外侧边带和逐像素反射覆盖另记在下文与 10，不将它们追溯算入第三轮语义覆盖。

## 第三轮覆盖与输入摘要

本轮选定 **34 个不同 native 范围、58121 字节**，均完整线性解码；另解析 **12 个 shader 文件、23 个 SPIR-V 模块**。这些是字节与格式覆盖，不能替代上述局部语义覆盖。没有把前轮屋顶模块或被后续范围替换的旧分析重复计入。

独立复核重新读取 EXE、PDB 和这 12 个 shader 的摘要；按 PE section 映射重新计算 34 个 native 范围摘要，按容器起点/长度计算 23 个内嵌模块摘要。文档检查覆盖目录内 11 份 Markdown、39 个相对链接，UTF-8、围栏配对及链接存在性均通过。平滑、河床、植物尺度、动画、位图、上传拆字和涟漪的构造算例也通过独立算术检查；这些不是原作运行测试。

下表路径相对目标 `compiled-shaders/country-core/compiled/`；EXE/PDB 摘要见本文开头。模块起点/长度及独立摘要保留在原始分析记录中。

| 文件 | 字节 | 模块数 | SHA256 |
| --- | ---: | ---: | --- |
| `water/draw_water_mask.precomp` | 2703 | 1 | `5004c9d3cae4181a8ea14b12adf9e9541c4331cd8ed8bb4cd92131e39662a27c` |
| `water/read_water_mask.precomp` | 2031 | 1 | `96ba447c8f594d6cee6cdd43d857c9470f4bde7689d38175a2e005ff11ba5f28` |
| `water_x_paths.precomp` | 39301 | 4 | `5b202ffcc99b26414fc218938c65c27c4bfe631080b37286bce4cf778188e4ae` |
| `terrain_editing/rasterize_terrain_stroke.precomp` | 66041 | 1 | `54f0e72ddb067dd93b8492280541ade5a2d0002fb9b03c1e2374ad8bdf9175a4` |
| `terrain_editing/floor.precomp` | 78791 | 4 | `2cf1b17f4ae4a7eacc50c0fc8732a36370558a9d7972c62f6835bc8cecea0731` |
| `terrain_derivative.precomp` | 3996 | 1 | `dfcd52029157743a734829c45d3975f863d5c59292aef993d8d788322a73eb3d` |
| `gauss_blur_mask.precomp` | 3688 | 1 | `aa16834285ace72b80dc53dd77ac8bd52c513192cde2a17739b96ca23b82e6e3` |
| `water/spawn_reeds.precomp` | 14676 | 1 | `98ff82c610f7a03bd3b713c68c6b70062476be4138a6b40e809360938812a870` |
| `water/spawn_lilypads.precomp` | 36165 | 1 | `6523e6dc09fb90dc3ea225e13f2100b16696aeb80439a233a947ea2848b7e213` |
| `water_plane.precomp` | 114715 | 4 | `1a2a3af9ccfea5864db48ae97c18bc8b4efdd0a17431684bce3ee823b29260ea` |
| `lut/water_noise.precomp` | 13951 | 1 | `1da8dd9002aadddfde2c341c1417a1e52f422d92664575e975cd59dd8672943d` |
| `upload_cpu_raster.precomp` | 7870 | 3 | `4640d5e9ab3bb9b84b39fea94a9ed4fbccb62c4038df016a68f8c41bd5f1ae1b` |

## 本机原始分析记录

本机可再生成产物根目录：

```text
C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7
```

其中 `tinyglade-water-input/` 保留点输入与栅格辅助函数 listing；`tinyglade-water-cpu-render/` 保留上传、脏块、调度与 blur 实参；`tinyglade-water-mask/` 保留地形/遮罩解析与结论；`tinyglade-water-surface/` 保留植被/LUT/水面解析与结论。各 `findings.json` 或 `summary.json` 带文件及模块 SHA256、大小与起点。详细输出不进入 Git，不作为可分发游戏资产或恢复生产代码。

正文保留公式、入口、分支和例子，因此本机目录丢失也不会只剩不可读证据链接。跨机器重新复核仍需同摘要的发行制品与相应离线分析工具。

## 回答状态、未做与风险

已回答：点平滑与栅格坐标、CPU 上传、四次模糊的实际通道关系、中央水域河床公式、局部泥土/坡度处理、选定芦苇/睡莲/花朵公式、水 LUT 和局部水面法线/涟漪。

部分回答：编辑状态/历史、完整河岸过渡、GPU 更新排序、整个水面显示。第四轮补充的固定状态、场景 depth 传递与岸边过渡见 [绘制专题](10-tiny-glade-water-render-pipeline-and-bank-transition.md)。全部 coverage、涟漪源生命周期、完整主题和物理河流机制仍未知。没有因选定 shader 不含流体循环就宣称整款游戏不存在任何流体系统。

未做：没有启动、附加或修改游戏，没有读取私人存档，没有 GPU 捕获、实际场景/性能测试、官方 SPIR-V validator、REA 项目构建或代码测试。纯研究文档的算术与结构检查不能建立产品运行等价性。

风险：优化/代码折叠限制类型和身份恢复；字段偏移不能自动命名；shader 同名资源需要绑定核对；采样状态、f32/半精度和边界会影响结果。当前无目标文件修改风险，仍有明确的研究覆盖缺口。

## 第四轮：可见边界和绘制管线

时间锚点：**2026-10-12 14:54:33 PDT，America/Los_Angeles**。本轮新增 [10：绘制与岸边过渡](10-tiny-glade-water-render-pipeline-and-bank-transition.md)，并修正 07 将河床公式误读为最终高度的可能歧义。前文第三轮的 34 范围/12 shader 数量保持历史范围，不与下面重复输入相加成为不去重的累计覆盖。

### 关键 CPU 交叉证据

| 职责 | RVA / 范围 | 结论与边界 |
| --- | --- | --- |
| 场景构图 | `0xF9F00` | 按直接及间接调用确认节点构造顺序；不是 GPU 时间线 |
| 地形栅格入口 | `0x9B16B0` | 输出 preset A，水域 preset 12；两次后处理 A→临时→A |
| 地形 binder | `0xC177E0` | 参数尺寸字段与 SPIR-V GlobalParams 对应，不凭结构偏移猜图像职责 |
| 高度 blur helper/binder | `0x179FC20 → 0xB6E140` | CPU+14→uniform+12 σ2；CPU+19→uniform+8 方向，uniform 先清零 |
| 高度格式 key | `0xB6E900` | enum3 文本 r32f、enum14 文本 r16；文本 RVA `0x305BBB5` / `0x305BBF4` |
| 主绘制 | `0x9AC8E0` | depth 指向第三参+18，对应调用者栈+7C8 |
| 水面共用深度值 | `0xFB89C–0xFBA52`、`0xFC38E–0xFC39D` | 24 字节 TexView 值经栈+1B0→+840，最终为水面第四参 |
| 水/冰选择 | `0xFC4C2–0xFC52E` | 条件入口选择，不能用 E8 扫描的遗漏宣称没有水面调用 |
| 水面 attachment | `0xB02994–0xB029A8` | 第四参直接成为 depth view；与 half-depth 采样输入分开 |
| shader 特定 preload | `0x25D37D0`，水面分支 `0x25D75C4` | 真实字符串匹配，合成运行时状态 `0x1C21FF68` |
| 实际 pipeline creator | `0x25DB760 → 0x15D28F0` | preload `0x25D5BCA` 传真实状态；`0x25DBAA1/0x25DBABF` 建立 descriptor 并调用后端 |
| 比较转换表 | `0x331F150` | 内部 2→Vulkan Greater=4；表 `[0,1,4,2]` 单独复读确认 |
| blend 转换 | `0xE39FE0` | 水面 blendEnable=0，RGBA mask15 |
| 深度/模板与覆盖字段 | `0x15D34B5–0x15D3574` | 深度启用/写入、Greater；模板 ALWAYS；alpha-to-coverage及depth bounds关闭 |
| 附件保留字段 | `0x174C335/0x174C340`、`0xE51832–0xE51880` | TexView+11/+12 到 Vulkan loadOp/storeOp；初值和缓存规范化未知 |
| 动态剔除 packet | `0x1758EB8 → 0xE25450`、`0xE22A06–0xE22B55` | 实际记录 BACK=2，传给 dispatch+720；加载地址中间所有权桥未贯通 |

### 关键 GPU 交叉证据

| 文件及模块 | 原容器偏移 | 内容 |
| --- | --- | --- |
| `floor.precomp`，VS 0/2 | `0x1F61–0x259D` / `0x122C8–0x12904` | 坡度、水 G 和 Y→−0.8 二次修正；函数指令体相等 |
| `floor.precomp`，FS 1 | `0xA296–0xA58E` | G=0.4 暗岸带、泥 R 决定遮罩域宽度 |
| `rasterize_terrain_stroke.precomp`，0 | `0xE340–0xE8A8` 及后续噪声链 | 世界边界五单位带、背景抬高；不同于普通河岸 |
| `gauss_blur.precomp`，0/1 | 模块起点/长度见原记录 | σ2 两方向，N1、R 输入、完整核 clamp 边缘；格式声明 3/14 |
| `water_plane.precomp`，FS 1/3 | `0xCFE` / `0x12F00` | EarlyFragmentTests；不定义 compareOp |
| `water_plane.precomp`，FS 3 | `0x167EC`、`0x1A018–0x1A878` | helper 排除、quad 覆盖、选主 lane、深度最低四位打包 |
| `water/calc_deferred_rt_args.precomp`，0 | `0x2AE–0x316` | n→`(ceil(n/64),1,1,n)` |
| `water/deferred_rt.precomp`，0 | `0x5392–0x56FE`、`0x1303E–0x14E4A` | 数量上界、深度/覆盖解包、四个目标逐位保护 |
| `extract_half_res_depth_normals.precomp`，0 | `0xFD0–0x127C` | 2×2 中单像素轮换与最低一位材质标签 |
| `water_plane_refraction_copy.precomp`，FS | `0xEBD–0xF51` | 来源 RGB fetch、alpha1；没有 mask/depth discard |

下面七份是本轮渲染/高度专题单独选择或重新复核的 shader；另复核前文已列的 rasterize_terrain_stroke 与 floor，共九份。表中仍包含与第三轮重复的 water_plane，不能称作九份全新 shader。rocky_terrain 只完成 framing/身份核对，未据文件名声称完整岩地算法已恢复。

| 相对 `compiled-shaders/country-core/compiled/` 的文件 | 字节 | 模块 | SHA256 |
| --- | ---: | ---: | --- |
| `water_plane.precomp` | 114715 | 4 | `1a2a3af9ccfea5864db48ae97c18bc8b4efdd0a17431684bce3ee823b29260ea` |
| `water_plane_refraction_copy.precomp` | 5558 | 2 | `57ace002dab64994d7610144424b4ac1e2a2b89435ddd149fd690d880d642f14` |
| `water/deferred_rt.precomp` | 95201 | 1 | `51fee1d60913c25131e672c6494fcf9d2338667941ab690234b31a9ce7c22783` |
| `water/calc_deferred_rt_args.precomp` | 930 | 1 | `729b62ab6ffa778918a9582a8e51bae593f169ef908c008a33e9b467c78210c9` |
| `extract_half_res_depth_normals.precomp` | 7500 | 1 | `4e36b589039aeaaf9b7fa9761c004561a3e61b859956be51546fcb23471df455` |
| `rocky_terrain/rocky_terrain.precomp` | 37915 | 4 | `3e64f4b61b6a47b5c2937ae1654438689c166ba2a5edb147236f864266862112` |
| `gauss_blur.precomp` | 5974 | 2 | `2cf24a8b7facd9b6009ee0d872fb09f4897d7dab30defc8681eeb9ffc9819e04` |

水面 JSON 只报告结构统计，未交付原始顶点/UV 数组：418 字节，SHA256 `4489e357dff4f2e48d1ce376ceb80441d44e5281377164db39500e909708f2c8`。它的两个三角形与固定 Y=−0.01 的 VS 联合证明该资源不是动态湖形边界网格。

### 本机记录及核对方式

原产物根目录下新增 `tinyglade-water-order-final/`、`tinyglade-water-pipeline-final/`、`tinyglade-water-banks-final/`、`tinyglade-water-visibility-final/`。其中保留 native 完整范围摘要和 listing、SPIR-V 模块摘要与选定指令、格式与固定状态表、逐 claim 的观察/推导/未知。`height-binding-confirmation.md/json` 专门保留方向/格式补证，后来的证据取代早期“仅见 packed 值”的待证项。

独立核对输出为原产物根目录的 `water-pipeline-validation.json`，内容包括 EXE/PDB、所选原 shader、模块、网格以及按 PE section 映射的 native 范围 SHA256。另独立复读比较转换表与两项格式文本，核对坡度修正、暗岸带、Greater 条件、覆盖位打包和 dispatch 数量算例。文档 UTF-8、围栏、尾随空格和相对链接一并检查。该记录没有执行原作，不是 REA Evidence，也不是官方 SPIR-V validator。

最终独立复核通过 **194 项检查**：本目录 **12 份 Markdown、49 个相对链接**；EXE/PDB、**9 个 shader、20 个内嵌 SPIR-V 模块**及水面 JSON 的摘要一致；按 RVA 去重的 **40 个 native 范围、133468 字节**摘要一致，全部选定范围完整线性解码。这些包含复用的 render_world 与既有 shader，不是全部新增代码，也不是全部语义已经恢复。

未做：实际场景截图/读回、GPU 捕获、render graph barrier 全链、全部反射/折射分支、缓冲容量/reset 和所有动态状态。风险：CPU 构图不能证明实际 GPU 时间线；样本、精度和局部显示修正可能影响最终边界。10 将这些限制与已经确认的字段分开列出。
