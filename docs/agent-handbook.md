# Agent 操作手册

> 常用命令、服务管理、故障排查的完整参考。

## Skills 管理

```bash
# 安装 skills（入口实拷、运行目录链接，排除 tests/evals）
make install-links

# 查看逐项跳过/保留原因、注册表验证详情
make install-links VERBOSE=1

# 强制彩色（如支持 ANSI 的日志查看器）；纯文本使用 COLOR=never
make install-links COLOR=always

# 安装到项目目录
make install-project PROJECT=/path/to/project

# 初始化新 skill
bash skills/authoring/feipi-skill-govern/scripts/init_skill.sh <name> --layer <layer>

# 校验 skill
bash skills/authoring/feipi-skill-govern/scripts/validate.sh <skill-path>

# 执行技能测试
bash <skill-path>/tests/run.sh
```

再次运行 `make install-links` 会按当前技能列表同步清理本仓库因源码删除、改名或退役留下的旧入口。请先同步 `skills/registry.yaml`；注册表校验失败时不会安装或清理。

安装器在每个 skill 目录写入 `.feipi-agent-kit-source` 来源标记，链接与实拷模式均适用。旧版未标记的安装通过指向本仓库的顶层链接，或指向同一源码 skill 的内部资源链接识别；相对链接按所在目录解析。清理时保留其他来源的 skill（包括失效链接）。

OpenClaw 原生 Git 安装的纯拷贝通过 `.openclaw/source-origin.json` 确认归属：Git 仓库地址必须与本仓库 `origin` 一致，`slug` 必须与入口目录名一致，`subdirectory` 必须是 `skills/` 下对应的技能路径。HTTPS 与 SSH 地址按仓库身份匹配。其他仓库、损坏或不匹配的来源记录均保留；显式来源标记或 OpenClaw 记录优先于内部链接证据。没有任何来源或链接证据的旧版纯实拷目录仍保留。

重复安装会比较过滤后的文件类型、权限、文件内容和链接目标；内容一致时计入跳过，保留现有目录和文件。变化的入口或纯拷贝资源会更新，错误链接会修复。链接模式的运行目录变化直接随源码生效，开发目录 `tests/`、`evals/` 不参与安装比较，其脚本引用的共享路径也不安装。安装失败会中止，不计入跳过。

安装输出按 agent/项目分组，目标路径与安装模式只显示一次。默认逐项显示变更、清理删除和警告，未变更的技能及保留的其他来源入口只汇总数量；`VERBOSE=1` 展开逐项名称、跳过/保留原因和验证详情。共享路径以 `共享/` 标识，计入安装小计和总计。

| 标记 | 终端样式 | 含义 |
|------|----------|------|
| `[新增]` | 绿色粗体 | 目标原先不存在，安装成功 |
| `[更新]` | 蓝色粗体 | 已有内容变化、链接迁移或修复成功 |
| `[跳过]` | 弱化显示 | 内容或链接未变，仅详细模式逐项显示 |
| `[清理]` | 删除项黄色粗体 | 已删除本仓库旧入口；清理计数独立列出 |
| `[保留]` | 弱化显示 | 其他来源或无法确认归属，仅详细模式逐项显示 |
| `[警告]` | 黄色粗体 | 冲突等导致跳过，默认也显示原因与路径 |
| `[失败]` | 红色粗体 | 验证或安装失败，中止并返回非零状态 |

每个目标显示小计，末尾分别汇总新增、更新、跳过和警告。警告数量是跳过中的异常项数量，不重复计入安装项数；清理的移除/保留数量不参与安装总计。输出即时写入控制台，失败时保留此前完成的日志，不打印成功总计。

`COLOR=auto` 为默认值，仅在终端且 `TERM` 不是 `dumb` 时启用颜色、粗体和弱化样式；管道或日志重定向默认使用纯文本。`COLOR=always` 强制启用，`COLOR=never` 禁用；非空 `NO_COLOR` 优先禁用所有样式。状态文字始终保留，颜色不影响结果识别。这些选项也适用于 `make install` 和 `make install-project`；直接运行脚本时使用 `--verbose`、`--color auto|always|never`。

输出回归测试：`python3 -m unittest discover -s tests -p 'test_install_output.py'`；完整安装、来源清理和目录过滤验证：`make harness-doctor`。测试使用临时安装目录。

## 服务管理

### LiteLLM

```bash
make litellm-up          # 启动
make litellm-down        # 停止
make litellm-restart     # 重启
```

### SearXNG

```bash
make searxng-up          # 启动
make searxng-down        # 停止
make searxng-restart     # 重启
```

### SearXNG MCP [已退役]

> SearXNG MCP 服务（`tools/search/searxng-mcp/`）已于 2026-05 移除。如需网页搜索能力，请使用 Crawl4AI MCP。

## 仓库维护

```bash
# 初始化设置
./scripts/bootstrap/setup.sh

# 健康检查
./scripts/doctor/check.sh
```

## 服务接入指南

### Claude Code 使用 SearXNG MCP [已退役]

> SearXNG MCP 已移除。如需网页搜索能力，请使用 Crawl4AI MCP（`tools/crawl/crawl4ai/`）。

### 使用 LiteLLM 作为模型网关

1. 启动服务：`make litellm-up`
2. 客户端通过 `http://127.0.0.1:4000/v1` 访问

## 故障排查

### 服务无法启动

1. 检查端口占用：`lsof -i :<port>`
2. 查看日志：`docker compose logs`
3. 验证配置：检查 `env/` 和 `compose/` 文件

### MCP 服务不可用

1. 检查基础服务：`curl http://localhost:8873/healthz`
2. 检查 MCP 进程
3. 验证 Claude Code MCP 配置

### Skill 无法使用

1. 检查安装：`ls ~/.claude/skills/`
2. 检查入口文件权限和运行目录链接
3. 重新安装：`make install-links`
