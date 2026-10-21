# Tiny Glade：稳态帧的两轮筛选、深度与绘制提交

这次优先回答性能问题：**不编辑时，哪些渲染工作仍然存在，怎样避免把每片砖瓦变成独立 CPU 绘制。** 新证据接通了 `render_world` 中第一轮列表、主绘制、HZB、第二轮列表和 `OC/2` 绘制的编排，并读到 recorder 的状态写入。它支持“持久实例＋按视图筛选＋间接列表”的解释；没有测得原作 FPS，也不能据此诊断用户工程。

本篇承接 [70：更新成本](70-tiny-glade-update-and-render-costs.md)、[72：CPU 绘制](72-tiny-glade-cpu-render-bindings-and-lifecycle.md)、[49：屋瓦可见性](49-tiny-glade-roof-gpu-visibility-and-depth.md)和 [112：实例池到绑定](112-tiny-glade-external-pool-producers-and-draw-bindings.md)。与上一轮 [114](114-four-game-performance-mechanisms-and-demo-priorities.md)的综合整理不同，这里新增当前制品的调用、分支、字符串和 shader 读取。

## 输入、工具与覆盖

目标为 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`，65,612,184 B，preferred image base `0x140000000`。本轮 REA `open_binary` 返回 PE/x86_64、SHA-256 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`，与既有身份相同；沿用本次调查摘要授权。相邻 PDB 的本地查询完整结束，`render_world` 范围为 `0x1400F9F00` 起 13,437 B，`main_pass_oc2` 为 `0x1409ABE20` 起 1,524 B。

使用现有 VS `dumpbin 14.44.35222.0`、[PDB 查询器](digging-a-hole/tools/pdb_probe.py)、[地址查询器](tiny-glade/tools/pdb_address_probe.py)和新增只读 [steady_render_probe.py](tiny-glade/tools/steady_render_probe.py)。包内 `compiled-shaders/country-core/compiled/nani/cull_and_bucket_roof_tile.precomp` 45,431 B 由现有 [SPIR-V 结构读取器](tools/spirv_probe.py)重新读取，三个模块完整解码、无候选拒绝；这不是语义验证或 GPU 执行。

新普通原文位于 ignored `.cache/procedural-modeling/steady-performance-followup/tiny-glade/`，包括 `render-world-current.txt`、`main-oc2-current.txt`、`oc2-gbuffer-graph-current.txt`、`bucket-current.txt`、`prebuilt-pipeline-corrected.txt`、`bind-stack-corrected.txt`、PDB JSON、`roof-cull-current.json/.txt` 及 `steady-render-anchors.json`。这些 **不是 REA Evidence**。REA 的 `inspect_binary_layout` 本次明确返回 `capability_unavailable`：该 profile 只支持 Linux x64；未把失败当作成功，也未安装替代工具。既有 Ghidra 深度分析超时前提未改变，未重试。身份打开本身没有生成新 Evidence ID。

## 两轮主视图工作接到了同一个入口

以下是 `render_world` 内选定正常资源路径的**CPU 调用顺序**，不是已观测的 GPU 时间线：

| 阶段         | 当前指令与实参                                                                                     | 性能含义及限制                                                           |
| ------------ | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 收集墙批次   | `0x1400FA5F2 → gather_wall_draw_batches`                                                           | 收集列表与砖的几何重建是不同工作。                                       |
| 第一轮列表   | `0x1400FA6FB → generate_wall_draw_lists`；`0x1400FA7A1 → gpu_generate_draw_lists`                  | 通用入口此处 `r8=0, r9d=0`，第五参数为 0；不能因没有编辑就推断不执行。   |
| 第一轮主绘制 | `0x1400FABCD → main_pass`                                                                          | 既有 G-buffer graph 专门化在 `0x1417557A8` 调 `render_bucket`。          |
| 构建 HZB     | `0x1400FABEC → generate_hzb`                                                                       | 字面 scope `Generate HZB` 已从 PE 回读；准备层级深度也有成本。           |
| 第二轮列表   | `0x1400FACAE → generate_wall_draw_lists_pass2`；`0x1400FAD62 → gpu_generate_draw_lists`            | 此处 `r8` 指向前述 HZB 返回局部记录，`r9d=1`，第五参数仍为 0。           |
| 第二轮主绘制 | `0x1400FAF8F → main_pass_oc2`                                                                      | 该入口确实注册后述 raster pass，而非仅存在同名符号。                     |
| 阴影视图另算 | `0x1400FB585 → generate_hzb`，`0x1400FB5F3 → wall_shadow`，`0x1400FB6A1 → gpu_generate_draw_lists` | 通用入口使用 `iter_shadow`、第五参数 1；主视图筛选不能自动免除阴影成本。 |

