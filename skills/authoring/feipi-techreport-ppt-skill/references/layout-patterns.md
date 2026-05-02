# 版式模式

## 8 类页面模式

### 1. architecture-map

**适用**：系统架构、链架构、agent 架构、组件依赖图。

**结构**：

```
Header: 标题 + 一句话结论
Main Visual: 架构图，占 50-60%
Side Panel: 关键模块说明 / 风险 / 取舍
Bottom Bar: takeaway
```

### 2. layered-stack

**适用**：分层能力、技术栈、模块边界、协议栈。

**结构**：

```
Header
Main Visual: 横向或纵向分层图
Right Notes: 每层职责/边界
Bottom Bar: 关键结论
```

### 3. flow-diagram

**适用**：交易流程、调用链、数据流、审批流程。

**结构**：

```
Header
Main Visual: 5-7 步流程图
Evidence Zone: 输入/输出/关键判断
Bottom Bar: 结论
```

### 4. comparison-matrix

**适用**：多个方案、多个链、多个模型对比、优劣分析。

**结构**：

```
Header
Main Table: 3-5 列 × 4-6 行
Left/Top Highlight: 推荐倾向
Bottom Bar: 取舍结论
```

### 5. roadmap-timeline

**适用**：阶段规划、演进路线、版本计划。

**结构**：

```
Header
Main Visual: 3-5 阶段路线图
Milestone Cards: 每阶段目标/交付
Bottom Bar: 当前阶段重点
```

### 6. metrics-dashboard

**适用**：TPS、TVL、成本、延迟、资源、数量等指标展示。

**结构**：

```
Header
Top KPI Cards: 3-5 个
Main Visual: 趋势/对比/分组图
Side Notes: 指标解释
Bottom Bar: 指标结论
```

### 7. decision-tree

**适用**：方案选择、判断条件、技术路线判断。

**结构**：

```
Header
Main Visual: 判断树
Right Panel: 关键判断标准
Bottom Bar: 推荐路径或待决问题
```

### 8. capability-map

**适用**：能力域、功能模块、生态事项分组、建设规划。

**结构**：

```
Header
Main Visual: 能力地图 / 模块分区
Side Panel: 优先级/依赖关系
Bottom Bar: 建设重点
```

## 选择规则

根据内容类型内部判断，不要让用户选：

| 内容特征 | 选择版式 |
|---------|---------|
| 组件和依赖关系 | architecture-map |
| 层级和职责边界 | layered-stack |
| 步骤和顺序 | flow-diagram |
| 方案优劣对比 | comparison-matrix |
| 阶段推进 | roadmap-timeline |
| 数字指标 | metrics-dashboard |
| 判断逻辑/条件分支 | decision-tree |
| 能力分类/模块分组 | capability-map |

**不要把这些候选全部展示给用户。** Page Contract 里只给一个推荐版式。
