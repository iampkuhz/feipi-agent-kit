# 新 Mac：从配置重建本地服务

本仓库保存服务定义；Podman、podman-compose、Python 3.10+ 等机器依赖由 Dotfiles 安装。不复制旧机容器、镜像、Podman 虚拟机或缓存，不需要 NAS。

## 首次准备

```bash
# 先完成 Dotfiles 初始化，再进入本仓库。
# macOS 仅首次且尚无 machine 时执行 init；已有 machine 不要重复创建。
podman machine list
podman machine init
podman machine start

# 只检查依赖、默认本地连接和服务定义，不安装或启动任何服务。
make setup
```

已有运行中的 Podman machine 时跳过 init/start。连接不是本机时脚本报错，不接管远端环境；缺 provider 时安装 `podman-compose`，不要求 Docker Desktop。

## 按需启动

| 服务 | 启动 | 状态 | 本地探测 |
|---|---|---|---|
| SearXNG | `make searxng-up` | `make searxng-status` | `http://127.0.0.1:8873/healthz` |
| Crawl4AI | `make crawl4ai-up` | `make crawl4ai-status` | `http://127.0.0.1:11235/health` |
| LiteLLM + PostgreSQL | `make litellm-up` | `make litellm-status` | `http://127.0.0.1:4000/health/readiness` |
| OTel collector/cleaner | `make otel-up` | `make otel-status` | 通过容器状态核对，接收端口 4317/4318 |
| draw.io | `bash tools/diagram/drawio/drawio.sh prepare`，再 `up` | 同脚本 `status` | `http://127.0.0.1:8200/health` |

前四项均可使用 `make <服务>-down/restart/logs`；日志入口最多显示最后 50 行（LiteLLM 保留其原有日志入口）。重建、重启与停止都是显式动作，检查失败不会自动停止其他服务。

draw.io 已有独立的固定源码快照与构建流程，继续复用，不导出旧镜像。PlantUML 继续使用其 skill 的有界预检合同，不在此引入另一套渲染编排。

## 配置和数据

- **SearXNG**：复用 Git 中的 settings 和固定镜像版本；启动脚本不自动加载根 `.env`。
- **Crawl4AI**：干净克隆默认使用不含秘密的 `env/.env.example`；需要代理或模型密钥时复制为忽略的 `env/.env.local`。现有本机 `.env` 已原样保留为 `.env.local`，运行中容器未重建。特殊路径可用 `CRAWL4AI_ENV_FILE` 显式指定。
- **LiteLLM**：真实上游密钥等由当前 shell 导出，沿用其现有环境变量入口；不会自动 source 根 `.env`。新机需要人工恢复必要凭据或重新授权；就绪探测不证明上游模型请求一定成功。
- **OTel**：日志默认重新生成，不作为迁移前置。

默认本机数据位置：

```text
$HOME/Documents/service-data/
├── postgres/                 # LiteLLM 数据库
├── litellm/chatgpt-tokens/    # 本机授权状态
└── otel/                     # 可重新生成的日志
```

需要更换位置时只设置一个根目录，脚本推导子目录：

```bash
export AGENT_SERVICE_DATA_DIR="$HOME/LocalServiceData"
make litellm-up
make otel-up
```

路径支持空格，不包含旧机用户名。启动前检查本地引擎；只有明确启动 LiteLLM/OTel 时才创建其本机数据目录。

镜像由仓库指定版本重新拉取。新数据库和重新授权可重建的状态不要求迁移；确有独有业务记录或必须保留的网关配置时，单独确定最小数据迁移范围，不能把启动定义等同于业务数据。

## 验证与边界

```bash
make setup
make doctor
python3 -m unittest discover -s tests -p test_service_bootstrap.py -v
```

`make doctor` 检查现有 SearXNG/LiteLLM 服务和仓库目录；服务未启动时返回非零，不代表新机依赖安装失败。`make setup` 单独检查启动前置，不强制启动所有可选服务。

回归覆盖不安装 Docker 的 Podman 环境、缺失引擎的退出码、干净克隆的 Crawl4AI、远端连接拒绝（包括 LiteLLM 的停止、日志和状态命令）、只读状态检查、数据根目录及 Compose 路径展开。隔离测试不会启动或停止真实容器；独立 JSON 展开测试使用已安装的 docker-compose 客户端，无需 Docker daemon，缺失时明确跳过。

2026-10-18 本机缓存中的 Crawl4AI、SearXNG、OTel、LiteLLM 与 PostgreSQL 镜像均核实为 ARM64。已有服务健康与隔离配置检查不等于在新 Mac 上完成冷启动；新机仍需验证拉取、挂载、网络与必要授权。没有将未执行的新机验证写成通过。

原有运行中的容器未因本次代码修改而重建。实际使用新配置前先评估对应服务的维护窗口，尤其是认证、数据库和挂载变更。
