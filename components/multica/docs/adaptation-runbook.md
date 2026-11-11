# Multica 与本机 Agent 的操作流程

当前默认仅绑定 Codex runtime 与4个 Codex 角色，其他执行器的实现按需启用。`acceptance.py` 只验收当前声明中的代表角色；已声明但没有机器绑定会停止，不用历史结果补齐。

配置仓库维护期望配置；Multica 保存任务、评论、附件与运行记录。当前主力为 MacBook，未来由 Mac mini 接替。一个 daemon 负责长期运行；MacBook 切换后只保留临时交互入口。

## 文件与职责

| 内容 | 真源/运行位置 | 维护规则 |
|---|---|---|
| Agent 职责、模型选择、并发 | `config/agents.json`、`config/instructions/` | 保留项目规则，机器参数用 `${...}` 绑定 |
| 能力要求和兼容组合 | `config/capabilities.json`、agents 的 compatibility | 区分静态检查与任务实际调用 |
| 机器身份、路径和依赖 | `~/.config/multica-selfhost/machine.json` | 0600；不进入 Git；迁机重建 daemon/runtime |
| 技能正文 | Agent Kit 的 `skills/integration/feipi-multica-manage-tasks` | 安装完整技能后同步工作区单文件入口，入口注明已发布资源目录 |
| 运行副本 | `~/.local/share/multica/ops` | 只能从源码发布，不手改 |
| 变更快照和请求回执 | `~/.local/state/multica/adaptation` | 私有；备份；不提交；并发锁限本机 |
| 数据库、附件、服务密钥 | Multica 私有存储、env vault 的最小投影 | 同批备份，工具登录另行认证 |

`config/agents.json` 只管理列出的字段与机器明确绑定的 UUID。不会按 provider 或显示名模糊接管其他对象，不删除额外技能、MCP、小队或其他项目资源。Qoder Worker 为通用入口，不加入 LexiFlow 正式审批链。

## 日常交互

在 Codex、Qoder、个人 OpenClaw 中使用共享 Skill：`$feipi-multica-manage-tasks`。新聊天重新加载技能。本机受管后台链使用 workspace Skill，但这不是其他平台 Agent 的派发资格条件，也不要求继承桌面聊天历史。

默认使用官方 `multica`，已明确工作区、项目与 Issue 时直接核对，不依赖机器映射、受管声明或包装器。只有从当前仓库自动发现项目时，才用 Skill 的 `scripts/project.py context --directory`；显式项目可用 `--project-id`。`find/read` 限定项目并标明分页或截断，保留全部根线程摘要。需要项目主动关联工作时，使用 `enable` 预览仓库 AGENTS 入口，再在已授权范围内 `--apply`；机器映射本身不等于主动启用。具体边界与典型操作见 [Skill 项目接入](../../../skills/integration/feipi-multica-manage-tasks/references/project-setup.md) 和 [标准操作](../../../skills/integration/feipi-multica-manage-tasks/references/operations.md)。

下面是可选本机回执示例，交互终端可按需要添加已配置的 `--profile`；后台不得指定个人 profile，每个写操作仍核对工作区、项目及 Issue。

```bash
multica-work --help
multica-work record --project PROJECT_UUID --title '任务标题' --body-file task.md --request-id source-123
multica-work bind TASK-123 --project PROJECT_UUID --directory /实际项目目录 --owner 'Codex 当前聊天' --request-id task-123-bind-1
multica-work dispatch TASK-123 --project PROJECT_UUID --agent AGENT_UUID --packet handoff.json --request-id task-123-dispatch-1
multica-work deliver TASK-123 --project PROJECT_UUID --body-file evidence.md --request-id task-123-materials-1
# 只有整单已满足申请条件并明确申请验收时才加 --status in_review
multica-work recover TASK-123 --project PROJECT_UUID --request-id task-123-materials-1
```

同一意图始终复用 request-id。`record` 创建未分派 Issue，初始状态沿用原生工作流或显式指定；`bind` 只备注当前聊天和实际 cwd，不表示锁定目录或接管原生会话。`dispatch` 先用 `--no-start` 设置归属，再发送唯一显式 @交接评论。服务端 `trigger_outcomes` 表示 queued/coalesced/blocked，仍需查 runs 确认实际启动。后台正文先写实际 cwd 的 UTF-8 文件，用 `--content-file` 发布，成功才清理；按本轮 trigger 的真实 parent 回复，并遵守当前平台一轮最终评论或合并多线程的具体规则。

