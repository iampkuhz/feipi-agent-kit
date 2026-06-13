# Feipi Agent Kit

> **定位**：Agent 工具链和服务管理平台

## 快速开始

```bash
# 安装 Skills
make install-links

# 启动服务
make searxng-up          # SearXNG 搜索
make litellm-up          # LiteLLM 模型网关
```

## 目录结构

```
feipi-agent-kit/
├── .claude/            # Claude Code 配置
├── .codex/             # Codex 配置
├── docs/               # 文档
├── rules/              # 行为规则和约束规范
├── runtimes/           # 运行时框架（FastMCP）
├── scripts/            # 仓库级脚本
├── skills/             # Agent Skills
├── tools/              # 外部工具和服务
└── tmp/                # 临时文件
```

### tools/ 子目录

```
tools/
├── search/searxng/     # SearXNG 搜索引擎
├── crawl/crawl4ai/     # Crawl4AI 网页抓取
└── gateway/litellm/    # LiteLLM 模型网关
```

## 核心目录职责

| 目录 | 职责 | 触发方式 |
|------|------|----------|
| `skills/` | Agent 技能扩展 | 隐式/显式触发 |
| `rules/` | 行为规则约束 | 自动应用 |
| `tools/` | 外部服务封装 | MCP/脚本调用 |
| `runtimes/` | 运行时框架 | 服务启动 |

## 服务说明

### LiteLLM

本地 AI 模型网关，提供统一的 OpenAI 兼容接口。

```bash
make litellm-up
```

详情：[tools/gateway/litellm/README.md](tools/gateway/litellm/README.md)

### SearXNG

私有化元搜索引擎。

```bash
make searxng-up
```

详情：[tools/search/searxng/README.md](tools/search/searxng/README.md)

### Crawl4AI

网页抓取与内容提取。详情：[tools/crawl/crawl4ai/README.md](tools/crawl/crawl4ai/README.md)

## Skills 列表

| Skill | 用途 |
|-------|------|
| `feipi-skill-govern` | 创建、重构、自检和治理其他 skill |
| `feipi-patent-generate-innovation-disclosure` | 专利创新交底书生成 |
| `feipi-video-read-url` | 视频 URL 处理（YouTube/Bilibili） |
| `feipi-plantuml-generate-diagram` | PlantUML 通用作图主入口 |
| `feipi-plantuml-generate-architecture-diagram` | PlantUML 架构图生成 |
| `feipi-plantuml-generate-sequence-diagram` | PlantUML 时序图生成 |
| `feipi-techreport-ppt-skill` | 技术报告 PPT 单页生成 |
| `feipi-dingtalk-send-webhook` | 钉钉群机器人 webhook 消息 |

## 环境配置

仓库根目录 `.env.example` 是统一环境变量模板：

```bash
cp .env.example .env
```

各服务有独立 `env/` 目录覆盖特定配置。

## 常用命令

```bash
make install-links              # 安装 skills
make searxng-up / searxng-down  # 启停 SearXNG
make litellm-up / litellm-down  # 启停 LiteLLM
./scripts/bootstrap/setup.sh    # 初始化设置
./scripts/doctor/check.sh       # 健康检查
```

## 架构

```
┌──────────────────────────────────────┐
│        Claude Code / Codex           │
└────────────────┬─────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│skills │  │rules/ │  │tools/ │
│(能力) │  │(规范) │  │(服务) │
└───────┘  └───────┘  └───┬───┘
                           │
                ┌──────────▼──────────┐
                │   外部服务/API       │
                │ SearXNG, LiteLLM... │
                └─────────────────────┘
```

## 文档索引

- [AGENTS.md](AGENTS.md) - Agent 行为指南
- [docs/agent-handbook.md](docs/agent-handbook.md) - 操作手册
- [docs/governance/tool-usage.md](docs/governance/tool-usage.md) - 工具使用规范
- [rules/README.md](rules/README.md) - 行为规则
- [skills/authoring/feipi-skill-govern/](skills/authoring/feipi-skill-govern/) - Skill 治理
