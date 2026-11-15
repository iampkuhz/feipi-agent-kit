# 首次安装与依赖顺序

从 `feipi-agent-kit` 根目录使用工作台入口。这里的准备工作用于新 Mac 或缺失环境的机器，**不是每次开机都安装**。
日常开机不运行 bootstrap，也不自动启动服务。已有机器先用 plan 看影响，不要为了“验证”重装。
完整新机的集中 copy/export/授权命令见[准备清单](../../../docs/new-mac-prepare.md)。

## 先准备并确认

裸机还没有 Git/Python 时，先从已取得的源码目录运行系统 Bash 前置入口：

```bash
bash scripts/bootstrap/prerequisites.sh plan
sudo -v # 首次安装所需的一次管理员授权
bash scripts/bootstrap/prerequisites.sh install
```

它使用固定提交和 SHA-256 校验的 Homebrew 官方安装器，以无交互方式准备 CLT/Homebrew，
再补装 Git/Python；不升级已有包，不写启动文件。缺少已有 sudo 授权会在下载安装前停止。
已在没有 CLT/Homebrew 的干净 macOS 26.6.2 arm64 中真实完成安装与独立 check。
完成此阶段不代表整个环境已验收。

| 顺序 | 需要准备什么 | 怎样确认 | 谁负责 |
| --- | --- | --- | --- |
| 1 | 普通用户账号、可用网络/必要代理、长期保存仓库的目录 | 不用 sudo 运行整个脚本；网络与认证由自己确认 | 人工 |
| 2 | Apple Command Line Tools | `xcode-select -p` 与 `xcrun --find clang` 都成功 | 上述 prerequisites 安装入口；必要的系统授权由本人完成 |
| 3 | Homebrew | 按 [官方说明](https://brew.sh/) 安装，用 `brew --version` 确认 | 上述 prerequisites 安装入口 |
| 4 | Git、curl 与本仓库 | `command -v git curl`；`components/mac/Brewfile` 存在 | CLT/系统工具与自行克隆 |
| 5 | 可选单机软件 | 按需复制 Brewfile.local.example 为 Brewfile.local | 人工选择，不从旧机软件快照生成 |

总入口会检查 macOS、普通用户、HOME、CLT 编译器、Homebrew/Git/curl 入口和共享清单。
它不测试网络、不打开 CLT 安装界面、不代装 Homebrew；前置条件不满足就停止。
发现命令入口不等于版本、网络或实际运行已经验收。

## 先看计划，再安装

```bash
./workbench plan mac        # 只读：看依赖阶段、清单、受管目标和已知冲突
./workbench install mac     # 补装缺失项，复用组件依赖编排
./workbench install mac --apps # 完整新机同时补齐 Brewfile.apps 中的应用
./workbench install mac --apps --agents # 同时补装与旧机兼容的四个 Agent CLI
./workbench apply mac       # 备份后发布独立运行副本
```

桌面安装入口复用已经取得的 `sudo -v` 授权并在该阶段保活，不保存密码；
授权缺失时在下载前失败。当前 Homebrew 会在首次 sudo 能力检查时清空凭据，
入口实际核实授权后标记本轮已检查，避免中途重新询问。清单已经齐备时只检查，不再要求授权。
整个裸机流程跨阶段的一次准备与业务恢复仍在整体验收中，不能用桌面阶段代替。

`--apps` 还会调用 `bootstrap/desktop-extras.sh install`，补齐固定官方发布包的
FlClash for oixCloud 0.9.3、oMLX 0.4.4 和 Session Browser 0.5.2。下载后核对 SHA-256，
DMG 检查应用身份、版本和代码签名；保留已有安装，不借初始化升级。固定来源与摘要见
`config/desktop-extras.tsv`，只支持 Apple Silicon；oMLX 区分 macOS 15 与 26/27 包。
也可在安装 CLT/Homebrew 前仅执行 `bash components/mac/bootstrap/desktop-extras.sh install flclash`；
这个入口只用系统工具。代理首次登录、节点同步和系统权限必须在准备阶段完成。
不要把旧机 `HTTP_PROXY=127.0.0.1:7890` 当作新机已经具备代理服务。

oMLX 固定包的应用缺少随包公证票据；安装入口使用 CLT 的 Apple `stapler` 附加并验证
原有票据，已有有效票据时保留。获取失败则停止，不关闭 Gatekeeper、不移除隔离属性。
此步骤不影响可在 CLT 前安装 FlClash 的入口。
安装后用 `bash components/mac/bootstrap/desktop-extras.sh check` 只读检查实际签名、
oMLX 公证票据及 CLI 入口；实际启动仍需单独验收。
`session-browser serve` 使用官方自包含 Java runtime，`omlx` 使用应用自带 CLI；
两者的 HOME 配置、会话数据、模型和真实业务请求另行恢复验收。
非交互脚本先 `source components/mac/bootstrap/environment.sh`；它和交互 Zsh 都预留 `~/.omlx/bin`，优先使用应用原生入口，尚未打开应用时回退到 `~/.local/bin`。原生入口由 oMLX 创建并读取其数据目录设置；不会为此向 shell 启动文件追加另一份配置。
恢复三个既用 oMLX 模型后运行 `python3 components/mac/bootstrap/verify-extras.py`：
用合成 Codex 会话验证原生索引与网页，用随机本机端口验证文本推理及两套语音识别。
仅创建本次隔离状态和公开验证音频，结束清理自有进程，保留私有日志、源码摘要及结果报告。
可用 `--only session-browser` 或 `--only omlx` 单独复验；模型不在默认位置时传 `--model-dir 路径`。
参考：[FlClash 官方发布](https://github.com/pickrui/FlClash/releases/tag/v0.9.3)、
[代理备份范围](https://docs.dler.io/en/flclash/backup.html)、
[oMLX 官方发布](https://github.com/jundot/omlx/releases/tag/v0.4.4)、
[Session Browser 官方发布](https://github.com/iampkuhz/feipi-session-browser/releases/tag/v0.5.2)。

plan 不联网、不执行 brew/nvm/rustup、不加载用户启动配置，也不创建 HOME 或日志。
已有 Stow 且 HOME 存在时会调用只读链接冲突模拟，否则显示“未核实”。已知阻塞返回非零；
退出 0 仅表示已检查范围内没有阻塞，不代表未核实项通过，也不是稍后可直接重放的执行凭证。

## 依赖与配置发布顺序

依赖顺序在 `bootstrap/run.sh` 的固定阶段数组中定义，预览与执行共用。工作台使用其四个依赖阶段，最后独立备份并发布运行副本；不会把 HOME 重新链接到研发源码。组件内 `run.sh` 在统一仓库中同样转到工作台。

| 步骤 | 脚本 | 需要先具备 | 完成后提供什么 |
| --- | --- | --- | --- |
| 1 | brew.sh install | Homebrew 与根目录清单 | Stow、Neovim、Python/uv、质量工具等共享依赖和已选择的单机软件 |
| 2 | node.sh install | Git/curl；保留已有 nvm default 或系统 Node | 可用 Node/npm，以及当前前缀中的 Prettier、prettierd、Yarn classic |
| 3 | rust.sh install | curl；已有 rustup 时核验工具链状态 | Rust 默认工具链与 rustfmt，保留已有版本 |
| 4 | ohmyzsh.sh install | Git；Node/Rust 已就绪便于生成补全 | oh-my-zsh、主题、插件和补全缓存 |
| 5 | workbench apply mac | 受管配置冲突已处理 | Zsh/Neovim 运行副本与桌面配置；备份原目标 |

Node 和 Rust 相互没有安装依赖，这里固定串行以便排障；它们先于 oh-my-zsh 是为了补全完整。
全新 nvm 固定安装 Node 24.22.3；已有 nvm default 或系统 Node 保留。当前 Qwen 0.12.3 在 Node 26 上会因内置网络库不兼容而请求失败，即使退出码为 0；验收须检查真实请求和工具产物，不能只检查版本或退出码。
配置链接本身不要求先启动 Neovim，但放最后能避免新终端先加载尚未准备好的工具配置。
单独执行 ohmyzsh.sh 时，生成补全所需的工具也应已在当前 PATH；全量入口会重新激活 nvm default。

`--agents` 在依赖阶段后运行 `bootstrap/agents.sh install`：Codex 版本从 Multica 的
`config/agents.json` 兼容声明派生，Qwen 使用固定 npm 包和完整性摘要；Claude/Qoder 使用
已与旧机程序核对的 Apple Silicon 原生发布包，不通过可漂移的 Homebrew cask 安装 CLI。
已有相同版本直接保留，其他版本先报冲突，下载摘要或执行版本不符则停止。安装不会复制认证状态，
完成后还需在新机登录或恢复受支持的 API 配置，再执行真实小任务。
只读核对：`bash components/mac/bootstrap/agents.sh check`；版本清单见 `config/cli-versions.json`。
安装完成会复用 oh-my-zsh 的补装入口刷新 CLI 补全，保留已有插件版本，避免首次终端缺少 Codex 补全。

工作台在任何下载安装前检查受管目录和父路径冲突；发布时再次检查并备份。以下 Stow 说明仅适用于独立组件源码链接调试。
已有 Stow 时，源码链接模式在下载安装前检查冲突；Homebrew 阶段结束后必须再检查一次。
若首次安装前还没有 Stow，则可能先完成 Homebrew 安装，随后才发现配置冲突；成功项会保留。
配置冲突由人工审查、备份并移走确认不用的文件，脚本不会自动接管。

## 安装后确认

新开终端后执行：

```bash
./workbench doctor mac
./develop mac run -- bash bootstrap/check.sh       # 全部来源与内容，接受工作台运行副本
./develop mac run -- bash bootstrap/brew.sh check  # 单独检查共享/单机 Homebrew 清单
```

来源检查会先激活已经存在的 Homebrew、nvm default/Cargo 路径，不加载 `.zshrc` 或安装软件；SSH/非交互 Bash 的 PATH 缺少 Homebrew 时会探测 macOS 标准安装位置。
工作台 doctor 也会核实不在父进程 PATH 中的 nvm Node，避免全新机器安装成功后误报缺失。
交互 Zsh 同时识别 nvm 默认别名中的 `24.22.3` 与 `v24.22.3`，让全局 CLI 在新终端直接可用。

恢复私有设置并准备当前终端的环境变量后，可执行真实 Agent 文件任务：

```bash
./develop mac run -- bash bootstrap/verify-agents.sh
# 单独复验某个 CLI，使用原有模型和代理设置：
./develop mac run -- bash bootstrap/verify-agents.sh --cli qwen
```

验收使用各 CLI 的原生非交互模式，在独立私有目录创建文件并逐字节核对；单项最多 180 秒，失败继续检查其余 CLI，最终返回非零。报告和原生日志保存在 `~/.local/state/feipi-workbench/validation/agent-tasks-*/`。这会按现有账号配置发送小型模型请求；没有凭据、服务未启动、退出码为 0 却未生成正确文件，均不算通过。完整迁移验收还须核实相关服务和开机后的真实行为。

配置发布后显式执行编辑器准备：

```bash
bash components/mac/bootstrap/neovim.sh
```

入口激活已有 Node/Rust，按锁文件恢复插件并保留锁文件原文，再启动恢复后的代码。
它核实全部插件 HEAD、Markdown 构建任务、31 个解析器的实际加载、5 个 Mason 语言服务器，
并在真实缓冲区检查 Lua LSP 初始化、Lua/JSON 格式化及 Markdown 本机 HTTP 页面。
任务超时或任一检查失败返回非零，保留成功安装项，可修复后重跑；不会打开浏览器或修改业务文件。
仍可在编辑器中用 `:checkhealth` 和实际项目检查更多功能。
私密环境变量按自己的安全备份渠道恢复，不在仓库保存真实 `.env`。

HHKB/iTerm2 所需应用与字体已列入 `components/mac/Brewfile.apps`；完整新机安装需要显式安装该清单，
`workbench apply mac` 会备份后复制配置。独立组件调试仍可使用 `bootstrap/desktop.sh check|install`。
尽量在首次配置应用前恢复，减少默认文件冲突；之后人工授予权限、选择 Profile 并测试按键。

桌面安装后可独立验证实际文档/编译能力：

```bash
python3 components/mac/bootstrap/verify-apps.py
```

它用独立临时浏览器/Office Profile 导出中英文 PDF，检查正文及中文字体嵌入，渲染 PNG；
另用 JDK 25 编译并运行小程序。报告、日志、源码版本和产物保存在
`~/.local/state/feipi-workbench/validation/mac-apps-*`。此检查不代表各客户端登录或键盘权限已完成。
共享清单显式包含 Fontconfig，应用清单包含 Noto Sans CJK SC；新终端默认使用 Homebrew 的
`fonts.conf`，保留已有 `FONTCONFIG_FILE`。非交互验收也显式使用同一配置，避免 LibreOffice
虽能抽取 PDF 中文却没有可见字形。直接从其他环境调用 Office 转换时也应传入该配置。

原生应用验收使用 `python3 components/mac/bootstrap/verify-extras.py`。oMLX 模型已恢复到
`~/.omlx/models` 且有迁入设置时，验收从设置的隔离副本解析模型路径，完成真实文本和两套语音请求，
不改动原设置；使用其他模型目录时可传 `--model-dir`。

服务、Skills、模型与业务资料按统一工作台的[恢复说明](../../../docs/workbench.md)处理；
完整新机验收状态见[交付清单](../../../docs/new-mac-delivery.md)。
