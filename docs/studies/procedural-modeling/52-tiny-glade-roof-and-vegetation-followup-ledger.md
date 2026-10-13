# Tiny Glade 屋顶几何、可见性、编辑与植被重建：第十二轮账本

本轮承接[47上一轮缺口](47-tiny-glade-four-systems-evidence-ledger.md)，继续查建筑间屋顶可见边界、屋顶更新和植被清旧。正式阅读路线：

- [48屋顶表面与装饰附着](48-tiny-glade-roof-trigger-mesh-and-attachments.md)。
- [49屋瓦可见性与屋面深度](49-tiny-glade-roof-gpu-visibility-and-depth.md)。
- [50编辑消息到重新铺瓦](50-tiny-glade-roof-edit-messages-and-regeneration.md)。
- [51植被计数与活跃列表](51-tiny-glade-vegetation-counts-and-active-list-rebuild.md)。

起始时间工具返回 **2026-10-13 06:43:52 UTC**，对应 **2026-10-12 23:43:52 PDT（America/Los_Angeles）**。另一次时间工具返回2026-10-13 07:00:22 UTC，即2026-10-13 00:00:22 PDT。本次跨Pacific午夜，保留实际起始时间和既有产物根目录，不以UTC或目录日期推断版本变化。

## 1. 身份、授权与取证方式

目标仍为`E:/Steam/steamapps/common/Tiny Glade`同一发行版：

| 制品 | 长度 | SHA256 |
| --- | --- | --- |
| tiny-glade.exe | 65,612,184B | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| tiny_glade.pdb | 310,513,664B | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |

匹配PDB GUID=`d8d61d04-9e31-5b47-4c4c-44205044422e`、age=1。首选image base=`0x140000000`；RVA按实际PE节表转换。shader位置为原precomp文件偏移及独立module起点。

REA MCP未连接、本地CLI缺少编译运行文件的既有阻塞没有变化。沿用DbgHelp、Capstone5.0.3及包内SPIR-V的静态备用流程；本轮没有REA provider/session或REA Evidence ID。PDB类型/源行仅作为定位与参数解释，实际指令/资源访问佐证行为，不表示取得私有源码。

只编辑本研究文档及索引。未启动、附加、改游戏/内存、读私人存档，未安装、构建、修配置或Git写入。并行研究按已读取reverse-engineer-anything技能“Plan broader investigations”第6项划分独立问题；正式结论由根任务整合并核字节。

## 2. 已回答、部分回答与未知

| 问题 | 发行版确认 | 尚未确认 |
| --- | --- | --- |
| 屋顶触发几何 | 本屋顶triangle/UV/normal生成；flat4/nonflat9带、圆形15周向格；属性替换与失配panic；RT顶点和raw tag输出 | 完整拓扑、第二组RT表面、hit枚举、RT同步；不能当建筑间Boolean |
| 装饰附着 | UV重心查询→三维位置；装饰变换缓存/分件显示实际caller，编辑读triangle slice | 所有装饰资格/回退和UV退化；CPU表面与GPU瓦逐点一致性 |
| 屋顶最终可见边界 | 选定11模块资源审计；本瓦plane/同wall dormer；视锥、前后visibility bits、主HZB min/倒数、太阳三级联max；屋面局部FragDepth写入 | CPU其他相交信息、全renderer附件/深度compare、完整跨pass顺序，建筑间保留侧仍部分回答 |
| 编辑到铺瓦 | 带类型包装器实际call；EditRoofCmd/OnWallChanged→RecalculateRoofCmd；reader游标、实体generation/query筛选；per-roof索引回收→flat/矩形/圆形分派 | 所有生产者/删除、全局去重、阶段枚举原名、固定帧时间线和GPU上传 |
| 植被清旧与重建 | 23条draw模板及8×16B dispatch模板；buffer copy/fill ABI参数；bush9/flower10 atomic追加；草清ActiveCount、45056输入→逻辑k→活动前缀，选定LOD0消费 | backend正式API槽/staging类型、indexCount补写、跨系统顺序/频率、逐DirtyTiles补种和树全系统 |

“已确认”保持各自证据类型：copy/fill语义为受参数支持的ABI推导；记录与调用为指令观察；算例为构造演算。没有因完整线性解码就声称所有分支语义均恢复。

## 3. 本轮对旧解释的推进

1. 41已确认先clear再铺瓦，本轮50进一步建立真实消息类型、执行对象资格和回收列表机制；不再只以入口名解释更新。
2. 42的同屋顶plane继续有效。本轮48追到triangle cache的实际消费者，49做完整选定模块资源审计，仍未把两者混成建筑间clip producer。
3. 45的发布链与各产物清理职责继续保留；本轮没有用屋顶局部消息链冒称整个游戏统一scheduler已恢复。
4. 46的garden `+29B`仍是raster状态。本轮51另找全局间接计数模板和草ActiveCount clear，区分实例payload、活动前缀及物理slot。
5. callback copy临时三qword按实际字段保留为`{u32 offset,0,u64 size}`。128/460是staging申请长度；未恢复正式descriptor类型，不把它们直接冒称已核callback类型字段。

旧轮统计保持当时覆盖。本轮新选择、复用和有界审计分别记录，不改写历史验证数。

## 4. 关键原生入口与shader定位

