# 项目定位与启用

## 配置只保留一个来源

机器连接、项目 UUID 和路径继续由 `~/.config/multica-selfhost/machine.json` 维护；自定义位置沿用 `MULTICA_MACHINE_CONFIG`。不在仓库复制 token、完整机器配置或第二份服务地址。

`scripts/project.py context --directory 当前目录` 读取以下现有字段：

```json
{
  "schema": 1,
  "profile": "personal",
  "workspace_id": "工作区UUID",
  "server_url": "http://localhost:8080",
  "app_url": "http://localhost:3000",
  "projects": {
    "project-key": {
      "id": "项目UUID",
      "root": "/实际开发仓库",
      "release": "/可选的独立发布仓库"
    }
  }
}
```

这只是字段示例，不能覆盖现有 machine.json，daemon、runtime、Agent 和其他项目字段须保留。尚无绑定时，使用 `multica-task project list/get` 与 `project resource list` 核对现有项目；用户明确要求接入后，按 Multica 运维流程备份并补充对应 projects 项。没有唯一匹配时集中询问项目归属，不按同名或相同 Git origin 自动接管。新建项目须有相应意图，不能因查询失败就创建。

每次 context 校验当前 CLI 工作区与项目 UUID，返回项目 URL、实际目录用途和 enabled。项目 URL 来自现有 app_url、服务端 workspace slug 和项目 UUID，不猜 URL 中的工作区名称。任务身份优先，缺任务字段或与本机映射冲突时停止，不回退个人 profile。

## 定位与主动纳管分开

有机器映射就能定位项目、处理用户明确提出的 Multica 操作。只有仓库入口声明启用，才在实质执行工作中主动关联和回写；enabled=false 不应被解释为已启用自动流程。

在允许修改规则的目标仓库运行：

```bash
python3 "$SKILL_DIR/scripts/project.py" enable --directory /目标仓库
python3 "$SKILL_DIR/scripts/project.py" enable --directory /目标仓库 --apply
```

第一条返回追加内容预览，第二条备份后追加 `AGENTS.md` 小入口；不创建项目、不修改 Issue、不启动后台任务。已授权的接入可核对预览后直接完成，不额外索取同一授权。重复执行不重复追加；已有规则保留。项目要求规则另有维护源时，在该源接入，不能跳过项目治理要求。

入口包含可解析的 `Multica 项目键：` 行和加载本 Skill 的说明；具体工作流程只维护在 Skill 中。入口更新后在新聊天或原生新会话中检查实际加载情况，文件存在不等于宿主已经加载。

仓库有入口长度或规则真源约束时，不必追加通用长块。可保留下面的短入口，把客户端启用范围写入现有规则维护源；例如只启用 Codex 的主动协作，并明确讨论/查询不写入、项目正式验收继续有效。context 的 enabled 表示存在项目声明，实际动作还须遵守规则中的客户端范围，不能据此启用其他客户端。

```markdown
Multica 项目键：`project-key`
Codex 按仓库协作规则加载 `feipi-multica-manage-tasks`。
```

开发目录、release 目录分别启用，主仓库启用不自动授权发布仓库。原生 Git worktree 通过 git-common-dir 找回项目，同时保留实际工作目录；项目键不会把 worktree 冒充原地目录，也不会绕过 multica-work 的派发限制。嵌套 Git 仓库必须有自己的绑定。

## 常见失败

- 没有唯一目录绑定：检查 projects 和实际目录，歧义时指定 `--project 项目键`；该参数仍须通过目录核对。
- CLI 默认工作区漂移：报告预期与实际身份不一致，按运维入口修复；查询脚本不静默切换工作区。
- 项目键冲突：先核对仓库入口，禁止用另一个项目的 UUID 继续写入。
- 服务不可达或认证失败：报告连接层问题，保留本地工作；不能把失败当成“项目不存在”。
