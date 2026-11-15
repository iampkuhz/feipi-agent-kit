# 新 Mac 完整初始化交付与验收

目标：在三天内完成部署能力，供新 Mac mini 使用。旧机集中导出必要私有资料，新机一次准备后执行安装、恢复、启动与验收；中途失败保留证据，可修复后续跑。最终完成必须有干净 macOS 的真实安装与使用证据，不能用替身回归或旧机已安装软件代替。

## 必须交付的范围

| 范围 | 完成证据 | 当前状态 |
| --- | --- | --- |
| 原 dotfiles 配置 | 57 个跟踪文件和 6 个新增文件完整迁入并已推送；执行权限一致 | 已核对 |
| Bash 3.2 与 UTF-8 | 实际预览、来源检查及 C/UTF-8 两组回归通过 | 本轮修复并通过 |
| 裸机前置 | 无 Git/Python 时使用系统 Bash；固定官方安装器、摘要校验、一次 sudo 授权 | 干净 macOS 26.6.2 中已真实无交互完成 CLT、Homebrew、Git、Python 安装及独立 check；完整工具链待验 |
| 工作台编排 | install 复用组件阶段及失败传播；Node/Rust 可供后续补全使用 | 干净 macOS 上四阶段真实通过：Brew 33 项、Node 26.13.1、Rust 1.100.0、oh-my-zsh/插件/补全；重复执行及最终整机验收待做 |
| 配置发布与来源 | 空白 HOME 首次/重复应用、33 个配置来源及内容、路径别名、冲突保全 | 干净 macOS 首次/重复 apply、doctor、全部 33 文件检查和真实 Zsh 的 Node/npm/Rust 通过；两种 locale 离线回归通过 |
| Neovim | 按锁恢复插件、原生构建、解析器/语言服务器与实际编辑功能 | 干净 macOS 上 31 个解析器可加载、5 个 Mason 服务安装、Lua LSP 初始化、Lua/JSON 格式化及 Markdown HTTP 预览通过；已补可重跑入口 |
| 常用软件 | 对照旧机 Brew 清单、近期命令频率、真实应用/脚本依赖 | 共享 CLI 清单补充；17 项应用/字体已在干净系统真实安装，清单检查通过；客户端账号和系统权限待验 |
| AI CLI/客户端 | 锁定现有兼容版本安装、登录状态、真实小任务 | 干净 macOS 上 Codex 0.162.1、Qwen 0.12.3、Claude 2.1.287、Qoder 1.1.54 安装及版本检查通过；客户端应用、账号和真实任务待验 |
| 私有资料 | 一次导出/校验/恢复；env 真源、私有配置与外部链接可恢复；不输出秘密 | 基础配置包 5 项回归通过；真实导出 10 文件，隔离 HOME 恢复及权限通过；完整业务包待补 |
| 数据一致性 | Multica 数据库/附件/密钥同批；OpenClaw SQLite 停写恢复；旧机不发生双主 | 复用现有备份能力，完整新机恢复待验 |
| 服务冷启动 | Podman VM、本地连接、Compose、镜像拉取、健康等待、模型实际请求 | 默认本机 Podman ensure 及三服务 10 分钟就绪等待已增加；43 项工作台、18 项服务回归通过；旧机 ensure 真实通过且未重启现有 VM；完整冷启动待验 |
| 图表和文档 | Mermaid、draw.io、PlantUML、PPT/PDF 实际生成并检查产物 | Chrome/LibreOffice 中英文 PDF 导出、字体嵌入及 PNG 渲染通过；Mermaid/draw.io/PlantUML/PPT 待验 |
| oMLX/语音 | 安装来源、模型清单、设置恢复、首次推理 | 待补 |
| 自启与重启 | Env Vault、Podman/受管服务、OpenClaw、Multica 按依赖恢复；完整重启后小任务 | Env Vault 已在干净系统真实加载、触发快照，完整关机开机后自动恢复及再次触发通过；终端 Node/Rust/Codex 复验通过。Podman 因该 VM 不支持嵌套虚拟化明确失败，其他组件待验 |
| 人工准备 | 所有必要 copy/export/授权命令集中成一次操作；运行中不逐项追问 | 待交付可执行命令包 |
| 最终端到端证明 | 干净 macOS、准确源码版本/环境指纹、逐阶段日志、真实产物、重复执行、失败恢复 | 未完成 |

## 本轮发现与修复

