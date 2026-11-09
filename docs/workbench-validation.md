# 工作台实机验收记录

## 2026-11-05：安装提速与 npm 依赖分离

当前索引及所有本地引用可达的 Git 历史均没有 `node_modules`；`.gitignore` 已排除该目录。本轮不改写历史。原问题是安装器将本地生成目录一起扫描、复制，再比较是否需要更新。运行依赖迁移验收后，已清理 Mermaid 源码中的旧依赖及本轮隔离测试缓存，正式共享缓存和全部发布备份保留。

### 同范围计时

以下为本机串行、隔离目标、相同五客户端与十技能的分段计时；当时目标名为 `make install-links`，现统一命名为 `make install-skills`。修复后计时时仍保留446 MB的源码依赖，避免把删掉依赖造成的加速算作安装器改进。

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| 空目标首次安装 | 24.349秒 | 5.955秒 |
| 全部50项未变的重复安装 | 39.927秒 | 两次为2.027、1.854秒 |
| 实际日常目录的 `make install` | 未作同路径旧版测量 | 2.511秒；新增0、更新0、跳过50、警告0 |

安装器排除技能根的 `node_modules`，发现技能及扫描共享依赖时也不进入该目录；比较过滤后的有效内容、权限、链接和来源，未变时不创建临时副本。保留注册表一致性、开发目录过滤、写入失败和第三方归属保护。没有用文件大小/mtime 相同代替内容验证。

### 固定依赖与实际运行

Mermaid v2 和 PPT v4 复用系统 Node；npm 包按各自清单、锁文件、系统/架构、Node 主版本与 ABI 准备本机共享缓存。首次使用执行 `npm ci`，相同版本跨客户端复用；只读检查不安装，不使用全局 npm 包替代锁定版本，也不在日常运行中执行 `npm update`。Mermaid 继续使用系统 Chrome，不下载 Puppeteer 浏览器。

实际安装检查发现 PPT 还隐式读取了父目录中的 `jszip`。本轮将已有锁文件中的3.10.1明确登记为直接依赖，并统一 Ajv、PptxGenJS 和 JSZip 的缓存解析；主生成链、诊断及关联入口同步。没有升级原有依赖版本。

- 安装器15项、Mermaid 46项、PPT依赖生命周期8项、PPT完整现有回归（含19项 P0）、workbench 6项与完整 Harness 通过。覆盖首次准备、防重、并发、锁/平台变化、损坏缓存、只读检查和失败隔离。
- Mermaid 六类结构化图、原生类图和均衡思维导图真实渲染、图包复核与实际看图通过；21项真实图包回归通过。隔离实拷副本首次自动准备并渲染，另一客户端在 npm 命令被阻止时仍复用同一缓存并渲染；本机已有 npm 下载缓存条件下分别耗时7.797秒和2.897秒。
- 日常 OpenClaw 安装副本实际生成 Mermaid 图并完成 review；日常 Codex 安装副本实际生成可编辑 PPTX，fast pipeline 为 pass，QuickLook/CoreText 渲染并看图通过。PPT 最终预览与已审阅的隔离实拷预览 SHA-256 同为 `eeaf825751df73220880397f69f1fb011fc9597109dde868595b482415d9c4be`。
- 五客户端中两个 Node 技能均不含 `node_modules`；`workbench diff skills` 无差异，统一 doctor 通过，Multica 当前实机证据仍匹配。两份受保护个人配置的 SHA-256 未变化。

首次改写前完整备份为 `~/.local/state/feipi-workbench/changes/20261105-094326-258323-skills`；后续发布同样留有备份，最终发布批次为 `20261105-100050-380382-skills`。程序、计时、安装与视觉证据在忽略目录 `tmp/install-runtime-fix/`，原始性能基线在 `tmp/install-performance/`。两个技能的新增依赖行为由程序和实际 CLI 验收，未声称全部行为用例均运行真实 Agent。实测为当前 Mac，PPT 验收为 fast 模式，不代替 strict 的编辑回环或 Linux 新机验收。

## 2026-11-05：Multica 协作闭环与主干回归

分支摸排时 main 为 `196ca69`。本地6个非 main 分支、GitHub 远端分支与 NAS 备份分支均已被其历史包含，没有遗漏的待合并提交。本轮在此基线上修复能力与补齐验收，不恢复已退役的 session-browser，不启用历史执行器。

