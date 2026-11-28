# References 渐进加载索引

默认只加载 `SKILL.md`。不要一次读取全部 references、fixture、历史 PPTX 或 golden。

| 当前需要 | 读取 |
|---|---|
| 模式和交互边界 | `workflow-modes.md`、`interaction-protocol.md` |
| 内部页面规划 | `page-contract.md`、`input-sufficiency.md` |
| 叙事、压缩、拆页 | `../design-system/composition-policy.md` |
| 选择版式 | `layout-patterns.md` + 候选 `design-system/layouts/*.layout.json` |
| 使用某组件 | `primitive-contracts.md` + 实际组件合同 |
| 构建 v2 IR | `slide-ir.md` + `schemas/slide-ir.v2.schema.json` |
| 理解编译链 | `executable-framework.md` |
| 后端边界 | `backend-selection.md` |
| QA 与 overflow | `qa-gates.md`、`visual-qa.md`、`repair-policy.md` |
| 有效重跑 | `auto-iteration.md` |
| 环境诊断 | `runtime-environment.md` |

`examples.md` 只在确需对照时加载。样例不能替代 token 或合同。
