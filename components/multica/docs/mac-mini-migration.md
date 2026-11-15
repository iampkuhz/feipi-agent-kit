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

按当前 compatibility 安装固定版本 Multica 0.6.3、Codex 0.162.1，以及 Podman/Compose 和项目实际依赖；可选执行器仅在显式启用后安装对应版本。源码统一从 Agent Kit 的 components 发布，不恢复独立旧仓库作为运行来源。包含未提交更改的源码需明确传输；不能只 clone 远端旧版本。备份中的 ops-runtime 提供实际发布脚本与声明的可恢复副本。若启用 LiteLLM，按该服务流程恢复数据库、模型路由、客户端访问密钥和既有容器，确认 readiness 后实际请求编码模型。

集中准备清单已执行以下两步；单独部署时在 `components/multica` 中运行。安装器仅下载官方固定 CLI 与固定提交的单个 Compose，并校验摘要，不克隆整个上游源码、不登录或启动服务。已有其他 CLI 版本或不同服务定义时停止，不自动覆盖或降级。

```bash
bash <<'PREPARE_MULTICA'
set -euo pipefail
python3 scripts/install-native.py install
python3 scripts/install-runtime.py
PREPARE_MULTICA
```

先用集中清单恢复基础 env、激活当前终端环境，再恢复 Multica 小配置。集中清单已包含下面命令；单独部署时在 `components/multica` 中执行一次：

```bash
bash <<'RESTORE_MULTICA_CONTROLS'
set -euo pipefail
../../workbench private restore-state multica "$HOME/feipi-restore/multica"
python3 scripts/configure.py --personal-profile
RESTORE_MULTICA_CONTROLS
```

入口只校验同批 `source-home.json`、`machine.reference.json`、`server.env`、`versions.json` 和 `compose.pinned.yml`，不读取数据库、附件或项目目录。旧备份缺少原 HOME 记录时，用当前旧机入口重新备份。版本/镜像锁定或三项服务密钥与本机 env 不匹配时，在写入前失败；不要执行 init-secrets 生成替换值。

恢复创建 0700 的 `~/.config/multica-selfhost` 和 0600 的 machine/server.env/匿名 Docker 配置，已有目标保持原样。保留 workspace、Agent、项目及 resource UUID 和额外声明；原 HOME 下路径改为新 HOME，仓库和程序路径按新机实际安装重建，Podman machine 取本机默认名称，role=primary。原 HOME 外的绝对路径保留，使用前须挂载到相同位置。daemon/runtime 的物理 ID 清空，稍后原生注册后重绑。它不复制 CLI 登录或创建项目目录，不启动服务。

## 3. 恢复数据（只在新机空数据库执行）

在 `components/multica` 中执行，备份默认已由用户直传到 `~/feipi-restore/multica`。先核对同批备份，再显式拉取锁定 digest 的镜像；全新机器没有旧机镜像，不能直接以 `--pull never` 冷启动。以同版本 PostgreSQL 17 恢复，等待数据库就绪并确认没有业务表后才导入：

```bash
bash <<'RESTORE_MULTICA'
set -euo pipefail
multica_batch="$HOME/feipi-restore/multica"
python3 scripts/backup.py --verify "$multica_batch"
running_services="$(multica-service ps --status running --services backend frontend)"
[[ -z "$running_services" ]] || {
  echo 'Web/API 正在运行；先停写，未恢复。' >&2; exit 1;
}
multica-service pull
multica-service up -d --pull never postgres
for ((attempt=0; attempt<60; attempt++)); do
  if multica-service exec -T postgres pg_isready -U multica -d multica > /dev/null 2>&1; then
    break
  fi
  sleep 2
done
multica-service exec -T postgres pg_isready -U multica -d multica > /dev/null
tables="$(multica-service exec -T postgres psql -U multica -d multica -Atc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")"
[[ "$tables" == 0 ]] || { echo '目标库已有业务表，未覆盖。' >&2; exit 1; }
multica-service exec -T postgres pg_restore -U multica -d multica --exit-on-error < "$multica_batch/database.dump"
# 创建停止的 backend 容器并写入同批附件；不启动 Web/API 写入
multica-service create --pull never backend
multica-service cp "$multica_batch/uploads/." backend:/app/data/uploads/
multica-service up -d --pull never
RESTORE_MULTICA
```

如果目标已有业务数据，停止此流程，不加 `--clean` 覆盖。对照旧机数据库记录数、Issue/Agent UUID、附件数量并实际下载一个附件。随后在新机图形终端执行下面整段命令，浏览器完成本人登录；使用绑定中的服务地址和准确工作区，不运行会自动启动 daemon 的 `setup`。

```bash
bash <<'LOGIN_MULTICA'
set -euo pipefail
source ../mac/bootstrap/environment.sh
python3 scripts/configure.py --personal-profile
binding="$HOME/.config/multica-selfhost/machine.json"
export MULTICA_PERSONAL_PROFILE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["profile"])' "$binding")"
workspace_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["workspace_id"])' "$binding")"
multica-task login
multica-task workspace switch "$workspace_id"
LOGIN_MULTICA
```

