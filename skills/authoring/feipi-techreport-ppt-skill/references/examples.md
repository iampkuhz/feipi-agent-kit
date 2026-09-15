# v2 示例路由

示例只说明语义选择，不定义视觉数值；token、组件和布局合同仍是规范真源。

## 分层架构

- 认知任务：理解层次、职责边界和依赖；
- `layout_id`：`layered-architecture`；
- 主组件：`capability-group`；
- 证据：`source-note` 或独立 `text-hierarchy`；
- fixture：`layered-architecture.slide-ir.v2.json`。

## 方案对比

- 认知任务：理解关键差异并做取舍；
- `layout_id`：`solution-comparison`；
- 主组件：`native-table`；
- 辅助组件：能力/风险摘要；
- fixture：`solution-comparison.slide-ir.v2.json`。

## 多方交互流程

- 认知任务：理解参与方、先后关系和关键交互；
- `layout_id`：`multi-party-flow`；
- 主组件：`flow-step`，连接线由编译器基于节点关系生成；
- fixture：`multi-party-flow.slide-ir.v2.json`。

这三个 fixture 用于 P0 自动化和真实 PPTX 验收。成为 golden 前仍需人工视觉签字，不能用样例反向推断新 token。
