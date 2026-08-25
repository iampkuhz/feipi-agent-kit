# 专利创新交底 Skill 流程与并行说明

> 本文件只供维护者人工理解和维护流程使用。Skill 运行时不得读取本文件，也不得把它加入 subagent 任务包。主 agent 运行时只读取 `SKILL.md`、当前阶段说明、当前节点配置和任务包白名单；worker 只读取已校验任务包、任务包绑定的聚焦输入、该角色专用 guide，制图 worker 额外读取直接依赖的 `$feipi-plantuml-generate-diagram` 必需资源。完整加载矩阵见同为维护者专用的 `handbook/progressive-loading.md`。

## 一、总体处理模型

- 整个任务仍然只有四个阶段，阶段之间严格串行：
  1. 阶段 1：素材确认与写作建模。
  2. 阶段 2：提交写作思路并等待用户确认。
  3. 阶段 3：生成最终正文、内部稿、manifest 和图包。
  4. 阶段 4：完成语义、视觉、确定性校验并交付。
- 并行只发生在阶段内部，并遵循统一结构：
  1. 主 agent 先完成串行屏障，冻结所有 worker 的共同输入。
  2. 主 agent 一次派发可并行的 subagent，不让 subagent 继续派生。
  3. 主 agent 同时处理不依赖 worker 的本地任务。
  4. 到达依赖屏障后，使用事件驱动等待汇合，不轮询 worker 状态。
  5. worker 返回结构化 row 后，由主 agent 写入合同结果文件；只有这些文件存在、非空、通过最低检查且 hash 仍有效，才能完成 join 和阶段 handoff。
- 并发与数量边界：
  - 同时活动的 subagent 最多 3 个。
  - 单次交底累计派发最多 9 个 subagent 实例，失败重派也计入累计数量。
  - 制图 worker pool 最多 2 个；全部图按 `D` 编号划分给两个 worker，每张图只能有一个 owner。
  - 视觉复核 worker pool 最多 2 个；全部 SVG 按 `D` 编号划分，每张图只能由一个视觉 worker 返回结论。
  - 宿主容量不足时减少并发、顺序执行相同 lane；不得降低门禁，也不得用短间隔等待弥补容量不足。

## 二、用户举例中的三个内容能否并行

### 1. 技术主体与主题

- 不能在事实台账形成前独立分析。
- 它决定技术对象、使用场景、业务域、系统归属、物理边界、核心机制和可用检索词，是阶段 1 的内部锚点。
- `patent_subject_boundary_analyst` 可以与两个竞品检索实例并行，但它的结论必须在候选创新点最终分析之前完成。

### 2. 候选创新点

- 不能与技术主体最终判断完全并行。
- 原因是创新点必须建立在已经泛化的技术主体、实现/扩展边界和外部基线上；提前完成容易把实现类、产品名或局部处理方式误当创新。
- 可以先从事实卡中保留问题、机制和约束线索，但这些线索不能作为完成的 checkpoint 结果。
- 正式的候选创新、价值因果和 `I/T` 建议由 `patent_innovation_value_analyst` 在主体分析与竞品研究第一次汇合后执行。

### 3. 交付目标要求

- 可以与主体分析和竞品检索并行整理，但由主 agent 负责，不能交给 subagent 冻结。
- 主 agent 只整理本次任务特有的目标，例如专利名、使用场景、保护倾向、已经实现与拟扩展范围、对外/内部版本要求和当前证据缺口。
- Skill 固定的目录、格式、验证和内外版本合同不需要在每次任务中重新分析。
- 交付目标只有在与主体、研究和创新候选汇合后才能成为最终写作计划的一部分。

## 三、阶段 1：素材确认与写作建模

### 1. 串行屏障

- 主 agent 是原始材料的唯一归一化协调者，依次完成：
  1. 建立 `material-index.tsv`，绑定每份材料的定位、有效锚点和 hash。
  2. 建立唯一的 `evidence-cards.md`，区分来源事实、发明扩展和外部资料。
  3. 泛化内部类名、函数、字段、表名和产品名。
  4. 提取可供主体与检索使用的技术对象、机制、约束、问题和使用场景锚点。
  5. 从完整 evidence cards 中为主体、两条检索和后续创新任务分别预生成不超过 12 KiB、hash 绑定的聚焦 input slice，再生成任务包。