| 位置 | 本轮职责 |
| --- | --- |
| `2809250 / B76780 / 14737C0` | 本屋顶表面、噪声外层、Triangle.normal |
| `A0A0F0 / A0A1B0 / A0A080` | 三种Vec替换、释放与数量断言 |
| `A0A130 → 1B45E90` | UV表面查询、重心插值与Y偏移 |
| `8E2D05 / 14C8B86 / 1F3D77A` | 装饰/编辑实际消费者 |
| `1F38B36 / 1F45858 / FDEA42` | edit/spatial/assemble三个带类型包装器的实际call |
| `280F6B0–280F715 / 280E986–280E9E6` | 重算消息实际追加 |
| `1F46490 / 1F4A6C0` | reader、实体筛选、allocation清旧与形状分派 |
| `6C32CF–6C32E4` | in_set注册，raw set=0x1D；完整阶段名未解 |
| `9EA890 / 1A88AC0` | 两份staging模板与backend copy形状参数 |
| `3032538 / 3021A00` | draw460B、dispatch16B模板原字节 |
| `B2126A → E29980 → E7D540` | ActiveCount clear构图及backend fill形状参数 |
| `B21395 / B213AF` | 45056输入dispatch literal及登记 |
| roof tile cull，start10981，`20113–22505` | 主HZB和前后visibility位 |
| roof tile cull，start24642，`34526–43218` | 三太阳layer各四次fetch及max |
| roof floor，start7330，`23510 / 49486 / 78450 / 80758` | 自身输入z、材质候选选择与FragDepth store |

E8全.text扫描结果在实际caller完整解码、call边界/目标核对之前仅是候选。另一个ui_move_decorator候选保持未单独解码，不计为实际消费者闭环。

## 5. 原始记录与再核方式

可再生成产物根目录仍为：

`C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7`

| 子路径 | 内容 |
| --- | --- |
| `tinyglade-roof-building-relations/findings.md/json` | 12原生范围、六组claims/指令定位、UV/setter/RT/消费者与算例 |
| `tinyglade-roof-building-relations/native-range-manifest.json` | 完整范围、原字节摘要与listing |
| `tinyglade-roof-visibility/summary.json` | 3个shader、11模块身份和解码目录 |
| `tinyglade-roof-visibility/resource-audit.json` | 每模块全部resource interface及实际访问位置 |
| `tinyglade-roof-visibility/selected-subranges.json` | 13段关键SPIR-V原字节、摘要和指令记录 |
| `tinyglade-roof-update-routing/findings.json` | 9主体范围、两复用入口、15段细范围及消息演算 |
| `tinyglade-roof-update-routing/messages/symbols.json` | RecalculateRoofCmd等专用FunctionSystem类型候选；不能独立作为行为证明 |
| `tinyglade-vegetation-rebuild/findings.md/json` | 9主体范围、13段native/25段shader、模板、ABI限定与三算例 |
| `tinyglade-land-vegetation/` | 四个复用CPU入口、四候选shader及LOD0消费证据 |
| `roof-vegetation-followup-validation.json` | 根任务独立重新读取/解码/算术/文档检查结果 |

正式交付为48–52的机制解释、独立规格和未知。原字节/listing是本机可再生成调查产物，没有包装为生产代码或可分发游戏资产。

## 6. 独立复核与运行局限

复核包括EXE/PDB整文件摘要、按RVA去重的原生范围摘要与新线性解码、细范围文件偏移/摘要/指令边界、CPU引用的具体指令位置及真实call目标。shader重读原precomp、核内嵌module的word count/摘要/指令边界，再核细范围和resource audit定位。常数模板独立从EXE读取并解释全部23条字段。

构造例覆盖剖面格数、法线/噪声、Vec释放量、UV权重、RT标记、消息游标/回收、HZB比较/visibility位、局部depth选择、植被计数/草逻辑ID和dispatch向上取整。它们验证说明中的算术及条件，不能建立float32逐位或发行版运行等价性。

最终独立验证：**2,283项通过，0失败**。54份Markdown、306个相对链接均有效；本轮36个不同RVA的原生范围共69,840B，摘要和新线性解码一致。另核28段native细范围、88个屋顶claim指令位置及实际直call。12个shader文件、23个内嵌模块的摘要、word count和边界一致，共结构遍历25,007条SPIR-V指令；38段shader细范围及939个resource audit声明/访问位置通过校验。

| 组 | 组内去重范围 | 字节 |
| --- | --- | --- |
| 屋顶表面与消费者 | 12 | 36,238 |
| 屋顶消息与铺瓦，含两复用入口 | 11 | 22,280 |
| 植被reset与生成，含四复用入口 | 13 | 11,322 |

shader覆盖包括3个屋顶文件/11模块、4个本轮植被文件/5模块，以及5个复用候选/LOD0筛选文件/7模块。部分本轮植被模块只保留候选角色，未用它们冒称最终indexCount生产链已经恢复。检查数包含原字节、资源位置和结构元数据核对，不是2,283个算法运行测试；线性解码和25,007条结构遍历也不代表全部分支语义已恢复。

## 7. 未做与剩余风险

未做：游戏运行/附加、私有存档、GPU抓帧、RT命中/提交观察、交叠建筑实机对照、真实编辑延迟/植被调度频率、性能测试、SPIR-V语义验证器及REA项目构建/实现测试。此次未改REA生产代码，文档检查是本次对应验证。

风险：完整建筑间屋顶裁切和最终pass状态仍未知；CPU surface cache、RT几何、可见瓦与局部材质深度是不同表示。植被初始化的copy/fill有ABI推导边界，tail payload可保留且安全依赖consumer遵守前缀规则。没有证明逐地块补种或全系统固定顺序。研究结果仅用于理解和独立设计，不携带原代码/资产作为自研生产实现。
