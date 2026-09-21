# Agent 操作手册

> 常用命令、服务管理、故障排查的完整参考。

## Skills 管理

```bash
# 安装 skills（入口实拷、运行目录链接，排除 tests/evals）
make install-links

# 安装到项目目录
make install-project PROJECT=/path/to/project

# 初始化新 skill
bash skills/authoring/feipi-skill-govern/scripts/init_skill.sh <name> --layer <layer>

# 校验 skill
bash skills/authoring/feipi-skill-govern/scripts/validate.sh <skill-path>

# 执行技能测试
bash <skill-path>/tests/run.sh
```

## 服务管理

### LiteLLM

```bash
make litellm-up          # 启动
make litellm-down        # 停止
make litellm-restart     # 重启
```

### SearXNG

```bash
make searxng-up          # 启动
make searxng-down        # 停止
make searxng-restart     # 重启
```

### SearXNG MCP [已退役]

> SearXNG MCP 服务（`tools/search/searxng-mcp/`）已于 2026-05 移除。如需网页搜索能力，请使用 Crawl4AI MCP。

## 仓库维护

```bash
# 初始化设置
./scripts/bootstrap/setup.sh

# 健康检查
./scripts/doctor/check.sh
```

## 服务接入指南

### Claude Code 使用 SearXNG MCP [已退役]

> SearXNG MCP 已移除。如需网页搜索能力，请使用 Crawl4AI MCP（`tools/crawl/crawl4ai/`）。

### 使用 LiteLLM 作为模型网关

1. 启动服务：`make litellm-up`
2. 客户端通过 `http://127.0.0.1:4000/v1` 访问

## 故障排查

### 服务无法启动

1. 检查端口占用：`lsof -i :<port>`
2. 查看日志：`docker compose logs`
3. 验证配置：检查 `env/` 和 `compose/` 文件

### MCP 服务不可用

1. 检查基础服务：`curl http://localhost:8873/healthz`
2. 检查 MCP 进程
3. 验证 Claude Code MCP 配置

### Skill 无法使用

1. 检查安装：`ls ~/.claude/skills/`
2. 检查入口文件权限和运行目录链接
3. 重新安装：`make install-links`
