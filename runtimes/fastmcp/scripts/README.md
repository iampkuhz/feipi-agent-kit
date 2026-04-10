# FastMCP Scripts

## test_searxng_mcp.sh

测试 SearXNG MCP 工具的脚本。

### 用法

```bash
# 使用默认参数
./runtimes/fastmcp/scripts/test_searxng_mcp.sh

# 指定搜索查询和结果数
./runtimes/fastmcp/scripts/test_searxng_mcp.sh "Python MCP protocol" 3
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 查询 | Python MCP | 搜索关键词 |
| 最大结果数 | 5 | 返回结果数量（1-20） |

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| MCP_URL | http://localhost:18080/mcp | MCP 服务地址 |

### 输出示例

```
=== SearXNG MCP 测试 ===
MCP URL: http://localhost:18080/mcp
查询：Python MCP
最大结果数：5

Step 1: 获取 Session ID
Session ID: xxx

Step 2: Initialize
Initialize 成功

Step 3: 调用 search_web
=== 搜索结果 ===
查询：Python MCP
返回结果数：5

1. MCP Python SDK - GitHub
   URL: https://github.com/modelcontextprotocol/python-sdk
   引擎：brave
   摘要：The official Python SDK for Model Context Protocol...

=== 测试完成 ===
```
