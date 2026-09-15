# 可执行框架

```text
Raw Material
→ Composition Policy
→ Semantic Slide IR v2
→ Schema Validator
→ Contract Registry
→ TokenStore
→ Resolved Render Plan
→ PptxBackend
→ Native Editable PPTX
→ Static / Package / Editability / Render QA
```

## 分层职责

| 层 | 真源/实现 | 不负责 |
|---|---|---|
| Composition | `design-system/composition-policy.md` | 字号、颜色、坐标 |
| Semantic IR | v2 schema | 解析视觉值 |
| Contract | `design-system/components/`、`layouts/` | 原子视觉值 |
| Token | `design-system/tokens/`、`compiler/token-store.js` | 叙事选择 |
| Compiler | `compiler/render-plan-compiler.js` | 通用 PPTX I/O |
| Backend | `adapters/` | 定义设计规范 |
| QA | `helpers/static-qa.js`、`helpers/pptx/postcheck.js`、render adapter | 静默修复业务内容 |

## Pipeline

`helpers/pipeline/run-pipeline.js` 是单次状态机：

1. 校验并适配 v1/v2；
2. 编译确定性 Render Plan 和 geometry snapshot；
3. 执行 Static QA 与 overflow evaluator；
4. 通过 backend 生成真实 PPTX；
5. 执行 package/editability postcheck；
6. 使用 PowerPoint/QuickLook 优先的渲染器输出证据；
7. 返回 `pass`、`needs_user_decision`、`fail` 或 `incomplete`。

同一 IR hash 不做无效重复轮次。需要调整时，先由语义层产生新的 IR，再运行新的 pipeline。

## 硬约束

- Renderer 只接收 Render Plan；缺少 resolved token 硬失败。
- 普通 v2 IR 不含视觉数值或自由几何。
- 不使用 autofit、连续字号搜索或 font scale。
- Solver 不得覆盖合同已给出的合法几何。
- 输出优先为原生文本、形状、表格、连接线和图表。
- Backend 是可替换 adapter；P0 使用 PptxGenJS，P1 与官方 Presentations/Artifact Tool 做 parity。

## 验证

```bash
node scripts/generate_pptx_pipeline.js <ir> <output-dir> --mode strict
node scripts/inspect_pptx_artifact.js <output.pptx> --json --release
```
