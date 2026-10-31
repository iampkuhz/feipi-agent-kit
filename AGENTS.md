# Feipi Agent Kit

个人工作台与 AI 工程助手仓库。日常入口 `./workbench`，研发入口 `./develop`。既有 skills / tools / rules / commands 职责保留；Mac、Multica、OpenClaw、OpenClash 集成在 `components/`。

## 强约束

1. **中文优先**：面向用户输出默认简体中文。详见 `rules/global/language.md`。
2. **规则先行**：先遵循 `rules/` 和 `skills/authoring/feipi-skill-govern/`，再实现。
3. **职责分离**：`skills/`（Agent 能力）| `tools/`（外部服务封装）| `rules/`（行为规范）| `runtimes/`（运行时框架）。

## 规则加载顺序

Agent 启动后按以下顺序加载规则：

1. `AGENTS.md`（本文件）— 核心约束与入口
2. `rules/README.md` — 规则索引
3. 具体规则文件（如 `rules/global/language.md`）
4. 目标 skill 的 `SKILL.md`（按需加载）

## 工具使用协议

操作文件/搜索/测试前先查阅 `docs/governance/tool-usage.md`。使用低 token 成本的命令组合，禁止一次性读取大文件或全量扫描仓库。

## 完成定义（DoD）

1. 可追溯：改动与用户目标直接对应
2. 可验证：必要验证已执行并反馈结果
3. 文档同步：代码和文档同步更新
4. 规范一致：遵循 `rules/` 和 AGENTS.md

## 运行与私有边界

- 研发修改不自动进入日常环境；经 `workbench diff/capture/apply` 显式发布，先备份。
- 不把旧独立仓库重新作为运行来源；来源记录见 `docs/workbench-plan.md`。
- 私有数据原位保留，恢复遵守 `docs/workbench.md`；数据库停写或使用原生一致性导出。
- 回收只接受白名单配置；记忆、会话、密钥、登录态、订阅、备份不得进入 Git。

## 用户个人配置

以下文件为用户个人本地配置，必须保持原样，不得修改：

- `.claude/settings.local.json` — Claude Code 本地配置
- `.mcp.json` — MCP 服务配置

## 参考

- [CLAUDE.md](CLAUDE.md) — 详细说明
- [docs/agent-handbook.md](docs/agent-handbook.md) — 操作手册
- [docs/governance/tool-usage.md](docs/governance/tool-usage.md) — 工具使用规范
- [rules/README.md](rules/README.md) — 行为规则
- [skills/authoring/feipi-skill-govern/SKILL.md](skills/authoring/feipi-skill-govern/SKILL.md) — Skill 治理
