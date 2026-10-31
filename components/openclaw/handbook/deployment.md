# OpenClaw 部署手册

## 1. 最终布局

```text
/Users/zhehan/Documents/tools/llm/feipi-agent-kit/components/openclaw/
  openclaw.json              唯一配置源
  versions.json              OpenClaw/provider 版本锁
  skill-list/                skill 下载与安装声明
  templates/workspace/       可复用人格和策略
  scripts/                   部署、校验和 runtime adapter

~/.env                       唯一环境变量源

~/.openclaw/
  .env                       -> ~/.env
  openclaw.json              仓库配置的部署副本
  scripts/...                runtime adapter 的部署副本
  workspace/AGENTS.md 等     workspace 模板的部署副本
  state/、sessions/、logs/等  OpenClaw 运行数据
```

仓库与运行目录职责不同：Git 管长期声明，`~/.openclaw` 管持续变化的状态。不要把整个 live workspace、skills、插件、浏览器数据或 SQLite 放进 Git。

配置和模板使用部署副本，不使用指向 `Documents` 的软链接。macOS LaunchAgent 后台进程读取此类软链接会受到文件访问控制限制，导致 Gateway 或 agent turn 阻塞。`~/.env` 位于用户主目录根部，可以安全地作为唯一软链接保留。

## 2. 部署前提

本仓库只支持 macOS，需要：

```bash
command -v git jq make node npm
```

仓库固定位置：

```bash
mkdir -p /Users/zhehan/Documents/tools/llm/openclaw
git clone git@github.com:iampkuhz/feipi-openclaw.git \
  /Users/zhehan/Documents/tools/llm/feipi-agent-kit/components/openclaw
cd /Users/zhehan/Documents/tools/llm/feipi-agent-kit/components/openclaw
```

`~/.env` 至少需要以下变量，格式参考仓库 `.env.example`：

- `LITELLM_BASE_URL`
- `LITELLM_CODE_MODEL_OPENAI`
- `LITELLM_API_KEY_OPENAI`
- `OPENCLAW_GATEWAY_TOKEN`
- `OPENCLAW_TG_BOT_TOKEN`
- `CLASH_PROXY`
- `HTTPS_PROXY`（和 `CLASH_PROXY` 填相同代理地址，原生 OpenAI 请求使用）
- `NO_PROXY`（至少包含 `127.0.0.1,localhost,::1`）

不要设置 `OPENCLAW_CONFIG_PATH`。CLI 和 LaunchAgent 都使用默认入口 `~/.openclaw/openclaw.json`。

如果访问 GitHub/npm 需要本机代理，可在当前 shell 临时设置：

```bash
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890
export all_proxy=socks5://127.0.0.1:7890
```

## 3. 一次性部署

先做只读检查：

```bash
make deploy-check
```

再执行完整部署：

```bash
make deploy
```

非交互执行使用：

```bash
make deploy YES=1
```

部署会依次完成：

1. 安装 `versions.json` 锁定的 OpenClaw。
2. 安装配置、全局 env 入口、workspace 模板和语音 adapter。
3. 安装版本锁中的 `@openclaw/qwen-provider` 和 `@tencent-weixin/openclaw-weixin`。
4. 重新覆盖插件生成的配置元数据，并校验配置与 SecretRef。
5. 根据 `skill-list/*.json` 安装 enabled skills。
6. 安装并重启 macOS LaunchAgent。
7. 检查 Gateway 和消息渠道；微信首次使用另行扫码登录。

## 4. 日常修改配置

只编辑仓库中的 `openclaw.json`，不要直接维护运行副本。修改后执行：

```bash
make runtime-install YES=1
make validate
openclaw gateway restart
make doctor
```

如果修改了 `~/.env`，执行完整的 `make deploy`，让 LaunchAgent 的服务环境重新生成。

## 5. Workspace 管理

`templates/workspace/manifest.json` 只列出值得长期版本管理的文件：

