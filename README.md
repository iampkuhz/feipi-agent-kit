# Skills Overview

| Skill | 用途 | 特点                                    |
|---|---|---------------------------------------|
| `feipi-gen-skills` | 新建或升级其他 skill | 明确 skill 命名规范，基于 best-practice 生成高质量的 skills |
| `feipi-gen-plantuml-code` | 根据指令生成 PlantUML 并自动校验语法 | 本地 server 优先，失败自动回退公网；内置宽度/布局约束与分类型 reference |
| `feipi-read-youtube-video` | 下载 YouTube 视频或提取音频 | 支持下视频或只拿音频                            |

## 安装 Skill（最简单）

在仓库根目录执行：

```bash
make install-links
```

这会把 `skills/` 下的技能以软链接方式安装到目标目录（默认 `~/.agents/skills`）。
如果 skill 脚本里通过 `$REPO_ROOT/...` 引用了仓库共享路径（例如 `feipi-scripts/video/*`），安装时也会自动在目标根目录补齐对应软链接（例如 `~/.codex/feipi-scripts`）。

可选示例：

```bash
AGENT=qwen make install-links
AGENT=qoder make install-links
AGENT=openclaw make install-links
```

默认目录映射：

codex -> `$CODEX_HOME/skills`（未设置时为 `~/.codex/skills`）
qwen -> `~/.qwen/skills`
qoder -> `~/.qoder/skills`
claudecode -> `~/.claude/skills`
openclaw -> `$OPENCLAW_HOME/skills`（未设置时为 `~/.openclaw/skills`）
未设置 AGENT -> `~/.agents/skills`

## 安装 Skill（拷贝到项目目录）

在仓库根目录执行：

```bash
make install-project PROJECT=/path/to/project
```

这会把 `skills/` 下的技能以“实际拷贝”的方式安装到项目目录（默认 `<project>/.agents/skills`），并覆盖同名 skill。
如果 skill 脚本里通过 `$REPO_ROOT/...` 引用了仓库共享路径（例如 `feipi-scripts/video/*`），安装时也会复制到项目根目录下对应位置。

可选示例：

```bash
AGENT=qwen make install-project PROJECT=/path/to/project
```

默认目录映射：

codex -> `<project>/.codex/skills`
qwen -> `<project>/.qwen/skills`
qoder -> `<project>/.qoder/skills`
coder -> `<project>/.coder/skills`
claudecode -> `<project>/.claude/skills`
openclaw -> `<project>/.openclaw/skills`
未设置 AGENT -> `<project>/.agents/skills`

## 统一环境变量

本仓库所有技能的环境变量模板统一维护在仓库根目录：

```bash
./.env.example
```

后续新增或修改环境变量时，统一更新此文件，不再按 skill 分散维护。
