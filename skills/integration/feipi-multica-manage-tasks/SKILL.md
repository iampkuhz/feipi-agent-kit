---
name: feipi-multica-manage-tasks
description: 用本机 multica CLI 查询、创建和更新 Multica 项目及项目资源，或定位仓库对应的项目、管理 Issue、派发和提交验收。用户要求 Multica 操作，或仓库明确启用 Multica 的实质执行工作时使用；查询与方案讨论不触发写入。
---

# Multica 项目与任务协作

## 先判断用户要管理什么

- **项目本身**：看项目清单、进度或资源，创建项目，修改项目状态、描述、负责人或日期，绑定仓库。读 [项目管理](references/project-management.md)。显式给出工作区与项目时可直接用本机 `multica`，无需先接入当前仓库。项目管理操作不附带创建 Issue、派发或永久启用仓库协作。
- **项目内的任务**：定位实际仓库，再按下文处理查询、录入、执行或验收。任务状态与项目状态分别核实；更新一方不等于更新另一方。

## 输入与输出

任务协作从实际工作目录解析项目，再结合对话确定 Issue、用户意图和交付要求。输出任务链接、操作结果、当前状态/实际执行者、证据或阻塞、下一步。只同步任务与结果，不复制私有聊天历史。

先区分记录、当前聊天处理和后台执行。仅要求讨论或设计时先调查与设计，不创建或派发任务；已明确授权的执行与验收连续完成，不重复确认。

生成报告、写入文件和“提交结果供验收”属于执行；核对过程只读并不使报告交付变成纯查询。真正的普通咨询或进度查询只回答信息，不产出待交付工作，不写任务或评论。

## 任务协作的项目定位与启用

先运行本 Skill 的 `python3 scripts/project.py context --directory 实际工作目录`（脚本路径相对完整 Skill 目录，不相对业务仓库；工作区单文件入口使用其中注明的 SKILL_DIR）。返回 project_id、project_url、directory_role、enabled；复用现有机器映射并核对服务端身份，不逐次询问项目链接或按名称猜测。

context 成功后直接复用返回的 ID、URL 与目录，不再为定位项目扫描客户端配置、会话、计划、记忆或凭据目录。失败时只核对实际目录和既有机器绑定，并按具体错误处理；不靠全盘搜索补猜。

context 成功只证明可定位。仓库 AGENTS.md 明确声明项目键并加载本 Skill 后，enabled 才为 true；主动关联还须遵守入口限定的客户端和工作范围，例如仅 Codex 启用不能扩展至其他客户端。对范围内已授权的实质工作主动关联与回写。用户显式要求 Multica 操作可在未启用项目执行本次操作，不顺带永久启用。仅讨论或设计不创建任务或评论。

初次配置、项目键冲突、worktree/release 边界和仓库入口的预览/应用见 [项目接入](references/project-setup.md)。新仓库无唯一绑定时先核对现有项目，再按授权接入；查询失败不能当作项目不存在。后台任务不修改机器配置或仓库入口。

## 标准操作

查询使用本 Skill 的 project.py；写入复用已安装的 `multica-work`（任务语义与回执）和 `multica-task`（原生 CLI）。首次读帮助及所用子命令帮助，标准输入、回执和典型用法见 [操作参考](references/operations.md)。缺少命令时报告环境缺口；不要另写 API 客户端或直接读取个人 token。服务部署、机器绑定与发布由 Multica 运维组件维护。

普通调用自动使用 personal profile；后台沿用 Multica 注入的 task token、task ID、agent ID、workspace ID 和 server URL。任一任务身份缺失应停止，禁止改用个人配置绕过。后台不能修改机器配置、安装技能或启动第二个 daemon。

| 用户意图 | 操作 | 是否启动运行 |
|---|---|---|
| 找当前项目/任务 | `project.py context / find / read` | 否，只读当前项目 |
| 把事情记下来 | `record --project ID --title 标题 --body-file 文件 --request-id 固定ID` | 否，创建未分派 Backlog |
| 当前聊天处理 | `bind ISSUE --directory 目录 --owner 当前工具及聊天标识 --request-id 固定ID` | 否，记录交互归属 |
| 更新进展 | `note ISSUE --body-file 文件 --request-id 固定ID` | 否，自动加 `/note` |
| 交给后台 | `dispatch ISSUE --agent 逻辑键 --packet 交接包.json --request-id 固定ID` | 是，一次明确派发 |
| 提交验收 | `deliver ISSUE --body-file 证据.md --artifact 产物 --request-id 固定ID` | 否，上传附件并进入 Review |
| 唤醒下一角色 | `handoff ISSUE --agent 逻辑键 --packet 交接包.json --request-id 固定ID` | 是，正常 @回复 |
| 失败后接着做 | `recover ISSUE`，检查后决定续接 | 否，不自动重派 |

