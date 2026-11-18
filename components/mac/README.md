# iampkuhz dotfiles

日常操作统一从仓库根目录 `./workbench` 进入；本目录命令供组件维护与显式源码调试。应用、回收与恢复见 [工作台手册](../../docs/workbench.md)。原独立仓库仅留作历史回退。

保存 Mac 研发环境的依赖声明、Zsh/Neovim 配置和 HHKB/iTerm2 小配置。
共享依赖在本目录 `Brewfile`，完整应用清单在 `Brewfile.apps`，单机选择在忽略的 `Brewfile.local`。

| 我现在想做什么 | 读哪份说明 |
| --- | --- |
| 新 Mac 先装什么、怎么确认、按什么顺序执行 | [首次安装与依赖顺序](docs/setup.md) |
| 检查配置、处理安装失败、补装或主动升级 | [日常检查与故障恢复](docs/maintenance.md) |

## 常用入口

先按首次安装说明准备 CLT、Homebrew、Git/curl，再从仓库根目录执行：

```bash
./workbench install mac     # 补齐依赖并发布配置

# 安装后新开终端
./workbench doctor mac
bash components/mac/bootstrap/check.sh
bash components/mac/bootstrap/brew.sh check
```

默认顺序：**Homebrew → Node/npm → Rust → Agent CLI → oh-my-zsh → 桌面应用**。
安装前预检受管路径。安装保留已有版本，并在发现路径冲突时停止。

`install mac` 包含 Homebrew 应用清单，以及固定官方发布包的 FlClash for oixCloud、oMLX、
Session Browser。代理可在裸机先单独安装；来源、摘要及账号准备边界见 [首次安装](docs/setup.md)。
这用于首次准备或补齐环境，不是每次开机要运行的流程，也不自动启动后台服务。

`./workbench install mac` 用 Stow 将运行目录中的 Zsh、Neovim、Qwen 语言配置、Karabiner 和 iTerm2 配置链接到 HOME。`.zshrc` 按编号加载 `.zsh_config/` 中的模块，`~/.env` 由本机维护。`bash components/mac/bootstrap/check.sh` 核对链接与源码。系统授权及按键在应用中验证。
修改初始化脚本后执行 `bash components/mac/bootstrap/test.sh`，在隔离 HOME 中验证 Bash、Zsh 和安装顺序。

密钥、认证、模型、缓存和生成物不入 Git；临时分析放 `tmp/`，不作为配置来源。
LiteLLM/PostgreSQL、SearxNG、Crawl4AI 的服务定义与启动配置归 `feipi-agent-kit`，本仓库只准备机器依赖。
