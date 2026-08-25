# 阶段交付与上下文压缩合同

本合同约束四个大阶段、六个 subagent role 模板及其动态实例的输入、判断、缓存和输出。目标是让每个阶段只读取完成本阶段所需的最小信息，并能在跨轮次恢复时从文件继续，而不是依赖完整对话或重复打开原始材料。

## 1. 固定目录与紧凑格式

内部过程文件统一放在 `disclosure-workspace/working/stages/`：

```text
stages/
├── stage-state.tsv
├── shared/
│   ├── material-index.tsv
│   └── evidence-cards.md
├── agents/
│   ├── subject-boundary-task.md
│   ├── prior-art-object-task.md
│   ├── prior-art-mechanism-task.md
│   ├── innovation-value-task.md
│   ├── diagram-Dn-task.md
│   ├── semantic-review-task.md
│   └── visual-review-Dn-task.md
├── phase-1/
│   ├── analysis-plan.json
│   ├── delivery-goals.md
│   ├── subject-boundary.tsv
│   ├── research-object.tsv
│   ├── research-mechanism.tsv
│   ├── innovation-candidates.tsv
│   ├── model.md
│   ├── research.tsv
│   └── handoff.md
├── phase-2/
│   ├── decision.md
│   └── handoff.md
├── phase-3/
│   ├── content-core.json
│   ├── diagram-plan.json
│   ├── diagrams/Dn-result.tsv
│   ├── diagram-result.tsv
│   ├── build-map.tsv
│   └── handoff.md
└── phase-4/
    ├── review-plan.json
    ├── semantic-review.tsv
    ├── visual/Dn-review.tsv
    ├── review.tsv
    └── handoff.md
```

- TSV 用于重复记录，只写一次表头；单元格必须是短标量，换行写成 `\\n`，不得在单元格内嵌套 JSON。
- Markdown 用于少量需要人读的结论；不复制整篇原文、完整网页、长日志、完整正文或完整 manifest。
- 所有路径均相对 `disclosure-workspace/working/`，禁止绝对路径、`..` 和符号链接越界。
- `handoff.md` 不超过 24 KiB，只传稳定 ID、相对路径、SHA-256、已确认决策和阻塞项。subagent 任务文件不超过 12 KiB。详细事实只在 `evidence-cards.md` 保存一份。
- `stage-state.tsv` 为每阶段绑定输入 hash、阶段缓存聚合 hash 和 handoff hash。上游原始材料、缓存或封存 handoff 的 hash 变化时，下游状态全部失效；旧文件可保留作缓存，但重新封存前不得作为当前输入。

固定 TSV 表头如下：

```text
material-index.tsv: source_id\tsource_type\tpath_or_locator\tsha256\trelevant_anchors
research.tsv:       lane\tquery_id\tsource_id\tevidence_status\tlocator\tconclusion
subject-boundary.tsv: subject_id\ttechnical_object\tuse_scenario\tbusiness_domain\tsystem_owner\tphysical_boundary\timplemented_scope\textension_scope\tcore_mechanism
innovation-candidates.tsv: candidate_id\tsource_fact_ids\textension_ids\tproblem\tmechanism\tconstraint\tbaseline\tdifference_hypothesis\tvalue_chain\teffect\tvalidation_status\tdiagram_landing
build-map.tsv:      artifact_id\tpath\tsha256\towner\tstatus
diagram-result.tsv: artifact_id\tpath\tsha256\towner\tstatus
review.tsv:         artifact_id\treview_type\tstatus\tbound_sha256\tconclusion
```

阶段计划 JSON 的最小合同：

- `diagram-plan.json.diagrams[]`：每项包含 `diagram_id`、小写连字符 `purpose`、`output_dir`；目录必须精确等于 `disclosure-workspace/diagrams/<Dn>-<purpose>`。
- `review-plan.json.diagrams`：只包含连续的 `D1...Dn`；正文、manifest 等非图工件使用其他字段，不能混入逐图数组。

