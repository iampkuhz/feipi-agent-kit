# architecture-brief 字段说明

## 单一真相

- `assets/validation/architecture-brief.schema.json`：唯一字段真相，负责必填项、格式、长度、枚举和对象结构。
- `assets/templates/architecture-brief.yaml`：填写模板，只负责交互体验，不重复硬规则。
- `assets/examples/architecture-brief.example.yaml`：完整样例，既用于说明也用于回归测试。

## 谁维护什么

- skill 维护者负责：schema、模板、样例、校验脚本。
- 任务发起方负责：具体业务 brief 的内容正确性。
- 画图执行方负责：先指出 brief 问题，再生成图，不得偷偷改写业务含义。

## 字段建议

### 顶层字段

- `diagram_id`：文件名与引用 id，建议简短稳定。
- `diagram_type`：当前固定为 `architecture`。
- `title`：图标题，面向读者显示。
- `summary`：一句话说明这张图想表达什么，便于前置语义检查。

### `layers`

- 至少 3 层，建议用“接入层 / 应用层 / 数据层”这类稳定分层。
- `name` 用业务可读中文，`id` 用稳定英文别名，`color` 用十六进制颜色。
- 每一层都应至少承载 1 个组件。

### `components`

- `id` 是 PlantUML alias 的唯一来源，生成图时必须原样使用。
- `name` 是展示名，图上必须与输入保持一致，不得擅自缩写或换译名。
- `type` 只描述图元类型，不表达业务重要性。
- `description` 用于帮助前置校验判断语义是否完整。

### `flows`

- `id` 统一使用 `S1`、`S2` 这类连续编号。
- `description` 是箭头文案的唯一来源，生成时可为了换行插入 `\\n`，但文字含义不能变。
- `from` / `to` 必须引用 `components[].id`。

### 可选字段

- `layout.include_legend`：是否强制包含图例。
- `out_of_scope`：明确不进入图中的内容，避免生成阶段脑补。
