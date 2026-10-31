# 首次安装与依赖顺序

从仓库根目录执行下文命令。这里的准备工作用于新 Mac 或缺失环境的机器，**不是每次开机都安装**。
日常开机不运行 bootstrap，也不自动启动服务。已有机器先用 plan 看影响，不要为了“验证”重装。

## 先准备并确认

| 顺序 | 需要准备什么 | 怎样确认 | 谁负责 |
| --- | --- | --- | --- |
| 1 | 普通用户账号、可用网络/必要代理、长期保存仓库的目录 | 不用 sudo 运行整个脚本；网络与认证由自己确认 | 人工 |
| 2 | Apple Command Line Tools | `xcode-select -p` 与 `xcrun --find clang` 都成功 | 人工执行 `xcode-select --install`，完成系统对话框 |
| 3 | Homebrew | 按 [官方说明](https://brew.sh/) 安装，用 `brew --version` 确认 | 人工 |
| 4 | Git、curl 与本仓库 | `command -v git curl`；仓库根目录有 Brewfile | CLT/系统工具与自行克隆 |
| 5 | 可选单机软件 | 按需复制 Brewfile.local.example 为 Brewfile.local | 人工选择，不从旧机软件快照生成 |

总入口会检查 macOS、普通用户、HOME、CLT 编译器、Homebrew/Git/curl 入口和共享清单。
它不测试网络、不打开 CLT 安装界面、不代装 Homebrew；前置条件不满足就停止。
发现命令入口不等于版本、网络或实际运行已经验收。

## 先看计划，再安装

```bash
bash bootstrap/run.sh plan  # 只读：看步骤、清单、已知冲突和未核实项
bash bootstrap/run.sh       # 补装缺失项；与显式 install 相同
```

plan 不联网、不执行 brew/nvm/rustup、不加载用户启动配置，也不创建 HOME 或日志。
已有 Stow 且 HOME 存在时会调用只读链接冲突模拟，否则显示“未核实”。已知阻塞返回非零；
退出 0 仅表示已检查范围内没有阻塞，不代表未核实项通过，也不是稍后可直接重放的执行凭证。

## 五步顺序及其原因

顺序在 `bootstrap/run.sh` 的固定阶段数组中定义，预览与执行共用，不另建可编辑的依赖配置。

| 步骤 | 脚本 | 需要先具备 | 完成后提供什么 |
| --- | --- | --- | --- |
| 1 | brew.sh install | Homebrew 与根目录清单 | Stow、Neovim、Python/uv、质量工具等共享依赖和已选择的单机软件 |
| 2 | node.sh install | Git/curl；保留已有 nvm default 或系统 Node | 可用 Node/npm，以及当前前缀中的 Prettier、prettierd、Yarn classic |
| 3 | rust.sh install | curl；已有 rustup 时核验工具链状态 | Rust 默认工具链与 rustfmt，保留已有版本 |
| 4 | ohmyzsh.sh install | Git；Node/Rust 已就绪便于生成补全 | oh-my-zsh、主题、插件和补全缓存 |
| 5 | macosinit.sh install | Stow；配置冲突已处理 | Zsh/Neovim 链接，正确旧链接复用 |

Node 和 Rust 相互没有安装依赖，这里固定串行以便排障；它们先于 oh-my-zsh 是为了补全完整。
配置链接本身不要求先启动 Neovim，但放最后能避免新终端先加载尚未准备好的工具配置。
单独执行 ohmyzsh.sh 时，生成补全所需的工具也应已在当前 PATH；全量入口会重新激活 nvm default。

已有 Stow 时，任何下载安装前先检查配置冲突；Homebrew 阶段结束后必须再检查一次。
若首次安装前还没有 Stow，则可能先完成 Homebrew 安装，随后才发现配置冲突；成功项会保留。
配置冲突由人工审查、备份并移走确认不用的文件，脚本不会自动接管。

## 安装后确认

新开终端后执行：

```bash
bash bootstrap/check.sh       # 静态检查、命令入口、全部已跟踪配置来源
bash bootstrap/brew.sh check  # 单独检查共享/单机 Homebrew 清单
```

Neovim 首次启动会联网下载 lazy.nvim/插件，Mason 也可能下载工具。使用 `:Lazy restore` 按锁文件恢复，
再按需执行 `:checkhealth`，实际打开代码与 Markdown 验证预览。命令入口或链接正确不等于这些功能已通过。
私密环境变量按自己的安全备份渠道恢复，不在仓库保存真实 `.env`。

HHKB/iTerm2 是独立可选分支：在 Brewfile.local 选择应用和字体后先安装软件，再执行
`bash bootstrap/desktop.sh check` 与 `bash bootstrap/desktop.sh install`。
尽量在首次配置应用前恢复，减少默认文件冲突；之后人工授予权限、选择 Profile 并测试按键。

服务、Skills、模型及业务项目回所属仓库恢复。LiteLLM/PostgreSQL、SearxNG、Crawl4AI 由
feipi-agent-kit 管理。完整换机和旧机退役前的人工验收仍以 [MIGRATION.md](../MIGRATION.md) 为准。
