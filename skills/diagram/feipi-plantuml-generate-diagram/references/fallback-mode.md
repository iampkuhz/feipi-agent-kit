# Fallback Mode 兜底模式

## 适用条件

- 用户请求"用 PlantUML 画个图"，未指定具体图类型。
- Router 无法识别或消歧图类型。

## 最低交付

- `diagram.puml` - 包含 `@startuml` 与 `@enduml` 的可渲染源码
- `diagram.svg` - 渲染后的 SVG（仅 render_result=ok 时存在）
- `validation.json` - 验证结果合同

## 最低校验

1. `.puml` 包含 `@startuml` 与 `@enduml`
2. 渲染脚本可执行（若 server 不可用，标记为 `blocked`，原因写入 `render_server_unavailable`）
3. `validation.json` 能区分以下状态：
   - `success` - 全部通过
   - `blocked` - 语法错误或渲染失败
   - `blocked` + `blocked_reason=render_server_unavailable` - 渲染服务不可达
   - `syntax_error` - PlantUML 语法错误

## 不要求

- 不要求用户先填写完整 typed brief
- 不执行覆盖校验（因为没有 typed schema 可对照）
- 不执行布局校验（因为没有 typed 布局规则）

## validation.json 结构

```json
{
  "schema_version": "1.1",
  "skill_name": "feipi-plantuml-generate-diagram",
  "diagram_id": "diagram",
  "diagram_type": "fallback",
  "profile": "fallback",
  "profile_version": "1.0",
  "brief_check": "skipped",
  "coverage_check": "skipped",
  "layout_check": "skipped",
  "render_result": "ok | skipped | syntax_error",
  "normalized_puml_sha256": "<sha256>",
  "artifacts": {"diagram": {"path": "diagram.puml", "sha256": "<sha256>"}},
  "metrics": {"node_count": 0, "edge_count": 0, "max_degree": 0},
  "final_status": "success | blocked",
  "blocked_reason": ""
}
```