评论触发的后台任务必须在 note、deliver、handoff 中加 `--parent 原触发评论ID`。用 `multica-task issue runs ISSUE` 定位当前 MULTICA_TASK_ID 对应的 trigger_comment_id；它不是其他工具的会话 ID。不得把所有完成交接都改成静默评论；需要下一角色运行时才用 handoff。执行角色以当前声明和完整绑定为准，历史示例不代表已启用；LexiFlow 专用角色只在其正式范围内使用，不能借来执行通用验收。

## 信息组织与工作节点

1. **开始**：context 定位；明确编号直接 read，否则 find 候选并核对范围。明确同一事项则复用；没有合适任务且已获执行/录入授权时按 [需求模板](templates/task.md) 创建。标题描述成果，不把角色或未经确定的版本写死。
2. **执行/恢复前**：读取最新需求、有效评论和活动 Run。find 的 has_more 为真、read 的正文被截断或线程有回复时，先按需展开相关内容；不能把一页无匹配视为不存在，也不能只依赖旧聊天上下文。已有后台执行时先确认接手方式，bind 不会注册原生会话或取得目录排他锁。
3. **范围或阻塞变化**：用 [进展模板](templates/progress.md) 写当前结果、证据、剩余、下一责任人、需要用户事项，通过 note 静默回写。不逐条复制聊天，不给纯查询写评论。父任务受影响时补简短汇总，避免机械同步状态。
4. **交付**：用户要求“提交结果供验收”时，按 [交付模板](templates/delivery.md) 写实际产物、已验证项和剩余限制，执行 deliver 上传持久附件，再读回附件与 Review 状态；只写本地报告不算提交。整体任务尚未通过验收不妨碍提交本次有界结果，不能因此省略回写，也不能自签整体通过。需要下一角色执行时显式 handoff，按项目自己的验收标准决定 Done。

模板是内容约定，填写实际事实，删掉不适用提示，不上传未填写的范文。稳定需求放正文，过程留评论，工程规则引用仓库文件。标准动作返回不足的信息从 read 取得；不编造任务 URL、负责人或验证结果。

## 派发与交接包

复制 [交接包模板](templates/handoff.json)，填写 objective、scope、directory、acceptance、artifacts、remaining、required_commands、required_mcp；前四项为非空字符串，后四项为字符串数组。跨工具传递任务与产物，不传私有会话历史。

dispatch 核对 Agent 的完整 runtime 身份、daemon、profile、项目目录、共享技能和命令。通用入口只处理当前机器绑定的 in_place 项目；worktree 交给原生项目流程并记录实际目录。必需 MCP 若没有任务内调用证据，不能仅凭桌面配置标记可用；此入口会阻止自动派发。可选工具缺失可降级，但须说明。

任务开始时读交接包与项目规则，验证实际 cwd、命令和技能可用性；执行前遇到缺口只回写阻塞，不修改个人环境。执行工具、OpenClaw Agent ID 和 LiteLLM 模型别名分别记录，不能混作一个 model 名称。

## 重试、结果和恢复

- 同一次意图的 request-id 固定，例如 `issue-123-deliver-1`；重试复用，不能每次生成新值。已成功返回原回执；pending 表示服务端结果未确认，先查 Issue、评论、runs 和产物。它是本机防重，不承诺多机器事务。
- 只读预检失败尚未发送请求，不应产生 pending；缺口解除后以原输入和原 request-id 重试。已成功的请求直接返回原回执；输入或附件改变属于新意图，先核对现状再使用新 request-id。
- `recover ISSUE` 返回运行、评论来源、request-id、附件定位和本机回执；只供核对，不重派、不删除 pending，也不把未知请求自动改为成功。部分交付可能已经上传附件但未更新状态，同样先核对服务端。
- `multica-task issue runs ISSUE`、`issue comment list ISSUE` 用于取证。已有活动 run 时不要重派。跨工具依赖显式交接包，同工具续接由原生 runtime 管理；不互换私有 session ID。
- 区分服务就绪、模型请求成功、技能和工具实际可用、产物验证通过四层结果。报告真实失败层，不因进程退出码为零自动宣告任务验收。
- doctor/verify 通过仅证明其覆盖的静态配置或服务检查；`evidence-required` 表示当前环境仍需实机证据。报告和附件必须对应本次 run、实际 Agent、runtime、工作区与目录；旧通过记录不能替代当前验收。
- deliver 正文写明产物、验证命令和结果、未验证事项及剩余工作；至少上传一个持久附件，可为包含提交/PR 地址的交付说明。临时目录不能是唯一交付。用户或项目验收流程决定 Done。
- 不主动向 Telegram、邮件或其他外部渠道发送通知；遵循本次用户明确授权。

## 验收标准

先核实项目和目录正确，再读回 Issue 和 runs：记录、绑定及进展没有新增 run；派发有且仅有目标执行，重复 request-id 返回原回执；交付附件可取得且状态为待验收。项目启用需在新会话验证实际加载；后台会话桌面显示、原 Run 纠偏和排他接管属于客户端接入能力，本 Skill 不宣称已经实现。无法完成时明确保留了哪些产物、阻塞层和接手方式。
