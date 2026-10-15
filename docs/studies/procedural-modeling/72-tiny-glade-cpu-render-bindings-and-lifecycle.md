# Tiny Glade：CPU 绘制绑定与 pass 生命周期

> 后续 [75：纹理句柄对应](75-tiny-glade-texture-handle-provenance.md)已逐跳接通 G-buffer 图资源记录到 `gbuffer_tex` 的 set 0 / binding 1；下文保留此前调查的范围，实际 GPU 对象与帧执行仍未观察。

> [77：墙绘制回调映射](77-tiny-glade-draw-callback-mapping.md)另补墙实体注册、DrawListItem 字段、阶段筛选与 indirect draw 命令寻址。

本篇补齐[材质与光照](69-tiny-glade-shading-lighting-and-contact.md)和[局部更新成本](70-tiny-glade-update-and-render-costs.md)之间的一段 CPU 调用链。静态证据已把 **G-buffer pass 注册 → 绘制桶绑定 → 条目绘制**，以及 **同一 `render_world` 路径注册 deferred 光照 pass** 接起来；具体 G-buffer 纹理句柄是否就是 `solid_light_sun_sky` 的 `gbuffer_tex`，仍须资源身份追踪或运行抓帧确认。

## 输入与核验方式

输入沿用 [70](70-tiny-glade-update-and-render-costs.md) 核对过的同版 `tiny-glade.exe`（65,612,184 B；SHA256 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`）和 `tiny_glade.pdb`。地址均为 EXE preferred VA。用正式 `digging-a-hole/tools/pdb_probe.py` 的显式路径与掩码读 PDB；`*deferred_raster*` 为 4/4、`*solid_light_sun_sky*` 为 2/2、`*render_bucket*` 为 1/1，均枚举完毕。用现有 VS2022 `dumpbin /DISASM /RANGE` 有界读取函数，原始投影在 ignored `.cache/procedural-modeling/render-chain-followup/tiny-glade/`：`render-world-slice.txt`、`main.txt`、`gbuffer-graph-raster.txt`、`bucket.txt`、`draw-indirect.txt`、`deferred-raster.txt`、`deferred-graph-raster.txt` 和符号 JSON。pass 与 shader 路径字面串从 EXE `.rdata` 的精确 VA 按 PE section 映射读取。本轮没有运行或附加目标、抓 GPU 帧、读取存档；没有新的 REA native session。

## 1. 从世界渲染入口到 G-buffer 绘制

`tiny_glade::render_loop::render_world` 的 `0x1400FABCD` **直接调用** `country_core::...::main_pass::main_pass`。后者在 `0x1409ACB8C–0x1409ACBA0` 把位于 `0x1430294C0` 的 `G-buffer` 字符串、局部 attachment/closure 参数交给 `GraphApi::raster`。该调用的目标 `0x1417555E0` 的 PDB 类型是 `GraphApi::raster<1, ([ColorAttachment;1], DepthAttachment), main_pass::...closure_env$0>`；它在 `0x1417557A8` **直接调用** `draw_lists::render_bucket`，于 `0x14175597C` 设置 render callback。这里确认的是一色彩 attachment 加深度 attachment 类型的 pass 与 CPU 绘制桶调用，不能仅凭类型判定纹理格式或最终 GPU 提交时间。

`render_bucket` 对当前条目的三处 binding stack 项分别调用 `GraphApi::find_binding_set_stack_item`（`0x140AF4FF0 / 500C / 502B`），任一查找失败便跳到错误分支。对选定 pipeline，`0x140AF51B9` 取得 `prebuilt_pipeline`，`0x140AF51D6–0x140AF51E4` 用明确的计数 **3** 调 `bind_stack_sets`；条目另有 binding set 时在 `0x140AF51EC–0x140AF51FA` 再绑定。随后 `0x140AF523F–0x140AF5260` 有两种条目路径：非空回调指针走 `0x140AF5080–0x140AF5098` 的间接调用；另一分支按条目参数调用 `RasterStreamRecorderWithPipeline::draw`。后续索引网格分支还在 `0x140AF53FC / 540C` 设置 vertex/index buffer。故“一个 bucket 等于一次 indirect draw”不成立；它会查找与绑定，然后按条目类型提交。

同一模块的 `draw_lists::...::indexed_indirect::draw_fn` 给出间接条目的**实际提交函数**：`0x140AF4A5E–0x140AF4A66` 检查资源容器，缺失则进入 `unwrap_failed` 分支；`0x140AF4CF8` 从 `AssetSsboLibrary` 取得 render-graph buffer，`0x140AF4D03 / 4D12` 设 vertex/index buffer，`0x140AF4D64–0x140AF4D7A` 计算 `20 × 列表索引` 的字节偏移并以计数 1 调 `draw_indirect`，最后 `0x140AF4D85` 调 `finish_read_rg_buffer`。这证明列表记录能被作为间接命令读取、记录绘制并释放该次 graph read；**尚未证明** `G-buffer` 这个 bucket 的每个回调恰好指向该函数，或 20 B 记录一定属于墙砖。调用、回调与图资源生命周期的界限应分别保留。

## 2. Deferred 光照 pass 的 CPU 注册

同一 `render_world` 的 `0x1400FC314` 调 `country_core::...::deferred_raster::deferred_raster`；在这条静态路径中，它晚于前述 `main_pass` 调用。`deferred_raster` 先查资源：`0x1409EA609 / 61B` 两次 `AssetSsboLibrary::read_rg_buffer`，`0x1409EA633` 向 `AssetTextureLibrary::get_rg_preset` 取纹理 preset。它把四个明确的着色器路径 `country_core/deferred/{solid,grass,plant,canopy}_light_sun_sky`（字符串 VA `0x143032410 / 439 / 462 / 48B`）以及捕获的资源放入 raster closure；`0x1409EA7B1` 以字面 pass 名 `Apply deferred lighting`（`0x1430324B5`）调用 `GraphApi::raster`。对应 PDB 专门化 `0x14175BB80` 的类型是一色彩 attachment 和深度 attachment；其中 `0x14175BEBA` 调 `shader_with_compatible_args`，`0x14175BEF4` 调 `draw`，`0x14175C64F` 注册 render callback。函数返回前在 `0x1409EA7EE / 7F9` 对两次 SSBO graph read 配对调用 `finish_read_rg_buffer`。

这是比[69](69-tiny-glade-shading-lighting-and-contact.md)的 shader 格式相容更强的 CPU 证据：实际 render-world 分支注册了命名的 deferred pass，传入了 `solid_light_sun_sky` 等四种 shader 路径，闭包代码能记录 draw。然而当前反汇编未完成 `main_pass` 输出 attachment 的**句柄身份**到 `solid_light_sun_sky` binder 中 `gbuffer_tex` 参数的逐字段对应；也未证明所有四种 shader、所有 pass 每帧都执行。`GraphApi::raster` 和 `draw` 是 graph/recorder 层调用，实际驱动执行及可见像素属未观测边界。

## 3. 局部更新如何进入绘制及构造规模

[70](70-tiny-glade-update-and-render-costs.md) 已证实选定 `InstancedWall` 的旧 allocation 在 `gpu_flush_brick_buffers` 清理、新砖以每条 64 B 经 `SparseInstanceBuffer::push` 写入并上传；`render_world` 在 `0x1400FACAE` 调墙 draw-list pass 2，`0x1400FAD62` 调通用 `gpu_generate_draw_lists`，之后还存在 shadow 路径 `0x1400FB5F3 / 0x1400FB6A1`。这些调用把“编辑后实例数据”与“生成供渲染使用的候选列表”接到同一渲染编排中，但本轮未追出每条墙砖 allocation 到特定 `DrawListItem` / `indexed_indirect::draw_fn` 指针的确切 ID 映射。不能把墙的上传粒度误作 G-buffer 的固定工作量，也不能把 compute 函数存在误写成所有帧必执行。

设**构造例**中一次 pass 有 `B=40` 个进入 `render_bucket` 的非空 bucket，共 `D=200` 个待处理条目，且每次三项 binding stack 查找均成功。桶级会有 `3B=120` 次查找；`bind_stack_sets` 位于条目处理路径，调用数还取决于条目是否复用已绑定的 pipeline，不能固定为 40。条目需按其类型走直绘或回调，最多 200 个绘制记录入口。若其中 50 条确实选择 `indexed_indirect::draw_fn` 且列表索引为 0–49，它们使用的命令偏移是 `0,20,…,980` B，各记录一次计数 1 的 `draw_indirect`；这是指令步长的演算，**不是实测调用数、FPS 或总 GPU 字节流量**。复杂度随有效 bucket 数和条目数增长，另有 hash lookup、实例筛选、渲染图调度与 GPU 像素成本，不能由这一段反汇编给出时间常数。

**验证与未知。** 通过 PDB 符号范围、EXE 指令地址、相对调用目标和 `.rdata` 字符串回读核对上述桥；`render_world → main_pass → G-buffer raster → render_bucket` 与 `render_world → deferred_raster → Apply deferred lighting` 是已答的静态链。资源句柄逐字段同一性、墙类回调注册、图编译后的实际 pass 运行条件及 GPU/帧耗时为 **Not Run / 未证实**，因为本任务限静态研究。
