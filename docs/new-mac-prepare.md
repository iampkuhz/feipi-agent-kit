# 新 Mac 集中准备与执行清单

Git 提供配置、清单和脚本；软件、依赖、镜像及派生文件在新机重建。私有配置使用约 23 KiB 的配置包。项目、资料、模型和必要原生备份由用户执行下面的传输命令，不要求生成整机大包，也不盘点资料容量。

本清单把人工输入集中列出；登录、系统权限和最终业务切换仍需本人完成。已实测范围与未完成项目见[交付验收](new-mac-delivery.md)，不能将这些命令的语法检查称为两台实体 Mac 的端到端证明。

## 旧机准备

在本仓库根目录执行，基础配置导出目录必须尚不存在。源码归档只包含当前提交的 Git 跟踪内容，供新机尚无 Git 时运行前置安装；不包含工作区未提交改动。

```bash
bash <<'EXPORT_CONFIG'
set -euo pipefail
./workbench private export-mac "$HOME/feipi-mac-private"
./workbench private verify-mac "$HOME/feipi-mac-private"
git archive --format=tar.gz --output "$HOME/feipi-bootstrap.tar.gz" HEAD
EXPORT_CONFIG
```

业务备份在最终切换维护窗口执行：先暂停 UI/聊天新派发，等活动任务归零，再执行下列命令。Multica 备份会短暂停 Web/API 写入并恢复 Web/API；daemon 保持停止。OpenClaw 备份会恢复原 Gateway 启动状态，最终切换前仍须停旧机 Gateway。记录两个命令打印的批次路径，填写下一节变量。

```bash
bash <<'BACKUP'
set -euo pipefail
umask 077
./workbench service multica stop
./workbench private backup multica
./workbench private backup openclaw

# LiteLLM 使用 PostgreSQL 原生一致性导出，不复制在线数据库目录。
./workbench service podman check
batch="$(mktemp -d "$HOME/feipi-litellm-backup.XXXXXX")"
podman exec litellm-db-podman pg_dump -Fc -U litellm litellm > "$batch/database.dump.partial"
podman exec -i litellm-db-podman pg_restore --list < "$batch/database.dump.partial" > /dev/null
mv "$batch/database.dump.partial" "$batch/database.dump"
podman inspect litellm-db-podman --format '{{.ImageName}}' > "$batch/database-image.txt"
printf 'LiteLLM 备份：%s\n' "$batch"
BACKUP
```

在 FlClash 官方界面导出本地备份到 `~/FlClash-backup.zip`，新机导入后完成账号登录和节点同步。授权和订阅不进入 Git。

## 有线连接与传输

用网线连接两台 Mac；旧机开启「系统设置 → 通用 → 共享 → 远程登录」，只允许自己的账号。查看旧机有线 IP，在新机填写以下变量；备份路径使用上一节打印的实际值。

```bash
export OLD_MAC='旧机账号@旧机有线IP'
export OPENCLAW_BATCH='/Users/旧机账号/.local/state/feipi-workbench/openclaw-backups/实际批次'
export MULTICA_BATCH='/Users/旧机账号/.local/state/multica/backups/实际批次'
export LITELLM_BATCH='/Users/旧机账号/feipi-litellm-backup.实际后缀'
```

