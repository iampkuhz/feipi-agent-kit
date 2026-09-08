# Component Contract

每个 v2 组件合同应声明：

- `component_id`；
- slots 及每个 slot 的固定 `text_role`；
- variants、sizes 和允许 region；
- size 对应的 token 引用；
- 最大行数、bullet 数、项目数和内容容量；
- 允许嵌套的组件；
- overflow policy；
- AI 可改变与禁止改变的属性；
- 原生可编辑要求；
- QA 验收条件。

Semantic Slide IR 只引用 component/variant/size/region，并提供内容。Renderer 不接受组件私有视觉覆盖。若合同缺少必要 token 或 slot role，Contract Registry 必须硬失败。

P0 完整合同覆盖当前三个验收页面实际使用的 `capability-group`、`native-table`、`text-hierarchy`、`flow-step`、`source-note`。其余组件在 P1 补齐，不能仅凭最大字符数视为完整合同。
