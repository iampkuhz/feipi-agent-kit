# Skill 图标素材库

这里存放 Codex 图标母版。每种图案保留一张方形透明 PNG，现有母版为 256 × 256 px。提交原创图稿或允许随仓库分发的图稿，并保留所需的来源与许可。新建 Skill 默认用 `code.png`。

| Git 内容 | 维护位置 |
| --- | --- |
| Cursor 原生图标名与颜色 | 各 Skill 的 `SKILL.md`。可用名称以[版本化图标表](../../skills/agent/skills/feipi-skill-govern/references/cursor-icon-names.txt)为准 |
| Codex 图像文件 | 本目录。多个 Skill 可以共用同一张图 |
| 图案名称、形状与用途说明、同义词 | `catalog.json`。记录 ID 对应同名 PNG，支持治理 Skill 按用途检索 |
| Skill 选用了哪张 Codex 图 | 各 Skill 的 `agents/openai.yaml`。两个字段都写出 `./assets/<图标 ID>.png` |
| Skill 源码中的图像关联 | `assets/<图标 ID>.png` 是指向图库同名母版的相对符号链接 |

给已有 Skill 换图时，通过图标 `bind` 命令同时更新宿主字段和图像链接。共享母版更新后，指向它的 Skill 会在各自下一次安装时取得更新。如果只想改动其中一个 Skill，另存一张母版并绑定该 Skill。

校验入口会拒绝缺失或越界的链接、仓库 Skill 私存的图标副本、两个宿主字段指向不同路径、以及文件名与母版不一致。`./workbench install skills --agent codex` 会按 YAML 配置复制 PNG，安装副本可以独立搬运。Cursor 原始字体、候选图册、尺寸预览和安装副本都属于工作区产物。完整规则见[治理规范](../../skills/agent/skills/feipi-skill-govern/references/frontmatter-policy.md#skill-图标与宿主适配)。

查找候选、绑定选图和按统一风格绘制新图稿，见[图标维护流程](../../skills/agent/skills/feipi-skill-govern/references/skill-icons.md)。
