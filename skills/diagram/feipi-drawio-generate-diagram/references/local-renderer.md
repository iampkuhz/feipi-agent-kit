# Podman 本地渲染准备

运行时依赖：主机 Python 3.10+、Podman，以及已准备好的 `localhost/feipi/drawio-renderer:1` 镜像和 `feipi-drawio` 容器。服务工具位于 Agent Kit 仓库 `tools/diagram/drawio/`；已安装的 skill 本身不需要仓库路径，只有首次环境准备需要该工具。

在 Agent Kit 仓库根目录执行：

```bash
bash tools/diagram/drawio/drawio.sh prepare
bash tools/diagram/drawio/drawio.sh up
```

- macOS 尚无 Podman 时先 `brew install podman`；`prepare` 在明确准备阶段初始化/启动默认本地 machine。Linux 使用本地 rootless Podman。
- `prepare` 下载固定 draw.io 源码并核对 SHA-256，在 Podman 中安装 Chromium、中文 Noto 字体和固定 Playwright 版本。无需宿主 Node、Java 或浏览器。
- `AGENT_DRAWIO_SERVER_PORT` 默认 8200，取值 1024–65535；服务绑定 `127.0.0.1`。工具和 skill 必须使用相同端口。
- 如虚拟机下载依赖需要本机代理，可仅对准备命令设置 `AGENT_DRAWIO_BUILD_PROXY=http://host.containers.internal:7890`。主机下载使用已有 HTTP 代理环境。不得把该代理用于渲染 HTTP 客户端。
- `up` 复用匹配的容器；同名但镜像/端口不同则停止并报告，不接管或删除。更新镜像后需用户安排旧容器替换；普通作图不自动升级环境。
- `status` 检查健康，`logs` 查看最后 50 行，`down` 显式停止专用容器。缺少容器或服务失败时给出这条准备路径，不切换在线服务。

[工具来源与准备说明](https://github.com/iampkuhz/feipi-agent-kit/tree/main/tools/diagram/drawio)。仅准备阶段访问软件发行源；源图仅提交本机 `/render`。服务用镜像内 draw.io `Graph` 实现渲染，不是自行拼装 SVG。
