# Feipi Agent Kit

> 统一个人工作台：Mac 配置、Skills 与工具服务、Codex、Multica、OpenClaw、OpenClash。沿用本仓库 Git；源码集中维护，日常环境显式应用。

## 工作台入口

`./workbench` 提供安装、状态检查、项目初始化、会话简报和本地服务操作。`install` 补齐依赖并发布仓库配置，组件测试直接运行。命令和组件范围见 [工作台手册](docs/workbench.md)。安装、维护和验收可从 [文档导航](docs/README.md) 按任务查找。

## 环境配置

手动配置 `~/.env`。已有本机私有 vault 时，维护其实际文件。

仓库根目录 `.env.example` 只是参考模板，启动脚本不会自动 source。LiteLLM 只自动加载 `~/.env`，不读取项目 `.env`。Crawl4AI 和 SearXNG 直接使用仓库里的服务配置。

新机只恢复配置、模板和启动入口，镜像重新拉取、缓存重建；详见 [新 Mac 服务重建](docs/setup-new-mac.md)，不依赖 NAS 或容器导出。

## 服务

| 服务 | 用途 | 启停 | 详情 |
|------|------|------|------|
| LiteLLM | 本地 AI 模型网关，提供 OpenAI 兼容统一接口 | `./workbench service litellm up` / `./workbench service litellm down` | [tools/gateway/litellm/](tools/gateway/litellm/) |
| SearXNG | 私有化元搜索引擎 | `./workbench service searxng up` / `./workbench service searxng down` | [tools/search/searxng/](tools/search/searxng/) |
| Crawl4AI | 网页抓取与内容提取 | `./workbench service crawl4ai up` / `./workbench service crawl4ai down` | [tools/crawl/crawl4ai/](tools/crawl/crawl4ai/) |
| OTel | 本机日志采集与清洗 | `./workbench service otel up` / `./workbench service otel down` | [tools/gateway/otel/](tools/gateway/otel/) |
| oMLX | 本机 Apple Silicon 推理服务 | `./workbench service omlx status` / `./workbench service omlx restart` | [配置](components/mac/config/omlx-service.json) |
| draw.io | Podman 本地渲染与中文图表预览 | `bash tools/diagram/drawio/drawio.sh ensure` | [tools/diagram/drawio/](tools/diagram/drawio/) |

## Skills

仓库 Skill 明确声明自动匹配或仅显式调用，并随包提供 Cursor Custom Mode 徽章和 Codex 图标。宿主字段见[治理规范](skills/agent/skills/feipi-skill-govern/references/frontmatter-policy.md#调用策略与宿主适配)。Codex 母版与选图方法见[图标素材库](assets/skill-icons/README.md)。

| Skill | 用途 |
|-------|------|
| [feipi-health-maintain-family-records](skills/health/feipi-health-maintain-family-records/SKILL.md) | 家庭报告归档、健康事件、问题跟踪与按需监测；[双端使用与维护](docs/family-health-skill.md) |
| `feipi-skill-govern` | Skill 创建、重构与审计；功能交付契约、主题归类、验收与源码维护资料隔离 |
| [feipi-multica-manage-tasks](skills/collaboration/feipi-multica-manage-tasks/SKILL.md) | 本机 CLI 管理项目与资源；任务记录、派发、交接与验收。[设计依据](docs/multica-project-skill.md) |
| `feipi-video-read-url` | 视频 URL 取证、本地音视频提取与总结、覆盖复核；领域流程由调用方维护 |
| `feipi-xiaohongshu-read-note` | 小红书图文/视频笔记、顺序原图与独立来源证据提取（依赖同级视频 skill） |
| `feipi-mermaid-generate-diagram` | Mermaid 六类图、通用语法与本地渲染验收 |
| `feipi-plantuml-generate-diagram` | PlantUML 架构图、时序图、思维导图及通用作图唯一入口 |
| `feipi-drawio-generate-diagram` | draw.io 可编辑图表、Podman 本地渲染与图包校验 |
| `feipi-techreport-ppt-skill` | 技术报告 PPT 单页 |
| [feipi-writing-refine-text](skills/content/writing/feipi-writing-refine-text/SKILL.md) | 精炼汇报等文稿并交付问题清单，也从对话和要点提炼自然回复 |
| [feipi-interaction-review-output](skills/content/delivery/feipi-interaction-review-output/SKILL.md) | 审查手机与聊天渠道的展示、产物访问和用户操作；与文字精炼同级独立 |