以下由用户在新机执行，不删除新机已有文件；普通项目、资料和模型目录的直传清单见[本地目录命令](workbench.md#本地目录由用户直接传输)。启用 LiteLLM 的 ChatGPT OAuth 上游时还需传输其 token 目录；使用自定义 `AGENT_SERVICE_DATA_DIR` 时替换示例中的数据根路径。

```bash
bash <<'COPY'
set -euo pipefail
umask 077
ssh -n "$OLD_MAC" 'id -un'
mkdir -p "$HOME/feipi-restore" "$HOME/feipi-restore/openclaw" \
  "$HOME/feipi-restore/multica" "$HOME/feipi-restore/litellm"
scp "$OLD_MAC:feipi-bootstrap.tar.gz" "$HOME/"
scp -pr "$OLD_MAC:feipi-mac-private" "$HOME/"
scp -p "$OLD_MAC:FlClash-backup.zip" "$HOME/"
rsync -a -e ssh "$OLD_MAC:$OPENCLAW_BATCH/" "$HOME/feipi-restore/openclaw/"
rsync -a -e ssh "$OLD_MAC:$MULTICA_BATCH/" "$HOME/feipi-restore/multica/"
rsync -a -e ssh "$OLD_MAC:$LITELLM_BATCH/" "$HOME/feipi-restore/litellm/"
COPY

# 仅启用该上游时执行；目录内容由用户直接传，不重新打包。
mkdir -p "$HOME/Documents/service-data/litellm/chatgpt-tokens"
rsync -a -e ssh "$OLD_MAC:Documents/service-data/litellm/chatgpt-tokens/" \
  "$HOME/Documents/service-data/litellm/chatgpt-tokens/"
```

新机下载暂时需要旧机代理时，在独立终端保留下列 SSH 会话；主终端设置对应代理后安装。17890 是临时转发端口，不替代新机 FlClash 的实际登录和同步。

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:17890:127.0.0.1:7890 "$OLD_MAC"
# 主终端：
export http_proxy=http://127.0.0.1:17890 https_proxy=http://127.0.0.1:17890
export NO_PROXY=localhost,127.0.0.1,::1
```

## 新机安装与配置恢复

普通用户在新机执行，首次 `sudo -v` 由本人授权。临时源码只用于准备 CLT/Homebrew/Git/Python；长期来源重新从 Git 克隆。若长期目录已存在，先核对其来源，不覆盖或重新套一层 clone。

```bash
bash <<'INSTALL'
set -euo pipefail
bootstrap_source="$(mktemp -d "${TMPDIR:-/tmp}/feipi-bootstrap.XXXXXX")"
tar -xzf "$HOME/feipi-bootstrap.tar.gz" -C "$bootstrap_source"
sudo -v
bash "$bootstrap_source/scripts/bootstrap/prerequisites.sh" install
source "$bootstrap_source/components/mac/bootstrap/environment.sh"
mkdir -p "$HOME/Documents/tools/llm"
git clone --depth 1 https://github.com/iampkuhz/feipi-agent-kit.git "$HOME/Documents/tools/llm/feipi-agent-kit"
cd "$HOME/Documents/tools/llm/feipi-agent-kit"
./workbench install mac --apps --agents
# 安装发生在子进程；刷新当前 Bash，才能找到本轮新建的 nvm default 和 Codex。
source components/mac/bootstrap/environment.sh
./workbench apply mac
./workbench private verify-mac "$HOME/feipi-mac-private"
./workbench private restore-mac "$HOME/feipi-mac-private"
rm -rf "$bootstrap_source"
INSTALL
```

应用安装完成后，先在 FlClash 导入 ZIP、登录并同步节点，确认本机 7890 已可用，再关闭临时 SSH 转发。恢复的 env 指向本机代理，不能继续把尚未启动的 7890 当作可用网络。随后新开终端，进入长期仓库，先完成普通目录直传，再恢复 OpenClaw。这里只安装锁定程序和依赖、发布配置，不启动渠道，不发送消息。

```bash
bash <<'RESTORE_CONFIG'
set -euo pipefail
source components/mac/bootstrap/environment.sh
openclaw_version="$(python3 -c 'import json; print(json.load(open("components/openclaw/versions.json"))["openclaw"])')"
npm install --global "openclaw@$openclaw_version"
./workbench private restore-state openclaw "$HOME/feipi-restore/openclaw"
bash components/openclaw/scripts/deploy.sh --dependencies-only --yes
# OpenClaw 晚于基础终端安装；复用原入口生成补全，不升级已有主题或插件。
bash components/mac/bootstrap/ohmyzsh.sh install
./workbench apply openclaw
./workbench apply skills
./workbench apply services
# 只准备固定程序、单个官方 Compose 和本地包装入口；账号/数据/设备绑定随后处理。
python3 components/multica/scripts/install-native.py install
python3 components/multica/scripts/install-runtime.py
bash components/mac/bootstrap/neovim.sh
RESTORE_CONFIG
```

OpenClaw 独立备份恢复会核对固定文件摘要、原 HOME 和 SQLite，拒绝覆盖已有状态；不需要项目或模型归档。旧格式缺少原 HOME 元数据时，用当前旧机入口重新导出。Multica 数据库、附件和服务密钥恢复及新设备注册，执行[Mac mini 切换步骤](../components/multica/docs/mac-mini-migration.md)，禁止克隆旧 daemon 身份。LiteLLM 先仅启动新机空 PostgreSQL，恢复同批 `database.dump` 和原密钥，再启动代理；详见[服务恢复](setup-new-mac.md)。这两项尚待实体新机冷启动验收，不跳过数据恢复而直接启动空业务。

## 一次完成授权与权限

| 项目 | 本人操作或命令 | 完成后的实际验证 |
| --- | --- | --- |
| FlClash | 导入 ZIP，登录、同步并选择节点，确认本机 7890 可用 | 关闭临时 SSH 转发后重跑下载和真实 CLI 请求 |
| Codex | `codex login`；`codex login status` | 下方 Agent 文件任务 |
| Figma MCP | `codex mcp login figma`；服务名以本机配置为准 | 新机真实读取有权限的设计资源，未授权不计通过 |
| Qoder | 启动 `qodercli`，执行 `/login` | 下方 Agent 文件任务 |
| Qwen / Claude | 保留恢复的 API/模型设置；启用账号模式时在原生客户端登录，Claude 可用 `claude auth login` | 下方 Agent 文件任务；不为通过测试擅自换模型或 provider |
| Multica | 新机 personal 登录、选择恢复的 workspace、注册新 daemon 并精确 rebind | 组件手册中的真实小任务、附件与重复应用检查 |
| SSH / Git | 使用本人选择的 SSH 私钥，或新建密钥并添加到服务端授权；不覆盖已有密钥 | `ssh -T git@github.com` 或实际 Git 拉取 |
| oMLX 原生应用 | 首次打开后执行 `omlx start --timeout 120`；在 `Settings → Server` 开启 `Automatically start server on launch`；Dock 右键 `Options → Open at Login` 核实勾号；菜单栏显示提示走系统设置 | 确认模型请求；完整关机开机并登录后直接复验，不先手动 start |
| 键盘与客户端 | Karabiner 的系统扩展/输入监控，Rectangle 辅助功能，iTerm2 Profile，以及需要的客户端登录 | 实际按键、窗口操作、终端和应用打开 |

## 准备完成后验收

```bash
bash <<'VERIFY_MAC'
# 子 Bash 失败即停止，不改动当前交互终端的选项；本人 env 沿用原生 Shell 求值。
set -eo pipefail
source components/mac/bootstrap/environment.sh
./workbench doctor mac
./develop mac run -- bash bootstrap/check.sh
python3 components/mac/bootstrap/verify-apps.py
python3 components/mac/bootstrap/verify-extras.py
# 仅加载本人已审核的本地 env，不输出密钥。
set -a; source "$HOME/.env"; set +a
./develop mac run -- bash bootstrap/verify-agents.sh
VERIFY_MAC
```

服务就绪、原生备份恢复、新设备绑定通过后，按[自启步骤](setup-new-mac.md#登录自启与-env-vault)安装自启；完整关机开机并登录后再次执行必要真实任务。旧机停止主力后才启新机 OpenClaw/Multica，避免双主。任何失败保留日志，按组件恢复批次处理；整机验收通过前不宣称部署完成。
