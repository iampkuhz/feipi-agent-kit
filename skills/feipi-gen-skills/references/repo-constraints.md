# 仓库落地硬约束

## 命名
- 必须符合命名规范，见 `references/naming-conventions.md`。

## Frontmatter 规范
- 仅保留 `name` 与 `description` 两个字段。
- `name` 与目录名一致；具体命名细则见 `references/naming-conventions.md`。
- `description` 非空，使用第三人称，<= 1024 字符。
- Frontmatter 不包含 XML 标签。

## 中文维护
- `SKILL.md` 的 `description` 与正文使用中文。
- `agents/openai.yaml` 的 `display_name`、`short_description`、`default_prompt` 使用中文。
- `references/` 默认中文（如保留英文原文，需附中文摘要）。
- 脚本与配置注释统一中文。

## agents/openai.yaml 版本约束
- 每个 skill 的 `agents/openai.yaml` 必须包含顶层整数 `version` 字段。
- 版本号按 skill 自己维护，不使用仓库统一版本号。
- 只要该 skill 自身发生更新（如 `SKILL.md`、`agents/openai.yaml`、`scripts/`、`references/`、`assets/` 变更且会影响使用、维护或触发），都必须同步递增该 `version`。
- 仅修改仓库级公共文件、且未改动某个 skill 自身时，不得顺带提升无关 skill 的版本号。

## 测试结构约束（开发流程）
- 每个 skill 必须提供统一测试入口：`<skill-root>/<name>/scripts/test.sh`。
- 测试数据默认放在：`<skill-root>/<name>/references/test_cases.txt`。
- 仓库级统一通过 `make test SKILL=<name>` 调度，不依赖非标准脚本名（支持 `skills/` 与 `.agents/skills/`）。
- 上述测试命令仅在创建/修改 skill 的开发流程执行，不写入目标 skill 的 `SKILL.md`。

## 校验约束
- 新建或修改 skill 后，必须执行：`make validate DIR=<skill-root>/<name>`。
- 修改 skill 后，除执行校验外，还必须确认该 skill 的 `agents/openai.yaml` 版本已递增，且 `CHANGELOG.md` 已在对应日期下追加或合并该版本记录。

## 新建 skill 目录判定
- 若用户明确要求“在本仓库内创建新 skill”，目标根目录固定为 `.agents/skills/`。
- 若用户未特别说明，且当前仓库存在 `skills/` 目录，默认根目录为 `skills/`。
- 若用户未特别说明且当前仓库不存在 `skills/` 目录，默认回退到 `.agents/skills/`。
- 开发阶段可使用 `make new SKILL=<name> TARGET=repo|skills|auto` 显式对齐目录策略。

## 使用态与开发流程分离
- 使用态（调用 skill 完成用户任务）：`SKILL.md` 只保留完成任务所需信息（输入、输出、执行步骤、结果校验）。
- 禁止在非 `feipi-gen-skills` 的 `SKILL.md` 中出现仓库维护命令（如 `make test SKILL=...`、`make validate DIR=...`）。
- 开发流程（创建/修改/重构 skill）：执行 `make validate` 与必要的 `make test`，结果记录在开发过程与提交说明中，不沉淀到目标 `SKILL.md`。

## 版本兼容策略
- 每次优化/重构默认所有环境适配最新版，不保留旧版兼容路径或多套读写逻辑。
