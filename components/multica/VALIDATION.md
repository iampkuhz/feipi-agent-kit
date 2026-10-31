# 本机验收记录

## 2026-10-31：单主机适配落地

本节为当前状态，后文保留历史部署证据。实际入口见 [操作手册](docs/adaptation-runbook.md)、[适配清单](docs/adapter-inventory.md) 和 [Mac mini 流程](docs/mac-mini-migration.md)。

- 新增声明配置、私有机器绑定、plan/apply/verify/doctor、统一任务入口与共享 Skill；既有 6 个 Agent 保留职责，新建 Qoder Worker；7 个受管 Agent 的并发均为 1。首次应用 15 项，重复应用 0 项，读回零差异。不创建小队或新的项目流水线控制器。
- 精确核对 daemon/runtime/provider/profile；runtime 切换和 UI 字段漂移受计划摘要约束；派发前再次核对预期 runtime、model、thinking、并发及 runtime_config，漂移时拒绝启动。写前有私有快照，局部失败不自动删除对象。源配置与后台副本分开发布。
- 认证、缺任务字段失败、不泄漏测试 token、同 provider 身份区别、完整技能内容漂移、分页排空检查、静默/派发区别、成功请求防重及响应丢失后拒绝盲重试：12 个确定性测试通过。模拟服务失败不等于真实上游故障演练。
- Agent Kit 新技能结构校验及安装检查通过；Codex/Qoder/个人 OpenClaw 均安装完整技能。共享协作技能和视频技能的说明、脚本、引用及依赖文件内容一致。既有安装器同步了本仓库其他登记技能的现有版本，未改其源码；重复安装三个客户端均新增 0、更新 0、跳过 10，其他来源条目保留。
- Codex CLI 0.162.1、Qoder CLI 1.1.54、OpenClaw 2026.9.2、Multica 0.6.3 为本次实际组合。额外发现 Homebrew Qoder 1.1.68 与用户目录 1.1.54 并存；机器绑定固定到已实测的用户目录版本，doctor 核对路径和版本，不自动切换。

| 独立验收 | 结果与证据 |
|---|---|
| TASK-37 / Codex Builder | run `01a190ff-37e1-72ea-9101-7324763ad39d` completed；实际执行 probe，五项任务契约齐全，凭据类型为任务 token；进度和交付评论 source_task_id/author_id 与实际 run 一致，上传 2 份附件，in_review |
| TASK-38 / LiteLLM Coder | run `01a19101-0b2f-7092-a87b-701831df03c4` completed；相同任务身份与回写验证通过，上传报告，in_review；实际 OpenClaw 任务配置 channels=[]、mcp_names=[]、状态目录为隔离目录 |
| LiteLLM 路由 | 本次运行时间窗口网关明细汇总 `litellm-code-openai → openai/qwen3.7-plus` 共 15 次 success；只查询路由、模型、状态和数量，未读取 prompt 或凭据 |
| TASK-39 / Qoder Worker | run `01a19104-255d-763c-807d-cf4401226688` completed；执行 probe、任务凭据回写和报告附件通过，in_review；Qoder 采用账户默认模型，原生 runs 的 usage 未给出实际模型名，不冒充已固定/核实该模型 |
| Codex → Qoder 交接 | TASK-37 的第二个 run `01a19106-b7f3-767a-9bf1-47ada0e17082` 由 Qoder 完成；读取 Codex Issue 评论、下载附件并核对本地 JSON，上传 cross-tool-handoff.md，回复正确触发线程，不依赖 Codex 私有聊天 |
| 静默与单次派发 | 初次证实 Backlog assign 不启动；修正为静默归属 + 唯一 @交接。重复相同 request-id 返回原评论回执，首轮仅 1 个 run。TASK-39 终态后发送含真实 @Agent 的 /note，run 数仍为 1 |
| 持久交付 | 临时移开 Codex 本地原 JSON 后，原生 attachment download 仍能下载；SHA-256 为 `c588fd1b2bfb08bb0eb3dbb9cabc8312d2b09bdf01228345efc427970b834bda`，与原文件一致；已还原本地文件 |

首次派发前的仅分配实验没有 run，保留其回执和说明作为语义证据；未冒充那次分配已执行。三个 Issue 保持 Review，未自动代替用户验收。

启动依赖检查发现既有 LiteLLM 容器停止，已启动既有 DB/Proxy，不更换模型或镜像。新 supervisor 只启动机器声明的既有 Podman VM、本栈与两个依赖，等待 readiness 再启动 daemon。daemon 的 OpenClaw 能力发现环境与 wrapper 一致，实际隔离任务未继承个人 MCP；未重启个人 Gateway。最终受管 daemon 已恢复，活动任务为零。

最近数据备份批次为 `~/.local/state/multica/backups/20261031T162711758133`，91 个文件校验通过。

