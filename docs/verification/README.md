# 本地服务验收指南

以下命令从仓库根目录运行。尚未发布服务定义时，先完成 [本地服务准备](../setup-new-mac.md#首次准备)。

## 选择检查方式

| 要确认什么 | 怎么检查 | 通过条件 |
| --- | --- | --- |
| 源码改动是否通过回归 | `python3 -m unittest discover -s tests -p 'test_service*.py'` | 相关用例通过，记录跳过的环境检验 |
| 本机服务是否已发布 | `./workbench doctor services` | 确认运行来源，并查看 LiteLLM 就绪结果 |
| 某个服务是否运行 | `./workbench service <服务> status` | 所需容器正在运行 |
| 服务是否就绪 | 请求下方健康端点 | HTTP 检查成功 |
| 客户端任务是否可用 | 用日常客户端执行一次真实请求 | 返回任务所需的结果，使用的服务和授权符合预期 |

## 启动并检查就绪

只启动要验收的服务。工作台启动 SearXNG、LiteLLM 和 Crawl4AI 时会等待对应的 HTTP 检查。

| 服务 | 启动命令 | 检查方式 |
| --- | --- | --- |
| SearXNG | `./workbench service searxng up` | `curl -fsS http://127.0.0.1:8873/healthz` |
| LiteLLM | `./workbench service litellm up` | `curl -fsS http://127.0.0.1:4000/health/readiness` |
| Crawl4AI | `./workbench service crawl4ai up` | `curl -fsS http://127.0.0.1:11235/health` |
| FastMCP | `./workbench service fastmcp up` | `bash runtimes/fastmcp/scripts/test_searxng_mcp.sh` |
| OTel | `./workbench service otel up` | `./workbench service otel status` |

## 验证功能

### SearXNG

发送 JSON 搜索请求，确认 `results` 有内容。若结果为空，换一个已知有结果的查询，并查看搜索引擎日志。

```bash
curl -fsS 'http://127.0.0.1:8873/search?q=podman&format=json' | jq '.results | length'
```

### LiteLLM

用已配置的客户端和有效密钥发起一次模型请求，核对返回内容和模型。可先调用 `/v1/models` 核对可见模型，再使用相应的 Chat Completions 或 Responses 接口。 [客户端配置与请求示例](../../tools/gateway/litellm/README.md)

### Crawl4AI

抓取一个已知可访问的网页，确认响应含目标正文。使用 MCP 的客户端再从实际会话调用一次抓取工具。 [HTTP 与 MCP 验证示例](../../tools/crawl/crawl4ai/README.md)

### OTel

从已接入的客户端发送一条可识别的日志，检查清洗后的输出中是否出现对应记录。 [OTel 配置和数据位置](../../tools/gateway/otel/README.md)

## 故障排查

1. 先运行 `./workbench service <服务> status` 和 `./workbench service <服务> logs`，再决定是否重启。
2. 连接失败时，核对 `./workbench service podman check` 的本机连接及目标端口占用，例如 `lsof -nP -iTCP:8873 -sTCP:LISTEN`。
3. LiteLLM 返回 502 时，查看网关日志，核对上游网络、代理与授权配置。需要查看数据库时运行 `./workbench service litellm logs postgres`。 [LiteLLM 排查说明](../../tools/gateway/litellm/README.md)
4. Crawl4AI 的 HTTP 健康检查通过但 MCP 调用失败时，核对客户端的 MCP 地址、容器日志和代理旁路设置。 [Crawl4AI MCP 配置](../../tools/crawl/crawl4ai/README.md#mcp-服务配置)

历史实机结果见 [工作台实机验收记录](../workbench-validation.md)。新环境分别记录检查、就绪探测、真实请求和跳过项。
