# Tiny Glade 屋瓦、木墙、稳定随机与陆地植被：第十一轮账本

本轮对应用户授权的四个方向：屋瓦与复杂屋顶接缝、普通木墙板、稳定随机/局部重建、陆地植被。正式阅读路线：

- 屋瓦：[41布局](41-tiny-glade-roof-tile-layout-and-clipping.md) → [42裁平面](42-tiny-glade-roof-edge-planes-and-seams.md)。
- 木墙：[43板条布局](43-tiny-glade-wooden-wall-board-layout.md)。
- 更新：[44稳定随机](44-tiny-glade-stable-randomness.md) → [45发布与重建](45-tiny-glade-shared-invalidation-and-rebuild.md)。
- 植被：[46候选与排除](46-tiny-glade-land-vegetation-and-exclusions.md)。

研究起始本机时间为 **2026-10-12 22:49:43 PDT（America/Los_Angeles）**，由本机时间命令取得。不同UTC日期不作为本地版本或调查日期依据。

## 1. 目标及权限范围

固定输入仍为 `E:/Steam/steamapps/common/Tiny Glade` 的同一发行版：

| 制品 | 字节数 | SHA256 |
| --- | --- | --- |
| tiny-glade.exe | 65,612,184 | `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5` |
| tiny_glade.pdb | 310,513,664 | `ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2` |

GUID=`d8d61d04-9e31-5b47-4c4c-44205044422e`、age=1匹配；首选image base=`0x140000000`。CPU用RVA，shader用precomp文件偏移；地址转换按实际PE节表。

REA MCP未连接、本地CLI缺少编译运行文件的阻塞未变化。本轮沿既有DbgHelp/Capstone5.0.3/SPIR-V静态备用流程，没有运行REA provider、创建REA Evidence ID或虚构session。没有因为缺原生反编译就以符号名补算法；静态线性解码与实际语义恢复分别统计。

仅修改研究文档和索引，游戏原文件保持只读。未启动/附加、未读取私人存档、未改内存、未安装/构建/修配置或执行Git写操作。并行研究分工由已读取的reverse-engineer-anything技能“Plan broader investigations”第6项支持；各组独立保存范围和未知，正式说明由根任务整合。

## 2. 四个方向的回答程度

| 方向 | 已确认 | 部分/未回答 |
| --- | --- | --- |
| 屋瓦铺排与屋顶接缝 | 矩形/圆形实际writer，64B实例对应；圆环分层/计数/旋转；同屋顶边平面生产、选择、压缩和GPU判定；先清旧 | 全姿态、原网格/末排/屋脊拓扑、建筑间roof-roof/wall-roof裁切与完整上传 |
| 普通木墙板 | 粗差集与精细列表分流、16轮扫描；方向选择、均分、递归切板、窄板合并；扩展墙空间/采样器；直/曲输出 | 完整35KB ctor样式/noise/上缘树、尺寸上限来源及所有坡屋顶query |
| 稳定随机与局部重建 | 墙ID混种子；行/区域/端点混合；屋瓦RNG零初态及counter；WorldRaster内容hash过滤、staging及发布；既有对象级缓存清理职责 | 每墙值完整来源、全操作/存档稳定性、统一scheduler、异步旧结果/GPU同步 |
| 陆地植被 | 花园/建筑bush与flower实际绑定、候选/值噪声/资格/尺寸/贴地；草位置序列及双通道mask；预置树转换；独立样本发布 | 全树/森林算法、活动列表/远草层级、旧实例清理和局部补种时间链、负转换设备行为 |

“部分回答”表示保留了重要具体未知，不以文件数或完整字节解码宣称全模块恢复。每个方向已有来源和构造演算。

## 3. 新证据纠正的旧解释

1. 第17篇曾把精细窗口映射直接接到粗板差集。本轮确认粗差集经FinalizedWallHoles及拱洞范围，精细列表另行构造，正文和20账本已同步修正。
2. 第17篇的14530C0真实builder为CurvedHalfTimber.new_curved_xy。共享setter/grow_one和80B大小不能证明直木板格式，已保留两类消费者。
3. 木板差集的0x10为16轮完整扫描，不是cut项数或窗数量。早期本轮草稿读成前16项，已被tail控制流否证；正式43保留正确循环。
4. 屋瓦非默认plane来自本屋顶分片边界，不能据此宣称建筑间裁切已经恢复。RT空间记录w分量也不能按普通Mat4解释。
5. 木板seed的float位模式零扩展u64后做64位乘/XOR，不能截成32位；正式44已校正。

旧轮检查计数保留当时范围。本轮对当前文档与新增证据另做复核，不把新范围冒称旧轮原有覆盖。

## 4. 关键定位与实际桥

