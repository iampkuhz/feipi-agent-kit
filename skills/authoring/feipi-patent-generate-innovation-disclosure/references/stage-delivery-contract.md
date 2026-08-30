# 阶段交付合同维护索引

> 本文件只供维护者核对跨阶段不变量和寻找细分合同。运行时禁止整体读取，也不得把它附到 subagent 任务包。主 agent 只加载当前阶段 guide；subagent 只加载自己的任务包和被加载策略明确点名的单角色 guide。

原先集中在本文件的四阶段细节、六个 subagent role 模板及其动态实例，已拆到阶段、角色和复核专用文档，避免每个 agent 重复加载整套流程。

## 1. 运行时路由

- 阶段 1 主 agent：`references/stages/phase-1-material-modeling.md`
- 阶段 2 主 agent：`references/stages/phase-2-idea-confirmation.md`
- 阶段 3 主 agent：`references/stages/phase-3-final-drafting.md`
- 阶段 4 主 agent：`references/stages/phase-4-review-delivery.md`
- 主体边界 subagent：`references/roles/subject-boundary.md`
- 两条现有技术研究实例：`references/roles/prior-art-research.md`
- 创新价值 subagent：`references/roles/innovation-value.md`
- 单图生成 subagent：`references/roles/diagram-engineer.md`
- 语义复核 subagent：`references/reviews/semantic-review.md`
- 单图视觉复核 subagent：`references/reviews/visual-review.md`

阶段 1 的任务各自加载一份聚焦 role guide；两条检索因属于同一 role 共用研究 guide，但任务包、实例和 slice 隔离。准确加载矩阵见只供维护者阅读的 `handbook/progressive-loading.md`。

## 2. 四阶段交付矩阵

- 阶段 1 是唯一可读取既有原始材料和实际打开检索页的阶段，封存 `phase-1/handoff.md`。
- 阶段 2 只消费阶段 1 handoff、被点名的模型条目和用户本轮变更；未获明确确认不得封存。
- 阶段 3 只消费阶段 2 handoff，并按节点加载正式模板；正文与单图任务必须从同一冻结计划派生。
- 阶段 4 只消费阶段 3 handoff、build map 指向的冻结工件及当前 hash；语义与视觉复核汇合后才完整校验。

上游材料或 handoff hash 变化时，下游封存状态失效。旧缓存可以保留，但重新封存前不得消费。

## 3. 跨阶段文件不变量

- 内部过程文件只写入 `disclosure-workspace/working/`；所有合同路径相对交底书目录，禁止绝对路径、`..` 和符号链接越界。
- 重复记录使用 TSV，单元格只放短标量；详细事实只在 `working/stages/shared/evidence-cards.md` 保存一份。
- `handoff.md` 不超过 24 KiB，只传稳定 ID、相对路径、SHA-256、已确认决策和未决项；subagent 任务包不超过 12 KiB，不复制原文、完整正文、网页、日志或思维链。
- 每个 handoff 前四行固定为 `handoff_version`、`from_stage`、`to_stage`、`status`；正文只用“决策摘要、传递索引、未决项”三个二级标题。
- `stage-state.tsv` 绑定输入、缓存和 handoff hash；只有 `stage_handoff.py seal` 成功的阶段可以供下游消费。

机器文件真源：

- 阶段 DAG 与角色注册：`agents/subagents/index.json` 及其引用文件。
- 运行并发、事件和等待合同：`agents/subagents/runtime.json`。
- 检查点任务、结果路径和最低检查：`agents/subagents/checkpoint-task-catalog.json`。
- 内容确定性规则：schema、validator 与 `references/content-quality-gates.md`；后者是维护总表，不是运行时上下文。

## 4. subagent 任务包 v2 与交付

