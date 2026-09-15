---
name: feipi-techreport-ppt-skill
description: 用于将中文技术材料重构成 CTO、技术负责人和管理层可读的技术汇报 PPT；负责确定性叙事、布局、组件、设计令牌和质量门禁。若只需普通 PPT 编辑、读取或模板操作，应使用 Presentations skill。
---

# 中文技术汇报 PPT Skill

## 目标

把用户提供的事实重构成“先结论，后结构、流程、对比、演进、指标或证据”的中文技术汇报。输出必须是高质量初稿，并尽量由 PowerPoint 原生文本、形状、表格、连接线和图表组成，便于继续编辑。

## 能力边界

本 skill 掌控：

- 中文技术叙事与信息压缩；
- Design Token、Component Contract、Layout Contract；
- Semantic Slide IR、确定性编译与 overflow 状态；
- 可编辑性、包结构、静态和渲染质量标准。

通用 PPTX 读取、写入、渲染、兼容性和文件检查优先复用官方 Presentations skill。P0 的确定性后端为仓内 `pptxgenjs` adapter；后端不得反向定义视觉规范。未来替换后端时，Semantic Slide IR、合同和 token 保持不变。

## 默认行为

- 默认语言：简体中文，保留必要英文术语。
- 默认受众：CTO / 技术负责人 / 管理层。
- 默认模式：`review`；材料完整且无关键分歧时可直接生成和 QA。
- 不外部补充事实，不编造数字、架构、性能或业务结论。
- 不要求一页一确认；Page Contract 可作为内部规划。
- 只有结论不明确、两种叙事均合理、必须删除重要内容、必须拆页或会改变业务含义时，才请求用户决策。
- 已锁定的字体、字号、颜色、间距和组件风格不重复询问。

## 执行链路

```text
Raw Material
→ Composition Policy
→ Semantic Slide IR v2
→ Schema Validator
→ Component/Layout Contract Registry
→ Token Resolver
→ Resolved Render Plan
→ PptxBackend Adapter
→ Native Editable PPTX
→ Package/Editability QA + Render QA
→ fit / structured overflow result
```

### 1. 理解与规划

先提炼页面核心结论、受众认知任务、内容分组、主视觉与证据。叙事和压缩遵循 `design-system/composition-policy.md`，不得在此阶段决定字号、颜色或任意坐标。

### 2. 选择有限表达

普通路径只从已登记集合中选择：

- `layout_id`；
- `component_id`；
- `variant`；
- `size`；
- `region_id`；
- `text_role`；
- `density`。

若固定布局不能表达，可使用 `custom-grid`，但只能填写 12 列整数网格起点与跨度，不能填写英寸坐标。

### 3. 生成并校验 Semantic Slide IR v2

使用 `schemas/slide-ir.v2.schema.json`。普通模式禁止 `style`、`font_size`、`font_face`、颜色、padding、圆角和 `x/y/w/h`。独立文本必须声明 `text_role`；复合组件 slot 的文本角色由 Component Contract 决定。

```bash
node scripts/validate_slide_ir.js <slide-ir.json>
```

v1 fixture 只通过兼容 adapter 进入 v2。已登记旧字号可映射，未知数值字号直接失败。

### 4. 编译确定性 Render Plan

编译器只从以下真源解析视觉和几何：

- 原子视觉值：`design-system/tokens/*.core.json`；
- 组件 slots、sizes、variants、容量和 overflow：`design-system/components/*.json`；
- 固定 regions、允许组件和替代策略：`design-system/layouts/*.layout.json`。

Renderer 不得包含数字字号 fallback、连续字体缩放、PowerPoint 自动字号或 solver 覆盖合法合同几何。相同输入必须产生相同 geometry hash。

### 5. Overflow

内容放不下时按固定顺序返回：

```text
compress_text
→ change_component_size
→ change_layout
→ drop_secondary
→ split_required
```

系统不得生成新字号，不得静默改写业务含义。只有 `split_required`、删除重要内容或业务含义变化需要用户确认。

### 6. 生成与验收

```bash
node scripts/generate_pptx_pipeline.js <slide-ir.json> <output-dir> --mode fast|review|strict
```

必须完成与模式相匹配的检查：

- Schema 与 contract 校验；
- role-aware 字号校验；
- text-to-text overlap、截断、越界和容量检查；
- OpenXML 包结构、唯一语义对象名、原生对象、离散字号和无 autofit 检查；
- PowerPoint / QuickLook 优先的全尺寸渲染检查；
- 对正式结果进行实际视觉检查，不能只依据退出码或 montage。

LibreOffice 只做兼容性对照；它无法解析 macOS 字体时，不得据此替换 `Kaiti SC`。禁止整页图片伪装成 PPT。

## 模式

- `fast`：材料清晰时直接生成和 QA。
- `review`：仅暴露影响内容、布局或业务含义的少量决策。
- `strict`：完整合同、包检查、权威渲染和编辑回环。

兼容别名：`draft` → `fast`，`production` → `strict`。

## 渐进式加载

运行时默认只读本文件。随后只读取当前任务所需资源：

| 需要 | 加载资源 |
|---|---|
| 叙事与压缩 | `design-system/composition-policy.md` |
| 选择布局 | `design-system/layouts/` 中候选合同 |
| 使用组件 | 当前页面实际使用的组件合同 |
| IR 结构 | `references/slide-ir.md`、对应 schema |
| Pipeline / QA | `references/executable-framework.md`、`references/qa-gates.md` |
| 后端边界 | `references/backend-selection.md` |

不要在每次生成时读取全部 references、历史 PPTX、golden 或所有 benchmark。完整路由见 `references/index.md`。
