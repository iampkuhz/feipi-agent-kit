# 专利交底 Skill 渐进式加载手册

> 仅供维护者人工理解和评审。Skill 运行时不得读取本 handbook，任何 main agent 或 subagent 都不能把它作为任务上下文。

## 一、审计结论

旧结构存在两个大上下文入口：约 300 行的 `SKILL.md` 在启动阶段要求继续读取约 300 行的 `references/stage-delivery-contract.md`，后者又同时包含四阶段、六角色、事件、检查点和回退细节；约 260 行的 `content-quality-gates.md` 也容易在最终复核时被语义、视觉和主 agent 共同加载。

这会导致：

- 阶段 1 提前加载最终写作、制图和复核规则。
- 阶段 3 图 worker 看见其他图、其他角色和完整正文职责。
- 阶段 4 语义与视觉 reviewer 读取同一大总表，职责互相污染。
- 恢复任务时，为找一个阶段规则重新加载全流程。

治理后的原则是“入口只路由、阶段只给主 agent、角色只给对应 worker、模板按节点加载、总表只给维护者和脚本”。运行时不再存在一个被所有 agent 共同读取的大文档。

## 二、资源分层

### 1. Bootstrap 层

主 agent 启动只读取：

- `SKILL.md`：目标、全局硬门槛、四阶段路由和失败边界。
- `agents/subagents/index.json`：找到当前阶段和角色配置。
- `agents/subagents/runtime.json`：并发、事件、等待与 fallback。
- `agents/subagents/loading-policy.json`：确定其余资源何时按需加载。

这四项是固定 Skill bootstrap。随后只读取当前任务的 `disclosure-workspace/working/CHECKPOINT.md` 和 `stage_handoff.py status` 输出，以决定当前阶段；它们是 session 状态，不是额外的 Skill 公共说明。

启动时禁止读取四份阶段 guide、所有角色配置、所有模板、stage contract 维护索引、质量总表、handbook、history、案例和 schema。

### 2. 当前阶段层

主 agent 根据 `resume/status` 只加载当前阶段配置和对应 guide：

- 阶段 1：`agents/subagents/stages/phase-1.json` + `references/stages/phase-1-material-modeling.md`
- 阶段 2：`agents/subagents/stages/phase-2.json` + `references/stages/phase-2-idea-confirmation.md`
- 阶段 3：`agents/subagents/stages/phase-3.json` + `references/stages/phase-3-final-drafting.md`
- 阶段 4：`agents/subagents/stages/phase-4.json` + `references/stages/phase-4-review-delivery.md`

进入新阶段后，上一阶段 guide 不继续保留为执行上下文；跨阶段只传已 seal 的紧凑 handoff。

### 3. 节点层

只有执行到对应节点才加载资源：

- 阶段 3 `public-draft`：`assets/proposal_template.md`
- 阶段 3 `manifest`：`assets/disclosure-manifest.template.json`
- 阶段 3 `internal-draft`：`assets/internal_trace_appendix_template.md`
- 派发任一 subagent 或执行 fallback：主 agent 只读取当前节点 `role_ref` 对应的单个 role JSON 和任务包模板；role JSON 不转发给 worker。任务包和动态输入生成后，必须先运行 `stage_handoff.py validate-task`，通过后才启动。

JSON Schema 不作为模型上下文；由校验脚本直接执行。

### 4. Worker 层

每个 subagent 使用 `fork_turns: none`，只获得已校验任务包路径和明确允许的单角色 guide：

- `patent_subject_boundary_analyst`：只读 `subject-boundary-task.md`、预生成的 `inputs/subject-boundary-input.json` 和 `references/roles/subject-boundary.md`。
- `patent_prior_art_researcher(object)`：只读 `prior-art-object-task.md`、预生成的 object slice 和 `references/roles/prior-art-research.md`；不读完整事实卡或 mechanism lane。
- `patent_prior_art_researcher(mechanism)`：只读 `prior-art-mechanism-task.md`、预生成的 mechanism slice 和同一份 `references/roles/prior-art-research.md`；不读完整事实卡或 object lane。两个实例共用研究判断合同，但 `task_type`、`role_instance` 和 slice 始终隔离。
- `patent_innovation_value_analyst`：只读 `innovation-value-task.md`、预生成的 innovation slice 和 `references/roles/innovation-value.md`；不直接读取完整 evidence cards、主体、交付目标或 canonical research 文件。
- `patent_diagram_engineer(Dn)`：只读 `diagram-Dn-task.md`、预生成的 `inputs/diagram-Dn-input.json`、`references/roles/diagram-engineer.md` 和 `$feipi-plantuml-generate-diagram` 的必需资源；只写分配的图包目录，返回结果 row，由主 agent 写 Dn 结果 TSV。
- `patent_semantic_reviewer`：只读 `semantic-review-task.md` 逐项绑定的对外稿、内部稿、manifest、阶段 3 handoff 和 `references/reviews/semantic-review.md`；只返回固定九项 row，由主 agent 写结果 TSV。
- `patent_visual_reviewer(Dn)`：只读 `visual-review-Dn-task.md` 逐项绑定的同图 brief、PUML、SVG、validation 和 `references/reviews/visual-review.md`；只返回当前 D 的 row，由主 agent 写结果 TSV。

