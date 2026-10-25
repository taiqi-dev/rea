# Tiny Glade：景深焦点、近远模糊与开关位置

后续 [163](163-tiny-glade-autofocus-parameter-producers.md) 已接回五个实际资源类型、当前相机的 focus/lens 选择表，以及配置点/光标/锁定/光圈/tilt-shift 的 CPU 来源；[165](165-tiny-glade-scene-depth-to-focus-and-coc.md) 补深度附件到两个消费者的记录身份。全部 UI 写端、图版本与 GPU 结果仍保留未知，下文为本轮原始范围。

2026-10-24，America/Los_Angeles。承接用户在「Supervisor｜小屋美化与未完事项」提出的新调查：镜头贴近物体时的景深是否与树木局部透明互斥。树的证据和两效果关系见 [162](162-tiny-glade-tree-see-through-and-dof-composition.md)。本项当前只授权先调研，不据此启动 Unity 制作或运行验证。

## 先回答“特别近才触发吗”

**所选景深程序按照焦点区间和每个像素的深度连续计算，近侧和远侧都能产生模糊；不是发现近处物体后才按对象类别打开景深。** 全局是否执行最终景深处理另有配置门。焦点落在哪里、是否锁定与 tilt-shift 也会改变画面，不能仅用相机到最近物体的一个固定距离解释。

已读指定 `codex-clipboard-26e38645-857e-4ad1-a749-df688b2c50a8.png`：近处塔墙占据前景，远处树景明显虚化。该单图不能确定焦点数值、焦点如何取得，或树的哪一部分已被渐隐。图上版号 v1.16.5a；未证明其构建与本机二进制完全相同。

本轮输入仍是 `C:/Software/Steam/steamapps/common/Tiny Glade` 的 65,612,184 B EXE 和匹配 PDB，GUID/age 沿 [153](153-tiny-glade-ground-startup-grid-and-background-seams.md)。延续原有界静态 fallback：PDB、dumpbin、现有 SPIR-V reader；不启动游戏、附加进程、取私人保存或导出美术资产。上一轮 REA native 分析超时且无保留 Evidence，没有前提变化便不重复同类长等待；本篇新结果是普通静态证据，不是新 REA Evidence。

## 自动焦点：深度采样、双焦点和锁定

本轮重新解析 `country-core/compiled/dof/calc_autofocus.precomp`：偏移 108、4,387 words，8×8×1 compute。它实际读取 `depth_tex`、`current_view`、当前 camera 索引的 `DofAutofocus`，以及下列参数：

| 参数/状态                                  | 已核职责                                                                                         | 仍未知                                                        |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| point_uv、focus_box_height、depth_tex_dims | `w2261–2348` 用焦点区域参数生成屏幕采样坐标并取深度；后面还有另一组区域采样                      | 默认区域大小、point_uv 是否随鼠标/选择目标改变的全部 CPU 写端 |
| use_dual_focus                             | 实际参数访问及条件路径；有 focus0/focus1 两组共享距离工作区                                      | 所有模式使用何种统计分位和完整退化处理                        |
| focus_lock_request、focus_is_locked        | 实际参与自动焦点计算，另有锁点世界位置与读回结果                                                 | 所有用户输入、锁定恢复与模式切换映射                          |
| use_tilt_shift、aperture_size              | 实际参数访问，焦点状态另含 focus_scale                                                           | 所有设备/画质默认值和每个模式的确切数值                       |
| 焦点状态                                   | focus0、focus1、lock_bias0/1、lock_pos_ws、interp_lock_pos_ws、interp_lock_bias0/1、is_locked 等 | 所有时间插值与首帧初始化分支的等价算法                        |

这里可以确认焦点不是只从“对象类型=树”得到的开关。参数中有插值/锁定状态也不等于已经证明一套进入/退出双阈值的空间滞回，不能用字段名替代实际算法。

## 近侧和远侧的带符号 CoC

`country-core/compiled/dof/prepare.precomp`（偏移 94、2,529 words）重新复核 [69](69-tiny-glade-shading-lighting-and-contact.md) 的实际指令。它从像素深度重建位置，并读取 focus0/1、use_tilt_shift、focus_scale。先定义两个倒数焦点阈值：

