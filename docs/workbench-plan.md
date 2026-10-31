# 个人工作台实施记录

本次沿用 feipi-agent-kit 的 Git 与原有 skills/tools/rules/runtimes。新增 `components/mac`、`components/multica`、`components/openclaw`、`components/openclash`，保留成熟实现，不引入子模块或新仓库。

## 已核实的基线（2026-10-31）

| 组件 | 原来源与状态 | 接管原则 |
| --- | --- | --- |
| Agent Kit | HEAD `39004de`；Multica 技能和四份注册/文档有未提交工作 | 保留原路径与修改；日常技能使用实拷 |
| Mac | dotfiles HEAD `71cf9f6`；bootstrap/Zsh 有未提交改动 | 带入现有改进，日常配置使用运行副本，保留显式源码链接入口 |
| Multica | multica-ops HEAD `b2c7150`；适配/任务入口有未提交工作 | 复用既有运行副本、plan/apply 与一致性备份 |
| OpenClaw | 新来源 HEAD `735a186`，微信/成长日记等有未提交工作；npm 2026.9.2 | 保留 `~/.openclaw` 和 env vault；不重置记忆与身份 |
| OpenClaw 旧仓库 | HEAD `2b2c99e`，是新来源的祖先，落后 9 个提交 | 仅作历史回退；Multica 仍引用此旧路径，须修正 |
| OpenClash | iStoreOS 24.10.8；已有地区优先模块与当日备份 | 以路由器实际文件为准；订阅、节点和控制密钥留在私有目录 |

首次工作区/运行配置备份：`~/.local/state/feipi-workbench/backups/20261031-175613`。其中包括未提交文件和补丁，但不是数据库一致性备份。两份受保护配置 `.mcp.json`、`.claude/settings.local.json` 已记录 SHA-256，不修改。

## 参考取舍

静态阅读 [mac-ai-kit](https://github.com/tanjishengwu001/mac-ai-kit) 的 README、start.sh、INSTALL.md、DOWNLOAD_RECOVERY.md、check_tools.py；只下载和阅读，未执行它的脚本。

吸收：按用户任务组织入口、预览不产生变更、安装与启动分开、复用底层组件命令、区分发现文件与功能通过、保留失败中间产物和明确重试方法。不引入其模型目录、推理后端、复杂下载恢复机制或整套菜单框架。

## 实施与验收顺序

1. 保全工作区、记录来源和私有边界。
2. 实现 `./workbench` 日常入口与 `./develop` 研发入口；配置 diff/capture/apply 明确方向和范围。
3. 分组件回归、备份、应用和真实验收；失败恢复当前组件。
4. 核对运行配置来源、旧路径、自启动和私有资料；写入真实验收记录。

实际切换和分层验证结果见 [切换验收](workbench-validation.md)。本文件记录调查与取舍，不用计划代替验证。
