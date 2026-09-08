# 工作流模式

配置真源为 `config/workflow-modes.json`。三种模式共享同一套 token、Component/Layout Contract、Semantic Slide IR、compiler 和 backend，不复制视觉系统。

| 模式 | 用途 | 交互 | QA |
|---|---|---|---|
| `fast` | 材料清晰、快速形成高质量初稿 | 无关键分歧时直接生成 | schema、contract、Static QA、package QA；渲染能力存在时执行 |
| `review` | 日常评审和结构取舍 | 只展示影响内容、布局或业务含义的决策 | fast 全部检查，并返回结构化 overflow/decision |
| `strict` | 正式交付 | 仅关键业务决策需确认 | 完整 package/editability QA、权威渲染、全尺寸视觉检查和编辑回环 |

兼容别名：`draft` 映射为 `fast`，`production` 映射为 `strict`。别名不维护独立规则。

## 共同硬约束

- 不编造事实，保留来源追溯；
- 不允许任意样式、字号或普通模式坐标；
- 不允许 autofit、连续缩放和 renderer fallback；
- hard fail 不得交付；
- 渲染 unavailable 必须如实记录，不能报告视觉通过；
- 相同 IR hash 不重复无效运行。

## 用户决策

只有以下情况暂停并请求用户：

- 核心结论不明确；
- 两个叙事方向都合理且会改变页面认知任务；
- 必须删除重要内容；
- `split_required`；
- 选择会改变业务含义。

颜色、字体、字号、间距、圆角、已登记组件 variant 和固定 layout 几何不要求用户确认。

## 状态

- `pass`：自动门禁通过；若为正式交付，还需完成实际视觉检查。
- `needs_user_decision`：存在上述关键取舍或结构化 `split_required`。
- `fail`：schema、contract、token、编译、package 或 QA 硬失败。
- `incomplete`：strict 所需的权威渲染或编辑回环证据不可用。

Pipeline 每次只检查一个明确 IR 版本。若需要修复，必须先形成新的 IR hash，再重新运行；不得对同一输入重复三轮并声称已修复。
