# 新建 Skill 目录判定

## 目录选择逻辑

| 用户要求 | 目标根目录 |
|----------|-----------|
| "在本仓库内创建新 skill" | `.agents/skills/` |
| 未特别说明，当前仓库存在 `skills/` | `skills/<layer>/` |
| 未特别说明，当前仓库不存在 `skills/` | `.agents/skills/` |

## 默认策略

- 优先 `skills/`（若存在），并按 `references/skill-layering-policy.md` 判定 layer。
- 回退 `.agents/skills/`（若 `skills/` 不存在）。
- `make new` 与 `bash skills/authoring/feipi-skill-govern/scripts/init_skill.sh` 采用同一套目录判定逻辑。