- 任务包只包含“输入、需要判断、返回”，并声明 role、输入引用、允许写入、result owner、最低检查和 timing log。每个动态输入固定写为 `path + sha256`；禁止绝对路径、`..`、通配符和目录级引用。
- “需要判断”和“返回”各只能引用注册表中的固定 `judgment_contract_id` / `return_contract_id`，不得内嵌长上下文、JSON、路径或 URL。研究 URL 只能进入该任务 slice 的 `payload`，不能进入任务包合同正文。
- 阶段 1 四类 input slice 统一为 JSON envelope：`slice_version=1`、`task_type`、`role`、`checkpoint`、`source_set_sha256`、对象型 `payload`。前三类 source set 固定为 material index、evidence cards、analysis plan；innovation 固定为 evidence cards、delivery goals、subject boundary、canonical research。逐图 envelope 同字段外加 `diagram_id`、`purpose`、`diagram_plan_sha256`，source set 固定为 `content-core.json` 与 `diagram-plan.json`；payload 还必须绑定当前批次成功且声明 `startup_policy=podman_once` 的 `renderer_url` 与 `renderer_preflight_sha256`。worker 只能读取自己的 envelope；语义和视觉任务则逐项绑定冻结工件及 hash。
- 所有集合 hash 使用同一规范：路径去重后按 UTF-8 字典序排序，逐项输入 `path UTF-8 + NUL + 当前文件 sha256 ASCII + LF`，再计算 SHA-256。`source_set_sha256`、receipt 的 `dynamic_input_set_sha256` 和语义复核四输入 `bound_sha256` 均不得使用拼接 JSON、任务包 hash 或任意 package hash 代替。
- 使用 `fork_turns: none`；派发消息只给任务包路径和该角色被允许的专用 guide，不复制对话或阶段 guide。
- 每次派发或 fallback 前必须运行 `validate-task`；成功时原子生成 `stages/agents/receipts/<task-basename>.dispatch.json`。receipt 固定含 `receipt_version=1`、`task_path`、`task_sha256`、含两类 contract ID 的 `task_spec`、`dynamic_input_set_sha256`、`validated_at`。失败、缺失，或任务、TaskSpec、动态输入变化使 receipt 过期时，均不得启动。
- subagent 终态必须为 `COMPLETE` 或 `BLOCKED`。除 diagram worker 只写分配的图包目录外，其余角色均为 `read_only`；所有角色只返回与目标 TSV 同构的 row，由主 agent 校验后写结果文件并执行最低检查。
- 单图生成和视觉复核按 `D1...Dn` 使用独占任务包；diagram worker 不写 Dn 结果 TSV，visual reviewer 不写 Dn review TSV，均由主 agent 写入，更不能写共享聚合文件。
- `permission` 与 `result_owner` 是可校验的行为合同，不等于宿主已施加文件系统 sandbox，也不构成真实写入 provenance。宿主无法提供只读或独占写目录时，worker 仍必须按合同执行，主 agent 通过真实 trace 核验；本地脚本只能证明声明、receipt 和工件一致，不能证明真实写入者。
- subagent 不读取 `SKILL.md`、本索引、其他阶段 guide、其他角色配置、handbook、history、案例、schema 或完整质量总表。

## 5. 关键事件与非轮询汇合

- 只上报 `MILESTONE`、`DECISION`、`BLOCKED`、`COMPLETE`；开始、工具调用、普通进度、心跳、缓存命中、重试和等待超时保持静默。
- 事件固定为一行 `[<EVENT>] <scope>｜<outcome>｜<next_or_artifact>`，不超过 240 字；subagent 只报主 agent，主 agent 去重并在阶段边界聚合。
- 派发后主 agent 继续不依赖 worker 的工作；到真实依赖屏障且没有其他工作时，才进行一次长时事件驱动等待。
- 禁止短间隔 wait、status/list/read/sleep 组合轮询。非终态等待到期不等于失败，也不触发心跳或重派。
- 阶段 2 等待用户确认时结束当前轮次；这不是 subagent wait。

## 6. 封存与回退不变量

```bash
python3 scripts/stage_handoff.py status --working <disclosure-workspace/working>
python3 scripts/stage_handoff.py validate-task --working <disclosure-workspace/working> --task stages/agents/<task>.md
python3 scripts/stage_handoff.py seal --working <disclosure-workspace/working> --stage <phase_name>
python3 scripts/stage_handoff.py rewind --working <disclosure-workspace/working> --stage <phase_name>
python3 scripts/stage_handoff.py validate --working <disclosure-workspace/working> --require-complete
```

- `seal` 只承认合同内缓存、逐图集合、hash 绑定、当前有效 dispatch receipt 和规范 handoff；它会复验本阶段全部任务 receipt 的任务 hash、TaskSpec 和动态输入集合。缺失或过期 receipt、阶段 3/4 的 D 集合不完整时不得封存；receipt 本身纳入阶段 cache digest。
- 阶段 3 的 `diagrams/Dn-result.tsv`、`diagram-result.tsv`、`build-map.tsv` 中每个 D 行 `sha256` 必须由主 agent 写入前复算为对应 `diagram.svg` 的当前实际 SHA-256，三处一致；阶段 4 当前 D 的 visual row 绑定同一值，不使用虚构的图包 hash。
- `rewind` 只执行主 agent 已明确选定的阶段，不推断依赖，也不删除缓存。
- 用户修改输入或冻结计划时，由主 agent 判断回退阶段：新事实通常回阶段 1，思路取舍回阶段 2，冻结工件变化回阶段 3，单纯复核处置回阶段 4。
- 主 agent 依次执行 checkpoint `rollback-stage` 与 handoff `rewind`；任一步失败即 `BLOCKED`，不得沿用旧下游结论。

## 7. 任务检查点与恢复

- 任务运行时维护 `disclosure-workspace/working/CHECKPOINT.md`，只表示当前状态，不写历史。
- 只在阶段开始、任务完成、等待用户、发生真实阻塞时更新；微步骤、工具调用、普通 subagent 事件和无变化等待不得更新。
- 任务只有在唯一结果文件存在、非空、通过声明的 `nonempty|markdown|json|tsv` 最低检查并绑定当前 SHA-256 后，才能进入“当前阶段已交付”。
- 恢复时先运行 checkpoint `validate` / `resume`，跳过结果仍有效的已完成任务，从第一个 pending 或失效任务继续；随后用 handoff `status` 核对阶段链。
- CHECKPOINT 不替代阶段 seal、图包 validator、完整交付校验或人工语义/视觉复核。
- 第一版不做自动依赖分析；主 agent 必须显式选择回退阶段并记录理由。

本索引只保存这些跨阶段不变量。任何阶段步骤、角色判断或复核量表的新增，都应写入对应的细分 guide，不得再次把全流程堆回本文件。
