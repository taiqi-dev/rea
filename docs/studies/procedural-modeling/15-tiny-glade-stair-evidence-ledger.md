# Tiny Glade 楼梯与连接结构：证据账本

本轮对应用户问题：端点锚定、踏步与平台、支撑生成，以及建筑变化后的局部重建。它补充已有建筑与水体研究，不覆盖它们的历史证据计数。时间工具复核时间为 **2026-10-12 15:45:03 PDT，America/Los_Angeles**（UTC 22:45:03）；这表示调查记录时间，不是游戏版本发布日期。

阅读顺序：[11 端点与路径](11-tiny-glade-stair-anchors-and-paths.md) → [12 踏步与平台](12-tiny-glade-stair-treads-and-platforms.md) → [13 支撑](13-tiny-glade-stair-supports.md) → [14 局部重建](14-tiny-glade-stair-local-rebuild.md)。

## 1. 原制品身份与方法

| 对象 | 身份 |
| --- | --- |
| 原始游戏目录 | `E:/Steam/steamapps/common/Tiny Glade` |
| EXE SHA-256 | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| PDB SHA-256 | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |
| 匹配 GUID / age | `d8d61d04-9e31-5b47-4c4c-44205044422e` / `1` |
| 首选镜像基址 | `0x140000000` |
| Native 解码 | Capstone `5.0.3`，按 DbgHelp/PDB 入口范围离线线性解码 |
| Shader 解码 | 只读有界 SPIR-V 解析，验证嵌入模块长度、指令边界与 opcode；没有运行 shader |

本文地址使用 RVA。首选 VA = 基址 + RVA；真实运行地址会受 ASLR 影响，不能将这里的首选 VA 直接当作运行时地址。文件偏移按 PE section 的 `PointerToRawData+(RVA−section RVA)` 计算，不能把 RVA 当作文件偏移。各 `.asm.txt` 每条指令同时保留两者。

本轮沿用已有工具限制：REA MCP 未连接，本地 CLI 缺少编译运行文件。没有为此重复安装、配置或构建工具。DbgHelp 提供本地符号身份和范围，Capstone 提供原 EXE 指令；手工数据流推导与独立算术检查由我们执行。**这些产物不是 REA Evidence，也没有伪造 REA session、decompiler 输出或运行捕获。**

PDB 函数名、源路径和行号只是元数据；未取得 PDB 指向的私有源文件。相同地址的模板/方法 alias 保留在证据文件中，不任选一个短名字冒充唯一函数身份。

## 2. 结论强度

| 请求模块 | 发行版已经支持的结论 | 保留的缺口 |
| --- | --- | --- |
| 端点锚定 | 从 decorator 变换与 stair extra 取位置和宽度；墙分支构造墙锚；按 AlignKind 与宽度偏移；邻居候选递归评分且有重复类别惩罚 | 非墙锚 enum 原名、所有墙形、完整退化 fallback、是否存在更高层全图策略 |
| 路径与高度 | 三次多项式采样、水平弧长归一化、默认宽高插值、两侧四分之一宽度地形采样及托高、坡度数值类别 | 样条参数与世界弧长关系、类别正式名称、完整子段合并、固定步高没有得到证明 |
| 踏步与平台 | 玩家楼梯直接消费样本；木踏板局部地形抬高；石阶/连续楼面有分离入口；平台木布局按三维长度等分，再生成踢板/侧梁/边角 | 所有最终可见踏步数、完整平台楼面拓扑、底部延伸、所有随机项与 shader 绑定 |
| 支撑 | 站点、梁柱/斜撑构造及结构图各有实际入口，细节见 13 | 不把结构图命名当物理求解证据，不把清理函数当生成函数；未恢复项在 13 单列 |
| 建筑变化与局部更新 | 地块订阅筛选、快照 old-only、assembly/visual 差集、按边清理缓存、消失边的端点邻居标脏 | 墙事件 enum 和字段名、订阅覆盖生产者、dirty 桥接、完整 ECS 调度/flush 与实际帧数 |

观察是制品字节、跳转、调用与存储；公式和集合规则是由这些观察推导。独立实现建议是进一步的设计归纳。没有声称恢复原作者意图、整个程序生成系统或可以直接复用的生产源码。

## 3. 关键入口与证据用法

