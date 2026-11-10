# Multica 项目管理 Skill：对标与设计

现有 `feipi-multica-manage-tasks` 已覆盖仓库绑定、Issue 录入、进展回写、后台派发和持久验收。项目本身此前主要用于定位 Issue 归属。此次保留名称、注册与接入方式，在同一入口补上项目清单、概览、元数据与资源管理；显式管理某个项目可直接复用本机 CLI 登录态，无需为当前目录建立绑定。

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
