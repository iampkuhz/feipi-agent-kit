# 新建 Skill 目录判定

## 默认判定逻辑

| 条件 | 目标路径 |
|------|----------|
| 明确要求“在本仓库内创建” | `skills/<layer>/<skill-name>/` |
| 未特别说明，且仓库存在 `skills/` | `skills/<layer>/<skill-name>/` |
| 当前环境没有仓库级 `skills/` 目录 | `.agents/skills/<skill-name>/` |
| 用户明确给出自定义目标路径 | `<target>/<layer>/<skill-name>/` 或 `<target>/<skill-name>/` |

说明：
- 只要落在 repo 的 `skills/` 根下，`layer` 就是必填。
- 若目标不是 repo 的 `skills/` 根，`layer` 视目标路径是否需要目录分层决定。

## 判定顺序

1. 先确定 `target_name`。
2. 再确定 `target_layer`。
3. 最后再确定目标根目录。

## 入口关系

- 主入口：`bash scripts/init_skill.sh <skill-name> --layer <layer>`
- 包装器：仓库级 `make` 仅包装上述本地脚本。
- `bash scripts/validate.sh <skill-dir>` 使用同一套 layer 判断逻辑。
