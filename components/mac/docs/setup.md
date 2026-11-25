# 首次安装与依赖顺序

从 `feipi-agent-kit` 根目录使用工作台入口。这里的准备工作用于新 Mac 或缺失环境的机器，**不是每次开机都安装**。
日常开机不运行 bootstrap，也不自动启动服务。已有机器先用 `./workbench doctor mac` 检查配置来源和差异。

## 首次安装

从已取得的源码目录执行下列命令。入口在需要时先准备 CLT、Homebrew、Git 和 Python。

```bash
./workbench install mac
```

裸机需要系统管理员授权时，在终端运行 `sudo -v` 后重试安装。已有 Homebrew 和 CLT 时直接补装缺项。

它使用固定提交和 SHA-256 校验的 Homebrew 官方安装器，以无交互方式准备 CLT/Homebrew，
再补装 Git/Python；不升级已有包，不写启动文件。缺少已有 sudo 授权会在下载安装前停止。
已在没有 CLT/Homebrew 的干净 macOS 26.6.2 arm64 中真实完成安装与独立 check。
完成此阶段不代表整个环境已验收。
`check` 会激活已经发现的 Homebrew，避免非交互环境误用系统旧版 Python；不会补装软件。
若此前只完成 nvm 下载、尚未安装 Node，环境激活允许继续执行安装；已有无效 default 仍会停止并保留原选择。

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

## 安装范围与授权

共享 `Brewfile` 对官方的 `sdkman/tap/sdkman-cli` 和 `multica-ai/tap/multica` 声明配方级信任。
Homebrew Bundle 会在安装前将这两个配方写入本机信任记录。

桌面应用按缺项补装，终端实时显示 Homebrew 的下载与安装输出。批量安装设置 `HOMEBREW_NO_SUDO=1`。需要 macOS 系统安装器的 PKG
列在 `Brewfile.apps.admin`，由本人逐项决定是否安装。查看当前缺项，以及查阅单项 cask 的安装类型：

```bash
brew bundle check --no-upgrade --verbose --file components/mac/Brewfile.apps.admin
brew info --cask temurin@25
```

确认某项需要安装时，例如 `brew install --cask temurin@25`，让 Homebrew 在实际运行该软件的
系统安装器时请求授权。每项操作后用 `sudo -k` 使当前终端的 sudo 缓存失效。PKG 及其安装脚本
可以在安装时以 root 执行，也可能安装由系统启动的后台组件。日常应用由登录用户启动。

`sogouinput` 是手动安装器。Homebrew 准备文件后，运行 `open "$(brew --caskroom sogouinput)"`，
在 Finder 选择原厂安装器。启动安装器后单独核对 macOS 的授权提示，并在系统设置中添加输入源。

### oMLX 命令行服务

桌面清单用 `brew install jundot/omlx/omlx --with-custom-kernel` 安装 oMLX 并编译原生自定义内核。
安装前需准备完整 Xcode 和 Metal Toolchain，用 `xcrun metal --version` 确认编译器可运行。
缺少 Metal Toolchain 时，先运行 `xcodebuild -downloadComponent MetalToolchain`。
`apps.sh` 会用 Homebrew 安装路径检查 CLI 版本和原生内核加载。重跑时复用通过检查的安装。
如果已有版本无法加载内核，可用 `brew reinstall jundot/omlx/omlx --with-custom-kernel` 重装。

oMLX 服务配置由 `config/omlx-service.json` 管理。修改 host、port 或并发请求数后，运行
`./workbench service omlx restart`；工作台合并受管键到 `~/.omlx/settings.json`（或 oMLX
选择的数据目录），保留 API key、模型、缓存等本机设置，随后重启并确认监听与 API 响应。
用 `./workbench service omlx status` 查看 PID、实际监听地址和接口状态，`logs` 查看 Homebrew
服务日志。默认以当前用户运行且仅监听本机 `127.0.0.1:8037`，不需要 sudo。要使用菜单栏应用，请运行
`bash components/mac/bootstrap/desktop-extras.sh install omlx`。

### OpenWhispr 全局听写

`./workbench install mac` 会从 `Brewfile.apps` 补装 OpenWhispr。已有环境只补这一项时运行
`brew install --cask openwhispr`。首次启动可使用无账号模式。按系统提示给 OpenWhispr 开启
麦克风和辅助功能，分别用于录音和把文字填回当前输入框。

1. 运行 `./workbench service omlx status` 核对本机服务。换机时在 oMLX 恢复 `Qwen3-ASR-1.7B-8bit`，
   并以本机 `/v1/models` 返回的模型 ID 为准。
