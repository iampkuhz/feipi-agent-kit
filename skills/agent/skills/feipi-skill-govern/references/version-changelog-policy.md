# 版本与变更记录策略

## 版本号规则

- 每个 skill 的 `agents/openai.yaml` 必须包含顶层整数 `version` 字段。
- 版本号按 skill 自己维护，不使用仓库统一版本号，按整数递增 `1`。

## 升版时机

- 只要该 skill 自身发生更新（`SKILL.md`、`agents/openai.yaml`、`scripts/`、`references/`、`assets/` 变更且会影响使用/维护/触发），都必须检查当天是否已升版。
- 若目标 skill 明确是 `feipi-skill-govern`，与其直接绑定的共享模板/初始化/校验脚本更新也按该 skill 的一次变更处理。
- 当天首次修改时递增 `version`；若当天已升版，继续沿用当天版本，不重复升版。
- 仅修改仓库级公共文件、未改动任何 skill 自身时，不得顺带提升无关 skill 的版本号。

## CHANGELOG 规则

- 每次更新完成后，必须更新仓库根目录 `CHANGELOG.md`。
- `CHANGELOG.md` 只按日期做二级标题 `## YYYY-MM-DD`，时间倒序（新日期在上）。
- 版本来源是目标 skill 的 `agents/openai.yaml` 顶层 `version` 字段；先递增版本，再写 changelog。
- 被调用来指导流程的 skill 不视为本次目标 skill；除非用户明确要求修改它，否则不得为它升版或补写 changelog。

**极致精简（强制）**：
- 同一天同一个 skill 只允许 **1 条**记录，也只允许升级 **1 次**版本。
- 若当天多次修改，首次修改时升版，后续全部合并到同一条记录，不新增第二条。
- 单条记录只写 **1 行**，冒号后摘要不超过 **24 个汉字**。
- 优先使用 2-3 个结果短语合并表达，如"补强版本规则与摘要约束"。
- 禁止长句、因果链、实现过程或展开句。

推荐结构：
```md
# 变更记录

## YYYY-MM-DD
- <skill-name> v<version>：合并后的更新摘要
```

## README 同步

- 每次更新后，检查 `README.md` 是否需要微调（命令/示例/路径/版本维护说明等变更）。
