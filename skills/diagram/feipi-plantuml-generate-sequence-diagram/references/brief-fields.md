# sequence-brief 字段说明

## 单一真相

- `assets/validation/sequence-brief.schema.json`：唯一字段真相，负责必填项、格式、长度、枚举和对象结构。
- `assets/templates/sequence-brief.yaml`：填写模板，只负责交互体验，不重复硬规则。
- `assets/examples/sequence-brief.example.yaml`：完整样例，既用于说明也用于回归测试。

## 谁维护什么

- skill 维护者负责：schema、模板、样例、校验脚本。
- 任务发起方负责：具体业务 brief 的内容正确性。
- 画图执行方负责：先指出 brief 问题，再生成图，不得偷偷改写业务含义。
- 当前 brief 只建模主路径消息，不单独为 `activate` / `deactivate` 或 `alt` / `else` 建字段。

## 字段建议

### 顶层字段

- `diagram_id`：文件名与引用 id，建议简短稳定。
- `diagram_type`：当前固定为 `sequence`。
- `title`：图标题，面向读者显示。
- `summary`：一句话说明这张图想表达什么交互流程，便于前置语义检查。

### `participants`

- `id` 是 PlantUML alias 的唯一来源，生成图时必须原样使用。
- `name` 是展示名，图上必须与输入保持一致，不得擅自缩写或换译名。
- `type` 描述图元类型：
  - `actor`：外部用户或系统
  - `participant`：服务/组件
  - `database`：数据库/存储
- `description` 用于帮助前置校验判断语义是否完整。

### `messages`

- `id` 统一使用 `M1`、`M2`（请求）或 `R1`、`R2`（返回）这类编号。
- `description` 是箭头文案的唯一来源，生成时可为了换行插入 `\\n`，但文字含义不能变。
- `from` / `to` 必须引用 `participants[].id`。
- `type` 描述消息类型：
  - `sync`：同步请求（实线箭头）
  - `return`：返回消息（虚线箭头）
  - `async`：异步消息（开放箭头）
  - `create`：创建对象
  - `destroy`：销毁对象

### `groups`（可选）

- 用于表达参与者的分层关系，如"前端层"、"后端层"、"数据层"。
- 每个组包含：
  - `id`：组的唯一标识。
  - `name`：组的展示名，会渲染为 `box` 标题。
  - `participants`：参与者 id 列表，必须引用 `participants[].id`。
  - `separator`：是否在该组相关消息段前添加 `== 组名 ==` 分隔线；不得生成 PlantUML `separator` 关键字。
- 生成图时，每个组会渲染为 `box "name" #颜色 { ... } endbox`。

### 可选字段

- `layout.direction`：支持 `top_to_bottom`（默认）或 `left_to_right`。存在 `groups` / `box` 时必须使用 `top_to_bottom`。
- `layout.include_legend`：是否强制包含图例。
- `out_of_scope`：明确不进入图中的内容，避免生成阶段脑补。
- `groups`：可选分层信息；若存在且 `separator=true`，生成图时必须补对应的 `== 组名 ==` 消息区分隔线。
