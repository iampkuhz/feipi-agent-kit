# Multica Cloud

从仓库根目录执行 `./workbench install mac`，Homebrew 会安装官方 `multica-ai/tap/multica`。把 Mac 接为执行机时，使用官方 CLI 登录并查看 daemon 状态。

```bash
multica setup cloud --profile cloud
multica daemon status --profile cloud
```

Multica Cloud 提供平台服务。Mac 上的 daemon 执行绑定到本机的任务，登录自启按需使用 `multica daemon autostart enable --profile cloud`。用 `type -a multica` 可以核对终端实际调用的版本。 [官方运行时说明](https://multica.ai/docs/daemon-runtimes)

## 仓库维护的配置

- `config/agents.json` 和 `config/instructions/` 维护 Agent 声明、模型、推理档位、并发和角色指令。当前默认声明 Codex Builder。
- 可选的 `config/machine.example.json` 提供 Cloud 机器绑定示例。使用 `~/.config/feipi-multica/machine.json` 保存准确的 Cloud 工作区、daemon、runtime 和项目 UUID。本机登录态由官方 CLI 管理。
- 任务操作走官方 `multica` 或 Web。需要本机操作回执时可选用 `multica-work`。配置差异和运行验收见 [操作手册](docs/adaptation-runbook.md)，任务协作见 [Skill 操作参考](../../skills/integration/feipi-multica-manage-tasks/references/operations.md)。
- 可选的本机工具通过 `python3 scripts/install-runtime.py` 发布到 `~/.local/share/multica/ops`。只用官方 CLI 的机器可以直接通过 Cloud 管理任务。

## 历史可选方案：LiteLLM Agent

以下记录此前的 LiteLLM 编码 Agent 方案；当前默认声明不启用该 Agent，通过上述独立 OpenClaw runtime 调用本地 `http://localhost:4000/v1`。使用现有客户端虚拟密钥，不把密钥写进 Multica 的 Agent 字段或源码。

| Multica Agent | OpenClaw Agent ID | LiteLLM 模型别名 | 用途 |
|---|---|---|---|
| LiteLLM Coder | litellm-coder | litellm-token-plan-deepseek | 编码、测试与代码交付 |

2026-10-23 实查编码入口上游为 Qwen3.7 Plus；模型上游以后随 LiteLLM 别名路由更新。Agent 并发 1，声明保守的 128000 上下文预算与 8192 最大输出，不配置跨模型回退；没有启用后台 heartbeat。先前创建的 LiteLLM Analyst 已归档，并从运行配置与声明移除；历史验收 TASK-9 保留。原 Codex Builder 保持现有路由。

普通可执行状态分派可能启动运行；Backlog 分派会停放。统一入口通过明确 @交接派发；只记录归属用 `--no-start`。终端示例：

```bash
multica-task issue assign TASK-123 --to "LiteLLM Coder"
multica-task issue assign TASK-123 --to "LiteLLM Coder" --no-start
```

无秘密声明在 `config/litellm-agents.json`。更新或迁移时先排空任务，再生成隔离配置、通过 schema 校验，最后幂等同步到新机 runtime：

```bash
python3 scripts/configure-openclaw.py
multica-openclaw config validate
multica-ops plan
multica-ops apply --plan-id <审阅后的摘要>
multica-ops verify
```

多 Agent 采用显式 ownership；Multica 的 OpenClaw “model” 字段实际是注册 Agent ID，不能直接填 LiteLLM 别名。原 `OpenClaw Assistant` 已显式选择 `main`。生成器会为有变化的私有配置保存回退副本；新配置工具只维护机器绑定中的准确 UUID；旧同步脚本已停用，避免双重配置真源。私有投影和回退副本都不进入 Git。

## 历史记录

自建部署及退出前的实机证据见 [历史验收](VALIDATION.md)。本机退役后遗留的数据库卷和附件卷属于私有数据。
