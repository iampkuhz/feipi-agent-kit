# Skill 主题归类

先确定用户要处理的主要对象，再查目标仓库 `skills/registry.yaml` 的已有归类。按对象选择更容易找到它的一级领域。只有主题可以收窄且子目录有导航价值时，才增加一个子领域。横跨子领域或归属尚未明确的 Skill 直接放在一级领域。工作流、验证及角色是运行契约，可在 Skill 内说明。

## 当前目录

| 领域 | 子领域与示例 |
| --- | --- |
| `agent/` | `skills/` 放处理 Skill 本身的 `feipi-skill-govern`。 |
| `content/` | `writing/` 收文字精炼，`presentations/` 收演示文稿单页重构，`delivery/` 收交付审查。 |
| `diagram/` | draw.io、Mermaid、PlantUML 通用图表 Skill 直接放领域根。 |
| `media/` | `video/` 放视频提取，`notes/` 放小红书笔记读取。 |
| `collaboration/` | Multica 项目、任务和交接协作。 |
| `health/` | 家庭健康记录维护。 |

例如 `skills/content/writing/feipi-writing-refine-text/` 方便按文字对象找到精炼能力。若新增同时服务文字、演示和交付的内容能力，先放 `skills/content/<Skill ID>/`。遇到新对象先核对现有领域能否清楚容纳，合适的新领域用简洁的主题名称。

## 源码、索引与安装

- 源码使用 `skills/<领域>/<Skill ID>/` 或 `skills/<领域>/<子领域>/<Skill ID>/`。Skill 命名见 [命名规范](naming-conventions.md)。
- 初始化用 `--domain`，需要子领域时另给 `--subdomain`。分类用小写 kebab-case。
- `skills/registry.yaml` 仅列仓库相对目录路径。固定入口为 `SKILL.md`，名称和 Description 读 frontmatter，分类由目录推导。仓库校验以索引与实际入口一致为前提。
- 安装按现有 Skill ID 平铺。源码改分类时保留已有调用 ID，同步实际路径调用者，检查现有受管链接并验证隔离重装后的保留和迁移行为。
