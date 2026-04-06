# 仓库落地硬约束

## 结构边界
- 便携最小结构只要求 `SKILL.md`。
- 本仓库内可交付的 skill 默认要求：
  - `SKILL.md`
  - `agents/openai.yaml`
  - `scripts/test.sh`
- `references/`、`assets/` 按需增加；只有真的承担长规则、模板或静态资源时才新增。

## 命名
- 必须符合命名规范，见 `references/naming-conventions.md`。

## Frontmatter 规范
- 见 `references/frontmatter-policy.md`。

## 中文维护
- 见 `references/chinese-policy.md`。

## 版本约束
- 见 `references/version-policy.md`。

## 触发与执行一致性
- `description`、`agents/openai.yaml` 和 `SKILL.md` 不能互相冲突。
- `description` 至少回答两件事：做什么、什么时候该用。
- 非 `feipi-skill-govern` 的 `SKILL.md` 禁止出现仓库维护命令（如 `make validate`、`make test`）。
- 模板产物不得残留 `{{...}}` 之类未替换占位符。

## 校验约束
- 新建或修改 skill 后，必须执行：`bash scripts/validate.sh <skill-dir>` 或等价 wrapper。
- 修改 skill 后，除结构校验外，还必须完成至少一种任务级验证。
- 若修改了初始化模板或初始化脚本，必须生成一个临时 skill 并验证产物。
- 修改 skill 后，还必须确认版本处理符合 `references/version-policy.md`。

## 新建 skill 目录判定
- 见 `references/skill-directory-policy.md`。

## 使用态与开发流程分离
- 使用态（调用 skill 完成用户任务）：`SKILL.md` 只保留完成任务所需信息（输入、输出、执行步骤、结果校验）。
- 禁止在非 `feipi-skill-govern` 的 `SKILL.md` 中出现仓库维护命令。
- 开发流程（创建/修改/重构 skill）：执行 `validate` 与必要的 `test`，结果记录在开发过程与提交说明中，不沉淀到目标 `SKILL.md`。

## 分层规则
- skills 目录必须分层，不能平铺。
- 当前采用层：`authoring/`、`diagram/`、`integration/`、`platform/`。
- 详细规则见 `references/skill-layering-policy.md`。

## 初始化与共享脚本同步
- 只要调整了目录标准、初始化逻辑、测试入口或校验规则，就要同步检查：
  - `templates/`
  - 当前 skill 本地的 `scripts/` 和 `templates/`
- 不允许 skill 文档一套说法、模板产物另一套结果。
- 每个 skill 应独立运行，不依赖仓库级共享脚本。

## 环境变量
- 环境变量模板只维护在仓库根目录 `.env.example`。
- 创建或优化 skill 时，优先通过参数或自动探测解决；确需新增环境变量时，再同步更新根目录 `.env.example` 与对应说明。

## 版本兼容策略
- 见 `references/version-policy.md`。