### 修改与验证

| 范围 | 本轮结果 |
| --- | --- |
| Multica 任务入口 | `bind` 的活动任务、目录和归属检查移到写请求意图之前；预检失败不再污染 pending。`recover` 返回评论来源、parent、request-id 和附件定位；交接包拒绝错误字段类型 |
| Multica 确定性回归 | 55项通过，覆盖记录、绑定、静默进展、派发、交付、交接、恢复、防重、部分交付、任务认证、完整 runtime、目录、技能和必需 MCP 边界 |
| 协作 skill | `feipi-multica-manage-tasks` v2；收窄误触发，明确当前角色、触发评论、预检重试与未知请求恢复；测试入口复用组件契约，行为用例从3条扩至8条 |
| 实机 Codex | 新 run `01a1a77f-db0e-7214-822c-bb61d8bbfff5` completed；实际探针、五项任务身份、Agent/runtime/工作区/cwd、探针版本、唯一进度与交付评论、真实 parent、附件重新下载全部通过；Issue 为 in_review |
| 原生交互与防重 | 独立 Issue `01a1a781-beb4-79a5-932e-35d05d676d00`：record、bind、含真实提及的 note、deliver 重复同一 request-id 均返回原回执；只有3条动作评论、0个 run；交付附件下载一致，recover 不改变运行或回执 |
| bind 实机反例 | Codex run 活动时绑定失败且没有请求回执；该 run 完成后，原输入和原 request-id 绑定成功，总 run 数仍为5（包含4个历史执行） |
| 安装器 | 固定来源标记权限，比较链接时只核对链接目标，避免 umask 引起无内容变更的重复更新；12项隔离安装回归通过 |
| 组件回归 | Mac 离线 bootstrap、OpenClaw 原部署/安装/微信测试及 schema、OpenClash 模块契约通过；services 18项、workbench 6项通过；Harness 核对10个技能的结构、安装过滤和归属清理 |
| 视频 | 140项程序回归通过；真实本地媒体5项集成通过。SenseVoiceSmall 与 Qwen3-ASR-1.7B-4bit 均为首次推理（cache_reused=0），固定41秒合成样例的162个正文汉字逐字一致；不据此推算自然长音频准确率 |
| PPT | 19项 P0 及完整现有回归通过；分层架构样例生成原生可编辑 PPTX，通过包/布局检查和 QuickLook/CoreText 渲染，已实际查看全尺寸预览，无缺字、重叠或裁切 |
| 图表 | Mermaid 37项及真实架构图通过，已看图并用内置入口完成 review；draw.io 64项离线检查与6项真实 Podman 集成通过，代表图实际看图通过；PlantUML 122项通过，思维导图预览实际看图通过 |

### 发布与证据

skill v2 已发布到5个客户端及 Multica workspace；服务端只更新共享协作技能，没有更改角色模型或项目职责。运行代码在排空、停止监督器后发布并恢复守护。备份批次：`~/.local/state/feipi-workbench/changes/20261105-005535-859096-skills`、`20261105-005726-472714-multica`；workspace 技能更新快照为 `~/.local/state/multica/adaptation/rollback/20261104T165625333921Z.json`。安装器固定源码后串行复验 Harness 及真实 Codex 安装，10个受管技能全部跳过，第三方条目保留。

统一 `workbench doctor`、`private check` 和 Multica 静态检查通过；新运行证据的环境指纹已匹配。指纹新增执行代码摘要，后续运行代码变化也会使旧证据失效。`.mcp.json` 与 `.claude/settings.local.json` 的 SHA-256 保持不变。

程序日志、当前执行报告、下载证据、视觉审阅记录和代表产物在仓库忽略目录 `tmp/multica-acceptance-20261105/`；skill 评估范围记录在 `tmp/skill-evals/feipi-multica-manage-tasks/20261105/results.json`。实际验收回执与下载文件另保存在私有 `~/.local/state/multica/adaptation/`。

本次探针附件 `01a1a784-857a-7780-aa8a-ceda067bbf63` 的下载文件 SHA-256 为 `81185d5064951b90ff1313057b94b04b75da69759473c6bfc1f412dcbcbff3fc`，内容匹配上述新 run；不依赖验收工作目录中唯一一份本地文件。

