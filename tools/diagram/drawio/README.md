# draw.io Podman 本地渲染服务

为 `feipi-drawio-generate-diagram` 提供本地 `/health` 与 `/render`。只使用 Podman，适用于 macOS ARM64 的 Podman machine 和 Linux 本地 Podman。

```bash
./workbench install services
./workbench service diagrams up
./workbench service diagrams status
```

draw.io 监听 `127.0.0.1:8200`，首次运行会构建镜像。故障时用 `./workbench service diagrams logs` 查看日志。

## 维护镜像

单独维护镜像时用 `bash tools/diagram/drawio/drawio.sh prepare`，下载并校验固定源码快照后构建 `localhost/feipi/drawio-renderer:1`。容器构建需要代理时，使用现有的 `AGENT_DRAWIO_BUILD_PROXY`。

准备超时会保留原始错误。若返回 `download_confirmation_required`，检查网络和 Podman 状态。确认继续等待后可用现有的 `AGENT_DRAWIO_ALLOW_SLOW_DOWNLOAD=1` 重试准备。

镜像使用 Debian 多架构 Chromium、Noto CJK 字体、Python 与 Playwright 1.55.0。draw.io 固定为 [v29.7.12](https://github.com/jgraph/drawio/tree/v29.7.12)，源码提交 `c9904435fd1a6795f6cad5c3908ec89d9afb8fb1`，压缩包 SHA-256 `90acf10c43751f245873506e6748d868e24da8bd863e96dd0aeeb48ba32baee7`。基础镜像和 Debian 系统更新按构建时发行源解析；更新后需重新验收，不声称位级可复现。

渲染复用官方 [export3.html](https://github.com/jgraph/drawio/blob/v29.7.12/src/main/webapp/export3.html) 及 `Graph.getSvg`，保存实际 cell 的文字/节点包围盒与路由点。浏览器只允许访问容器内部静态服务；所有外部 HTTP 请求失败，服务运行不使用在线导出端点。容器不挂载宿主目录，使用非 root 用户、只读文件系统和内存临时目录。

接口：`GET /health` 返回服务标识和版本；`POST /render` 接受 `{"xml":"<mxGraphModel>...</mxGraphModel>"}`，返回 SVG、base64 PNG、实际几何及 renderer 标识。请求最大 2 MiB，客户端超时 60 秒。该接口仅供受信任本地 skill 使用，不暴露到公网。

安装 skill 后可独立运行；工具只用于准备服务。升级工具后先重新构建，在维护窗口显式删除旧专用容器再 `up`；普通作图不会替换运行中容器。
