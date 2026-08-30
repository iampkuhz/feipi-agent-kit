---
name: feipi-plantuml-generate-diagram
description: PlantUML 唯一作图入口；在用户要求生成架构图、时序图、组件图、活动图、部署图或其他 PlantUML 图时触发，按图型 brief 生成并校验 diagram package。
---

# PlantUML 通用作图生成与校验

## 核心目标

- 作为仓库内唯一 PlantUML 作图入口，覆盖架构图、时序图、组件图、活动图、部署图及其他请求。
- 先识别图类型，再路由到对应 typed profile；识别不了则进入 fallback 模式，不拒绝用户。
- 输出不仅是 `.puml` 源码，还要产出 diagram package（含 `validation.json`），供上游集成。
- 默认消费已经存在的本地 renderer；唯一启动例外是批次 preflight 首次不可用时执行一次固定 Podman 命令。禁止杀死、重启、等待或排查 renderer/proxy 进程。

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

1. **Router**：识别用户意图的图类型，并一次性读取对应 profile 规则。
   - 已注册类型：`architecture`、`sequence`、`component`、`activity`、`deployment` → 进入对应 typed profile。
   - 未注册类型：保留用户请求的 `diagram_type`，但明确进入 `fallback`，不跳过 schema 后伪装成 typed profile。
   - 可推断类型：用户描述包含特定关键词 → 推断后进入对应 typed profile。
   - 不确定类型 → 进入 fallback mode。

2. **Prepare**：补齐并冻结 brief；在渲染前完成 schema、语义和规模预算校验。brief 缺失或超限时直接返回缺口或压缩/拆图建议，不创建图 worker、不调用 renderer。

3. **Preflight**：每个批次只运行一次 `scripts/preflight_renderer.sh`。先探测默认本地地址；不可用时只执行一次固定的 `podman run --rm -d -p 8199:8080 --name plantuml docker.io/plantuml/plantuml-server:jetty`，随后只复检一次。成功后把 `renderer_url` 传给所有图；仍失败则返回 `status: blocked`，不创建 worker、不再操作进程。单图任务也使用同一 preflight。

4. **Generate**：仅在 preflight 成功后生成 `.puml`。typed profile 按图类型执行 brief、跨字段语义、覆盖和布局校验；`sequence` 缺省使用 `interaction_mr`，专利流程使用 `process_s`。fallback 规则见 `references/fallback-mode.md`。

5. **Validate and Repair**：每张图首次生成最多渲染 1 次；仅 `syntax`、`coverage`、`layout` 失败允许针对性修改当前失败图并再渲染 1 次。每张图总渲染上限是 2 次，修复上限是 1 次。修复时只读取 `validation.json`，不重新读取规则；brief 未变时复用冻结校验，只重跑发生变化图的 diagram-dependent checks。

6. **Reuse**：同一输出目录再次验证且 diagram、brief、父 brief、profile 与渲染合同均未变化时，显式增加 `--reuse-valid-package`。命中后不访问 renderer；任一绑定变化则旧合同失效。

## 失败策略

- `brief` / `over_budget`：返回缺失字段或压缩建议，renderer 调用为 0。
- `renderer`：一次固定 Podman 启动和一次复检后仍失败则 `blocked`；不创建 worker、不继续重试或管理进程。
- `syntax` / `coverage` / `layout`：最多修复 1 次；第二次失败后 `blocked`。
- `visual_review`：交给 reviewer；不自动修改、不进入渲染循环。
- `contract` / `retry_limit`：直接 `blocked`，由维护者处理。

## 输入与输出

1. 输入
- 推荐输入：`assets/templates/diagram-brief.yaml` 对应格式的 YAML brief。
- 备选输入：自然语言描述；此时先识别类型，再决定是否补齐 brief。

2. 输出（Diagram Package）

- `diagram.puml` - PlantUML 源码
- `diagram.svg` - 渲染后的 SVG（仅 render_result=ok 时存在）
- `validation.json` - v1.2 验证结果合同；包含 artifact hash、metrics、失败分类、结构化 issues、修复能力、累计 attempt 和 timing/counters
- 可选：`brief.normalized.yaml`
- 批次或单图 preflight：`renderer-preflight.json`

## 验收标准

1. 必须产出 `validation.json`，不可口头声称成功。
2. fallback 模式下 `.puml` 必须包含 `@startuml` 与 `@enduml`。
3. typed profile 模式下必须执行对应的 brief 校验和覆盖校验。
4. 渲染可用时必须产出 `diagram.svg`。
5. 若 `render_result` 不为 `ok`、renderer 身份缺失或当前 SVG 不存在，`final_status` 必须为 `blocked`；不可复用旧 SVG。
6. `scripts/validate_package.sh` 已内置 `scripts/verify_package.py`，会双向复核 v1.2 路径、hash、状态与实际 PUML metrics；不要再手工调用 verifier。
7. `max_render_attempts=2` 表示首次生成 1 次、针对性修复 1 次，不是 2 次重试；未修改的失败图不得重复渲染。
8. `timings` / `counters` 保留最近一次完整生成数据，`last_run_timings` / `last_run_counters` 记录本次实际调用；上游应优先消费后者。命中复用时 `render_ms=0`、renderer 请求与轮次均为 0，并单独记录 cache hit，不得把首次生成的历史数据当作本次调用。

重复执行示例：

```bash
bash scripts/preflight_renderer.sh --out renderer-preflight.json
bash scripts/validate_package.sh --diagram-type component --brief brief.yaml --diagram diagram.puml --out-dir package --server-url http://127.0.0.1:8199
```

## 资源说明

- `assets/templates/diagram-brief.yaml`：通用 brief 空白模板。
- `assets/templates/types/`：五种已注册 typed profile 的 brief 模板。
- `assets/examples/fallback/fallback-brief.example.yaml`：fallback 模式示例 brief。
- `assets/examples/fallback/fallback-diagram.example.puml`：fallback 模式示例图。
- `assets/server_candidates.txt`：PlantUML server 候选地址。
- `scripts/preflight_renderer.sh`：批次级 renderer 预检；首次不可用时只允许一次固定 Podman 启动和一次复检。
- `references/type-routing.md`：类型识别与路由规则。
- `references/fallback-mode.md`：兜底模式工作流与校验要求。
- `references/diagram-type-profiles.md`：typed profile 注册表与接口约定。
- `references/render-rules.md`：通用渲染规则。
- `references/anti-patterns.md`：常见失败方式。
- `references/expansion-playbook.md`：新增图类型的标准流程。

## 环境变量约定

- 渲染脚本复用仓库统一变量 `AGENT_PLANTUML_SERVER_PORT`，默认本地端口为 `8199`。
- 除该变量外，其余路径与输出优先走命令行参数。
- 默认地址只使用 `127.0.0.1`；显式地址也必须是 loopback。
- Podman 启动默认最多等待 30 秒，启动成功后等待 1 秒再复检；可用 `PLANTUML_PODMAN_START_TIMEOUT_SECONDS` 与 `PLANTUML_PODMAN_READINESS_DELAY_SECONDS` 收紧测试环境时限。
