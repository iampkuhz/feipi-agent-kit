# Schemas

- `slide-ir.v2.schema.json`：Semantic Slide IR v2。普通模式禁止 style、任意字号、字体、颜色、padding 和英寸坐标；`custom-grid` 只接受整数网格起点与跨度。
- `render-plan.schema.json`：编译器内部 Render Plan。只有该层允许解析后的 EMU 和 pt。
- `slide-ir.schema.json`：v1 兼容输入；由 adapter 映射到 v2，未知旧字号硬失败。
- `style-lock.schema.json`：派生 profile 引用，不允许内联视觉数值。

`scripts/validate_slide_ir.js` 使用共享 Ajv validator；结构合法性由 schema 负责，允许值和跨文件关系由 token store 与 contract registry 负责。

QA report schema 与完整 Component/Layout Contract schema 在 P1 补齐。
