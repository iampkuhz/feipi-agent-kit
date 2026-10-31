# Mac mini 接替主力机器

本流程尚未在 Mac mini 上执行。先恢复当前相同版本，再另行升级。当前机器切换后只作临时客户端，不保留长期 worker；不能同时运行复制来的 daemon 身份。

## 1. 排空与同批备份

停止新派发，在 UI 确认所有项目 active runs 为零；`multica-task daemon status` 的 active_task_count 为零。仅停止 daemon 不会阻止其他客户端入队，因此整个维护窗口暂停 UI/聊天派发。

```bash
python3 scripts/manage-runtime.py stop
python3 scripts/backup.py --apply
python3 scripts/backup.py --verify ~/.local/state/multica/backups/本批次
python3 scripts/restore-check.py ~/.local/state/multica/backups/本批次
```

备份脚本要求 daemon stopped 和受管 Agent 无活动任务；停 Web/API 写入，导出并校验 PostgreSQL dump，复制附件、服务密钥、版本、声明、机器参考绑定及防重回执，并打包经哈希核对的已发布 ops-runtime，然后恢复 Web/API。原机此时仍不可重新派发。批次含真实秘密，使用已有加密方式传输，禁止提交 Git 或放公开网盘。

另行备份项目 Git 未推送提交/允许保留的资料目录，以及 LiteLLM 的数据库、客户端密钥对应记录和必要 OAuth 状态。这些不属于 Multica 数据卷，不能只迁 Multica 后宣称模型环境可用。Codex/Qoder/OpenClaw 登录优先新机重新认证；不复制 Multica CLI daemon/device ID。工具私有聊天不是任务交接依赖。

## 2. 新机准备

安装固定版本 Multica 0.6.3、Codex 0.162.1、Qoder 1.1.54、OpenClaw 2026.9.2，以及 Podman/Compose 和项目实际依赖。重建 Agent Kit、Multica Ops 和个人 OpenClaw 声明源码。包含未提交更改的源码需明确传输；不能只 clone 远端旧版本。备份中的 ops-runtime 提供本次实际发布脚本与声明的可恢复副本。按原 LiteLLM 项目流程恢复数据库、模型路由、客户端访问密钥及明确的两个容器名；确认 readiness 后实际请求编码模型。

从备份 machine.reference.json 建立 `~/.config/multica-selfhost/machine.json`，0600。保留恢复数据库中的 workspace、Agent、项目及 resource UUID；更新主机名、源码和项目路径、工具包装路径、模型地址、Podman VM/容器名。role=primary。runtimes 与 daemon 的物理身份稍后重绑，不直接复用旧设备身份。

按现有 `configure.py` 与安全投影流程设置服务 env，必须恢复同批 JWT/VCS 加密密钥与数据库口令。不要执行 init-secrets 生成替换值；保留原始 env vault 真源和 0600 最小投影。用锁定 digest 的 compose 创建新机空卷，先仅启动 postgres；Web/API 保持停止。

## 3. 恢复数据（只在新机空数据库执行）

先 `backup.py --verify 本批次`，确认 volumes 是新机空卷。以同版本 PostgreSQL 17 恢复：

```bash
multica-service up -d --pull never postgres
multica-service exec -T postgres pg_restore -U multica -d multica --exit-on-error < 本批次/database.dump
# 创建停止的 backend 容器并写入同批附件；不启动 Web/API 写入
multica-service create backend
multica-service cp 本批次/uploads/. backend:/app/data/uploads/
multica-service up -d --pull never
```

如果目标已有业务数据，停止此流程，不加 `--clean` 覆盖。对照旧机数据库记录数、Issue/Agent UUID、附件数量并实际下载一个附件。重建 CLI personal 登录和工作区选择；确认 server_url/workspace_id 后注册新 daemon。依据 `runtime profile --help` 为原有隔离 OpenClaw profile 设置新机包装命令路径，不创建同名重复 profile。

## 4. 重建能力并重绑

发布运行副本、生成隔离 OpenClaw 候选配置并通过 schema 校验，使用 Agent Kit 既有安装器向三个客户端安装完整技能，重新认证工具。项目资源目标目录须先存在。

```bash
python3 scripts/install-runtime.py
python3 scripts/configure-openclaw.py
multica-task runtime profile set-path 隔离Profile_UUID --path 新机multica-openclaw绝对路径
# 新机并发配置为 1，禁自动升级；检查 setup 不覆盖 profile
python3 scripts/manage-runtime.py install
multica-task daemon status
multica-ops rebind --daemon-id 新机Daemon_UUID
multica-ops plan
multica-ops apply --plan-id 审阅后的摘要
multica-ops verify
multica-ops doctor
```

rebind 仅更新本机 daemon/runtime 绑定；以 provider+profile+新 daemon 唯一匹配，歧义即停。apply 再更新明确受管 Agent 与项目本地路径，保留项目其他资源。未纳管项目需逐项核对，不能随意替换数据库里的所有路径。

恢复 adaptation/requests 防重记录；旧 acceptance/fixture 的机器路径和能力结论不能作为新机证据。为新机独立验收项目显式更新准确绑定或新建带设备名的试验项目，重新验证。工具实际 cwd、模型、技能、MCP 都要重新取证。

## 5. 验收、切换和回退

验收静态差异为零、重复应用零变更；每个执行器真实任务；/note 不增 run、派发一次、跨工具交接；缺失任务凭据明确失败；附件在任务目录清理后仍可下载；模拟模型/服务错误时保留产物并说明层级。整机重启并完成登录后，确认 Podman、LiteLLM、Multica 和 daemon 自动恢复，再跑一个小任务。此项不能用 launchctl 重启代替。

全部通过后把旧 MacBook machine.json 的 role 改为 client，bootout 受管 LaunchAgent，并删除/移出仅此受管 plist（先确认 MulticaOpsManaged=true），避免下次登录恢复长期 worker。保留 multica-task/multica-work，personal profile 改连 Mac mini 的受信地址。当前 loopback 默认无法被 MacBook 访问；通过已有私网或显式 SSH 转发接入，不直接开放公网端口。

切换前若失败，可停新机派发并排空，启用原机主力并重新按精确 runtime 绑定恢复声明。新机已经写入新任务后，不得直接启用旧数据库；先同批备份新数据并制定反向恢复，避免丢失任务与附件。