本轮真实 Agent 评估覆盖 `fresh-task-delivery`；记录与预检恢复另有原生 CLI 集成，其余行为用例由隔离契约回归覆盖，未声称8条用例均已运行真实 Agent。handoff 的命令语义已回归，未运行 LexiFlow 专用审批链；必需 MCP、停用执行器、跨机器和整机恢复仍按原专项边界处理。

首次图表检查出现 Podman info 超时、SSH 握手重置及 renderer 无响应；之后只读复查连接恢复，复验通过。未定位该瞬态问题的永久根因，首轮失败与后续通过日志均保留。期间原生 CLI 的个别历史查询也曾超时，使用活动运行与单 Agent 查询确认同一 run 继续执行，没有因观察超时重新派发。

## 2026-11-04：全部分支集成与复验

本轮合入 Multica 任务技能、Mac/Multica/OpenClaw/OpenClash 组件、workbench/develop 入口与备份恢复能力，以及 video oMLX 转写。保留原提交历史。11月1日已正式发布的 Multica 声明与运行脚本较分支源码更新，经发布清单核对后回收；当前仅启用 Codex Builder 和 LexiFlow 三个专用角色，其他执行器实现保留。

| 验证 | 本轮结果 |
| --- | --- |
| 研发回归 | 10组检查全部通过：Mac、Multica、OpenClaw、OpenClash、Skills Harness、services、workbench、安装器、Multica skill、video ASR 契约。修复后补跑 Multica 31项与 workbench 6项，全部通过；安装器11项、服务18项、oMLX HTTP契约19项通过 |
| 统一检查 | `./workbench doctor`、`./workbench private check`、`./workbench multica verify` 返回0，受管运行文件一致，LiteLLM就绪且配置来自运行副本 |
| 终端与编辑器 | 实际登录Zsh发现 compdef/nvm，Node v26.11.1；实际Neovim启动并返回验收标记 |
| OpenClaw | 本机 Gateway 模型请求返回 `FEIPI_INTEGRATION_MODEL_OK_20261104`，provider=qwen，model=litellm-code-openai；4.257秒；未请求外部投递 |
| OpenClash | 路由器真实请求 Baidu/Google 均HTTP200；连接表分别命中 Domestic→DIRECT、PROXY→地区优先→香港自动 |
| Multica | 排空后停止监督器、备份发布、重新启动。新 Codex Builder run `01a1a5b4-4017-74a0-821f-28ab412ca441` completed；实际probe、五项任务身份、note/deliver、in_review与附件下载全部通过。下载JSON与最新run报告一致，报告SHA-256为 `44b2e1287390678045e2d89890ad0a33647a2df170b67c91aaee889ff4b832f7` |
| Skills发布 | 备份后更新5个客户端中的video skill，其余45个受管安装项跳过；第三方技能保留 |

本轮修复：doctor按启用执行器检查依赖和版本，Codex模式不再访问已移除的LiteLLM/OpenClaw机器字段；验收角色随声明选择，缺失绑定明确失败；附件下载不再追加原生命令不支持的JSON参数，报告必须匹配最新执行，验收未通过返回非零。回收持续监督器、共享VM启动进程组隔离、停止等待与局部发布能力，新增隔离HOME及模拟监督测试。workbench diff/doctor现在同时检查运行代码，配置回收白名单未扩大。

本轮原始日志与摘要位于私有 `~/.local/state/feipi-workbench/integration-20261104/`，研发检查位于仓库忽略目录 `tmp/workbench-integration/`。运行发布备份保留在 `~/.local/state/feipi-workbench/changes/`；回收前源码与第一次运行发布也均有备份。`.mcp.json`、`.claude/settings.local.json` 的摘要与本轮开始时相同。

实际任务验收覆盖当前Codex通路，未重新启用或验收停用的Qoder/LiteLLM执行器；MCP实际调用保持not-tested。路由器未主动断网注入故障，Mac mini整机迁移尚未执行。以下10月31日记录为历史证据，不能当作本轮复测。

## 2026-10-31：本机切换

本次保留 feipi-agent-kit 原 Git，未另建仓库或重新初始化历史。原 dotfiles、multica-ops、两份 OpenClaw 仓库均保留；原未提交工作在首次完整工作区备份中可恢复。引入的源码和未提交改进按原职责归入组件，运行环境通过显式副本接管。

### 实际来源与效果

