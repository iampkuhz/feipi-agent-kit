# 治理产物与模板索引

## 模板清单

| 阶段 | 模板路径 | 用途 |
|------|----------|------|
| Step 1 | `assets/governance/step-1-audit.template.md` | 建立当前问题基线 |
| Step 1.5 | `assets/governance/step-1-5-rename-review.template.md` | 评审 target_name / target_layer |
| Step 1.5 | `assets/governance/rename-plan.template.md` | 规划重命名与迁移执行项 |
| Step 2 | `assets/governance/step-2-execution-checklist.template.md` | 控制执行边界与修复项 |
| 收口 | `assets/governance/governance-report.template.md` | 汇总问题、修复、验证与风险 |
| 案例沉淀 | `assets/governance/anti-pattern.template.md` | 记录反模式、症状、修复与检测信号 |

## 通用字段

以下字段应在相关模板中出现，并保持同名：

- `current_name`
- `target_name`
- `target_layer`
- `target_domain`
- `target_action`
- `target_object`
- `rename_reason`
- `rule_violation`
- `migration_risk`
- `script_localization_status`
- `validation_status`

## 使用原则

- 模板是治理产物骨架，不替代真实分析与验证。
- 若本次不涉及命名迁移，可跳过 Step 1.5，但仍需在 report 中说明原因。
- 旧 rename 结论若不符合 v2，必须通过 Step 1.5 重审，不能直接复用历史模板。
