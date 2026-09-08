# Scripts

## 主要入口

| 脚本 | 职责 |
|---|---|
| `validate_slide_ir.js` | 共享 Ajv schema + token/contract 校验，自动识别 v1/v2 |
| `build_pptx_from_ir.js` | Semantic Slide IR → Render Plan → PptxBackend |
| `generate_pptx_pipeline.js` | 单次 validate → compile → QA → build → postcheck → render 状态机 |
| `inspect_slide_ir_layout.js` | 编译后 Static QA |
| `inspect_pptx_artifact.js` | OpenXML、原生对象、语义名称和编辑性检查 |
| `validate_design_system.js` | token、component、layout、profile 引用一致性 |
| `validate_style_lock.js` | 派生 style profile 校验，拒绝内联视觉数值 |
| `run_benchmarks.js` | benchmark 套件与期望状态比较 |
| `doctor.js` | 运行时和渲染能力诊断 |
| `test.sh` | P0、兼容、真实 PPTX、benchmark 和 pipeline 总入口 |

## 常用命令

```bash
npm ci
node scripts/validate_slide_ir.js fixtures/acceptance/layered-architecture.slide-ir.v2.json
node scripts/build_pptx_from_ir.js <slide-ir.json> <output.pptx>
node scripts/generate_pptx_pipeline.js <slide-ir.json> <output-dir> --mode strict
node scripts/run_benchmarks.js --dry-run --full
bash scripts/test.sh
```

## 模式与渲染

- `fast`：快速生成与基本 QA。
- `review`：仅在影响内容、布局或业务含义时返回决策。
- `strict`：要求完整 package/editability/render 证据；仍需对全尺寸渲染做实际视觉检查。
- `draft`、`production` 分别是 `fast`、`strict` 的兼容别名。
- macOS 优先使用 PowerPoint/QuickLook/CoreText；LibreOffice 只做兼容性对照。

## 约束

- Node 依赖安装在 skill 本地并使用 lock 文件。
- 不把缺少渲染器描述成视觉 QA 已通过。
- Pipeline 不会对未改变的 IR 重复多轮检查；相同 IR hash 直接返回结构化 overflow/decision。
- 测试生成物写入临时目录，不把运行时输出提交为规范真源。
