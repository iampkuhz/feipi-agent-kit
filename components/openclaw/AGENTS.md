# feipi-openclaw 仓库约定

## 目标

维护 macOS 上可审计、可从零部署的 OpenClaw 配置。仓库只保存长期声明，`~/.openclaw` 只保存运行状态。

## 强约束

1. `~/.env` 是唯一环境变量源
- API Key、Token、密码和代理地址只在 `~/.env` 或其 vault 中维护。
- `~/.openclaw/.env` 必须软链接到 `~/.env`，仓库不保存真实 `.env`。
- 敏感配置使用 OpenClaw SecretRef，不使用明文或 `${ENV_NAME}` 代替 SecretRef。

2. 配置只有一个入口
- 唯一配置文件是仓库根目录的 `openclaw.json`。
- `scripts/install-runtime.sh` 将其复制到 `~/.openclaw/openclaw.json`；不配置 `OPENCLAW_CONFIG_PATH`。
- 只保留非默认行为和必要安全边界，以锁定版本的官方 schema 为准。

3. Git 与运行态分离
- Git 仓库固定为 `/Users/zhehan/Documents/tools/llm/feipi-agent-kit/components/openclaw`。
- `agents/`、`browser/`、`credentials/`、`logs/`、`memory/`、`npm/`、`plugins/`、`skills/`、`state/`、`tasks/`、`telegram/` 等运行目录不得入库。
- 仓库只保留最终态长期文件；一次性诊断产物不入库。

4. Workspace 只管理可复用模板
- `templates/workspace/` 保存人格、身份、用户偏好、Agent 策略和小型静态资源。
- `scripts/install-runtime.sh` 按 manifest 将这些文件逐个安装进 live workspace。
- `MEMORY.md`、`memory/`、媒体、任务产物和其他持续变化内容只留在 `~/.openclaw/workspace`。

5. Skills 只管理来源
- `skill-list/<name>.json` 每个 skill 一个文件，只声明 Git repository、ref、子目录和安装选项。
- 本组件不重复保存 skill 源码；共享源码仍在根目录 skills/。日常共享技能由 `workbench apply skills` 实拷，外部业务技能沿用本组件 bootstrap。
- 删除 manifest 不自动删除已安装 skill。

6. 版本成对锁定
- `versions.json` 同时锁定 OpenClaw 和 `@openclaw/qwen-provider`。
- 更新版本时先适配配置并通过 `make validate`，不得只升级全局 npm 包。

7. 验证
- 仓库和配置：`make validate`
- live 受管文件：`make runtime-check`
- Gateway、provider、Telegram：`make doctor`
- MCP 外部服务：`make mcp-probe`
- 静态通过不等于真实 Telegram、模型或 MCP 请求通过。

8. 仅支持 macOS
- 脚本不实现 Linux/Windows 分支。
