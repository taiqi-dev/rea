# Windows 安装与验收（供另一台电脑的 AI Agent 使用）

目标：在当前 Windows x64 电脑安装这个源码仓库的依赖、构建原生模块，完成本机验收，并让 GitHub Desktop 能正常提交、拉取和推送。

先读当前电脑适用的全局指令和本仓库 [AGENTS.md](AGENTS.md)。本文是操作入口；工具版本以 `.nvmrc` 和 `package.json#packageManager` 为准，执行行为以 [安装脚本](scripts/windows.ps1) 和 [Windows 验收脚本](scripts/check-windows.mjs) 为准。不要从旧聊天记录复制版本号或已通过的结果。

## 1. 确认仓库与本机条件

在这台电脑已有的 REA 仓库根目录执行，路径不必与第一台电脑相同：

```powershell
git rev-parse --show-toplevel
git status --short --branch
git remote -v
```

- 仓库应是 `taiqi-dev/rea`，`origin` 应指向 `https://github.com/taiqi-dev/rea.git` 或对应 SSH 地址。
- 这是独立维护的 Windows fork。只从自己的 `origin` 拉取和推送，不使用 Sync fork，不合并或抓取原始 `morluto/rea` 仓库。
- 复用已有检出，不重新 clone 整个项目。若路径、远端身份不符，或有未处理的本地改动、冲突，先报告具体情况；不要覆盖、清理或重置它们。
- 需要 Windows x64、Windows 自带 PowerShell 5.1 或更高版本、Git 或 GitHub Desktop、Python 3，以及带 Windows SDK 的 Visual Studio C++ x64 工具。无需先安装全局 Node/npm。
- 如果 `git` 不在终端路径中，可使用 GitHub Desktop 自带 Git 做只读预检；安装脚本也会自动发现它。不要因此修改全局 PATH。
- 缺少编译器、SDK 或 Python 时，报告缺失项和安装目标，按用户现有授权处理；本文不额外授权安装系统软件或修改系统策略。沿用有效的依赖安装与既有完整性校验授权；若本机规则要求而当前授权确实缺失，再说明具体缺口。

已有仓库的当前分支为 `main` 且工作区干净时，先快进拉取：

```powershell
git -c submodule.recurse=false pull --ff-only origin main
```

这里暂不递归进入子模块，以便旧检出先拿到新的 Windows 安装脚本。若当前分支不是 `main`，先确认用户要安装的分支，再使用对应分支拉取；不要擅自切换或合并分叉历史。

## 2. 安装并运行本机完整 Windows 验收

在仓库根目录依次执行，每一步必须返回退出码 0：

```powershell
powershell.exe -NoProfile -File scripts/windows.ps1 setup
if ($LASTEXITCODE -ne 0) { throw 'Windows setup failed; inspect its output before continuing.' }
powershell.exe -NoProfile -File scripts/windows.ps1 check
if ($LASTEXITCODE -ne 0) { throw 'Windows acceptance failed; retain the failing output.' }
```

`setup` 会在项目缓存内准备固定版本 Node/npm，安装锁定依赖，备份并配置本仓库 Git 设置，安装提交/推送 hooks，用现有 MSVC 构建 Windows 原生模块与验证夹具，再构建 CLI/MCP 运行产物。它不会修改全局 Node/npm，也不会安装 Java、Ghidra、IDA 或其他分析引擎。

`check` 会检查源码、类型、lint、依赖及元数据，运行核心/服务测试和 Windows 能力测试，实际验证原生文件系统/进程边界、子模块同步回归、打包后的 CLI/MCP、Python 辅助测试和文档等。不要用一次构建成功替代这一步。

### 2.1 配好 Ghidra、Java 和当前 Codex

用户要求完整分析环境时，开发依赖安装后还必须完成本节。源码开发环境检查通过，不代表分析引擎或当前 AI 接入已就绪。

```powershell
powershell.exe -NoProfile -File scripts/windows.ps1 analysis-setup
if ($LASTEXITCODE -ne 0) { throw 'Ghidra/JDK setup failed.' }
powershell.exe -NoProfile -File scripts/windows.ps1 rea setup --client codex --dry-run --json
```

`analysis-setup` 是明确选择的源码安装步骤：从 NSA Ghidra 和 Eclipse Adoptium 官方发布地址准备脚本固定版本的 Ghidra、64 位完整 JDK。工具解压到 `.cache/windows-analysis-tools/`，不安装 MSI、不改系统 PATH；已有 `GHIDRA_INSTALL_DIR` / `JAVA_HOME` 选择优先保留并验证，不静默替换不兼容的用户安装。`.cache/windows-analysis-tools/environment.json` 是本机默认路径记录，后续 `scripts/windows.ps1` 命令会自动加载。不要把另一台电脑的绝对路径或缓存复制过来。

检查 dry-run 的实际计划：应仅为当前 Codex 增加本仓库 CLI 的 MCP 注册、Ghidra/JDK 路径和 REA skill，并保留其他配置。配置和 skill 的实际目标由该机客户端位置解析器决定，不要手工复制第一台电脑的 `config.toml`。沿用用户配置 Codex 的有效授权，确认计划符合授权后应用：