- 屏障完成前不得派发任何阶段 1 subagent。这样可以避免多 agent 重读原始材料、事实编号冲突和内部标识泄漏。
- 每个任务包在派发或 fallback 前必须通过 `stage_handoff.py validate-task`；worker 只读自己的 slice，不直接读取完整 `evidence-cards.md` 或 `analysis-plan.json`。

### 2. 第一轮 fan-out

- 主 agent 同时派发三个 subagent：
  - 一个 `patent_subject_boundary_analyst`：确定技术主体、主题、业务/系统/物理边界，以及实现与拟扩展的边界候选。
  - 一个 `patent_prior_art_researcher` 的 `object` 实例：只执行技术对象与使用场景检索线。
  - 一个 `patent_prior_art_researcher` 的 `mechanism` 实例：只执行核心机制与现有问题检索线。
- 两个 prior-art 实例共享角色合同，但任务包、查询范围、结果文件和 checkpoint 各自独立；任何实例都不得继续派生。
- 主 agent 在三个 worker 运行期间整理本次交付目标和证据缺口。
- 主 agent 不发送 `STARTED`、心跳或普通进度；只有产生需要选择的边界、出现真实阻塞或职责完成时才处理关键事件。

### 3. 第一次 join

- join 输入包括：
  - 主 agent 校验主体 worker 返回 row 后写入的 `subject-boundary.tsv`。
  - 主 agent 校验两个研究 worker 返回 row 后写入的 `research-object.tsv` 和 `research-mechanism.tsv`。
  - 主 agent 整理的交付目标与证据缺口。
- join 门禁包括：
  - 技术主体和检索词都能回溯到相同的证据卡。
  - 实现基础与拟扩展保护没有混写。
  - 两条检索焦点不同，检索记录完整；允许诚实的 `searched_no_usable_evidence`，不允许“待检索”。
  - 结果文件均通过最低检查且绑定 hash。
- join 产物是去重后的 canonical `research.tsv`；创新价值任务只能引用该汇总，不直接拼接两条 lane 的自由文本。
- 任一必需结果失败时只重做对应实例，不丢弃仍有效的主体或另一条研究结果。

### 4. innovation 后续 lane

- 第一次 join 通过后才派发 `patent_innovation_value_analyst`。
- 该 lane 形成 2–4 个候选创新点，并为每项补全：
  - 来源事实支持的已实现基础。
  - 可选且带 `IE` 追溯的拟扩展保护。
  - 对比基线、核心机制、必要约束和实质差异。
  - “差异为什么带来可观察结果”的价值因果。
  - 一一对应的候选 `T` 效果和正文/图示落点。
- 该 worker 只提出结构化候选，不能替主 agent 冻结核心主张、保护范围或最终 `I/T`。

### 5. 最终 join

- 主 agent 汇合主体边界、canonical `research.tsv`、交付目标和创新价值结果。
- 主 agent 结合 `innovation-candidates.tsv` 生成最终 `model.md`，不再重新解释或改写已汇总的研究证据。
- 只有形成一个核心发明主张、2–4 组候选 `I/T`、明确实现/扩展边界、候选图职责和未决项后，才能封存阶段 1 handoff。
- 若不同候选会实质改变保护范围，由主 agent 上报 `DECISION`；不能由 subagent 自行选择。

## 四、阶段 2：写作思路确认

### 1. 为什么保持串行

- 阶段 2 是用户决策屏障，不配置 subagent，也不提前启动正文或制图。
- 核心主张、候选 `I/T`、实现/扩展边界、图示职责和证据处置必须作为同一个写作思路提交，拆给多个 worker 会形成互相矛盾的确认项。
- 主 agent 必须判断用户回复属于：
  - 对既有候选的确认、否决或取舍，可以留在阶段 2 更新。
  - 新增或改变来源事实，必须显式回退阶段 1。
