# Patterns

`patterns/` 维护复杂模块和图形组合规则。它不直接存放 PPTX 生成代码，而是说明多个 component 如何组合成一个稳定版式。

当前 pattern 和 layout pattern 一一对应：

| Pattern | 对应 layout | 主要组件 |
|---------|-------------|----------|
| 架构图 | `architecture-map` | `native-component-diagram` + `rounded-text-box` |
| 分层图 | `layered-stack` | `rounded-text-box` + group container |
| 流程图 | `flow-diagram` | step marker + connector + note |
| 对比矩阵 | `comparison-matrix` | `native-table` + KPI cards + insight panel |
| 路线图 | `roadmap-timeline` | milestone card + connector |
| 指标看板 | `metrics-dashboard` | KPI cards + native chart/table |
| 决策树 | `decision-tree` | decision node + branch connector |
| 能力地图 | `capability-map` | grouped component nodes |

维护规则：

1. pattern 只描述组合关系和容量上限。
2. 颜色、字体、圆角、间距必须引用 `tokens/`。
3. 基础形状必须引用 `components/`。
4. 新增 pattern 时，需要同步 `references/layout-patterns.md`、Slide IR schema、builder、benchmark。