一致性备份已包含数据库、附件、服务密钥、机器参考绑定、防重回执、声明及经清单核对的已发布运行副本。无网络临时 PostgreSQL 恢复验证通过：issue=39、comment=37、attachment=9、agent=8（包括历史归档对象）；临时容器已清理。恢复检查采用 TCP readiness，避免误判 PostgreSQL 初始化临时 Unix socket。Podman exec 在 dump 目录检查阶段曾输出 attach reset 提示，命令返回成功；完整隔离 pg_restore 和记录数核对验证了备份可读。

未执行：Mac mini 真机迁移、整机重启/FileVault 登录测试、真实上游模型错误或断网中断演练、桌面 MCP 专项后台调用。MCP 实际调用在验收记录中为 not-tested，必需 MCP 的自动派发当前会明确拒绝。视频技能安装一致性不等于隔离 OpenClaw 已完成视频处理验收。未执行 LexiFlow 正式工作包、外部消息发送、远程推送或 Git 提交。


2026-10-19 开始部署，2026-10-20 完成本机验证（Asia/Shanghai）。范围为用户明确授权的本地部署、Codex/OpenClaw 协作与迁移准备。

## 部署与登录

- Multica CLI v0.6.3 / `18fa9f728a9e25f2465df2789631edb2a75442ad`，官方 archive SHA-256 校验通过。
- 三个 ARM64 镜像按 digest 锁定，在已有 Podman VM 中建立独立 multica 项目、数据库卷与附件卷。
- Web 为 http://localhost:3000，API 为 http://localhost:8080；只绑定 loopback，数据库不发布宿主端口。Web HTTP 200，readyz 的 db/migrations 均为 ok。
- 用户网页及 CLI 登录成功；工作区“Feipi 任务中心”，slug 为 feipi，任务前缀为 TASK。
- 未配置 SMTP/Resend，验证码只在本机日志，页面“已发送邮件”不能证明投递。保持 production，未使用固定验证码；已设置本人邮箱白名单并关闭新注册。
- 服务秘密在现有 env vault，投影 0600；重复生成未轮换秘密。全局源权限收紧为 0600，写入前副本保存在 vault 私有 backups。
- CLI 自动升级关闭，daemon 和两个 Agent 并发均为 1。

## 任务闭环

| 验收 | 实际结果 |
|---|---|
| TASK-2 / Codex 首次执行 | 修复金额 float 精度错误；原测试 3 项中 2 项失败，交付代码用原测试独立复测后 3 项通过 |
| TASK-2 / 评论续接 | 同一 Issue 补充 README；保留 Decimal 修复，测试仍通过，交付附件可下载 |
| TASK-3 / OpenClaw 独立执行端 | 真实读取 TASK-2 标题、状态、负责人及两个已完成 run，回写结果；在守护环境中再次查询成功 |
| 原有 OpenClaw Gateway | 通过 CLI 真实查询 TASK-2；Gateway PID 25181、18789 端口及 RPC 保持正常，没有重启 |
| TASK-7 / Gateway 录入与串行重试 | 首次创建未分派任务；同一标题与来源的第二次请求返回原 TASK-7，独立查询只存在 1 条 |

三个验收 Issue 已在独立复核后标记 Done。后续事项为 TASK-4（Mac mini 切换）、TASK-5（可选邮件投递）、TASK-6（Gitea 回调），没有自动派发。

串行重试结果不等于并发幂等保证。没有新增 Telegram 消费者或发送 Telegram/邮件；真实 Telegram 收发仍需实际渠道消息验收，不能用 Gateway RPC 查询代替。

## 执行隔离与运维

- Codex Builder 使用 Codex App Server、独立任务状态及显式空托管 MCP；没有修改全局 Codex 配置。
- 原生 OpenClaw local 首次失败，原因是个人 Gateway 占用同一状态目录。已改用 OpenClaw Multica 自定义 runtime，状态在 ~/.local/share/multica/openclaw-state。
- 隔离配置从 OpenClaw 声明仓库只取模型与默认模型，env 只投影所需三项 provider 变量；不带个人渠道、插件或记忆。关闭 memory 插件后再查询，没有先前的无关 embedding 错误。
- 原 OpenClaw workspace 新增 TOOLS.md 任务管理说明；声明仓库、Gateway 配置入口、技能安装和个人记忆未切换。
- local.multica.personal LaunchAgent 安装成功。空闲 daemon 被终止后自动恢复，恢复后的环境也完成了 OpenClaw 查询；内置 autostart 保持禁用。
- macOS 实际拒绝 launchd 读取 Documents 中的脚本。通过 install-runtime.py 将受管运行副本发布到 ~/.local/share/multica/ops 后启动成功，没有扩大系统隐私权限。

## 一致性备份与隔离恢复

- 批次：~/.local/state/multica/backups/20261020T001159507140。
- 暂停 Web/API 写入，pg_dump custom format 成功并通过 pg_restore 目录检查；附件与服务密钥投影同批保存，8 个文件校验通过，随后恢复原服务。
- 独立、无网络、临时 PostgreSQL 容器中完成 pg_restore；users=1、issues=7、comments=7、attachments=2，与正式实例一致。
- 恢复测试容器已停止并自动移除，正式数据卷保留。恢复包含秘密，只保存在本机私有目录，没有上传 NAS 或提交 Git。

