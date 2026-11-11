# Multica 项目管理 Skill：对标与设计

`feipi-multica-manage-tasks` 在同一入口管理项目、资源和 Issue。v5 默认使用官方 `multica`：平台已明确项目时，无需机器映射或仓库接入；本机映射只服务目录自动发现。部署声明管理哪些 Agent，与平台上哪些 Agent 可被授权执行任务，是两个独立问题。

| 对标来源 | 实现中的做法 | Multica Skill 的对应选择 |
|---|---|---|
| [OpenAI Linear Skill](https://github.com/openai/skills/blob/main/skills/.curated/linear/SKILL.md) | 先确认团队、项目和意图，按分诊、计划等场景组织步骤，先读再写。 | 先分流项目管理与 Issue 协作；用工作区、项目 UUID 定位，再选清单、概览或明确写动作。沿用本机 `multica` 登录态。 |
| [GitHub Awesome Copilot Issues Skill](https://github.com/github/awesome-copilot/blob/main/skills/github-issues/SKILL.md) 与 [GitHub Projects CLI](https://cli.github.com/manual/gh_project_item-edit) | 写前查询实际字段和目标 ID，按任务类型组织内容，只修改需要变更的字段，返回目标链接；Projects CLI 支持 JSON。 | 复用现有 Issue 模板；项目变更只传目标字段，用 JSON 读回确认，并返回已验证的链接或 UUID。 |
| [Anthropic Linear API Skill](https://github.com/anthropics/claude-tag-plugins/blob/main/linear/skills/linear-api/SKILL.md) | 单独核对身份，区分展示编号与 UUID，重复的筛选和分页封装在脚本。 | `project.py` 集中做工作区与项目身份核对、摘要和分页；只读列表与聚合概览封装，项目写入使用原生命令。 |
| [Multica 内置 Skill（0.6.3）](https://github.com/multica-ai/multica/blob/18fa9f728a9e25f2465df2789631edb2a75442ad/server/internal/service/builtin_skills/multica-platform/references/projects.md) | 通过原生 CLI 操作项目与资源；项目描述、仓库及目录会进入后续任务上下文。 | 区分项目资源、临时 checkout 和本机绑定；资源写前核对现有值，写后重列。只有明确要求才改变 Agent 的执行目录或方式。 |

首批功能围绕三个场景：

| 用户说法 | Skill 的行为 |
|---|---|
| “看进行中的项目；这个项目做到哪了？” | 从已确认的 CLI 工作区查清单，按 UUID 或仓库绑定查概览。项目完成数来自服务端总计，Issue 只取一页，资源按需展开。 |
| “新建发布准备项目，截止月底” | 先核对工作区和已有同名项目，明确新建后调用原生 `project create`，读回项目和日期。结果未知时先查再重试。 |
| “把这个 GitHub 仓库绑定到项目；把项目改为进行中” | 分别核对项目、资源和目标状态，按授权写入、读回。项目状态更新不会被扩写成 Issue 更新；目录映射与 Agent 派发仍是独立操作。 |

后续功能需要另有实际需求和命令证据再加入。当前无需增加 MCP、API 客户端、凭据来源或新的分发入口。项目删除、批量改写、工作流及服务运维未纳入这批功能。

运行方法见 [项目管理操作参考](../skills/integration/feipi-multica-manage-tasks/references/project-management.md)。

## 任务边界与恢复

- 每次写入核对身份、工作区、项目和 Issue；后台身份不完整时不回退个人 profile。派发核对平台 Agent、活动 Run 与已知目录约束，不以本机受管名单、模型、推理配置或 Skill 实例 ID 限制通用操作。
- 执行端确认实际 cwd、可执行文件、MCP 和验收能力；未知能力保留待验证，不伪称可用，也不因派发端缺少工具就拒绝。交接包区分 `required_executables` 与 `validation_commands`。
- 查询保留全部根线程轻量摘要，再按相关线程展开，避免只读最新五条遗漏要求。后台遵守当前平台每轮最终评论、正文文件与 parent 契约。
- 发布材料不强制附件、不自动改整单状态，也不代表测试或验收通过。只有明确意图且满足整单条件时单独改变状态。
- `multica-work` 是可选本机回执：按内容识别输入，绑定服务、工作区、操作者与 Run；重放核对远端，分步续接已确认的缺失操作。未知评论或创建结果保持 pending，不盲目重发。它不提供全局去重、需求去重或目录锁。

确定性回归入口是目标 Skill 的 `tests/run.sh`，行为评估标准在 `evals/cases.json`。真实平台验证应使用独立测试项目/服务，分别记录原生派发与交付、重试恢复、身份拒绝及全部线程摘要；这些结果与源码结构通过、安装副本一致性分别报告。运维声明保持不变，不通过新增 `session-browser-agent` 规避问题。

## 2026-11-12 验证范围

- macOS 与 Podman Linux 实际运行项目脚本 24 项、组件 54 项测试；registry 全部 10 个 Skill 的布局与安装过滤校验通过。
- `tests/platform_smoke.py` 在唯一临时 API、数据库、工作区和身份上验证：名单外 Agent 派发及 claim、仅官方 CLI 的明确项目入口、跨项目/工作区拒绝、完整十二个线程摘要、五项任务身份缺失拒绝、当前 Run 唯一最终评论及真实 parent、附件下载、正文换路径重放、评论丢失响应确认、部分成功只补状态及未知结果不重发。测试服务、数据和临时 profile 随测试清理。它验证真实平台协议与实际探针，不运行模型或实际 MCP。
- 完整附件链使用锁定的 Multica API/CLI 0.6.3；CLI 由无修改的官方 `18fa9f7` 源码临时构建，没有替换全局命令。可通过 `--cli` 指定该测试二进制，`--report` 写入本次唯一验证目录。
- 当前全局 CLI 已是 0.8.2，而本机 API 仍为 0.6.3。`--compat-cli` 额外复现了该组合：普通材料评论正常，附件上传未绑定 Issue，评论关联返回 409；回执保留 pending，相同请求重试没有再上传。这是已确认的环境兼容性限制，未通过自动升级、降级或绕过附件校验掩盖。
- v6 经工作台备份后定点安装到 Codex、Claude Code、Qwen、Qoder、OpenClaw；全部运行文件与源码一致，排除了 tests/evals。六个相关组件文件通过既有安装器定点发布；工作区 Skill 内容由原生 CLI 备份、更新及读回，保留现有 `-general` 展示名。
- 发布期间机器角色绑定发生变化，完整运维计划已失效，未应用。角色指令模板及运行文件已同步源码，但本轮未改平台 Agent 实例配置、模型或任务队列；角色声明与新机器绑定的诊断留在运维范围，不成为普通任务入口的前置条件。
