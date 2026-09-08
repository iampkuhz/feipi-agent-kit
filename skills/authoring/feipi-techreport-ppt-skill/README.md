# feipi-techreport-ppt-skill

面向 CTO、技术负责人和管理层的中文技术汇报 PPT skill。AI 负责语义理解、叙事和从有限合同中选择表达；视觉原子值与常规几何由代码确定。

## 架构

```text
材料 → Composition Policy → Semantic Slide IR v2
→ Schema + Component/Layout Contract
→ TokenStore → Resolved Render Plan
→ PptxBackend → 原生可编辑 PPTX
→ Static / Package / Editability / Render QA
```

单一事实源：

- `design-system/tokens/`：字体、离散字号、颜色、间距、圆角、线宽、页面与网格；
- `design-system/components/`：slots、variants、sizes、text role、容量与 overflow；
- `design-system/layouts/`：固定 regions、允许组件、容量与替代布局；
- `design-system/composition-policy.md`：结论、主视觉、压缩和拆页；
- `schemas/`：结构合法性；
- `compiler/`：将引用解析为确定性 Render Plan；
- `adapters/`：可替换 PPTX 后端；
- `fixtures/benchmarks/`：开发回归，不进入默认运行时上下文。

## P0 已实现

- 统一 TokenStore，theme/style lock/renderer 不再维护第二套字号；
- Semantic Slide IR v2 禁止普通模式任意样式、字号和坐标；
- v1 兼容 adapter 只映射已登记旧值；
- role-aware 最小字号校验；
- 固定 Layout Contract 和 geometry hash；
- 无 autofit、无连续缩放、无 renderer 数字 fallback；
- 结构化 overflow，不自动改写业务内容；
- 原生文本、形状、表格和连接线；稳定语义对象名；
- OpenXML 检查离散字号、重复 ID、自动字号、整页图片和原生对象；
- `fast/review/strict` 模式及 `draft/production` 兼容别名。

## 快速验证

```bash
cd skills/authoring/feipi-techreport-ppt-skill
npm ci
bash scripts/test.sh
```

生成一个 v2 acceptance 页面：

```bash
node scripts/generate_pptx_pipeline.js \
  fixtures/acceptance/layered-architecture.slide-ir.v2.json \
  /tmp/feipi-ppt-output \
  --mode strict
```

## 兼容与限制

- v1 `slide-ir.schema.json` 和旧 CLI 文件名继续保留；新页面应使用 v2。
- P0 后端为 PptxGenJS adapter；P1 将与官方 Presentations/Artifact Tool adapter 做 parity 后再切换默认。
- `Kaiti SC` 是最终 PPTX 首选字体。LibreOffice 缺少 macOS 字体解析能力时只记录兼容 warning，不改变字体规范。
- P0 完整合同覆盖分层架构、方案对比和多方交互流程；其余组件与 Layout 在 P1 补齐。
- golden PPTX/PNG 只有经人工视觉签字后才能建立。

执行说明见 [SKILL.md](SKILL.md)，按需资源路由见 [references/index.md](references/index.md)。
