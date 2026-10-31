---
name: feipi-multica-manage-tasks
description: 用于把本地聊天工作记录到 Multica、查询进展、静默回写、明确派发和跨 Agent 交接；用户要记录任务、交给后台、提交验收或恢复任务时使用。普通编码但未涉及 Multica、服务部署或技能治理不触发。
---

# Multica 任务协作

## 输入与输出

从对话确定 Issue 或项目、用户意图、实际工作目录和交付要求。能从当前项目和 Issue 取得的信息直接读取；不要凭 Agent 显示名猜机器。输出 Issue 链接、实际执行者及 runtime、结果或阻塞、验证证据。只同步任务与结果，不复制私有聊天历史。

## 执行入口

使用本机已安装的 `multica-work`（任务语义与回执）和 `multica-task`（原生查询）。首次先读 `multica-work --help` 及所用子命令帮助。缺少命令时报告环境缺口；不要另写 API 客户端或直接读取个人 token。服务部署、机器绑定与发布由 multica-ops 维护。

普通调用自动使用 personal profile；后台沿用 Multica 注入的 task token、task ID、agent ID、workspace ID 和 server URL。任一任务身份缺失应停止，禁止改用个人配置绕过。后台不能修改机器配置、安装技能或启动第二个 daemon。

## 意图到动作

| 用户意图 | 操作 | 是否启动运行 |
|---|---|---|
| 把事情记下来 | `record --project ID --title 标题 --body-file 文件 --request-id 固定ID` | 否，创建未分派 Backlog |
| 当前聊天处理 | `bind ISSUE --directory 目录 --owner 当前工具及聊天标识 --request-id 固定ID` | 否，记录交互归属 |
| 更新进展 | `note ISSUE --body-file 文件 --request-id 固定ID` | 否，自动加 `/note` |
| 交给后台 | `dispatch ISSUE --agent 逻辑键 --packet 交接包.json --request-id 固定ID` | 是，一次明确派发 |
| 提交验收 | `deliver ISSUE --body-file 证据.md --artifact 产物 --request-id 固定ID` | 否，上传附件并进入 Review |
| 唤醒下一角色 | `handoff ISSUE --agent 逻辑键 --packet 交接包.json --request-id 固定ID` | 是，正常 @回复 |
| 失败后接着做 | `recover ISSUE`，检查后决定续接 | 否，不自动重派 |

评论触发的后台任务必须在 note、deliver、handoff 中加 `--parent 原触发评论ID`。这个 ID 来自原生任务上下文，不是另一个工具的会话 ID。不得把所有完成交接都改成静默评论；需要下一角色运行时才用 handoff。遵循项目已有角色、审批和验收规则，不能用此入口跳过 LexiFlow 的正式协作要求。

## 交接包

JSON 必须包含以下字段：

```json
{
  "objective": "要达到的结果",
  "scope": "允许修改的范围、禁止事项和项目规则位置",
  "directory": "/实际项目目录",
  "acceptance": "可执行的验收标准",
  "artifacts": ["已有提交、附件或可访问文件"],
  "remaining": ["剩余工作与失败层"],
  "required_commands": ["git"],
  "required_mcp": []
}
```

dispatch 核对 Agent 的完整 runtime 身份、daemon、profile、项目目录、共享技能和命令。通用入口只处理当前机器绑定的 in_place 项目；worktree 交给原生项目流程并记录实际目录。必需 MCP 若没有任务内调用证据，不能仅凭桌面配置标记可用；此入口会阻止自动派发。可选工具缺失可降级，但须说明。

任务开始时读交接包与项目规则，验证实际 cwd、命令和技能可用性；执行前遇到缺口只回写阻塞，不修改个人环境。执行工具、OpenClaw Agent ID 和 LiteLLM 模型别名分别记录，不能混作一个 model 名称。

## 重试、结果和恢复

- 同一次意图的 request-id 固定，例如 `issue-123-deliver-1`；重试复用，不能每次生成新值。已成功返回原回执；pending 表示服务端结果未确认，先查 Issue、评论、runs 和产物。它是本机防重，不承诺多机器事务。
- `multica-task issue runs ISSUE`、`issue comment list ISSUE` 用于取证。已有活动 run 时不要重派。跨工具依赖显式交接包，同工具续接由原生 runtime 管理；不互换私有 session ID。
- 区分服务就绪、模型请求成功、技能和工具实际可用、产物验证通过四层结果。报告真实失败层，不因进程退出码为零自动宣告任务验收。
- deliver 正文写明产物、验证命令和结果、未验证事项及剩余工作；至少上传一个持久附件，可为包含提交/PR 地址的交付说明。临时目录不能是唯一交付。用户或项目验收流程决定 Done。
- 不主动向 Telegram、邮件或其他外部渠道发送通知；遵循本次用户明确授权。

## 验收标准

读回 Issue 和 runs：记录、绑定及进展没有新增 run；派发有且仅有目标执行，重复 request-id 返回原回执；交付附件可取得且状态为待验收。无法完成时明确保留了哪些产物、阻塞层和接手方式。
