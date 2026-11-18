# 新 Mac 服务重建

手动准备 `~/.env` 后，按需准备 Podman、发布服务定义并启动。服务从仓库配置重建，镜像重新拉取。需要延续旧环境时，单独恢复业务数据和凭据。

## 首次准备

先用 Mac 安装流程准备 Podman、Compose provider 和 Python 3.10+。 [Mac 安装指南](../components/mac/docs/setup.md)

```bash
./workbench service podman ensure
./workbench service podman check
./workbench install services
```

`ensure` 会复用运行中的默认本机 machine，发现远端或不明确的默认连接时停止。首次初始化最多等 15 分钟，启动最多等 5 分钟，随后等待引擎就绪。失败时保留已有 machine。`install services` 检查本地连接和 Compose，再发布服务定义。

## 按需启动

需要保留旧网关数据时，先完成 [LiteLLM 数据恢复](#恢复已有-litellm-数据)。

| 服务 | 启动 |
| --- | --- |
| SearXNG | `./workbench service searxng up` |
| Crawl4AI | `./workbench service crawl4ai up` |
| LiteLLM + PostgreSQL | `./workbench service litellm up` |
| OTel collector/cleaner | `./workbench service otel up` |
| draw.io | `bash tools/diagram/drawio/drawio.sh ensure` |

工作台启动 LiteLLM、SearXNG 和 Crawl4AI 时会等待 HTTP 就绪，最多 10 分钟。超时返回非零并保留容器，可查看 `./workbench service <服务> logs`。随后用实际客户端确认模型调用、搜索或抓取。 [服务验收指南](verification/README.md)

draw.io 复用固定源码快照，启动后用同一脚本的 `status` 检查。 [draw.io](../tools/diagram/drawio/README.md)

## 恢复已有 LiteLLM 数据

1. 准备基础 env 和同批 PostgreSQL 原生 dump。
2. 保持 LiteLLM 停止，确认目标 PostgreSQL 数据库为空，再用 `pg_restore --single-transaction --exit-on-error` 导入。
3. 启动 LiteLLM，等就绪检查通过后，用原客户端发起一次模型请求。

## 登录自启

完成服务定义发布并确认 `~/.env` 可用后，安装和启动登录任务。

```bash
./workbench service startup install
./workbench service startup check
./workbench service startup start
```

`~/.env` 由用户在本机维护。服务自启负责启动服务。升级后的 `startup start` 会停用并移除同一运行副本过去生成的 `com.local.envvault` 任务。
Podman 自启复用默认本机 ensure，然后分别启动 LiteLLM、SearXNG、Crawl4AI 并等待就绪；
一个服务失败仍继续其他独立服务，最终返回失败并保留日志。

已安装原生 `~/.local/bin/session-browser` 时，同一入口额外安装独立的
`com.feipi.session-browser` 任务，直接运行原生 `serve`，只监听 `127.0.0.1:8848`。
不依赖 Podman，也不复制索引缓存；未安装该可选应用时只创建 Podman 服务任务。
退出或启动失败后保留原生日志，不循环重试掩盖端口冲突。

日志位于 `~/.local/state/feipi-workbench/logs/` 下对应任务名的 `.log` 和 `.error.log`。
加载成功只表示 LaunchAgent 注册完成；完整重启、三个服务的真实业务请求，以及 OpenClaw、Multica、
oMLX、图表渲染服务的各自恢复与验收仍须完成。

### oMLX 登录启动

菜单栏版使用应用的原生登录启动方式。以下步骤在固定的 0.4.4 上操作过。

1. 首次打开应用后执行 `omlx start --timeout 120`，确保设置页面能够连接服务器。
2. 在应用 `Settings → Server` 开启 `Automatically start server on launch`；恢复的旧设置可能关闭了它。
3. 右击 Dock 中的 oMLX，勾选 `Options → Open at Login`，核实菜单出现勾号。
4. 完整关机、开机并登录后，只检查控制状态和实际模型请求，不能先手动 start 再称自启通过。

Mac 配置已预留原生 CLI 路径，安装脚本会附加并验证 Apple 公证票据。遇到菜单栏显示提示时，可按提示进入系统设置的菜单栏选项显示 oMLX；该准备步骤不需要授予“完全磁盘访问”。原生首次 `start`、登录启动和重启后实际请求分别验收，不能互相替代。

## 配置和数据

- **SearXNG**：复用 Git 中的 settings 和固定镜像版本；启动脚本不自动加载根 `.env`。
- **Crawl4AI** 使用仓库中的 `compose/docker-compose.yml` 和 `config/config.yml`。可选代理在 Compose 中配置，LLM 接口的凭据由调用进程提供。
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
./workbench service litellm up
./workbench service otel up
```

路径支持空格，不包含旧机用户名。启动前检查本地引擎；只有明确启动 LiteLLM/OTel 时才创建其本机数据目录。

镜像由仓库指定版本重新拉取。新数据库和重新授权可重建的状态不要求迁移；确有独有业务记录或必须保留的网关配置时，单独确定最小数据迁移范围，不能把启动定义等同于业务数据。

## 验证

```bash
./workbench doctor services
python3 -m unittest discover -s tests -p 'test_service*.py'
```

`./workbench doctor services` 检查 LiteLLM 就绪状态与运行来源。未启动时返回非零。

回归覆盖不安装 Docker 的 Podman 环境、缺失引擎的退出码、干净克隆的 Crawl4AI、远端连接拒绝（包括 LiteLLM 的停止、日志和状态命令）、只读状态检查、数据根目录及 Compose 路径展开。隔离测试不会启动或停止真实容器；独立 JSON 展开测试使用已安装的 docker-compose 客户端，无需 Docker daemon，缺失时明确跳过。

2026-10-18 的本机检查确认 Crawl4AI、SearXNG、OTel、LiteLLM 和 PostgreSQL 的缓存镜像为 ARM64。新机仍需检查镜像拉取、挂载、网络和授权。 [历史实机结果](workbench-validation.md)
