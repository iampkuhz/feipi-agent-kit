# Mac 迁移手册与准备状态

本手册只覆盖高优先级迁移。Dotfiles 负责机器依赖、Zsh/Neovim 和 HHKB/iTerm2；
业务代码、服务定义由各自仓库负责。Zed 不配置，其他桌面偏好暂不扩展。

只想安装机器环境，先读 [首次安装与依赖顺序](docs/setup.md)；日常检查和失败重试见
[维护速查](docs/maintenance.md)。下方日期对应历史迁移盘点，不等于本次机器已重新验收。

状态核对日期：2026-10-21。本轮补查基线为 Dotfiles `7e53c72`、Agent Kit `4317716`，
两者工作区均有未提交内容。配置是否已入库、是否已有备份、是否在新机验收是三个独立状态。
已有整机资料盘点和备份记录维护于 `~/Documents/Playground/mac-mini-migration`，本手册仅提供操作入口。

## 1. 哪些已经准备好，哪些还没完成

“具备条件”表示已有配置来源、执行入口和本机检查证据；实际换机后仍要验收。
“部分具备”表示主要文件已保存，但还有明确缺口；“待准备”表示尚未确认备份或恢复方法。

| 分类 | 当前状态 | 到时候怎样迁移 | 剩余事项 |
| --- | --- | --- | --- |
| Homebrew、ShellCheck、Node/npm、Rust、oh-my-zsh | 具备条件 | 克隆 Dotfiles，执行 `bootstrap/run.sh`，重新下载安装 | 新机网络下载、安装和命令验证；GUI 软件需先选择 |
| Zsh 配置 | 已入库，具备迁移条件 | 用初始化入口或 `bootstrap/macosinit.sh` 建立链接 | 15 个配置/脚本均受 Git 跟踪；当前两处本地修改另需提交或保留 |
| Neovim | 已入库，具备迁移条件 | 脚本链接配置，插件按锁文件重新下载 | 18 个配置/脚本及锁文件均受 Git 跟踪；Treesitter 分支差异与新机插件验收另列 |
| HHKB/Karabiner | 具备条件 | 重装应用，执行 `bootstrap/desktop.sh install` 复制 JSON | 新机授予系统权限，连接 HHKB 验证按键；换设备时核对设备编号 |
| iTerm2 与字体 | 具备条件 | 重装应用及字体，同一桌面脚本复制 Profile | 在应用里选择 `Dotfiles` 并按需设为默认，检查字体与按键 |
| 日常 AI 客户端与 CLI | 部分具备 | 单独重装实际使用的客户端、恢复必要配置并登录 | 初始化脚本没有安装这些客户端；可选 Qwen 配置已有说明，其余尚未逐项验收 |
| Agent Kit 的 Skills 与服务定义 | 由所属仓库提供重建入口 | 克隆 Agent Kit，按其手册安装 Skills、重建服务 | 其工作区也有未提交/未跟踪内容；密钥、业务数据及自启需独立验收 |
| 其他项目代码 | 部分具备，未逐仓验收 | 已推送的代码重新克隆；本机独有内容另行保存 | 核对未提交、未跟踪、忽略文件和仅本地存在的提交 |
| `~/.env`、SSH、Git 本机配置及账号 | 有本地文件/历史，异机恢复待验证 | 必要秘密单独保存；账号优先同步或重新登录 | Env Vault 是无远程的本地 Git，不能视为已有异机副本；钱包密钥等见私有盘点 |
| 个人文件与独有业务数据 | 已有部分备份，新增范围待补 | 沿用迁移工作台的归档；需要的数据库按所属项目恢复 | 已有资料快照不等于全 HOME 覆盖；Multica 有本机恢复测试记录，其他新增状态另核对 |