每个 `handoff.md` 的前四行固定为：

```text
handoff_version: 1
from_stage: <当前阶段>
to_stage: <下一阶段或 delivery>
status: <ready|confirmed|built|reviewed>
```

正文只允许三个二级标题：`决策摘要`、`传递索引`、`未决项`。`传递索引`引用本阶段缓存，不重复缓存内容；没有未决项时明确写“无”。

## 2. 四阶段交付矩阵

| 阶段 | 允许读取的原始材料 | 接受的结构化输入 | 本阶段判断 | 必须缓存的内部文件 | 传给下一阶段 |
|---|---|---|---|---|---|
| 阶段 1 素材确认与建模 | 用户消息、用户文件、明确范围内的代码、实际打开的公开检索页 | 无；首次执行先建材料索引 | 输入门槛、SF/IE/EM 边界、技术主体、交付目标、问题/机制/约束、候选 I/T、两线检索是否充分 | 材料索引、事实卡、分析计划、主体边界、双线检索、创新价值、规范化模型与 handoff | 核心主张、候选 I/T、实现/扩展边界、证据结论、缺口、候选图职责；只给 ID 和缓存定位 |
| 阶段 2 思路确认 | 仅用户本轮新增的确认、否决或补充；不得重读既有原始材料 | `phase-1/handoff.md` 及其中点名的 `model.md` 条目 | 是否得到明确确认；冻结哪些 I/T/D/E/S；用户调整是否导致阶段 1 事实或检索失效 | `phase-2/decision.md`、`phase-2/handoff.md` | 已确认且冻结的 I/T/D/E/S、实现/扩展边界、图示职责、所需模板、未决阻塞项 |
| 阶段 3 最终撰写 | 正常情况下不读原始材料；只有用户新增材料使阶段 1 失效时才回退 | `phase-2/handoff.md`；按需加载三份正式模板 | 共同内容真源、中心图计划、编号一致性、正文/内部稿/manifest/图包同源关系 | `content-core.json`、`diagram-plan.json`、逐图结果、聚合结果、最终工件、build map 与 handoff | 最终工件的相对路径、hash、owner、状态和待复核项；不得复制完整正文或图源码 |
| 阶段 4 复核与交付 | 正常情况下不读原始材料，也不重读网页 | `phase-3/handoff.md` 及 `build-map.tsv` 指向的最终工件；按需加载相关质量门禁 | 语义复核、逐图视觉复核、hash 绑定与确定性校验状态 | `review-plan.json`、语义/逐图视觉结果、聚合 `review.tsv`、validation 与 handoff | 给用户的工件路径、最终状态、警告、验证边界和 timing summary 路径 |

## 3. 阶段执行规则

1. 每阶段开始先运行 `status`，只读取它给出的 `next_input`；阶段结束写完缓存后再 `seal`。跨轮次恢复不重放旧推理，只从最后一个有效 handoff 继续。
2. 阶段 1 对每份原始材料只读取一次，并用 `source_id + sha256 + relevant_anchors` 建索引。`evidence-cards.md` 只摘录会进入主张、I/T、检索词或边界判断的证据；事实卡与分析计划完成前不得派发 subagent。完成后主体边界与两条研究 lane 并行，交付目标由主 agent 同时整理；创新价值必须等待这些结果汇合。
3. 阶段 2 的写作思路必须落入 `decision.md`，不能只留在对话。用户补充新事实时先更新材料索引并回退阶段 1；只有对既有候选的确认或取舍可以直接封存阶段 2。
4. 阶段 3 只依据已冻结 handoff 工作。主 agent 先冻结 `content-core.json` 与 `diagram-plan.json`；正文与逐图生成可以并行，各图写入独立目录和结果文件。所有图汇合前不得生成最终 manifest hash，也不得启动阶段 4。
5. 阶段 4 只复核 `build-map.tsv` 绑定的 hash。语义与逐图视觉复核并行，主 agent 汇合后才执行完整校验；任一工件变化后，主 agent 必须显式回退到受影响阶段，使相应复核和阶段 4 handoff 失效，禁止沿用旧结论。第一版不做自动依赖分析。
6. 长分析只在当前阶段内发生，缓存只保留结论、证据定位和未决项。禁止把完整对话、长检索日志或上一阶段的推理过程传入下一阶段或 subagent。

