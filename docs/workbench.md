# 工作台使用与恢复

从 feipi-agent-kit 根目录运行命令。`./workbench` 只显示入口；`doctor / plan / diff` 不安装或启动服务。`./develop` 定位组件、运行测试或显式执行源码。没有自动同步、自动提交、自动升级或新的发布服务。

## 日常顺序

1. `./workbench doctor`：看缺项、来源、漂移和运行状态；`./workbench private check` 检查恢复所需资料。
2. `./workbench plan mac`：列出受管路径。将 `mac` 换成其他组件。
3. `./workbench diff mac`：比较仓库与运行环境。原文差异可能包含秘密，只写 `~/.local/state/feipi-workbench/diff/`，权限 0600。
4. 保留本机调优：`./workbench capture mac --select zsh/.zshrc`，可重复 `--select`；只回收所选文件，不提交 Git。恢复仓库声明：`./workbench apply mac`。
5. 按下表让配置生效，执行真实任务；有差异不等于出错，先判断哪边应保留。

| 组件 | 公开来源 → 日常目标 | 应用后的生效方式 |
| --- | --- | --- |
| Mac | `components/mac` → `~/.local/share/feipi-workbench/mac`；HOME 链接指向此副本，桌面配置实拷 | 新开 Zsh；重开 Neovim；iTerm2 加载 Dynamic Profile；Karabiner 自动读取 |
| Skills | `skills/` → 已安装客户端的用户 skills 目录，排除 tests/evals | 新对话重新发现；不卸载第三方技能 |
| 服务 | `tools/` → `~/.local/share/feipi-workbench/services/tools` | `./workbench service litellm restart` 重建代理容器，保留数据库；其他服务按需启动 |
| Multica | `components/multica` → `~/.local/share/multica/ops` | 排空任务后 apply；隔离配置生成、服务端字段 plan/apply、daemon 重启分别显式执行 |
| OpenClaw | `components/openclaw` → `~/.openclaw` 中清单指定的 7 个运行文件及 env 链接 | `./workbench service openclaw restart --force`；不覆盖会话、记忆或登录态 |
| OpenClash | `components/openclash/OIX-Region-Priority.conf` → 路由器覆写模块 | 原生合并及当前核心 `-t` 通过才应用；变化时重启并恢复选择；相同内容直接接管，避免中断网络 |

Mac 不自动覆盖现有真实目录（例如 `~/bin`），必须先合并或备份挪开；已有符号链接会在备份后换到运行副本。iTerm2 配置是名为 Dotfiles 的可选 Profile，不强制修改原默认 Profile。

## 安装与补缺

```bash
./workbench install mac       # 复用 Brewfile 和 bootstrap：brew/node/rust/ohmyzsh
./workbench install mac --apps # 新机同时安装终端、AI 客户端、浏览器、文档与 Java 应用
./workbench apply mac
./workbench install skills    # 等同 apply skills
./workbench install services  # 检查 Podman/Compose，安装定义，不启动所有服务
./workbench service litellm up
./workbench install openclaw  # 复用版本锁定的原部署器；先恢复所需 env
./workbench install multica   # 已绑定机器发布运行副本；缺身份时给出原部署手册
```

Mac 的 Podman VM 与桌面初始化是独立、有状态操作，按 `components/mac/docs/setup.md` 执行对应 bootstrap 阶段；安装软件不等于 VM 或服务已经启动。Multica 新机需按 `components/multica/docs/mac-mini-migration.md` 安装锁定版本、恢复同批数据、重新登录并注册本机 runtime；不克隆另一台仍在使用的设备身份。OpenClash 的安装与私有 SSH/API 配置见其 README。

`make install` 保留为兼容实拷安装命令；推荐有回退批次的 `workbench apply skills`。`make *-up/restart` 已转到运行副本，首次先 `apply services`。组件内部脚本是底层能力，不再作为日常源码挂载入口。

## 单个 Skill 发布

只更新一个客户端中的一个 skill，保留其他已安装入口及未发布源码：

```bash
./workbench apply skills --agent codex --skill feipi-health-maintain-family-records
./workbench apply skills --agent openclaw --skill feipi-health-maintain-family-records
```

仍先验证完整注册表，再备份被选 skill 和直接共享依赖，随后实拷；不清理其他已退役入口。底层安装器也支持 `--skill <name>`，日常更新优先使用带备份的工作台。省略筛选参数时保持原有安装范围。

## 两个方向的具体场景

Zsh 调好了别名：`diff mac` → 打开私有差异文件 → `capture mac --select zsh/.zsh_config/20-aliases.zsh` → 检查 Git diff → `develop mac test` → `apply mac`。回收只支持已列出的文件；新增配置文件先明确加入源码受管范围。

