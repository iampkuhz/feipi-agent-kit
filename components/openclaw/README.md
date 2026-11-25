# feipi-openclaw

日常操作统一从仓库根目录 `./workbench` 进入；本目录命令供组件维护与显式源码调试。安装与恢复见 [工作台手册](../../docs/workbench.md)。原独立仓库仅留作历史回退。

OpenClaw 的 macOS 配置仓库。版本基线由 `versions.json` 锁定 OpenClaw、Qwen provider 和腾讯微信插件。

```bash
# 在 feipi-agent-kit 根目录执行
./workbench install openclaw
./workbench service openclaw up
```

详细说明见 [部署手册](handbook/deployment.md)。

## 日常入口

| 目的 | 命令 |
|---|---|
| 安装锁定依赖并发布配置 | `./workbench install openclaw` |
| 启停、重启、状态与日志 | `./workbench service openclaw up`，同一入口支持 `down / restart / status / logs` |
| 只检查部署条件 | `bash components/openclaw/scripts/deploy.sh --check` |
| 检查运行状态 | `./workbench doctor openclaw` |
| 检查运行文件是否与仓库一致 | `bash components/openclaw/scripts/install-runtime.sh --check` |
| 源码回归和配置校验 | `bash components/openclaw/tests/run.sh`、`bash components/openclaw/scripts/validate-config.sh` |
| 检查 Gateway、provider、消息渠道 | `bash components/openclaw/scripts/doctor.sh` |
| 微信扫码登录 | `bash components/openclaw/scripts/weixin-login.sh` |
| 预览 skill 更新 | `bash components/openclaw/scripts/bootstrap.sh --dry-run` |
| 安装或更新 skill | `bash components/openclaw/scripts/bootstrap.sh` |
| 探测 MCP 外部服务 | `openclaw mcp doctor --probe` |

## 管理边界

- 仓库：`openclaw.json`、版本锁、skill 来源清单、可复用人格/策略模板、部署脚本。
- `~/.env`：唯一人工维护的环境变量和密钥来源。
- `~/.openclaw`：SQLite、会话、浏览器、插件、skills、日志、长期记忆和任务产物。

`~/.openclaw/.env` 软链接到 `~/.env`。配置、workspace 模板和语音 adapter 由 `./workbench install openclaw` 复制到运行目录；不用 Documents 软链接，因为 macOS LaunchAgent 会被系统文件访问控制阻塞。 语音消息复用同批安装的 `feipi-video-read-url`，通过本地 oMLX 使用 `Qwen3-ASR-1.7B-8bit`。启用语音转写时在全局环境中提供 `OMLX_API_KEY`。

业务路径使用 OpenClaw 原生 `${HOME}` 插值；workspace 文字使用 `~/`。本地 skill manifest
的 `source.repository` 支持 `~/`（当前用户）和 `./`、`../`（相对本组件），安装时解析真实路径，
不执行配置中的 Shell 表达式。独立家庭资料库仍须先恢复；缺少来源明确失败，不创建空资料库代替。

新机手动准备 `~/.env` 和外部资料库后，运行 `./workbench install openclaw`，再用工作台启动 Gateway。会话、记忆和登录状态由 OpenClaw 原生流程处理。

微信使用腾讯官方 `@tencent-weixin/openclaw-weixin` 插件。部署后运行 `bash components/openclaw/scripts/weixin-login.sh`，手机微信扫码确认，再向 ClawBot 发送“请只回复：微信接入成功”。扫码凭据保存在 `~/.env` 所在 vault；微信与 Telegram 私聊会话隔离。详细步骤及验收边界见[微信入口](handbook/deployment.md#10-微信入口)。

Telegram 提供 `/housing`、`/growth` 和 `/health`，没有 `housing_review`。成长日记的规则、文字、原始媒体单独放在 `~/Documents/life/child-growth-diary`；使用方式见该目录 `README.md`。MCP 服务统一定义在 `openclaw.json#mcp.servers`。

默认对话、Telegram 私聊和图片理解通过本机 LiteLLM 使用百炼 Token Plan 的 `deepseek-v4.1-flash-1017`。OpenClaw 用 `LITELLM_API_KEY_OPENAI` 访问网关，网关用 `BAILIAN_TOKEN_PLAN_API_KEY` 访问百炼。

记忆检索使用本机 SQLite 全文索引。迁入工作区记忆文件后，运行 `openclaw memory index --force --agent main` 更新索引，再用 `openclaw memory status --agent main` 核对。

日常照护工作簿、原件和展示入口随 `~/Documents/life/child-growth-diary/40-Daily-Care/` 迁移。日常照护查询读年度 Excel，`/growth` 查询读同一资料库下的 `10-Diary/`。用照护目录中的 `打开宝宝日常.command` 查看本机台账页面。

工作区规则要求微信中的宝宝照护日报和阶段汇总直接采用资料库查询脚本生成的 Markdown，保留日期标题、两列表格和睡眠归属日。

`/housing 装修 <原话和链接>` 先保存收件，再自动提取 B站视频或小红书视频/图文，补充摘要、关键词和可追溯证据。只保存链接、提取原文及必要图片/关键帧，不下载完整原视频；实际读取受限时回执明确报告部分完成或失败。资料保存在独立住宅装修库的 `00-Inbox` 和专属 `40-Assets/housing-<记录ID>/`，不进本配置仓库。`/housing 查找 灯带 散热` 查询记录及提取全文；`/housing 重新提取 <记录ID>` 重试，`/housing 复核 YYYY-MM` 只读汇总。三项 skill 的源码分别来自住宅装修库和 Agent Kit，由 `skill-list/` 安装，OpenClaw 只维护路由与安装声明。

### 成长日记接入与验收

`/health` 定向使用 Agent Kit 中的 `feipi-health-maintain-family-records`，维护 `~/Documents/life/家庭健康`。示例：`/health 更新奶奶头疼的进展：……`、`/health 归档这些体检报告`（附文件）、`/health 查询某成员历年报告`。照片说明或文件说明中带上命令，保留原消息与附件；持续事件在同一记录追加，监测数据按需记录。该入口走 Agent 读取 skill 并操作本地资料，不新增收件插件。源码修改后用工作台按 skill 定向实拷到 Codex/OpenClaw；用 `./workbench install openclaw` 发布配置后重启 Gateway。资料和来源只在健康库维护，不进本配置仓库。

`feipi-growth-diary` 插件代码随独立成长资料库的 skill 安装，配置仅在本仓库 `openclaw.json` 声明。收件走 Gateway 官方 `before_dispatch` 接入点，先调用日记脚本保存原件，再独立分析图片或用本地 large-v3 转写。具体用法与原件限制维护在 `~/Documents/life/child-growth-diary/README.md`。

该本地 Git skill 显式启用 `setup.useLocalWorkingTree`：安装器要求当前分支与 manifest ref 相同，记录基准 commit 和运行源码树 SHA-256，不自动提交 Git；其他 manifests 仍按锁定 Git ref 克隆安装。tests/evals/缓存不安装进 live skill。

原件字节校验、分维度字段、语音确认、错误与恢复测试入口：独立 skill 的 `tests/run.sh`。Telegram `/growth 测试开始` 将当前会话隔离到资料库 `99-System/acceptance/`，`/growth 测试结束` 恢复正式收件。正式记录与验收材料均不进本配置仓库。
