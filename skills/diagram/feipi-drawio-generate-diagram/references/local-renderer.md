# Podman 本地渲染准备

运行时依赖：主机 Python 3.10+、Podman，以及已准备好的 `localhost/feipi/drawio-renderer:1` 镜像和 `feipi-drawio` 容器。服务工具位于 Agent Kit 仓库 `tools/diagram/drawio/`；已安装的 skill 本身不需要仓库路径，只有首次环境准备需要该工具。

首次作图缺环境时，在 skill 目录运行以下入口（其他目录使用脚本真实路径）：

```bash
python3 scripts/prepare_renderer.py
```

入口自动定位源码或安装器的 `.feipi-agent-kit-source` 标记，调用工具 `ensure`，完成后重新只读预检。已就绪时不下载、不重建、不重复启动；仅缺容器时复用镜像创建容器；镜像也缺失时才下载构建。随后用原图包目录重新执行作图命令。

独立拷贝且源码不在本机时，入口返回 `preparation_tool_missing` 和可执行的源码获取/重试命令；不猜测仓库位置、不自动下载执行工具。也可显式指定已获取的工具：

```bash
python3 scripts/prepare_renderer.py --tool-dir /path/to/feipi-agent-kit/tools/diagram/drawio
```

在 Agent Kit 仓库根目录可直接执行：

```bash
bash tools/diagram/drawio/drawio.sh ensure
```

- macOS 尚无 Podman 时先 `brew install podman`；显式准备时仅在 machine 缺失或停止后初始化/启动。运行中的 machine 引擎故障保留原始诊断，不重新创建或切换连接。Linux 使用本地 rootless Podman。
- `prepare` 下载固定 draw.io 源码并核对 SHA-256，在 Podman 中安装 Chromium、中文 Noto 字体和固定 Playwright 版本。无需宿主 Node、Java 或浏览器。
- `AGENT_DRAWIO_SERVER_PORT` 默认 8200，取值 1024–65535；服务绑定 `127.0.0.1`。工具和 skill 必须使用相同端口。
- 如虚拟机下载依赖需要本机代理，可仅对准备命令设置 `AGENT_DRAWIO_BUILD_PROXY=http://host.containers.internal:7890`。主机下载使用已有 HTTP 代理环境。不得把该代理用于渲染 HTTP 客户端。
- `prepare` 显式重建镜像；`up` 只创建/启动容器、不拉取镜像。`ensure` 按缺失状态组合准备和启动。同名容器镜像/标签/端口不符时立即拒绝，保留原容器；更新镜像后需用户安排旧容器替换，普通作图不自动升级环境。
- `status` 检查健康，`logs` 查看最后 50 行，`down` 显式停止专用容器。缺少容器或服务失败时给出这条准备路径，不切换在线服务。

预检返回 `blocked` 时：`image_missing` / `container_missing` 按 `next_steps` 准备；`podman_missing` 先安装依赖；`engine_unavailable` / `podman_failed` / `podman_timeout` 查看原始诊断，不能仅凭退出码 125 推断缺容器；`container_mismatch` / `connection_rejected` 先核实配置；`container_stopped` 表示只读预检拒绝启动；`health_unavailable` 查看容器日志；`health_contract_mismatch` 核实端口上的服务身份。普通作图最多启动已有容器一次，健康探测有界等待 30 秒，不重试 `/render`。

[工具来源与准备说明](https://github.com/iampkuhz/feipi-agent-kit/tree/main/tools/diagram/drawio)。仅准备阶段访问软件发行源；源图仅提交本机 `/render`。服务用镜像内 draw.io `Graph` 实现渲染，不是自行拼装 SVG。