| 范围 | 切换前 → 切换后 | 实际证据 |
| --- | --- | --- |
| Mac | HOME 依赖独立 dotfiles → `~/.local/share/feipi-workbench/mac` | 新 Zsh PTY 输出 `WORKBENCH_TERMINAL_OK`；compdef、nvm、OpenClaw 补全缓存正常。真实 Neovim 加载 basic/keybindings，写入验收文件，输出 `WORKBENCH_NVIM_OK` |
| 桌面配置 | 本机 Karabiner 调整先回收，随后受管实拷；iTerm2 Dynamic Profile 实拷 | Karabiner CLI 返回当前 `HHKB-test`；运行中 iTerm2 的偏好中出现 `Dotfiles` 及受管 Dynamic Profile 文件路径。保留原默认 Profile |
| Skills | 源码运行目录链接 → 五个客户端用户目录实拷 | 50 个受管安装项，第三方内容保留；runtime 文件摘要一致。OpenClaw 真正读取 `feipi-writing-refine-text` 及其 4 份参考，执行改写并交付问题清单；Multica 真正调用任务协作技能 |
| LiteLLM | 容器挂载 Agent Kit 源码 → 工作台 services 运行副本 | 实查 `/app/config.yaml` bind 来源为运行副本；readiness healthy、数据库连接正常；下述两个 Agent 实际模型请求成功 |
| Multica | 原独立 ops 源码 + 旧 OpenClaw 来源 → 统一组件 + 既有 `~/.local/share/multica/ops` | machine.json 的 agent_kit/openclaw_source 已更新；声明 plan 无差异；本次新任务执行、回写、上传、下载全部完成 |
| OpenClaw | npm 2026.9.2 + 原私有资料 → 版本保持、配置由统一组件管理 | 7 个受管文件及 env 链接匹配；Gateway RPC 正常；原 memory 目录实际发现 180 个文件并读取其中已有文件；Gateway 模型交互成功，备份重启后同一会话再次回复确认 |
| OpenClash | 路由器现有地区模块 → 同内容由统一仓库接管 | SSH 原生 YAML 合并与当前核心 `-t` 成功；实际模块 SHA-256 与仓库一致；7 项运行策略检查通过；国内/国外实流量见下 |

两份 OpenClaw 源码关系已经按 Git 验证：旧 `2b2c99e` 是新 `735a186` 的祖先，落后 9 个提交；原运行配置来自新仓库，但 Multica 曾引用旧路径，现已改正。并未把两份仓库当作两个独立运行实例合并数据。

活动 HOME 链接、自启动、运行绑定中原 dotfiles/multica-ops/OpenClaw 来源依赖已检查。Qwen 的 output-language.md 已改成受管实拷；8 个指向不存在的旧 agent-skills 公共资源链接已备份并移除。`~/.qwen/settings.json.orig` 是保留的历史备份链接，不是加载入口；含 env/认证/codingPlan 的真实 settings.json 保留私有，不整份覆盖。

### 代表性任务与联网

Multica 新验收 Issue：`01a19174-65d3-7714-9933-8ddee0ba8882`。执行 `01a1917a-abf1-742f-8bf1-b98397d61bb4` 使用 LiteLLM Coder、隔离 OpenClaw runtime，实际运行 probe，task 身份字段齐全，计算值 5；随后 note、deliver，将 Issue 留在 `in_review`。附件 `01a1917c-15f3-73c3-aff2-cf38d97c81c4` 已通过原生 CLI 重新下载，JSON task_id 与该执行一致，SHA-256 为 `6554318b4f441afe346294b08f13702259ebdda5893ee404cad4cf3f4f883dab`。不是复用旧 Issue/旧附件或只检查 completed。

OpenClaw 原资料交互 run：`dda93a81-230c-4423-8bb3-aa55eb9a26c6`，会话 `f40a3ba2-57e4-4d98-9d13-41c9c3b76f26`，provider qwen、模型 litellm-code-openai、实际工具 read/exec，36.899 秒完成。最终备份恢复运行后，同一会话的 run `7d1f1f65-7042-40b7-993b-71bf49ffcff3` 回复 `WORKBENCH_FINAL_OK`。

路由器 iStoreOS 24.10.8、OpenClash 0.48.011、Mihomo alpha-oix-bf37525。通过路由器代理（显式地址及现有私有认证，不经过本机 FlClash）请求：

