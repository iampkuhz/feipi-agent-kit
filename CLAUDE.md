# Feipi Agent Kit

统一个人工作台与 AI 工程助手仓库。日常入口 `./workbench`，研发入口 `./develop`；组件与私有边界见 `AGENTS.md` 和 `docs/workbench.md`。

## 强约束

1. **中文优先**：面向用户输出默认简体中文。详见 `rules/global/language.md`。
2. **规则先行**：先遵循 `rules/` 和 `skills/authoring/feipi-skill-govern/`，再实现。
3. **职责分离**：`skills/`(能力) | `tools/`(服务) | `rules/`(规范) | `runtimes/`(运行时)。

## 渐进式加载

- 详细说明 → `AGENTS.md`
- 操作手册 → `docs/agent-handbook.md`
- Skill 治理 → `skills/authoring/feipi-skill-govern/SKILL.md`
- 行为规则 → `rules/README.md`
