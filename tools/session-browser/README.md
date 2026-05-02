# Agent Run Profiler

> 面向本地 Claude Code / Codex 的会话索引与 Token 分析工具

## 快速开始

### 本地运行

```bash
# 安装依赖
pip install jinja2 markdown-it

# 扫描并索引（首次约 8 秒）
./scripts/session-browser.sh scan

# 启动 Web 服务，浏览器打开 http://127.0.0.1:8899
./scripts/session-browser.sh serve
```

### Docker 容器

```bash
# 构建
docker compose -f compose/docker-compose.yml build

# 首次扫描索引
docker compose -f compose/docker-compose.yml run --rm session-browser ./scripts/session-browser.sh scan

# 启动服务
docker compose -f compose/docker-compose.yml up -d
# 浏览器打开 http://localhost:8899
```

容器将 `~/.claude` 和 `~/.codex` 以只读方式挂载，index 持久化在 `./data/index/`。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CLAUDE_DATA_DIR` | `~/.claude` | Claude Code 数据目录 |
| `CODEX_DATA_DIR` | `~/.codex` | Codex 数据目录 |
| `INDEX_DIR` | `~/.cache/agent-session-browser` | 索引存储目录 |
| `SERVER_HOST` | `0.0.0.0` | 服务绑定地址 |
| `SERVER_PORT` | `8899` | 服务端口 |

## 页面

| 页面 | 路径 | 内容 |
|------|------|------|
| Dashboard | `/dashboard` | 紧凑指标卡片、趋势图、项目/会话列表 |
| Projects | `/projects` | 所有项目聚合，含 Cache Read/Write 列 |
| Project | `/projects/{key}` | 项目级统计 + 会话列表 |
| Sessions | `/sessions` | 全局会话列表，支持 Agent/Model/Project 过滤 |
| Session | `/sessions/{agent}/{id}` | 折叠对话轮次、Token 柱状图、Token Profile、Tool 树 |
| Agents | `/agents` | Agent 级统计 |
| Token Glossary | `/glossary` | Token 指标定义与 Provider 映射 |
| Search | `/search?q=` | 按标题、项目、模型搜索 |

## 快捷键

| 键 | 操作 |
|----|------|
| `/` | 聚焦搜索框 |
| `t` | 切换到 Token Profile 标签 |
| `m` | 切换到 Messages 标签 |
| `r` | 切换到 Raw 标签 |
| `Esc` | 折叠所有展开的对话轮次 |

## Token 指标

| 指标 | 说明 |
|------|------|
| **Input Fresh** | 实际新发送的输入 Token（未命中缓存） |
| **Cache Read** | 缓存命中的输入 Token（输入侧读） |
| **Cache Write** | 写入缓存的输入 Token（输入侧写） |
| **Output** | 可见输出 Token |

注意：Cache Read ≠ 输出缓存。`cache_read_input_tokens` 和 `cache_creation_input_tokens` 都是输入侧字段。

## Claude Code 子 Agent 诊断

Claude Code 的父会话文件只记录主会话的 `Agent` 工具调用；子 Agent 内部的真实工具循环会写到同级目录：

```text
~/.claude/projects/<project>/<session-id>/subagents/*.jsonl
```

`session-browser` 会把这些 sidechain 文件合并到父 session 的诊断视图：

- 会话级 `Tools` 包含主会话工具调用和子 Agent 内部工具调用。
- `Tools` 页会用 `Scope` 标记 `main` 或 `subagent`。
- `Rounds` 表新增 `LLM` 列，显示该 round 的主模型调用数和嵌套 Agent 内部模型调用数。
- `Agent` 工具行会显示子 Agent 摘要，包括 `LLM` 调用数、内部工具调用数和工具分布。

LLM 调用数基于 Claude Code JSONL 中唯一 `assistant.message.id` 推断。它能反映已经落盘的模型响应；如果要精确看到 LiteLLM 层的 HTTP 重试、失败状态和未落盘请求，需要后续接入 LiteLLM proxy 日志或数据库作为补充数据源。

## 目录结构

```
tools/session-browser/
├── Dockerfile                      # 容器镜像
├── .dockerignore
├── .gitignore
├── compose/
│   └── docker-compose.yml          # 容器编排
├── env/
│   └── .env.example                # 环境变量模板
├── scripts/
│   └── session-browser.sh          # 启动脚本
├── src/
│   └── session_browser/
│       ├── config.py               # 配置中心（环境变量）
│       ├── cli.py                  # CLI 入口
│       ├── domain/
│       │   ├── models.py           # 数据模型
│       │   └── token_normalizer.py # Token 标准化器
│       ├── sources/
│       │   ├── claude.py           # Claude Code 解析器
│       │   └── codex.py            # Codex 解析器
│       ├── index/
│       │   ├── indexer.py          # SQLite 索引
│       │   └── metrics.py          # 聚合统计
│       └── web/
│           ├── routes.py           # HTTP 服务
│           └── templates/          # Jinja2 模板
├── tests/
│   ├── fixtures/                   # 测试数据
│   ├── test_token_normalizer.py    # Token 标准化测试
│   └── test_title_extraction.py    # 标题提取测试
```

## 隐私

- **只读**：不修改任何原始数据
- **本地**：数据源目录以只读方式挂载
- **脱敏**：敏感字段默认隐藏

## Troubleshooting：orphan `-zsh` 高 CPU

`session-browser` 本身不创建 `zsh`、`zpty`、`pty` 或交互式 shell。启动脚本会用 `exec python3 -m session_browser ...` 替换当前脚本进程，避免额外的父 shell 长期驻留；`stop` 命令只短暂调用 `lsof` 查找端口，并在 timeout 时清理子进程组。

如果 Activity Monitor 中看到高 CPU 的 `-zsh`，可先确认是否为外部 agent/terminal executor 在本目录遗留的 login shell：

```bash
ps -axo pid,ppid,pgid,sess,tty,stat,etime,%cpu,%mem,command \
  | grep -E 'session-browser|python3 -m session_browser|-zsh' \
  | grep -v grep
```

重点看这些信号：

- `COMMAND=-zsh`：login zsh，不是 `python3 -m session_browser`。
- `PPID=1`：原父进程已退出，进程被 `launchd(1)` 收养。
- `TTY=??`：没有真实终端窗口，常见于 agent/executor 创建的伪终端。
- `STAT=R` 或 `U` 且 CPU 高：不是 idle shell。

确认 cwd：

```bash
lsof -a -p <pid> -d cwd
```

检查是否有未回收的 zombie child：

```bash
ps -axo pid,ppid,pgid,stat,etime,%cpu,%mem,command | awk -v p="<pid>" '$2 == p {print}'
```

如果确认目标 PID 是已知的 orphan `-zsh`，可先温和结束指定 PID：

```bash
kill <pid1> <pid2>
sleep 2
ps -ww -p <pid1>,<pid2> -o pid,ppid,stat,etime,%cpu,command
```

若仍未退出，再对同一批已确认 PID 使用：

```bash
kill -9 <pid1> <pid2>
```
