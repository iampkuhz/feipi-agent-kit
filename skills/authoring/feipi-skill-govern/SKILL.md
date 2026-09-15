---
name: feipi-skill-govern
description: 用于治理 repo 内 skill 的命名、触发、执行、模板、脚本与验证边界；在创建、重构、自检或审计 skill 时使用。若任务是普通业务执行而非 skill 工程，不要误用本 skill。
---

# Skill 工程治理（中文）

## 核心目标

- 让 `feipi-skill-govern` 成为后续 skill 治理的唯一正确入口，先修规则真源，再修脚本、模板与验证闭环。
- 输出必须可追溯：问题清单、修复清单、验证结果、剩余风险、待重审项缺一不可。
- 默认只治理目标 skill 与直接共享文件，不把发现的所有问题捆成一次无边界大动作。

## 适用场景

- 新建 repo 内 skill，并确定 `domain -> action -> object -> layer`。
- 重构已有 skill 的命名、layer、触发文案、执行流程、模板、脚本或验证方式。
- 审计某个 skill 或 `feipi-skill-govern` 自身，清理旧规则、旧模板、旧校验残留。
- 产出 Step 1、Step 1.5、Step 2 报告、rename plan、governance report 与待重审清单。

## 不适用场景

- 普通业务任务、代码开发、数据处理或内容生成，本次目标不是治理 skill。
- 仅使用某个 skill 完成一次用户需求，而不是创建、重构或审计 skill 本身。
- 发现其他 skill 也有问题时顺手大范围改名；此时只记录到待重审清单。

## 先确认什么

1. 必填
- `target_skill`：本次要治理的唯一目标 skill，或新建 skill 的目标能力。
- `task_type`：`create` / `refactor` / `govern` / `self-audit`。
- `success_criteria`：本次要消除的失真点，例如旧命名、误触发、模板漂移、验证不闭环。

2. 按需确认
- `allowed_shared_files`：允许同步修改的共享文件；默认仅限确实共享的仓库根文件，如 `.env.example`、`README.md`、`CHANGELOG.md`。目标 skill 自己的 `templates/`、`scripts/`、`references/`、`assets/` 属于本地资源，不应继续挂在仓库公共目录。
- `current_name` / `current_layer`：已有 skill 的当前名称与目录位置。
- `validation_env`：是否能运行本地脚本、临时目录初始化、dry-run 校验。

## 输入与输出

1. 输入
- 用户目标、目标 skill 路径或名称、已知问题、历史 rename 结论。
- 现有 `SKILL.md`、`agents/openai.yaml`、`references/`、`scripts/`、`assets/`、`templates/`。

2. 输出
- 问题清单：哪些文件残留旧规则、违反了什么。
- 修复结果：改了什么、为什么这样改、边界控制在哪里。
- 验证结果：主验证入口、执行命令、通过/失败、剩余风险。
- 治理产物：Step 1 / Step 1.5 / Step 2 / Step 3 的临时工作文档、待重审清单。

## 决策顺序

1. 先判断本次是不是治理型任务；若不是，不触发本 skill。
2. 锁定唯一目标 skill 与允许改动的直接共享文件。
3. 若涉及命名或归位，严格按 `domain -> action -> object -> layer` 决策。
4. 判断问题落在哪层：触发层、执行层、资源层、脚本归位层、验证层。
5. 只改最小有效改动集；发现其他 skill 问题只登记，不扩散执行。
6. 完成本地验证、旧规则残留搜索、版本与变更记录同步，再关闭。

## 默认策略

- 默认只改一个目标 skill；只有目标就是 `feipi-skill-govern` 时，才允许同时改它自己的 `references/`、`scripts/`、`assets/`、`templates/` 与直接关联入口文件。
- `feipi-skill-govern` 是治理型 skill，不是普通业务 skill；触发说明必须写清“什么时候该用、什么时候不该用”。
- 命名真源统一是 `feipi-<domain>-<action>-<object...>`，`feipi-skill-govern` 是保留特例。
- layer 只负责目录分层，不进入 skill 主语法，不为单个 skill 临时发明新 layer。
- 仓库级脚本或 `make` 只能作为包装器；主流程必须可通过当前 skill 本地脚本闭环执行。
- 仓库根目录不再保留给多个 skill 兜底的公共 `templates/`；模板要么放在 `feipi-skill-govern/templates/`，要么放在目标 skill 自己的 `templates/` 或 `assets/`。
- 若发现历史 rename 建议是按旧规则得出的，只记录到待重审清单，不在本次顺手重命名其他 skills。
- 运行内容与开发内容分层：普通 skill 的 `SKILL.md` 不引用 `tests/` 或 `evals/`；只有本 Skill Creator 在创建、维护、评估或审计 skill 时读取这些目录。
- `tests/` 保存确定性脚本测试、集成测试和 fixtures，统一入口为 `tests/run.sh`；`evals/` 保存真实 Agent 行为用例、判定标准和基线，不保存运行产物。
- `tests/`、`evals/` 都是源码维护目录，安装器必须排除；评估输出写入仓库 `tmp/`，不能回流到 skill。
- 创建或迁移开发资料时按需读取 `references/development-layout.md`。

