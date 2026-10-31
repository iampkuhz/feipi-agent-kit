# Repository Guidelines

## 项目结构与模块组织
- `bootstrap/`：macOS、Homebrew、Rust 等初始化脚本。
- `docs/setup.md`：首次准备、固定依赖顺序与人工验收；`docs/maintenance.md`：日常命令、重试与维护边界。
- `zsh/`：Zsh 配置（`.zshrc`、`.zsh_config/`），通过 GNU Stow 管理。
- `neovim/`：Neovim 配置根目录 `neovim/.config/nvim/`（Lua、`init.vim`、格式化配置、`lazy-lock.json`）。
- `qwen/`：可选的 Qwen 配置，单独按其 README 安装。
- 根目录 `Brewfile`：共享依赖；忽略的 `Brewfile.local`：单机选择；`Brewfile.local.example`：按需示例。
- `tmp/`：临时目录，不作为配置来源。
- `desktop/`：HHKB/Karabiner 和 iTerm2 的小型 JSON 配置；不保存应用缓存、源码或凭据。

## 构建、测试与开发命令
- `bash bootstrap/run.sh`：新 Mac 初始化；先检查 macOS、CLT、Homebrew，再按 Homebrew、Node/npm、Rust、oh-my-zsh、配置链接的顺序执行。
- `bash bootstrap/run.sh plan`：只读预览，共用实际执行的阶段顺序；缺少 Stow/HOME 时链接检查标为未核实，不自动准备。已知阻塞非零，0 不代表未核实项通过。
- `bash bootstrap/macosinit.sh check|install`：Zsh/Neovim 唯一链接入口；整体模拟后执行 Stow，正确链接可重复使用，冲突不覆盖。
- `bash bootstrap/macosinit.sh verify`：只读验证默认包内全部 Git 跟踪文件的实际来源；不同于安装前 Stow 冲突模拟，不检查运行时缓存或可选 Qwen。
- 链接入口仅使用仓库 Stow 规则，屏蔽用户级 `~/.stowrc`，避免 adopt/override/ignore 改变安全边界。
- `bash bootstrap/brew.sh check|install|upgrade`：只管理根目录共享/单机 Homebrew 清单；安装默认不升级、不 cleanup。
- `bash bootstrap/node.sh install|upgrade`：先准备 Node，再补装 npm 工具；upgrade 只升级 npm 工具。
- `bash bootstrap/rust.sh install|upgrade`、`bash bootstrap/ohmyzsh.sh install|upgrade`：补装和升级分离，不向 shell 启动文件追加内容。
- `bash bootstrap/check.sh`：只读检查 Bash 语法、可用时的 ShellCheck、关键命令和配置来源，不联网、不加载用户启动文件、不启动服务。
- `bash bootstrap/desktop.sh check|install`：独立检查/恢复两份桌面配置，使用普通副本并拒绝覆盖，不由全量入口隐式执行。

## 编码风格与命名规范
- Bash 脚本优先使用 `set -euo pipefail`；缩进 2 空格；函数用 `snake_case` 命名。
- Lua 配置遵循 `stylua` 默认风格；模块路径放在 `neovim/.config/nvim/lua/`。
- 新脚本文件使用小写、可读的命名（如 `bootstrap/tooling.sh`）。

## 配置新增与注释要求（重要）
- 任何新增配置必须附带中文解释说明，避免只写“裸配置”。
- 当出现首次使用的配置格式/语法（如某类 `zstyle`、`eval "$(tool init)"`、`export` 组合写法等），必须添加中文注释说明其语义与用途。
- 你对 Bash 命令熟悉，但对 Bash 脚本语义不熟悉：脚本里出现的关键流程（条件判断、循环、子进程、环境变量持久化等）要用简短中文注释解释。
- 注释尽量多，可以连续多行都有注释。但是对于非常简单、重复出现的格式，不需要重复注释

## 测试与验证
- `bash bootstrap/test.sh`：统一离线入口，要求已有 Stow/Zsh/Git/ShellCheck/shfmt；隔离测试环境，缺依赖不安装。
- `bash bootstrap/test-bootstrap.sh`、`bash bootstrap/test-completion-cache.sh`：替身验证计划零安装、阶段顺序与失败传播，以及补全生成失败时保全旧缓存。
- `bash bootstrap/test-links.sh`：在临时 HOME 中离线验证首次/重复安装、正确旧链接与冲突保全。
- `bash bootstrap/test-node.sh`：离线验证 NVM/Node/npm/npx 首次懒加载后保留 nvm 函数，以及无 nvm 时的系统 Node 回退。
- 每个脚本分别运行语法检查：`for script_file in bootstrap/*.sh; do bash -n "$script_file" || break; done`；`bash -n bootstrap/*.sh` 不会检查全部文件。
- 格式检查：`shfmt -i 2 -d bootstrap/*.sh`；ShellCheck 可用时执行 `shellcheck bootstrap/*.sh`。
- 日常通过仓库根 `workbench` 使用运行副本；源码链接仅用于显式调试。离线测试不操作真实 HOME；用户明确要求切换时，备份后逐组件应用并做真实终端/应用验收。
- 保全任务开始前的未提交修改，按文件职责区分归属，工具或网络缺失如实报告。

## 提交与 PR 规范
- 现有提交信息简短直接（多为中文）；保持风格一致，不强制 Conventional Commits。
- PR 需包含：变更目的、影响范围（如 `zsh/`、`neovim/`）以及合并后的手工步骤。

## 安全与配置提示
- 避免提交密钥、认证状态和生成物；`.env` 保存在本机，示例文件仅放占位值。
- JSON 配置和 Neovim `lazy-lock.json` 必须可追踪，不用全局 `*.json` 隐藏真实配置。
- 可重建服务保存配置、Compose 与启动脚本，不提交或导出 Podman 镜像、容器和虚拟机。
- 当前桌面迁移仅限 Karabiner 和 iTerm2，不扩展到其他编辑器或中优先级设置。
- LiteLLM/PostgreSQL、SearxNG、Crawl4AI 的 Compose、启动和自启配置由 `feipi-agent-kit` 管理，不在本仓库重复维护。
- 初始化脚本会安装 Homebrew 和 Rustup 相关工具，仅在可信机器上运行。
