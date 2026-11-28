# Agent 操作手册

以下命令从仓库根目录运行。Mac 配置、组件命令和私有资料恢复见 [工作台手册](workbench.md)。

## 安装或更新 Skill

```bash
./workbench install skills
```

工作台先备份客户端中的受管入口，然后安装运行副本。安装后新开客户端对话，让客户端重新发现技能。

| 需要的范围 | 命令 |
| --- | --- |
| 发布到一个客户端 | `./workbench install skills --agent codex` |
| 发布一个 Skill 到一个客户端 | [单个 Skill 发布](workbench.md#单个-skill-发布) |
| 安装到某个项目 | `bash scripts/install_skills.sh --dir /path/to/project` |
| 检查仓库结构与注册表 | `bash scripts/harness/doctor.sh` |
| 验证安装行为 | `python3 -m unittest discover -s tests -p test_install_output.py` |

安装前会检查 `skills/registry.yaml`。全量同步会清理能确认由本仓库安装的旧入口。按 Skill 发布只更新选定技能及直接共享依赖。安装过程中会递归过滤 `maintenance/`、`tests/` 和 `evals/`。

## 阅读安装结果

| 标记 | 含义 |
| --- | --- |
| `[新增]` / `[更新]` | 安装新入口，或更新内容、权限和链接 |
| `[跳过]` | 内容、权限和链接一致 |
| `[删除]` | 删除已确认由本仓库安装的退役入口 |
| `[保留]` | 与仓库 Git 历史中的 Skill 同名，安装来源无法确认，保留现有入口 |
| `[警告]` | 存在冲突等异常，安装器会给出原因和路径 |
| `[失败]` | 校验或安装中止，退出码非零 |

安装日志按客户端或项目分组，并在终端实时输出。每组小计和全局总计统一列出新增、更新、删除、保留、跳过和警告。警告也计入跳过。与本仓库无关的入口直接略过，无明细和计数。日志重定向、`TERM=dumb` 或非空 `NO_COLOR` 时以纯文本输出。

安装器用 `.feipi-agent-kit-source` 识别仓库归属。没有标记的旧入口，可通过指向本仓库的链接，或 OpenClaw 的 `.openclaw/source-origin.json` 识别。OpenClaw 记录须匹配仓库身份、技能名及子目录。显式来源记录优先于内部链接，来源不明的旧实拷会保留。

## 新增或维护 Skill

1. 查阅命名、主题归类、测试和注册要求。 [Skill 工程治理](../skills/agent/skills/feipi-skill-govern/SKILL.md)
2. 创建脚手架，替换下方占位参数为实际名称和领域。
3. 运行 Skill 自身测试与注册表回归，最后用一个代表性任务验证结果。

```bash
bash skills/agent/skills/feipi-skill-govern/scripts/init_skill.sh <name> --domain <领域> [--subdomain <子领域>]
bash skills/agent/skills/feipi-skill-govern/scripts/validate.sh <skill-path> --require-maintenance
bash <skill-path>/tests/run.sh
bash scripts/harness/doctor.sh
```

## 接入本地服务

- **LiteLLM** · 使用 `http://127.0.0.1:4000/v1` 作为兼容接口。 [网关与客户端配置](../tools/gateway/litellm/README.md)
- **SearXNG** · 通过 HTTP API 查询搜索结果。 [搜索接口](../tools/search/searxng/README.md)
- **Crawl4AI** · 通过 HTTP API 或内置 MCP 接口提取网页内容。 [Crawl4AI 接入](../tools/crawl/crawl4ai/README.md)

启动顺序和自启设置见 [新 Mac 服务重建](setup-new-mac.md)。服务或 MCP 不可用时，从 [验收与排查](verification/README.md) 查健康端点和日志。Skill 未出现时，先核对安装输出中的客户端、目录和来源，再定点发布并开启新对话。