## 执行流程（治理态）

1. Step 1：基线审计
- 读取目标 skill 的入口文件和直接资源。
- 产出问题清单，标记命名、layer、触发、执行、资源、脚本归位、验证七类状态。
- 产物必须写到仓库根 `tmp/` 或系统临时目录，不得写回 skill 内部目录。

2. Step 1.5：命名与归位评审
- 只有涉及命名、layer 或路径时进入此步。
- 先定 `target_domain`，再定 `target_action`，再定 `target_object`，最后定 `target_layer`。
- 产出 rename review 与 rename plan 草稿；统一放到仓库根 `tmp/` 或系统临时目录。

3. Step 2：定点修复
- 只修改目标 skill 与直接共享文件。
- 同步修触发配置、`SKILL.md`、`references/`、`scripts/`、`assets/`、`templates/` 的一致性。
- 若发现仓库根目录残留的公共模板或运行时脚本，优先迁回目标 skill 内部；无法证明仍被现役 skill 使用时，直接删除。
- Step 2 检查清单属于临时执行文档，只能写到 `tmp/` 或系统临时目录。

4. Step 3：验证与收口
- 先做结构校验，再做行为校验，再做旧规则残留搜索。
- 输出 governance report、validation status 与待重审清单。
- governance report 属于临时治理文档，不得沉淀回当前 skill。

## 失败处理

- 缺少 `target_skill` 或边界不清时，默认收敛到用户明确点名的唯一目标 skill。
- 若共享文件变更会影响无关 skills，先停下来缩小范围或把影响写入风险，不直接扩散执行。
- 若本地脚本无法验证，必须明确阻塞点、受影响环节与未验证风险。
- 若发现旧命名结论已污染后续步骤，暂停后续步骤，从 Step 1 重新建立基线。

## 资源导航

- `references/naming-conventions.md`：命名规范 v2 与命名决策顺序。
- `references/skill-layering-policy.md`：layer 的职责、边界与禁忌（含目录判定）。
- `references/workflow.md`：执行顺序、边界、失败处理、验证矩阵。
- `references/governance-process.md`：Step 1 / Step 1.5 / Step 2 / Step 3 的治理流程（含产物落位）。
- `references/version-changelog-policy.md`：版本号递增与 CHANGELOG 极简记录规则。
- `references/quality-checklist.md`：交付前核查清单。
- `references/reassessment-backlog.md`：既有治理结论待重审清单。
- 其他规则见 `references/repo-constraints.md`、`references/frontmatter-policy.md`、`references/anti-patterns.md`。

## 语言与中文要求

- `SKILL.md` 的 `description` 与正文使用中文。
- `agents/openai.yaml` 的 `display_name`、`short_description`、`default_prompt` 使用中文。
- `references/` 默认中文；脚本与配置注释统一中文。
- 技术术语可保留英文，但需附中文解释。详见 `rules/global/language.md`。

## 历史来源说明

当前规则真源以仓库 `AGENTS.md` 与本 skill 自身文档、脚本、模板为准。历史参考资料（OpenAI skill-creator、Claude Code Best Practices、`feipi-gen-skills` 旧规则）只提供背景，不替代当前规则真源。若旧文档仍提到 `feipi-gen-skills`、action-first 命名或历史 rename 结论，以本 skill 当前 v2 规则为准。

## 主入口与包装器

1. 当前 skill 目录执行
```bash
bash scripts/validate.sh .
bash tests/run.sh
```

2. 仓库根目录执行
```bash
bash skills/authoring/feipi-skill-govern/scripts/validate.sh skills/authoring/feipi-skill-govern
bash skills/authoring/feipi-skill-govern/scripts/init_skill.sh feipi-video-read-youtube --layer integration
```

说明：
- `scripts/validate.sh` 是结构校验主入口。
- `tests/run.sh` 是开发回归与旧规则残留搜索入口。
- `scripts/init_skill.sh` 是新建 skill 的本地脚手架入口；仓库级 `make` 只可作为包装器，不是唯一真源。

## 验收标准

1. 命名、layer、触发、执行、资源、脚本归位、验证七类规则与模板一致。
2. 仅修改目标 skill 与直接共享文件，无无边界扩散。
3. 本地验证、dry-run 或临时产物验证至少完成一条真实动作链。
4. 已输出问题清单、修复清单、规则摘要、待重审清单与重启建议。
