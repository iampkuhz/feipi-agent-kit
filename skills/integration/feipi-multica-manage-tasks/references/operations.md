# 原生任务操作与可选回执

## 身份、项目和只读上下文

`multica` 是默认入口。交互式调用沿用用户选定的 CLI profile 和工作区，不固定为 personal；后台使用注入的完整任务身份，不传个人 profile。选择工作区用 `--workspace-id`，不改变默认工作区。下面的 `mc` 仅表示已经选好身份的原生 CLI，`SKILL_DIR` 是本次加载的 Skill 目录。

```bash
mc() { multica --profile "$profile" --workspace-id "$workspace_id" "$@"; }
mc workspace get --output json
mc project get "$project_id" --output json
mc issue get "$issue_id" --output json
```

写操作前核对工作区 `id`、项目 `id/workspace_id` 和 Issue `id/project_id/workspace_id`，不靠标题或当前目录猜。单轮内复用读回结果；切换目标或恢复未知请求时重新核实。后台不得用上面带个人 profile 的函数；直接调用注入环境中的 `multica`。

也可用 Skill 的查询辅助入口，只有 Python 标准库和官方 CLI 即可工作：

```bash
python3 "$SKILL_DIR/scripts/project.py" find --project-id "$project_id" --profile "$profile" --workspace-id "$workspace_id" --query '关键词'
python3 "$SKILL_DIR/scripts/project.py" read "$issue_id" --project-id "$project_id" --profile "$profile" --workspace-id "$workspace_id"
python3 "$SKILL_DIR/scripts/project.py" read "$issue_id" --project-id "$project_id" --thread "$thread_id" --limit 10 --runs
```

显式项目无需 machine.json 或运维命令。后台省略 profile，所选工作区必须等于注入值；项目由当前平台任务上下文明确指定。需要从仓库自动发现时省略 `--project-id` 并用 `--directory`，见项目接入。

find 是一页标题/编号包含匹配，`has_more/next_offset` 用于继续，不是全局语义去重。read 默认读取需求预览和**全部根线程轻量摘要**；`--runs` 才查活动运行。先扫描完整索引，再按相关 ID 用 `--thread` 展开。正文截断时加 `--full-description`。原生线程游标在 stderr，继续读取使用成对的 `--before/--before-id`；不得因预览或尾部回复没有出现要求，就认定要求不存在。

## 写入、派发与发布

以下每一项都先按上节核对目标归属，并读当前环境给出的评论/状态规则。正文文件放实际工作目录内，以 UTF-8 写入真实换行；不要把未知来源正文拼进 shell。评论成功后才清理文件。

| 意图 | 原生操作 |
|---|---|
| 记录需求、不启动 | `mc issue create --project "$project_id" --title "$title" --status backlog --description-file ./task.md --output json`；不传 assignee，读回确认未启动。项目用自定义初始状态时按项目实际状态键。 |
| 改需求、日期、优先级或状态 | `mc issue update "$issue_id" ... --no-start --output json`；只传要求修改的字段，读回。状态必须匹配项目实际工作流。 |
| 静默备注或发布材料 | 正文以 `/note` 开头：`mc issue comment add "$issue_id" --content-file ./reply.md --output json`；任务评论触发的回复需加本轮指定的 `--parent`。附件按需要追加 `--attachment`，已有提交或 PR 链接可直接放正文。 |
| 明确派发 | `mc agent list --output json` 选择 UUID，`mc agent get "$agent_id" --output json` 核对；查 `mc issue runs "$issue_id" --active --output json`。确认可启动后先 `mc issue assign "$issue_id" --to-id "$agent_id" --no-start --output json`，再发布包含 `[@名称](mention://agent/UUID)` 和交接内容的评论。读回触发结果和 Run；不使用会取消旧任务的 rerun。 |
| 下一角色交接 | 在平台要求的本轮线程中，用上面的明确 mention 发最终交接评论；通常不需要再次分派。遵守当前运行契约，不用静默 `/note` 吞掉需要的唤醒。 |
| 申请验收 | 材料发布后，仅在整单已满足申请条件且有相应意图时，单独 `mc issue update "$issue_id" --status "$review_status" --no-start --output json` 并读回。部分交付默认保留整单状态。 |

后台一轮只发最终评论（若当前平台有多线程/特殊角色规则，则按具体契约）。不为开始、过程或报告落盘另发评论。交付模板只组织证据，不替代测试、下载核对或验收人判断。需要核对附件时使用官方 attachment 帮助下载到本次唯一临时目录，并检查内容，而非把 hash 当正确性证明。

## 可选本机回执与分步恢复

已有 `multica-work` 时可用它为一次写操作保留回执；没有它仍按原生流程完成任务。它只依赖官方 CLI，不要求机器映射、受管 Agent 声明、固定 runtime 配置或共享 Skill 实例。每次操作都必须指定 `--project`，可指定 `--profile/--workspace-id/--server-url`，后台不得覆盖身份。首次用对应 `--help`。

```bash
multica-work deliver "$issue_id" --project "$project_id" --profile "$profile" --body-file ./delivery.md --request-id issue-123-materials-1
multica-work deliver "$issue_id" --project "$project_id" --profile "$profile" --body-file ./delivery.md --status "$review_status" --request-id issue-123-review-1
multica-work recover "$issue_id" --project "$project_id" --profile "$profile" --request-id issue-123-review-1
```

deliver 默认只发材料，无强制附件、无自动状态变更；它不运行测试，也不代表验收通过。bind 只是当前 cwd 的归属备注，不是原生会话注册、任务接管或排他锁。dispatch/handoff 的 `--agent` 使用平台 UUID 或唯一精确名称；执行端的必需工具和 MCP 待实际探针验证，不因派发端没有这些工具就拒绝。

同意图使用相同 request-id、内容和身份；正文换路径不会改变意图。回执绑定服务、工作区、操作者和当前 Run，重放先重新核对 Issue 和已发布评论。它不识别两个 Issue 是否同一需求，不提供跨机器去重或目录锁；平台已有的触发合并不由此包装器替代。

新回执逐步记创建、无启动分派、评论/附件和显式状态变更。评论成功而状态更新失败时，原参数重试会先确认原评论，只补状态；响应丢失时沿相关线程的分页核对 receipt-key，确认后继续。找不到可靠证据时保留 pending，禁止删回执或换新 ID 盲目重发。旧版单 pending 回执不自动迁移为成功，保留原审计信息，用原生只读核对。

recover 只返回当前 Issue、活动运行、完整轻量线程索引和指定请求的回执，不展开所有评论或扫描所有本机请求。输入或附件语义改变需先核对现状再作为新意图处理。不要用旧 Run 的回执或附件证明当前执行已经完成。
