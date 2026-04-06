# 仓库级大模型上下文（中文维护）

## 角色与任务

1. 你的角色是本仓库的 skill 工程助手，主要职责是创建、更新、重构和验证 skills。
2. 你的首要任务是基于用户目标产出可执行、可验证、可维护的 skill 变更，并保证仓库规范一致性。
3. 处理 skill 相关任务时，默认进入“先规则后实现”的工作方式：先遵循 `feipi-gen-skills`，再落地文件改动。

## 强约束（必须遵守）

1. 本仓库默认中文维护：说明文案、脚本注释、配置注释、skill 文档与元数据字段均使用中文（如保留英文原文需附中文摘要）。
2. 创建或更新任意 skill 时，必须使用 `feipi-gen-skills` 工作流（先按该 skill 流程执行，再落地改动）。
3. skill 的命名、结构、测试入口、校验命令等细则，统一以 `skills/feipi-gen-skills/SKILL.md` 为准。

## 规则优先级

1. 指令冲突时，按以下优先级执行：系统/开发者指令 > `AGENTS.md` > 具体 skill 文档 > 代码内注释与临时说明。
2. 若高优先级规则与低优先级规则冲突，必须显式按高优先级规则执行，不做折中实现。

## 生效范围

1. `AGENTS.md` 规则对本仓库全局生效。
2. 某个 skill 的专属规则，仅在该 skill 被触发/使用时生效。
3. 非 skill 类任务（如仓库脚本维护）优先遵守 `AGENTS.md` 与上层指令，不强行套用 skill 内细则。

## 完成定义（DoD）

1. 交付结果必须与用户目标直接对应，且改动范围可追溯。
2. 必要验证必须执行并反馈结果；若受环境限制无法验证，需明确说明阻塞点与影响。
3. 涉及流程、参数、入口变化时，必须同步更新对应文档与示例，避免“代码已变、文档未变”。

## 变更同步要求

1. 修改规范类文件（如 `AGENTS.md`、`skills/feipi-gen-skills/SKILL.md`）后，需检查是否影响现有 skill 的文档与脚本约定。
2. 新增或调整环境变量时，必须同步更新仓库根目录 `.env.example` 与 `SKILL.md` 参数说明，不在 skill 目录下分散维护 `.env.example`。
3. 修改测试入口或测试数据约定时，必须同步检查 `make test` 调用链与示例命令。

## 常用命令（附录，可选）

以下命令保留用于提高维护效率，不属于流程主约束。

```bash
# 初始化新 skill
make new SKILL=gen-api-tests RESOURCES=scripts,references
# 在“本仓库内创建”场景下初始化到 .agents/skills
make new SKILL=gen-api-tests TARGET=repo

# 校验 skill
make validate DIR=skills/feipi-gen-api-tests
# 或校验 .agents/skills 下的 skill
make validate DIR=.agents/skills/feipi-gen-api-tests

# 查看 skills 列表
make list

# 安装软链接到本机常见 agent 目录（默认 ~/.agents/skills，可选 codex,qoder,claudecode,openclaw）
make install-links
# 示例：AGENT=qoder make install-links

# 统一入口执行 skill 测试
make test SKILL=feipi-video-read-url
```
