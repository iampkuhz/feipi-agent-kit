# 新 Mac：从配置重建本地服务

本仓库保存服务定义；Podman、podman-compose、Python 3.10+ 等机器依赖由本仓库 `components/mac` 安装。不复制旧机容器、镜像、Podman 虚拟机或缓存，不需要 NAS。

## 首次准备

```bash
# 裸机先运行 bash scripts/bootstrap/prerequisites.sh install；随后 install mac。
# 自动创建或启动唯一默认本机 machine；已有运行实例不会重启，不切换连接。
./workbench service podman ensure
./workbench service podman check

# 只检查依赖、默认本地连接和服务定义，不安装或启动任何服务。
make setup
./workbench apply services
```

已有运行中的 Podman machine 时跳过 init/start。连接不是本机时脚本报错，不接管远端环境；缺 provider 时安装 `podman-compose`，不要求 Docker Desktop。
`ensure` 对首次镜像下载最多等待 15 分钟，启动最多 5 分钟，随后有界等待引擎；失败不删除虚拟机。

## 按需启动

| 服务 | 启动 | 状态 | 本地探测 |
|---|---|---|---|
| SearXNG | `make searxng-up` | `make searxng-status` | `http://127.0.0.1:8873/healthz` |
| Crawl4AI | `make crawl4ai-up` | `make crawl4ai-status` | `http://127.0.0.1:11235/health` |
| LiteLLM + PostgreSQL | `make litellm-up` | `make litellm-status` | `http://127.0.0.1:4000/health/readiness` |
| OTel collector/cleaner | `make otel-up` | `make otel-status` | 通过容器状态核对，接收端口 4317/4318 |
| draw.io | `bash tools/diagram/drawio/drawio.sh ensure` | 同脚本 `status` | `http://127.0.0.1:8200/health` |

前四项均可使用 `make <服务>-down/restart/logs`；日志入口最多显示最后 50 行（LiteLLM 保留其原有日志入口）。重建、重启与停止都是显式动作，检查失败不会自动停止其他服务。
通过工作台启动 LiteLLM、SearXNG、Crawl4AI 后，最多等待 10 分钟的本地 HTTP 健康检查；
超时返回非零并保留运行状态，不重复重建。健康检查通过仍需实际模型、搜索和抓取请求验收。

draw.io 已有独立的固定源码快照与构建流程，继续复用，不导出旧镜像。PlantUML 继续使用其 skill 的有界预检合同，不在此引入另一套渲染编排。

## 恢复已有 LiteLLM 数据

新机先恢复基础 env、用户复制的 OAuth token 目录和原生 `database.dump`，再执行下列命令。它复用已发布 Compose 和本机连接检查，只启动 PostgreSQL；代理已运行或数据库已有业务表即拒绝恢复。不复制旧机 PostgreSQL 目录，不使用 `--clean`。该流程仍待实体新机冷启动验收，不能用旧机临时容器恢复成功代替。

```bash
bash <<'RESTORE'
set -euo pipefail
./workbench service podman ensure
runtime_tools="$HOME/.local/share/feipi-workbench/services/tools"
source "$runtime_tools/lib/podman.sh"
podman_require_runtime
set -a
source "$HOME/.env"
set +a
agent_service_data_root
if [[ "$(podman inspect litellm-proxy-podman --format '{{.State.Running}}' 2>/dev/null || true)" == true ]]; then
  echo 'LiteLLM 已运行；先核对新机状态，未恢复数据库。' >&2
  exit 1
fi
dump="$HOME/feipi-restore/litellm/database.dump"
[[ -f "$dump" ]] || { echo '缺少原生 database.dump。' >&2; exit 1; }
mkdir -p "$AGENT_SERVICE_DATA_DIR/postgres" "$AGENT_SERVICE_DATA_DIR/litellm/chatgpt-tokens"
podman_compose --env-file /dev/null -f "$runtime_tools/gateway/litellm/compose/docker-compose.yml" up -d postgres
for ((attempt=0; attempt<60; attempt++)); do
  if podman exec litellm-db-podman pg_isready -U litellm -d litellm > /dev/null 2>&1; then
    break
  fi
  sleep 2
done
podman exec litellm-db-podman pg_isready -U litellm -d litellm > /dev/null
tables="$(podman exec litellm-db-podman psql -U litellm -d litellm -Atc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")"
[[ "$tables" == 0 ]] || { echo '目标库已有业务表，未覆盖。' >&2; exit 1; }
podman exec -i litellm-db-podman pg_restore -U litellm -d litellm --exit-on-error < "$dump"
./workbench service litellm up
RESTORE
```

恢复成功且 readiness 通过后，继续执行原客户端的真实请求。若恢复失败，保持代理未启动并保留日志；不要在已有部分导入结果上盲目重复导入。

## 登录自启与 Env Vault

恢复私有包、确认 `~/.env` 后，集中安装自启定义：

```bash
./workbench apply services
./workbench service startup install # 先备份受管 plist，写入运行副本路径并保存 env 本地 Git 快照
./workbench service startup check
./workbench service startup start   # 加载当前用户图形登录域；会替换同名旧自启任务
```