- 沉默、仅补充材料或不明确表态都不视为确认。

### 2. 串行流程

- 主 agent 根据阶段 1 handoff 生成 `decision.md`。
- 向用户发出一条合并后的 `DECISION`，然后结束当前轮次等待用户。
- 收到明确确认后，主 agent 原子冻结 `I/T/D/E/S`、实现/扩展边界、图示职责和未决项。
- 冻结结果写入阶段 2 handoff；此前不得生成最终 `disclosure.md`、manifest 或图包。

## 五、阶段 3：最终写作与按图并行

### 1. 中心 diagram plan 屏障

- 主 agent 只读取已经确认的阶段 2 handoff，先建立唯一的中心 diagram plan。
- plan 必须一次冻结：
  - 所需图及其 `D` 编号。
  - 每张图的唯一职责、图型、输入节点/步骤和触发依据。
  - 每张图独占的写入目录；`diagrams[]` 每项使用 `diagram_id + purpose + output_dir`，其中目录精确为 `disclosure-workspace/diagrams/<Dn>-<purpose>`。
  - 图文共用的 `E`、`S` 编号和仅呈现已实现路径的限制。
- plan 未通过编号、职责和路径检查前，不得派发 diagram worker。
- 每个 D 必须从中心文件预生成独立 `stages/agents/inputs/diagram-Dn-input.json`，只保留本图职责、必要公开字段、已实现路径、编号和目录；任务包通过 `validate-task` 后才可派发或 fallback。worker 禁止直接读取完整 `content-core.json` 或 `diagram-plan.json`。

### 2. fan-out

- 主 agent 按 `D` 编号把全部图分给最多两个 `patent_diagram_engineer` 实例：
  - 每张图只能属于一个 worker。
  - 两个 worker 的目录必须不相交。
  - 每个 worker 先完成自己负责图的 brief，再逐图生成和校验 package。
  - 每个 worker 只写被分配的图包目录并返回一行结果；主 agent 校验图包后写 `phase-3/diagrams/Dn-result.tsv`，再绑定动态 checkpoint `phase-3-diagram-Dn`。
  - 单张图失败只允许重做该图，不重渲染未变化图包。
- 制图期间主 agent 同时构建冻结的公开语义模型并撰写唯一对外正文 `disclosure.md`。
- 主 agent 与 diagram worker 不得修改对方负责的文件。

### 3. join 与内部稿/manifest 顺序

- 所有图包与对外正文完成后进入 join，顺序固定为：
  1. 等待 `disclosure.md` 与全部 `phase-3-diagram-Dn` 动态任务完成，形成“图包 + 公开稿”汇合屏障。
  2. 主 agent 验证每个 `phase-3/diagrams/Dn-result.tsv` 所绑定的 package、hash、编号和唯一职责，通过 `phase-3-diagram-join` 一次写定 `phase-3/diagram-result.tsv`。
  3. 用 `content-core.json` 中冻结的公开语义字段、公开稿和图包汇总结果生成 `disclosure-manifest.json`，并校验正文与 manifest 同源。
  4. 从已经完成的 `disclosure.md` 复制公开正文，并以 manifest 的追溯字段只在文末追加内部附录，生成 `disclosure-internal.md`。
  5. 汇总正文、内部稿、manifest 和全部图包，生成 `build-map.tsv`。
  6. hash 全部稳定后生成并封存阶段 3 handoff。
- 内部稿不能与对外稿分别写作；图/公开稿尚未 join 时，不得开始内部稿或 manifest。

## 六、阶段 4：语义与视觉并行复核

### 1. 串行屏障

- 主 agent 先冻结阶段 3 `build-map.tsv`，并分别生成语义复核和视觉复核任务包；语义任务逐项绑定四个冻结文本工件，视觉任务逐项绑定同 D 的四个图包工件，派发/fallback 前均运行 `validate-task`。
- `review-plan.json.diagrams` 只列 `D1...Dn`；`DOC` 等非图语义工件放其他字段，避免被逐图 fan-out 误认。
- 两类 reviewer 都只能复核任务包绑定的 hash；正文、manifest 或 SVG 仍在变化时不得派发。

