# 四款游戏：命令初始化、尾字段与相机目标续查

本轮承接[80 的具体静态断点](80-four-static-resource-acceptance.md)，优先追 Tiny Glade 槽 23 和沙堡末尾四字节，同时补掘地求财的材质到 section、SUMMERHOUSE 的外部相机目标。**四款均有新增静态证据；Tiny Glade 槽 23 的最终生产者和沙堡尾值的唯一字段名仍未闭合。** 游戏启动、附加、GPU/性能测试、玩家存档和截图写入均为 **Not Run**。

| 专题                                                                                | 本轮查清的连接                                                                                                                                                           | 仍不能下的结论                                                                                                                             |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| [Tiny Glade：命令初始化与槽 23](81-tiny-glade-command-initialization-and-slot23.md) | 同一 typed buffer 的空输入创建路径上传 460 B 全零，即 23 条 20 B 命令；另一路五字段模板经 CPU 绑定确认属于 NaniDrawListSsbo。阶段 3 槽 23 的选择和 payload 门已定位。    | 槽 23 要读 460–479 B，是否在提交前扩容、是否进入该提交，以及其最终模板/生产者均未知；不能定性为越界错误或保留槽。                          |
| [沙堡：PlayerSettings 尾字段](sandcastle/12-player-settings-tail-field.md)          | `03 00 00 00` 位于 class129 的 916 B 对象内；公开 Release 树消费 912 B。排除通用填充/对齐解释；原生字段登记函数也确认末项为四字节 allowedHttpConnections。               | 运行库字段登记不是构建资源的 writer；`+0x38c` 零与 `+0x390` 三仍有两种相容映射，不能唯一命名尾值。Linear 字段在更早位置独立定位。          |
| [掘地求财：材质到 section](digging-a-hole/10-terrain-material-to-sections.md)       | 区间判断包含起止端点；初始 LOD2 取基础材质、LOD3/4 取替代材质。追到弱引用缓存、普通材质包装、Mixed 可见 Clustered 分组和组件材质查询。                                   | 需实际 chunk 进入相应单材质支路；插件的多材质能力不能当作本场景结果。实际 LOD、动态覆盖与最终 shader 未观测。                              |
| [SUMMERHOUSE：遮罩与截图目标](summerhouse/11-mask-target-and-camera-overrides.md)   | 遮罩 Camera 经 external fileID2 接到 MaskingMap；2048²、Point/Clamp、mip 关闭，再发布为全局纹理。截图组件则绑定主相机，以 1024² 临时目标替换 target，正常返回设回 null。 | 原生 RenderTexture 默认标志和设备兼容格式未知。主相机空 target 的结论适用于普通配置，不能套用截图内部；没有执行 Camera.Render 或文件写入。 |

本轮最有价值的修正是把“初始状态”“后续生产”“提交条件”分开：Tiny Glade 的全零命令不能当作最终模板；沙堡读到对象尾也不等于字段映射完整；掘地求财的关卡配置要经真实区间和分组传到消费者；SUMMERHOUSE 的序列化相机状态还存在明确的截图切换分支。

## 可继续的静态工作与运行边界

Tiny Glade 下一个有效目标是把墙命令的四个非计数字段、通用/内联写入和后续 buffer 长度接到同一 typed key，或把非墙 shader 的 CPU 绑定接到确切绝对槽。仅增加同名资源清单不会解决槽 23。沙堡需要同一 Windows player build 的 class129 字段布局或原生序列化成员表来区分两个零/三值槽；公开示例配置只能提供候选。

掘地求财可进一步追 chunk 的材质模式和材质索引如何选择单/多材质分支；SUMMERHOUSE 可继续查原生 RenderTexture 构造默认值与遮罩 renderer 的完整物件覆盖。这些是尚可静态分析的方向，未伪装成必须运行才能回答。相机最终设备格式、真实提交、GPU 同步、像素和耗时则另属[运行验证用例](74-runtime-validation-cases.md)，本轮均未执行。

## 复核与交付范围

原始投影统一保存在 ignored `.cache/procedural-modeling/static-tail-followup/`，每篇列出输入身份、地址或对象偏移及新输出位置。只将新专题、必要的静态读取器和导航改动纳入交付；原发行代码/资产不进入自研实现，未新增分析软件。

已复核 native 定点指令、SPIR-V 边界、实例配置演算、托管 CIL/枚举常量，以及 SUMMERHOUSE 两个 Camera、目标 RenderTexture、两个 MonoBehaviour 和脚本身份的完整读取。SerializedFile 外部表扩展保持原默认索引各字段不变，三份实际文件 metadata 完整消费；错误版本、截断和输出覆盖的失败诊断已检查。本轮 12 份 Markdown 的 UTF-8、182 个相对链接、代码围栏与空白检查通过，3 份 Python 的 AST 解析通过，结果在 `static-tail-followup/document-validation.json`。没有把静态公式演算计作运行或性能通过。
