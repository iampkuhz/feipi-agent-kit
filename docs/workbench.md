# 工作台使用

从仓库根目录运行 `./workbench --help`。初次安装可直接查看 [Mac 安装指南](../components/mac/docs/setup.md) 或 [本地服务重建](setup-new-mac.md)。

## 安装和检查

在仓库编辑配置，再用 `./workbench install <组件>` 发布。`./workbench doctor <组件>` 检查已安装程序、配置或运行状态。安装出错时尝试恢复原受管文件，正常结束后会清理本次临时副本。

## 安装后怎样生效

| 安装目标 | 行为和生效方式 |
| --- | --- |
| `mac` | 补齐工具链、Agent CLI 和桌面依赖，发布 dotfiles 到 `~/.local/share/feipi-workbench/mac/dotfiles`，通过 Stow 链接 Zsh 入口和模块、Neovim、Qwen 语言配置、Karabiner 与 iTerm2。`.env` 由本机维护，单文件 `.zshrc` 只用于临时换机 |
| `skills` | 发布到已安装客户端。新对话会重新发现 |
| `codex` | 发布两个可选命名 Profile 到 `CODEX_HOME`（默认 `~/.codex`）。启动 CLI 会话时显式选择 |
| `services` | 检查本机 Podman 和 Compose，发布服务定义。按需执行 `service <名称> up` 或 `restart` |
| `openclaw` | 安装锁定程序与插件并发布配置。用 `./workbench service openclaw up` 启动网关 |
| `openclash` | 校验并应用路由覆写模块。模块有变化时由路由器流程重启并恢复选择，相同内容直接接管 |

Multica CLI 由 `install mac` 的 Homebrew 阶段补齐。平台服务由 Multica Cloud 提供，本机执行机通过官方 CLI 接入。详见 [Multica 使用说明](../components/multica/README.md)。

### 单个 Skill 发布

只更新 Codex 中的家庭健康 Skill，可同时指定客户端和技能名。

```bash
./workbench install skills --agent codex --skill feipi-health-maintain-family-records
```

`skills/deleted-skills.txt` 记录仓库历史中已删除 `SKILL.md` 的名称。安装器用它提示目标目录里的同名旧副本；名称相同不等于来源已确认，也不会因此自动删除。确认删除时应逐项核对目标路径与来源。

工作台发布使用独立运行副本。Mac 的 Podman VM、桌面授权及应用验收见 [Mac 安装说明](../components/mac/docs/setup.md)。OpenClash 的 SSH、API 和真实网络验收见 [组件手册](../components/openclash/README.md)。

## 用户、项目和会话配置

| 范围 | 工作台管理 | 各自维护 |
| --- | --- | --- |
| 用户 | `components/codex/profiles/` 是 Codex 命名 Profile 源码。`feipi-develop` 允许工作区写入，扩权请求由用户审批，默认无网络。`feipi-review` 使用只读权限。共享 skill 与 OpenClaw 受管配置继续按已有组件发布。 | Codex 基础 `config.toml`、账号、模型、项目的信任决定、个人插件和 MCP 属于本机。OpenClaw 的登录、状态、渠道身份与密钥留在本机私有位置。 |
| 项目 | `templates/agent/projects.json` 用 Git 远端身份找到已有项目入口。`project init` 写入相应 checkout 的 `tmp/feipi-agent-kit/project.json`，记录相对路径和模板摘要。 | 项目维护自己的 `AGENTS.md`、`.codex/config.toml`、角色、Hook、规格、验收用例及 Gate。 |
| 会话 | `templates/agent/` 下共享开发、只读审阅和验证三种简报。启动命令显式声明本次权限，CLI 参数优先于已信任项目的默认设置。 | 任务内容、候选、获准动作、正式验收身份和运行凭证来自本轮与项目实际系统。 |

第一次安装用户档位并为一个项目初始化。目录可传仓库根、子目录或该项目的 checkout。

```bash
./workbench install codex
./workbench doctor codex
./workbench project init ../lexiflow
./workbench project doctor ../lexiflow
./workbench session review ../lexiflow
```

会话命令打印一份简报和可复制的 Codex CLI 命令。运行 CLI 命令或在现有对话粘贴简报，分别使用对应入口。现有对话由它自己的权限设置控制。正式验收按项目角色、候选与 Gate 规则执行。