OpenClaw 调好配置：`diff openclaw` → `capture openclaw --select openclaw.json` → schema 检查 → `apply openclaw` → 重启 Gateway、实际对话。回收拒绝常见明文凭据，但扫描不能代替人工审查；用 env/SecretRef 保存秘密。workspace 只管理 manifest 中的人格模板，记忆与会话永不回收公开 Git。

Multica 网页调好 Agent：`./workbench multica plan` 看服务端差异；`./workbench multica capture --agent codex-builder --field model` 先预览，追加 `--write` 才回收。允许的字段见 `--help`。共享协作指令单独治理，不把整个远端 Agent JSON 收回仓库。仓库往服务端：排空任务 → `apply multica` → `workbench multica plan` → `workbench multica apply --plan-id <审阅的摘要>` → `workbench multica verify`。启动脚本变化时先 `service multica stop`，发布后再 start；当前默认只绑定 Codex，启用可选 OpenClaw 执行器才需生成并校验其隔离配置。diff/doctor 同时比较运行代码和配置，capture 白名单仅限配置，较新的运行代码需审阅合并。

路由器调好地区优先模块：`diff openclash` 会先 SSH 读取当前模块；`capture openclash --select OIX-Region-Priority.conf` 明确收回；原订阅、代理认证和 UCI 只进私有备份。应用后执行 `./workbench service openclash verify`，同时核对 HTTP 响应和核心连接路径。

研发时 `./develop <组件> test`、`./develop <组件> run -- <命令>`。它们不会自动发布；显式命令本身若会改环境仍有副作用。只有 Skills 提供 `./develop skills link`，结束后 `./workbench apply skills` 恢复实拷。不要直接编辑运行副本而忘记 capture。

技能安装会排除根目录的 `tests/`、`evals/` 和 `node_modules/`，并在内容、权限与链接均未变化时跳过复制。Git 只保存 npm 包清单和锁文件；本地依赖由技能在使用时按锁文件准备。Mermaid 和 PPT 复用系统 Node，以各自本机共享缓存保存固定 npm 依赖；Mermaid 另外复用已安装 Chrome，多个客户端不重复复制或安装；日常执行不运行 `npm update`。新机首次使用需准备依赖，缓存可重建，运行资料与私有数据仍按以下边界保留。

## 私有范围与备份

| 资料 | 位置与要求 |
| --- | --- |
| 密钥 | `~/.env` 指向现有 env vault；本机私有配置权限 0600；不写入公开 Git |
| 可选应用覆盖 | Qwen settings.json 原位私有；Crawl4AI 旧忽略的 env.local 收纳至 `~/.config/feipi-workbench/private/services/crawl4ai.env`，日常 wrapper 显式使用，源码发布不删除 |
| OpenClaw 原资料 | `~/.openclaw/workspace`（含 memory）、`agents`、`state`、渠道 credentials、微信状态、浏览器状态；前 3 项是本次连续使用的必需资料；后几项按启用功能需要 |
| Multica | 数据库容器卷 + 上传附件 + `~/.config/multica-selfhost/server.env` 必须同批；machine.json、任务回执另保留；新机重新认证/注册 |
| OpenClash | 本机 `~/.config/feipi-workbench/router.json`、`private/openclash` 与路由器 UCI/订阅；最小备份仍含秘密，不能 Git |
| 可重建内容 | node_modules、镜像、OpenClash core/GeoIP/规则提供器下载缓存；恢复匹配版本后重建，不当作用户资料 |

```bash
./workbench private backup openclaw
./workbench private backup multica
./workbench private backup openclash

# 迁机基础配置：旧机导出；将整个私有目录复制到新机后校验并恢复。
# 导出目录必须在仓库外且尚不存在；包内含秘密，不上传公开网盘或 Git。
# 若有 Codex 模型目录，旧机导出使用 Python 3.11+ 和清单锁定版 Codex；
# 新机先完成 install mac --agents，再 restore-mac，以原生程序重建目录。
./workbench private export-mac "$HOME/feipi-mac-private"
./workbench private verify-mac "$HOME/feipi-mac-private"
./workbench private restore-mac "$HOME/feipi-mac-private"
# 例如核对已复制到新机的 OpenClaw 独立备份：
./workbench private verify openclaw "$HOME/feipi-restore/openclaw"
```

### 本地目录由用户直接传输

新机从 Git 获取本仓库，软件和依赖走安装脚本。个人项目、资料和已有模型目录由用户复制，不先生成整机大包，也不把资料目录容量作为初始化验收条件。
集中导出、传输、安装、恢复和授权命令见[新 Mac 准备清单](new-mac-prepare.md)。`private check` 只看必要路径、目录是否为空和 env 定义，不递归统计资料文件。

