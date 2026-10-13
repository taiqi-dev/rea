# Tiny Glade 普通窗户与自动装饰：证据账本

本轮回答放窗后如何生成墙洞、重建砖和木板、让窗框贴墙，以及窗边装饰如何自动生成。沿用同一匹配的本地发行版制品，未借公开原型替代本轮算法。开始时本机时间工具返回 **2026-10-13 00:19:12 UTC，即 2026-10-12 17:19:12 PDT，America/Los_Angeles**；记录使用 Pacific Time，不把 UTC 日期跨日当作本地调查日期变化。

阅读顺序：[16 放置与墙洞生产](16-tiny-glade-window-placement-and-holes.md) → [17 砖木重建及精细洞形](17-tiny-glade-window-wall-reconstruction.md) → [18 窗框与楣梁](18-tiny-glade-window-frames.md) → [19 窗边自动装饰](19-tiny-glade-window-autoclutter.md)。

## 1. 已确认与未知分别到哪一步

| 请求问题 | 本轮确认 | 明确保留的未知 |
| --- | --- | --- |
| 放窗后生成墙洞 | 从 modified decorator 取墙坐标和 collision 尺寸；cottage 生成一条粗 region，gothic 生成三条；另有条件地产生精细切口；按墙发布，finalize 才转 min/max 并处理周期副本 | 鼠标命中、拖动/吸附如何修改 decorator；完整 enum 和所有墙材质条件 |
| 重建砖 | 普通墙 `WallConstructor` 实际调用局部洞筛选与砖切分；不同覆盖关系走不同分支 | 所有洞组合、最终分块数、退化情况和完整显示/碰撞调度 |
| 重建木板 | 粗洞经板坐标映射进入差集，精细窗记录另形成每构件列表；三个planner实际扣洞后细分/合并；第十一轮纠正两条输入链及曲板类型，见17/43 | 全部样式的几何形状与最终实例数 |
| 精细洞形 | CPU 32B cut 转 GPU 48B；木板实例 `+72` 与 shader 契约对齐；片元实际读取索引、窗口法线/bounds 和形状距离场，处理深度/法线与 demote 分支 | 所有上传/descriptor 绑定、SDF 光栅化/重采样/编码、迭代与噪声分支；不宣称整墙通用 SDF 布尔 |
| 窗框贴墙 | 整体弦中点/yaw、部分墙模式固定出墙量；楣梁按 subtype 分段，各段取墙点独立朝向；gothic 携带局部 normal/position | 缓存刷新、动态墙厚/倾角、gothic 专属 shader 如何消费局部参数 |
| 窗台装饰 | 模型 marker 变换成 80B 候选，再转稳定键的 pending 请求；与 cottage 实际生产端对齐 | 上游完整生成概率、所有资源索引对应的物件名称 |
| 窗周装饰 | 双侧定向区域、局部重采样、位置与类型种子、特定分支加权选择、边距/周期位置采样、候选重叠贪心筛选、swap-remove、实体匹配与待删除标记 | 全部类别权重/环境 mask；确切上游事件和 epoch/scheduler；最终网格、动画与 deferred 命令执行 |

“确认”表示正文中的实际指令、调用与数据布局支持相应切片；不是全功能每个分支都恢复。默认研究从目标制品静态数据出发，没有运行图形界面或捕获真实游戏帧。

## 2. 制品与地址身份

| 对象 | 身份 |
| --- | --- |
| 原始安装目录 | `E:/Steam/steamapps/common/Tiny Glade` |
| EXE SHA-256 | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| PDB SHA-256 | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |
| 匹配 GUID / age | `d8d61d04-9e31-5b47-4c4c-44205044422e` / `1` |
| preferred image base | `0x140000000` |
| Native 解码 | Capstone `5.0.3`；匹配 PDB 的 DbgHelp 范围，原始 EXE 线性解码 |
| Shader 解码 | 本地有界 SPIR-V 模块解析、官方 grammar opcode/长度核对；不执行 shader |