新增项目时，在目录登记能够从仓库根解析的四个入口，并初始化一次。新 checkout 或 worktree 单独生成绑定。初始化可以重复运行，已有同版本且内容相同的文件会保留原时间。更新模板后，doctor 会识别版本差异，重新初始化即可刷新；用户 Profile 更新通过 `install codex` 发布。发现同名个人配置、本机漂移、路径越界或未知项目时，命令会报告具体冲突。绑定由目录生成，放在项目已忽略的 `tmp/`。现有项目若实际需要随仓分发某个 skill，仍走手册里的单 skill 项目安装。 [项目安装方式](agent-handbook.md#安装或更新-skill) · [Codex 配置优先级](https://learn.chatgpt.com/docs/config-file/config-basic)

## 命令与参数

尖括号表示必填，方括号表示可省略。各层命令支持 `--help`，例如 `./workbench service litellm logs --help`。

| 命令 | 参数与行为 |
| --- | --- |
| `workbench doctor [组件]` | `mac / skills / services / openclaw / openclash / codex`。省略时检查全部已启用组件，Codex 以安装回执为准 |
| `workbench install <组件>` | `mac / skills / services / openclaw / openclash / codex`。仅 `skills` 可选 `--agent <客户端>` 和 `--skill <已注册名称>` |
| `workbench project init [目录]` | 从项目 Git 根目录生成本机配置。省略目录时使用调用位置 |
| `workbench project doctor [目录]` | 只读检查项目身份、配置版本与现有入口 |
| `workbench session <模式> [目录]` | 生成 `develop / review / verify` 会话简报和 Codex CLI 启动命令 |
| `workbench service <服务> <操作>` | 管理工作台托管的服务，见下表 |

`--agent` 支持 `codex / claudecode / qwen / qoder / openclaw`。两个筛选项可分别使用，也可组合。

| 服务 | 操作 |
| --- | --- |
| `litellm / searxng / crawl4ai / fastmcp / diagrams / otel / omlx / openclaw` | `up / down / restart / status / logs` |
| `litellm logs [范围]` | 省略时查看网关日志，可指定 `postgres` 或 `all` |
| `podman` | `check / ensure` |
| `startup` | `check / install / start` |

OpenClaw 复用原生 LaunchAgent。`service openclaw up` 首次注册网关并等待就绪，已有网关直接复用。

oMLX 的受管服务配置在 `components/mac/config/omlx-service.json`。修改后运行
`./workbench service omlx restart`：工作台只合并其中明确管理的服务键到 oMLX 数据目录的
`settings.json`，保留 API key、模型目录、缓存等本机内容，再重启 Homebrew 服务并检查实际
监听端口和 `/v1/models` 接口。默认只监听本机 `127.0.0.1:8037`；服务启动和状态查询不需要 sudo。

## `.env` 本地历史

`./workbench install mac` 将普通 `~/.env` 的内容原样放到 `~/.local/state/feipi-workbench/env-history/.env`，权限为 `0600`，并把 `~/.env` 改为指向它的相对符号链接。首次安装可以创建空文件。已有有效的自定义 vault 链接继续使用。两份现有文件内容冲突时，安装保留两份并报错。

macOS 用户 LaunchAgent `com.feipi.env-history` 在安装、登录和环境文件变更时记录内容，并每分钟补查一次。没有图形登录会话时，任务随下次登录加载。

历史写入 `~/.local/state/feipi-workbench/env-history.git`。仓库权限为 `0700`，没有远端且禁用 Git 传输协议。版本包含凭据原文，仅供当前机器使用。已有旧 env vault 历史仍可按原路径查看。连续快速写入或休眠期间的修改以调度实际读到的稳定版本为准。

```bash
git --git-dir="$HOME/.local/state/feipi-workbench/env-history.git" \
  log --date=iso --format='%h %ad' -- .env
```

需要取出某一版时，可用 `git --git-dir="$HOME/.local/state/feipi-workbench/env-history.git" show <提交编号>:.env`，并把输出重定向到权限为 `0600` 的本机文件。

## 换机传输

全新重建时，把凭据手动写到新机的 `~/.env`，设为仅当前用户可读写（`chmod 600 ~/.env`）。已有 env vault 链接时，更新链接实际指向的文件。`.zshrc` 和受管配置由仓库安装。

一次性脚本位于仓库的 `tmp/copy-data.sh`，由 Git 忽略。脚本只复制 `~/Documents/life/` 下的四份资料：`child-growth-diary`、`家庭健康`、`2028.装修/home-renovation-playbook-2028` 和 `2030.房地产`。

在新机的仓库根目录运行 `bash tmp/copy-data.sh`，按提示输入旧 Mac 的用户名和 IP。脚本通过 SSH/rsync 逐项统计每个目录过滤前后的普通文件数和逻辑大小，按 B、KB、MB、GB 等单位显示，输入 `y` 才复制到新机 HOME 的对应位置。任一目录过滤后为空时停止。传输排除临时文件、密钥、设备身份、登录状态和模型权重。复制结束后用同一规则核对源与目标的文件内容。新 Mac 使用自己的 SSH 密钥和授权。

成长资料库中的 `10-Diary/` 和 `20-Originals/` 保存成长日记及原件，`40-Daily-Care/` 保存年度照护台账、原始记录和展示入口。换机后核对年度 Excel 的最近登记日期。离线页落后台账时，在 `40-Daily-Care/` 运行 `python3 可视化/dashboard.py` 生成页面。
