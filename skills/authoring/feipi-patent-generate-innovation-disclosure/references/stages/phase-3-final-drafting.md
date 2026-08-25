# 阶段 3：最终撰写与制图

> 仅供阶段 3 主 agent 加载。单图 subagent 不读取本文件；它只读取单图任务包、`references/roles/diagram-engineer.md` 和直接依赖的 PlantUML skill。

## 输入与按节点加载

只读取已封存的 `phase-2/handoff.md`。正常情况下不读取原始材料、阶段 1/2 guide、竞品网页、质量总表、handbook 或案例。

模板不得在阶段开始一次性加载：

- `public-draft` 节点才加载 `assets/proposal_template.md`。
- `manifest` 节点才加载 `assets/disclosure-manifest.template.json`；schema 交给 validator，不作为写作上下文整体读取。
- `internal-draft` 节点才加载 `assets/internal_trace_appendix_template.md`。

## 中心计划屏障

主 agent 先生成并冻结：

- `phase-3/content-core.json`：标题、场景、核心主张、关键词、I/T、实现/扩展边界、竞品结论和公开字段真源。
- `phase-3/diagram-plan.json`：每图 `diagram_id`、唯一目的、profile、职责、实现范围、D/E/S 分配、父组件、依赖和独占输出目录。

两项都通过最低检查后才能启动正文和逐图并行。图计划必须满足：

- `component_overview` 与 `main_flow` 各恰好一张。
- 分支/状态驱动主流程用 activity；多方调用/回执驱动用 sequence + `process_s`。
- 跨网、跨链、在线/离线、HSM、人工摆渡或交接时增加 `deployment_boundary`。
- `module_detail` 每张只展开一个父组件；`core_mechanism` 只有独立目的时才生成。
- 默认两张必需图，不为凑数加图；图只呈现已实现路径，扩展保护不进入 PUML/SVG。
- `D1...Dn`、`E1...En`、`S1...Sn`/`Sx.y` 由中心计划统一分配，专利图不得出现 M/R。

`diagram-plan.json.diagrams[]` 的 `output_dir` 必须精确为 `disclosure-workspace/diagrams/<Dn>-<purpose>`，purpose 使用小写连字符。

## 正文与逐图并行

主 agent 从 `content-core.json` 撰写根部唯一对外稿 `disclosure.md`。每张图先预生成 `stages/agents/inputs/diagram-Dn-input.json` JSON envelope：`slice_version=1`、与任务包一致的 `task_type` / `role` / `checkpoint`、`diagram_id`、`purpose`、`diagram_plan_sha256`、`source_set_sha256` 和对象型 `payload`。source set 只含 `content-core.json` 与 `diagram-plan.json`；路径去重后按 UTF-8 字典序排序，逐项输入 `path + NUL + 当前文件 sha256 + LF` 再取 SHA-256。`payload` 只含当前 D 的职责、必要公开字段、已实现路径、D/E/S 和独占目录；worker 禁止读取完整中心文件。

主 agent 为每张图生成独立三段式任务包；“需要判断/返回”只能分别写 `JUDGMENT-DIAGRAM-Dn-V1` / `RETURN-DIAGRAM-Dn-TSV-V1`，不得内嵌上下文、JSON、路径或 URL。派发或 fallback 前运行：

```bash
python3 scripts/stage_handoff.py validate-task --working <disclosure-workspace/working> --task stages/agents/diagram-Dn-task.md
```

校验成功会原子写入 `stages/agents/receipts/diagram-Dn-task.dispatch.json`，绑定任务 hash、当前 TaskSpec 与动态输入集合 hash；失败或 receipt 缺失/过期不得启动。subagent 只加载任务包、Dn envelope、diagram guide 和 `$feipi-plantuml-generate-diagram`。每个 worker 只写自己的图包目录并返回一行；主 agent 校验后写 `phase-3/diagrams/Dn-result.tsv`。若 subagent 不可用，主 agent 仅为当前 Dn fallback 加载同一集合。

`workspace_write` / `result_owner=main_agent` 是行为合同，不等于宿主已施加独占写目录或证明真实写入者。宿主不能施加时仍按合同执行，并在真实 trace 核验；本地校验只证明声明、receipt 和工件一致。

正文合同：

- 标题、场景、核心主张、关键词和 I/T 公开字段从 `content-core.json` 原样渲染。
- 每个创新点连续呈现“对比基线 → 已实现处理方式 → 实质差异 → 价值因果 → 可观察效果”，不能只剩处理方式。
- 已实现基础保留泛化后的真实对象、动作、状态、接口和约束，不显示 SF/EM、来源定位或内部实现名。
- 每个可选扩展使用不带 IE 编号的 `> **拟扩展保护**` 引用块；无扩展不显示空块。
- 关键词共 5–8 个：技术对象 1–2、核心机制 2–4、关键约束 1–2，三组互斥。
- 顶层组件只放业务域、独立系统和物理端点；流程顶层连续 5–10 步，长参数和异常解释放图下。
- 竞品章节展示实际检索范围、日期和结论；有可靠证据才列 1–3 项，无证据时写明已查范围和无法形成具名对比的原因，不写“待检索”。
- 每个 PlantUML 块前写唯一 `<!-- diagram-id: Dn -->`，内嵌 PUML 与图包同源。

## 汇合顺序

1. 主 agent 校验所有逐图结果，再生成唯一 `diagram-result.tsv`；写 `Dn-result.tsv`、聚合 `diagram-result.tsv` 和 `build-map.tsv` 前，必须复算对应 `<output_dir>/diagram.svg` 当前实际 SHA-256，并把三类 D 行的 `sha256` 写成同一值，不得使用虚构 package hash。缺任一计划图时不得 join。
2. 对外稿和图 join 都完成后，生成 manifest；公开字段必须与正文一致，图路径相对工作区且 hash 对应当前图包。
3. 复制完整对外正文形成 `disclosure-workspace/disclosure-internal.md`，只在文末按内部附录模板追加 SF/IE/EM 与 I/T 追溯，不维护第二套公开正文。
4. 生成 `build-map.tsv`，记录最终工件路径、SHA-256、owner 和状态。
5. 写 `phase-3/handoff.md`，只传 build map 和待复核项，不复制正文、manifest、PUML 或 SVG。

图包自身验证由单图 worker 调用一次 `validate_package.sh` 完成；不得重复手工调用 verifier。未变化图包用 `--reuse-valid-package`；brief/PUML/SVG 变化才重跑对应图，修复最多 2 轮。

## 完成与回退

- 所有图汇合前不得完成 manifest、build map 或启动阶段 4。
- 某图失败时保留该图 pending，只修该图；其他有效图与正文不回滚。
- 已冻结 I/T/D/E/S 或图职责变化时，主 agent 判断回退阶段 2 或 3，不能在 worker 内私改全局编号。
- 正文、图包、manifest、内部稿和 build map 完成最低检查后封存；seal 会复验所有逐图 dispatch receipt 并纳入 cache digest，receipt 缺失或过期不得封存。可进入终审时最多上报一条 `MILESTONE`。
