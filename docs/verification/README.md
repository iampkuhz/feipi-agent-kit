# 验证指南

> 如何验证 Agent Tools 重构已落地并可实际使用

---

## 验证清单

### 1. 目录结构验证

```bash
# 检查核心目录是否存在
ls -d skills rules commands tools runtimes docs
```

**预期结果**：所有目录存在

### 2. SearXNG 服务验证

```bash
# 启动服务
make searxng-up

# 等待 10 秒后检查健康状态
sleep 10
curl http://localhost:8873/healthz
```

**预期结果**：
- 容器启动成功
- 健康检查返回 200

```bash
# 测试搜索
curl -s "http://localhost:8873/search?q=test&format=json" | jq '.results | length'
```

**预期结果**：返回结果数量 > 0

### 3. LiteLLM 服务验证

```bash
# 配置环境变量
cp tools/gateway/litellm/env/.env.example tools/gateway/litellm/env/.env
# 编辑 .env 填入真实值（至少 BAILIAN_API_KEY）

# 启动服务
make litellm-up

# 等待 30 秒后检查健康状态
sleep 30
curl -s http://localhost:4000/health
```

**预期结果**：健康检查返回 200

```bash
# 测试模型调用
curl -s http://localhost:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" | jq .
```

**预期结果**：返回配置的模型列表

### 4. SearXNG MCP 服务验证

```bash
# 安装依赖
cd tools/search/searxng-mcp
uv sync

# 运行测试
./scripts/run.sh test
```

**预期结果**：测试通过

```bash
# 手动测试（需要 SearXNG 运行中）
uv run python -c "
from src.client import SearXNGClient
import asyncio

async def test():
    client = SearXNGClient()
    results = await client.search('test query', max_results=3)
    print(f'Found {len(results)} results')

asyncio.run(test())
"
```

**预期结果**：返回搜索结果

### 5. Claude Code 集成验证

**步骤 1**：配置 MCP Server

在 `~/.claude/settings.local.json` 中添加：

```json
{
  "mcpServers": {
    "searxng": {
      "command": "uv",
      "args": ["run", "python", "src/server.py"],
      "cwd": "/Users/zhehan/Documents/tools/llm/skills/agent-skills/tools/search/searxng-mcp",
      "env": {
        "SEARXNG_BASE_URL": "http://localhost:8873",
        "SEARXNG_TIMEOUT": "30.0"
      }
    }
  }
}
```

**步骤 2**：启动 MCP 服务

```bash
# 在 Claude Code 中验证
# Claude Code 会自动启动配置的 MCP 服务
```

**步骤 3**：使用工具

在 Claude Code 中输入：

```
使用 search_web 搜索 "Python async best practices"，返回 3 条结果
```

**预期结果**：返回 3 条搜索结果，包含 title、url、snippet、engine 字段

### 6. 健康检查脚本验证

```bash
# 运行健康检查
./scripts/doctor/check.sh
```

**预期结果**：显示各项检查状态

---

## 常见问题排查

### SearXNG 无法启动

**症状**：容器启动失败或健康检查失败

**排查步骤**：
1. 检查 settings.yml 语法：`docker compose -f tools/search/searxng/compose/docker-compose.yml config`
2. 查看日志：`docker compose -f tools/search/searxng/compose/docker-compose.yml logs`
3. 检查端口占用：`lsof -i :8873`

### LiteLLM 返回 502

**症状**：API 调用返回 502 错误

**可能原因**：容器内代理配置问题

**解决方案**：
1. 检查 compose 文件中的代理设置（应清空）
2. 重启服务：`make litellm-restart`

### MCP 服务无法连接

**症状**：Claude Code 提示 MCP 服务不可用

**排查步骤**：
1. 检查 SearXNG 是否运行：`curl http://localhost:8873/healthz`
2. 手动运行 MCP 服务：`cd tools/search/searxng-mcp && ./scripts/run.sh stdio`
3. 检查 Claude Code 配置中的路径是否正确

---

## 完成定义

满足以下**全部条件**时，可判定重构已实际落地：

### 基础条件

- [x] `tools/` 目录结构已创建
- [x] `rules/` 目录已创建
- [x] `commands/` 目录已创建
- [x] `runtimes/fastmcp/` 已创建

### 服务验证

- [x] LiteLLM 已配置到 `tools/gateway/litellm/`
- [x] SearXNG 已配置到 `tools/search/searxng/`
- [x] 服务可正常启动和停止

### 新增服务

- [x] SearXNG MCP 已创建于 `tools/search/searxng-mcp/`
- [x] MCP 服务可通过测试

### 集成验证

- [ ] SearXNG MCP 可在 Claude Code 中使用
- [ ] 搜索工具返回有效结果
- [ ] 错误处理清晰可读

### 文档完整

- [x] README.md 已更新
- [x] AGENTS.md 已更新
- [x] 各服务 README 完整
- [x] 运行说明清晰

---

## 后续验证计划

1. **Crawl4AI 服务**：当实现后添加验证步骤
2. **更多 MCP 工具**：当新增后添加验证步骤
3. **自动化测试**：添加 CI/CD 验证

---

## 参考

- [docs/architecture/overview.md](architecture/overview.md) - 架构说明
- [README.md](../README.md) - 仓库总览
- [AGENTS.md](../AGENTS.md) - Agent 行为指南
