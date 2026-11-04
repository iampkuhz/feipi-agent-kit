# Multica 与本机 Agent 的操作流程

当前默认仅绑定 Codex runtime 与4个 Codex 角色，其他执行器的实现按需启用。`acceptance.py` 只验收当前声明中的代表角色；已声明但没有机器绑定会停止，不用历史结果补齐。

配置仓库维护期望配置；Multica 保存任务、评论、附件与运行记录。当前主力为 MacBook，未来由 Mac mini 接替。一个 daemon 负责长期运行；MacBook 切换后只保留临时交互入口。

## 文件与职责

| 内容 | 真源/运行位置 | 维护规则 |
|---|---|---|
| Agent 职责、模型选择、并发 | `config/agents.json`、`config/instructions/` | 保留项目规则，机器参数用 `${...}` 绑定 |
| 能力要求和兼容组合 | `config/capabilities.json`、agents 的 compatibility | 区分静态检查与任务实际调用 |
| 机器身份、路径和依赖 | `~/.config/multica-selfhost/machine.json` | 0600；不进入 Git；迁机重建 daemon/runtime |
| 技能正文 | Agent Kit 的 `skills/integration/feipi-multica-manage-tasks` | 通过既有安装器安装完整技能；工作区同步单文件 SKILL.md |
| 运行副本 | `~/.local/share/multica/ops` | 只能从源码发布，不手改 |
| 变更快照和请求回执 | `~/.local/state/multica/adaptation` | 私有；备份；不提交；并发锁限本机 |
| 数据库、附件、服务密钥 | Multica 私有存储、env vault 的最小投影 | 同批备份，工具登录另行认证 |

`config/agents.json` 只管理列出的字段与机器明确绑定的 UUID。不会按 provider 或显示名模糊接管其他对象，不删除额外技能、MCP、小队或其他项目资源。Qoder Worker 为通用入口，不加入 LexiFlow 正式审批链。

## 日常交互

在 Codex、Qoder、个人 OpenClaw 中使用共享 Skill：`$feipi-multica-manage-tasks`。新聊天重新加载技能。后台 Agent 已绑定同一 workspace Skill，不要求继承桌面聊天历史。

```bash
multica-work --help
multica-work record --project PROJECT_UUID --title '任务标题' --body-file task.md --request-id source-123
multica-work bind TASK-123 --directory /实际项目目录 --owner 'Codex 当前聊天' --request-id task-123-bind-1
multica-work note TASK-123 --body-file progress.md --request-id task-123-note-1
multica-work dispatch TASK-123 --agent codex-builder --packet handoff.json --request-id task-123-dispatch-1
multica-work deliver TASK-123 --body-file evidence.md --artifact result.zip --request-id task-123-deliver-1
multica-work recover TASK-123
```

同一意图始终复用 request-id。`record` 为未分派 Backlog，`bind` 记录当前工作，`note` 自动加 `/note`。`dispatch` 先用 `--no-start` 设置归属，再发送唯一显式 @交接评论；仅 assign Backlog 不启动。服务端 `trigger_outcomes` 表示 queued/coalesced/blocked，仍需查 runs 确认实际启动。后台评论触发的任务必须传 `--parent 触发评论ID`。

`handoff` 用正常 @回复唤醒下一角色；不可把它统一改成静默日志。提交验收用 deliver，上传附件再 `in_review --no-start`，不自动标 Done。项目自身的审批与独立验收规则继续有效。

当前通用逻辑键为 `codex-builder`；`coordinator`、`validator`、`reviewer` 保留 LexiFlow 专用范围。历史可选键 `qoder-worker`、`openclaw-assistant`、`litellm-coder` 需先补齐声明、runtime 及实际验收后使用；OpenClaw 的 model 是 Agent ID，`litellm-coder` 再选择 `litellm/litellm-code-openai`。

交接包字段见 [任务模板](../TASK_TEMPLATE.md)。通用派发入口要求当前 daemon 上明确的 in_place 项目资源。原生 worktree 项目继续使用其原有流程并记录真实目录。必需 MCP 未有任务内验证器时入口会阻止自动派发；不得用空 mcpServers 声称关闭所有 MCP。

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

## 启动、隔离与恢复

LaunchAgent `local.multica.personal` 在用户登录后启动持续监督器。它检查/启动 machine.json 明确的 Podman VM，仅启动已存在且停止的 Multica postgres/backend/frontend 容器；API 和 Web 就绪后维护唯一 daemon，每60秒复查。缺少容器时要求显式安装，不自动创建或升级。共享 VM 启动脱离 LaunchAgent 进程组，停止监督器时保留容器。当前 Codex 流程不依赖 LiteLLM；其他模型服务由各自管理器维护。不把端口健康当作模型请求成功；Mac mini 整机重启和 FileVault 登录仍需在目标机实测。

若重新启用 OpenClaw 执行器，能力发现与包装命令均须指向隔离目录，保留 CLI 生成的每任务 OPENCLAW_CONFIG_PATH。个人 Gateway 不切换目录、不重启，禁止在 UI 中误选个人实例。

失败先分层：服务/依赖 → daemon/runtime → 认证 → 模型 → 工具/技能 → 产物。`recover` 只查询，不重跑。pending 回执表示请求可能已经到达服务器；查 Issue 评论中的 request-id、runs 和附件，记录结论后显式确定新一轮操作，不删除回执盲重试。跨机器/直接 UI 调用不受本机锁保护。

## 可重复验收

```bash
python3 scripts/acceptance.py prepare
python3 scripts/acceptance.py start --agent codex-builder --request-id 本轮固定ID
python3 scripts/acceptance.py check
# 多执行器显式启用后，仅在上一 run 终态时验收下一角色；不并发
python3 scripts/acceptance.py check --save
```

prepare 按当前声明创建专用项目及代表角色的未分派 Issue，私有 fixture 防重复；不使用 LexiFlow 正式任务。历史 fixture 中停用的角色不参与本轮验收，新增角色缺少 fixture 则停止，不重复创建项目。新一轮验收先核对已有 runs 和产物，使用新的、可说明的 request-id；同一轮重试保留原 ID。fixture 丢失而同名项目存在会拒绝接管，需人工恢复准确绑定。

探针验证五项任务环境、真实执行与计算、任务身份回写、下载附件和待验收状态；启用隔离 OpenClaw 时还核对任务配置。附件内容必须匹配最新 completed 执行，旧附件不能证明新执行成功，未通过时 check 返回非零。MCP 实际调用明确为 not-tested；要依赖某 MCP，应另加其真实任务调用验收。`--save` 保存环境摘要与逐角色结果，配置/机器/技能变化后 doctor 标记证据待更新。历史测试记录在 [VALIDATION.md](../VALIDATION.md)，本轮集成见 [工作台验收](../../../docs/workbench-validation.md)。

依据： [Multica runtime 与任务环境契约](https://multica.ai/docs/daemon-runtimes)、[评论触发与 /note](https://multica.ai/docs/mentioning-agents)。借鉴 [multica-agent-team](https://github.com/stone16/multica-agent-team) 的职责/实例/部署拆分、[Mops](https://github.com/jamillazarev/multica-ops/blob/main/REFERENCE.md) 的恢复方法和 [stometa-skills](https://github.com/stone16/stometa-skills/blob/main/docs/multica.md) 的能力验证边界；具体行为以本机 0.6.3 及实测为准。