- `AGENTS.md`：稳定执行策略。
- `SOUL.md`：人格和表达方式。
- `USER.md`：长期、可复用的用户偏好。
- `IDENTITY.md` 和头像：稳定身份信息。

修改模板后运行：

```bash
make runtime-install YES=1
openclaw gateway restart
```

以下内容始终只留在 live workspace：

- `MEMORY.md` 和 `memory/` 日记。
- 附件、媒体、任务输出和临时文件。
- OpenClaw 或 sidecar 生成的运行状态。

安装脚本只覆盖 manifest 中列出的稳定文件，不删除上述动态内容。

## 6. Skills 管理

仓库只保存来源声明，不保存 skill 源码。每个 skill 对应一个 `skill-list/<name>.json`：

```json
{
  "version": 1,
  "name": "example-skill",
  "source": {
    "type": "git-subdirectory",
    "repository": "https://github.com/owner/repo.git",
    "ref": "main",
    "path": "skills/example-skill"
  }
}
```

常用命令：

```bash
make skills-check
make bootstrap
make bootstrap SKILL=skill-list/feipi-video-read-url.json
```

安装目标固定为 `~/.openclaw/skills/<skill-name>`。bootstrap 会下载 manifest 指定的 Git ref，比较来源 commit、内容和安装选项，再决定新增、覆盖或跳过。删除 manifest 不会自动删除已安装 skill。

## 7. Telegram 任务入口

`openclaw.json` 注册 `/housing`、`/growth`，并在 owner 私聊 prompt 中规定行为。`housing_review` 命令及其行为均不存在。

Housing 的业务 skill 从本机住宅装修 Git 仓库的已提交 `main` 安装；迁移前先恢复该仓库。图文和视频通用 skill 来自 Agent Kit，两个 manifest 锁定同一 commit。依次执行：

```bash
bash scripts/bootstrap.sh --manifest skill-list/feipi-video-read-url.json --yes
bash scripts/bootstrap.sh --manifest skill-list/feipi-xiaohongshu-read-note.json --yes
bash scripts/bootstrap.sh --manifest skill-list/feipi-housing-capture-inbox.json --yes
make runtime-install YES=1
openclaw gateway restart
```

首次接入或更新后，旧 Telegram 会话若仍使用原流程，先发送 `/new` 刷新会话；已有笔记和聊天历史保留。随后用 `/housing 装修 <链接>` 验证自动收件、字幕/语音、实际读图及摘要回写，再用 `/housing 查找 <提取内容中的词>` 验证全文查找。小红书登录受限、视频缺少独立音频或画面未读时必须如实返回部分完成；安装和静态验证不能替代这些真实检查。

托管浏览器保持直连和严格 SSRF，只为小红书主站与分享短链声明精确域名例外。锁定版 OpenClaw 会拒绝“显式浏览器代理＋严格 SSRF”的组合；不要通过允许整个私有网络解决。Telegram、模型和视频提取仍按各自环境配置使用代理。浏览器若需要登录，由用户在正常浏览器中完成，不导出登录凭据。

`/growth` 使用 `feipi-growth-record-diary`，规则和数据在 `/Users/zhehan/Documents/life/child-growth-diary` 独立维护。该目录同时是本地 Git skill 来源；从零部署时先恢复它，再执行：

```bash
make bootstrap SKILL=skill-list/feipi-growth-record-diary.json
make runtime-install YES=1
```

