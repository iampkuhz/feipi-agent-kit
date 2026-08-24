# 阶段交付与上下文压缩合同

本合同约束四个大阶段及三个 subagent 的输入、判断、缓存和输出。目标是让每个阶段只读取完成本阶段所需的最小信息，并能在跨轮次恢复时从文件继续，而不是依赖完整对话或重复打开原始材料。

## 1. 固定目录与紧凑格式

内部过程文件统一放在 `disclosure-workspace/working/stages/`：

```text
stages/
├── stage-state.tsv
├── shared/
│   ├── material-index.tsv
│   └── evidence-cards.md
├── agents/
│   ├── prior-art-task.md
│   ├── diagram-task.md
│   └── final-review-task.md
├── phase-1/
│   ├── model.md
│   ├── research.tsv
│   └── handoff.md
├── phase-2/
│   ├── decision.md
│   └── handoff.md
├── phase-3/
│   ├── build-map.tsv
│   └── handoff.md
└── phase-4/
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
build-map.tsv:      artifact_id\tpath\tsha256\towner\tstatus
review.tsv:         artifact_id\treview_type\tstatus\tbound_sha256\tconclusion
```

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
| 阶段 1 素材确认与建模 | 用户消息、用户文件、明确范围内的代码、实际打开的公开检索页 | 无；首次执行先建材料索引 | 输入门槛、SF/IE/EM 边界、技术泛化、问题/机制/约束、候选 I/T、两线检索是否充分 | `material-index.tsv`、`evidence-cards.md`、`agents/prior-art-task.md`、`phase-1/model.md`、`phase-1/research.tsv`、`phase-1/handoff.md` | 核心主张、候选 I/T、实现/扩展边界、证据结论、缺口、候选图职责；只给 ID 和缓存定位 |
| 阶段 2 思路确认 | 仅用户本轮新增的确认、否决或补充；不得重读既有原始材料 | `phase-1/handoff.md` 及其中点名的 `model.md` 条目 | 是否得到明确确认；冻结哪些 I/T/D/E/S；用户调整是否导致阶段 1 事实或检索失效 | `phase-2/decision.md`、`phase-2/handoff.md` | 已确认且冻结的 I/T/D/E/S、实现/扩展边界、图示职责、所需模板、未决阻塞项 |
| 阶段 3 最终撰写 | 正常情况下不读原始材料；只有用户新增材料使阶段 1 失效时才回退 | `phase-2/handoff.md`；按需加载三份正式模板 | 文档结构、图型与数量触发、编号一致性、正文/内部稿/manifest/图包的同源关系 | 最终工件、`agents/diagram-task.md`、`phase-3/build-map.tsv`、`phase-3/handoff.md` | 最终工件的相对路径、hash、owner、状态和待复核项；不得复制完整正文或图源码 |
| 阶段 4 复核与交付 | 正常情况下不读原始材料，也不重读网页 | `phase-3/handoff.md` 及 `build-map.tsv` 指向的最终工件；按需加载相关质量门禁 | 实现/扩展边界、因果删除、泛化、对外泄漏、SVG 视觉质量、确定性校验状态 | `agents/final-review-task.md`、`phase-4/review.tsv`、`disclosure-validation.json`、`phase-4/handoff.md` | 给用户的工件路径、最终状态、警告、验证边界和 timing summary 路径 |

## 3. 阶段执行规则

