---
name: feipi-plantuml-generate-architecture-diagram
description: 用于根据 architecture-brief 模板生成并校验 PlantUML 架构图；在用户要交付可渲染、可覆盖核对的架构图时使用。
---

# PlantUML 架构图生成与校验

## 核心目标

- 先把架构图需求收敛成 `architecture-brief`，再根据 brief 生成 PlantUML，避免“需求没定清就开始画”。
- 输出不只是一段 `.puml` 代码，还要补齐 brief 校验、命名覆盖校验、布局校验和渲染校验结果。
- 让“模板维护”和“具体业务内容填写”分开：模板/schema 由 skill 维护，具体 brief 由任务发起方维护。

## 适用场景

- 用户要画系统架构图、模块分层图、组件关系图，且交付物必须是 PlantUML。
- 用户已经准备好 YAML brief，希望直接生成并校验图。
- 用户只有自然语言需求，但接受先补成模板，再继续生成图。
- 用户明确要求校验“所有命名都落图”“渲染正常”“排版不过宽、无明显拥挤”。

## 不适用场景

- 时序图、类图、流程图等非架构图场景。
- 只要结构建议或文字分析，不需要可渲染 PlantUML。
- 目标产物是 Mermaid、Draw.io、Excalidraw 等非 PlantUML 格式。
- 只有一句非常抽象的口号，连层次、组件、流向都没有时；此时先补模板，不直接画图。
- 需要治理或重构 skill 本身时；这类任务应使用 `feipi-skill-govern`，不是当前 skill。

## 先确认什么

1. 必填
- `architecture-brief` 文件路径、YAML 内容，或足够补成 brief 的原始需求。
- 图标题、系统摘要、至少 3 个层、至少 3 个组件、至少 1 条跨组件流程。

2. 按需确认
- 是否需要保留图例。
- 哪些内容明确不画进图里，可写入 `out_of_scope`。
- 若用户只有自然语言，先按 `assets/templates/architecture-brief.yaml` 补齐缺失字段，再进入生成。

## 工作流（Explore -> Plan -> Implement -> Verify）

1. Explore：判断当前输入是“完整 brief”还是“原始需求”；如是原始需求，先整理为 brief 草稿。
2. Plan：列出缺失字段、输出文件路径和要执行的校验脚本。
3. Implement：
   - 先用 `python3 scripts/validate_brief.py <brief.yaml>` 做前置校验。
   - 再按 `references/render-rules.md` 生成 `.puml`，要求组件 alias 与 brief 中的 `components[].id` 完全一致。
   - 生成后依次执行：
     - `python3 scripts/check_coverage.py --brief <brief.yaml> --diagram <diagram.puml>`
     - `bash scripts/lint_layout.sh <diagram.puml>`
     - `bash scripts/check_render.sh <diagram.puml> --svg-output <diagram.svg>`
4. Verify：只有在覆盖和布局通过后才能交付；渲染环境不可用时，必须明确写“未完成真实渲染校验”，不能冒充已验证。

## 输入与输出

1. 输入
- 推荐输入：`assets/templates/architecture-brief.yaml` 对应格式的 YAML。
- 备选输入：原始需求描述；此时先补齐 brief，再继续。

2. 输出
- 规范化后的 brief（如本轮有补齐或修正）。
- `.puml` 源码；环境可用时附 `.svg`。
- 一段验证摘要：brief 校验、命名覆盖、布局检查、渲染检查各自是否通过。

## 标准命令

```bash
python3 scripts/validate_brief.py ./brief.yaml
python3 scripts/check_coverage.py --brief ./brief.yaml --diagram ./diagram.puml
bash scripts/lint_layout.sh ./diagram.puml
bash scripts/check_render.sh ./diagram.puml --svg-output ./diagram.svg
```

## 验收标准

1. brief 必须先通过 `scripts/validate_brief.py`，否则暂停生成。
2. 图中必须落地 brief 的层名、组件名、组件 id、流程编号和流程描述，不能私自新增核心组件。
3. 架构图必须使用纵向布局，并通过 `scripts/lint_layout.sh`。
4. 默认要尝试真实渲染；若所有渲染后端都不可用，只能降级为“未完成真实渲染校验”。

## 资源说明

- `assets/templates/architecture-brief.yaml`：人填写的空白模板。
- `assets/examples/architecture-brief.example.yaml`：完整 happy-path 示例。
- `assets/validation/architecture-brief.schema.json`：字段真相。
- `references/brief-fields.md`：字段说明与维护分工。
- `references/render-rules.md`：绘图硬约束。
- `references/anti-patterns.md`：常见失败方式。

## 环境变量约定（如需）

- 渲染脚本复用仓库统一变量 `AGENT_PLANTUML_SERVER_PORT`，默认本地端口为 `8199`。
- 除该变量外，其余路径与输出优先走命令行参数，不新增同义环境变量。
- 字段规则只维护在 `assets/validation/architecture-brief.schema.json` 一处；模板和说明文档不得再重复写一套硬规则。
