# Frontmatter 规范

## 必需字段

- `name` 为非空字符串，与目录名一致。
- `description` 为非空字符串，以第三人称说明用途和触发，最多 1024 字符。短描述优先保留能区分相邻 Skill 的信息。
- `disable-model-invocation` 显式声明是否禁用自动调用。使用小写、无引号的 YAML 布尔值 `true` 或 `false`，并同步 Codex 的调用策略。
- `icon` 为 Cursor 支持的图标名，必填且区分大小写。每个 Skill 同时提供下述 Codex 图标配置和资源。
- `color` 为 Cursor Custom Mode 徽章颜色，必填且区分大小写。可选 `default`、`green`、`cyan`、`blue`、`purple`、`magenta`、`orange`、`yellow`、`red`、`brand`。
- Frontmatter 使用 `---` 包裹，必需字段仅出现一次，值中避免 XML 标签。

## 调用策略与宿主适配

普通 Skill 默认允许按描述自动匹配，工作模式以用户显式启用为入口。普通 Skill 需要仅手动运行时，也可将两端配置改为对应的一组。

| 用户意图 | `SKILL.md` 的 `disable-model-invocation` | `agents/openai.yaml` 的 `policy.allow_implicit_invocation` |
| --- | --- | --- |
| 允许自动匹配 | `false` | `true` |
| 仅用户显式调用 | `true` | `false` |

| 宿主 | 调用入口与分发 | 图标和颜色 |
| --- | --- | --- |
| Codex | 从 `agents/openai.yaml` 读取 `policy.allow_implicit_invocation`，用 `$skill-name` 显式调用。 [官方文档](https://learn.chatgpt.com/docs/build-skills#optional-metadata) | 读取 `interface.icon_small`、`interface.icon_large`，可选 `interface.brand_color` 使用带引号的六位十六进制颜色。 [官方字段](https://developers.openai.com/plugins/deploy/submission-errors) |
| Claude Code 本地端 | 从 `SKILL.md` 读取 `disable-model-invocation`，用 `/skill-name` 显式调用。 [官方文档](https://code.claude.com/docs/en/skills#control-who-invokes-a-skill) | Skill 字段表没有 Cursor 徽章配置。 [官方字段](https://code.claude.com/docs/en/skills#frontmatter-reference) |
| Claude Code 云端 | 使用 Claude Code 的同一字段。将 Skill 放到云会话实际读取的来源，例如仓库的 `.claude/skills/`。可用 `bash scripts/install_skills.sh --agent claudecode --dir <项目根目录>` 准备项目副本。自托管环境按 runner 配置加载。 [云端加载规则](https://code.claude.com/docs/en/claude-projects#what-threads-pick-up-from-your-repositories) | 沿用 Claude Code Skill 字段。 |
| Cursor | 从 `SKILL.md` 读取 `disable-model-invocation`，用 `/skill-name` 显式调用。 [官方文档](https://cursor.com/docs/skills#disabling-automatic-invocation) | `icon` 和 `color` 用于 Custom Mode 徽章。 [官方字段](https://cursor.com/docs/skills#using-a-skill-as-a-custom-mode) |
| OpenCode v2 | 从 `SKILL.md` 读取 `disable-model-invocation`，用 `@skill-id` 显式加载。可复用工作台的项目级 `.agents/skills/`。若上游设有优先级更高的 `metadata.opencode/autoinvoke`，迁移时核对它与共享字段的行为一致。 [官方文档](https://opencode.ai/docs/skills/) | Skill 字段表没有 Cursor 徽章配置。 |
| VS Code（Copilot） | 从 `SKILL.md` 读取 `disable-model-invocation`，用 `/skill-name` 显式调用。 [官方文档](https://code.visualstudio.com/docs/agent-customization/agent-skills) | Skill 字段表没有 Cursor 徽章配置。 |

治理脚本检查两处 YAML 布尔值、映射位置及一致性。沿真实宿主验证时，在两个新会话发送同一任务意图，其中一次附显式 Skill 调用。检查普通请求的可用 Skill 列表与显式请求的正文注入。仓库安装使用同一份配置，按宿主读取对应字段。

## Skill 图标与宿主适配

- 选图、检查新版 Cursor 和新绘 Codex 图标按[查找、设计与分发](skill-icons.md)执行。选图工具以目录中的图形与用途描述、双语名称和同义词为输入。
- 已登记 Skill 和新增 Skill 都按主要用途选一个可辨认的图形。初始化提供 `code` 和通用图稿，交付前按用途审查并替换需要区分的图稿。
- Cursor 读取 `SKILL.md` 顶层 `icon`。从[仓库校验使用的 Cursor 图标表](cursor-icon-names.txt)选名称。需要较新版本的名称时，按 [官方文档](https://cursor.com/docs/skills#using-a-skill-as-a-custom-mode)或客户端图标表核对并记录来源。可用 `color` 设置 Custom Mode 输入栏徽章颜色。未知名称会回退到闪电图标。
- Codex 的 `interface.icon_small` 和 `interface.icon_large` 都从 Skill 根读取 `./assets/<图标 ID>.png`。一张高分辨率方形 PNG 供两处缩放，设计时检查缩到 16–24 px 后的辨识度。
- 源码的图标文件名与仓库根目录 `assets/skill-icons/` 母版同名，通过相对符号链接引用。多份 Skill 可以绑定同一母版。安装器复制 YAML 指定的图像到 Skill 包内，独立创建的 Skill 也携带本地文件。
- 校验入口检查 Cursor 名称和颜色、Codex 母版与目录的一致性、两个宿主字段、源码关联、安装副本和 PNG 格式。验收时审阅图形是否表达 Skill 用途，分别记录客户端实际显示和元数据、资源读取的证据。

## 扩展字段与迁移

- 共享入口允许可携带的扩展字段。迁移前按固定上游入口逐键登记。默认保留字段及其值、类型和结构。例如 YAML 布尔值 `true` 与字符串 `"true"` 不等价。
- 按用户目标适配 `name` 和 `description`。故意改写或删除其他字段时，记录原值、理由、真实消费者与行为影响。当前宿主没有读取某个字段，仍保留该字段；若某宿主实际拒绝，先在该宿主的读取或分发边界处理并记录实跑证据。
- Registry 只读取 `name`、`description`，安装器按原文件打包。迁移清单登记入口与允许改写的键，核对其余字段从固定上游到候选再到隔离安装包的保留结果。
- 从上游迁移时保留原有自动或手动触发语义，并按上表补齐目标宿主的对应字段。仅手动调用的 Skill 应在 Claude Code 和 VS Code（Copilot）保留 `user-invocable` 的默认值 `true`。

## 示例

```markdown
---
name: skill-name
description: 用第三人称说明用途与触发时机。
disable-model-invocation: true
icon: crown
color: yellow
---
```

`agents/openai.yaml` 的图标字段如下，保留现有 `interface` 的其他字段。

```yaml
interface:
  icon_small: "./assets/skill-govern.png"
  icon_large: "./assets/skill-govern.png"
policy:
  allow_implicit_invocation: false
```