## 4. subagent 三段式交付

每个 subagent 的任务文件都只包含 `输入`、`需要判断`、`返回` 三节，并写明 role、输入引用（阶段 1 使用材料索引，其余阶段使用上游 handoff）、允许写入和 timing log；`返回` 中必须声明统一关键事件合同。派发使用 `fork_turns: none`，消息中只给任务文件路径，不复制任务文件内容。

角色的模型、effort、权限和实例上限以 `agents/subagents/roles/` 为机器真源；本节只说明业务交接。

### `patent_subject_boundary_analyst`

- 输入：`agents/subject-boundary-task.md`；只引用事实卡和 `analysis-plan.json`，不读取原始材料。
- 需要判断：技术对象、场景、业务/系统/物理边界及已实现与拟扩展范围。
- 返回：`subject-boundary.tsv` 数据行和一行终态事件；只提供候选边界，不冻结最终主张。

### `patent_prior_art_researcher`

- 输入：对象/场景或机制/问题的独立任务包；每个实例只处理一条检索线，不含完整原始材料。
- 需要判断：候选页面相关性、证据属性、是否足以说明该线行业基线、何时停止扩散。
- 返回：各自 `research-object.tsv` 或 `research-mechanism.tsv` 数据行和一行终态事件；不得共同追加文件，主 agent 汇合为唯一 `research.tsv`。

### `patent_innovation_value_analyst`

- 输入：`agents/innovation-value-task.md`；只引用主体边界、交付目标、canonical `research.tsv` 和事实卡的稳定 ID/hash。
- 需要判断：问题—机制—约束、差异假设、价值因果、候选效果和图示落点。
- 返回：`innovation-candidates.tsv` 数据行和一行终态事件；正式核心主张与 I/T 仍由主 agent 收敛。

### `patent_diagram_engineer`

- 输入：单张 `agents/diagram-Dn-task.md`；只引用冻结的 `diagram-plan.json` 对应条目及该图独占目录。
- 需要判断：单图 brief、布局、编号落地和“仅呈现已实现路径”是否成立；不得重判其他图职责或全局编号。
- 返回：单张 `phase-3/diagrams/Dn-result.tsv` 和一行终态事件；图文件直接写入自己的目录，不在消息中回传 PUML/SVG。主 agent 汇合为不可变 `diagram-result.tsv`。

### `patent_semantic_reviewer`

- 输入：`agents/semantic-review-task.md`；只引用阶段 3 handoff、正文/manifest hash 和相关质量门禁。
- 需要判断：实现/扩展边界、泛化、因果删除、创新—价值、内外泄漏和图文 ID 一致性，不判断 SVG 布局。
- 返回：`semantic-review.tsv` 数据行和一行终态事件，不回传正文副本或逐步推理。

### `patent_visual_reviewer`

- 输入：单张 `agents/visual-review-Dn-task.md`；只引用该图 SVG、validation、brief、冻结职责和 hash。
- 需要判断：交叉、遮挡、唯一职责和“仅呈现已实现路径”，不重复语义审查。
- 返回：单张 `phase-4/visual/Dn-review.tsv` 和一行终态事件；主 agent 汇合为唯一 `review.tsv`。

## 5. 关键事件与非轮询汇合

### 5.1 关键事件定义

主 agent 和 subagent 只允许上报以下四类事件：

