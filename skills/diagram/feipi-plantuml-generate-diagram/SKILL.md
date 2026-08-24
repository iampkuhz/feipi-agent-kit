---
name: feipi-plantuml-generate-diagram
description: PlantUML 通用作图入口；在用户要求生成架构图、时序图、组件图、活动图、部署图或其他 PlantUML 图时触发，并输出带校验合同的 diagram package；若用户明确指定旧架构图或时序图兼容 skill，优先使用对应兼容入口。
---

# PlantUML 通用作图生成与校验

## 核心目标

- 作为仓库内 PlantUML 通用作图入口，覆盖架构图、时序图、组件图、活动图、部署图及其他请求。
- 先识别图类型，再路由到对应 typed profile；识别不了则进入 fallback 模式，不拒绝用户。
- 输出不仅是 `.puml` 源码，还要产出 diagram package（含 `validation.json`），供上游集成。

## 适用场景

- 用户说"用 PlantUML 画个图"，未指定具体图类型。
- 用户明确说"画架构图"、"画时序图"、"画组件图"、"画活动图"或"画部署图"等。
- 用户描述中包含"参与者、调用、返回"（推断 sequence）或"层、组件、依赖"（推断 architecture）。
- 用户已有 YAML brief，希望直接生成并校验。

## 不适用场景

- 目标产物是 Mermaid、Draw.io、Excalidraw 等非 PlantUML 格式。
- 只要文字分析或流程建议，不需要可渲染 PlantUML。
- 需要治理或重构 skill 本身时，应使用 `feipi-skill-govern`。

## 先确认什么

1. 必填
- 用户要画的图内容（自然语言或 brief YAML）。
- 若提供 brief，须包含 `diagram_type` 字段。

2. 按需确认
- 是否需要分层/分组。
- 哪些内容不画进图里（`out_of_scope`）。

## 工作流

1. **Router**：识别用户意图的图类型。
   - 已注册类型：`architecture`、`sequence`、`component`、`activity`、`deployment` → 进入对应 typed profile。
   - 未注册类型：保留用户请求的 `diagram_type`，但明确进入 `fallback`，不跳过 schema 后伪装成 typed profile。
   - 可推断类型：用户描述包含特定关键词 → 推断后进入对应 typed profile。
   - 不确定类型 → 进入 fallback mode。

2. **Typed Profile**：按图类型执行 brief、跨字段语义、覆盖、布局与渲染校验。`sequence` 缺省使用 `interaction_mr`；专利流程使用 `process_s`，禁止 `M/R` 与 `S` 混用及 `autonumber`。详见 `references/diagram-type-profiles.md`。

3. **Fallback Mode**：不强制 typed brief，生成最小可渲染 `.puml` 并完成基础校验。详见 `references/fallback-mode.md`。

4. **Verify**：每份图包只通过 `scripts/validate_package.sh` 完成一次静态检查、渲染和内置 verifier；不要再手工重复调用 `verify_package.py`。只有 `validation.json` 中 `final_status=success` 且 `render_result=ok` 时，skill 才算完成。

5. **Reuse**：同一输出目录再次验证且 diagram、brief、父 brief、profile 与渲染合同均未变化时，显式增加 `--reuse-valid-package`。脚本会先重算现有图包的路径、hash、metrics 与 SVG 合同；命中后不再访问 renderer，任一项变化则自动回退完整校验。

## 输入与输出

1. 输入
- 推荐输入：`assets/templates/diagram-brief.yaml` 对应格式的 YAML brief。
- 备选输入：自然语言描述；此时先识别类型，再决定是否补齐 brief。

2. 输出（Diagram Package）

- `diagram.puml` - PlantUML 源码
- `diagram.svg` - 渲染后的 SVG（仅 render_result=ok 时存在）
- `validation.json` - v1.1 验证结果合同；包含相对 artifact 路径、原始/规范化 hash、静态 metrics、`render_contract_version`，以及当前/最近完整运行的 timing 与调用计数
- 可选：`brief.normalized.yaml`

## 验收标准

1. 必须产出 `validation.json`，不可口头声称成功。
2. fallback 模式下 `.puml` 必须包含 `@startuml` 与 `@enduml`。
3. typed profile 模式下必须执行对应的 brief 校验和覆盖校验。
4. 渲染可用时必须产出 `diagram.svg`。
5. 若 `render_result` 不为 `ok`、renderer 身份缺失或当前 SVG 不存在，`final_status` 必须为 `blocked`；不可复用旧 SVG。
6. `scripts/validate_package.sh` 已内置 `scripts/verify_package.py`，会双向复核 v1.1 路径、hash、状态与实际 PUML metrics；任何包内文件变化都必须使旧合同失效。
7. 成功路径只请求一次 SVG endpoint；语法错误依据 PlantUML 响应头或错误 SVG 根元数据识别，不扫描用户可见文字。单张已变图默认最多修复并重渲染 2 轮，只重跑发生变化的图。
8. `timings` / `counters` 保留最近一次完整生成数据，`last_run_timings` / `last_run_counters` 记录本次实际调用；上游应优先消费后者。命中复用时 `render_ms=0`、renderer 请求与轮次均为 0，并单独记录 cache hit，不得把首次生成的历史数据当作本次调用。

重复执行示例：

```bash
bash scripts/validate_package.sh --diagram-type component --brief brief.yaml --diagram diagram.puml --out-dir package --reuse-valid-package
```

## 资源说明

- `assets/templates/diagram-brief.yaml`：通用 brief 空白模板。
- `assets/templates/types/`：五种已注册 typed profile 的 brief 模板。
- `assets/examples/fallback/fallback-brief.example.yaml`：fallback 模式示例 brief。
- `assets/examples/fallback/fallback-diagram.example.puml`：fallback 模式示例图。
- `assets/server_candidates.txt`：PlantUML server 候选地址。
- `references/type-routing.md`：类型识别与路由规则。
- `references/fallback-mode.md`：兜底模式工作流与校验要求。
- `references/diagram-type-profiles.md`：typed profile 注册表与接口约定。
- `references/render-rules.md`：通用渲染规则。
- `references/anti-patterns.md`：常见失败方式。
- `references/expansion-playbook.md`：新增图类型的标准流程。

## 环境变量约定

- 渲染脚本复用仓库统一变量 `AGENT_PLANTUML_SERVER_PORT`，默认本地端口为 `8199`。
- 除该变量外，其余路径与输出优先走命令行参数。