2. 在 **Settings → Speech to Text → Dictation** 选择 **Self-Hosted**。`Server URL` 填
   `http://127.0.0.1:8037/v1`，`Model` 填 `Qwen3-ASR-1.7B-8bit`。在
   **HTTP headers → Add header** 中填 `Authorization`，值填 `Bearer <本机 oMLX API key>`。
   应用向此基址下的 `/audio/transcriptions` 发送音频，认证信息在应用内保存。
3. 在 **Preferences → Language** 选择自动识别，在 **Preferences → Clipboard** 开启
   `Automatic pasting`。在 **Hotkeys** 把 `Dictation Hotkey` 设为 `Control+Shift+Space`，
   使用点按启停。在 **Language Model → Dictation Cleanup / Voice Assistant / Translation**
   关闭对应的三项功能。搜狗继续作为键盘输入法。
4. 在 TextEdit 草稿中按快捷键录一条含中英文术语的短句，再按一次结束，核对文字出现在
   原输入框。用 `./workbench service omlx logs` 核对转写请求到了本机服务。

参考 [OpenWhispr 的 Homebrew 安装项](https://formulae.brew.sh/cask/openwhispr) 和
[自定义转写接口说明](https://github.com/OpenWhispr/openwhispr/tree/main/examples/custom-asr-shim)。

### 固定桌面应用

`install mac` 还会调用 `bootstrap/desktop-extras.sh install`，补齐固定官方发布包的
FlClash for oixCloud 0.9.3 和 oMLX 0.4.4 GUI。下载后核对 SHA-256，
DMG 检查应用身份、版本和代码签名；保留已有安装，不借初始化升级。固定来源与摘要见
`config/desktop-extras.tsv`，只支持 Apple Silicon；oMLX 区分 macOS 15 与 26/27 包。
DMG 缺项需要当前用户可写 `/Applications`，否则在下载前提示单独处理。
也可在安装 CLT/Homebrew 前仅执行 `bash components/mac/bootstrap/desktop-extras.sh install flclash`；
这个入口只用系统工具。代理首次登录、节点同步和系统权限必须在准备阶段完成。
不要把旧机 `HTTP_PROXY=127.0.0.1:7890` 当作新机已经具备代理服务。

oMLX 固定包的应用缺少随包公证票据；安装入口使用 CLT 的 Apple `stapler` 附加并验证
原有票据，已有有效票据时保留。获取失败则停止，不关闭 Gatekeeper、不移除隔离属性。
此步骤不影响可在 CLT 前安装 FlClash 的入口。
安装后用 `bash components/mac/bootstrap/desktop-extras.sh check` 只读检查实际签名、
oMLX 公证票据及 CLI 入口；实际启动仍需单独验收。
`omlx` 使用应用自带 CLI。模型和真实业务请求另行验收。
非交互脚本先 `source components/mac/bootstrap/environment.sh`；它和交互 Zsh 都预留 `~/.omlx/bin`，优先使用应用原生入口，尚未打开应用时回退到 `~/.local/bin`。原生入口由 oMLX 创建并读取其数据目录设置；不会为此向 shell 启动文件追加另一份配置。
恢复三个既用 oMLX 模型后运行 `python3 components/mac/bootstrap/verify-extras.py`：
用随机本机端口验证文本推理及固定模型的语音识别。
仅创建本次隔离状态和公开验证音频，结束清理自有进程，保留私有日志、源码摘要及结果报告。
模型不在默认位置时传 `--model-dir 路径`。
参考：[FlClash 官方发布](https://github.com/pickrui/FlClash/releases/tag/v0.9.3)、
[代理备份范围](https://docs.dler.io/en/flclash/backup.html)、
[oMLX 官方发布](https://github.com/jundot/omlx/releases/tag/v0.4.4)。

## 依赖与配置发布顺序

`install mac` 依次补装 Homebrew 依赖、Node/npm、Rust、Agent CLI、oh-my-zsh、Homebrew 桌面清单和固定发布包。补全在 CLI 就绪后统一生成。
安装中断时保留已完成的软件，处理报错后重跑。依赖就绪后，同一次安装会发布配置。

全新 nvm 安装 Node 24.22.3；已有 nvm default 或系统 Node 保留。Agent CLI 的验收应检查真实请求和工具产物。
安装完成后再发布应用配置。
单独执行 ohmyzsh.sh 时，生成补全所需的工具也应已在当前 PATH；全量入口会重新激活 nvm default。

`install mac` 从共享 Homebrew 清单补齐 Codex，并在依赖阶段后运行 `bootstrap/agents.sh install` 补齐其他缺失 CLI。Qwen 使用 npm 的 `latest`，Claude Code 和 Qoder CLI 使用各自的 Homebrew cask。安装后检查 CLI 是否已进入 PATH。版本和发布包校验由各安装渠道管理。

Multica CLI 也由共享 Homebrew 清单安装。登录 Cloud 和检查 daemon 的命令见 [Multica 使用说明](../../multica/README.md#multica-cloud)。

升级 Codex 使用 `brew upgrade --cask codex`。从旧 npm 安装迁移时，先用 `"$(brew --prefix)/bin/codex" --version` 核对 Homebrew 入口，然后在安装了旧包的 Node 环境执行 `npm uninstall -g @openai/codex`。用 `type -a codex` 核对终端入口。Multica 自托管配置如绑定了 npm 路径，改用 Homebrew 的 `bin/codex` 入口，排空任务后重启 daemon。
新机安装后需登录或配置受支持的 API，再执行真实小任务。只读核对可运行 `bash components/mac/bootstrap/agents.sh check`。
Agent CLI 就绪后统一补装 oh-my-zsh 插件并生成补全。

安装组件软件前检查配置目录和父路径。发布中断时尝试还原本机目标。
配置发布由 Stow 建立链接。工作台识别自己发布过的旧链接和同内容副本，遇到用户自行修改的文件时先停止，由用户检查冲突。

## 安装后确认

新开终端后执行：

```bash
./workbench doctor mac
bash components/mac/bootstrap/check.sh       # 全部来源与内容，接受工作台运行副本
bash components/mac/bootstrap/brew.sh check  # 单独检查共享/单机 Homebrew 清单
```

来源检查会先激活已经存在的 Homebrew、nvm default/Cargo 路径，不加载 `.zshrc` 或安装软件；SSH/非交互 Bash 的 PATH 缺少 Homebrew 时会探测 macOS 标准安装位置。
工作台 doctor 也会核实不在父进程 PATH 中的 nvm Node，避免全新机器安装成功后误报缺失。
SSH 中缺少交互 PATH 时，doctor 还会只读探测 `/opt/homebrew/bin` 和 `/usr/local/bin`，不要求重复安装已有软件。
交互 Zsh 同时识别 nvm 默认别名中的 `24.22.3` 与 `v24.22.3`，让全局 CLI 在新终端直接可用。

恢复私有设置并准备当前终端的环境变量后，可执行真实 Agent 文件任务：

```bash
bash components/mac/bootstrap/verify-agents.sh
# 单独复验某个 CLI，使用原有模型和代理设置：
bash components/mac/bootstrap/verify-agents.sh --cli qwen
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
Minuet AI 行内补全需要当前 Neovim 进程收到 `AUTOCOMPLETE_API_BASE`、`AUTOCOMPLETE_API_KEY` 和 `AUTOCOMPLETE_MODEL`。
缺少任意一项时跳过 AI 补全初始化。补齐后从已加载 `~/.env` 的交互 Zsh 重新打开 Neovim。

HHKB/iTerm2 所需应用与字体已列入 `components/mac/Brewfile.apps`；完整新机安装需要显式安装该清单，
`workbench install mac` 会复制仓库配置。
尽量在首次配置应用前恢复，减少默认文件冲突；之后人工授予权限、选择 Profile 并测试按键。

桌面安装后可独立验证实际文档/编译能力：

```bash
python3 components/mac/bootstrap/verify-apps.py
```

它用独立临时浏览器和 Office Profile 导出中英文 PDF，检查正文及中文字体嵌入并渲染 PNG。
Chrome 可嵌入 Noto Sans CJK SC 或系统苹方，LibreOffice 须嵌入 Noto Sans CJK SC。
Java 验收用本机 JDK 25 编译并运行小程序。报告、日志、源码版本和产物保存在
`~/.local/state/feipi-workbench/validation/mac-apps-*`。此检查不代表各客户端登录或键盘权限已完成。
共享清单显式包含 Fontconfig，应用清单包含 Noto Sans CJK SC；新终端默认使用 Homebrew 的
`fonts.conf`，保留已有 `FONTCONFIG_FILE`。非交互验收也显式使用同一配置，避免 LibreOffice
虽能抽取 PDF 中文却没有可见字形。直接从其他环境调用 Office 转换时也应传入该配置。

原生应用验收使用 `python3 components/mac/bootstrap/verify-extras.py`。oMLX 模型已恢复到
`~/.omlx/models` 且有迁入设置时，验收从设置的隔离副本解析模型路径，完成真实文本和固定语音模型请求，
不改动原设置；使用其他模型目录时可传 `--model-dir`。

服务、Skills、模型与业务资料按统一工作台的[恢复说明](../../../docs/workbench.md)处理；