```powershell
powershell.exe -NoProfile -File scripts/windows.ps1 rea setup --client codex --yes --json
if ($LASTEXITCODE -ne 0) { throw 'Codex registration failed.' }
powershell.exe -NoProfile -File scripts/windows.ps1 rea doctor --client codex --provider ghidra --skill --json
if ($LASTEXITCODE -ne 0) { throw 'Codex/Ghidra readiness failed.' }
powershell.exe -NoProfile -File scripts/windows.ps1 verify-analysis
if ($LASTEXITCODE -ne 0) { throw 'Real program analysis failed.' }
```

作用域自检应返回 `healthy: true`。未配置的 IDA、Windows 不支持的 Hopper 等可能使全局 `environment_healthy` 为 false；应按所选 Codex/Ghidra 范围判断，不安装无关引擎来凑全局绿色。

`verify-analysis` 会用本机 MSVC 编译仓库自有的 [C++ 样例](tests/fixtures/windows/analysisSample.cc)，实际运行两个分支，再通过 CLI 和当前 Codex 配置中的真实 MCP 启动命令调用 Ghidra。它核对反编译、导出函数、调用关系、内存与文件字节对应、快照关闭/重开、源文件未改变和最终关闭状态。输出证据保存在 `.cache/windows-analysis-proof/` 的独立运行目录，不能提交到 Git。它不扫描或执行用户其他软件。

当前 Codex 若尚未加载新增 REA 工具，按其客户端支持的方式重新加载或重启后，调用 `binary_session` 核对 `server_identity.alignment.state` 为 `aligned`，再对上述自有样例完成一次 `open_binary`、`procedure_pseudo_code` 和 `close_binary`；不要仅凭工具目录包含 193 个名字就声称真实分析可用。

出错时保留命令、退出码及关键日志，先分类根因再修复。不要为了变绿删除断言、批量跳过失败或把全部跨平台旧测试都当作 Windows 缺陷。原 `check:pr` 是更广的跨平台诊断，不等于本 fork 的 Windows 验收；它的失败和未运行项要单独说明。

## 3. 核对 Git 与验收结果

```powershell
git remote -v
git config --local --get remote.pushDefault
git config --local --get-regexp '^submodule\..*\.(active|update)$'
git status --short --branch
```

预期默认推送远端为 `origin`；`.gitmodules` 中 `update = none` 的可选子模块在本机为 `active=false`、`update=none`。安装脚本会备份配置，并仅移除指向原始 `morluto/rea` 的 `upstream` 远端；不要自行移除其他远端。

安装本身不应产生需要提交的源码改动。`.cache/`、`node_modules/`、`dist/`、`native/windows/build/` 等依赖、缓存和编译产物应留在本机，不从另一台电脑复制或提交进 Git。

子模块包含 Windows 不支持的上游测试文件名，正常运行 REA 不需要初始化这些可选源码。不要直接递归 checkout Unblob，不关闭 Windows 文件名保护。只有任务明确需要查看或修复 Unblob/Wakaru 源码时，才运行：

```powershell
powershell.exe -NoProfile -File scripts/init-windows-submodules.ps1
```

更多细节见 [贡献指南的 Windows 章节](CONTRIBUTING.md#windows-source-checkouts)。源码能检出不代表原来的 Linux/macOS 专属分析能力已支持 Windows。

## 4. 两台电脑日常使用

- 开工前先在 GitHub Desktop 拉取；切换电脑前提交并推送。两台电脑不要各自堆积尚未同步的提交。
- 依赖或工具版本变动后重新运行 `setup`；原生源码或运行代码变动后运行 `build`；开发环境验收运行 `check`，实际引擎与 Codex 链路验收再运行 `verify-analysis`。这些子命令都通过同一个 `scripts/windows.ps1` 入口执行。
- Desktop 的提交/推送 hooks 会使用项目固定工具链。普通拉取/推送不需要再次初始化可选子模块；不要把可选源码恢复命令加入日常同步。
- Windows 会锁定正在被 REA MCP 加载的原生模块。需要重新构建原生源码时，先在客户端正常停止或重新加载 REA 服务，再执行 `build`；出现链接器无法写入 `.node` 时先核对占用，不反复编译、不结束身份不明的进程。普通 pull/push 和源码检查不需要重编译这个模块。
- 验证 Desktop 同步时，使用真实 GitHub Desktop 或其自带 Git，在工作区干净且允许同步时拉取核对。只有存在已授权的实际改动时才提交/推送，不为安装验收制造测试提交或改写远端历史。

## 5. 给用户的完成回执

报告仓库路径、分支、当前提交、实际 Node/npm/Python/编译器版本，`setup` 与 `check` 的退出结果和有原因的跳过项，Git 远端与工作区状态，以及真实做过的 Desktop 拉取/推送结果。失败附最小必要日志，不附凭证或完整环境变量。

将未执行项明确写为 `Not Run`。其他电脑或 GitHub CI 曾经通过，只能作为参考；必须实际完成本机验收，才能声称这台电脑已经装好。未安装或未调用的真实分析引擎也应列为未验证。
