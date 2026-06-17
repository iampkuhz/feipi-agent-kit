# Feipi Agent Kit

> Agent 工具链和服务管理平台。为 Claude Code / Codex 等 AI 编码助手提供可复用的 Skills、工具服务和行为规则。

## 快速开始

```bash
# 1. 初始化
make setup

# 2. 安装 Skills 到 Claude Code / Codex
make install-links

# 3. 启动服务（按需）
make searxng-up          # SearXNG 搜索
make litellm-up          # LiteLLM 模型网关

# 健康检查
make doctor
```

## 环境配置

```bash
cp .env.example .env
# 按注释填入所需的 API Key 等变量
```

仓库根目录 `.env.example` 是统一模板；各服务有独立 `env/` 目录可覆盖特定配置。

## 服务

| 服务 | 用途 | 启停 | 详情 |
|------|------|------|------|
| LiteLLM | 本地 AI 模型网关，提供 OpenAI 兼容统一接口 | `make litellm-up` / `litellm-down` | [tools/gateway/litellm/](tools/gateway/litellm/) |
| SearXNG | 私有化元搜索引擎 | `make searxng-up` / `searxng-down` | [tools/search/searxng/](tools/search/searxng/) |
| Crawl4AI | 网页抓取与内容提取 | — | [tools/crawl/crawl4ai/](tools/crawl/crawl4ai/) |

## Skills

| Skill | 用途 |
|-------|------|
| `feipi-skill-govern` | Skill 的创建、重构、自检与治理 |
| `feipi-patent-generate-innovation-disclosure` | 专利创新交底书生成 |
| `feipi-video-read-url` | 视频 URL 处理（YouTube / Bilibili） |
| `feipi-plantuml-generate-diagram` | PlantUML 通用作图主入口 |
| `feipi-plantuml-generate-architecture-diagram` | PlantUML 架构图 |
| `feipi-plantuml-generate-sequence-diagram` | PlantUML 时序图 |
| `feipi-techreport-ppt-skill` | 技术报告 PPT 单页 |
| `feipi-dingtalk-send-webhook` | 钉钉群机器人 webhook |

## 常用命令

```bash
make help                      # 查看所有可用命令
make setup                     # 初始化
make install-links             # 安装 Skills
make searxng-up / down / restart / logs
make litellm-up / down / restart / logs
make doctor                    # 健康检查
```
