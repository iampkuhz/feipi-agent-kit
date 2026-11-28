# P0 技术汇报单页 PPT 模板分类

本文件定义 `feipi-techreport-ppt-skill` 的 P0 单页 PPT 模板。分类轴不是业务场景，而是**页面信息组织结构 / PPT 模板**。

## P0 模板清单

| P0 ID | 模板类型 | 模板定义 | 可承载的典型需求 | 推荐现有 builder | 主要组件 |
|---|---|---|---|---|---|
| P0-01 | 复杂多对象对比矩阵页 | 一个大表格对 ≥4 个对象、≥5 个维度进行横向对比，并给出口径、补充说明和结论 | 技术选型、竞品对标、Benchmark、能力成熟度、供应商对比 | `comparison-matrix.js` | `native-table`, `source-note`, `badge-and-label`, `rounded-text-box` |
| P0-02 | 分层架构 / 组件结构图页 | 展示系统层级、组件、职责、上下游关系和改造点 | 系统架构、节点架构、平台架构、支付架构、数据架构 | `architecture-map.js` / `layered-stack.js` | `native-component-diagram`, `capability-group`, `legend`, `rounded-text-box` |
| P0-03 | 多角色交互流程 / 泳道流程页 | 展示多个角色/系统之间按步骤发生的交互，强调谁调用谁、何时产生状态变化 | 链上链下交互、跨链流程、支付流程、审批流、AI 多角色协作 | `flow-diagram.js` | `flow-step`, `legend`, `source-note`, `rounded-text-box` |
| P0-04 | 阶段演进 Roadmap 页 | 按阶段展示目标、时间窗口、能力、交付物、场景支持和风险 | 技术路线、产品路线、主网/测试网计划、平台演进 | `roadmap-timeline.js` | `timeline-milestone`, `kpi-card`, `progress-indicator`, `capability-group` |
| P0-05 | 端到端链路闭环页 | 从入口到最终生产验收，展示完整业务/技术闭环、检查点和完成标准 | 链接入生命周期、交易生命周期、数据处理链路、模型调用链路、发布流程 | `flow-diagram.js`，必要时配合 `capability-map.js` | `flow-step`, `kpi-card`, `capability-group`, `source-note` |

## P0 选择原则

P0 只覆盖最通用、最高频、最能检验生成质量的页面模板：

1. 是否是技术汇报高频页型；
2. 是否能承载多个业务场景；
3. 是否能测试结构化信息压缩能力；
4. 是否能暴露布局、表格、箭头、层级、准出校验等核心问题；
5. 是否能复用现有 builder 快速进入测试。

## 暂不纳入 P0 的模板

| 模板 | 暂缓原因 | 后续归并 |
|---|---|---|
| 方案取舍决策页 | 可先并入 P0-01，属于少对象、强结论版本 | P1 |
| 能力地图 / 蓝图页 | 与架构图和 Roadmap 有重叠 | P1 |
| 迁移路径页 | 可先由 Roadmap 承载 | P1 |
| 安全边界 / 信任域架构页 | 属于架构图的安全特化版本 | P1 |
| 指标体系 / 口径说明页 | 可并入对比矩阵或诊断页 | P1 |
| 上线验收 / Checklist 页 | 视觉复杂度较低，后续单独实现 | P1 |
| 部署拓扑 / 网络架构页 | 需要更强网络边界与图标体系 | P2 |
| 异常 / 补偿 / 回放流程页 | 属于流程图高级变体 | P2 |
