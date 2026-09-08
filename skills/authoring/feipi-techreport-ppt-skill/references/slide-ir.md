# Semantic Slide IR v2

Semantic Slide IR 只表达内容语义和对登记合同的选择，不携带最终视觉值。结构真源为 `schemas/slide-ir.v2.schema.json`。

```json
{
  "version": "v2",
  "slide_id": "architecture-01",
  "language": "zh-CN",
  "audience": "CTO",
  "layout_id": "layered-architecture",
  "density": "standard",
  "takeaway": "核心链路已收口为三层职责",
  "source_summary": [],
  "elements": [
    {
      "id": "core-layer",
      "component_id": "capability-group",
      "variant": "standard",
      "size": "md",
      "region_id": "main",
      "semantic_role": "system_component",
      "content": { "title": "核心服务", "items": ["编排", "校验"] },
      "source_refs": []
    }
  ],
  "provenance": []
}
```

## AI 可选择

- `layout_id`、`component_id`、`variant`、`size`、`region_id`；
- 已登记 `semantic_role`、`text_role` 和 density；
- 内容、分组、顺序和来源引用。

## 普通模式禁止

- `style`、任意字体或字号、颜色、padding、圆角；
- `x/y/w/h`、英寸、pt 或 EMU 几何；
- renderer 私有字段；
- 未登记 component/layout/variant/size/region。

独立文本必须显式声明 `text_role`。复合组件 slot 的 text role 由 Component Contract 固定，AI 不得覆盖。

## custom-grid

固定 Layout 不能表达页面时，可选择 `layout_id: custom-grid`。每个元素只能提供 12 列网格的整数 `column`、`row`、`column_span`、`row_span`；编译器将其转换为真实几何。custom-grid 仍不能内联视觉样式。

## v1 兼容

`schemas/slide-ir.schema.json` 继续接受历史 fixture，但共享 validator 会立即通过 `compiler/v1-to-v2.js` 转换：

- 旧 layout 名称映射到登记合同；
- 旧语义推导 `text_role`；
- 只有 token 中登记的 legacy 字号可映射；
- 未知数值（例如任意小数）直接失败；
- 历史几何只在兼容 adapter 内受控收口，新 v2 不暴露该入口。

## 编译结果

`compiler/render-plan-compiler.js` 将合法 IR 解析成 `schemas/render-plan.schema.json` 定义的 Render Plan。只有 Render Plan 包含 EMU、pt、解析后的颜色和 z-order，并生成稳定 geometry hash。

```bash
node scripts/validate_slide_ir.js <slide-ir.json>
node scripts/build_pptx_from_ir.js <slide-ir.json> <output.pptx>
```
