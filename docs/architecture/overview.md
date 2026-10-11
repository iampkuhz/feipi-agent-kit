# Feipi Agent Kit 架构说明

> **版本**：v0.1.0
> **最后更新**：2026-10-11

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Claude Code  │  │   Codex    │  │  其他客户端  │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          │                                       │
│                 ┌────────▼────────┐                              │
│                 │  commands/      │  ← 显式 Slash Commands       │
│                 │  (命令入口)      │                              │
│                 └─────────────────┘                              │
└──────────────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
│    skills/      │ │   rules/    │ │   tools/        │
│   (Agent 技能)   │ │  (行为规则)  │ │  (外部服务)      │
│                 │ │             │ │                 │
│  • PlantUML     │ │  • global   │ │  • search       │
│  • 技术汇报      │ │  • coding   │ │  • crawl        │
│  • 视频处理      │ │  • diagram  │ │  • gateway      │
│  • 集成工具      │ │  • review   │ │                 │
└────────┬────────┘ └─────────────┘ └────────┬────────┘
         │                                   │
         │                                   │ MCP
         │                          ┌────────▼────────┐
         │                          │   runtimes/     │
         │                          │   fastmcp       │
         │                          │  (运行时框架)    │
         │                          └────────┬────────┘
         │                                   │
         └───────────────────────────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │    外部服务/API       │
                              │                     │
                              │  • SearXNG         │
                              │  • LiteLLM         │
                              │  • Crawl4AI        │
                              └─────────────────────┘
```

---

## 目录分层

### 第一层：核心目录

| 目录 | 职责 | 类比 |
|------|------|------|
| `skills/` | Agent 能力扩展 | "技能树" |
| `rules/` | 行为约束规范 | "游戏规则" |
| `commands/` | 显式命令入口 | "控制台命令" |
| `tools/` | 外部服务封装 | "工具库" |
| `runtimes/` | 运行时框架 | "引擎/容器" |

### 第二层：功能分组

以 `tools/` 为例：

```
tools/
├── search/       # 搜索类服务
│   ├── searxng/      # SearXNG 本体
│   └── searxng-mcp/  # SearXNG MCP 封装 [已退役]
├── crawl/        # 抓取类服务
│   ├── crawl4ai/
│   └── crawl4ai-mcp/
└── gateway/      # 网关类服务
    └── litellm/  # LiteLLM 模型网关
```

### 第三层：服务内聚结构

每个服务/工具内部自包含：

```
tools/search/searxng/
├── README.md           # 服务说明
├── settings/           # 配置
│   └── settings.yml
├── compose/            # Docker Compose
│   └── docker-compose.yml
├── env/                # 环境变量
│   └── .env.example
└── scripts/            # 运维脚本
    └── searxng.sh
```

---

## 设计原则

### 1. 内聚优先于集中

**不推荐**（集中式）：
```
compose/          ← 全局 compose 目录
├── litellm.yml
├── searxng.yml
└── ...
```

**推荐**（内聚式）：
```
tools/gateway/litellm/compose/
tools/search/searxng/compose/
```

**原因**：
- 每个服务的配置、环境、脚本高度相关
- 服务的增删改不影响其他服务
- 便于独立测试和部署

### 2. 职责分离

| 目录 | 管什么 | 不管什么 |
|------|--------|----------|
| `skills/` | Agent 能力 | 外部服务运维 |
| `tools/` | 服务封装 | Agent 行为逻辑 |
| `rules/` | 约束规范 | 具体实现 |
| `commands/` | 命令入口 | 业务逻辑 |
| `runtimes/` | 框架模板 | 具体业务 |

### 3. 显式优于隐式

- `commands/` 中的命令必须显式触发（`/command`）
- `rules/` 中的规则自动应用
- `skills/` 可以隐式或显式触发

### 4. 可验证性

所有服务/技能必须具备：
- 健康检查端点或命令
- 测试脚本或测试用例
- 清晰的完成定义（DoD）

---

## 服务通信模式

### MCP 模式（推荐）

> 以下为历史架构图，SearXNG MCP 已退役。当前推荐使用 Crawl4AI MCP。

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Claude Code  │ ──► │  searxng-mcp │ ──► │   SearXNG    │
│              │ MCP │  (FastMCP)    │HTTP │  (搜索引擎)   │
│              │     │  [已退役]     │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

**优点**：
- 标准化协议（Model Context Protocol）
- 类型安全的工具定义
- 错误处理规范化

### HTTP 直连模式

```
┌──────────────┐     ┌──────────────┐
│  Python 脚本  │ ──► │   SearXNG    │
│              │HTTP │              │
└──────────────┘     └──────────────┘
```

**适用场景**：
- 非 MCP 客户端
- 批处理脚本
- 快速原型

---

## 扩展指南

### 新增 Skill

1. 使用 `feipi-skill-govern` 工作流
2. 在 `skills/` 下创建对应 layer 目录
3. 编写测试和文档

### 新增 MCP 服务

1. 从 `runtimes/fastmcp/templates/python/` 复制模板
2. 实现 server、client、schema
3. 在 Claude Code 中注册 MCP server

### 新增规则

1. 在 `rules/<category>/` 下创建 `.md` 文件
2. 定义清晰的适用场景和优先级
3. 提供正反示例

---

## 版本兼容性

| 组件 | 版本 | 依赖 |
|------|------|------|
| Python | 3.10+ | MCP 服务 |
| FastMCP | 0.2+ | MCP 服务 |
| Docker | 20+ | 所有服务 |
| Docker Compose | 2.0+ | 所有服务 |

---

## 参考

- [README.md](../README.md) - 仓库总览
- [AGENTS.md](../AGENTS.md) - Agent 行为指南
- [runtimes/fastmcp/](../runtimes/fastmcp/) - FastMCP Runtime
- [tools/](../tools/) - 外部工具
