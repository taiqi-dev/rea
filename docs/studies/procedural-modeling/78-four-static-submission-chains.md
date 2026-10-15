# 四款游戏：提交、回调、格式与 LOD 顺序的静态续查

> 后续 [80](80-four-static-resource-acceptance.md)补碰撞最终接受门、命令基址与槽 16–22、沙堡 Linear 配置和低分辨率 mip/附件；槽 23 等明确缺口仍保留，下文是此前范围。

本轮按 [76](76-four-static-chain-answers.md) 的四个剩余入口继续，结果分成以下专题。**已接通的都是选定发行版本的代码/资源关系；游戏、附加、抓帧和性能测量全部 Not Run。** 没有读取个人存档或修改安装文件。

| 指定问题 / 阅读入口                                                              | 新增静态结论                                                                                                                                                             | 保留的边界                                                                                                                            |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| [掘地求财 08：Mixed 提交链](digging-a-hole/08-mixed-handler-submission-chain.md) | Mixed 按标记把可见网格送 Clustered、碰撞/导航送 Basic；Clustered 完成结果经活动槽、cluster 指针和序号门进入组件 section、材质与渲染更新，另有移除和短结果清理            | MainLevel 的初始选择条件沿用 07；具体 chunk flags、材质到各 section、上游令牌和本地序号的同源性、旧 collision cook 的最终接受门仍未证 |
| [Tiny Glade 77：墙绘制回调映射](77-tiny-glade-draw-callback-mapping.md)          | 墙注册 `indirect_draw_bricks`，两个机器字进入 64 B DrawListItem 的函数/payload 字段；render_bucket 调墙回调，经阶段与组筛选后尾跳 indexed_indirect，按 20 B 命令步长录制 | 尚未逐槽对齐 GPU 命令写入资源与索引 `0x10–0x17`；内部阶段字节的命名语义及运行可见性没有补成已知                                       |
| [沙堡 10：颜色格式来源](sandcastle/10-camera-color-format-selection.md)          | 静态字段来自 `SystemInfo.GetGraphicsFormat(DefaultFormat.HDR)`；A 颜色与 opaque 副本再按 activeColorSpace 经 sRGB/Linear 格式转换后申请                                  | HDR 是请求类别；具体 GraphicsFormat、位深、色彩空间分支和设备支持不能由此变成固定常量                                                 |
| [SUMMERHOUSE 09：LOD 写入交错](summerhouse/09-lod-writers-and-pass-order.md)     | 唯一 active feature 先入队，URP 传统路径稳定按事件排序；成功 copy300 写 0 后，到 back400 之间已追 pass 不写非零 LOD。反射图集可写非零 mip，但已追入口在 copy 前          | copy 跳过时没有本次重设保证；运行中的配置变动、未覆盖入口、有效 mip 与实际 GPU 结果仍未知                                             |

## 这轮改变了哪些判断

掘地求财的 Basic 提交链现在有了 **Mixed 的实际静态调用来源**：它承担碰撞/导航，而可见网格经 Clustered 合并。两支路的结果门与物理 cook 回调需要分开，不能用 renderer 的序号检查代替物理最终接受保证。

Tiny Glade 的墙条目不能直接标成通用 indexed_indirect 回调：中间的墙函数会按 payload 和阶段筛选。专题演算中，循环组 `i=1` 配阶段字节 3 选择索引 23、460 B 偏移；改成不匹配阶段则返回。这证明了回调筛选与命令寻址关系，没有证明 GPU 对应槽内的具体命令内容。

沙堡的颜色格式不是未找到的硬编码位深，而是已找到的**设备查询加条件转换**。这部分来源可以静态回答；查询结果本身仍是未知，不以常见 Unity 格式代填。

SUMMERHOUSE 从“所有 Blitter 都可能覆盖”收窄为**哪个调用实际位于当前两 pass 之间**。当前包内路径的 copy 成功时可推出 back 使用 0；仍保留 08 已证的共享状态结构，不能把条件式改写成所有帧的常量。

## 复核范围与后续静态窄点

本轮复用匹配 PDB、IL2CPP metadata/codegen 映射、已有资源解析器和有界反汇编；新增 CIL 读取器的显式类型通配/操作数过滤，保留实际 examined/decoded 覆盖。各专题列出函数地址、字段、token、配置输入与构造演算。原始投影在 ignored `.cache/procedural-modeling/static-submission-followup/`，正式文档和工具留在本研究目录。静态字段/分支核对、CIL 兼容及过滤/失败检查、构建、UTF-8、链接与空白检查通过。

仍可继续的静态问题已经具体到：Clustered 合并 helper 的几何操作与物理 cook 最终门、墙命令 buffer 的写入/读取逐槽身份、沙堡色彩空间资源的可靠 schema、SUMMERHOUSE 低分辨率目标的 mip/attachment 和主体 shader。它们与[74 的运行用例](74-runtime-validation-cases.md)分开；本次没有执行该清单。研究用于独立行为规格，不携带原作恢复代码、二进制或资产进入产品。
