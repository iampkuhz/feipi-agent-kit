# 首次安装与依赖顺序

从 `feipi-agent-kit` 根目录使用工作台入口。这里的准备工作用于新 Mac 或缺失环境的机器，**不是每次开机都安装**。
日常开机不运行 bootstrap，也不自动启动服务。已有机器先用 plan 看影响，不要为了“验证”重装。

## 先准备并确认

| 顺序 | 需要准备什么 | 怎样确认 | 谁负责 |
| --- | --- | --- | --- |
| 1 | 普通用户账号、可用网络/必要代理、长期保存仓库的目录 | 不用 sudo 运行整个脚本；网络与认证由自己确认 | 人工 |
| 2 | Apple Command Line Tools | `xcode-select -p` 与 `xcrun --find clang` 都成功 | 人工执行 `xcode-select --install`，完成系统对话框 |
| 3 | Homebrew | 按 [官方说明](https://brew.sh/) 安装，用 `brew --version` 确认 | 人工 |
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
./workbench apply mac       # 备份后发布独立运行副本
```

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
配置链接本身不要求先启动 Neovim，但放最后能避免新终端先加载尚未准备好的工具配置。
单独执行 ohmyzsh.sh 时，生成补全所需的工具也应已在当前 PATH；全量入口会重新激活 nvm default。

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

Neovim 首次启动会联网下载 lazy.nvim/插件，Mason 也可能下载工具。使用 `:Lazy restore` 按锁文件恢复，
再按需执行 `:checkhealth`，实际打开代码与 Markdown 验证预览。命令入口或链接正确不等于这些功能已通过。
私密环境变量按自己的安全备份渠道恢复，不在仓库保存真实 `.env`。

HHKB/iTerm2 所需应用与字体已列入 `components/mac/Brewfile.apps`；完整新机安装需要显式安装该清单，
`workbench apply mac` 会备份后复制配置。独立组件调试仍可使用 `bootstrap/desktop.sh check|install`。
尽量在首次配置应用前恢复，减少默认文件冲突；之后人工授予权限、选择 Profile 并测试按键。

服务、Skills、模型及业务项目回所属仓库恢复。LiteLLM/PostgreSQL、SearxNG、Crawl4AI 由
feipi-agent-kit 管理。完整换机和旧机退役前的人工验收仍以 [MIGRATION.md](../MIGRATION.md) 为准。