- `MILESTONE`：阶段 handoff 已封存，或关键工件已经通过自身合同并可供下游消费。它不用于报告开始、进度比例或普通中间步骤；同一 scope、同一结果最多上报一次。
- `DECISION`：必须由接收方作出选择，且不同选择会改变核心主张、实现/扩展边界、证据范围、图示职责或最终交付状态。必须写清选择点和接收方需要做的动作。
- `BLOCKED`：缺少必要输入、权限或工具能力，合同相互冲突，或必做门禁失败，导致当前职责不能继续。必须写清影响和解除阻塞所需动作。
- `COMPLETE`：当前 subagent 的全部职责已经闭环，或主任务最终交付完成。每个 subagent 最终必须以 `COMPLETE` 或终态 `BLOCKED` 收口；最终响应本身就是该事件，不再重复发送同内容通知。

`STARTED`、`RUNNING`、`HEARTBEAT`、空泛 `STATUS`、工具调用、文件读写、缓存命中、无变化等待、预算内重试和“仍在处理”均为静默事件。等待超时本身不构成 `BLOCKED`，也不能触发心跳。宿主强制的首次操作说明不计入事件流；宿主要求长任务更新时，只能上报已经完成且可验证的结果，不得虚构 `MILESTONE`。

分类发生重叠时按结果判断：当前职责已经全部闭环就使用 `COMPLETE`，不再使用 `MILESTONE`；接收方作出明确选择即可解除停滞时使用 `DECISION`，没有可供接收方选择的解除路径时才使用 `BLOCKED`。未注册的事件类型视为合同错误，主 agent 拒绝转发给用户，不把它降级成普通状态消息。

### 5.2 必须上报的触发点

- 主 agent：阶段 2 提交写作思路等待确认时，用一条 `DECISION` 合并说明核心主张、主要边界和需要用户确认的选择，不再另发同结果 `MILESTONE`；阶段 3 正文与图包汇合且可进入终审时，最多上报一条 `MILESTONE`；阶段 4 需要用户取舍时上报 `DECISION`，必做门禁失败且无法继续时上报 `BLOCKED`，最终正式答复承担主任务 `COMPLETE`。
- subagent：遇到任务包外且会改变结果的选择时立即上报 `DECISION`；当前职责无法继续时上报 `BLOCKED`；只有确有可供主 agent 提前消费的已验证工件时才允许一次 `MILESTONE`；职责闭环时以 `COMPLETE` 最终响应收口。研究、制图和终审的普通中间步骤都不单独上报。
- 主 agent 收到 subagent `COMPLETE` 后，若下游可以直接继续且用户无需行动，只更新内部状态；到阶段边界再与其他结果合并展示，不能机械转发每个 worker 的完成消息。

### 5.3 上报路径与紧凑格式

- subagent 只向主 agent 上报；主 agent 校验并聚合后，只把会改变用户下一步或交付有效性的事件展示给用户。不得把 subagent 的 TSV、正文、图源码、日志或推理原样转发给用户。
- subagent 事件 envelope 固定为一行：`[<EVENT>] <scope>｜<outcome>｜<next_or_artifact>`，不超过 240 个字符；详细 TSV 数据仍按既有返回合同交给主 agent，不塞入事件行。
- 主 agent 的用户可见上报同样只用一句“结果 + 下一步”；同一 `event + scope + outcome` 只展示一次。多个 subagent 事件若属于同一阶段，优先在阶段边界合并为一条。
- `MILESTONE` 后若紧接着就是相同结果的 `COMPLETE`，只保留 `COMPLETE`；最终交付通过正式答复完成，不额外发送一条空泛完成进度。

### 5.4 等待纪律

1. subagent 通过宿主事件通道主动上报；主 agent 不定时拉取状态。
2. 派发后主 agent 先执行不依赖该 subagent 的本地工作。到依赖汇合点且确实无其他工作时，才允许长时、事件驱动等待。
3. 禁止短间隔重复调用 `wait`，以及使用 `list`、`status`、`read` 或 `sleep` 组合轮询。若宿主因非终态超时结束一次长等待且 worker 仍在运行，可以在同一依赖屏障继续长时事件等待，但中间不得查询状态、发送心跳或改成短周期等待。
4. 非终态等待到期不是 subagent 失败。只有宿主明确返回失败或超时终态、事件负载不合合同，或任务截止条件真正到达时，主 agent 才能记录 `BLOCKED`，并选择接管或最多重派一次。
5. 阶段 2 等待用户确认时结束当前对话轮次；这不是 `subagent_wait`，也不得通过消息或工具循环催询。