| 请求 | 响应 | 核心连接表实际命中 |
| --- | --- | --- |
| https://www.baidu.com/ | HTTP 200，完整读取 | RuleSet Domestic → Domestic → DIRECT |
| https://www.google.com/ | HTTP 200，完整读取 | RuleSet PROXY → Proxy → 地区优先 → 香港自动 |

可重跑 `./workbench service openclash verify`。没有主动切断节点模拟所有地区故障，也没有把策略 API 可访问当作联网证据。

### 备份与恢复验证

- 首次源码/未提交文件/运行配置：`~/.local/state/feipi-workbench/backups/20261031-175613`，保留各仓库工作树归档、Git patch/status、HEAD 和受保护配置摘要。
- OpenClaw 最终停写批次：`~/.local/state/feipi-workbench/openclaw-backups/offline-20261031-183125.ZtkgnV`。摘要通过；停写时 4 个主要 SQLite 通过；解到新的私有临时目录后，包括工作区历史试验和锁库在内的 23 个 SQLite 全部 integrity_check=ok；workspace 文件和 env 链接保留，env 归档实际内容与原文件一致。完成后只删除该临时恢复目录，原数据不动。macOS tar 的 AppleDouble 元数据不当作第二份 env。
- Multica 批次：`~/.local/state/multica/backups/20261031T180756893694`。排空并停 daemon，原工具短暂停 Web/API；91 个文件摘要通过。在无网络临时 PostgreSQL 中恢复成功，当时记录 Issue 39、评论 37、附件 9、Agent 8；这些计数是备份时间点，之后验收新增任务不在旧批次里。
- OpenClash 最小批次：`~/.local/state/feipi-workbench/openclash-backups/20261031-181654-680257`。压缩包 22,748 bytes，对比保留的原完整包 37,869,578 bytes；摘要和完整 tar 流通过。只含配置、订阅与覆写，排除 core/GeoIP/cache，均不进入 Git。路由器原模块/UCI 保存在 `/root/feipi-workbench-backup-20261031-181655`。
- 工作台回退测试在临时 HOME 中验证了文件、目录、符号链接、原先不存在路径的恢复；公开回收路径白名单与秘密拒绝在写入前生效。当前机器没有为测试而故意回滚全部组件或中断家庭网络。

### 本次发现和修复

Neovim 原通用 prettierd 规则会让纯文本保存超时，已限定到支持的文件类型，真实保存复验通过。OpenClaw 补全缓存缺失已用现有生成器补齐。Multica 只读预检失败原本留下 pending 回执，现改为预检通过后才记远端请求意图；网络结果不明仍保留 pending，不盲目重放。验收工具现要求下载的附件内容匹配最新执行，防止旧附件误判。LiteLLM 慢启动采用有界 readiness 等待，不重复重建数据库。

首次新 Multica 任务在本地配置发现阶段超时，尚未请求模型；直接复查配置命令约 2 秒完成。确认失败且无活动 run 后明确续接成功。没有声称已找到该瞬时超时的永久根因，失败记录保留，恢复步骤可用。

仓库回归：Mac 离线 bootstrap 通过；Multica 14 项；服务 18 项；安装输出 11 项；工作台边界 5 项；OpenClaw 原部署/安装/微信测试及当前 schema 通过；Harness 的规则、命令、registry、manifest 和 10 个技能的布局/安装过滤全部通过；OpenClash 另执行路由器原生合并与核心校验。

### 证据位置与边界

原始结果都在本机私有 `~/.local/state/feipi-workbench/`：`doctor-final.log`、`private-final.log`、`multica-evidence-summary.json`、`downloaded-artifacts/`、`openclaw-evidence-summary.json`、`openclaw-final-result.json`、`openclaw-restore-check.json`、`openclash-connectivity.json` 以及测试日志。公开文档只保留摘要，不复制记忆正文、订阅、密钥或登录态。

本次完成代表性 Multica 路径，未重新验收所有 Agent/MCP 组合；旧能力矩阵的 fingerprint 过期提示保持真实，不改成全通过。Telegram/微信外部投递未发送测试消息。iTerm2 验证到运行应用已加载 Profile，未自动切换用户当前窗口；Karabiner 未模拟物理键盘按键。所要求的实际终端与应用操作由 Zsh、Neovim 以及应用读取的当前配置共同证明。

`.mcp.json` 与 `.claude/settings.local.json` 的 SHA-256 与首次备份完全一致。未向远端 Git 推送，也未自动外传私有备份。