`--personal-profile` 复用固定版原生 `config set`，只设置服务地址、设备名、任务根目录、并发 1 和禁自动升级；不读写 env、不复制 token、不登录或启动服务。重复执行跳过已一致字段，同名 profile 已指向其他服务时拒绝覆盖；登录后重跑保留原生 token 和其他设置。原生 login 会重置默认工作区，所以最后必须 `workspace switch` 到恢复的 UUID，并通过服务器权限验证。0.6.3 的 `auth status` 在未登录或 token 失效时也会返回 0，不能作为脚本登录门禁。SSH 登录回调按原生 CLI 提示使用本地转发；令牌方式在交互终端使用 `multica-task login --token` 提示输入，随后仍须准确切换工作区。

若启用隔离 OpenClaw，依据 `runtime profile --help` 为原 profile 设置新机包装命令路径，不创建同名重复 profile。

启动新机 daemon 前，恢复同批 adaptation/requests 防重记录；由用户执行以下复制命令，已有目标时停止。备份没有该目录则无需复制。该步骤不复制 CLI 登录/设备身份。

```bash
bash <<'RESTORE_MULTICA_RECEIPTS'
set -euo pipefail
receipts_source="$HOME/feipi-restore/multica/adaptation"
receipts_target="$HOME/.local/state/multica/adaptation"
if [[ -d "$receipts_source" ]]; then
  [[ ! -e "$receipts_target" && ! -L "$receipts_target" ]] || {
    echo '防重记录目标已存在，未覆盖。' >&2; exit 1;
  }
  mkdir -p "$(dirname "$receipts_target")"
  cp -R "$receipts_source" "$receipts_target"
fi
RESTORE_MULTICA_RECEIPTS
```

## 4. 重建能力并重绑

发布运行副本，使用 Agent Kit 工作台安装完整技能并重新认证工具。当前默认只绑定 Codex；若启用隔离 OpenClaw，才生成并校验其候选配置。项目资源目标目录须先存在。

`manage-runtime.py install/start` 在写 LaunchAgent 或调用 launchctl 前检查主机角色、profile 的服务/工作区/路径/并发/升级设置及个人凭据是否存在；缺项即报错，不把失败的后台循环当成已启动。该本地检查不证明凭据仍有效，须先完成上面的原生工作区访问。

```bash
bash <<'START_MULTICA'
set -euo pipefail
source ../mac/bootstrap/environment.sh
python3 scripts/install-runtime.py
# 仅在声明启用隔离 OpenClaw 时：
# python3 scripts/configure-openclaw.py
# multica-task runtime profile set-path 隔离Profile_UUID --path 新机multica-openclaw绝对路径
# 新机并发配置为 1，禁自动升级；检查 setup 不覆盖 profile
python3 scripts/manage-runtime.py install
"$HOME/.local/bin/multica-ops" rebind --local
"$HOME/.local/bin/multica-ops" plan
START_MULTICA
```

`rebind --local` 在最多 120 秒内等待本机 daemon 和 runtime 注册。它核对原生 profile、服务地址、设备名、操作系统、固定版本/提交及本机生成的 `~/.multica/daemon.id`，再与同一工作区的原生注册列表和服务端唯一线上 runtime 交叉核对；存在活动任务时继续等待。身份冲突或重复 runtime 立即失败，超时不写机器绑定；重复执行已一致时不重写文件。无需手填新机 UUID，不复制或生成设备身份，不修改服务端 Agent 或项目。显式指定 `--daemon-id` 的入口仍保留，两种方式不能混用。

审阅 plan 中明确受管对象的差异后，使用该次准确摘要执行下面一段；计划改变时 apply 会拒绝，不沿用旧摘要。

```bash
bash <<'APPLY_MULTICA'
set -euo pipefail
multica-ops apply --plan-id 审阅后的摘要
multica-ops verify
multica-ops doctor
APPLY_MULTICA
```

rebind 仅更新本机 daemon/runtime 绑定；以 provider+profile+新 daemon 唯一匹配，歧义即停。apply 再更新明确受管 Agent 与项目本地路径，保留项目其他资源。未纳管项目需逐项核对，不能随意替换数据库里的所有路径。

旧 acceptance/fixture 的机器路径和能力结论不能作为新机证据。为新机独立验收项目显式更新准确绑定或新建带设备名的试验项目，重新验证。工具实际 cwd、模型、技能、MCP 都要重新取证。

## 5. 验收、切换和回退

验收静态差异为零、重复应用零变更；每个启用执行器真实任务；/note 不增 run、派发一次，多执行器时另验跨工具交接；缺失任务凭据明确失败；附件在任务目录清理后仍可下载；模拟模型/服务错误时保留产物并说明层级。整机重启并完成登录后，确认 Podman、Multica 和 daemon 自动恢复，可选模型服务按各自管理器验证，再跑一个小任务。此项不能用 launchctl 重启代替。

全部通过后把旧 MacBook machine.json 的 role 改为 client，bootout 受管 LaunchAgent，并删除/移出仅此受管 plist（先确认 MulticaOpsManaged=true），避免下次登录恢复长期 worker。保留 multica-task/multica-work，personal profile 改连 Mac mini 的受信地址。当前 loopback 默认无法被 MacBook 访问；通过已有私网或显式 SSH 转发接入，不直接开放公网端口。

切换前若失败，可停新机派发并排空，启用原机主力并重新按精确 runtime 绑定恢复声明。新机已经写入新任务后，不得直接启用旧数据库；先同批备份新数据并制定反向恢复，避免丢失任务与附件。