## 6. 稳定性与失效边界

- 只有已封存的上游 handoff 才能启动下一阶段或 subagent。主 agent 在派发前校验输入 hash，汇合后再次校验输出路径与 hash。
- 并行组固定为：阶段 1 的主体边界 + 两条独立研究 lane（主 agent 同时整理交付目标）、阶段 3 的主正文 + 逐图生成、阶段 4 的语义 + 逐图视觉复核。阶段 2 禁止 subagent；未列出的任务保持串行。
- 全局同时最多 3 个 subagent；diagram 与 visual role 各使用最多两个长期 worker，收到终态事件后再派下一图，不轮询空闲状态。单图写入路径与单图结果必须独占。
- 宿主明确返回 subagent 失败或超时终态，或返回格式不合同时，不把半成品写入共享 TSV，也不启动下游；由主 agent 最多重派一次或接管同一职责。普通事件等待到期不得触发立即重派。
- 使用 `scripts/stage_handoff.py` 管理封存链：

```bash
python3 scripts/stage_handoff.py init --working <disclosure-workspace/working>
python3 scripts/stage_handoff.py status --working <disclosure-workspace/working>
python3 scripts/stage_handoff.py seal --working <disclosure-workspace/working> --stage phase_1_material_modeling
python3 scripts/stage_handoff.py rewind --working <disclosure-workspace/working> --stage phase_1_material_modeling
python3 scripts/stage_handoff.py validate --working <disclosure-workspace/working> --require-complete
```

`seal` 只承认合同登记的固定缓存、按冻结图计划展开的逐图任务/结果、聚合 TSV、hash 绑定和 handoff 头；阶段 3/4 的 D 集合、逐图目录、成功状态及语义/视觉汇合不完整时不得封存。上游 hash 变化时从 `stage-state.tsv` 删除下游有效状态，但不删除缓存文件。`rewind` 只接受主 agent 已经明确选择的阶段，验证并保留其上游封存前缀，再删除所选阶段及下游封存行；它不删除缓存，也不推断回退阶段。`validate` 负责发现篡改、断链、越界、缺文件和超大 handoff，不判断专利内容质量。

## 7. 任务检查点与恢复

### 7.1 文件职责与固定内容

任务运行时必须维护 `<disclosure-dir>/disclosure-workspace/working/CHECKPOINT.md`。该文件只表示当前状态，不保存历史事件；每次允许更新时都原子重写，并固定包含：

1. 当前阶段和阶段状态。
2. 本阶段输入：只列相对 `<disclosure-dir>` 的文件或稳定输入说明。
3. 本阶段任务：每项包含稳定 task id、owner、唯一结果文件、最低检查类型和完成状态。
4. 当前阶段已交付：只列已经通过完成门禁的 task id、结果路径、最低检查类型和绑定 SHA-256。
5. 下一步：一个可以直接执行的任务或需要接收方完成的动作。
6. 阻塞项：没有时明确写“无”；等待用户只写入状态与“下一步”，不能放在阻塞项中。

任务粒度只能是“一个阶段交付物”或“一个 subagent 职责”。读取材料、调用工具、生成中间片段、重试和普通校验步骤都不能单独登记为任务，也不能进入“当前阶段已交付”。

CHECKPOINT 由 `scripts/checkpoint.py` 规范渲染并内嵌机器状态，禁止手工编辑。task id 必须稳定且阶段内唯一；owner 使用 `main_agent` 或对应 subagent role 等小写稳定标识。标准调用为：

