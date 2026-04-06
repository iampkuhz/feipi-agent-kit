---
name: feipi-skill-govern
description: 按仓库规范创建、重构、治理 skill，并同步脚手架、校验与版本记录。
---

# Skill 工程治理（中文）

## 核心目标

- 让目标 skill 更容易被正确触发、更容易稳定产出、更容易验证，而不只是在目录上"看起来规范"。
- 以最小改动修复触发边界、执行流程、模板脚手架、验证入口和版本记录之间的不一致。
- 交付可追溯：说明改了什么、为什么改、怎么验证、还有什么风险。

## 适用场景

- 新建 repo 内 skill，并补齐脚手架、元数据与统一测试入口。
- 重构已有 skill 的 `description`、`SKILL.md`、`references/`、`scripts/`、`assets/`。
- 修复"会触发但做不对""不会触发/乱触发""模板和规范互相打架""验证失真"等问题。
- 调整 skill 维护约定，并同步到直接关联的共享脚本、模板与文档。
- **治理其他 skills**：使用本 skill 作为总入口，批量治理仓库内的其他 skills。

## 不适用场景

- 普通业务代码开发、缺陷修复或仓库脚本维护，但任务本身与 skill 工作流无关。
- 仅使用某个 skill 完成一次用户任务，而不是创建或优化 skill 本身。
- 只想讨论创意方向、暂不落地文件改动的纯脑暴场景。

## 先判断问题落在哪一层

1. **触发层**：`description`、`short_description`、`default_prompt` 是否准确描述"做什么、什么时候用、什么时候别用"。
2. **执行层**：`SKILL.md` 是否明确输入、输出、默认策略、失败处理和验证方式。
3. **资源层**：`references/` 是否按需拆分，`scripts/` / `assets/` 是否真正复用，而不是复制粘贴。
4. **脚手架层**：初始化模板、目录标准、共享脚本是否与规约一致，能否生成可通过校验的骨架。
5. **验证层**：校验与测试是否同时覆盖结构正确性和行为正确性，而不是只搜关键词。

## 默认交付要求

- 优先给出一个最小但完整的可执行方案，不把维护者留在"规则很多但不知道先改哪里"。
- 若用户只点名一个目标 skill，默认只改该 skill 与直接关联的共享文件；不顺手扩散到其他 skill。
- 若目标就是 `feipi-skill-govern`，允许同时改它自己的 `references/`、`scripts/`，以及直接关联的共享模板/脚本。
- 只要改动影响初始化、校验、版本或文档入口，就要同步检查 `templates/`、共享脚本、`CHANGELOG.md`，必要时补查 `README.md`。

## 决策顺序

1. 先修会直接影响效果的问题：误触发、漏触发、默认策略错误、模板产出不合规、验证失真。
2. 再修会放大维护成本的问题：重复规则、入口不一致、目录拆分过细但缺少导航。
3. 最后再做纯文案整理，避免"改了很多字，但行为没有更稳"。

## 仓库落地结构

### 便携最小结构

- `SKILL.md`：skill 的入口说明与执行规则。

### 本仓库交付结构

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/test.sh`
- `references/`：按需存在，放长规则、样例和清单。
- `scripts/`：放确定性脚本；若修改初始化或校验逻辑，优先脚本化。
- `assets/`：放模板或静态资源；只有真的被初始化或输出流程复用时才新增。
- `templates/`：放初始化模板（若 skill 有初始化其他 skill 的职责）。

## 执行流程（开发态摘要）

1. **Explore**：锁定目标 skill、用户想达成的效果、当前失真点和直接关联的共享文件。
2. **Plan**：列出要改的文件，并写清每个文件是在修触发、修流程、修模板、修验证还是修版本同步。
3. **Implement**：先改最能影响结果稳定性的层，再补文档与导航；若引入新入口，必须同步旧入口或明确废弃。
4. **Verify**：默认执行 `bash scripts/validate.sh <skill-dir>`；若目标 skill 有统一测试入口，再执行 `bash scripts/test.sh` 或等价脚本；涉及初始化模板时，至少生成一个临时 skill 并验证生成结果。
5. **Iterate**：根据失败样例、误触发/漏触发案例和维护成本继续收敛，而不是凭感觉扩写规则。
6. **Close**：更新目标 skill 版本与 `CHANGELOG.md`；入口命令或维护说明变化时，补查 `README.md`。

详细执行细节见 `references/workflow.md`。

## 何时改哪个文件

- `description` / `agents/openai.yaml`：
  当问题主要是不会触发、乱触发、默认提示偏离目标时优先改这里。
- `SKILL.md`：
  当问题主要是输入输出不清、步骤顺序混乱、默认策略缺失、失败处理不完整时优先改这里。
- `references/`：
  当正文太长、规则需要复用、反模式或清单需要独立维护时再下沉。
- `scripts/` / `assets/`：
  当动作稳定、重复、可判定，或需要让初始化、校验、测试变成可复用流程时优先落这里。
- `templates/`：
  当共享脚手架和 skill 规约不一致，或本 skill 依赖共享实现时同步修这里。

## 规则索引

- `references/repo-constraints.md`：仓库落地硬约束与结构边界。
- `references/naming-conventions.md`：命名规范与 action 字典。
- `references/frontmatter-policy.md`：frontmatter 约束。
- `references/chinese-policy.md`：中文维护要求。
- `references/version-policy.md`：版本与兼容策略。
- `references/skill-directory-policy.md`：新建 skill 目录判定。
- `references/workflow.md`：工作流、改动优先级与验证策略。
- `references/anti-patterns.md`：常见失真与修复方式。
- `references/changelog-policy.md`：版本记录与 README 同步规则。
- `references/quality-checklist.md`：交付前核查清单。
- `references/sources.md`：来源说明。
- `references/skill-layering-policy.md`：skills 分层规则。
- `references/governance-process.md`：第二阶段治理其他 skills 的流程。

## 常用命令

```bash
# 新建 skill（本地脚本是标准入口）
bash scripts/init_skill.sh <name> [resources] [target]

# 校验单个 skill
bash scripts/validate.sh <skill-dir>

# 执行统一测试入口
bash scripts/test.sh
```

**说明**：
- 本地脚本是唯一真源，仓库级 `make` 只是可选包装器。
- 本 skill 不依赖仓库级 Makefile 也能独立运行。
- 生成目标 skill 默认放在 `skills/<layer>/` 下，layer 判定见 `references/skill-layering-policy.md`。

## 第二阶段：治理其他 skills

若使用本 skill 去治理其他 skills，见 `references/governance-process.md`。

核心流程：
1. 分析目标 skill 的问题（使用 `validate.sh`）
2. 迁移共享脚本到 skill 本地
3. 更新目标 skill 的文档和配置
4. 执行验证确保独立运行
5. 更新版本和 changelog

## 分层规则

skills 目录必须分层，不能平铺。当前采用以下层：

- `authoring/`：技能创作与治理（本 skill 所在层）
- `diagram/`：图表生成
- `integration/`：外部服务集成
- `platform/`：平台/工具链集成

详细分层规则见 `references/skill-layering-policy.md`。
