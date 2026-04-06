# 仓库落地硬约束

## 结构边界

- 便携最小结构只要求 `SKILL.md`。
- 本仓库内交付的 skill 默认要求：
  - `SKILL.md`
  - `agents/openai.yaml`
  - `scripts/test.sh`
- `references/`、`assets/`、`templates/` 按需存在；没有复用价值时不要硬加目录。

## 命名与目录

- 命名真源见 `references/naming-conventions.md`。
- repo 内 `skills/` 目录下的 skill 必须位于 `skills/<layer>/<skill-name>/`。
- layer 规则见 `references/skill-layering-policy.md`。
- `feipi-skill-govern` 是唯一允许保留三段式名称的特例。

## 触发与执行一致性

- frontmatter `description`、`agents/openai.yaml`、`SKILL.md` 不能互相冲突。
- 触发说明必须同时回答：做什么、什么时候用、什么时候别用。
- 治理型 skill 必须明确“仅用于 skill 工程任务”，避免误触发到普通业务场景。

## 边界控制

- 默认只修改目标 skill 与直接共享文件。
- 发现其他 skill 问题时，只能记录到待重审清单。
- 非 `feipi-skill-govern` 的 `SKILL.md` 禁止沉淀仓库维护命令。

## 初始化与脚本归位

- 当前 skill 的核心流程必须可通过本地 `scripts/` 闭环执行。
- 仓库级 `make` 或共享脚本只能作为包装器，不能成为唯一真入口。
- 调整目录、初始化、模板或校验规则时，必须同步检查：
  - 当前 skill 的 `scripts/`
  - 当前 skill 的 `templates/`
  - 直接引用这些规则的 `references/`

## 验证约束

- 修改后必须完成结构校验。
- 除结构校验外，还必须完成至少一种行为校验。
- 若改了模板或初始化脚本，必须生成临时 skill 验证产物。
- 必须完成旧规则残留搜索，确认未继续传播旧命名真源。
- 需写清哪些命令在仓库根执行，哪些命令在 skill 目录执行。

## 环境变量

- 环境变量模板只维护在仓库根目录 `.env.example`。
- 优先通过参数或自动探测解决；确需新增环境变量时，再同步更新根目录 `.env.example` 与对应说明。