第二轮通用入口传入的 HZB 局部记录来自 `0x1400FABD8` 指定的 `[rbp+0x560]` 返回位置，`0x1400FAD4F` 再以同一地址传入。这是同一 CPU 记录的传递；完整物理纹理与最终 descriptor 身份仍没有逐项恢复。

`0x1400FABF2–0x1400FABFC` 读取导入符号 `FREEZE_OCCLUSION_CULLING`，非零跳到 `0x1400FADDA`，越过第二轮列表生成区间。它**不跳过前面的 HZB，也没有直接跳过后面的全部 OC/2 绘制**。该开关当前实际值、初始化与运行用途未知，不能把它当“静止自动休眠”。`wall_pass2` 自身还保留 [70](70-tiny-glade-update-and-render-costs.md)已见资源存在门；本轮没有把资源查询失败和空场景都解释成相机没动。

`main_pass_oc2` 的五个 raster 标签已按显式长度从当前 `.rdata` 读取：`G-buffer OC/2`、`G-buffer emissive OC/2`、`G-buffer velocity OC/2`、`Forward OC/2`、`Velocity OC/2`。其中 `0x1409AC0C1 → 0x141758190` 是 G-buffer 专门化；其 `0x14175835E` 再直接进入同一个 `render_bucket`。标签数量不等于实际每帧 GPU pass 数，render graph 仍有资源、依赖和执行条件。

通用列表入口保存 `r9d` 后，在 `0x1409B876D–0x1409B8789` 将两个参数映成区段偏移：主第一轮为 0，主第二轮为 `0x220`，阴影参数非零则为 `0x440`；后续捕获的 span 为 `0x220`。这是 CPU 回调记录的区段选择，**不是 544 条 draw，也不能除以 20 B 来推绘制数**。真实间接命令结构及 mesh/instance 聚合另见 [108](108-tiny-glade-distance-meta-consumers-and-draw-budget.md)。

## 前后可见位怎样减少第二轮重复追加

当前三个屋瓦 compute 模块起点为文件偏移 `208 / 10981 / 24642`，local size 均为 64。重新读取保留了 [49](49-tiny-glade-roof-gpu-visibility-and-depth.md)的两种主视图职责，同时补核了第一轮也写下一份可见位：

| 模块       | 当前文件锚点                                                                                               | 已确认职责                                                                                                                        |
| ---------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 第一主模块 | `0x2074–0x212C` 的 prev 位读取与分支；`0x2164–0x21A4` 的 next 地址链及 AtomicOr                            | 不读取 HZB。通过资格与先前可见位选择的实例写 next 位，再追加 filtered/meta/直方图。完整资格还有其他分支，不能简化为只看一个 bit。 |
| 第二主模块 | 四处 ImageFetch：`0x52B1/0x5361/0x5411/0x54AD`；`0x562D–0x566D` 写 next 位；`0x5689–0x56F5` 查 prev 并取反 | 当前通过 HZB/资格门后写 next 位；先前不可见才走后面的列表追加。可见位写入与本轮新增绘制条目分开。                                 |
| 太阳模块   | 12 个 ImageFetch，分别服务三个 layer                                                                       | 独立阴影视图候选；不能把主镜头筛掉的实例直接从所有阴影工作中删除。                                                                |