```bash
python3 scripts/checkpoint.py start-stage --root <disclosure-dir> \
  --stage <phase_name> --input "<输入或相对路径>" \
  --task <task-id> "<标题>" <owner> <result-path> <nonempty|markdown|json|tsv>

python3 scripts/checkpoint.py complete-task --root <disclosure-dir> --task <task-id>
python3 scripts/checkpoint.py wait-user --root <disclosure-dir> --reason "<等待选择>"
python3 scripts/checkpoint.py block --root <disclosure-dir> --reason "<阻塞及解除动作>"
python3 scripts/checkpoint.py resume --root <disclosure-dir>
python3 scripts/checkpoint.py validate --root <disclosure-dir>
```

`--input` 和 `--task` 均可重复。全新任务第一次 `start-stage` 只能选择阶段 1；重新进入同一阶段时，输入和任务定义必须与当前 CHECKPOINT 一致；定义变化只能使用带原因的 `rollback-stage`。新阶段只能按固定四阶段顺序开始，不能跳过中间阶段。

### 7.2 完成门禁

- 每项任务只绑定一个相对交底目录的结果文件；禁止绝对路径、`..` 和符号链接越界。
- 标记完成前必须确认文件存在、非空，并通过任务声明的最低检查：`nonempty` 只检查非空，`markdown` 检查非空 Markdown，`json` 检查可解析 JSON，`tsv` 检查非空且列数一致的 TSV。
- 完成时记录当前文件 SHA-256。未通过门禁时命令失败且不得修改 CHECKPOINT，也不得把任务加入“当前阶段已交付”。
- 阶段内允许并行的主 agent / subagent 任务可按真实完成顺序分别登记，不要求 completed 形成有序前缀；`resume` 仍按任务清单顺序返回第一个 pending 或失效任务，并跳过其他仍然有效的已交付任务。
- 最低检查仅证明结果文件具备可消费的基本格式。阶段 handoff 仍需 `stage_handoff.py seal`，图包仍需自身 validator，正式交底仍需完整交付校验，内容语义仍需人工复核。

### 7.3 更新时机

CHECKPOINT 只允许在以下四类时机更新：

- 阶段开始：写入当前阶段、输入、完整任务清单、下一步，并清空旧阶段交付。
- 任务完成：结果通过门禁后勾选任务、绑定 hash、加入当前阶段已交付，并指向下一个未完成任务。
- 等待用户：记录 `waiting_user` 和用户必须作出的具体选择，然后结束当前对话轮次。
- 发生阻塞：记录 `blocked`、影响和解除动作；普通重试、等待超时或无状态变化不构成阻塞。

写入等待或阻塞前重新检查已交付结果；已经缺失、为空、格式无效或 hash 改变的任务降回 pending 并移出“当前阶段已交付”，不能因旧勾选继续保留。完全相同的阶段开始、回退、等待或阻塞请求视为幂等 no-op，不重写文件时间戳。

禁止为阶段内微步骤、工具调用、文件读写、subagent 普通事件、缓存命中、预算内重试、恢复扫描或重复进度更新 CHECKPOINT。关键事件是否向用户展示仍由第 5 节决定；CHECKPOINT 更新本身不自动产生用户可见消息。

### 7.4 恢复顺序

1. 恢复时先运行 checkpoint `validate` / `resume`，不得先重放对话、重读原始材料或轮询 subagent。
2. 按任务清单顺序检查 pending 和已完成结果的文件、最低格式及绑定 hash；有效完成项跳过，返回第一个 pending 或失效任务。处于 `waiting_user` / `blocked` 时，如果第一可执行项本来就是 pending，则保持暂停状态；只有排在它之前的已交付项失效时，才优先返回 `redo`。
3. 再运行 `stage_handoff.py status` 核对最后一个有效封存 handoff。CHECKPOINT 不能让未封存阶段绕过阶段链，阶段链也不能让已损坏的任务结果被跳过。
4. `resume` 只返回恢复结论和第一个应执行的 task id，不改写 CHECKPOINT；真正完成、等待或阻塞时再按 7.3 更新。

