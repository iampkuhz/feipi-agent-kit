# Feipi Agent Kit

> Agent 工具链和服务管理平台。为 Claude Code / Codex 等 AI 编码助手提供可复用的 Skills、工具服务和行为规则。

## 快速开始

```bash
# 1. 先由 Dotfiles 安装 Podman、podman-compose 与 Python，并准备本地 machine
# 2. 只读检查（失败会返回非零，不再打印虚假的初始化完成）
make setup

# 3. 安装 Skills 到 Claude Code / Codex
make install-links

# 4. 启动服务（按需）
make searxng-up          # SearXNG 搜索
make litellm-up          # LiteLLM 模型网关
make crawl4ai-up         # Crawl4AI（按需）
make otel-up             # 本机 OTel 日志（按需）

# 健康检查
make doctor
```

## 环境配置

```bash
cp .env.example .env
# 按注释填入所需的 API Key 等变量
```

仓库根目录 `.env.example` 只是参考模板，启动脚本不会自动 source。LiteLLM 只自动加载 `~/.env`，不读取项目 `.env`；Crawl4AI 需要覆盖时使用忽略的服务级 `.env.local`；SearXNG 使用已追踪的 settings。

新机只恢复配置、模板和启动入口，镜像重新拉取、缓存重建；详见 [新 Mac 服务重建](docs/setup-new-mac.md)，不依赖 NAS 或容器导出。

## 服务

| 服务 | 用途 | 启停 | 详情 |
|------|------|------|------|
| LiteLLM | 本地 AI 模型网关，提供 OpenAI 兼容统一接口 | `make litellm-up` / `litellm-down` | [tools/gateway/litellm/](tools/gateway/litellm/) |
| SearXNG | 私有化元搜索引擎 | `make searxng-up` / `searxng-down` | [tools/search/searxng/](tools/search/searxng/) |
| Crawl4AI | 网页抓取与内容提取 | `make crawl4ai-up` / `crawl4ai-down` | [tools/crawl/crawl4ai/](tools/crawl/crawl4ai/) |
| OTel | 本机日志采集与清洗 | `make otel-up` / `otel-down` | [tools/gateway/otel/](tools/gateway/otel/) |
| draw.io | Podman 本地渲染与中文图表预览 | `bash tools/diagram/drawio/drawio.sh ensure` | [tools/diagram/drawio/](tools/diagram/drawio/) |

## Skills

| Skill | 用途 |
|-------|------|
| `feipi-skill-govern` | Skill 的创建、重构、自检与治理 |
| `feipi-video-read-url` | 视频 URL 处理（YouTube / Bilibili / 小红书 / 严道单讲及文章视频） |
| `feipi-plantuml-generate-diagram` | PlantUML 架构图、时序图、思维导图及通用作图唯一入口 |
| `feipi-drawio-generate-diagram` | draw.io 可编辑图表、Podman 本地渲染与图包校验 |
| `feipi-techreport-ppt-skill` | 技术报告 PPT 单页 |
| [feipi-writing-refine-text](skills/authoring/feipi-writing-refine-text/SKILL.md) | 精炼汇报等文稿并交付问题清单，也从对话和要点提炼自然回复 |
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
