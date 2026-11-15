# 新 Mac 完整初始化交付与验收

目标：在三天内完成部署能力，供新 Mac mini 使用。旧机集中导出必要私有资料，新机一次准备后执行安装、恢复、启动与验收；中途失败保留证据，可修复后续跑。最终完成必须有干净 macOS 的真实安装与使用证据，不能用替身回归或旧机已安装软件代替。

## 必须交付的范围

| 范围 | 完成证据 | 当前状态 |
| --- | --- | --- |
| 原 dotfiles 配置 | 57 个跟踪文件和 6 个新增文件完整迁入并已推送；执行权限一致 | 已核对 |
| Bash 3.2 与 UTF-8 | 实际预览、来源检查及 C/UTF-8 两组回归通过 | 本轮修复并通过 |
| 裸机前置 | 无 Git/Python 时使用系统 Bash；固定官方安装器、摘要校验、一次 sudo 授权 | 入口已增加，旧机 plan/check 通过，真实冷安装待验 |
| 工作台编排 | install 复用组件阶段及失败传播；Node/Rust 可供后续补全使用 | 已统一；C/UTF-8 的四阶段、环境传递与失败停止回归通过，冷安装待验 |
| 配置发布与来源 | 空白 HOME 首次/重复应用、33 个配置来源及内容、路径别名、冲突保全 | Mac 两种 locale 与工作台回归通过，最终整机复验待做 |
| 常用软件 | 对照旧机 Brew 清单、近期命令频率、真实应用/脚本依赖 | CLI 清单补充；16 项应用清单与 --apps 安装入口已增加，真实新机安装待验 |
| AI CLI/客户端 | 锁定现有兼容版本安装、登录状态、真实小任务 | 待完整自动部署与验收 |
| 私有资料 | 一次导出/校验/恢复；env 真源、私有配置与外部链接可恢复；不输出秘密 | 基础配置包 5 项回归通过；真实导出 10 文件，隔离 HOME 恢复及权限通过；完整业务包待补 |
| 数据一致性 | Multica 数据库/附件/密钥同批；OpenClaw SQLite 停写恢复；旧机不发生双主 | 复用现有备份能力，完整新机恢复待验 |
| 服务冷启动 | Podman VM、本地连接、Compose、镜像拉取、健康等待、模型实际请求 | 待自动编排与验收 |
| 图表和文档 | Mermaid、draw.io、PlantUML、PPT/PDF 实际生成并检查产物 | 待新机验收 |
| oMLX/语音 | 安装来源、模型清单、设置恢复、首次推理 | 待补 |
| 自启与重启 | Env Vault、Podman/受管服务、OpenClaw、Multica 按依赖恢复；完整重启后小任务 | 旧机入口已盘点，待补并验收 |
| 人工准备 | 所有必要 copy/export/授权命令集中成一次操作；运行中不逐项追问 | 待交付可执行命令包 |
| 最终端到端证明 | 干净 macOS、准确源码版本/环境指纹、逐阶段日志、真实产物、重复执行、失败恢复 | 未完成 |

## 本轮发现与修复

- Bash 3.2 在 UTF-8 环境把变量后相邻中文标点误解析为变量名：使用明确的大括号边界；测试同时运行 C 与可用的 UTF-8 locale。
- 原来源验证只接受源码链接：增加工作台运行副本识别，同时逐文件比较源码与副本内容；旧副本仍失败。
- macOS `/var` 与 `/private/var` 别名导致 doctor 误报：统一解析真实路径，增加别名回归。
- 工作台原先直接循环四个脚本，遗漏总入口前置检查及 Node/Rust 环境激活：复用总入口的依赖阶段；统一仓库的组件入口转到工作台发布。
- 本机 Brew 清单缺少 Homebrew 管理的 Git 和 jq：本轮实际安装 Git 2.56.1、jq 1.8.2；按其依赖更新 libunistring 1.4.2 → 1.5，安装 oniguruma 6.9.10。首轮直连 GHCR 瓶包出现 TLS 错误，改用已确认可访问 GHCR 的当前代理后安装成功。共享 Brewfile 33 项现已检查通过；libtiff/webp 仍有不阻塞检查的元数据循环告警，需进一步定位，不通过删除软件处理。

工作台当前 21 项回归（含裸机前置 4 项、配置包 5 项）、服务 18 项回归通过。以上覆盖程序/配置层，不包含实际新机服务、账号和重启验收。

软件使用依据分开记录：Shell 历史覆盖 2025-08 至 2026-11，不能把全量频次当作最近使用。最近 30 天可定位 Podman 22 次、session-browser 12 次、SSH 11 次、tree/psql 各 1 次；Agent 自动调用通常不写该历史，因此还依据当前脚本依赖和运行服务补入 jq、ripgrep、PDF/Graphviz 工具、语言管理器与文档浏览器。session-browser 与相关 Java 项目仍需纳入后续完整环境恢复，不能仅安装 JDK 就认为功能已恢复。

## 当前真实验证条件

当前主机为 Apple M1、16 GiB 内存，可用磁盘约 77 GiB，未预装 macOS VM 工具。已查询 Tart 官方文档：当前主机不能提供 Podman 所需的嵌套虚拟化，因此即便虚拟机内基础软件通过，也不能据此声称整套本地容器服务已经在干净 Mac 验收。仍推进可独立完成的软件/恢复/服务交付，并寻找真实可用的整机验收路径。

Tart 手动下载首次经当前代理请求 GitHub API 返回 403；限定该下载使用直连后成功，Tart 2.41.1 归档通过官方 release 校验和。干净镜像 `ghcr.io/cirruslabs/macos-tahoe-vanilla:latest` 正在下载（24 GB 压缩层），尚未启动虚拟机或运行新机安装。验证工具和镜像保存于仓库外 `~/.local/state/feipi-workbench/new-mac-validation/`，关闭自动清理其他镜像。

参考：[Tart 嵌套虚拟化边界](https://tart.run/faq/#nested-virtualization-support)、[Homebrew 无交互安装](https://docs.brew.sh/Installation#unattended-installation)、[OpenAI 固定版本 Codex 安装示例](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex)。