- Bash 3.2 在 UTF-8 环境把变量后相邻中文标点误解析为变量名：使用明确的大括号边界；测试同时运行 C 与可用的 UTF-8 locale。
- 原来源验证只接受源码链接：增加工作台运行副本识别，同时逐文件比较源码与副本内容；旧副本仍失败。
- macOS `/var` 与 `/private/var` 别名导致 doctor 误报：统一解析真实路径，增加别名回归。
- 工作台原先直接循环四个脚本，遗漏总入口前置检查及 Node/Rust 环境激活：复用总入口的依赖阶段；统一仓库的组件入口转到工作台发布。
- 干净系统实测发现：nvm 已安装 Node，但非交互 Bash 的 doctor 未激活它，误报缺少 Node；统一已有环境激活入口供安装、检查和 Agent CLI 使用，并让 doctor 核实 nvm default。两种 locale 的 Mac 四组回归通过，工作台新增该误报的回归；同一虚拟机复验继续进行。
- Agent CLI 在初始补全阶段之后安装，首次终端缺少 Codex 缓存；CLI 安装后复用原补全入口刷新，不更新已有插件版本。干净系统重复安装后四个版本保留，真实 Zsh 中 Codex 及缓存通过。
- Neovim 配置使用新版 Treesitter API，锁文件却仍固定旧 master；异常被 pcall 静默忽略，导致解析器没有安装。只更新该插件到已核对的 main 提交，显式共享解析器清单，补入已配置却遗漏安装的 Lua LSP；新增原生安装/验收入口。真实冷安装中发现 `:Lazy! restore` 可在构建失败时仍返回 0，因此现在检查任务错误和实际产物/服务，不能只看编辑器退出码。
- 本机 Brew 清单缺少 Homebrew 管理的 Git 和 jq：本轮实际安装 Git 2.56.1、jq 1.8.2；按其依赖更新 libunistring 1.4.2 → 1.5，安装 oniguruma 6.9.10。首轮直连 GHCR 瓶包出现 TLS 错误，改用已确认可访问 GHCR 的当前代理后安装成功。共享 Brewfile 33 项现已检查通过。
- webp 的旧安装记录仍依赖 libtiff，而当前 libtiff 依赖 webp；重装当前 webp 后记录已更新，循环告警消失。操作意外触发 Homebrew 连带升级，已中止后续升级，已发生的变更包括 jpeg-turbo、little-cms2、librsvg、Graphviz、OpenJPH、OpenEXR、JPEG XL、ImageMagick、yt-dlp 及部分图像/证书/Python 依赖；没有回滚卸载现有库。`brew missing` 通过，共享清单 check 通过；JPEG→WebP→TIFF→PNG、Graphviz SVG、PDF→PNG 实际产物通过。安装入口已额外禁用已安装 dependent 的连带升级，显式 upgrade 保留原能力。

工作台 43 项回归与服务 18 项回归通过，覆盖原生自启、Env Vault 幂等/权限/保全其他暂存项、Git 环境隔离、服务失败隔离与不支持虚拟化的提前失败边界。以上覆盖程序/配置层，不包含实际新机服务、账号和重启验收。

软件使用依据分开记录：Shell 历史覆盖 2025-08 至 2026-11，不能把全量频次当作最近使用。最近 30 天可定位 Podman 22 次、session-browser 12 次、SSH 11 次、tree/psql 各 1 次；Agent 自动调用通常不写该历史，因此还依据当前脚本依赖和运行服务补入 jq、ripgrep、PDF/Graphviz 工具、语言管理器与文档浏览器。session-browser 与相关 Java 项目仍需纳入后续完整环境恢复，不能仅安装 JDK 就认为功能已恢复。

追加盘点：Session Browser 的原生入口明确要求 JDK 25，应用清单已改为 `temurin@25`（不能用当前最新主版本替代）。旧机 7890 监听由 FlClash for oixCloud 0.9.2 提供；只恢复 `.env` 会让代理变量指向未启动的端口，代理客户端/私有配置恢复仍需补齐。oMLX 0.4.4 与三个本地模型（Qwen3-ASR-1.7B-4bit、Qwen3.5-0.8B-MLX-4bit、SenseVoiceSmall）已盘点，完整安装/恢复待做。

- 桌面应用安装中发现：Homebrew 会主动重置 sudo timestamp，使已有保活失效；新入口实际核实授权后通知 Homebrew 本轮已检查，安装期间保活，授权失效明确失败、不保存密码。16 项桌面依赖在验证机仅开始授权一次后安装成功；随后补装 Noto 中文字体，共 17 项。
- 文档实际图像复核发现：LibreOffice PDF 可抽出中文，但页面字形空白。已显式声明 Fontconfig 与 Noto Sans CJK SC，终端和非交互验收复用 Homebrew 标准字体配置；新验收同时检查中英文正文、字体嵌入和渲染页面，实际产物通过。JDK 25 编译与执行也通过。

## 当前真实验证条件

当前主机为 Apple M1、16 GiB 内存；建立验证机前可用磁盘约 77 GiB，目前约 19 GiB。没有预装 VM 工具。本轮安装的 Tart 2.41.1 及验证资料均在仓库外，不清理用户其他镜像或资料。

干净镜像 `ghcr.io/cirruslabs/macos-tahoe-vanilla@sha256:eeec54bfe1f076e27786c5d92b89187a05b1d109b5071eb2dcdf02d596e34640` 为 macOS 26.6.2 arm64，初始无 CLT/Homebrew，分配 2 CPU / 4 GiB，系统卷扩至约 80 GB。真实完成 CLT/Homebrew/Git/Python、共享工具链、四个锁定 CLI、17 项应用/字体和上述编辑器/文档验收。Neovim 与配置已用提交 `2521096` 完整复放并通过来源检查；桌面、字体、编辑器与基础配置已用提交 `5fb906d` 在完整关机开机后再次执行 install/apply/验收：全部通过，产物报告的 source_dirty=false。该复放没有再输入管理员密码，已有软件/CLI/插件版本保留。源码、环境指纹、私有阶段日志及产物保存于 `~/.local/state/feipi-workbench/new-mac-validation/`。

Env Vault 使用验证专用无秘密 `.env`，已通过原生加载、目标文件监听、完整关机开机后的自动恢复；不据此声称真实私有数据已完成迁移。本机 `kern.hv_support=1`，该 VM 为 0，Podman 在下载前明确拒绝并返回非零；M1 不支持该场景所需的嵌套虚拟化。完整容器服务/模型及实际新 Mac mini 的整机证明仍未完成，继续推进可独立交付的恢复和业务能力。
参考：[Tart 嵌套虚拟化边界](https://tart.run/faq/#nested-virtualization-support)、[Homebrew 无交互安装](https://docs.brew.sh/Installation#unattended-installation)、[OpenAI 固定版本 Codex 安装示例](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex)。
