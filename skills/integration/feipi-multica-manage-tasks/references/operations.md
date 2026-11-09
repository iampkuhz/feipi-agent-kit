# 标准交互与回执

`SKILL_DIR` 是当前加载的 Skill 实际目录；从客户端已提供的位置取得，不固定为 Codex 路径。首次用 `python3 "$SKILL_DIR/scripts/project.py" --help` 和 `multica-work --help`；写动作再读取对应子命令帮助。脚本只包装原生 CLI，不读取个人 token。

## 查询当前项目与任务

```bash
python3 "$SKILL_DIR/scripts/project.py" context
python3 "$SKILL_DIR/scripts/project.py" find --query '任务关键词'
python3 "$SKILL_DIR/scripts/project.py" read TASK-123
python3 "$SKILL_DIR/scripts/project.py" read TASK-123 --full-description --thread 评论ID
```

context 的 project_id 用于后续 record；project_url 用于返回用户。每轮在实际工作目录执行，跨仓库时重新解析。明确提供任务编号时直接 read，并校验所属项目；跨项目请求先定位对应仓库，不靠当前目录的默认项目写入。

find 每次只读当前项目一页标题与状态，默认50条，最多100条；返回 has_more/next_offset。用 `--offset` 继续，不能因为当前页没有候选就宣称不存在。query 是标题/编号包含匹配，不是语义去重；换相关关键词、看当前活跃事项，并 read 候选范围后才能决定复用或创建。已取消/已完成事项可能提供关联依据，但不自动恢复或合并。

read 默认返回最多1600字需求、活动 Run、最近5个根评论预览和附件定位。`description_truncated` 或 `content_truncated` 为真时，执行前按需展开有效范围、授权或纠偏；有回复数时展开相关线程。`--thread ID` 返回该线程最近5条回复及根评论，仍不承诺全历史；完整线程与更早回复用原生 `issue comment list --thread ID --tail N` 及其游标。恢复未知请求使用原有 recover，而非仅凭摘要判断。

## 写入与执行

| 场景 | 输入与动作 | 预期回执与读回 |
|---|---|---|
| 记录需求 | `record --project context返回的ID --title 成果型标题 --body-file task.md --request-id 固定ID`；使用需求模板 | Issue UUID/链接；Backlog、未分派、无新增 Run |
| 当前聊天执行 | `bind ISSUE --directory 实际目录 --owner '工具及真实聊天标识' --request-id 固定ID` | 静默归属评论；已有活动 Run 则停止绑定，不另起后台 |
| 更新进展 | `note ISSUE --body-file progress.md --request-id 固定ID`；使用进展模板 | 评论 ID；read 回当前变化，无新增 Run |
| 调整需求 | 先 read，再用原生 `issue update --help` 支持的标题/正文参数，必须 `--no-start` | 读回范围与状态；调整不隐式派发，保留证据关联 |
| 交给后台 | `dispatch ISSUE --agent 当前启用逻辑键 --packet handoff.json --request-id 固定ID` | 回执是派发请求；再查 runs，确认目标执行，不能将 queued 当作已完成 |
| 交接下一角色 | `handoff ISSUE --agent 当前启用逻辑键 --packet handoff.json --parent 触发评论ID --request-id 固定ID` | 正常 @回复；检查原线程、触发结果和实际 Run |
| 提交验收 | `deliver ISSUE --body-file delivery.md --artifact 持久产物 --request-id 固定ID` | 附件可取得、Issue 为 in_review；不代替验收者标 Done |
| 失败后接手 | `recover ISSUE`，核对评论来源、request-id、附件、活动 Run、pending 回执 | 只读恢复摘要；结果未知不重派、不删回执 |

上表写入命令均由 `multica-work` 执行（明确标注“原生”的除外）。后台评论触发的 note/deliver/handoff 必须传当前 Run 的 trigger_comment_id 作为 parent。

deliver 的 `--artifact` 可以重复，例如 `--artifact README.md --artifact evidence.md`；正文文件不会自动成为附件，需持久保存时也列为 artifact。上传由 deliver 完成，无需先手动上传同一文件。`multica-work` 是已安装的运维命令，不是本 Skill 的 scripts/work.py。

每次面向用户的回执统一回答：**任务链接、完成了什么操作、当前状态/实际执行者、证据或阻塞、下一步**。原 CLI 没有返回的字段通过 read 或原生查询取得，不能编造。bind 仍是归属记录，不是原生会话注册或排他锁。

## 典型用法

- “把这个需求记下来”：context → find/read 候选 → 填需求模板 → record → 读回。不会因为录入自动派发。
- “我就在这里把它修好”：项目已启用时，关联同一 Issue → read 最新范围与评论 → bind → 实现 → note/deliver。普通咨询和仅讨论设计不建任务。
- “之前做的接着做”：read/recover → 确认最新范围、活动执行及已有产物 → 继续当前执行或明确交接，重试保留原 request-id。
- “现在进展怎样”：只读摘要，先说明结果、阻塞和下一责任人；无需给每一条查询写评论。

任务正文只放稳定目标、范围和验收；当前结果与变化使用短进展，工程规则引用仓库文件，原始材料用附件或持久路径。父任务存在且本轮改变其进展时，可补一条静默汇总，不机械同步百分比、不自动关闭父任务。