除制图角色只能写独占图包目录外，所有 subagent 均为 `read_only`。worker 不读取 `SKILL.md`、阶段 guide、其他任务包、其他 role/review guide、完整 stage contract、质量总表或维护资料。若任务包缺少必要输入，应 `BLOCKED`，不能自行扩大读取范围。

这里的 `permission` / `result_owner` 是任务 validator 可检查的行为合同，不等于宿主文件系统 sandbox 或写入 provenance。宿主不能施加只读/独占写目录时仍按同一合同执行，并以真实 Session trace 核验实际读写者；合成脚本通过只能证明声明、receipt 与工件 hash 自洽。

运行环境不支持 subagent 时，main agent 只为当前 fallback 节点加载同一任务包、该 role 的 `instruction_refs` 和 `skill_dependencies`，执行结束即回到阶段主职责；不得借 fallback 批量读取其他角色资料。

## 三、逐阶段加载矩阵

### 阶段 1

主 agent 加载阶段 1 guide，并且是唯一原始材料读取者。事实卡完成后：

- 派主体 worker 时，仅临时读取 `agents/subagents/roles/patent-subject-boundary-analyst.json`，从完整 evidence cards 预生成主体 slice，再校验任务包。
- 派两个研究 lane 时，仅临时读取 `agents/subagents/roles/patent-prior-art-researcher.json`；两个 worker 的预生成 slice、任务包和网页集合互相隔离。
- 汇合主体、交付目标与 canonical research 后，才读取 `agents/subagents/roles/patent-innovation-value-analyst.json`，预生成 innovation slice 并派创新价值 worker。

不加载模板、图角色 guide、复核 guide 或内容质量总表。

### 阶段 2

只加载阶段 2 guide。没有 subagent、模板或角色配置；写作思路等待用户确认后结束当前轮次。用户确认只靠 `decision.md` 与 handoff 恢复，不回读阶段 1 guide。

### 阶段 3

主 agent 只加载阶段 3 guide 和已确认 handoff。content core/diagram plan 冻结后：

- 正文节点按需加载 proposal template。
- 每个图节点读取一次 diagram role JSON，从中心文件只切出该 D 的 `diagram-Dn-input.json`，为该 D 生成并校验独立任务包。
- 图 worker 加载单图 slice、role guide 和通用 PlantUML skill，不加载专利阶段 guide、完整 content core 或完整 diagram plan。
- 所有图 join 后，manifest 和内部稿节点才分别加载各自模板。

不同图 worker 不共享任务包，也不读取其他 D 的内容；共享信息只由中心图计划中该图条目提供。

### 阶段 4

主 agent 只加载阶段 4 guide 和冻结 build map；subagent 可用时不加载两个 review guide：

- 派语义 reviewer 前只读取 semantic role JSON；任务包逐项绑定四个冻结工件及 hash，通过 `validate-task` 后 worker 单独加载 semantic review guide。
- 派每张图的视觉 reviewer 前只读取 visual role JSON；任务包逐项绑定同 D 的四个图包工件及 hash，通过 `validate-task` 后 worker 单独加载 visual review guide。
- 主 agent 只消费结构化结果并执行 join/validator，不重复做 worker 的长语义/视觉推理。

若 subagent 不可用，主 agent 仅在执行当前 semantic 或 Dn visual fallback 时加载对应一份 guide，不同时加载两份。

## 四、明确不进入模型上下文的资源

### Script-only

- `agents/subagents/checkpoint-task-catalog.json`：由 `checkpoint.py` 消费。
- `assets/*.schema.json`：由 validator 消费。
- `scripts/` 实现和图包 hash：直接运行或按错误定位，不为执行任务全文读取。
- `disclosure-validation.json` 的规则枚举：主 agent 读取结果摘要和失败规则，不加载 validator 源码证明内容质量。

### Maintainer-only

- `references/stage-delivery-contract.md`：跨阶段维护索引。
- `references/content-quality-gates.md`：完整规则编号总表。
- `handbook/`：人工流程、并行与加载说明。
- `MAINTAINER_HISTORY.md`、`CHANGELOG.md`。

维护或排错时可以人工打开这些文件；业务运行不能把它们声明为所有 agent 的公共前置阅读。

## 五、任务包 v2 是上下文防火墙

任务包必须小于 12 KiB，只包含“输入、需要判断、返回”。每个动态输入使用固定行：

```text
- path：`<relative-to-disclosure-dir>`；sha256：`<64hex>`
```

