# 日常检查与故障恢复

以下命令从仓库根目录执行。首次安装见 [setup.md](setup.md)。

| 用途 | 命令 |
| --- | --- |
| 补齐机器环境 | `./workbench install mac` |
| 检查配置差异 | `./workbench doctor mac` |
| 发布配置 | `./workbench install mac` |
| 核对工具、脚本语法与配置来源 | `bash components/mac/bootstrap/check.sh` |
| 检查 Homebrew 清单 | `bash components/mac/bootstrap/brew.sh check` |
| 运行离线回归 | `bash components/mac/bootstrap/test.sh` |

## 失败后怎样继续

出现下载或安装错误时，处理原始报错后重跑 `./workbench install mac`。已经完成的项会核对并复用。

| 提示/现象 | 处理方法 |
| --- | --- |
| CLT 无法定位 clang | 在系统界面完成 CLT 安装，再运行 `./workbench install mac` |
| .zshrc 或 Neovim 配置冲突 | 核对内容/链接来源，备份并移走确认不用的冲突项，再运行 `./workbench install mac` |
| `.zshrc` 来源不符 | 用 `workbench doctor mac` 确认状态。选择保留本机修改或发布仓库版本 |
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
bash components/mac/bootstrap/brew.sh install
bash components/mac/bootstrap/node.sh install
bash components/mac/bootstrap/rust.sh install
bash components/mac/bootstrap/ohmyzsh.sh install

# 只有主动选择才升级
bash components/mac/bootstrap/brew.sh upgrade
brew upgrade --cask codex
bash components/mac/bootstrap/node.sh upgrade      # 仅 npm 工具，不升级 Node/nvm
bash components/mac/bootstrap/rust.sh upgrade
bash components/mac/bootstrap/ohmyzsh.sh upgrade
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

`test.sh` 要求已有 Bash、Zsh、Git、ShellCheck 和 shfmt。
它逐文件检查 Bash 语法，运行 ShellCheck/shfmt，再执行链接、Node、总入口和补全缓存离线测试。
可单独执行 `test-links.sh`、`test-node.sh`、`test-bootstrap.sh`、`test-completion-cache.sh` 定位失败。
测试使用隔离 HOME 和本地替身。提交前另运行 `git diff --check`。

真实 Zsh/Neovim 启动、插件下载、GUI 和业务项目在目标环境验证。
