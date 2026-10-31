# 日常检查与故障恢复

所有命令从仓库根目录执行。首次安装顺序见 [setup.md](setup.md)，完整迁移见 [MIGRATION.md](../MIGRATION.md)。

## 选择合适的入口

| 想做什么 | 命令 | 会不会修改环境 |
| --- | --- | --- |
| 看整体安装计划 | `bash bootstrap/run.sh plan` | 只读；未核实项明确标出 |
| 看命令入口、脚本语法与配置来源 | `bash bootstrap/check.sh` | 只读，不加载 .zshrc |
| 看 Homebrew 清单是否满足 | `bash bootstrap/brew.sh check` | 不安装、不主动更新元数据 |
| 看配置能否安全链接 | `bash bootstrap/macosinit.sh check` | Stow 整体模拟，未实际链接 |
| 看当前配置是否已来自本仓库 | `bash bootstrap/macosinit.sh verify` | 只读，核对默认包内 Git 跟踪文件 |
| 补齐机器环境 | `bash bootstrap/run.sh` | 会下载安装和链接，失败停止 |
| 修改脚本后离线验证 | `bash bootstrap/test.sh` | 只在临时 HOME/替身环境测试，不安装依赖 |

check 与 verify 不等价：Stow 模拟通过可能表示“没有冲突，可以建立缺失链接”；verify 会把缺失链接报错。
verify 兼容正确的旧目录链接和逐文件链接，拒绝把独立副本当作受管来源。
配置清单来自 Git 中的 zsh/neovim 文件，不含 Qwen 可选包、未跟踪文件、缓存和日志。
若某个受跟踪配置被 Stow 忽略，verify 会指出未安装；维护者应调整包内容或规则，不能默默漏装。

PATH 中没有命令不等于从未安装；先检查其安装目录和管理方式。check 不运行这些工具核验版本。
ShellCheck 已安装时会执行，缺失会在关键工具检查中报告；Zsh 的语法应另用 `zsh -f -n 文件`，不由 ShellCheck 检查。
参数错误返回 2；普通检查不满足返回非零。原安装命令失败时总入口保留其退出码。

## 失败后怎样继续

例如 npm 下载失败，总入口会列出 Homebrew 完成、Node/npm 失败、其他三步未执行，并显示重试入口。
先处理原始错误，再执行 `bash bootstrap/node.sh install`；成功后重新运行总入口，已安装内容按原规则保留。
这不是跳过检查的断点续装，也不会自动卸载之前已经安装成功的软件。

| 提示/现象 | 处理方法 |
| --- | --- |
| CLT 无法定位 clang | 在系统界面完成 CLT 安装，再运行 plan |
| .zshrc 或 Neovim 配置冲突 | 核对内容/链接来源，备份并移走确认不用的冲突项，再 check、install；不用 adopt/override |
| 某个 Zsh 模块来源不符 | 检查是否仍指向旧仓库；verify 不自动改链接 |
| nvm default 无效 | 人工选择已有版本，例如 `nvm alias default <已安装版本>`，不以重装替代版本选择 |
| 已有 Rust 工具链但默认版本不可用 | 按提示执行 `rustup default <已安装版本>`，再重试 |
| oh-my-zsh 仓库有本地修改 | 自己审查和处理改动；升级不自动 stash/reset |
| 补全更新失败/输出为空/语法错误 | 原缓存保留，其他补全继续；排查提示中的对应工具后重跑 ohmyzsh.sh install |
| 桌面配置与仓库不同 | 可能是应用内主动调整；审查后选择同步回仓库或人工备份，再恢复；不自动覆盖 |

补全先生成临时文件，成功且通过 Zsh 语法检查后替换；错误输出不混入补全。
补全失败作为非致命警告计数，不把已安装的主题和插件判为失败；没有旧缓存时不会凭空生成可用缓存。
桌面配置先整体检查再复制，正确副本跳过；应用侧修改不会自动回写仓库。

## 安装与升级分开

```bash
# 只补装缺失项，可单独重试；前置条件见 setup.md
bash bootstrap/brew.sh install
bash bootstrap/node.sh install
bash bootstrap/rust.sh install
bash bootstrap/ohmyzsh.sh install

# 只有主动选择才升级
bash bootstrap/brew.sh upgrade
bash bootstrap/node.sh upgrade      # 仅 npm 工具，不升级 Node/nvm
bash bootstrap/rust.sh upgrade
bash bootstrap/ohmyzsh.sh upgrade
```

Homebrew install 使用 `--no-upgrade` 并关闭自动更新；新包所需依赖仍由 Homebrew 解析。不执行 cleanup，
也不要用 `brew bundle dump --force` 覆盖共享清单。Node/nvm 自身升级需按官方说明人工选择新的 default。
oh-my-zsh upgrade 只允许干净仓库 `git pull --ff-only`。Neovim 主动升级用 `:Lazy update` 并审查 lazy-lock.json。

| 工具归属 | 维护约定 |
| --- | --- |
| Homebrew | 多机共用放根 Brewfile；单机软件放忽略的 Brewfile.local |
| Node/npm | 优先已有 nvm default，再用系统 Node；都没有才初装固定 nvm v0.40.8 + LTS；不抢占非 npm 管理的同名工具 |
| Rust | rustup minimal + rustfmt；安装器使用 --no-modify-path，不追加 shell 配置 |
| Python | Homebrew Python + uv；业务项目使用自己的锁文件与环境，pyenv 按需 |
| Java/Ruby | 不设默认依赖；JDK/SDKMAN/rbenv 按项目要求准备 |
| 容器 | 只默认安装 Podman/Compose 命令；不启动虚拟机或服务，不导出镜像 |

使用非默认 NVM_DIR、CARGO_HOME、ZSH 等目录时，需要让后续终端保持相同配置；不能只在某次安装临时指定。
不会从旧机恢复全部 pip/npm 包。Homebrew JDK 的注册与 PATH 按对应 `brew info` 提示处理。

## 桌面与开发验证

桌面仅限 HHKB/Karabiner 和 iTerm2。Brewfile.local 可选 iterm2、karabiner-elements、font-jetbrains-mono-nerd-font。
Karabiner 恢复普通 JSON 副本，保留 HHKB-test，设备匹配 vendor 1278 / product 33；更换键盘需核对编号。
iTerm2 动态 Profile 写入 `~/Library/Application Support/iTerm2/DynamicProfiles/dotfiles.json`，在应用里选择 Dotfiles；
不替换其他 Profile，不恢复会话、认证或偏好数据库。应用权限、字体和按键均需人工验收。

`test.sh` 要求已有 Bash、Zsh、Git、Stow、ShellCheck、shfmt；缺失返回 2，不自动安装。
它逐文件检查 Bash 语法，运行 ShellCheck/shfmt，再执行链接、Node、总入口和补全缓存离线测试。
可单独执行 `test-links.sh`、`test-node.sh`、`test-bootstrap.sh`、`test-completion-cache.sh` 定位失败。
测试不会在真实 HOME 重新 Stow，也不执行真实联网安装。提交前另运行 `git diff --check`。

真实 Zsh/Neovim 启动、插件下载、GUI 和业务项目仍在新机人工验证。`bootstrap/podman.sh` 是独立的可选
PlantUML 启动命令，不由全量安装或测试入口调用；服务定义始终归所属仓库。
