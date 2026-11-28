# Components

组件层维护可复用的 PPT 原生组件配置。这里的“组件”不是前端组件，而是可被 PPTX builder 复用的一组视觉和结构规则。

## 组件全集

### 1. 文本与说明类

| 组件 | 文件 | 用途 |
|------|------|------|
| 文本层级 | `text-hierarchy.json` | 标题、副标题、正文、脚注、来源 |
| 圆角文本框 | `rounded-text-box.json` | 普通说明、证据、风险、结论 |
| 代码块 | `code-block.json` | 配置、伪代码、SQL、日志片段 |
| 来源脚注 | `source-note.json` | 数据来源、口径说明、页脚 |

### 2. 版面与容器类

| 组件 | 文件 | 用途 |
|------|------|------|
| 版面区域 | `layout-region.json` | header、main、side、footer 的视觉边界 |
| 分隔线 | `section-divider.json` | 区块分隔、标题下划线、表格组分隔 |
| 标签徽标 | `badge-and-label.json` | 状态、阶段、风险等级、版本标签 |
| 图例 | `legend.json` | 颜色、线型、状态解释 |

### 3. 数据表达类

| 组件 | 文件 | 用途 |
|------|------|------|
| KPI 卡片 | `kpi-card.json` | 关键数字、指标对比、状态摘要 |
| 原生表格 | `native-table.json` | 短矩阵、关键事实表 |
| 热力矩阵 | `heatmap-matrix.json` | 方案评分、能力成熟度、风险分布 |
| 原生图表 | `native-chart.json` | 趋势、柱状、占比、简单分布 |
| 进度指标 | `progress-indicator.json` | 完成率、阶段进度、资源占用 |

### 4. 图解与架构类

| 组件 | 文件 | 用途 |
|------|------|------|
| 原生组件图 | `native-component-diagram.json` | 架构节点、分组框、连接线、端口 |
| 流程步骤 | `flow-step.json` | 顺序步骤、输入输出、关键判断 |
| 时间线里程碑 | `timeline-milestone.json` | 路线图、版本计划、交付阶段 |
| 决策节点 | `decision-node.json` | 判断树、分支条件、推荐路径 |
| 能力分组 | `capability-group.json` | 能力域、模块分区、建设优先级 |

### 5. 媒体与引用类

| 组件 | 文件 | 用途 |
|------|------|------|
| 媒体框 | `media-frame.json` | 截图、架构图片、引用图、logo |

## 使用规则

1. builder 应优先使用组件 token，不直接硬编码颜色、字号、圆角。
2. 一个组件只做一类稳定事情，不混合多个复杂 pattern。
3. 复杂页面由 pattern 组合组件，不在组件层塞完整页面。
4. 新增组件必须声明 `depends_on`。
5. 组件参数变化需要同步 benchmark 或 fixture。