### 2. fan-out

- `patent_semantic_reviewer` 单实例完成：
  - 实现与拟扩展边界复核。
  - 泛化替换测试和逐创新点因果删除测试。
  - 创新—价值—效果映射、来源悬空和对外泄漏复核。
  - 图文编号与图示职责的语义一致性复核。
  - 恰好返回九个固定 check ID 的 row，由主 agent 写 `semantic-review.tsv`。
- `patent_visual_reviewer` 使用最多两个实例，按 `D` 编号划分 SVG：
  - 复核零交叉、零文字遮挡、可读性和布局职责。
  - 每条结论绑定当前 `svg_sha256`。
  - 每张图返回一行绑定 SVG hash 的 row，由主 agent写 `phase-4/visual/Dn-review.tsv`，并绑定动态 checkpoint `phase-4-visual-review-Dn`。
  - 不判断专利新颖性或正文语义。
- 语义与视觉复核并行进行，两个角色均为 `read_only`，不直接写工作区。

### 3. join

- 主 agent 验证 `phase-4-semantic-review` 与全部 `phase-4-visual-review-Dn` 后，通过 `phase-4-review-join` 生成 canonical `phase-4/review.tsv`。
- 任一必做复核为 `fail` 时状态为 `blocked`；结果为 `pending` 时状态为 `review_required`。
- 两类复核都通过后，主 agent只运行一次完整交底包校验，再生成 timing summary 和阶段 4 handoff。

## 七、六个角色的落地合同

### 1. `patent_subject_boundary_analyst`

- 输入：已通过 `validate-task` 的主体边界任务包，以及主 agent 从材料索引/证据卡预生成并 hash 绑定的主体 slice；不读取完整材料索引或证据卡。
- 判断：技术主体与主题、业务/系统/物理边界、系统拥有方、已实现路径与拟扩展候选、图示触发条件。
- 写路径：无直接工作区写权限；主 agent 将结构化返回写入 `phase-1/subject-boundary.tsv`。
- 结果：紧凑 TSV 结论，不复制原始材料或长推理。
- checkpoint：`phase-1-subject-boundary`；`subject-boundary.tsv` 通过 `tsv` 最低检查并绑定 hash 后完成。

### 2. `patent_prior_art_researcher`

- 输入：同一角色派生两个已校验任务包与两个预生成 slice；`object` 实例只包含对象/场景检索线，`mechanism` 实例只包含机制/问题检索线，各自带依据词、上下文词、来源上限和停止条件。
- 判断：页面相关性、证据属性、是否足以说明行业基线、何时停止扩散。
- 写路径：无直接工作区写权限；主 agent 分别将结构化返回写入 `phase-1/research-object.tsv` 和 `phase-1/research-mechanism.tsv`。
- 结果：符合固定表头的研究记录；不返回网页副本或长检索日志。
- checkpoint：对象实例绑定 `phase-1-research-object` / `research-object.tsv`，机制实例绑定 `phase-1-research-mechanism` / `research-mechanism.tsv`；各自通过 `tsv` 最低检查并绑定 hash 后独立完成。

### 3. `patent_innovation_value_analyst`

- 输入：已校验的创新价值任务包，以及主 agent 从主体边界、canonical 研究、证据卡和交付目标预生成的 innovation slice；不直接读取这些完整文件。
- 判断：候选创新是否具有完整机制、约束、实质差异、价值因果、`I/T` 双射和正文/图示落点。
- 写路径：无直接工作区写权限；主 agent 将结构化返回写入 `phase-1/innovation-candidates.tsv`。
- 结果：2–4 组结构化候选，不冻结最终保护范围。
- checkpoint：`phase-1-innovation-candidates`；`innovation-candidates.tsv` 通过 `tsv` 最低检查并绑定 hash 后完成。

### 4. `patent_diagram_engineer`

