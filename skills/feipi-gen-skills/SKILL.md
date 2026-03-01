---
name: feipi-gen-skills
description: 用于在本仓库创建、更新与重构中文 skills，覆盖结构设计、文案完善、脚本补齐与验证闭环。在新建 skill、统一规范或批量提升已有 skill 质量时使用。
---

# Skill Creator（中文）

## 核心目标
- 以最小上下文成本，产出可发现、可执行、可验证、可迭代的高质量 skills。
- 保持规则集中、实现可复用、验证可追溯。

## 适用场景
- 新建 skill（含结构初始化与文案落地）。
- 更新/重构 skill（规则对齐、脚本补齐、验证闭环）。
- 批量统一规范（命名、结构、验证、文档同步）。

## 内容分层
- `SKILL.md`：入口说明、执行流程摘要、规则索引与关键命令。
- `references/`：规则细节、清单、命名规范、流程与策略。
- `scripts/`：可重复执行的确定性操作。

## 目录标准

```txt
<skill-name>/
├── SKILL.md             # 唯一必需文件，定义触发与执行规则
├── agents/openai.yaml   # UI 元数据（展示名、短描述、默认提示词）
├── scripts/             # 确定性、可重复执行的脚本
├── references/          # 按需加载的详细资料
└── assets/              # 输出时使用的模板或静态文件
```

## 执行流程（开发态摘要）
1. Explore：明确目标、输入输出、边界与风险。
2. Plan：列出改动文件、理由与验证方式。
3. Implement：先落脚本/参考/资产，再更新 `SKILL.md`。
4. Verify：运行 `make validate DIR=<skill-root>/<name>` 并完成至少一种任务级验证。
5. 收尾：按 `references/changelog-policy.md` 更新 `CHANGELOG.md` 并检查 `README.md`。

详细流程与约束见 `references/workflow.md`。

## 规则索引（必读）
- `references/repo-constraints.md`：仓库落地硬约束与使用/开发分离。
- `references/naming-conventions.md`：命名规范（action 字典与示例）。
- `references/env-policy.md`：环境变量最小化策略。
- `references/workflow.md`：工作流、验证与反模式修复。
- `references/changelog-policy.md`：变更记录与 README 同步规则。
- `references/quality-checklist.md`：交付清单（复制打勾）。
- `references/sources.md`：来源说明。

## 常用命令（开发态）

```bash
# 初始化新 skill（默认优先 skills/，可切换到 .agents/skills）
make new SKILL=<name> [RESOURCES=scripts,references,assets] [TARGET=auto|skills|repo|<path>]

# 校验单个 skill 目录
make validate DIR=<skill-dir>/<name>

# 统一入口执行 skill 测试
make test SKILL=<name>
```
