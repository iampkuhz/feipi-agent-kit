# Feipi Agent Kit

> 统一个人工作台：Mac 配置、Skills 与工具服务、Multica、OpenClaw、OpenClash。沿用本仓库 Git；源码集中维护，日常环境显式应用。

## 两个入口

```bash
./workbench                         # 日常菜单说明；不安装、不启动
./workbench doctor                  # 缺项、配置漂移、运行来源与服务状态
./workbench plan mac                # 查看具体受管文件与目标
./workbench diff mac                # 本机 ↔ 仓库；原文差异保存在私有目录
./workbench capture mac --select zsh/.zshrc  # 选定本机文件收回源码
./workbench apply mac               # 备份后发布运行副本

./develop mac path                 # 定位组件源码
./develop mac test                 # 组件回归
./develop mac run -- bash bootstrap/check.sh  # 显式运行源码命令
# 修改后再次 diff / apply，才进入日常环境
```

组件为 `mac / skills / services / multica / openclaw / openclash`。完整顺序、双向同步及失败续接见 [工作台使用与恢复](docs/workbench.md)；本次实际结果见 [切换验收](docs/workbench-validation.md)，来源与研究取舍见 [实施记录](docs/workbench-plan.md)。

Mac、Skills 和服务定义默认使用实拷运行副本；Multica 继续使用现有发布目录；OpenClaw 继续使用原私有状态目录。源码调试使用 `./develop <组件> run -- <命令>`；Skills 如需链接使用 `./develop skills link`，结束后 `./workbench apply skills` 恢复实拷。

新增组件放在 `components/`；既有 `skills / tools / rules / runtimes` 职责不变，不移动已有 Skill 路径。

## 环境配置

```bash
# 秘密保留在 ~/.env 所指向的本机私有 vault
./workbench private check
./workbench private backup openclaw
./workbench private backup multica
./workbench private backup openclash
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
| `feipi-multica-manage-tasks` | Multica 任务记录、静默进展、明确派发、跨工具交接与持久验收 |
| `feipi-video-read-url` | 视频 URL 取证、本地音视频提取与总结、覆盖复核；领域流程由调用方维护 |
| `feipi-xiaohongshu-read-note` | 小红书图文/视频笔记、顺序原图与独立来源证据提取（依赖同级视频 skill） |
| `feipi-mermaid-generate-diagram` | Mermaid 六类图、通用语法与本地渲染验收 |
| `feipi-plantuml-generate-diagram` | PlantUML 架构图、时序图、思维导图及通用作图唯一入口 |
| `feipi-drawio-generate-diagram` | draw.io 可编辑图表、Podman 本地渲染与图包校验 |
| `feipi-techreport-ppt-skill` | 技术报告 PPT 单页 |
| [feipi-writing-refine-text](skills/authoring/feipi-writing-refine-text/SKILL.md) | 精炼汇报等文稿并交付问题清单，也从对话和要点提炼自然回复 |
| `feipi-dingtalk-send-webhook` | 钉钉群机器人 webhook |

## 常用命令

```bash
make help                      # 查看所有可用命令
make setup                     # 只读检查服务依赖
./workbench apply skills       # 备份后实拷安装 Skills
make install VERBOSE=1         # 兼容实拷安装入口；install-links 仅用于源码调试
make searxng-up / down / restart / logs
make litellm-up / down / restart / logs
make doctor                    # 健康检查
```

安装输出区分新增、更新、跳过、清理和警告，终端自动启用颜色与粗体；`COLOR=never` 禁用样式，`COLOR=always` 强制启用，非空 `NO_COLOR` 优先禁用。更多选项见 [操作手册](docs/agent-handbook.md#skills-管理)。