### 7.5 阶段与 subagent 绑定

`agents/subagents/checkpoint-task-catalog.json` 是固定 task、动态图模板、结果路径、最低检查和允许 owner 的机器真源；本节只说明职责分组，不复制全部字段。`checkpoint.py` 在阶段开始、回退及读取既有状态时强制校验 catalog：固定项必须完整，动态图任务必须在模板位置按 `D1...Dn` 连续展开，额外阶段级结果只能在固定序列之后追加。

阶段任务按以下职责分组，具体结果路径和最低检查直接从 catalog 读取：

- 阶段 1：
  - 主 agent 基线：`phase-1-material-index`、`phase-1-evidence-cards`、`phase-1-analysis-plan`。
  - 首轮 fan-out：`phase-1-delivery-goals`、`phase-1-subject-boundary`、`phase-1-research-object`、`phase-1-research-mechanism`。
  - 后续汇合与分析：`phase-1-research-join`、`phase-1-innovation-candidates`、`phase-1-material-model`、`phase-1-handoff`。
- 阶段 2：`phase-2-decision`、`phase-2-handoff`；提交思路等待用户时 handoff 保持 pending，明确确认后才完成。
- 阶段 3：
  - 中心计划：`phase-3-content-core`、`phase-3-diagram-plan`。
  - 并行构建：`phase-3-public-draft` 与按计划展开的 `phase-3-diagram-D1...Dn`。
  - 汇合交付：`phase-3-diagram-join`、`phase-3-manifest`、`phase-3-internal-draft`、`phase-3-build-map`、`phase-3-handoff`。
- 阶段 4：
  - 中心计划：`phase-4-review-plan`。
  - 并行复核：`phase-4-semantic-review` 与按图展开的 `phase-4-visual-review-D1...Dn`。
  - 汇合交付：`phase-4-review-join`、`phase-4-validation`、`phase-4-timing-summary`、`phase-4-handoff`。

逐图生成和逐图视觉结果在完成后分别绑定 hash；主 agent 只能在全部计划实例有效后完成 join。不能用一个聚合“已写完”掩盖缺失的 D 任务，也不能在任务完成并绑定 hash 后继续追加内容。

- subagent 返回终态事件后，由主 agent 先把结构化结果写入合同指定的缓存文件并执行最低检查，再完成相应 checkpoint task；仅有聊天消息或事件行不能标记完成。

### 7.6 手工回退

用户增加或修改原始输入时，通常回退阶段 1；修改未确认写作思路时通常留在阶段 2；修改已冻结 I/T/D/E/S 或图示规划时由主 agent判断回退阶段 2 或 3；只改变复核处置时可回退阶段 4。主 agent 必须记录具体回退阶段和理由，再重建该阶段任务清单。

主 agent 先用 checkpoint `rollback-stage` 重置到选定阶段，再立即对同一阶段执行 `stage_handoff.py rewind`。`rewind` 只校验并保留所选阶段之前的有效前缀，删除所选阶段及下游封存行且保留缓存；两步完成后 `resume` 与 `stage_handoff.py status` 必须指向同一阶段。任一步失败时记录 `BLOCKED`，不得继续使用旧下游 handoff。所选阶段重建完成后必须重新 `seal`。

```bash
python3 scripts/checkpoint.py rollback-stage --root <disclosure-dir> \
  --stage <phase_name> --reason "<主 agent 的回退判断>" \
  --input "<输入或相对路径>" \
  --task <task-id> "<标题>" <owner> <result-path> <minimum-check>
python3 scripts/stage_handoff.py rewind \
  --working <disclosure-workspace/working> --stage <phase_name>
```

第一版不自动分析任务依赖，也不根据文件变化自行选择回退阶段；“显式选择阶段后按固定四阶段顺序截断下游封存”不属于自动推断。无法确定回退范围且不同选择会改变交付内容时，按 `DECISION` 请求用户确认。