- 输入：已校验的单图任务包、中心文件预生成的 `diagram-Dn-input.json`、单图角色 guide 和通用 PlantUML 依赖 Skill；每个实例只接收自己负责的 `D` 编号和目录，不读取完整 center plan/content core。
- 判断：图型、节点/步骤、触发条件、编号、布局，以及是否只呈现已实现路径。
- 写路径：只允许写分配的 `disclosure-workspace/diagrams/<D编号>-<用途>/`；不得写正文、manifest 或其他 worker 的目录。
- 结果：每张图生成经过自身 package 校验的 brief、PUML、SVG、validation；主 agent 将该图的结构化返回写入 `phase-3/diagrams/Dn-result.tsv`。
- checkpoint：每张图动态绑定 `phase-3-diagram-Dn`；全部动态任务完成后，主 agent 通过固定的 `phase-3-diagram-join` 汇总为 `phase-3/diagram-result.tsv`。

### 5. `patent_semantic_reviewer`

- 输入：已校验的语义复核任务包；逐项 hash 绑定阶段 3 handoff、正文、内部稿和 manifest，并只加载语义 review guide。
- 判断：固定九项 `SEM-IMPLEMENTATION / SEM-SYSTEM-BOUNDARY / SEM-INNOVATION-VALUE / SEM-GENERALIZATION / SEM-CAUSALITY / SEM-FLOW / SEM-KEYWORDS / SEM-EVIDENCE / SEM-PUBLIC-LEAK`。
- 写路径：无直接工作区写权限；主 agent 将结构化返回写入 `phase-4/semantic-review.tsv`。
- 结果：恰好九行带输入集合 hash 的结论，不增加总评行。
- checkpoint：`phase-4-semantic-review`；结果文件通过 `tsv` 最低检查并绑定 hash 后完成。

### 6. `patent_visual_reviewer`

- 输入：已校验的视觉复核任务包；每个实例只读取被分配图逐项 hash 绑定的 brief、PUML、SVG、validation 和视觉 review guide，不读取完整图计划。
- 判断：交叉、遮挡、可读性、布局和图的唯一目的是否可辨识。
- 写路径：无直接工作区写权限；主 agent 将每张图的结构化返回分别写入 `phase-4/visual/Dn-review.tsv`。
- 结果：按 `D` 编号返回绑定 SVG hash 的视觉结论。
- checkpoint：每张图动态绑定 `phase-4-visual-review-Dn`；全部动态图完成后，由主 agent 通过固定的 `phase-4-review-join` 与语义结果共同汇总。

## 八、事件驱动汇合与禁止轮询

- subagent 只上报 `MILESTONE`、`DECISION`、`BLOCKED`、`COMPLETE`，普通工具调用、文件读写和处理中状态保持静默。
- 主 agent 派发后先完成自己的独立工作；只有到 join 且确实没有其他工作时才进行长时事件等待。
- 禁止：
  - 短间隔重复 `wait`。
  - 使用 `list`、`status`、`read` 或 `sleep` 探测 worker。
  - 发送心跳、百分比进度或“仍在处理”。
  - 因一次非终态等待到期立即重派 worker。
- 收到 worker `COMPLETE` 后，主 agent 先验证结构化结果并写入合同文件，再完成对应 checkpoint；聊天事件本身不是交付物。

## 九、局部失败与恢复

- 通用原则：
  - 先运行 checkpoint `resume`，跳过结果仍存在、非空、最低检查通过且 hash 未变化的任务。
  - 只从第一个失效或未完成任务继续，不重复执行有效 lane。
  - `resume` 只判断单个结果是否有效，不推导任务依赖。上游输入、冻结计划或重做结果发生语义/hash 变化时，由主 agent 选择回退阶段，并显式执行 checkpoint `rollback-stage` 与 `stage_handoff.py rewind`；第一版不做自动依赖分析。
  - 显式回退会重置该阶段及下游 checkpoint/封存状态，但不删除缓存；主 agent 可以重新校验并复用 hash 未变化的独立 lane，不能把旧 join、manifest、内部稿或复核记录直接标回完成。