| RVA | 入口/用途 | 对应正文 |
| --- | --- | --- |
| `0x563F10` | decorator 到 48B StairPoint 的节点映射 | 11 |
| `0x89B500`、`0xC01470` | 派生节点锚；墙锚标签查询 | 11 |
| `0xC01750`、`0x38C6D0` | AlignKind 宽度偏移与实际调用者 | 11 |
| `0x89B730`、`0x89E6A0` | 对齐候选评分与邻居组合选择 | 11 |
| `0x37E080` | `generate_playermade_stair_requests<false>`，路径及参数生产者 | 11 |
| `0x89E4B0`、`0xDEA860` | 样条采样点数与多项式求值 | 11 |
| `0x89BBD0`、`0x14E1900` | 组装参数及两侧地形高度 fold | 11 |
| `0x5AB920` | `playermade_stairs_assemble<false>`，实际视觉消费与分支组合 | 12 |
| `0x8B3700`、`0x8A5870`、`0x8A2D40` | 木踏步、石踏步、连续楼面 | 12 |
| `0x140DBE0`、`0x1411410` | 平台木/石构造 | 12 |
| `0x24B4D90`、`0x24B5270` | 平台木布局与发射器 | 12 |
| `0x8282D0`、`0x8279F0`、`0x826390` | 木支撑生产、站点采样与斜撑规划 | 13 |
| `0x8A6E90`、`0x8A7560` | 支持/非支持子段拆分及实际墙侧射线测试 | 13 |
| `0x8AD180`、`0xC460B0` | 结构碰撞体/初始图与 span 插入 | 13 |
| `0x894A80`、`0x8970C0` | 变化订阅、旧子段缓存与 dirty 传播 | 14 |
| `0xA60A40`、`0xA5F000` | 图快照差与公共 token 取消 | 14 |
| `0xC429D0`、`0xB15430` | 旧产物失效与 visual 删除 | 14 |

入口范围完整解码不意味着该函数全部分支已经解释。大函数只对与当前问题有关的数学、调用和生命周期切片做语义分析。

## 4. 本机证据产物

这些可选原始证据位于本次会话的本机可视化目录，没有进入 Git 或复制原游戏资产。跨机器阅读正文不依赖这些链接；要逐条复查指令需要保留此目录和匹配原制品。

- [端点完整分析](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-stairs-anchors/analysis.md)，[结构化结论和范围哈希](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-stairs-anchors/findings.json)。
- [踏步/平台指令索引](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-stairs-layout/layout-entrypoints-decode.json)，[辅助构造指令索引](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-stairs-layout/helper-entrypoints-decode.json)，[实际组装器索引](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-stairs-layout/assembly-entrypoints-decode.json)。
- [支撑调查](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-stairs-supports/findings.md)。
- [局部重建调查](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-stairs-rebuild/findings.md)，[结构化集合演算](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-stairs-rebuild/findings.json)。
- [选定 shader 模块索引](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/tinyglade-stairs-layout/shaders/summary.json)，[独立复核结果](C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7/stairs-validation.json)。

`layout-caller-candidates.json` 里的 E8 字节扫描只是找 caller 的候选；随后解码 `0x5AB920`，真实指令边界的 direct call 才成为正文证据。未解码的另一模板实例仍只列为候选。四个 shader 文件中的 10 个内嵌模块用于契约/候选范围复核，没有把它们全部称为玩家楼梯渲染闭环。

## 5. 复核与未执行的验证

本轮复核记录在 `stairs-validation.json`：原 EXE/PDB 摘要、选定 native 函数范围字节摘要、完整线性解码标志、listing 存在性、shader/内嵌模块摘要与长度、UTF-8、相对链接、围栏和独立算例。最终实际数量记录在索引的第五轮检查中，不以候选符号总数表示算法覆盖。

| 本轮 native 范围组 | 范围数 | 原 EXE 字节 |
| --- | ---: | ---: |
| 端点/路径与参数生产 | 33 | 73,314 |
| 踏步、平台与实际组装器 | 15 | 156,048 |
| 支撑、结构图、动画及 swizzle 辅助 | 19 | 101,794 |
| 局部失效与状态生命周期 | 31 | 20,894 |
| 按 RVA 去重的本轮总计 | 98 | 352,050 |

范围摘要与完整线性标志全部复核通过；语义分析只覆盖正文明确列出的切片。shader 为 4 个文件、10 个内嵌模块；文档为 17 篇、74 个相对链接。与此前建筑/水体轮次有复用输入，不能将这些计数机械相加为整款游戏的覆盖率。

算例只检查恢复公式和集合规则是否自洽：宽度相关端点偏移、有限重复类别惩罚、样条点数、两侧地形阈值、木踏板调整、平台等分布局和局部缓存失效。它们没有执行目标程序，不能证明重建结果与发行版运行等价。

未做：没有启动或附加游戏，没有读取私人存档，没有修改原 EXE/PDB/资产，没有安装反编译引擎，没有构建或测试 REA 源码，也没有执行 GPU/性能验证。当前改动为正式研究文档，已有与本任务无关的工作区改动保持原状；没有 Git 写操作。

风险：静态结构字段名不完整；可选数组、模板参数和调用分支不能无条件泛化；每个 buffer 的删除与重新生成有不同范围；实际调度顺序和退化场景未验证。后续最有价值的验证是建筑变换请求消费者、visual dirty 读取者、最终踏步计数，以及支撑/平台接缝的退化分支。
