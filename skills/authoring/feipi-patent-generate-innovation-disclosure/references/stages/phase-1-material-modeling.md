# 阶段 1：素材确认与写作建模

> 仅供阶段 1 主 agent 在进入或恢复本阶段时加载。subagent 不读取本文件；后续阶段也不加载本文件。

## 本阶段输入与出口

这是唯一允许读取用户消息、文件、范围内代码和公开检索页的阶段。开始前读取 CHECKPOINT 与 handoff `status`；全新任务没有上游 handoff。

本阶段必须封存：

- `shared/material-index.tsv` 与 `shared/evidence-cards.md`
- `phase-1/analysis-plan.json`、`delivery-goals.md`
- `subject-boundary.tsv`、两条研究 lane 与 canonical `research.tsv`
- `innovation-candidates.tsv`、`model.md`、`handoff.md`

handoff 只传核心主张、候选 I/T、边界、证据结论、缺口和图职责的稳定 ID、路径与 hash，不复制原始材料或检索日志。

## 串行基线

1. 建立 `material-index.tsv`：每份原始材料分配 `source_id`，记录类型、相对路径或定位、SHA-256 和相关锚点；同一材料只读取一次。
2. 建立 `evidence-cards.md`：只摘录会进入主张、I/T、检索词或边界判断的事实，不收录完整原文。
3. 生成 `analysis-plan.json`，明确缺口、两条检索线、角色、目标和结果路径；为四类任务预生成 `stages/agents/inputs/<task-type>-input.json`。
4. 成稿门槛至少包含专利名、使用场景、1 个技术对象、1 个核心机制、1 个必要约束或边界、1 个现有问题事实。缺失时定向追问，不能用发明扩展冒充来源事实。

事实台账必须分开：

- `SF` 来源事实：陈述与输入定位齐全。
- `IE` 发明扩展：引用至少一个已有 SF，不能写成已经实现。
- `EM` 外部资料：记录标题、公开定位、检索日期和事实/合理推断属性。

同步建立术语泛化映射、缩写白名单和内部标识限制；实现名和未授权产品名不能进入公开表达。

## 第一轮并行

事实卡与分析计划有效后，主 agent 同时推进以下互不写同一文件的任务：

- 自行整理 `delivery-goals.md`。
- 派发 `patent_subject_boundary_analyst`，只给三段式任务包、预生成的主体 slice 与 `references/roles/subject-boundary.md`，返回主体/系统/物理边界及实现/扩展候选 row。
- 派发两个 `patent_prior_art_researcher` 实例：对象/场景 lane 与机制/问题 lane 共用 `references/roles/prior-art-research.md`，但各有独立 `task_type`、`role_instance`、任务包、预生成 slice 和返回 row，不能跨 lane 读取。

slice 是 JSON envelope：`slice_version=1`、匹配任务的 `task_type/role/checkpoint`、`source_set_sha256` 和对象型 `payload`。主体/研究 source set 为 material index、evidence cards、analysis plan；innovation 为 evidence cards、delivery goals、subject boundary、canonical research。集合按路径排序，对 `path + NUL + 文件 sha256 + LF` 取 SHA-256。payload 只保留当前角色必需内容；研究 URL 只能在研究 slice 内。

任务包“需要判断/返回”只写 TaskSpec 注册的固定 `judgment_contract_id` / `return_contract_id`，不内嵌上下文、JSON、路径或 URL：subject、object、mechanism、innovation 分别使用 `JUDGMENT-...-V1` 和 `RETURN-...-TSV-V1` 对应合同。每次派发或 fallback 前运行：

```bash
python3 scripts/stage_handoff.py validate-task --working <disclosure-workspace/working> --task stages/agents/<task>.md
```