- 阶段 1：
  - 主体 lane 失败时保留已完成研究缓存，重做主体后重新执行 join。
  - 研究 lane 失败时只重做研究；innovation 后续 lane尚未开始，不生成占位候选。
  - innovation lane 失败时保留主体、研究和交付目标，只重做 innovation。
- 阶段 3：
  - 单图失败只重做该图；其他 hash 未变化的图包直接复用。
  - 单图重做后 hash 未变化，可继续使用原下游绑定；hash 变化时由主 agent 显式回退阶段 3，再重建 `diagram-result.tsv`、manifest、内部稿相关追溯和 `build-map.tsv`，不能沿用旧汇合 hash。
  - 只改正文时不重渲染未变化图包。
- 阶段 4：
  - 只改正文或 manifest 语义字段时重做语义复核，SVG 未变则保留有效视觉结论。
  - SVG 改变时该图的旧视觉结论立即失效，只重做对应图和视觉 lane；若图文语义或编号同时改变，也要重做语义复核。
  - join 只接受当前 `build-map.tsv` 所绑定的 review hash。

## 十、配置目录导航

- `agents/openai.yaml`
  - 只放 Skill 的 UI 元数据、版本和调用提示。
  - 不放 subagent 的模型、DAG、读写权限或 checkpoint 配置。
- `agents/subagents/index.json`
  - subagent 配置总入口，只负责注册 runtime、loading policy、六个角色和四个阶段配置。
- `agents/subagents/loading-policy.json`
  - 渐进加载的机器真源，只维护受众、时机、路径类别和体积上限，不保存业务正文。
- `agents/subagents/runtime.json`
  - 维护并发上限、累计派发上限、checkpoint catalog 指针、事件合同、非轮询等待和 fallback。
- `agents/subagents/roles/`
  - 六个角色各自的静态合同。
  - 维护 role 名称、model、reasoning effort、权限、实例上限、能力、禁止动作、专用说明和允许写入模板；不维护阶段输入、结果路径或 checkpoint 绑定。
- `agents/subagents/stages/`
  - 四阶段 DAG 的机器真源。
  - 维护当前阶段说明、executor、role 引用、输入依赖、parallel group、fan-out、join、checkpoint 引用和运行时任务包路径。
- `agents/subagents/checkpoint-task-catalog.json`
  - 固定任务与动态任务模板的机器真源，维护 owner、结果路径模式和最低检查。
- `agents/subagents/task-packet.template.md`
  - 运行时 v2 三段式任务包模板；只规定“输入 / 需要判断 / 返回”和权限、事件、checkpoint 字段。
- `disclosure-workspace/working/stages/agents/`
  - 真实任务运行时生成的三段式任务包目录，不属于 Skill 静态配置。
  - 每个任务包只写“输入 / 需要判断 / 返回”，以 `path + sha256` 固定行引用当前交底工件；阶段 1 和单图生成的聚焦 slice 存在其 `inputs/` 子目录。
  - 派发或 fallback 前必须执行 `stage_handoff.py validate-task`，检查注册、结构、体积、路径/hash、Skill 资源白名单与权限。
- `references/stage-delivery-contract.md`
  - 维护者使用的跨阶段索引；运行时不读取，阶段细则已拆入 `references/stages/`。
- `references/roles/`、`references/reviews/`
  - 只供对应制图、语义或视觉 subagent 加载的小合同；不得跨角色共读。
- `handbook/progressive-loading.md`
  - 逐阶段、逐角色的文件加载说明和维护检查清单；Skill 运行时不得读取。

### 同源验证边界

- `content-core.json` 是主 agent 在阶段 3 的冻结执行输入，阶段 handoff 会把其 hash 纳入缓存绑定。
- 当前确定性脚本验证 manifest 与对外正文的字段一致性，但不证明某段文本在生成历史上确实由当前 `content-core.json` 派生；这仍是主 agent 必须执行并在阶段汇合时复核的流程合同。
- 因此维护者不能仅凭 checkpoint 的 `json` 最低检查宣称完成了 `content-core → manifest / disclosure` 的机器溯源证明。