本次本机只读检查：`bootstrap/check.sh` 通过；链接和 Node 隔离测试通过。
`bootstrap/brew.sh check` 未全通过：缺少 Homebrew 管理的 `git`，但系统 `/usr/bin/git`
可用；另有 `libtiff/webp` 依赖元数据告警。这不等于新机安装失败，也未为通过检查改动旧机软件。
迁移工作台记录了 2026-10-19 的 30 个私有 Git 仓库、45 个工作区恢复验证和 21 批资料归档，
本轮已核对本地完成摘要，未再次连接 NAS 验证。它们是指定范围的历史快照，不是持续同步。

## 1.1 两台 Mac 都在手边：可以先用迁移助理

如果希望保留现有用户资料和应用状态，省事的路线是雷雳线连接两台 Mac，使用 Apple 的
[迁移助理](https://support.apple.com/en-us/102613)选择用户账户、应用和设置。
新机在初始设置时选择“从 Mac 传输”，旧机打开迁移助理选择“传输到另一台 Mac”，
核对配对码后选择范围并等待完成；也可以在新机完成初始设置后单独打开迁移助理。
Apple 说明使用 [Thunderbolt 或以太网线直接连接](https://support.apple.com/guide/macbook-air/migrate-your-data-apda75cd668e/2026/mac/26)
通常比无线传输快，需使用支持相应数据传输的线缆和端口。

迁移助理已经带过来的仓库不用再次克隆，直接进入目录检查配置来源和依赖。
第 3 节适用于选择从头安装或需要补齐的部分。迁移助理不会替代服务数据库的项目级恢复验收，
也不是此后两台 Mac 的持续同步工具。

Chrome 可以在两台电脑登录同一 Google 账号，恢复已保存到账号的书签、密码、扩展和设置；
历史记录与标签页按所选同步项处理。旧机本地数据要先确认已保存到账号，
详见 [Chrome 官方同步说明](https://support.google.com/chrome/answer/165139?co=GENIE.Platform%3DDesktop&hl=zh-Hans)。
连接线本身不会让新 Chrome 自动读取另一台的 Profile；网站登录状态仍可能要求重新认证。

Apple 说明，初始设置中的迁移会转移钥匙串；iCloud 钥匙串项目使用同一 Apple 账号同步。
因此不必把所有密码都手工导出成文件。确需手动搬迁钥匙串时按
[Apple 钥匙串迁移说明](https://support.apple.com/guide/keychain-access/copy-keychains-kyca1121/mac)处理。

## 2. 离开旧机前：保住无法重新下载的内容

### 2.1 整理代码与配置

对 Dotfiles、Agent Kit 及正在使用的长期业务主仓库分别运行以下只读命令。
沿迁移工作台既有范围，历史 worktree、临时检出不再补备份或列作迁移前置：

```bash
# 在每个仓库目录执行；同时查看跟踪文件修改和未跟踪文件。
git status --short
# 查看分支的上游和领先情况，识别尚未推送的本地提交。
git branch -vv
# 列出被忽略的文件；只人工筛选本机独有资料和私密配置。
git ls-files --others --ignored --exclude-standard
```

- 可共享的代码和配置审查后提交、推送；新机从远端克隆。
- 尚不适合提交的工作，把相关文件或整个项目目录单独备份，包含需要的隐藏文件。
  整个项目副本需要保留 `.git` 才能保留本地分支与提交；复制后仍要核对外部软链接。
- 忽略文件不会随 `git clone` 恢复。重点检查 `.env`、手写配置、未入库文档和本地数据；
  `node_modules`、`.venv`、构建产物、缓存通常可重新生成。
- Dotfiles 当前两处本地修改属于已有工作，本手册没有代为提交；Agent Kit 的修改同样原样保留。

### 2.2 单独准备私密恢复清单

这些内容不加入 Dotfiles；迁移时使用自己的安全备份渠道或重新授权。

| 内容 | 旧机现状/位置 | 新机操作 |
| --- | --- | --- |
| Shell 私密变量 | `~/.env` 指向 `~/.local/env-vault/.env`；Vault 的 Git 没有远程，另有不同内容的 `~/.env.litellm` | 必要变量经安全渠道保存/恢复；要保留历史时连同 Vault 私有历史处理，核对本机路径和代理地址 |
| SSH | `~/.ssh/`、`~/.ssh/config` 存在 | 恢复仍需要的主机别名；新建并授权密钥，或安全恢复必须沿用的密钥，核对权限 |
| GPG | 默认 `~/.gnupg/` 存在，本轮未见默认私钥目录 | 有实际签名/解密用途再确认，不能仅因目录存在就列为必须搬迁的私钥 |
| Git 本机配置 | `~/.gitconfig` 存在，未由本仓库管理 | 核对用户名、邮箱、签名及 include 路径，只恢复仍适用的设置 |
| GitHub、AI 工具与其他账号 | 本机有认证目录，未审查认证内容 | 账号通常重新登录即可；本地会话/历史是另一类资料，按需保存 |
| 服务私密覆盖 | Agent Kit 的环境变量及被忽略的服务配置 | 按 Agent Kit 的说明恢复，仓库示例文件不包含真实密钥 |

注意：只复制 `~/.env` 的软链接可能在新机得到断链。也不能因为恢复了 `.env` 就认为
EnvVault 的自启、GUI 进程环境或所有账号都已恢复；这些需要各自验证。
`~/.codex`、`~/.claude`、`~/.qwen`、`~/.qoder`、`~/.openclaw` 同时包含配置、账号、历史与运行状态。
其中独有会话/记忆值得保存，认证通常可重新登录，缓存可重建；需要目录副本时先退出对应应用，
数据库按应用支持的方式一致性保存。文件备份存在不等于已证明新客户端能直接接续全部旧会话。

### 2.3 个人文件与服务数据

- `Documents/life` 和两个知识库已有迁移工作台的指定范围归档，按其清单取回并补后续变更。
  `Desktop`、`Downloads`、`Pictures` 和历史电脑资料中还有前轮来源范围外的内容，详见工作台私有报告。
- 确有独有文件的目录使用迁移助理、可信备份或文件传输复制。
  先核对目标容量，复制后抽查重要文件；云盘文件需要确认实际同步或已下载。
- 模型一般重新下载；不可再下载的模型、自训练权重或大体积模型可以单独复制以节省下载。
  这属于数据迁移，不加入 Dotfiles。
- LiteLLM 的网关 Key 可以重建，但依赖旧 Key 的客户端需要更新；日志可按需舍弃。
  Multica 有项目、任务消息与附件，已有本机备份和隔离恢复证据，异机保存/新机恢复仍待执行。
  LexiFlow 当前词库可按所属项目的固定来源重新导入，不默认要求搬迁旧数据库。
  服务定义与数据始终回所属项目处理。运行中的数据库目录不能作为普通文件夹直接复制来保证一致性，
  参见 [PostgreSQL 文件级备份说明](https://www.postgresql.org/docs/current/backup-file.html)。
- 先完成必要数据备份，再让旧机退役；本次没有执行任何业务数据导出。

## 3. 新 Mac：先装基础环境

1. 在系统中准备用户账号和网络。需要代理或私有仓库认证时，先恢复最小的网络及登录能力。
2. 执行 `xcode-select --install`，在系统对话框完成 Command Line Tools 安装。
3. 按 [Homebrew 官方安装说明](https://docs.brew.sh/Installation) 安装 Homebrew。
4. 使用统一 feipi-agent-kit；下文组件级命令仅供维护参考，日常配置通过运行副本生效，完整顺序见 ../../docs/workbench.md。

```bash
# HTTPS 克隆可避开尚未恢复 SSH 密钥的问题；私有访问仍需相应认证。
mkdir -p "$HOME/Documents/tools/llm"
git clone https://github.com/iampkuhz/feipi-agent-kit.git "$HOME/Documents/tools/llm/feipi-agent-kit"
cd "$HOME/Documents/tools/llm/feipi-agent-kit"
./workbench install mac
./workbench apply mac
```

5. 复制 `Brewfile.local.example` 为 `Brewfile.local`，按需取消注释。
   本机目前没有 `Brewfile.local`，因此桌面应用尚未形成单机必装清单。
   为恢复当前高优先级桌面配置，选择 `iterm2`、`karabiner-elements`、
   `font-jetbrains-mono-nerd-font`。其他 GUI 和 JDK 仅在业务需要时选择。
6. 在仓库内执行：

```bash
# 先只读查看计划与已知冲突；未核实项不代表通过。
bash bootstrap/run.sh plan
# 安装声明的依赖、Node/npm、Rust、oh-my-zsh，最后链接 Zsh 与 Neovim。
bash bootstrap/run.sh
```

如果遇到已有 `.zshrc` 或 Neovim 文件冲突，先审查、备份并移走确认可替代的文件再重试。
脚本拒绝覆盖；不会自动接管系统或其他工具生成的配置。

基础配置恢复后，从安全渠道恢复必要的 `~/.env`，再新开终端。
Node/Rust 按脚本规则准备可用环境，各业务项目要求的精确版本按项目声明补齐。
Python 用项目锁文件和 `uv sync` 等项目入口重建，Java 按项目要求安装；无需复制旧机工具链目录。

## 4. 新 Mac：恢复 HHKB 和 iTerm2

在首次配置应用前执行以下命令，可减少应用先生成默认 JSON 带来的冲突：

```bash
# 先确认两个固定目标没有冲突，再复制小型 JSON 配置。
bash bootstrap/desktop.sh check
bash bootstrap/desktop.sh install
```

脚本只复制普通文件，不启动应用；与已有配置不同会停止，先人工备份、合并再处理。

- Karabiner：按应用提示完成系统权限，在应用中确认选中 `HHKB-test`，实际测试右 Command/Fn
  和方向键层。保存规则的设备编号为 vendor `1278`、product `33`。
- iTerm2：选择动态 Profile `Dotfiles`，按需设为默认，确认 JetBrains Mono Nerd Font 和常用按键。
- 两份 JSON 合计约 25 KB；应用内后续调整不会自动回写仓库，需要人工审查后同步。

## 5. 新 Mac：项目、Skills 和服务

### 5.1 项目代码

重新克隆已推送的仓库，再补回第 2 节保存的本机独有文件。按照各项目自己的锁文件、
README 和版本声明安装依赖；含原生编译产物的旧环境尤其需要重建。
使用软链接安装的配置或 Skills，必须在新机重新运行所属安装入口，避免链接仍指向旧机路径。

日常使用的 AI 应用/CLI 需要另行安装和登录；PATH 配置存在不代表可执行程序已经安装。
可选的 Qwen 设置见 [Qwen 配置说明](qwen/README.md)，它不包含客户端安装、私密凭据或完整历史恢复。
这些工具的用户数据目录未在本次形成经过验证的整体搬迁方案。

### 5.2 Agent Kit

克隆 `feipi-agent-kit` 后，阅读其 `README.md` 和 **`docs/setup-new-mac.md`**。
当前旧机入口为：

- [Agent Kit README](https://github.com/iampkuhz/feipi-agent-kit/blob/main/README.md)
- [新 Mac 服务重建](https://github.com/iampkuhz/feipi-agent-kit/blob/main/docs/setup-new-mac.md)

旧机仓库位于 `~/Documents/tools/llm/feipi-agent-kit`；离线时直接阅读仓库内对应文件。
Skills 使用该仓库自己的 `make install-links` 入口；服务、Podman machine、环境变量、
健康检查和后续自启均按该仓库维护的说明处理。Dotfiles 不增加第二套 Compose 或自启脚本。
本次仅核对其文件与说明存在，没有运行它的安装或启停命令。

目前核对的 LiteLLM/PostgreSQL、SearXNG、Crawl4AI 三份 Compose 都使用 `image:`，
没有 `build:`；它们重新拉取镜像即可，服务配置随 Agent Kit 克隆。
其他组件有自己的构建方式，例如 Agent Kit 的 draw.io；仍在所属仓库处理。

### 5.3 本机自启与独立工具

本机还存在 EnvVault、OpenClaw、GitHub Runner、Multica 和监控任务等 LaunchAgent。
它们不在 Dotfiles 的初始化范围，本次未逐项证明具备迁移条件。
迁移当天仍依赖的任务，回到对应项目执行安装/注册并核对路径、凭据和日志。
不能直接复制整个 `~/Library/LaunchAgents/`：其中有旧机绝对路径，引用的解释器、脚本和私密环境也未必存在。
不再使用的任务不作为本次迁移前置。

## 6. 旧机退役前的验收清单

以下复选框只在新机实际验证后勾选。服务就绪探测与真实业务调用分别验收。

- [ ] 重要仓库的分支、未提交修改、未跟踪文件和本地独有资料均已保存，并在新机核对。
- [ ] 新开终端，运行 `bash bootstrap/check.sh` 与 `bash bootstrap/brew.sh check`，逐项处理报告。
- [ ] Git 能访问常用远端；需要的 SSH 主机可连接；需要时验证 GPG 签名/解密。
- [ ] 必要的私密环境变量已恢复；通过实际功能验证，不打印密钥确认。
- [ ] Neovim 完成插件安装，运行 `:Lazy restore`、`:checkhealth`，实际打开代码和 Markdown 验证。
      Treesitter 分支与锁文件差异仍须审查处理，不能只凭配置链接正确就验收。
- [ ] HHKB 按键正确，iTerm2 字体、Profile 和常用按键符合预期。
- [ ] 常用项目能够安装依赖、构建或运行；项目版本正确。
- [ ] 按需完成 Agent Kit 的检查和服务恢复，必要上游实际调用成功；有数据要求时核对已恢复数据。
- [ ] 仍需要的自启任务在新机重新安装并实际验证；没有重复执行同一个外部任务。
- [ ] 个人文件备份与恢复抽查完成，账号可登录；保留旧机或另一份可恢复备份直至确认无遗漏。

## 7. 哪些可以直接复制文件夹

| 对象 | 建议方式 | 是否要保存大量代码/运行文件 |
| --- | --- | --- |
| Dotfiles 配置 | 克隆仓库，运行脚本 | 当前配置文件内容合计不到 1 MB；不含 `.git` 历史和下载的依赖 |
| oh-my-zsh、nvm、Neovim 插件 | 安装入口重新下载 | 部分确实会克隆源码，存放在新机工具目录；不把它们复制进 Dotfiles |
| 已推送的业务仓库、Agent Kit | 重新克隆 | 只恢复实际要用的项目；项目源码由其自己的仓库保存 |
| 未提交项目、未入库文档、个人资料 | 筛选后复制/备份恢复 | 可以复制目录，包含必要隐藏文件，核对软链接和本地 Git 状态 |
| `~/.env`、SSH/GPG 等 | 安全恢复必要文件或重新授权 | 通常体积小，不能提交 Git；注意 `~/.env` 的实际目标文件 |
| Podman 镜像、容器、虚拟机 | 按 Agent Kit 重建 | 新机仍会下载和占用磁盘；不加入配置仓库 |
| 运行中数据库目录 | 专门的数据库备份与恢复流程 | 不能用普通目录复制替代一致性备份 |
| `node_modules`、`.venv`、缓存、编译产物 | 按项目声明重建 | 通常无需迁移；独有输出文件另行筛选 |

未完成的迁移项并不都靠复制文件夹解决：代码要保住本地工作，私密变量要恢复实际内容，
账号要授权，数据库要有一致性备份，应用权限和自启要在新机重新验证。