- 输入使用稳定 ID、相对交底目录的路径、hash 和有限锚点，不允许绝对路径、`..`、通配符或目录级引用，不复制上游长文。
- 需要判断与返回各只写一个注册的固定 `contract_id`，由 task type 映射到对应 role/review guide；任务包不得内嵌长上下文、JSON、路径或 URL。研究 URL 只能存在对应 slice `payload`。
- 返回合同指定固定 row 和一行关键事件，不要求在聊天回传正文、SVG、日志或思维链；结果文件由主 agent 写入。
- 允许读取的 Skill 资源必须显式声明：主体、双线研究、创新价值、diagram、semantic、visual 各自只能声明 role JSON 点名的聚焦 guide；双线研究可共用同一研究 guide，但任务包仍须按 `task_type` 分别声明并绑定各自 slice。其他 Skill 资源一律禁止。

阶段 1 与逐图输入统一使用可自证身份的 JSON envelope：

- 阶段 1：`slice_version`、`task_type`、`role`、`checkpoint`、`source_set_sha256`、对象型 `payload`。主体/两条研究的 source set 是 material index、evidence cards、analysis plan；创新价值的 source set 是 evidence cards、delivery goals、subject boundary、canonical research。
- 逐图：上述字段加 `diagram_id`、`purpose`、`diagram_plan_sha256`；source set 只含 `content-core.json`、`diagram-plan.json`。

集合 hash 统一为：路径去重后按 UTF-8 字典序排序，逐项输入 `path UTF-8 + NUL + 当前文件 sha256 ASCII + LF`，再取 SHA-256。worker 先核对 envelope 的 task identity 与任务包一致，再消费 `payload`；不匹配即 `BLOCKED`。

每次派发或 fallback 前运行：

```bash
python3 scripts/stage_handoff.py validate-task --working <disclosure-workspace/working> --task stages/agents/<task>.md
```

校验负责确认任务类型已注册、三段式结构、固定 contract ID、体积、动态路径/hash、envelope identity/source set、Skill 资源白名单和读写权限；失败即不得启动任务。成功时原子写入 `stages/agents/receipts/<task-basename>.dispatch.json`，绑定任务路径/hash、TaskSpec、动态输入集合 hash和时间。派发只承认当前 receipt；任务、TaskSpec 或动态输入变化会使旧 receipt 失效。

事实只在 evidence cards 保存一次，阶段 1 worker 读取由主 agent 预生成的角色 slice；跨阶段只传 handoff。图 worker 使用 Dn slice，视觉 worker 由任务包逐项绑定同 D 工件。任务包缺内容的修复方式是由主 agent 重建 slice/任务包并重新校验，不是让 worker 加载更多共享大文档。

## 六、恢复与回退时的加载顺序

1. 读取 Bootstrap 层和 CHECKPOINT，运行 `checkpoint.py resume`。
2. 运行 `stage_handoff.py status` 确认当前阶段；不先加载任何阶段 guide。
3. 只加载返回阶段的单份 guide 与 stage JSON。
4. 跳过结果存在、非空、最低检查通过且 hash 未变的完成项。
5. 从第一个 pending/失效任务继续；只有执行到具体节点才加载模板或 role 配置。

阶段封存会重新验证本阶段全部 dispatch receipt，并把 receipt 纳入 cache digest；无 receipt 或 receipt 过期不得 seal。阶段 3 三类 D 结果行由主 agent 写入前复算对应 `diagram.svg` 的实际 SHA-256，阶段 4 visual row 继续绑定同一值。语义九行的 `bound_sha256` 是其四个动态输入按上述规范得到的集合 hash。

用户改变输入或冻结计划时，主 agent 显式选回退阶段，再执行 checkpoint rollback 与 handoff rewind。回阶段 3 不加载阶段 1/2 guide；如果判断需要重建来源事实，才回阶段 1。第一版不自动做依赖分析。

## 七、防回退检查

加载策略的机器配置和 validator 应至少阻止：

- 把 stage contract、质量总表、handbook、history、案例、schema 或 checkpoint catalog 放入模型 bootstrap。
- 一个阶段声明多份阶段 guide，或四个阶段共同声明同一份大 guide。
- subagent 读取 `SKILL.md`、整个阶段 guide、其他角色 guide 或其他 D 任务。
- 阶段 3 在相应节点前加载全部模板。
- 阶段 4 让主 agent 与两个 reviewer 共同加载完整质量总表。
- 声明的路径不存在、越界，或 stage/role guide 超过约定体积。

静态策略只能证明“配置声明的加载集合”满足隔离，不能证明宿主在真实运行中从未额外读取。真实 Session 仍需通过 trace 核验；未获得脱敏样本前，只能报告配置和合成回归已覆盖。

## 八、维护规则

- 新增阶段规则写入对应 stage guide，不扩写 SKILL 或 stage contract。
- 新增单角色判断写入该角色专用 guide；仅靠任务包足够的角色不要创建全景文档。
- 跨角色共用且较短的硬门槛优先放任务包字段或机器 schema，不创建另一个大共享参考。
- 修改完整规则编号时，以 content quality 总表为维护入口，同步 validator、聚焦 review guide 和测试；业务运行仍只读聚焦 guide。
- handbook 可详细，但必须始终标记 maintainer-only，不能被加载策略引用。