1. 每阶段开始先运行 `status`，只读取它给出的 `next_input`；阶段结束写完缓存后再 `seal`。跨轮次恢复不重放旧推理，只从最后一个有效 handoff 继续。
2. 阶段 1 对每份原始材料只读取一次，并用 `source_id + sha256 + relevant_anchors` 建索引。`evidence-cards.md` 只摘录会进入主张、I/T、检索词或边界判断的证据；不保存思维链和材料复述。
3. 阶段 2 的写作思路必须落入 `decision.md`，不能只留在对话。用户补充新事实时先更新材料索引并回退阶段 1；只有对既有候选的确认或取舍可以直接封存阶段 2。
4. 阶段 3 只依据已冻结 handoff 工作。正文与制图可以并行，但主 agent 与 diagram worker 写入路径必须不相交；两者汇合前不得生成最终 manifest hash，也不得启动阶段 4。
5. 阶段 4 只复核 `build-map.tsv` 绑定的 hash。任一工件变化后，相应复核和阶段 4 handoff 自动失效，禁止沿用旧结论。
6. 长分析只在当前阶段内发生，缓存只保留结论、证据定位和未决项。禁止把完整对话、长检索日志或上一阶段的推理过程传入下一阶段或 subagent。

## 4. subagent 三段式交付

每个 subagent 的任务文件都只包含 `输入`、`需要判断`、`返回` 三节，并写明 role、输入引用（阶段 1 使用材料索引，其余阶段使用上游 handoff）、允许写入和 timing log。派发使用 `fork_turns: none`，消息中只给任务文件路径，不复制任务文件内容。

### `patent_prior_art_researcher`

- 输入：`agents/prior-art-task.md`；其中只含两条检索线的 basis/context terms、查询上限、允许来源类型和阶段 1 缓存 ID，不含完整原始材料。
- 需要判断：候选页面相关性、证据属性、是否足以说明行业基线、何时停止扩散。
- 返回：符合 `research.tsv` 表头的数据行和一行状态；不返回长页面摘录、搜索日志或重复字段。主 agent 是 `research.tsv` 的唯一写入者。

### `patent_diagram_engineer`

- 输入：`agents/diagram-task.md`；只引用已封存的阶段 2 handoff、每张图的职责和允许写入的 `diagrams/` 目录。
- 需要判断：图型、触发条件、布局、编号和“仅呈现已实现路径”是否成立。
- 返回：符合 `build-map.tsv` 表头的图包数据行和一行状态；图文件直接写入各自目录，不在消息中回传 PUML/SVG。主 agent 可并行写正文，但在 worker 返回前不得封存阶段 3。

### `patent_final_reviewer`

- 输入：`agents/final-review-task.md`；只引用阶段 3 handoff、`build-map.tsv` 中的路径/hash 和本轮相关质量门禁。
- 需要判断：实现/扩展边界、因果删除、泛化、对外泄漏和最终 SVG 视觉质量。
- 返回：符合 `review.tsv` 表头的数据行和一行状态；不回传正文副本或逐步推理。主 agent 是 review 缓存和 manifest 复核记录的唯一写入者。

## 5. 稳定性与失效边界

- 只有已封存的上游 handoff 才能启动下一阶段或 subagent。主 agent 在派发前校验输入 hash，汇合后再次校验输出路径与 hash。
- 并行只允许“阶段 3 主 agent 写正文 + 单个 diagram worker 写 diagrams”这一组不相交写入；竞品的两条检索线在同一 worker 内处理，终审只启一个 reviewer。
- subagent 超时、失败或返回格式不合同时，不把半成品写入共享 TSV，也不启动下游；由主 agent重派一次或接管同一职责。
- 使用 `scripts/stage_handoff.py` 管理封存链：

```bash
python3 scripts/stage_handoff.py init --working <disclosure-workspace/working>
python3 scripts/stage_handoff.py status --working <disclosure-workspace/working>
python3 scripts/stage_handoff.py seal --working <disclosure-workspace/working> --stage phase_1_material_modeling
python3 scripts/stage_handoff.py validate --working <disclosure-workspace/working> --require-complete
```

`seal` 只承认固定缓存文件和 handoff 头；上游 hash 变化时从 `stage-state.tsv` 删除下游有效状态，但不删除缓存文件。`validate` 负责发现篡改、断链、越界、缺文件和超大 handoff，不判断专利内容质量。