校验成功会原子写入 `stages/agents/receipts/<task-basename>.dispatch.json`，绑定任务 hash、TaskSpec 与动态输入集合 hash；失败或 receipt 缺失/过期不得启动。subagent 只拿任务包、envelope 和单份聚焦合同，不拿本阶段 guide、原始材料、其他角色合同或 lane 结果。阶段 1 角色均按 `read_only` 执行，只返回 row；主 agent 校验后落盘，并到 join 屏障才等待。

`read_only` 与 `result_owner=main_agent` 是可校验行为合同，不代表宿主已经提供文件系统 sandbox 或真实写入 provenance。宿主无法施加只读时仍按合同执行，并在真实 trace 中核验；本地脚本通过不能证明真实写入者。

## 两条竞品检索线

- 无论用户是否提供竞品，都必须主动检索；不能输出“待检索”。
- 两条检索分别围绕泛化后的技术对象/使用场景和核心机制/现有问题。
- 每条查询含 `basis_terms`、另一分类或已确认场景的 `context_terms` 及研究限定词；两类术语以纯文本原样进入，禁止实体编码、零宽/控制字符和内部标识。
- 每条 lane 最多打开 3 个候选页面；优先官方页、官方文档、公开专利、标准和论文。找到足够说明行业基线的材料即停止扩散。
- 主 agent 校验并去重两条独立结果，生成唯一 `research.tsv`；总计保留 1–3 项最佳证据，或记录 `searched_no_usable_evidence` 的检索范围、页面与无具名结论。
- 检索工具不可用、页面不可访问、两条记录不完整或查询与主题无关时阻塞最终成稿，不以占位符越过。

## 创新与价值汇合

只有 `delivery-goals.md`、`subject-boundary.tsv` 和 canonical `research.tsv` 均有效后，主 agent 才从这些结果与证据卡的必要稳定条目预生成 `innovation-value-input` slice，写入声明 `references/roles/innovation-value.md` 的任务包并通过 `validate-task`，然后派发 `patent_innovation_value_analyst`。worker 不直接读取上述完整结果文件或完整事实卡，要求返回：

- 原问题、核心机制、必要约束、对比基线和实质差异假设。
- “差异为什么产生结果”的价值链，而非只写处理方式或泛化好处。
- 候选效果、验证状态及 D/E/S 落点。
- 每项已实现基础的 SF 绑定；每项拟扩展保护的唯一 IE 绑定。

主 agent 再收敛 `model.md`：

- 形成一句核心发明主张。
- 保留 2–4 个连续 `I1...In` 和 2–4 个连续 `T1...Tn`，保持双向一一映射。
- 每个 I 写清“现有做法 → 已实现处理方式 → 实质差异 → 价值因果 → 可观察效果”。
- 每个 T 写清原问题、采用机制、可观察结果和验证状态；无实测材料时使用 `expected_observable`。
- 已实现基础接近真实路径，但只保留对象、输入输出、关键动作、状态、接口和约束；拟扩展保护单独高亮规划，不能进入图示。
- 候选组件总览顶层只允许业务域、独立系统和物理端点；先定边界，再拆组件。

subagent 结果只是候选。核心主张、正式 I/T、实现/扩展边界和候选图职责仍由主 agent 统一收敛。

## 检查点、事件与封存

- 按当前阶段 DAG 调用 `checkpoint.py` 登记任务；checkpoint catalog 只由脚本内部消费，主 agent 不读取。结果存在、非空、通过最低检查并绑定 hash 后，才标记完成。
- subagent 普通完成只更新内部任务状态；阶段边界由主 agent 聚合，不逐条转发。
- 缺输入、检索能力或边界冲突导致不能继续时记录 `BLOCKED`；需要用户选择且选择会改变主张/边界时记录 `DECISION`。
- 写完 handoff 后运行 `stage_handoff.py seal --working <disclosure-workspace/working> --stage phase_1_material_modeling`；seal 复验并纳入全部 receipt，缺失或过期不得进入阶段 2。

恢复时运行 checkpoint `resume`，跳过有效项；材料 hash 变化则从首个失效任务重做，不重读未变化材料。