Env Vault 使用原生 WatchPaths 与 5 分钟兜底调度，不再依赖旧机 fswatch/xargs 管道；仅提交
`~/.local/env-vault/env` 到该私有目录的 Git 历史，不执行 hooks、不提交其他暂存文件、不上传。
Podman 自启复用默认本机 ensure，然后分别启动 LiteLLM、SearXNG、Crawl4AI 并等待就绪；
一个服务失败仍继续其他独立服务，最终返回失败并保留日志。

已安装原生 `~/.local/bin/session-browser` 时，同一入口额外安装独立的
`com.feipi.session-browser` 任务，直接运行原生 `serve`，只监听 `127.0.0.1:8848`。
不依赖 Podman，也不复制索引缓存；未安装该可选应用时仍只管理前两个任务。
退出或启动失败后保留原生日志，不循环重试掩盖端口冲突。

日志位于 `~/.local/state/feipi-workbench/logs/` 下对应任务名的 `.log` 和 `.error.log`。
加载成功只表示 LaunchAgent 注册完成；完整重启、三个服务的真实业务请求，以及 OpenClaw、Multica、
oMLX、图表渲染服务的各自恢复与验收仍须完成。

oMLX 使用系统与应用的原生启动能力，不另建同职责的 LaunchAgent。以下路径已在固定的 0.4.4 上实际操作：

1. 首次打开应用后执行 `omlx start --timeout 120`，确保设置页面能够连接服务器。
2. 在应用 `Settings → Server` 开启 `Automatically start server on launch`；恢复的旧设置可能关闭了它。
3. 右击 Dock 中的 oMLX，勾选 `Options → Open at Login`，核实菜单出现勾号。
4. 完整关机、开机并登录后，只检查控制状态和实际模型请求，不能先手动 start 再称自启通过。

Mac 配置已预留原生 CLI 路径，安装脚本会附加并验证 Apple 公证票据。遇到菜单栏显示提示时，可按提示进入系统设置的菜单栏选项显示 oMLX；该准备步骤不需要授予“完全磁盘访问”。原生首次 `start`、登录启动和重启后实际请求分别验收，不能互相替代。

## 配置和数据

- **SearXNG**：复用 Git 中的 settings 和固定镜像版本；启动脚本不自动加载根 `.env`。
- **Crawl4AI**：干净克隆默认使用不含秘密的 `env/.env.example`；需要代理或模型密钥时复制为忽略的 `env/.env.local`。现有本机 `.env` 已原样保留为 `.env.local`，运行中容器未重建。特殊路径可用 `CRAWL4AI_ENV_FILE` 显式指定。
- **LiteLLM**：只自动加载 `~/.env`，支持 Shell 赋值及变量引用；不读取项目 `.env`，也不复用已从文件删除的旧 shell 配置。`restart` 只重建 LiteLLM，首次搭建使用 `up`，需要重建整个服务栈时使用 `recreate`。新机需要人工恢复必要凭据或重新授权；就绪探测不证明上游模型请求一定成功。
- **OTel**：日志默认重新生成，不作为迁移前置。

默认本机数据位置：

```text
$HOME/Documents/service-data/
├── postgres/                 # LiteLLM 数据库
├── litellm/chatgpt-tokens/    # 本机授权状态
└── otel/                     # 可重新生成的日志
```

需要更换位置时只设置一个根目录，脚本推导子目录。LiteLLM 将下列变量写在 `~/.env`；OTel 仍读取当前 shell 中导出的值：

```bash
export AGENT_SERVICE_DATA_DIR="$HOME/LocalServiceData"
```

保存后再启动服务；OTel 的终端需先加载该变量：

```bash
make litellm-up
make otel-up
```

路径支持空格，不包含旧机用户名。启动前检查本地引擎；只有明确启动 LiteLLM/OTel 时才创建其本机数据目录。

镜像由仓库指定版本重新拉取。新数据库和重新授权可重建的状态不要求迁移；确有独有业务记录或必须保留的网关配置时，单独确定最小数据迁移范围，不能把启动定义等同于业务数据。

## 验证与边界

```bash
make setup
./workbench apply services
make doctor
python3 -m unittest discover -s tests -p test_service_bootstrap.py -v
```

`make doctor` 检查现有 SearXNG/LiteLLM 服务和仓库目录；服务未启动时返回非零，不代表新机依赖安装失败。`make setup` 单独检查启动前置，不强制启动所有可选服务。

回归覆盖不安装 Docker 的 Podman 环境、缺失引擎的退出码、干净克隆的 Crawl4AI、远端连接拒绝（包括 LiteLLM 的停止、日志和状态命令）、只读状态检查、数据根目录及 Compose 路径展开。隔离测试不会启动或停止真实容器；独立 JSON 展开测试使用已安装的 docker-compose 客户端，无需 Docker daemon，缺失时明确跳过。

2026-10-18 本机缓存中的 Crawl4AI、SearXNG、OTel、LiteLLM 与 PostgreSQL 镜像均核实为 ARM64。已有服务健康与隔离配置检查不等于在新 Mac 上完成冷启动；新机仍需验证拉取、挂载、网络与必要授权。没有将未执行的新机验证写成通过。

原有运行中的容器未因本次代码修改而重建。实际使用新配置前先评估对应服务的维护窗口，尤其是认证、数据库和挂载变更。
