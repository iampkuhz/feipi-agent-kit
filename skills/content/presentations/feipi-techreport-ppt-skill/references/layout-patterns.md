# 版式模式

## 版式决策原则

先判断页面的“认知任务”，再选择结构。不要从原始材料的形态出发：

- 原始材料是大表，不代表 PPT 应该是大表。
- 原始材料是长段落，不代表 PPT 应该是文字页。
- 原始材料是多个维度，不代表每个维度都必须进入主画面。

如果内容超过当前版式容量，先做信息降维，再进入生成。

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
Top KPI Cards: 3-4 个关键差异
Main Matrix: 3-4 个对象 × 4-5 个维度
Right Insight Panel: 推荐倾向 / 缺口 / 取舍
Bottom Bar: 取舍结论 + 编号脚注
```

**强规则**：

- 默认不生成 5 列以上、6 行以上的大表。
- 如果用户给出全量矩阵，主画面只保留支撑结论的关键维度。
- 对比对象超过 4 个时，保留“我方目标/我方现状/最关键竞品/参照对象”，其余进入备注或建议拆页。
- 单元格内容优先写成短标签，例如 `理论 20K+ / 实测 2.4`，不要写成长句。
- 高亮只用于目标列、风险列或最大差异，不要整页多处抢色。
- 表格右侧 insight panel 不能覆盖表格；如果空间不足，应把 insight panel 放到顶部 KPI 或底部结论区。

**反例处理**：

当输入类似“自建链 vs 自建链 现状 vs Tempo vs Arc vs Solana，10 个维度全量对比”时，必须先压缩为：

```
Header: 主题 + 一句话结论
KPI Cards: TPS / 出块间隔 / 节点配置 / 共识路径
Main Matrix: 4 个对象 × 5 个维度
Insight Panel: 自建链 目标与当前缺口
Footer: 脚注编号 + 数据口径说明
```

如果用户坚持保留 6 列 × 10 行，必须建议拆成两页：第 1 页讲结论和关键差异，第 2 页放全量矩阵。

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

## 组合版式

当单一版式承载不了高密度技术内容时，可以组合，但必须有主次：

| 组合 | 适用 | 约束 |
|------|------|------|
| KPI cards + matrix | 指标驱动的竞品对比 | KPI 不超过 4 个，matrix 不超过 4 × 5 |
| architecture + side panel | 架构和关键取舍 | side panel 不超过 4 条 |
| timeline + risk strip | 路线图和风险 | risk strip 只放关键风险，不写长句 |
| heatmap + takeaway | 多维方案优劣 | heatmap 用 3 档以内，不做彩虹色 |

组合版式不能变成“所有东西都放一点”。如果主视觉不清楚，宁可拆页。