## 已解决的配置问题

- Docker 旧 GHCR 认证导致公开镜像 403；采用独立匿名配置，原认证保留。VM 单次拉取使用宿主代理后成功，没有更改引擎全局代理。
- Compose 让 shell 变量覆盖 env-file，初次发现其他项目的 POSTGRES_PASSWORD 影响投影；已清理 Compose 进程环境，并将专用数据库密码与本服务投影对齐，其他数据库未改动。
- v0.6.3 setup 会覆盖已有 profile 字段；已重新设置并核实并发和禁自动更新，日后重新登录使用 login。
- CLI 回调地址曾被页面状态读取带出。已轮换本服务 JWT 签名密钥并重新登录；旧签名请求 HTTP 401，新签名 HTTP 200。数据库密码及 VCS 加密密钥未因此轮换，记录中不保存 token。

## 尚未实测或执行

- Mac mini 实机切换、整机重启/FileVault 解锁后的恢复；当前 LaunchAgent 为用户登录后运行。
- Podman VM 冷启动、所有 Documents 业务目录的后台访问权限；本次使用独立验收仓库，业务任务优先 Git 资源独立检出，本地资料权限逐项验证。
- SMTP/Resend 投递、Gitea webhook/私网 HTTPS、真实 Telegram 消息端到端。
- 未创建 Autopilot、Squad、定时通知或公网服务；未推送代码或备份到远程。

## 2026-10-23：接入本地 LiteLLM Agent

- LiteLLM `http://localhost:4000/v1` readiness 正常；使用现有 OpenAI 客户端虚拟密钥查询模型可见性，没有更改 LiteLLM 服务、模型路由或密钥权限。
- 在独立 OpenClaw Multica runtime 新增 LiteLLM Coder / LiteLLM Analyst，各并发 1。模型映射分别是 `litellm/litellm-code-openai` 和 `litellm/litellm-token-plan-deepseek`，没有跨模型 fallback。
- 本次采用 128000 上下文预算、8192 最大输出作为初期保守配置，不把它们当作上游模型最大能力声明。
- OpenClaw 2026.9.2 的多 Agent schema 要求显式 ownership，已使用 `agents.ownership=explicit` 与 `agents.entries`。原 OpenClaw Assistant 显式选择 `main`，避免新增 Agent 后依赖隐式默认；main 的 workspace 保留原路径。heartbeat 无 owner 的提示与未启用后台 heartbeat 一致。
- 投影改为直接读取全局 env vault 中所需三项变量，0600；修改前的私有配置回退副本在 `~/.local/state/multica/config-backups`。个人 Gateway 配置与 env 的前后 SHA-256 相同，PID 25181 保持运行。

| 验收任务 | 结果 |
|---|---|
| TASK-8 / LiteLLM Coder | run `01a16460-2ea1-796e-a6de-83def9d24871` completed，无 error；读取临时 worktree 两个文件，真实执行原有 unittest，3 项中 1 通过、2 失败、退出码 1，正确指出 float 精度缺陷并建议 Decimal；本次要求只读，没有要求修复基线 |
| TASK-8 / 独立复核 | 在未修改的 smoke-project 执行 `python3 -B -m unittest -v`，结果同为 1 通过、2 失败；这与旧 TASK-2 下载的修复附件 3/3 通过是两份不同输入，不应混称 |
| TASK-9 / LiteLLM Analyst | run `01a16462-ab18-7bc9-819b-a3039d4a5ad1` completed，无 error；通过 CLI 真实查询 TASK-2，正确报告 done、Codex Builder、总 run=2 且 completed=2 |
| LiteLLM 独立链路证据 | 同一验收时间窗口的明细请求记录显示：`litellm-code-openai → openai/qwen3.7-plus` 12 次 success；`litellm-token-plan-deepseek → openai/deepseek-v4.1-flash-1017` 8 次 success。仅提取请求时间、路由、模型、状态与 token 数，未记录 prompt、密钥或完整 spend log |

两个 Issue 都先进入 Review，再由本次配置工作独立复核并标记 Done。声明在 `config/litellm-agents.json`，同步脚本 `scripts/sync-litellm-agents.py` 重复执行复用同一组 Agent UUID。原 Codex Builder 未切换到 LiteLLM；没有部署或下载新的本地模型，LiteLLM 仍转发到已有上游。接入字段对照了 [OpenClaw 官方 LiteLLM 文档](https://docs.openclaw.ai/providers/litellm) 和本机安装版 schema。

### 当前范围：仅编码模型

用户随后明确选择“先只配置编码模型”。已归档 LiteLLM Analyst，并从 `config/litellm-agents.json`、隔离 OpenClaw Agent 注册与 provider 模型声明移除分析角色；同步脚本不会重新创建它。LiteLLM Coder 的原 UUID、模型、并发和验收结果保留。TASK-9 与分析 Agent 的历史运行记录保留用于追踪；没有删除 LiteLLM 全局 DeepSeek 路由或历史数据。本节取代上文两个 Agent 同时启用的范围。
