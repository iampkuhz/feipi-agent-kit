# Skills Overview

| Skill | 用途 | 特点                                    |
|---|---|---------------------------------------|
| `feipi-skill-govern` | 创建、重构、自检和治理其他 skill | 统一 v2 命名、layer、模板、脚本与验证边界，作为治理总入口 |
| `feipi-patent-generate-innovation-disclosure` | 把零散创新点整理成专利创新交底书 | 先补齐专利名与使用场景，再协同架构图/时序图 skill 产出可校验交底书 |
| `feipi-plantuml-generate-architecture-diagram` | 根据 architecture-brief 生成 PlantUML 架构图 | 先校验 brief，再检查命名覆盖、布局和渲染；把需求定义和画图执行分开 |
| `feipi-plantuml-generate-sequence-diagram` | 根据 sequence-brief 生成 PlantUML 时序图 | 先校验 brief，再检查参与者覆盖、布局和渲染；把需求定义和画图执行分开 |
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

## 版本维护

每个 skill 的版本号独立维护在各自的 `agents/openai.yaml` 顶层 `version` 字段。
后续只要更新某个 skill 本身，就需要先判断该 skill 当天是否已升版：当天首次修改时递增该版本号，同日后续修改保持当天版本。
仓库根目录 `CHANGELOG.md` 仍按日期维护，并在对应日期下按“skill + version”写清合并后的更新内容。
同一天内同一个 skill 只升级一个版本；若当天多次修改，需要汇总到同一条记录中。
changelog 的摘要保持单行短语，建议不超过 18 个汉字、最多不超过 24 个汉字。