预检失败不留下 pending。缺口解除后可用原输入及 request-id 重试；重放先核对远端 Issue 与原评论，再返回确认结果。正文换路径但内容相同不改变意图；内容或附件语义变化时先核对现状，再确定新意图。回执绑定服务、工作区、操作者与 Run，不证明跨机器全局去重。

`handoff` 用最终 @回复唤醒下一角色；不可把它统一改成静默日志。deliver 默认只发布材料，附件可选，状态不变；显式 `--status` 才单独改变整单状态，不自动标 Done，也不运行测试或代替验收。评论成功、状态失败时，原参数重试只补缺失状态；结果未知先沿相关线程核查，不能盲目重发。

本机部署与 `acceptance.py` 的逻辑键仍来自声明：`codex-builder` 为通用部署角色，`coordinator`、`validator`、`reviewer` 保留 LexiFlow 范围。历史部署键需显式补齐声明、runtime 及实际验收后再启用。这些是本机运维约定；普通派发从平台选择 UUID 或唯一精确名称，不要求目标进入该名单。

交接包字段见 [任务模板](../TASK_TEMPLATE.md)。派发端只核对平台已知的资源约束，不要求 in_place 或派发端存在执行目录。执行端确认真实 cwd、`required_executables` 与 `required_mcp`，完整验证命令放 `validation_commands`。未知能力待探针确认，不能伪称可用、清空要求绕过，或仅因本机无验证器就拒绝派发。模型、推理与并发漂移继续由运维 plan/doctor 诊断。

## 变更配置

```bash
multica-ops plan
multica-ops apply --plan-id 上一步输出的摘要
multica-ops verify
multica-ops doctor
```

默认只显示差异。plan_id 同时绑定声明、机器身份和读回状态；过期计划会被拒绝。apply 要求受管 Agent 排空；写前保存私有快照，逐项写后读回。重复应用不创建重复对象。它不是数据库事务，局部失败后检查新 plan 和快照，不自动删除已创建对象。

UI 漂移显示 before/after；长指令显示全文哈希与行数，可通过 `multica-task agent get UUID` 对照对应 instructions 文件。选择保留 UI 编辑时，手工回收差异到声明并检查机器参数占位；选择恢复声明时，审阅新 plan 后 apply。无后台周期覆盖。

修改源码后：

```bash
/usr/bin/python3 -m unittest discover -s tests -v
# 排空活动任务；修改 daemon 环境或启动脚本时先停守护
python3 scripts/manage-runtime.py stop
python3 scripts/install-runtime.py
python3 scripts/manage-runtime.py start
multica-ops doctor
```

安装器先校验 Python/JSON，再逐文件原子发布和生成校验清单；整批不是原子事务，排空期间发布。首次启动定义用 `manage-runtime.py install`，已经注册时先 stop。配置更新不需要重建服务镜像。

已有运行副本可用 `install-runtime.py --only config/agents.json` 定点发布；可重复 `--only`。`--remove 相对文件名` 仅能移除源码已退役、摘要未变的受管文件，拒绝覆盖无关命令。局部发布前会校验既有清单；遇到运行修改先比较回收。工作台 diff/doctor 同时比较运行代码，配置以外的代码差异需审阅合并，不能用 capture 扩大回收范围。

技能更新在 Agent Kit 根运行 `./workbench diff skills`，再 `./workbench apply skills`，备份后安装到各客户端并保留其他来源。之后同步 workspace Skill：plan → apply → verify。doctor 比较当前执行器所需技能的全部运行文件，排除 tests/evals、缓存和 tmp；不能只比较 SKILL.md。

本机 Multica 0.6.3 的同名 workspace Skill 优先于用户目录，工作区只装载 SKILL.md。当前受管执行链为 Codex，因此同步器先比较源码与 `~/.codex/skills/feipi-multica-manage-tasks` 的全部运行文件，再从已安装正文生成工作区入口：注明完整资源目录 SKILL_DIR，并将参考和模板链接改为该目录的绝对路径。未安装或内容漂移时拒绝同步，后台不直接加载研发目录。更换执行器或机器时需按实际安装路径重新验收，不能沿用旧入口。

