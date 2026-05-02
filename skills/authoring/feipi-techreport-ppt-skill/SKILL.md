---
name: feipi-techreport-ppt-skill
description: Creates one-slide-at-a-time Chinese technical report PowerPoint slides from user-provided source material. Use when the user asks to create, refine, or structure a high-density technical report slide with diagrams, tables, bullet text, architecture maps, process flows, comparison matrices, roadmaps, metrics dashboards, or CTO-facing technical presentation content. Built as an authoring layer above the pptx skill; verifies input sufficiency, produces a Page Contract for confirmation, then generates or edits PPTX slides.
---

# 技术汇报 PPT 单页撰写 Skill

## Purpose

这是一个面向 CTO / 技术负责人的中文技术汇报 PPT 单页撰写 skill。

CTO 有技术背景，关心方向、路线、逻辑合理性、风险与取舍，但不默认了解当前具体领域细节。

用户提供原始事实与数据，本 skill 负责将其结构化、图解化、PPT 化，输出适合 CTO 阅读的高密度技术汇报单页。

## 与底层 pptx Skill 的关系

本 skill 是 Anthropic 官方 `pptx` skill 之上的**撰写与排版层**，不是替代品。

- 本 skill 负责：信息充足性检查、Page Contract 确认、内容重构、版面选择、视觉 QA、修复策略。
- `pptx` skill 负责：PPTX 文件创建、编辑、模板处理、渲染、缩略图生成、XML 操作、底层文件操作。
- 本 skill 调用 `pptx` skill 完成所有 PPTX 级别的读写操作。
- 本 skill 不复制、不修改、不绕过 `pptx` skill 的源文件。

## 默认假设

所有默认值内置，不主动询问用户：

- **默认语言**：中文为主，英文技术术语保留。
- **默认受众**：CTO / 技术负责人。
- **默认风格**：高密度技术汇报 PPT，少装饰，重结构、重图解、重结论。
- **默认页面比例**：16:9。
- **默认交互**：一页一交互，一页一确认。
- **默认信息密度**：一页可同时包含图、表格、列表文字，但必须可读。
- **默认视觉方向**：正式、克制、工程化、咨询式，不做营销页，不做花哨动效。

## 不可协商的规则

1. Always respond in Chinese unless the user explicitly requests otherwise.
2. Default audience is CTO / technical executive.
3. Do not ask the user to choose audience, visual style, color theme, or information density.
4. Do not perform external research.
5. Do not invent facts, numbers, architecture details, comparisons, conclusions, roadmap claims, or performance metrics.
6. Use only user-provided source material for factual content.
7. Before creating or editing a slide, verify that the user provided enough raw information.
8. If raw information is insufficient, ask for the missing source material before drafting the slide.
9. Generate exactly one slide at a time unless the user explicitly asks for a multi-slide plan.
10. Before generating a slide, produce a Page Contract and wait for user confirmation.
11. After generating a slide, perform visual QA and repair layout issues when possible.
12. Use the underlying pptx skill for PPTX creation, editing, template handling, rendering, and low-level file operations.
13. This skill is an authoring and layout layer, not a replacement for the pptx skill.

## 主工作流

```
Raw Input
→ Input Sufficiency Check
→ Page Contract
→ User Confirmation
→ PPTX Generation / Editing
→ Visual QA
→ Repair if needed
→ Final Response
```

### Step 1: Raw Input

用户可以提供：一段文字、bullet 列表、表格数据、架构描述、流程说明、对比项、阶段规划、已有 PPTX 或模板、想表达的大意。

### Step 2: Input Sufficiency Check

必须先判断信息是否足够支撑当前页。

最低输入要求：

1. **主题**：这一页讲什么。
2. **结论**：希望 CTO 看完记住什么。
3. **原始事实**：支撑结论的事实、数据、模块、流程、对象、对比项。
4. **关系**：内容之间是什么关系（分层、流程、对比、因果、阶段、取舍）。

如果缺少关键项，不要生成 Page Contract，不要生成 PPT。直接要求用户补充原始信息。

信息不足时输出：

```
当前信息不足，无法稳定生成 PPT 单页。请补充以下原始信息：

1. 缺少【...】：...
2. 缺少【...】：...
3. 缺少【...】：...

请直接补充原始信息，不需要描述设计风格。
```

详细检查规则见 `references/input-sufficiency.md`。

### Step 3: Page Contract

信息足够时，先生成 Page Contract，不生成 PPT。

格式：

```
## Page Contract

### 1. 本页目标
...

### 2. 一句话结论
...

### 3. 使用的原始信息
- ...

### 4. 页面内容范围
本页包含：
- ...

本页不包含：
- ...

### 5. 推荐页面结构
- 主图：...
- 表格：...
- 文字：...
- 结论区：...

### 6. 生成前确认
请确认是否按这个内容范围生成当前页 PPT。
```

禁止在 Page Contract 阶段擅自生成 PPTX。详细规则见 `references/page-contract.md`。

### Step 4: User Confirmation

只有用户明确确认后，才进入 PPTX 生成或修改。

可识别确认语："确认"、"按这个生成"、"可以"、"继续"、"生成"、"就这样"、"没问题"。

如果用户要求调整，则更新 Page Contract，不生成 PPT。

详细交互协议见 `references/interaction-protocol.md`。

### Step 5: PPTX Generation / Editing

确认后：

- 如果用户提供了已有 PPTX：调用底层 `pptx` skill 读取、分析、修改。
- 如果用户提供了模板：基于模板创建或编辑。
- 如果用户没有提供 PPTX：从零创建一页 PPTX 或追加到当前 deck。
- 必须使用底层 `pptx` skill 处理所有 PPTX 文件操作。
- 生成时不要加入用户未提供的事实内容。
- 可以改写、压缩、重组用户提供的内容。

页面结构选择见 `references/layout-patterns.md`。

### Step 6: Visual QA

生成后必须进行视觉 QA。

检查项：是否有元素溢出页面、是否有文本被截断、是否有非预期重叠、表格是否可读、主图是否是视觉中心、页面是否过密、字号是否过小、箭头/层级/分组是否清楚、页面是否有明确 takeaway、CTO 是否能在 30 秒内理解主结论。

详细检查清单见 `references/visual-qa.md`。

### Step 7: Repair

如果 QA 失败，自动修复一次。

修复优先级：压缩文字 → 合并 bullet → 把表格改成 cards → 减少图中节点 → 调整布局比例 → 增加分组和留白 → 最后才考虑缩小字号 → 如果仍然过载，建议拆成两页（必须问用户，不自动拆）。

详细策略见 `references/repair-policy.md`。

## Reference Files

- `references/interaction-protocol.md`：当需要判断交互流程、确认机制、是否应该追问时读取。
- `references/input-sufficiency.md`：当需要判断用户信息是否足够支撑当前页时读取。
- `references/page-contract.md`：当需要生成或修改 Page Contract 时读取。
- `references/layout-patterns.md`：当需要选择页面结构、图表组合、单页版式时读取。
- `references/visual-style.md`：当需要确定默认视觉规范、字号、颜色、密度、间距时读取。
- `references/visual-qa.md`：当 PPTX 生成后需要检查视觉问题时读取。
- `references/repair-policy.md`：当需要修复过密、重叠、溢出、不清楚的问题时读取。
- `references/examples.md`：当需要参考输入输出示例时读取。

## 示例

参考 `references/examples.md` 中的架构页、对比矩阵页、路线图页示例。