正文 CPU 地址均为 RVA；首选 VA=基址+RVA，不等于 ASLR 后的真实地址。文件偏移按真实 PE section 转换。SPIR-V 地址则是原 `.precomp` 文件偏移，与 RVA 属于不同坐标系。

REA MCP 未连接、本地 CLI 缺编译运行文件的既有阻塞未改变。本轮继续有界静态 fallback，没有安装、配置或构建引擎，也没有伪造 REA Evidence/session/decompiler 输出。PDB 私有源路径与行号只是定位元数据，不表示取得原 Rust 源文件。

同址泛型 alias 多次出现，例如容器 grow 与实例 setter。本文用真实参数位置、stride、写入偏移和消费者证明语义，不将自动挑选的短名字当成唯一类型身份。E8 字节扫描仅用于找 caller 候选；后续完整范围解码确认指令边界的 call，才纳入正文调用链。

## 3. 本轮 native 覆盖与共享范围

| 范围组 | 解码记录 | 原 EXE 字节 |
| --- | ---: | ---: |
| 窗户蓝图、发布、粗洞 finalize 与比较 | 33 | 46,616 |
| 砖木消费者、精细 cut、SDF 与辅助函数 | 30 | 97,176 |
| 框体、楣梁、墙坐标和 marker | 26 | 38,611 |
| 自动装饰区域、候选与生命周期 | 26 | 71,414 |
| **按 RVA 去重的本轮范围** | **105** | **225,565** |

四组共 115 条记录，包含 10 条重复范围，不能机械相加作为独立覆盖。重复范围摘要与长度相同。完整线性解码只证明选定字节范围能解码，不证明每条指令可达，也不证明大函数所有分支都已解释。

此前 04 的砖切分与矩形差集在本轮复用，并重新核对原字节；新的内容是普通窗的生产与消费连接。本轮也复用了旧的 helper 身份和工具，不将历史文档计数改写成当前计数。

## 4. 关键入口与解释边界

| RVA | 入口/证据职责 | 正文 |
| --- | --- | --- |
| `0x8C71E0`、`0x8C3060` | cottage / gothic 普通墙窗生产 | 16、18 |
| `0xC3BA10`、`0x901130` | modified decorator 入口与墙目标坐标 | 16 |
| `0x8F3750`、`0x8F4090` | 蓝图按 ID 更新、发布及新旧视觉比较 | 16 |
| `0x14FCF70`、`0x14FD210` | CPU 粗洞与精细 cut 两条真实 extend | 16 |
| `0xC2B060`、`0xDEEAD0` | center/dims 转 AABB、周期副本 | 16 |
| `0x1446690`、`0x815BE0`、`0x146C450` | 普通墙砖构造、洞筛选与局部切分 | 17 |
| `0x144A4C0`、`0x1485B80`、`0x14877D0`、`0x14899D0` | 板构造与三种 planner | 17 |
| `0x1484710` | 严格相交后的区域扣洞 | 17，另见 04 |
| `0xA69E90`、`0xA6A320` | finalized 范围与 GPU 48B 格式 | 17 |
| `0x24BD0E0`、`0xA78260`、`0xAAAB70` | 每构件窗口列表、24/8 位编码和实例字段 | 17 |
| `0x19BA6D0`、`0x19BC990`、`0x19BC400` | mask、距离变换与加权抛物线下包络 | 17 |
| `0x92F860`、`0xDEA260` | 墙投影模式与世界曲线转换；两种长度未证明恒等 | 18 |
| `0x8C6840`、`0x8C2BE0` | 分段楣梁与 gothic 局部法线参数 | 18 |
| `0x8C7060`、`0x14E3200` | flowerbed 模型标记到世界 Transform | 18、19 |
| `0x28E9C40`、`0x28EDA10` | 窗台候选请求、窗周区域 | 19 |
| `0x10CFF30`、`0x28DBD80`、`0x28E9FF0` | region 更新、采样、候选筛选 | 19 |
| `0x10D0740`、`0x28EAD00` | swap-remove 与实体更新/待删除 | 19 |