| RVA/文件 | 本轮用途 |
| --- | --- |
| `1F46490 / 1F4A6C0` | 屋瓦装配入口与实际清旧 |
| `2812C70 / 2816BA0` | 矩形与圆形装配 |
| `2816720 / 2817E20 / 1F49FD0` | 输出闭包与64B专用writer |
| `2814752–2815599` | 本屋顶边界plane生产/选择/half写入 |
| `280E580 / 2808770 / FC5E70` | 有界续查空间/底板职责，未补通建筑间plane |
| `144A4C0 / 1484310 / 1484710` | 木墙入口、粗cut重映射与循环差集 |
| `14887E0 / 14871B0 / 14882C0 / 1488BE0` | 均分、方向、长向切分、窄横板合并 |
| `1483D90 / 1483E90 / 1483630 / 1483090 / 1483320` | 扩展墙坐标、重映射、采样与切线 |
| `8096B9–8096DA` | 普通墙身份混seed |
| `A02200 / 905940 / A78AE0 / A84210` | staging入口、tile内容hash过滤与发布 |
| `9AE210 / B32850` | garden/建筑周边植被真实管线选择 |
| `B20F60 / C24F90 / B22B40` | 草相关CPU入口，具体行为按已恢复消费者限定 |
| `A32F00 / A85430 / B325D0` | 预置树、样本发布和灌木中心读回 |
| roof/garden/grass所选precomp | 字段布局、候选/资格/变形消费者 |

PDB源行路径仅定位，不表示取得开发者私有源码。函数同址alias、半径类字段、raw枚举与shader名称都需实际调用/指令佐证。

## 5. 原始记录位置

统一可再生成产物根目录：

`C:/Users/81553/.codex/visualizations/2026/10/12/01a12f36-6ef5-7a13-a524-0ffafe4443f7`

| 子目录/文件 | 内容 |
| --- | --- |
| `tinyglade-symbols/identity.json` | 原制品身份及PE节表 |
| `tinyglade-roof-tiles-layout/findings.md/json` | 24范围的原屋瓦记录、shader对应、公式与未知 |
| `tinyglade-roof-tiles-layout/bounded-followup.md/json` | 独立追加3范围空间/底板记录；原冻结报告未覆盖 |
| `tinyglade-wooden-wall-layout/findings.md/json` | 31新范围及复用外层/RNG，raw-ranges原字节、布局/合并/采样证据 |
| `tinyglade-stability-rebuild/` | 范围清单、12段细证据、墙seed与WorldRaster发布记录；复用同身份外层/Public producer |
| `tinyglade-land-vegetation/findings.md/json` | 22native清单、8native细范围、23SPIR-V细范围和构造例 |
| `tinyglade-land-vegetation/shaders/summary.json` | 9文件17模块的身份与格式记录 |
| `four-systems-validation.json` | 根任务独立复核的最终结果 |

正式交付是本目录的解释和规格，不包含恢复源代码或原游戏资产作为生产实现。临时原字节/解码用于本机研究，可再生成；不把这些产物当跨机器正式工具。

## 6. 复核方法与局限

独立重读EXE/PDB整文件摘要；按RVA去重native范围并新解码；核原字节、长度、文件偏移和重复一致性。shader核原文件、内嵌module摘要、word count及指令边界；细证据另核范围摘要与对齐。构造演算验证正常输入的算术与状态步骤，不调用发行版函数。

文档检查包括UTF-8、围栏、当前相对链接及各专题例子。交叉复核已检查屋瓦/plane、木墙/seed、植被关键公式，修正过强解释。整体byte覆盖不等于所有字段、分支或布局都已恢复。

最终独立验证：**612项通过，0失败**。当前49份Markdown、265个相对链接均有效；93个不同RVA的native范围，共198,840字节，摘要及新线性解码一致。10个shader文件、21个内嵌模块摘要/word count/边界一致，结构遍历20,016条SPIR-V指令；另核20段native细证据、23段shader细证据，以及31个木墙原字节块。SPIR-V结构遍历聚合成每模块检查，不冒充20,016项算法测试。

| 组 | 组内去重范围 | 字节 |
| --- | --- | --- |
| 屋瓦及有界空间/底板续查 | 27 | 33,243 |
| 木墙板，含复用外层/RNG | 33 | 92,437 |
| 稳定性与staging发布，含复用外层/Public producer | 14 | 64,279 |
| 陆地植被 | 22 | 31,165 |

各组有共享范围，直接相加不等于93或198,840。shader中1个屋瓦文件/4模块复用旧对应，9个植被文件/17模块为本专题选定输入；全部在最终复核时重读原字节。

算例按实数解释规则；float32的round/ceil、相等、half压缩以及GPU设备转换可能造成门槛差异。未运行shader语义验证器或实机重放。

## 7. 未做及剩余风险

未做：游戏启动/附加、真实交叠/编辑/补种场景、GPU抓帧/同步观察、原资产提取为交付、REA生产构建与项目测试。此次仅研究文档，没修改REA生产行为，因此不增加项目实现测试。

风险：建筑间屋顶裁切与统一重建时序仍未恢复；32位tile hash会有碰撞空间；种子身份/序列/浮点表示不能互代；花第二候选的负值无符号转换未建立设备语义；树全系统和植被旧产物清理仍部分回答。下一步若需提升这些结论，应分别追完整消费者/注册关系或选最小运行场景，而不是重复已确认的局部公式。