```text
a = 1/focus0, b = 1/focus1
U = max(.001, max(a,b)) + .00001
L = max(.001, min(a,b)) - .00001
δ = min(.01, .05*(U-L))
r = 1/max(1e-10, projected_distance)
```

`w2226` 的 GLSL.std.450 操作是 **FMin**。因此 δ 是取较小者，旧 69 中“至少 .01”已更正；本轮没有把旧说明继续当作新证据。

`w2233–2333` 的响应 q 是三段连续表达：

- r>U：q=r-U+δ。
- r<L：q=r-L-δ。
- 其间：q=-δ+2δ*(r-L)/(U-L)。

随后 `w2385` **先取负号**，再乘 focus_scale、投影矩阵的 `[1][1]` 和垂直尺寸 `H/720`。在普通投影距离、正尺度的前提下，近侧 r 较大产生负 CoC，远侧产生正 CoC；焦点区间中部接近零，不是整段都严格零。tilt-shift 另改变投影距离和响应尺度，不可以把它替换成单一世界欧氏距离。

每线程另计算 `min(H/24, abs(CoC))` 参与 tile 的 min/max 聚合；写像素 `coc_out_tex` 时仍保留符号。这个 tile 上限不能直接说成像素输出也已经被同样钳住。

**构造例，非运行。** 假设 focus0=10、focus1=20、projected_distance 分别为 5 和 40，则 U≈.10001、L≈.04999、δ≈.002501；q 分别约 .102491 与 -.027491。忽略 tilt-shift 并令最终正尺度为 1，CoC 分别约 -.102491 和 +.027491。它展示近远两侧的符号，不预测实际截图的半径或清晰度。

## CPU 入口、最终开关与成本边界

PDB 与实际 E8 调用把三段接到同一个 `tiny_glade::render_loop::render_world`：

| 调用点 preferred VA | 实际目标                             | 已确认职责                       |
| ------------------- | ------------------------------------ | -------------------------------- |
| 0x1400FBC1B         | calculate_dof_autofocus，0x140B38410 | 自动焦点 compute 的资源/节点构建 |
| 0x1400FC598         | dof_prepare，0x140B04C70             | CoC 与 tile 信息的准备节点       |
| 0x1400FC6F5         | render_dof_with_coc，0x140CD3700     | rhapsody_dof 后续处理节点        |

最终处理前 `0x1400FC6A8–0x1400FC6B0` 检查所取配置的一个索引 bool，为零则跳到 `0x1400FC71D` 传递未经过这一景深处理的图像记录。该 raw 配置索引的完整模式名尚未接通；不能猜成某个特定 UI 选项或相机类别。

这一门检查发生在上述 prepare 调用之后，所以“跳过最终处理”本身不能证明此前没有焦点/CoC 准备成本。`render_dof_with_coc` 中还存在 analyze、halfres、fullres 及 indirect dispatch 变体；完整 tile 分类、资源句柄同一性、最终合成/GPU 执行顺序没有全部恢复。内部名称里的 lod0/1 不足以证明与树几何 LOD 同义。

对我方有用的独立取舍：景深采用自己的正式焦点目标/锁定、可控近远强度、设置开关和预算；明确关闭时哪些准备也能跳过。不要给每个场景物件挂一个“靠近就开启景深”的竞争脚本，或为追求柔和画面把 UI 一起模糊。具体管线和实施范围由项目当前 owner 决定，本轮只交研究候选。

## 证据与未知

复核器 [dof_tree_probe.py](tiny-glade/tools/dof_tree_probe.py) 对当前输入读取 5 个文件内的 14 个模块、校验所选指令/CPU 调用/写端；完整原始记录在 ignored `.cache/procedural-modeling/tiny-dof-tree/`。解析通过仅表示所选模块的 framing/指令边界和锚点匹配，不是 GPU 或全 SPIR-V 语义验证。

仍未知：全部 autofocus CPU 生产者/默认值、精确焦点跟随与锁定时序、完整合成和每个材料到景深深度图的最终绑定。游戏、GPU、Unity、画面与帧时验证均 **Not Run**。
