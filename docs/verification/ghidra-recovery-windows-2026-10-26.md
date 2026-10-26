# Windows Ghidra 恢复与单函数超时验证

日期：2026-10-26，Pacific Time。本记录与对应实现一起提交；验证期间未修改原始游戏或应用。

## 实现范围

- 启动超时提示区分 REA 启动环境、运行中的服务器配置和客户端工具调用期限。修改环境后需导出有用 Evidence、关闭目标并处理清理失败，再重启 REA、重连 MCP、重新打开目标。
- 新增可选 `REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS`：1–2,147,483 整秒，未设置仍无限制。上限来自 Ghidra 秒转有符号整数毫秒的实现。
- 反编译失败或超时后，函数资料保留汇编、引用、调用关系和 CFG，并标明伪代码、native API 和 p-code 不可用及原因。
- 部分结果继续保留为 Evidence，但禁止作为已完成的快照重放；该策略沿现有会话和 CLI/MCP 组合查询传递。调用方取消仍关闭会话，并保留并发失败及清理诊断。
- `rea setup` 仅转存显式选择的两个 Ghidra 超时设置；不复制其他环境变量、不安装默认值、不改客户端期限。

上游参考：[恢复提示 #5356](https://github.com/morluto/rea/pull/5356)、[失败资料 #4650](https://github.com/morluto/rea/pull/4650)、[单函数期限 #5662](https://github.com/morluto/rea/pull/5662)。按本 fork 的既有契约适配，没有整体合并上游，也没有引入 IL2CPP 或 Windows 句柄所有权更新。

## 边界复核

配置仍由现有环境解析器持有；Java bridge 持有原生反编译状态，结果解析器验证 bridge 的结构。现有 `AnalysisExecution` 携带仅限单次结果的 live 策略，现有快照写入者执行拒绝重放；没有第二个缓存或 Evidence 注册表。

Windows P0 的目标、私有数据库和修改权限保持现有范围。部分成功不吞取消或未知异常。原生期限只覆盖反编译阶段，不覆盖导入、汇编/CFG 收集、传输或整次批量查询。

## 本机验证

环境：Windows x64；Node 24.18.0 / npm 11.16.0；既有 Ghidra 12.1.4 / Temurin JDK 21.0.12.1。Windows 原生 addon 未改源码，复用已验证的 6.4.0 构建；测试 DLL 由本机 MSVC x64 新编译。未安装或升级分析引擎。

| 检查                                                   | 结果                                                                      |
| ------------------------------------------------------ | ------------------------------------------------------------------------- |
| 配置、结果解析、错误投影、取消竞争、快照重试、组合策略 | 7 个文件，182 项通过                                                      |
| MCP 部分资料/重试、全工具转换后 schema、客户端设置保留 | 3 个文件，29 项通过；provider seam 为受控替身                             |
| `scripts/windows.ps1 check`                            | 命令成功；核心 3,369 项通过；Windows 专项 950 项通过、34 项按平台条件跳过 |
| 门禁中的原生权限/进程、Inspector、打包、Python、文档   | 通过；打包验证包含 193 个工具、配置幂等、卸载和更新                       |
| 实际重复代码扫描                                       | 2,470 个文件，2.93%，保持原 3.5% 阈值及仓库内排除范围                     |
| 默认未设置函数期限的真实 Windows Ghidra 验证           | 26 个读操作通过；来源字节与文件偏移验证、provider 清理通过                |
| 新期限的真实 Windows Ghidra 验证                       | 下述自然超时、部分资料、原子错误、同会话后续调用通过                      |

真实期限验证入口：`npm run verify:ghidra:windows:timeout`。需要 VS x64 developer 环境与绝对 `REA_CC`，详情见 [Windows P0](../windows-ghidra-p0.md)。样本源码限定在一 MiB 内，生成 6,000 个独立分支，DLL 没有入口例程，也未被加载或执行。

最终自然超时运行 `6452de52-613d-4f03-a56f-93b42c91365c`：

- 原生反编译期限为 1 秒；完整 `analyze_function` 含资料收集耗时约 5.912 秒，不宣称工具调用在 1 秒内结束。
- 保留 138,006 行汇编、18,001 个基本块；不可用原因进入资料及上层 Evidence 限制；结果禁止快照重放。
- 原子伪代码请求返回 `provider_timeout`、`retryable: true`、`timeout_ms: 1000` 和 `decompile_timed_out`。
- 后续小函数成功；前后 bridge run ID 相同，目标字节逐字节相同，provider close 成功。

默认期限运行 `43cc125c-65af-473a-976f-201670a08429` 使用独立受控 PE，完成正常读操作与清理。whole-verifier 的通用 lineage 观察在 Windows 为 unavailable；不把它扩大声明为全宿主进程家族证明。provider 的 Job Object/运行目录清理按其现有 owner 验证。

## 失败与证据限制

- 首轮新增解析测试误用了 native API 不可用分支的字段；修正样本契约后通过，没有放宽生产解析器。
- 首轮 Windows 专项缺少隔离检出中的既有 `rea-windows-analysis.exe`；补齐同源受控样本后完整重跑通过。
- 初版新 verifier 的编译命令使用 `OwnedCommand` 时，编译器退出码为 0，但 Windows 输出收尾未在 120 秒内完成。该失败日志保留；verifier 改用仓库现有 `execFileOutput`，等待编译命令及其管道结束。未修改通用进程生命周期实现。
- 默认重复代码扫描受父目录 `.codex` 排除项影响，报告 0 个文件；该次结果为 Inconclusive。补充扫描仅将相同排除项锚定到仓库内，保持阈值、gitignore 和其余选项，实际覆盖量见上表。未改正式扫描配置。
- 未运行真实 Linux/macOS 引擎验证；没有游戏运行时验证，也没有通用速度提升结论。进程家族 CPU 和峰值内存未测量。自然期限和部分资料不是完整反编译能力保证。
- Hosted CI 单独绑定实际推送提交，由本任务最终交付链接报告；本记录不把本地结果当作 Hosted CI 结果。

本机完整日志位于该工作树 `.cache/ghidra-recovery-*` 和 `.cache/ghidra-timeout-windows-*`，属忽略产物，不随仓库分发。哈希流程沿用本次 owner 对构建、目标/bridge/profile/Evidence 身份及必要 Windows/MCP 验证的明确授权；未新增独立哈希工具。