Gateway 重启后，用“文件 / 不压缩”发送附件并写 `/growth YYYY-MM-DD <原话>`；日期可省略。`/growth 查询 YYYY-MM-DD 到 YYYY-MM-DD` 只读返回素材。普通 Telegram 照片保留平台收到版本，不能宣称为手机原图。云端 Bot API 的 20 MB 下载限制用 Mac 本地原文件导入解决；本次不部署本地 Bot API。[Telegram getFile](https://core.telegram.org/bots/api#getfile)

完整使用方法和原件传输边界见独立资料库的 `README.md`。日记、原件和后续导出均不进本仓库，也不进入资料库源码 Git；需单独备份。静态校验与本地收件测试通过后，仍需 Telegram 新消息验收，才可确认该渠道端到端可用。

用户选择保留成长资料库的 Documents 位置，并手动为 Gateway 后台进程配置 macOS 文件访问权限。本机 LaunchAgent 使用 `/opt/homebrew/opt/node/bin/node`；授权方法和授权后的查询、附件验收顺序维护在独立资料库 `README.md`。后台访问阻塞时不自动迁移目录。

## 8. MCP 服务

MCP 定义统一位于 `openclaw.json` 的 `mcp.servers`：

- `crawl4ai`：`http://127.0.0.1:11235/mcp/sse`，当前启用。
- `fastmcp-gateway`：`http://127.0.0.1:18080/mcp`，当前因本机服务未监听而禁用。

OpenClaw 根据这些定义连接服务，并把服务暴露的工具交给 Agent。静态校验与真实探测是两回事：

```bash
make validate
make mcp-probe
```

外部 MCP 进程不由本仓库启动；端口未监听时应修复相应服务，而不是把服务源码、缓存或日志放进本仓库。

启用 `fastmcp-gateway` 时，先确认 18080 端口的服务已经启动，再把仓库配置中的 `enabled` 改为 `true`，执行 `make runtime-install YES=1`、`openclaw gateway restart` 和 `make mcp-probe`。不要只修改运行副本。

## 9. 验收与更新

部署后检查：

```bash
openclaw --version
openclaw gateway status
openclaw channels status --probe
make doctor
make mcp-probe
```

最后从 Telegram owner 私聊验证普通文本、语音转写、`/housing` 和带文件附件的 `/growth`。

OpenClaw 继续使用日期版本号；“OpenClaw 2.0”是 `v2026.8.1` 的发布名称。升级时同时修改 `versions.json` 中的 OpenClaw 与 Qwen provider，按新 schema 调整 `openclaw.json`，然后重新执行 `make deploy`。不要单独安装 `openclaw@latest`。

## 10. 微信入口

采用[腾讯维护的微信插件](https://github.com/Tencent/openclaw-weixin)，版本由 `versions.json` 独立锁定；当前为 `2.4.10`，要求 OpenClaw `>=2026.5.12`。本仓库的 `2026.9.2` 满足要求。插件提供个人微信 ClawBot 私聊和媒体收发，不配置群聊。

完整部署后执行：

```bash
make weixin-login
```

手机微信扫码并确认连接。脚本检查登录凭据和扫码者 ID，覆盖登录器自动生成的配置时间戳，随后重启 Gateway。扫码会过期，未完成时重新执行即可。账号索引不在仓库；从零部署后需重新扫码。

账号标签写在 `channels.openclaw-weixin.accounts.<实际账号ID>.name`，第一个账号为 `hanzhe`。新增第二个用户并标记为 `xuzan`：

```bash
bash scripts/weixin-login.sh --name xuzan
```

二维码必须由 xuzan 本人的微信扫描。脚本对比登录前后的账号与扫码者 ID，确认新增了独立用户并保留原账号后，才把新账号标签写回仓库配置并部署；重复标签或误扫已有用户时不会写入新标签。从零部署恢复未登录的标签时也用 `--name`，成功后替换该标签的旧账号 ID。标签供 OpenClaw 管理使用，不修改微信中的联系人备注，也不自动授予管理员权限。

凭据规则：

- 此插件不提供 token 或 SecretRef 配置字段，`openclaw.json` 只声明启用状态和账号标签，不写入 Token 或 `${ENV_NAME}`。
- 登录脚本把 `~/.openclaw/openclaw-weixin/accounts` 链接到 `~/.env` 真实文件所在 vault 的 `openclaw-weixin/accounts`。本机目标为 `~/.local/env-vault/openclaw-weixin/accounts`；若 `~/.env` 是主目录中的普通文件，也使用该 vault。
- 凭据目录权限为 `700`，账号文件为 `600`；插件放在账号目录内的上下文令牌也保留在 vault。已有非预期目录会拒绝覆盖，须先迁移原件。
- 普通账号索引、消息缓存和日志留在 `~/.openclaw`。备份时把 env vault 和运行态分别处理，均不加入本仓库。

此版本优先读取插件的旧格式账号 allowlist，没有该列表时使用扫码者 ID。首次扫码后只允许该微信用户访问；不要删除凭据里的 `userId`，也不要把通用 `openclaw pairing` 命令当作此插件的授权/撤销入口。插件配置 schema 没有 `dmPolicy` 或 `allowFrom` 字段，不添加无效的安全配置。

微信沿用现有 main agent 和模型；`session.dmScope=per-account-channel-peer` 按账号、渠道和用户隔离上下文。变更作用于所有渠道，原私聊会进入新的会话键，历史文件不会删除。两个用户仍共用 main agent 的 workspace、skills 和工具权限。Telegram 的专属 `/housing` prompt 和成长日记插件授权未扩展到微信，本节验收针对通用对话。

微信中可以直接发送文本命令，如 `/help`、`/status`、`/new`、`/stop`；插件另有 `/echo 内容` 用于不经过模型的收发检查。`请用 $weather 查询杭州天气` 这样的显式 skill 引用由 OpenClaw 解析，微信输入框没有 Control UI 的技能选择器。`@名字` 不会自动切换 agent；当前微信渠道只提供私聊。管理员命令另受 `commands.ownerAllowFrom` 限制。

验证顺序：

1. 微信 ClawBot 中发送 `请只回复：微信接入成功`，确认收到模型回复。
2. 连续发送两条关联问题，确认同一微信会话能延续上下文。
3. 按需要发送一张图片或一段语音，分别验证媒体处理。
4. 执行 `make runtime-check`、`make doctor`。无账号时状态提示未配置属于未完成扫码；状态正常也不能代替微信实际收发验收。

插件安装、版本检查和 Gateway 存活只能验证各自层级，收到新的微信消息并成功回复后才算文本端到端通过。

### Telegram 装修摘要入口的模型与交付

`channels.modelByChannel.telegram["7026716907"]` 使用 `openai/gpt-6-astra`，其余入口仍使用全局默认模型。该选择来自同源装修视频实测：默认模型能通过引用校验但误解画面归属，Astra 能定向补帧并保留来源歧义。该入口依赖本机 OpenAI 登录凭据；部署后须验证实际模型请求，模型列表可见不等于账户可调用。它的延迟和用量高于原模型，不能据此宣称所有素材都会自动无误。

Housing 新收件使用编号证据草稿和 `finalize` 完成构建、复核、入库；最多一次集中修复。最终回执来自实际笔记，Telegram 发送须有工具成功回执；不能把内部历史正文视为已送达。语义验收仍须检查原有层级、模糊术语、重要条件与画面时间归属，引用校验通过不等于内容正确。

OpenAI provider 显式使用 `request.proxy.mode=env-proxy`。终端 shell 的临时 `https_proxy` 不会自动传入 LaunchAgent；标准代理变量必须保存在唯一源 `~/.env`。修改后执行 `openclaw gateway install --force` 重新生成受管服务环境，再重启 Gateway，分别验证原生模型请求与 Telegram 回执。不要用隔离 CLI 成功代替 Gateway 实测，也不要把自动回退模型的成功当作所选模型成功。

`agents.entries.main.model.fallbacks=[]` 显式关闭模型失败时的自动回退，避免 Telegram 指定的质量模型失败后悄悄改用未通过该素材验收的全局默认模型。其余入口的首选模型不变；失败时应返回真实失败状态。
