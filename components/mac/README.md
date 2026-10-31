# iampkuhz dotfiles

日常操作统一从仓库根目录 `./workbench` 进入；本目录命令供组件维护与显式源码调试。应用、回收与恢复见 [工作台手册](../../docs/workbench.md)。原独立仓库仅留作历史回退。

保存 Mac 研发环境的依赖声明、Zsh/Neovim 配置和 HHKB/iTerm2 小配置。
共享依赖在根目录 `Brewfile`，单机选择在忽略的 `Brewfile.local`。

| 我现在想做什么 | 读哪份说明 |
| --- | --- |
| 新 Mac 先装什么、怎么确认、按什么顺序执行 | [首次安装与依赖顺序](docs/setup.md) |
| 检查配置、处理安装失败、补装或主动升级 | [日常检查与故障恢复](docs/maintenance.md) |
| 完整换机、私密文件和数据恢复、旧机退役验收 | [迁移手册与历史准备状态](MIGRATION.md) |

## 常用入口

先按首次安装说明准备 CLT、Homebrew、Git/curl，再从仓库根目录执行：

```bash
bash bootstrap/run.sh plan   # 只读预览，未核实项不代表通过
bash bootstrap/run.sh        # 补装缺失项；失败停止并给出阶段摘要和重试入口

# 安装后新开终端
bash bootstrap/check.sh      # 静态检查、命令入口、全部已跟踪配置来源
bash bootstrap/brew.sh check # 共享/单机软件清单的独立检查
```

默认顺序：**Homebrew → Node/npm → Rust → oh-my-zsh → 配置链接**。
已有 Stow 时先预检冲突；Homebrew 安装后再复检。安装与升级分开，冲突不覆盖。
这用于首次准备或补齐环境，不是每次开机要运行的流程，也不自动启动后台服务。

配置链接入口是 `bootstrap/macosinit.sh`：`check` 判断能否安全安装，`verify` 核对是否已经来自本仓库，
`install` 才建立链接。真正的 Neovim 配置位于 `neovim/.config/nvim/`，Qwen 是 [独立可选包](qwen/README.md)。

HHKB/iTerm2 使用独立的 `bash bootstrap/desktop.sh check|install`，不由全量入口隐式恢复。
修改初始化脚本后执行 `bash bootstrap/test.sh`：只做隔离回归，不联网安装，也不在真实 HOME 重新 Stow。

密钥、认证、模型、缓存和生成物不入 Git；临时分析放 `tmp/`，不作为配置来源。
LiteLLM/PostgreSQL、SearxNG、Crawl4AI 的服务定义与启动配置归 `feipi-agent-kit`，本仓库只准备机器依赖。