MacBook 没有网口时，可用雷雳线连接两机的雷雳端口，通过「系统设置 → 网络 → 雷雳网桥」取得 IPv4；普通 Type-C 充电线不能直接替代雷雳网桥。也可让两机连接同一 Wi-Fi。旧机「系统设置 → 通用 → 共享」开启「远程登录」，只允许自己的账号；新机使用所选网络接口的旧机 IP。参考 [Apple 雷雳连接说明](https://support.apple.com/zh-hk/guide/mac-help/mchld53dd2f5/26/mac/26)及[远程登录说明](https://support.apple.com/guide/mac-help/allow-a-remote-computer-to-access-your-mac-mchlp1066/mac)。

以下由用户在新机执行一次，替换旧机账号和 IP。固定目录范围用同一入口的 `--help` 查看；只直接同步目录，不删除新机文件，不先盘点数量/容量。任一传输失败即停止。Agent 不自行运行资料传输。

```bash
./workbench new-mac copy-data 旧机账号@旧机IP
```

这是用户执行的传输模板，尚未在两台实体 Mac 之间验收。Documents 访问受系统隐私权限限制时，需在旧机远程登录设置中允许远程用户访问相应资料。OpenClaw SQLite、Multica/PostgreSQL 等运行中数据不按上述普通目录热复制：用户先按对应组件命令停写并做原生一致性导出，再传输输出目录，由恢复脚本处理。

### 可选的旧全量备份入口

以下能力保留供显式全量备份使用，**不是新机初始化的必需步骤**，后续不再以该包大小或普通资料归档数量衡量初始化交付。

```bash

# 旧机集中准备：先暂停 Multica 新派发，在 FlClash 官方界面导出本地 ZIP。
# 用实际保存的 ZIP 路径替换参数；命令会短暂停写并恢复原业务启动状态。
./workbench private prepare-migration "$HOME/feipi-new-mac-transfer" \
  --proxy-backup "$HOME/FlClash-backup.zip"
./workbench private verify-migration "$HOME/feipi-new-mac-transfer"

# 将整个私有批次复制到新机后，先恢复代码和资料到空目录。
# 已存在的任一目标会在写入前报错；可重复 --only 选择尚未恢复的来源。
./workbench private restore-sources "$HOME/feipi-new-mac-transfer"
# 基础配置另行恢复，数据库仍按对应组件手册恢复，最后再启动业务。
./workbench private restore-mac "$HOME/feipi-new-mac-transfer/mac-private"

# 状态恢复拒绝覆盖已有目录，且不启动服务。OpenClaw 程序须先按 versions.json
# 安装到已激活的 Node 环境，尚不要创建 Gateway 或启动渠道。
./workbench private restore-state omlx "$HOME/feipi-new-mac-transfer"
./workbench private restore-state openclaw "$HOME/feipi-new-mac-transfer"
# 恢复后重建未归档的程序依赖；这一步不启动 Gateway。
bash components/openclaw/scripts/deploy.sh --dependencies-only --yes
```

OpenClaw 当前原生备份拒绝 `.env` 的绝对符号链接，因此使用标准 tar：停 Gateway → SQLite integrity_check 与 WAL checkpoint → 归档原状态（不跟随链接）和实际 env 文件 → 校验 → 恢复原启动状态。停写后使用 SQLite 原生读写连接，允许初始化已删除的 WAL 辅助文件；仍有锁定或数据库损坏即失败。不热复制 SQLite，不归档整个 HOME。Multica 复用原停写 pg_dump + 附件 + 服务密钥流程；单独备份前还须 `service multica stop`，完成后 `start`；集中准备入口自动处理已加载的受管 LaunchAgent。`verify multica` 在无网络临时 PostgreSQL 中恢复验证；`verify openclaw` 是摘要验证，SQLite 恢复演练应在新目录解包后运行，不能将校验和通过称作完整功能恢复。

`export-mac` 只包含固定白名单的基础配置。对于 Codex 配置实际引用的模型目录，只保存模型名称、程序版本和元数据摘要；新机使用锁定版 `codex debug models --bundled` 精确重建，不传完整派生 JSON，也不带未引用的旧目录。若是自定义元数据或原生内容不匹配，导出或恢复会在写入前失败，并提示单独复制，不用近似默认值代替。旧格式配置包仍可恢复。

导出解引用 `.env` 后保存真源，恢复时重建指向本机 vault 的相对链接。恢复先校验全部摘要和可重建内容，再备份已有目标和原子写入；不复制设备身份、认证、运行中数据库或模型权重。HOME 变化时仅调整配置中以旧 HOME 开头的路径；密钥有效性、SSH 授权、服务数据和模型仍须分别验收。完整新机交付进展见 [验收清单](new-mac-delivery.md)。

`prepare-migration` 在基础配置外集中保存 Multica、OpenClaw 和 LiteLLM 的原生一致性备份、FlClash 官方备份、三个当前使用的 oMLX 模型，以及机器绑定引用的 Git 项目和 env vault 历史。Git 项目保留全部 refs、stash、暂存/未暂存补丁、未跟踪文件及固定私有覆写项；成长日记和装修项目还保留忽略的资料原件，家庭健康和房地产等非 Git 资料单独归档，跳过声明的构建缓存。它不复制 Multica 登录/设备身份、Podman VM 或容器镜像；新设备账号登录、节点同步、系统权限和切换前旧机停主力仍是集中准备中的独立事项。失败批次含 `INCOMPLETE`，不能用于恢复。`restore-sources` 只恢复代码和资料，不启动业务；已有工作台源码目录也会触发保全检查，可用 `--only 'Documents/…'` 选择其余来源。

`restore-state` 先校验完整业务包，在新建临时目录中解包和检查，成功后发布整个状态目录。OpenClaw 恢复会话、记忆和数据库，重新检查所有已记录 SQLite；配置中的 HOME 路径和 env 链接跟随新机，原生插件技能链接指向新机同版本 npm 程序目录。无法识别的外部链接直接失败，不带着旧机路径继续启动。oMLX 恢复当前三个模型并检查配置与权重；随后仍须做真实推理。目标已存在时保持原样；该入口不替代同批 PostgreSQL 恢复、新设备授权或旧机切换。

新机默认使用独立 OpenClaw 停写备份：`./workbench private restore-state openclaw "$HOME/feipi-restore/openclaw"`。它只要求 `backup openclaw` 的四个原生文件及摘要，先校验后检查 SQLite、调整 HOME 和程序链接，不依赖全量迁移清单、资料或模型包。须先恢复基础 env 并安装锁定版 OpenClaw；已有 `.openclaw` 保持原样，Gateway 不启动。

Multica 小配置入口为 `./workbench private restore-state multica "$HOME/feipi-restore/multica"`。先恢复基础 env、安装固定 CLI/Compose 和运行包装入口；命令校验同批五个控制文件、版本和原密钥，生成本机 machine/server.env/匿名 Docker 配置。它保留业务 UUID，更新 HOME、仓库和程序路径，清空旧 daemon/runtime ID；已有目标拒绝覆盖。不读取数据库、附件或项目目录，不登录或启动服务；数据、防重记录和新设备注册按[组件切换手册](../components/multica/docs/mac-mini-migration.md)完成。

备份目录：`~/.local/state/feipi-workbench/{backups,changes,openclaw-backups,openclash-backups}` 与 `~/.local/state/multica/backups`。不自动清理，避免删除最后可用副本。长期保留最近可恢复批次并加密复制到用户选定的外部介质；本次未配置自动外传。

## 失败后如何继续

配置应用会先打印 `./workbench restore <批次>`；当前组件文件写入失败会尝试恢复。restore 只恢复该批受管文件，不恢复数据库，也不自动重启服务。需要回到切换前来源时用首次应用批次，后续批次恢复的是上一次运行副本。

- Mac/Skills：restore 后新开终端/对话；确认原链接目标仍存在，再运行真实用例。
- LiteLLM：restore services 批次后 `service litellm restart`，等待 readiness，再请求模型。慢启动先查日志，不能盲目 recreate 数据库。
- Multica：排空任务、停 daemon；恢复配置批次或按原同批数据库手册恢复；重新 plan/verify、启动、完成新任务并下载附件。`recover ISSUE` 先核对远端，pending 回执不能盲目重派；确认失败且无活动 run 后才新建一次续接意图。
- OpenClaw：先停 Gateway，解压备份到新目录；对所有 SQLite 执行 `PRAGMA integrity_check`；恢复匹配版本依赖、所需目录及 env 原链接目标后启动，核对旧记忆和新对话。不在线覆盖 SQLite/WAL/SHM。
- OpenClash：apply 失败恢复旧模块、重启并恢复选择；本机完整回退所需的最小配置见组件 README。只有核心 API 和真实网络都通过才确认恢复。

首次工作区备份包含原未提交工作，原独立仓库仍保留，不删除。`.mcp.json` 和 `.claude/settings.local.json` 不由工作台修改。`doctor` 证明配置/来源/服务层状态；真实使用和验证限制记录在 `workbench-validation.md`。
