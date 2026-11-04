# 本机 Multica 运维

日常操作统一从仓库根目录 `./workbench` 进入；本目录命令供组件维护与显式源码调试。应用、回收与恢复见 [工作台手册](../../docs/workbench.md)。原独立仓库仅留作历史回退。

服务采用 Multica v0.6.3，源码固定在 `~/.local/share/multica/server`，Web/API/PostgreSQL 镜像由 `config/compose.pinned.yml` 锁定 digest。当前目录不保存真实凭据或业务数据。后台运行副本位于 `~/.local/share/multica/ops`，通过 `scripts/install-runtime.py` 发布，避免 launchd 直接读取 Documents 被 macOS 拒绝；运行副本不手工编辑。

## 当前运行选择（2026-11-04）

已回收本机11月1日正式发布的声明：当前仅启用 Codex Builder 及 LexiFlow 的 Coordinator、Validator、Reviewer，机器只绑定 Codex runtime。合并历史能力不重新启用 Qoder、OpenClaw Assistant 或 LiteLLM Coder；相关实现和历史说明保留，启用前需显式补齐声明、机器身份及实际验收。

`acceptance.py` 按当前声明选择代表性角色，不强制运行已停用的角色；已声明但缺少机器绑定仍明确失败。当前完整路径以 Codex Builder 验证任务凭据、执行、回写与附件，不能将10月31日的其他执行器结果当作本次通过。

11月1日已发布的持续监督器、停止等待与局部发布功能一并回收：监督器复用现有 Multica 容器，每60秒检查就绪并维护唯一 daemon；共享 Podman VM 启动脱离 LaunchAgent 进程组。发布前排空任务，启动脚本更新先停止监督器。验收附件按原生下载命令取回，失败时检查返回非零。

## 适配与配置管理（2026-10-31）

已实现 `multica-ops plan/apply/verify/doctor` 和 `multica-work` 统一交互。日常操作以 [适配操作手册](docs/adaptation-runbook.md) 为准；Mac mini 单主机切换见 [迁移流程](docs/mac-mini-migration.md)。声明与机器绑定分开；共享 Skill 由 Agent Kit 维护。

## 日常入口

```bash
multica-service ps
curl -fsS http://localhost:8080/readyz
multica-task daemon status
multica-task issue list
multica-task issue get <任务编号>
multica-task issue runs <任务编号>
```

网页为 `http://localhost:3000`。`multica-task` 在普通终端、Codex 或 OpenClaw 中使用本机 personal profile；在 Multica 管理的任务内沿用注入的任务认证，不复制个人 token。

**当前没有配置 SMTP/Resend，不会发送验证码邮件。** 页面请求登录码后，在本机终端运行 `multica-service logs --tail 30 backend`，读取自己邮箱对应的一次性验证码并填入页面。保持 production 模式，不使用固定验证码。首次账户已建立，注册已关闭并限制为本人的邮箱；以后需要真正邮件投递时再单独配置邮件服务凭据。

创建任务时用 stdin 提供完整目标、范围、来源、验收与交付：

```bash
multica-task issue create --title "任务标题" --description-stdin < task.md
multica-work dispatch <任务编号> --agent codex-builder --packet handoff.json --request-id <本次固定标识>
multica-work note <任务编号> --body-file progress.md --request-id <本次固定标识>
```

未明确要求后台执行的事项先不指定 Agent；仅记录负责人时使用 `issue assign ... --no-start`。同一事项避免同时在 Codex 客户端和后台 Agent 中重复执行。任务正常交付先进入 Review，再由用户验收。

## 配置与秘密

`scripts/configure.py --init-secrets` 只在缺失时生成三项 Multica 秘密并追加至现有 `~/.env` 指向的 env vault；保存私有回退副本，之后不轮换原值。服务投影为 `~/.config/multica-selfhost/server.env`，0600。`--email` 设置注册邮箱白名单，首次登录完成后用 `--lock-signup` 关闭新增注册。

