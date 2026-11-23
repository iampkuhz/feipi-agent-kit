# FastMCP 搜索网关

网关通过 Podman 运行，只监听本机 `127.0.0.1:18080`。MCP 客户端使用 `http://127.0.0.1:18080/mcp`，传输方式为 Streamable HTTP。

```bash
./workbench install services
./workbench service searxng up
./workbench service fastmcp up
./workbench service fastmcp status
```

`searxng_search_web` 使用 SearXNG 返回搜索结果。在已运行网关的机器上，可用 `bash runtimes/fastmcp/scripts/test_searxng_mcp.sh` 验证一次真实调用。日志使用 `./workbench service fastmcp logs` 查看。

## 扩展

网关发现 `runtimes/fastmcp/<服务>/src/server.py` 导出的 `mcp` 实例，并用服务名作为工具前缀。镜像复制当前声明的运行模块。新增服务时一并更新 `Containerfile`，重新发布并重启网关。
