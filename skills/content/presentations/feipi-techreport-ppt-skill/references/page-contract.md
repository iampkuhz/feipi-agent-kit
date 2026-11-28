# Page Contract

Page Contract 是语义规划工具，不是视觉配置，也不默认要求用户确认。

## 内部字段

- 页面核心结论；
- 受众需要完成的认知任务；
- 事实、证据、风险和建议的映射；
- 主视觉与次要证据；
- 候选 `layout_id`、组件组合和 density；
- 容量判断与可能的 overflow action；
- 不在本页表达的内容。

Page Contract 不填写字号、颜色、padding、圆角或真实坐标。它只指导 Semantic Slide IR 从登记合同中选择引用。

## 何时对用户可见

只有以下情况把 Page Contract 中的取舍转换成精简决策卡片：

- 核心结论不明确；
- 两种叙事方向都合理；
- 必须删除重要内容；
- 必须拆页；
- 选择会改变业务含义。

决策卡片只说明业务/内容取舍、推荐项和影响，不让用户选择已锁定的视觉参数。没有关键分歧时，Page Contract 保留在内部并直接继续生成。

## 与 IR 的关系

Page Contract 的结论、认知任务、内容范围和来源映射进入 Semantic Slide IR；布局与组件只转换为登记 id。Schema、合同和 compiler 再负责结构、允许值和确定性几何。
