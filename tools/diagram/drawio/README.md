# draw.io Podman 本地渲染服务

为 `feipi-drawio-generate-diagram` 提供本地 `/health` 与 `/render`。只使用 Podman，适用于 macOS ARM64 的 Podman machine 和 Linux 本地 Podman。

```bash
# 主机依赖：Python 3.10+、curl、tar、Podman
bash tools/diagram/drawio/drawio.sh prepare
bash tools/diagram/drawio/drawio.sh up
bash tools/diagram/drawio/drawio.sh status
```

`prepare` 在 macOS 按需初始化/启动默认 machine，下载 draw.io 固定快照并校验 SHA-256，构建 `localhost/feipi/drawio-renderer:1`。下载依赖需要联网；主机用已有代理，容器构建需要代理时显式设置 `AGENT_DRAWIO_BUILD_PROXY`。不会改写系统代理、容器注册表或其他服务。

```bash
AGENT_DRAWIO_BUILD_PROXY=http://host.containers.internal:7890 \
  bash tools/diagram/drawio/drawio.sh prepare
```

`up` 创建/启动专用容器 `feipi-drawio`，端口默认 `127.0.0.1:8200`；可用 `AGENT_DRAWIO_SERVER_PORT` 改为 1024–65535。同名容器配置不匹配时拒绝复用。`down` 停止专用容器，`logs` 打印最后 50 行。

镜像使用 Debian 多架构 Chromium、Noto CJK 字体、Python 与 Playwright 1.55.0。draw.io 固定为 [v29.7.12](https://github.com/jgraph/drawio/tree/v29.7.12)，源码提交 `c9904435fd1a6795f6cad5c3908ec89d9afb8fb1`，压缩包 SHA-256 `90acf10c43751f245873506e6748d868e24da8bd863e96dd0aeeb48ba32baee7`。基础镜像和 Debian 系统更新按构建时发行源解析；更新后需重新验收，不声称位级可复现。

渲染复用官方 [export3.html](https://github.com/jgraph/drawio/blob/v29.7.12/src/main/webapp/export3.html) 及 `Graph.getSvg`，保存实际 cell 的文字/节点包围盒与路由点。浏览器只允许访问容器内部静态服务；所有外部 HTTP 请求失败，服务运行不使用在线导出端点。容器不挂载宿主目录，使用非 root 用户、只读文件系统和内存临时目录。

接口：`GET /health` 返回服务标识和版本；`POST /render` 接受 `{"xml":"<mxGraphModel>...</mxGraphModel>"}`，返回 SVG、base64 PNG、实际几何及 renderer 标识。请求最大 2 MiB，客户端超时 60 秒。该接口仅供受信任本地 skill 使用，不暴露到公网。

安装 skill 后可独立运行；工具只用于准备服务。升级工具后先重新构建，在维护窗口显式删除旧专用容器再 `up`；普通作图不会替换运行中容器。
