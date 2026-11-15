# 新 Mac 完整初始化交付与验收

目标：在三天内完成部署能力，供新 Mac mini 使用。以 Git 跟踪的配置、清单和脚本为交付主体；软件、依赖、镜像和可生成内容由脚本准备。用户集中准备必要私有配置和授权，本地资料目录由用户按提供的有线连接、SSH/rsync 命令直接复制。最终完成必须有干净 macOS 的真实安装与使用证据。

## 交付边界

本次核对提交 `7bb826e`：Git 跟踪 898 个文件，内容合计 4,525,063 字节（4.32 MiB）；其中 `components/mac/` 为 77 文件、265,970 字节（约 260 KiB），包含配置、脚本、测试和文档。最大跟踪文件为 265,330 字节，没有超过 1 MiB 的跟踪文件。这是该版本内容的统计，不包含 Git 历史、工作区未跟踪文件或仓库外资料。

此前 GB 级迁移包是仓库外的私有资料副本，不是 Git 交付内容，也不再作为新机初始化的前置条件。后续验收关注 Git 声明是否齐全、脚本能否安装和启动、配置是否生效、实际功能能否运行；不再为普通资料目录进行打包、全量遍历、容量盘点或逐文件验收。必要目录和传输命令见 [本地目录直传](workbench.md#本地目录由用户直接传输)。数据库仍保留原生一致性导出要求，但由用户执行导出和传输，不合并成整机迁移大包。

私有配置只保留必要输入。Codex 目录现只导出实际引用的模型名称、固定程序版本和摘要，由新机原生程序精确重建；未引用的旧目录不导出。真实基础配置导出为 10 文件、21,371 字节，另有 2,314 字节清单，合计约 23 KiB；不包含模型权重、项目资料和数据库。下文全量归档的实测记录仅保留为历史证据，不代表后续交付方式。

## 必须交付的范围

| 范围 | 完成证据 | 当前状态 |
| --- | --- | --- |
| 原 dotfiles 配置 | 57 个跟踪文件和 6 个新增文件完整迁入并已推送；执行权限一致 | 已核对 |
| Bash 3.2 与 UTF-8 | 实际预览、来源检查及 C/UTF-8 两组回归通过 | 本轮修复并通过 |
| 裸机前置 | 无 Git/Python 时使用系统 Bash；固定官方安装器、摘要校验、一次 sudo 授权 | 干净 macOS 26.6.2 中已真实无交互完成 CLT、Homebrew、Git、Python 安装及独立 check；完整工具链待验 |
| 工作台编排 | install 复用组件阶段及失败传播；Node/Rust 可供后续补全使用 | 干净 macOS 上四阶段真实通过；首次 Node 26.13.1 暴露 CLI 兼容问题，新机现固定 Node 24.22.3，实际安装/CLI 及 OpenClaw 依赖检查通过；最终整机验收待做 |
| 配置发布与来源 | 空白 HOME 首次/重复应用、33 个配置来源及内容、路径别名、冲突保全 | 干净 macOS 首次/重复 apply、doctor、全部 33 文件检查和真实 Zsh 的 Node/npm/Rust 通过；两种 locale 离线回归通过 |
| Neovim | 按锁恢复插件、原生构建、解析器/语言服务器与实际编辑功能 | 干净 macOS 上 31 个解析器可加载、5 个 Mason 服务安装、Lua LSP 初始化、Lua/JSON 格式化及 Markdown HTTP 预览通过；已补可重跑入口 |
| 常用软件 | 对照旧机 Brew 清单、近期命令频率、真实应用/脚本依赖 | 共享 CLI 清单补充；17 项应用/字体已在干净系统真实安装，清单检查通过；客户端账号和系统权限待验 |
| AI CLI/客户端 | 锁定现有兼容版本安装、登录状态、真实小任务 | 四个锁定 CLI 安装/版本检查通过；迁入设置的 Qwen 真实文件任务通过，Claude 经现有 LiteLLM 隔离转发通过；Codex/Qoder 已确认需要新机登录，整套尚未通过 |
| 私有配置与本地资料 | 必要私有配置集中准备；目录提供直传命令；不把用户资料容量作为初始化验收指标 | 实际新配置包约 23 KiB，干净 macOS 连续两次恢复通过；Codex 原生读取自动重建的三个模型，元数据摘要完全一致；主机 70 项工作台回归通过；用户复制目录后核实所需功能 |
| 数据一致性 | Multica 数据库/附件/密钥同批；OpenClaw SQLite 停写恢复；旧机不发生双主 | 当前 PostgreSQL 备份已在无网络临时容器恢复；OpenClaw 在实际新 HOME 恢复、重建依赖和发布配置，4 个 SQLite、7,289 个业务文件核查通过，Gateway 未启动；完整业务切换待验 |
| 服务冷启动 | Podman VM、本地连接、Compose、镜像拉取、健康等待、模型实际请求 | 默认本机 Podman ensure 及三服务 10 分钟就绪等待已增加；64 项工作台、18 项服务回归通过；旧机 ensure 真实通过且未重启现有 VM；完整冷启动待验 |
| 图表和文档 | Mermaid、draw.io、PlantUML、PPT/PDF 实际生成并检查产物 | Chrome/LibreOffice 中英文 PDF 导出、字体嵌入及 PNG 渲染通过；Mermaid 原生 Chrome 的 SVG/PNG、可编辑 PPTX 与 QuickLook/CoreText 渲染及实际看图通过；旧机现有 draw.io/PlantUML 服务的中文 SVG/PNG 出图及实际看图通过；两者新机本地容器冷启动与 PowerPoint 编辑回环待验 |
| oMLX/语音 | 安装来源、模型清单、设置恢复、首次推理 | 三个模型及完整设置已从迁移包恢复；文本及 Qwen3-ASR/SenseVoiceSmall 语音推理通过；本轮原生 start、登录自启及重启后文本请求通过；菜单栏显示准备仍按集中清单执行 |
| 自启与重启 | Env Vault、Podman/受管服务、OpenClaw、Multica 按依赖恢复；完整重启后小任务 | Env Vault 加载、快照及电源重启恢复通过；终端 Node/Rust/Codex 复验通过。Session Browser/oMLX 未手动启动即 HTTP 200，oMLX 控制状态及真实文本请求通过。Podman 因该 VM 不支持嵌套虚拟化明确失败，其他组件待验 |
| 人工准备 | 所有必要 copy/export/授权命令集中成一次操作；运行中不逐项追问 | [集中清单](new-mac-prepare.md)已列出源码/配置、独立备份、用户直传、代理过渡、安装与授权；25 个文档命令块通过系统 Bash 3.2 语法检查；实体双机执行与最终切换待验 |
| 最终端到端证明 | 干净 macOS、准确源码版本/环境指纹、逐阶段日志、真实产物、重复执行、失败恢复 | 未完成 |

业务恢复补验：Multica 原入口隐含依赖 Docker CLI/Compose 和旧机的 `/var/run/docker.sock`，共享清单现补入两项（加上 Fontconfig 后共 36 项），隔离配置自动发现 Homebrew Compose 插件并按机器绑定派生 Podman 当前 socket。干净 macOS 的空白 HOME 已真实执行 Docker Compose 5.7.1；本机现有服务只读查询通过，未重启服务。58 项 Multica 回归通过，现有 `20261101T102523041588` 备份也已恢复至独立、无网络的临时 PostgreSQL，四张表记录数一致并清理临时容器。它证明现有备份可恢复，不能代替当前数据的新备份或新机容器冷启动。

原生应用补验：FlClash for oixCloud 0.9.3、oMLX 0.4.4、Session Browser 0.5.2 官方发布包已核对摘要，DMG 身份、版本及签名通过；干净 macOS 首次安装与重复保留通过。Session Browser 已用合成 Codex 会话完成原生扫描、索引和 HTTP 页面验证；oMLX 已用当前三个模型完成文本与两套语音请求。语音输入由系统 say 生成，不读取个人资料；验收使用独立数据目录、随机 loopback 端口并清理自有进程。已用提交 `8665934` 再次复放安装与全部功能验收，报告 source_dirty=false。代理账号/节点同步尚未完成，不能将应用安装通过表述为代理可用。

OpenClaw 冷安装发现并修复：业务配置和本地 skill 来源写死旧 HOME；首次插件安装被尚不存在的成长日记插件路径阻断；安装清单还指向 `94fcd48` 已删除的专利 skill。配置改用原生 HOME 插值，本地来源使用 HOME/组件相对路径，删除失效声明。依赖用同一状态目录中的临时空配置先准备，再发布完整声明；原生 npm 插件安装目录由配置父目录决定，不能把临时配置放系统临时目录。新增仅准备依赖模式，不要求业务凭据、不启动 Gateway。干净 macOS 已真实安装 OpenClaw 2026.9.2、Qwen provider 2026.9.2、微信插件 2.4.10 和 8 项 skills；两项插件在临时配置移除后仍可检查，新 HOME 解析通过。递归分发排除开发目录，C/UTF-8 路径及内容回归、全 10 项 registry 安装边界检查通过；业务请求和重启尚未完成。

原生状态恢复已补验：`restore-state openclaw` 先检查同版本 npm 程序，恢复 SQLite、会话、记忆和资料，重建随 HOME/程序位置变化的链接。旧 BSD tar 的根 AppleDouble 元数据经格式检查后跳过，新备份禁用该附加元数据；未知外部链接、损坏数据库和已有目标均保全失败。实际验证机恢复后重建依赖、`workbench apply openclaw`、原生 runtime/config 检查通过，Qwen、微信和成长日记插件均 loaded；`launchctl` 确认 Gateway 未加载。7,289 个业务文件内容一致；两个 Agent 数据库和微信引用库共 115 张表逐行一致，主状态库 108 张表中的 104 张保留全部原行，其余四张仅在原生命令运行后更新配置、健康检查、诊断和版本元数据。WAL/SHM 按 SQLite 语义核对，不要求瞬态辅助文件字节相同。Node 24 下又完成依赖、runtime 和 config 检查。

模型恢复已补验：`restore-state omlx` 在临时目录检查三个模型的配置和权重后发布，已有模型目录不覆盖。真实验收使用提交 `f9a9ef1`，source_dirty=false，从迁入设置读取新 HOME 的模型目录，并使用用户别名 `qwen3.5-text-fast` 完成文本请求，以及 Qwen3-ASR/SenseVoiceSmall 两套语音请求；输入仍为系统生成的合成语音。新状态恢复七项回归及原有工作台检查通过。

CLI 真实任务补验：Node 26 与 Qwen 0.12.3 内置 dispatcher 的接口不兼容，实际捕获 `UND_ERR_INVALID_ARG: invalid onError method`；CLI 错误退出码却为 0。新机 Node 基线固定为 24.22.3，已有默认版本保留，相关安装回归通过；同一迁入设置无需代理 CLI 覆写即可完成文件工具任务。机制参考 [Node 维护者的接口兼容说明](https://github.com/nodejs/node/issues/63757)。新增 `bootstrap/verify-agents.sh` 复用四个 CLI 原生非交互入口，逐项在独立目录生成并核对文件，180 秒限时，任何失败最终非零；假成功、单项失败后继续及链接产物保全均有回归。

提交 `ded5b1f` 的完整 CLI 演练中，Qwen 通过，Codex 暴露模型目录 JSON 漏迁，Claude 等待未启动的本地 LiteLLM，Qoder 明确返回未登录。已补入两份 Codex 模型目录白名单，真实重新导出并恢复 12 文件配置包。使用提交 `315ce35` 复验，source_dirty=false，Codex 已能运行至官方接口鉴权，失败为未登录的 401；Claude 通过只绑定 loopback 的 SSH 转发使用旧机 LiteLLM 后，按原设置完成精确文件任务。7890 代理和 4000 LiteLLM 转发均为隔离验证条件，不能代替新 FlClash 登录或新机容器冷启动证明。Codex、Qoder、Figma MCP 的新设备授权仍须纳入集中准备。64 项工作台回归在验证机通过。恢复、推理、CLI 原生日志及逐文件摘要已集中保存于 `~/.local/state/feipi-workbench/new-mac-validation/native-state-inference-evidence-5a6vv6uc/`。

按小配置交付边界补验：提交 `b5eec47` 不再导出完整 Codex 派生目录。基础配置加清单实际为 23,685 字节，已在干净 macOS 的全新隔离 HOME 中连续恢复两次，source_dirty=false；程序从锁定版内置目录重建三个模型，规范化 JSON 摘要与旧机一致，原生 `codex debug models` 成功读取迁入配置及其目录。未引用的旧 LiteLLM 目录没有生成，env vault 相对链接及 0600 权限通过。此项不需要登录、不调用模型接口，不能替代真实任务鉴权。报告保存在 `~/.local/state/feipi-workbench/new-mac-validation/configuration-native-e3jahbr1/native-restore-report.json`。

图表补验：首次 Mermaid 运行明确失败于浏览器发现，已安装的 Homebrew Chrome 没有 PATH 入口，原脚本遗漏 macOS 应用发现。提交 `f4c8061` 改用 AppKit 应用注册信息；同一个原图包复验成功，source_dirty=false，真实 SVG/PNG、覆盖及几何通过，实际查看中文和两条关系后登记 `final_status=success`。Python 依赖由 uv 隔离准备，固定 npm 包使用共享缓存，不传旧依赖。Mermaid 46 项离线回归、治理结构与平台静态扫描通过；Linux 未在本轮实测。PPT 使用同一新机的固定 npm 依赖、原生可编辑单页验收输入和 QuickLook/CoreText 生成 1800px 图像，自动门禁与实际看图通过；未做 PowerPoint 编辑回环。证据位于 `~/.local/state/feipi-workbench/new-mac-validation/document-native-esieuzpx/`。

独立状态恢复补验：提交 `f670cbe` 为 OpenClaw 停写备份记录原 HOME，`restore-state openclaw` 直接校验四个原生输出与摘要，不再要求项目、资料或模型的全量包。70 项工作台回归与 OpenClaw validate 通过；越界摘要、损坏归档、已有目标均保全失败。干净 macOS 上用合成 SQLite 和记忆完成原生备份、独立恢复、真实 OpenClaw 配置校验，source_dirty=false，两条原始记录及记忆保留、HOME/env 链接正确，重复恢复拒绝覆盖，Gateway 全程未加载。它验证机制，不替代用户实际业务切换；报告为上述证据目录中的 `standalone-report.json`。`private check` 同时移除递归资料统计，只检查必要路径及 env 定义。

集中迁移补验：新增 `workbench private prepare-migration/verify-migration/restore-sources`，复用原生数据库备份，不复制热数据目录。真实批次 `full-20261115-prepare-03` 包含基础配置 10 文件、6 个 Git 项目（含 env vault 历史和 Session Browser 两份 stash）、家庭健康 102 个原件、房地产 363 个原件、FlClash 官方 ZIP、三个 oMLX 模型及业务备份。总计 906 文件、3.98 GiB，目录权限 0700，清单和摘要通过。当前 Multica 恢复后 issue/comment/attachment/agent 分别为 119/697/307/9，与同批记录一致；LiteLLM 原生恢复成功，public schema 有 75 张表。两者均使用无网络临时容器并清理；没有据此宣称新机容器冷启动通过。

干净 macOS 恢复演练使用提交 `13e0276`，source_dirty=false，通过只读共享读取完整业务包，在独立 HOME 恢复全部 6 个 Git 项目和 2 个资料目录。HEAD、暂存/未暂存补丁的原生反向检查和变更统计、两份 stash、1,571 项归档文件内容均通过；Git 对象摘要缩写会随仓库对象数量变化，因此没有用补丁显示字符串相等代替内容检查。4 个 OpenClaw SQLite 从真实归档恢复后完整性通过；再次运行在写入前拒绝覆盖。54 项工作台回归在该机全部通过。真实首次演练暴露初始化默认分支 `master` 阻止导入同名分支，已仅对新建临时仓库允许原生 fetch 更新 HEAD，显式 reset 后才发布目录，并补回归。私有日志、报告和同批数据库恢复证据保存在 `~/.local/state/feipi-workbench/new-mac-validation/migration-13e0276-evidence/` 及相邻记录中。该业务包保全导出当时的源码工作区；验收工具的版本单独记录。已有项目的实际私有 MCP 覆写项保留原样，仍需结合新机最终 HOME 和准备步骤核对路径。

真实备份还发现：Gateway 停止后微信 SQLite 会删除 WAL 辅助文件，原只读检查因此失败。已改为停写后的原生读写检查与 WAL checkpoint；损坏、锁定仍报错，退出时恢复 Gateway。当前 4 个数据库完整性检查及备份通过，失败测试也验证恢复启动与不输出秘密。模型采用标准 gzip 低压缩级别，减少大模型打包耗时；未打完的测试批次带 `INCOMPLETE`，不能用于恢复。

## 本轮发现与修复

- 集中清单连续执行补验：首次安装在子进程中创建 nvm/全局 CLI，当前 Bash 需要再次激活 `environment.sh` 才能立即恢复 Codex 模型配置。隔离 HOME 中先复现未刷新时失败且未写入目标，再刷新后经真实工作台恢复成功；Codex 本身使用离线替身，此项不代表账号或模型请求验收。Multica 恢复清单补齐锁定镜像拉取、数据库就绪等待及已有业务表检查；系统 Bash 3.2 中用离线替身验证成功顺序和失败中止，Compose 原生帮助确认参数可用，尚未据此宣称新机容器冷启动通过。
- Bash 3.2 在 UTF-8 环境把变量后相邻中文标点误解析为变量名：使用明确的大括号边界；测试同时运行 C 与可用的 UTF-8 locale。
- 原来源验证只接受源码链接：增加工作台运行副本识别，同时逐文件比较源码与副本内容；旧副本仍失败。
- macOS `/var` 与 `/private/var` 别名导致 doctor 误报：统一解析真实路径，增加别名回归。
- 工作台原先直接循环四个脚本，遗漏总入口前置检查及 Node/Rust 环境激活：复用总入口的依赖阶段；统一仓库的组件入口转到工作台发布。
- 干净系统实测发现：nvm 已安装 Node，但非交互 Bash 的 doctor 未激活它，误报缺少 Node；统一已有环境激活入口供安装、检查和 Agent CLI 使用，并让 doctor 核实 nvm default。两种 locale 的 Mac 四组回归通过，工作台新增该误报的回归；同一虚拟机复验继续进行。
- Agent CLI 在初始补全阶段之后安装，首次终端缺少 Codex 缓存；CLI 安装后复用原补全入口刷新，不更新已有插件版本。干净系统重复安装后四个版本保留，真实 Zsh 中 Codex 及缓存通过。
- Neovim 配置使用新版 Treesitter API，锁文件却仍固定旧 master；异常被 pcall 静默忽略，导致解析器没有安装。只更新该插件到已核对的 main 提交，显式共享解析器清单，补入已配置却遗漏安装的 Lua LSP；新增原生安装/验收入口。真实冷安装中发现 `:Lazy! restore` 可在构建失败时仍返回 0，因此现在检查任务错误和实际产物/服务，不能只看编辑器退出码。
- 本机 Brew 清单缺少 Homebrew 管理的 Git 和 jq：本轮实际安装 Git 2.56.1、jq 1.8.2；按其依赖更新 libunistring 1.4.2 → 1.5，安装 oniguruma 6.9.10。首轮直连 GHCR 瓶包出现 TLS 错误，改用已确认可访问 GHCR 的当前代理后安装成功。共享 Brewfile 33 项现已检查通过。
- webp 的旧安装记录仍依赖 libtiff，而当前 libtiff 依赖 webp；重装当前 webp 后记录已更新，循环告警消失。操作意外触发 Homebrew 连带升级，已中止后续升级，已发生的变更包括 jpeg-turbo、little-cms2、librsvg、Graphviz、OpenJPH、OpenEXR、JPEG XL、ImageMagick、yt-dlp 及部分图像/证书/Python 依赖；没有回滚卸载现有库。`brew missing` 通过，共享清单 check 通过；JPEG→WebP→TIFF→PNG、Graphviz SVG、PDF→PNG 实际产物通过。安装入口已额外禁用已安装 dependent 的连带升级，显式 upgrade 保留原能力。

早期自启与服务修复时，工作台 43 项回归与服务 18 项回归通过，覆盖原生自启、Env Vault 幂等/权限/保全其他暂存项、Git 环境隔离、服务失败隔离与不支持虚拟化的提前失败边界。后续工作台回归已扩至上述 64 项；这仍不能代替实际新机服务、账号和重启验收。

软件使用依据分开记录：Shell 历史覆盖 2025-08 至 2026-11，不能把全量频次当作最近使用。最近 30 天可定位 Podman 22 次、session-browser 12 次、SSH 11 次、tree/psql 各 1 次；Agent 自动调用通常不写该历史，因此还依据当前脚本依赖和运行服务补入 jq、ripgrep、PDF/Graphviz 工具、语言管理器与文档浏览器。session-browser 与相关 Java 项目仍需纳入后续完整环境恢复，不能仅安装 JDK 就认为功能已恢复。

追加盘点：Session Browser 的原生入口明确要求 JDK 25，应用清单已改为 `temurin@25`（不能用当前最新主版本替代）。旧机 7890 监听由 FlClash for oixCloud 0.9.2 提供；只恢复 `.env` 会让代理变量指向未启动的端口，新设备代理账号和节点同步仍需补齐。oMLX 0.4.4 和三个当前模型已完成上述安装、恢复与推理。

- 桌面应用安装中发现：Homebrew 会主动重置 sudo timestamp，使已有保活失效；新入口实际核实授权后通知 Homebrew 本轮已检查，安装期间保活，授权失效明确失败、不保存密码。16 项桌面依赖在验证机仅开始授权一次后安装成功；随后补装 Noto 中文字体，共 17 项。
- 文档实际图像复核发现：LibreOffice PDF 可抽出中文，但页面字形空白。已显式声明 Fontconfig 与 Noto Sans CJK SC，终端和非交互验收复用 Homebrew 标准字体配置；新验收同时检查中英文正文、字体嵌入和渲染页面，实际产物通过。JDK 25 编译与执行也通过。

图表补验发现并修复：PlantUML 首次容器启动原来绑定所有网卡，现限定 `127.0.0.1:8199`；15 项预检回归通过。draw.io 的 `--existing-only` 没有启动服务，但回执原来总写 `podman_once`，现准确记录选定策略并防止健康响应覆盖它；离线回归 65 项通过，6 项真实容器用例另计。两个现有旧机 renderer 各生成一次中文图并实际看图，保留 XML/PUML、SVG、PNG、报告及独立视觉复核；未重启旧容器，不能把该结果计作新机冷启动。

PPT 演示入口仍引用搬迁前的样例路径与已经移除的 builder 接口，曾生成零页文件却返回成功。开发入口已移到 `tests/`，复用当前 Render Plan 编译器与原生后端，完整生成三类页面，缺样例或失败返回非零；真实 OpenXML 校验三页均含原生文本，既有 19 项 P0 与完整回归通过。追加预览实测发现旧脚本只导出第一页且 JSON stdout 混入进度文字；现先导出 PDF，再由已有 Poppler 逐页转 PNG，校验实际页数并只登记本轮文件，三页 PNG 实际生成且 JSON 可解析；系统 Bash 3.2 再次渲染通过，报告只登记本轮三张图、排除旧图；看图发现当前旧机 LibreOffice 缺少楷体中文，记录为兼容预览告警，不能宣称该预览视觉通过，也不更改最终主题字体。主业务 pipeline 的新机出图证据仍独立保留。

已将提交 `aff8b23` 通过小型 Git 增量包复放到干净 macOS 验证机，报告 `source_dirty=false`：当前开发演示入口实际生成三页含原生文本的 PPTX，PlantUML 15 项预检回归通过。验证机这次未执行容器冷启动或 PPT 视觉验收，旧机的 LibreOffice 对照结果也不算新机证据。

早期验证机 oMLX 原生 `start` 已真实尝试：应用进入首次 Shell PATH 确认弹窗，45 秒后 CLI 因控制 socket 尚未建立失败。进程采样定位到 `promptForShellPathExport` / `NSAlert runModal`，没有重复启动或杀进程，也没有将其归咎于模型。当时该路径尚未通过完整重启验收，后续修复与复验见下文。

后续首次启动修复：`771cedd` 在 Bash/Zsh 预留 oMLX 原生入口；`61ce740` 兼容 nvm 原生不带 `v` 的默认别名，修复新终端找不到 OpenClaw，并在安装时通过 Apple `stapler` 附加固定应用包缺失的公证票据；`7bb826e` 修复 SSH `doctor` 未探测 Homebrew 标准位置的误报。Mac 四组回归在 C/UTF-8 下通过，75 项工作台回归通过。验证机使用 `7bb826e`、`source_dirty=false`，在 Gatekeeper 开启的状态从原包重新安装 oMLX，实际执行附加票据分支并通过只读 check；新终端直接执行 OpenClaw 2026.9.2、SSH doctor 通过。原生应用 `start` 25.8 秒成功、控制接口报告 running、模型列表 HTTP 200，实际界面确认本机 8037 运行；不等同于独立 spctl 评估命令已通过，其此前拒绝与后续超时日志仍保留。

`85b5333` 复用现有启动管理为已安装的 Session Browser 增加独立 loopback 任务，不经 Podman 或额外 shell。实际首次服务启动用时约 36 秒，早期 30 秒探测超时保留为失败记录；随后 HTTP 200、仅监听 127.0.0.1:8848。完整关机开机后，在未手动启动 Session Browser 的情况下再次得到 HTTP 200。OpenClaw 后安装的补全刷新已加入集中命令；恢复环境中缓存实际生成，后续新终端通过。

oMLX 两个自启开关已按固定版本的真实界面设置：Dock 原生 Open at Login 有勾号，Settings → Server 的自动启动开启，JSON 确认原先 false 已变为 true。macOS 菜单栏显示提示仅关闭，未使用要求完全磁盘访问的 Auto-Fix。上述报告位于验证机 `~/.local/state/feipi-workbench/validation/first-launch.XygPwyf3/`。此前验证机 Gatekeeper 曾关闭，本轮已恢复开启；其他应用的既有安装记录不能代替默认安全策略下首次打开的验收。

重启期间曾因主机可用空间降至约 116 MiB 而无法创建命令临时文件，该次重启结果不计通过。已停止验证机，仅删除本轮重新安装时保留的公开应用副本、可重建安装包及自有 Homebrew/Tart 下载缓存，可用空间恢复约 6.5 GiB。个人资料、模型和历史私有归档未做遍历或删除。

清理后最终电源重启补验：仍为 `7bb826e`、`source_dirty=false`，内核启动时间已改变，Gatekeeper 开启，oMLX 自动启动设置为 true。新启动后没有执行 start 或手动启动会话浏览器：8848 页面与 8037 模型列表均 HTTP 200，控制接口 status=ok/state=running，原别名 `qwen3.5-text-fast` 的真实文本请求 HTTP 200 且结果非空。两个端口均只监听 loopback。完整报告为上述目录的 `final-reboot-report.json`；它证明这两项原生服务的后台自启和业务，不代替 Podman 冷启动、其他组件或全部 GUI/账号验收。

## 当前真实验证条件

当前主机为 Apple M1、16 GiB 内存；建立验证机前可用磁盘约 77 GiB。没有预装 VM 工具。本轮安装的 Tart 2.41.1 及验证资料均在仓库外，不清理用户其他镜像或资料。原生恢复和安装验证后可用空间曾降至约 839 MiB，已用 Tart 原生入口仅删除本轮下载的指定摘要 OCI 缓存，运行中的验证机、完整业务包和原始备份保留，可用空间回升至约 4.7 GiB。

干净镜像 `ghcr.io/cirruslabs/macos-tahoe-vanilla@sha256:eeec54bfe1f076e27786c5d92b89187a05b1d109b5071eb2dcdf02d596e34640` 为 macOS 26.6.2 arm64，初始无 CLT/Homebrew，分配 2 CPU / 4 GiB，系统卷扩至约 80 GB。真实完成 CLT/Homebrew/Git/Python、共享工具链、四个锁定 CLI、17 项应用/字体和上述编辑器/文档验收。Neovim 与配置已用提交 `2521096` 完整复放并通过来源检查；桌面、字体、编辑器与基础配置已用提交 `5fb906d` 在完整关机开机后再次执行 install/apply/验收：全部通过，产物报告的 source_dirty=false。该复放没有再输入管理员密码，已有软件/CLI/插件版本保留。源码、环境指纹、私有阶段日志及产物保存于 `~/.local/state/feipi-workbench/new-mac-validation/`。

Env Vault 的开机验证使用专用无秘密 `.env`；之后真实私有配置已恢复至验证机，但真实 vault 历史和全业务重启仍需完整流程验收。本机 `kern.hv_support=1`，该 VM 为 0，Podman 在下载前明确拒绝并返回非零；M1 不支持该场景所需的嵌套虚拟化。完整容器服务及实际新 Mac mini 的整机证明仍未完成，继续推进可独立交付的恢复和业务能力。
参考：[Tart 嵌套虚拟化边界](https://tart.run/faq/#nested-virtualization-support)、[Homebrew 无交互安装](https://docs.brew.sh/Installation#unattended-installation)、[OpenAI 固定版本 Codex 安装示例](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex)。