## 5. Shader 输入和 CPU/GPU 对齐

本轮解析四份发行版文件，共 16 个内嵌模块：

- `nani_wooden_plank.precomp`：实例字段、窗口列表、48B 窗数据读取、距离场和深度/法线处理。
- `nani_gothic_window_bricks.precomp`：完成模块身份与边界复核；局部 normal/bone 参数的全部顶点消费没有恢复。
- `nani_solid_vertex_color_window.precomp`：窗口模型材质候选，楣梁生成器有实际 shader key；本轮未恢复其全材质表达式。
- `wall/wall_brick_lod0.precomp`：所选模块未找到窗口命名资源；这是有界名称检索结果，不证明全部石墙无其他裁剪机制。

列表setter写`+0x48`，直木板和曲梁shader各自的window_cut_list都在offset=72；片元拆高8/低24位并按48B读窗口。第十一轮确认14530C0真实builder为CurvedHalfTimber，不能据共享setter/80B大小把它当直木板仿射格式。见[43后续证据](43-tiny-glade-wooden-wall-board-layout.md)；本账本第六轮检查计数保留当时范围。descriptor和每种木件上传顺序仍未全部闭环。

## 6. 本机可选原始证据

大型 listings、结构化范围和验证输出保存在当前会话的本机可视化目录，没有提交到 Git。跨机器读正文不依赖这些链接；逐指令复查需要保留此目录与匹配原制品。

- [放置与墙洞结论](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-windows-placement/findings.json)。
- [砖木消费者解码](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-windows-consumers/chain-entrypoints-decode.json)，[记录与列表解码](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-windows-consumers/entrypoints-decode.json)，[复用扣洞及 setter 解码](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-windows-consumers/helper-entrypoints-decode.json)。
- [窗框范围与算例](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-windows-frames/findings.json)。
- [窗边装饰 41 段字节证据](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-windows-clutter/findings.json)，[其独立验证](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-windows-clutter/verification.json)。
- [Shader 模块索引](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-windows-consumers/shaders/summary.json)，[整轮独立复核](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/windows-validation.json)。

## 7. 复核的实际含义

独立复核涵盖：EXE/PDB 摘要、105 个去重 native 范围摘要/长度/线性完整标志/listing、重复记录一致性、四份 shader 和16个模块摘要与长度、41段装饰子范围摘要与真实文件偏移，以及文档 UTF-8、围栏、相对链接。

构造算例核对包括：center/dims 与周期边界、gothic 三矩形、严格相交/面积守恒、窗口列表与 layer 编码、SDF 局部采样门槛与下包络、弦朝向/固定偏移、楣梁端头、marker 位置、双区域、收边/fract 采样、特定权重分支、候选 swap-remove。它们验证公式和状态规格自洽，没有执行原 EXE，不能证明与真实游戏画面、性能或生命周期等价。

各篇都明确原作常数与构造输入。没有把一个资源权重槽猜成“空物件概率”，没有把粗矩形并集当作 GPU 精细窗形，没有把待删除命令当即时删除，也没有把 cached transform 当旧新姿态动画。

未做：未启动/附加游戏，未读取私人存档，未修改原程序或资产，未安装/构建引擎，未运行 REA 源码测试或 GPU/性能测试。当前任务只补研究文档；已有无关工作区改动保留，没有 Git 写操作。

风险：raw enum 和资源槽原名、若干墙字段的物理语义仍未知；hash 相等与逐字段相等不同；大函数的切片解释不能推广到所有分支；静态调用存在不能证明帧顺序。下一轮有价值的入口是输入吸附到 modified 的写入、窗框局部参数的专属 shader、以及装饰 deferred 命令到真实网格/删除的最后消费链。