服务使用单独的 Docker 匿名认证配置，同时保留本机 Compose plugin 路径。它不覆盖 `~/.docker/config.json` 中其他服务的认证。Compose 进程只继承必要的路径与本机 Docker socket，避免 shell 中其他项目的 POSTGRES_PASSWORD、端口等覆盖本服务投影。仅接受不展开秘密的 `config --quiet/--images/--services`；不要将真实 env 或展开的 Compose 配置粘贴到聊天。

若 Podman 服务端直接拉取慢，可以只为一次拉取设置指向宿主代理的 HTTP_PROXY/HTTPS_PROXY；不更改容器引擎的全局代理。实际拉取结果和本机验收见 `VALIDATION.md`。

## 运维与迁移

前端/API 绑定 loopback，数据库没有宿主端口。CLI 自动升级关闭，初期 daemon 和 Agent 并发都为 1。

已安装 `local.multica.personal` LaunchAgent，负责登录启动、持续服务检查和 daemon 退出恢复；按机器绑定启动已存在的 Podman VM、本服务，等待 API/Web 就绪。不创建或升级容器，当前 Codex 流程不依赖 LiteLLM。管理入口：

```bash
python3 ~/Documents/tools/llm/feipi-agent-kit/components/multica/scripts/manage-runtime.py status
python3 ~/Documents/tools/llm/feipi-agent-kit/components/multica/scripts/manage-runtime.py stop
python3 ~/Documents/tools/llm/feipi-agent-kit/components/multica/scripts/manage-runtime.py start
```

停止请使用上述 stop；单独 `multica-task daemon stop` 会被守护重新拉起。stop 保留 Web/API。需要维护配置或升级时，先排空运行中的任务。更新本目录 bin、镜像锁定或后台启动脚本后，执行 `scripts/install-runtime.py` 发布运行副本；更新启动定义时先 stop，再运行 `scripts/manage-runtime.py install`。

原 Gateway 可通过 `multica-task` 录入和查询。以下为历史可选 OpenClaw 执行方案：`OpenClaw Assistant` 绑定 `OpenClaw Multica` 自定义 runtime，使用独立状态目录 `~/.local/share/multica/openclaw-state`。`scripts/configure-openclaw.py` 从声明组件读取原模型定义，再合并 LiteLLM 角色；从全局 `~/.env` 只投影三项所需 provider 变量，不复制原渠道、插件或个人记忆。隔离执行端关闭 memory 插件，避免无关 embedding 请求。原 Gateway 不切换入口、不重启。

## 历史可选方案：LiteLLM Agent

以下记录此前的 LiteLLM 编码 Agent 方案；当前默认声明不启用该 Agent，通过上述独立 OpenClaw runtime 调用本地 `http://localhost:4000/v1`。使用现有客户端虚拟密钥，不把密钥写进 Multica 的 Agent 字段或源码。

| Multica Agent | OpenClaw Agent ID | LiteLLM 模型别名 | 用途 |
|---|---|---|---|
| LiteLLM Coder | litellm-coder | litellm-code-openai | 编码、测试与代码交付 |

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

## 数据备份与版本迁移

创建同一任务后通过评论继续，首次代码验收为 TASK-2；OpenClaw 查询验收为 TASK-3。临时 worktree 会被运行时回收，交付应保存在提交/PR、附件或补丁中，不仅记录临时路径。

本机一致性备份（先排空任务）：`python3 scripts/backup.py --apply`。脚本短暂停止 Web/API 写入，导出并校验数据库，复制附件和服务密钥投影，生成校验清单，再恢复原服务。批次在 `~/.local/state/multica/backups`；其中含真实秘密，向 NAS 传输前加密，不能提交 Git。

修改服务 env 后用 `multica-service up -d`，仅 restart 不重新载入环境。升级前先暂停派发、排空任务、停写并保存同批数据库、附件和服务加密密钥；迁移先恢复相同版本再升级。不要复制 CLI 设备身份给第二台机器，Mac mini 重新登录和注册 runtime。

当前单主机流程维护在 [Mac mini 迁移手册](docs/mac-mini-migration.md)；早期迁移工作台仅供历史参考。正式运行和后续恢复状态以本目录 `VALIDATION.md` 为准。
