# 新 Mac 分阶段部署

每次只执行一个仓库命令；脚本结束会说明人工检查项和下一步，不自动串到后一个阶段。软件、配置和可重建内容来自 Git 与固定安装入口；普通资料由用户运行直传命令，不盘点容量、不制作整机大包。新增入口的离线验证不等于新 Mac mini 已完成实机验收。

## 先准备网络

1. 新机完成 macOS 初始设置，使用普通管理员账号，连接 Wi-Fi。
2. 手动安装 [FlClash for oixCloud 0.9.3](https://github.com/pickrui/FlClash/releases/tag/v0.9.3)，本人登录、同步节点，确认浏览器能上网。
3. 下载[仓库 ZIP](https://github.com/iampkuhz/feipi-agent-kit/archive/refs/heads/main.zip)，在下载目录解压。让 Codex 打开解压目录，或在终端进入这个目录。此时不需要先装 Git/Python。
4. 从解压目录执行一次网络检查：

```bash
bash workbench new-mac network
```

人工检查：FlClash 节点已同步、浏览器能打开所需网站。终端检查仅覆盖 GitHub/Homebrew 来源；它优先保留已有代理，未指定代理且本机 7890 可达时为当前阶段启用该代理，不改 shell 启动文件。

## 新机安装与配置恢复

仍在 ZIP 解压目录执行：

```bash
bash workbench new-mac prepare
```

本阶段复用原前置脚本准备 CLT/Homebrew/Git/Python。需要时由本人输入一次管理员密码，然后克隆正式仓库到 `~/Documents/tools/llm/feipi-agent-kit`。已有正式仓库只核对来源，保留其改动，不自动 pull 或覆盖。人工检查：正式目录是 Git 仓库，Git/Python 可用。

**此后让 Codex/终端切换到正式仓库，后续命令都从正式仓库执行。** 原始 ZIP 不作为日常配置来源。

```bash
./workbench new-mac software
```

本阶段复用 `install mac --apps --agents`、备份发布公共配置和原生 Neovim 准备入口。人工检查：打开新终端、Neovim 和常用应用，确认能启动。此时尚未恢复个人 env、账号和业务数据。

完成下一节旧机导出/新机接收后，再执行：

```bash
./workbench new-mac config
```

本阶段校验并恢复小配置包、发布公共配置和技能。人工检查：新终端、代理和应用设置正常；代理需要时导入接收的 ZIP 并完成本人登录。私有包不会复制 SSH 私钥、登录态或模型权重。

```bash
./workbench new-mac services
```

本阶段创建/复用本机 Podman、准备服务定义、启动 SearXNG/Crawl4AI/OTel。人工检查：搜索、抓取与容器状态。LiteLLM 留待数据库恢复阶段；此时不安装业务自启，不启动 OpenClaw Gateway 或 Multica daemon。

## 旧机准备

在旧机正式仓库执行：

```bash
./workbench new-mac export
```

只导出并校验必要私有配置到 `~/feipi-mac-private`。首次导出目标必须尚不存在，已有目录不会覆盖。在 FlClash 中另行导出 `~/FlClash-backup.zip`。人工检查：命令显示配置包校验通过。

## 有线连接与传输

MacBook 没有网口也可以直接连接：

- 两端使用支持 Thunderbolt 的端口和雷雳线；Type-C 是接口形状，普通充电线/普通 USB 数据线不能直接当作雷雳网桥。
- 两台 Mac 的「系统设置 → 网络 → 雷雳网桥（Thunderbolt Bridge）」查看连接和 IPv4 地址；不存在该服务时先添加。
- 旧机「系统设置 → 通用 → 共享 → 远程登录」仅允许自己的账号。
- 新机命令中的 IP 使用旧机的雷雳网桥 IPv4。没有雷雳线时，两机连接同一 Wi-Fi，也能使用相同 SSH/rsync 命令；无需为了部署购买网口转接器。
- 双机连接只负责本地传输；新机继续通过 Wi-Fi/FlClash 获取互联网。脚本不会改网络设置或自动开 SSH。

参考：[Apple 雷雳 IP 连接](https://support.apple.com/zh-hk/guide/mac-help/mchld53dd2f5/26/mac/26)、[雷雳线与 USB-C 充电线的区别](https://support.apple.com/en-sg/111750)、[远程登录](https://support.apple.com/zh-cn/guide/mac-help/mchlp1066/mac)。

在新机正式仓库执行，替换唯一的连接参数：

```bash
./workbench new-mac receive 旧机账号@旧机IP
```

只接收小配置包和旧机已有的 FlClash ZIP，校验配置；小配置包目标已存在时停止，已用于新机网络准备的 FlClash ZIP 原样保留。人工检查后执行 `config`。

普通项目、资料、Env Vault 历史、模型和可选 OAuth token 目录，由用户主动运行一次：

```bash
./workbench new-mac copy-data 旧机账号@旧机IP
```

它只对固定目录执行 rsync，不打包、不预先统计数量/容量、不删除新机文件；同路径文件按 rsync 正常更新。旧机缺少的可选目录显示跳过，SSH 错误会停止。范围包含原直传清单中的家庭资料、LexiFlow/Session Browser 源码、Env Vault、oMLX 模型及可选 LiteLLM OAuth token。需查看准确路径时运行 `./workbench new-mac copy-data --help`。人工检查：所需项目/资料可打开，模型能被原生应用发现。

## 业务停写与备份

**只在新机基础安装完成、已安排停写窗口后执行。** 先在旧机 UI 暂停新派发、确认所有 active runs 为零。此阶段会停止旧机 Multica daemon，原生入口继续检查活动任务，并短暂停 Web/API 写入。OpenClaw 备份恢复其原 Gateway 启动状态，最终切换前还须显式停止旧机 Gateway。

旧机执行一次：

```bash
./workbench new-mac backup
```

复用 Multica/OpenClaw 原生一致性备份，并导出 LiteLLM PostgreSQL dump。原生备份保持各自批次；只生成一个小的私有路径回执，不复制成新的整机大包。任一组件失败即停止，不发布新的完成回执。人工检查：三项备份都成功，继续保持暂停派发。

新机执行一次：

```bash
./workbench new-mac receive-backup 旧机账号@旧机IP
```

脚本从私有回执取得准确批次，直传至 `~/feipi-restore/{litellm,openclaw,multica}`，无需手填三个备份路径。已存在目标会停止，避免混合批次。

## 分别恢复业务

每个组件一条命令，完成并人工检查后再做下一项：

```bash
./workbench new-mac restore litellm
```

只向空业务库原生恢复，已有运行代理或业务表即拒绝。完成后用原客户端发一次真实请求，核对原有访问密钥。

```bash
./workbench new-mac restore openclaw
```

校验/恢复原生状态、安装固定版程序和依赖、发布受管配置与技能。检查原有记忆和会话；不启动 Gateway、不向渠道投递。

```bash
./workbench new-mac restore multica
```

校验同批备份、准备固定程序/本机小配置、拉取固定镜像、仅向空库导入数据库和附件，并恢复防重记录。检查 Web 中的项目/Issue，下载一个历史附件核对；daemon 尚未启动。数据库恢复中途失败时保留现场，交给 Codex 定位；不能盲目重跑或清库。

## 一次完成授权与权限

账号与系统权限由本人操作；每次只处理当前提示。包括 FlClash 登录同步，Codex/Qoder 等原生登录，Figma MCP 授权，Karabiner/Rectangle 权限，以及 oMLX 的登录启动和服务自动启动。密码、验证码与令牌不发进聊天。

Multica 登录、准确工作区访问合并为：

```bash
./workbench new-mac login-multica
```

确认旧机不再派发、新机项目目录已直传后，准备本机 daemon 身份并展示差异：

```bash
./workbench new-mac bind-multica
```

人工审阅输出 plan 的受管对象/路径和 `plan_id`；然后只传该次摘要：

```bash
./workbench new-mac apply-multica 已审阅的plan_id
```

本阶段复用原生摘要校验、apply、verify、doctor，不自动接受新的计划。最后执行一个真实小任务并下载产物。若绑定阶段中断，Codex 使用原有 install/start/rebind 入口按实际状态恢复，不反复安装已加载的 LaunchAgent。

OpenClaw 渠道最终切换仍由 Codex 按实机状态引导：先停止旧机 Gateway，再显式启用新机，核对渠道授权与真实使用。它不由基础安装顺带启动。

## 准备完成后验收

业务数据恢复、登录和系统权限完成后：

```bash
./workbench new-mac startup
```

该入口要求 LiteLLM 真正 readiness 通过，再安装/检查/加载受管自启；只看到容器存在不算通过。oMLX 的两个原生自启开关仍由本人设置。

```bash
./workbench new-mac verify
```

合并基础 doctor、配置检查、应用/模型检查、四个 CLI 和 OpenClaw 的隔离文件任务。每个原生任务必须成功退出且产物匹配；OpenClaw 日志仅保存在本机私有目录，不启动 Gateway。Multica 的业务任务、图表渲染、Office 编辑和渠道授权继续由 Codex 按实际组件检查，不能凭此命令代替整机完成证明。

人工完整关机、开机并登录，再执行同一条 `verify`，同时检查业务和自启。脚本不会自动重启电脑。

入口是固定仓库代码：`workbench` 分发、`scripts/bootstrap/new-mac.sh` 负责无 Python 的前置、`scripts/workbench/new_mac.py` 组合现有组件命令。没有下载后生成的临时执行脚本；私有配置、备份回执和验证产物保存在仓库外。详细证据与限制见[交付验收](new-mac-delivery.md)。
