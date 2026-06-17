# 验证指南

> 如何验证 Feipi Agent Kit 重构已落地并可实际使用

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
# LiteLLM 脚本只读取当前 shell 环境，不读取仓库内 .env 文件。
# 如需覆盖默认值，把变量配置到你自己的 ~/.env，并打开新的 zsh。

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
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY:-sk-litellm-local-dev}" | jq .
```

**预期结果**：返回配置的模型列表

### 4. SearXNG MCP 服务 [已退役]

> SearXNG MCP（`tools/search/searxng-mcp/`）已于 2026-05 移除。如需网页搜索能力，请使用 Crawl4AI MCP（`tools/crawl/crawl4ai/`）。

### 5. Claude Code 集成验证

> 以下 SearXNG MCP 配置示例已随服务退役失效。如需配置 MCP Server，请参考 Crawl4AI MCP 的文档。

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

> SearXNG MCP 服务已退役。如需 MCP 搜索能力，请使用 Crawl4AI MCP（`tools/crawl/crawl4ai/`）。

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

- [x] LiteLLM 已配置到 `tools/gateway/litellm/`
- [x] SearXNG MCP 曾创建于 `tools/search/searxng-mcp/`（已于 2026-05 移除）

### 集成验证

- [ ] Crawl4AI MCP 可在 Claude Code 中使用
- [ ] 搜索工具返回有效结果
- [ ] 错误处理清晰可读

### 文档完整

- [x] README.md 已更新
- [x] AGENTS.md 已更新
- [x] 各服务 README 完整
- [x] 运行说明清晰

---

## 参考

- [docs/architecture/overview.md](architecture/overview.md) - 架构说明
- [README.md](../README.md) - 仓库总览
- [AGENTS.md](../AGENTS.md) - Agent 行为指南
