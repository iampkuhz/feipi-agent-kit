# 工作台使用

从仓库根目录运行 `./workbench --help`。初次安装可直接查看 [Mac 安装指南](../components/mac/docs/setup.md) 或 [本地服务重建](setup-new-mac.md)。

## 安装和检查

在仓库编辑配置，再用 `./workbench install <组件>` 发布。`./workbench doctor <组件>` 检查已安装程序、配置或运行状态。安装出错时尝试恢复原受管文件，正常结束后会清理本次临时副本。

## 安装后怎样生效

| 安装目标 | 行为和生效方式 |
| --- | --- |
| `mac` | 补齐工具链、Agent CLI 和桌面依赖，发布 dotfiles 到 `~/.local/share/feipi-workbench/mac/dotfiles`，通过 Stow 链接 Zsh 入口和模块、Neovim、Qwen 语言配置、Karabiner 与 iTerm2。`.env` 由本机维护，单文件 `.zshrc` 只用于临时换机 |
| `skills` | 发布到已安装客户端。新对话会重新发现 |
| `services` | 检查本机 Podman 和 Compose，发布服务定义。按需执行 `service <名称> up` 或 `restart` |
| `openclaw` | 安装锁定程序与插件并发布配置。首次使用原生 `openclaw gateway install --force`，发布后按需运行 `openclaw gateway restart` |
| `openclash` | 校验并应用路由覆写模块。模块有变化时由路由器流程重启并恢复选择，相同内容直接接管 |
| `multica` | 安装固定 CLI 和 Compose 定义。`doctor multica` 读取原生 personal profile 的 daemon 状态。任务、绑定和数据管理见[组件手册](../components/multica/README.md) |

### 单个 Skill 发布

只更新 Codex 中的家庭健康 Skill，可同时指定客户端和技能名。

```bash
./workbench install skills --agent codex --skill feipi-health-maintain-family-records
```

工作台发布使用独立运行副本。Mac 的 Podman VM、桌面授权及应用验收见 [Mac 安装说明](../components/mac/docs/setup.md)。OpenClash 的 SSH、API 和真实网络验收见 [组件手册](../components/openclash/README.md)。

## 命令与参数

尖括号表示必填，方括号表示可省略。各层命令支持 `--help`，例如 `./workbench service litellm logs --help`。

| 命令 | 参数与行为 |
| --- | --- |
| `workbench doctor [组件]` | `mac / skills / services / openclaw / openclash / multica`。省略时检查全部 |
| `workbench install <组件>` | `mac / skills / services / openclaw / openclash / multica`。仅 `skills` 可选 `--agent <客户端>` 和 `--skill <已注册名称>` |
| `workbench service <服务> <操作>` | 管理工作台托管的服务，见下表 |

`--agent` 支持 `codex / claudecode / qwen / qoder / openclaw`。两个筛选项可分别使用，也可组合。

| 服务 | 操作 |
| --- | --- |
| `litellm / searxng / crawl4ai / otel / omlx` | `up / down / restart / status / logs` |
| `litellm logs [范围]` | 省略时查看网关日志，可指定 `postgres` 或 `all` |
| `podman` | `check / ensure` |
| `startup` | `check / install / start` |

oMLX 的受管服务配置在 `components/mac/config/omlx-service.json`。修改后运行
`./workbench service omlx restart`：工作台只合并其中明确管理的服务键到 oMLX 数据目录的
`settings.json`，保留 API key、模型目录、缓存等本机内容，再重启 Homebrew 服务并检查实际
监听端口和 `/v1/models` 接口。默认只监听本机 `127.0.0.1:8000`；服务启动和状态查询不需要 sudo。

## `.env` 本地历史

`./workbench install mac` 默认启用 macOS 用户 LaunchAgent `com.feipi.env-history`。它在安装、登录和 `~/.env` 变更时检查内容，并每分钟补查一次。已有符号链接时读取其当前指向的文件。安装时文件尚未创建也可以先启用任务。没有图形登录会话时，任务随下次登录加载。

历史写入 `~/.local/state/feipi-workbench/env-history.git`。仓库权限为 `0700`，没有远端且禁用 Git 传输协议。版本包含凭据原文，仅供当前机器使用。已有旧 env vault 历史仍可按原路径查看。连续快速写入或休眠期间的修改以调度实际读到的稳定版本为准。

```bash
git --git-dir="$HOME/.local/state/feipi-workbench/env-history.git" \
  log --date=iso --format='%h %ad' -- .env
```

需要取出某一版时，可用 `git --git-dir="$HOME/.local/state/feipi-workbench/env-history.git" show <提交编号>:.env`，并把输出重定向到权限为 `0600` 的本机文件。

## 换机传输

全新重建时，把凭据手动写到新机的 `~/.env`，设为仅当前用户可读写（`chmod 600 ~/.env`）。已有 env vault 链接时，更新链接实际指向的文件。`.zshrc` 和受管配置由仓库安装。

一次性脚本位于仓库的 `tmp/copy-data.sh`，由 Git 忽略。LexiFlow 和 Session Browser 分别从 Git 远端克隆。脚本只复制 `~/Documents/life/` 下的四份资料：`child-growth-diary`、`家庭健康`、`2028.装修/home-renovation-playbook-2028` 和 `2030.房地产`。

在新机的仓库根目录运行 `bash tmp/copy-data.sh`，按提示输入旧 Mac 的用户名和 IP。脚本通过 SSH/rsync 逐项统计每个目录过滤前后的普通文件数和逻辑大小，按 B、KB、MB、GB 等单位显示，输入 `y` 才复制到新机 HOME 的对应位置。任一目录过滤后为空时停止。传输排除临时文件、密钥、设备身份、登录状态和模型权重。复制结束后用同一规则核对源与目标的文件内容。新 Mac 使用自己的 SSH 密钥和授权。
