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
./workbench apply mac
./workbench install skills    # 等同 apply skills
./workbench install services  # 检查 Podman/Compose，安装定义，不启动所有服务
./workbench service litellm up
./workbench install openclaw  # 复用版本锁定的原部署器；先恢复所需 env
./workbench install multica   # 已绑定机器发布运行副本；缺身份时给出原部署手册
```

Mac 的 Podman VM 与桌面初始化是独立、有状态操作，按 `components/mac/docs/setup.md` 执行对应 bootstrap 阶段；安装软件不等于 VM 或服务已经启动。Multica 新机需按 `components/multica/docs/mac-mini-migration.md` 安装锁定版本、恢复同批数据、重新登录并注册本机 runtime；不克隆另一台仍在使用的设备身份。OpenClash 的安装与私有 SSH/API 配置见其 README。

`make install` 保留为兼容实拷安装命令；推荐有回退批次的 `workbench apply skills`。`make *-up/restart` 已转到运行副本，首次先 `apply services`。组件内部脚本是底层能力，不再作为日常源码挂载入口。

## 两个方向的具体场景

Zsh 调好了别名：`diff mac` → 打开私有差异文件 → `capture mac --select zsh/.zsh_config/20-aliases.zsh` → 检查 Git diff → `develop mac test` → `apply mac`。回收只支持已列出的文件；新增配置文件先明确加入源码受管范围。

OpenClaw 调好配置：`diff openclaw` → `capture openclaw --select openclaw.json` → schema 检查 → `apply openclaw` → 重启 Gateway、实际对话。回收拒绝常见明文凭据，但扫描不能代替人工审查；用 env/SecretRef 保存秘密。workspace 只管理 manifest 中的人格模板，记忆与会话永不回收公开 Git。

Multica 网页调好 Agent：`./workbench multica plan` 看服务端差异；`./workbench multica capture --agent litellm-coder --field model` 先预览，追加 `--write` 才回收。允许的字段见 `--help`。共享协作指令单独治理，不把整个远端 Agent JSON 收回仓库。仓库往服务端：排空任务 → `apply multica` → `develop multica run -- python3 scripts/configure-openclaw.py` → `multica-openclaw config validate` → `workbench multica plan` → `workbench multica apply --plan-id <审阅的摘要>` → `workbench multica verify`。有启动脚本变化再 `service multica stop/start`。

路由器调好地区优先模块：`diff openclash` 会先 SSH 读取当前模块；`capture openclash --select OIX-Region-Priority.conf` 明确收回；原订阅、代理认证和 UCI 只进私有备份。应用后执行 `./workbench service openclash verify`，同时核对 HTTP 响应和核心连接路径。

研发时 `./develop <组件> test`、`./develop <组件> run -- <命令>`。它们不会自动发布；显式命令本身若会改环境仍有副作用。只有 Skills 提供 `./develop skills link`，结束后 `./workbench apply skills` 恢复实拷。不要直接编辑运行副本而忘记 capture。

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
./workbench private verify <组件> <输出的私有批次>
```

OpenClaw 当前原生备份拒绝 `.env` 的绝对符号链接，因此使用标准 tar：停 Gateway → SQLite integrity_check → 归档原状态（不跟随链接）和实际 env 文件 → 校验 → 恢复原启动状态。不热复制 SQLite，不归档整个 HOME。Multica 复用原停写 pg_dump + 附件 + 服务密钥流程；备份前还须 `service multica stop`，完成后 `start`。`verify multica` 在无网络临时 PostgreSQL 中恢复验证；`verify openclaw` 是摘要验证，SQLite 恢复演练应在新目录解包后运行，不能将校验和通过称作完整功能恢复。

备份目录：`~/.local/state/feipi-workbench/{backups,changes,openclaw-backups,openclash-backups}` 与 `~/.local/state/multica/backups`。不自动清理，避免删除最后可用副本。长期保留最近可恢复批次并加密复制到用户选定的外部介质；本次未配置自动外传。

## 失败后如何继续

配置应用会先打印 `./workbench restore <批次>`；当前组件文件写入失败会尝试恢复。restore 只恢复该批受管文件，不恢复数据库，也不自动重启服务。需要回到切换前来源时用首次应用批次，后续批次恢复的是上一次运行副本。

- Mac/Skills：restore 后新开终端/对话；确认原链接目标仍存在，再运行真实用例。
- LiteLLM：restore services 批次后 `service litellm restart`，等待 readiness，再请求模型。慢启动先查日志，不能盲目 recreate 数据库。
- Multica：排空任务、停 daemon；恢复配置批次或按原同批数据库手册恢复；重新 plan/verify、启动、完成新任务并下载附件。`recover ISSUE` 先核对远端，pending 回执不能盲目重派；确认失败且无活动 run 后才新建一次续接意图。
- OpenClaw：先停 Gateway，解压备份到新目录；对所有 SQLite 执行 `PRAGMA integrity_check`；恢复匹配版本依赖、所需目录及 env 原链接目标后启动，核对旧记忆和新对话。不在线覆盖 SQLite/WAL/SHM。
- OpenClash：apply 失败恢复旧模块、重启并恢复选择；本机完整回退所需的最小配置见组件 README。只有核心 API 和真实网络都通过才确认恢复。

首次工作区备份包含原未提交工作，原独立仓库仍保留，不删除。`.mcp.json` 和 `.claude/settings.local.json` 不由工作台修改。`doctor` 证明配置/来源/服务层状态；真实使用和验证限制记录在 `workbench-validation.md`。