这些 shader 数据流与 CPU 的“两轮主绘制、中间建立 HZB”相互支持。**仍只属部分接通**：具体 shader permutation 到每一个 CPU binder、prev/next 物理 buffer 的跨帧交换、清空及失效全部写者没有在本篇闭合；不能据此保证切镜头、读档、冻结开关变化后的所有时序正确。

构造演算（非游戏样本）：设三个候选 A/B/C 均通过其它资格，prev 位只有 A/B。第一模块的选定 prev 分支追加 A/B；第二模块假定 HZB 保留 A/C，则 A 写可见位但不在这里重复追加，C 才新增。两处合计三个追加，不能将“第二次也 visible”算成 A 又增加一次。B 的先前列表是否仍提交、最终是否通过深度测试，需保留 raster/列表与像素层的区别；本例没有证明全帧实际三次 draw，也没模拟跨帧位交换。

## 分桶和实例化不等于免费绑定

`render_bucket` 处理的是 64 B 条目（`0x140AF509A` 前进 `0x40`），每项可选回调或普通 draw；[112](112-tiny-glade-external-pool-producers-and-draw-bindings.md)已把 RoofTile 的 coarse 分支接到实例列表与间接绘制。这使“一个实例记录”不必对应一个 CPU 对象及一次单独提交，但**桶本身仍遍历条目**。

新向下读取发现：`0x140AF51B9` 调的 `prebuilt_pipeline 0x140E21920` 只是取 handle 并尾跳 `set_pipeline_impl 0x140E21930`。所选成功尾段在 `0x140E21AA4` 保存 handle，并在 `0x140E21AA8` 将 recorder `+0x288` 与 `0x10001` 做 OR。`bind_stack_sets 0x140E24E00` 则解析 stack 索引、按 layout 找位置、核边界，最后写绑定记录并置 `0x20` 位。两者是记录层状态更新，不能把函数调用存在直接当作一条 Vulkan 驱动调用，也不能凭“prebuilt”声称同 pipeline 条目之间已省略所有重复绑定。

本轮因此没有升级 [72](72-tiny-glade-cpu-render-bindings-and-lifecycle.md)的复用假设为固定绑定次数：GPU 命令发射前是否进一步比较状态、每帧有多少非空桶/条目、细/粗列表的选择及实际调用数仍未知。追下层发射只在未来确实需要解释提交热点时有价值，不必为了综合 demo 完整重做原作的 recorder。

## 对综合 demo 的价值与停止边界

优先借鉴三层分离：编辑只使相关建筑/空间块的持久实例失效；渲染按视图选择这些实例；材质、网格和提交以可共享批次组织。没有编辑时应避免重造几何，却仍要支付所选视图的筛选、阴影、片元和后处理成本。将这几项分开统计，才能区分生成性能与稳态渲染性能；这里只提出独立设计原则，未读取或适配 `3DSandboxTest`。

两轮 HZB 是有附加筛选、深度图构建和同步关系的方案。首版小场景可先保持简单视锥/距离分级与批量实例；只有测量表明遮挡/提交规模值得，才实现相应复杂链。不能由本篇推“照搬后会从 10 FPS 到某个数”，也不能据静态支路判 CPU 或 GPU 谁更慢。

**Answered（静态）**：两轮主调用顺序及实参、freeze 局部门、OC/2 raster 到桶、列表区段选择、两主 shader 的 prev/next 读写区别、recorder 状态写入。**Partial**：shader 与 CPU permutation/资源的最终一一对应、全部跨帧交换和失效。**Unknown**：实际开关、活动实例/命令数、线程/GPU时间、吞吐与视觉收益。新探针核 17 个相对调用、13 个指令锚点、1 个分支和 6 个字符串；运行频率、游戏/Unity/目标函数/GPU、Profiler、私人存档及 Ghidra 深度重试全部 **Not Run**。
