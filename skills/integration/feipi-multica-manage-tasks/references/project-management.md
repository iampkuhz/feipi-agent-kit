# 本机 CLI：管理 Multica 项目

项目用来组织 Issue，也保存会进入未来 Agent 任务的项目描述和资源。用本机 `multica` 和已授权的 CLI 登录态；本入口按本机验证过的 0.6.3 命令设计。先用 `multica --version` 和实际子命令的 `--help` 核对能力。服务不可达、认证失败、工作区不一致或命令不支持时，说明具体缺口；不读取凭据，不自行登录、切换默认工作区、升级或启动 daemon。

## 定位与查询

`SKILL_DIR` 指当前已加载的 Skill 目录。CLI 默认 profile 能用时省略 `--profile`；下面的 `personal` 仅为本机示例。显式指定工作区时传完整 UUID，不把名称当作 ID。

```bash
python3 "$SKILL_DIR/scripts/project.py" projects --profile personal
python3 "$SKILL_DIR/scripts/project.py" projects --profile personal --status in_progress
python3 "$SKILL_DIR/scripts/project.py" overview "$project_id" --profile personal --workspace-id "$workspace_id" --resources
python3 "$SKILL_DIR/scripts/project.py" overview --directory "$actual_directory"
```

- 看工作区：`projects` 先核对工作区身份，再列项目 UUID、状态、负责人 ID、计划日期、任务总数和完成数。若目标不在当前工作区，用 `multica workspace list --output json` 找用户指定的工作区，再用 `--workspace-id`；不改变默认工作区。多个候选时请用户指出目标，不对同名项目写入。
- 看项目：项目 UUID 或链接中的 UUID 可直接用；用户说“这个仓库的项目”时用目录模式，沿用 [仓库绑定](project-setup.md)。没有唯一绑定时可以列工作区项目辅助确认，但不能从仓库名称、Git origin 或列表顺序推断归属。后台仅使用当前任务的已绑定目录查询，不切换到个人 CLI。
- 看进度：项目 `done_count / issue_count` 是服务端总计，默认的一页 Issue 是明细样本。按需用 `--issue-status`（当前项目实际状态键）、`--offset`（用返回的 `next_offset`）扩展；`has_more` 为真不能宣称清单完整。没有证据时不把未完成任务判为阻塞。具体 Issue 的执行线程与回执见 [任务操作](operations.md)。
- 看上下文：`--resources` 才拉附加资源；预览被截断时按需加 `--full-description`。映射确认了 Web 地址时返回链接；无已核实地址时返回工作区和项目 UUID，或保留用户提供且匹配该 UUID 的链接。不要用 API 地址拼 Web 链接。

## 项目写入与读回

只在交互式 CLI 身份下执行明确的项目变更；后台任务不改用个人身份做项目写入。写前确认 CLI 使用的 profile、工作区 UUID、目标项目 UUID；目录模式先从 `context` 取得身份，不另建配置。交互式终端可用下面的函数复用选定身份；`profile` 为空时使用已核实的原生默认 profile。

```bash
mc() {
    if [ -n "$profile" ]; then set -- --profile "$profile" "$@"; fi
    "${MULTICA_CLI_BIN:-multica}" --workspace-id "$workspace_id" "$@"
}
mc workspace get --output json
```

验证返回的工作区 `id` 后再读写。已有项目先 `mc project get "$project_id" --output json`，核对 `id` 与 `workspace_id`；值已经符合要求就直接报告。JSON 从 stdout 读取，不把 stderr 的提示混入；没有成功回执时先查现状，再决定是否重试。

| 意图 | 用法与验证 |
|---|---|
| 建项目 | `mc project list --output json` 核对已有同名和范围；明确要新建时 `mc project create --title "$title" --output json`，可按需加描述、日期、负责人、状态。用返回的 UUID 读回；若调用超时，先查清单和候选详情，不能再盲目建一次。 |
| 改名称、描述、日期、负责人 | `mc project update "$project_id" --due-date "$date" --output json`。只传要求变更的字段；空字符串日期代表清空，省略代表不变。`--lead` 用 CLI 支持的已核实成员或 Agent 名称；若重名或无法核实，不猜。重新 `get` 验证字段。 |
| 更新项目状态 | `mc project status "$project_id" "$status" --output json`，再 `get`。0.6.3 项目状态键为 `planned`、`in_progress`、`paused`、`completed`、`cancelled`；它们不是 Issue 状态。项目完成的判断应来自用户意图和交付证据，不因少量样本完成就批量修改任务。 |
| 添加 GitHub 仓库 | 先 `mc project resource list "$project_id" --output json` 对照 URL 和 ref，再 `mc project resource add "$project_id" --type github_repo --url "$repo_url" --output json`；可加 `--ref` 指定分支、标签或 SHA。再次列资源验证。 |
| 添加本地执行目录 | 仅在用户明确给出或确认实际目录及其所属 daemon 后添加：`mc project resource add "$project_id" --type local_directory --local-path "$absolute_path" --daemon-id "$daemon_id" --output json`。用 `mc runtime list --output json` 核对目标机器的 `daemon_id`，不要用 runtime 的 ID；确认真实路径。`in_place` 默认共用目录，`worktree` 需要已有提交的 Git 仓库和 daemon 能力；只有用户要求时才改变执行模式。重新列资源核对。 |
| 改动、解除资源 | 从资源清单核对资源 UUID 与归属，使用 `mc project resource update "$project_id" "$resource_id" ...` 只改必要字段；明确要求解除时用 `mc project resource remove "$project_id" "$resource_id" --output json`，列清单确认。 |

资源会影响未来任务：项目资源不等于 `repo checkout`，也不等于本机目录映射或仓库协作启用。注册项目与资源按独立回执报告；项目已创建而资源未确认时，保留项目 UUID，只检查或续接资源步骤。项目删除、工作区管理、工作流管理、部署和批量改写不属于此入口。