## 启动、隔离与恢复

LaunchAgent `local.multica.personal` 在用户登录后启动持续监督器。它检查/启动 machine.json 明确的 Podman VM，仅启动已存在且停止的 Multica postgres/backend/frontend 容器；API 和 Web 就绪后维护唯一 daemon，每60秒复查。缺少容器时要求显式安装，不自动创建或升级。共享 VM 启动脱离 LaunchAgent 进程组，停止监督器时保留容器。当前 Codex 流程不依赖 LiteLLM；其他模型服务由各自管理器维护。不把端口健康当作模型请求成功；Mac mini 整机重启和 FileVault 登录仍需在目标机实测。

若重新启用 OpenClaw 执行器，能力发现与包装命令均须指向隔离目录，保留 CLI 生成的每任务 OPENCLAW_CONFIG_PATH。个人 Gateway 不切换目录、不重启，禁止在 UI 中误选个人实例。

失败先分层：服务/依赖 → daemon/runtime → 认证 → 模型 → 工具/技能 → 产物。`recover` 只查询当前 Issue、活动 runs、全部根线程轻量摘要与指定请求回执，不扫描所有历史和本机请求。pending 表示请求可能已到服务器；按分步记录核对相关线程和附件后，只补缺失动作。旧版单 pending 保留审计，不自动认定成功或删除重试。跨机器/直接 UI 调用不受本机锁保护，平台自己的触发合并机制仍然有效。

## 可重复验收

```bash
python3 scripts/acceptance.py prepare
python3 scripts/acceptance.py start --agent codex-builder --request-id 本轮固定ID
python3 scripts/acceptance.py check
# 多执行器显式启用后，仅在上一 run 终态时验收下一角色；不并发
python3 scripts/acceptance.py check --save
```

prepare 按当前声明创建专用项目及代表角色的未分派 Issue，私有 fixture 防重复；不使用 LexiFlow 正式任务。已有 fixture 会先确认没有活动 run，再刷新探针、任务说明和交接包，避免沿用旧版本脚本。历史 fixture 中停用的角色不参与本轮验收，新增角色缺少 fixture 则停止，不重复创建项目。新一轮验收先核对已有 runs 和产物，使用新的、可说明的 request-id；同一轮重试保留原 ID。fixture 丢失而同名项目存在会拒绝接管，需人工恢复准确绑定。

探针验证五项任务环境、真实执行与计算，以及当前 Agent、runtime、工作区、目录和探针 SHA-256。Agent 仅发一条最终交付评论，以本次 task ID 加 `-deliver` 重复相同命令验证回执；author/source_task_id/parent 必须匹配当前执行。附件重新下载后须与本次报告一致，按本验收任务明确要求进入 in_review。旧附件、错误身份、错误线程、额外过程评论或过期探针均不能证明通过，check 失败返回非零。启用隔离 OpenClaw 时还核对任务配置。

MCP 实际调用明确为 not-tested；要依赖某 MCP，应另加其真实任务调用验收。`--save` 保存环境摘要与逐角色结果，配置、机器、技能或 Multica 执行代码变化后 doctor 标记证据待更新。doctor 退出码零只表示静态检查没有阻塞，仍须检查 runtime-capabilities 是否 evidence-required。历史测试记录在 [VALIDATION.md](../VALIDATION.md)，本轮集成见 [工作台验收](../../../docs/workbench-validation.md)。

依据： [Multica runtime 与任务环境契约](https://multica.ai/docs/daemon-runtimes)、[评论触发与 /note](https://multica.ai/docs/mentioning-agents)。借鉴 [multica-agent-team](https://github.com/stone16/multica-agent-team) 的职责/实例/部署拆分、[Mops](https://github.com/jamillazarev/multica-ops/blob/main/REFERENCE.md) 的恢复方法和 [stometa-skills](https://github.com/stone16/stometa-skills/blob/main/docs/multica.md) 的能力验证边界；具体行为以本机 0.6.3 及实测为准。
