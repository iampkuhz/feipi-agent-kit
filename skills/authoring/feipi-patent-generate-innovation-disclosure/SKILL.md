---
name: feipi-patent-generate-innovation-disclosure
description: 用于把零散业务与技术事实整理为带来源台账、PlantUML 图包和内容质量门禁的专利创新交底包；在需要专利交底初稿或评审材料时使用。若只需单图、创意润色、法律意见或 skill 治理，不要使用。
---

# 专利创新交底包生成

## 目标与边界

生成同时具备“对外可读”和“内部可追溯”能力的交付包，而不是只生成一篇格式完整的 Markdown。交付包必须让来源、创新主张、技术效果、图文编号和复核状态相互可追溯，但内部追溯标识不得污染对外版本。

不要把本地校验结果表述为专利新颖性、法律可专利性或外部资料真实性证明。竞品输入缺失时仍须主动检索公开资料；没有找到可用证据时记录检索范围和具体结论，不得留空或输出“待检索”占位，也不得补写未经证实的产品能力。

## 成稿前门槛

先从对话和用户材料提取已知信息，只追问缺失项。进入成稿前必须具备：

- 专利名和使用场景。
- 至少 1 个技术对象。
- 至少 1 个核心机制。
- 至少 1 个必要约束或边界。
- 至少 1 个现有问题事实。
- 至少 1 条可追溯的已实现技术路径，并明确哪些内容只是拟扩展保护。

缺少任一项时定向追问并暂停成稿。不得用推测出的“发明扩展”冒充来源事实或已实现内容。

## 快速执行与资源加载

- 启动时只读取本文件；运行环境支持 subagent 时，再读取 `references/subagent-orchestration.json` 并按其中的 model、`reasoning_effort`、`fork_turns` 和读写边界显式派发。`agents/openai.yaml` 不承载 subagent 角色配置。
- 阶段 1 不读取正式模板或 JSON Schema。先把用户材料压缩为一次性的事实台账和缺口清单；同一材料不重复摘要，缺失项合并为一轮定向追问。
- 用户确认写作思路后，阶段 3 才读取 `assets/proposal_template.md`、`assets/internal_trace_appendix_template.md` 和 `assets/disclosure-manifest.template.json`。`assets/disclosure-manifest.schema.json` 只由校验脚本消费，模型不得逐行分析。
- 阶段 4 只在人工复核时读取 `references/content-quality-gates.md` 的相关规则；确定性格式、路径、hash 和字段检查交给脚本，主 agent 不重复逐项推演。

subagent 最多累计 3 个、同时最多 1 个；子 agent 禁止继续派生。主 agent 保留素材门槛、用户确认、正文合并和最终交付责任：

- `patent_prior_art_researcher`：`gpt-5.6-luna` + `medium`，一次处理两条检索线。
- `patent_diagram_engineer`：`gpt-5.6-terra` + `medium`，确认后只写 `disclosure-workspace/diagrams/`。
- `patent_final_reviewer`：`gpt-5.6-sol` + `high`，最终只读复核一次。

派发时使用 `fork_turns: none`，只传精简任务包，不复制完整对话；指定模型不可用时省略 model override 并保留原 effort，不得把所有角色静默升级为最高模型。运行环境不支持 subagent 时由主 agent 执行同一职责，不降低确认和验证门禁。

## 耗时观测（必做）

真实执行开始时读取 `references/session-timing.md`，立即在 `disclosure-workspace/working/session-timing.jsonl` 初始化新 session。主 agent 是 timing log 的唯一写入协调者，并按以下口径记录：

- 四个阶段分别记录 start/end；阶段 2 包含等待用户明确确认的墙钟时间。
- 每次资源读取记录 `resource_read`；竞品研究记录 `retrieval`；制图 worker 记录 `diagram_generation`。
- PlantUML 图包完成后使用 `ingest-diagram` 导入真实 `render_ms` 与 `static_validation_ms`；完整交底校验必须通过 `session_timing.py run` 包装。
- subagent 派发成功后记录 role、agent id、model、effort；从派发完成到结果返回记录 `subagent_execution`，只有主 agent 实际阻塞时才记录 `subagent_wait`。
- 交付前生成 `session-timing-summary.json` 并确认 `incomplete_spans` 为空。活动可能并行，禁止把各活动耗时简单相加当作 session 总耗时。

## 输出目录合同

将当前交底书目录作为稳定输出根。根部只放需要跟踪和外发的 `disclosure.md`；内部稿、事实模型、验证报告、图包以及任何需要落盘的中间材料统一进入固定工作区 `disclosure-workspace/`。`disclosure-manifest.json` 是内容真源：

```text
<disclosure-dir>/
├── disclosure.md
└── disclosure-workspace/
    ├── disclosure-internal.md
    ├── disclosure-manifest.json
    ├── disclosure-validation.json
    ├── working/                     # 检索记录、写作思路、临时草稿与 session timing
    │   ├── session-timing.jsonl
    │   └── session-timing-summary.json
    └── diagrams/
        └── <D编号>-<用途>/
            ├── brief.normalized.yaml
            ├── diagram.puml
            ├── diagram.svg
            └── validation.json
```

- 根部 `disclosure.md`：唯一对外版本和稳定主入口。不得出现 `SF/IE/EM/C/BD/SYS/PB` 等内部台账编号、内部事实定位、`来源依据` 标签、除 `diagram-id` 外的模板注释，或 `expected_observable/verified/public_fact/reasonable_inference/pending_retrieval/evidence_found/searched_no_usable_evidence` 等机器枚举；公开竞品资料可保留来源链接，必要状态改写为自然中文。
- `disclosure-workspace/disclosure-internal.md`：内部评审版本。公开正文必须与根部 `disclosure.md` 完全一致，只允许在文末增加一份“内部追溯附录（禁止对外）”，集中记录来源台账、创新映射和证据定位。
- `disclosure-workspace/` 是固定保留名，不追加专利名、日期或随机后缀；需要统一忽略时可在仓库根 `.gitignore` 使用 `**/disclosure-workspace/`。不得在工作区内复制第二份 `disclosure.md`。
- manifest 中的 `diagrams/...` 路径相对 `disclosure-workspace/` 解析。外发稿必须自包含，不能引用被忽略工作区中的 SVG 或其他文件。
- 检索日志、写作思路、预览稿、临时导出等文件一旦落盘，必须放入 `disclosure-workspace/working/`，不得与外发稿并列。

对外版本中的拟扩展内容仍使用 `> **拟扩展保护**` 高亮，但不显示 `IE` 编号；`IE` 映射只保留在 manifest 和内部追溯附录中。

只使用工作区内相对路径；禁止绝对路径和 `..`。每个 Markdown PlantUML 块前写稳定标识：

```markdown
<!-- diagram-id: D1 -->
```

`disclosure-workspace/disclosure-validation.json` 的最终状态只有三种：

- `success`：确定性检查和必做复核均通过；可保留诚实警告。
- `review_required`：机器检查通过，但语义或视觉复核仍为 `pending`。
- `blocked`：确定性规则失败，或任一必做复核为 `fail`。

## 分阶段执行流程

### 阶段 1：素材确认与写作建模

1. **建立事实台账**
   - 将输入分为“来源事实 / 发明扩展 / 外部资料”。
   - 为发明扩展记录依据事实；为外部资料记录定位地址、检索日期和证据属性。
   - 将类名、函数、字段、表名和内部产品名泛化为技术表达；必要缩写加入白名单。
   - 单独确认哪些对象、触发条件、处理步骤、约束和输出状态已经实现，哪些只是希望纳入保护范围的扩展；无法确认时定向追问。
   - 已实现基础应接近真实技术路径，但只保留可说明机制的对象、动作、边界和状态，不照搬类名、函数、字段、表结构或产品内部标识。
   - 只保留会进入核心主张、`I/T` 映射或检索词的事实；不做无边界代码库扫描或材料复述。

2. **主动完成行业竞品检索**
   - 无论用户是否提供竞品材料，都使用公开资料检索行业竞品和相似方案；不能把“用户未提供”当作跳过理由。优先交给 `patent_prior_art_researcher`，主 agent 同时继续事实建模。
   - 至少执行两组互不相同的检索：一组围绕泛化后的技术对象与使用场景，一组围绕核心机制与现有问题。每组通过 `basis_terms` 绑定同时存在于输入完整性和关键词中的技术词，并通过 `context_terms` 绑定另一技术分类或已确认使用场景；两类词都必须以纯文本原样进入检索式，检索式还要包含产品、官方、专利、论文、标准或相似方案等研究限定词。不得用内部产品名、类名、字段名、HTML entity、零宽字符或其他未授权标识伪造检索关联。
   - 两组检索在一次 subagent 任务内并行执行。每组最多打开 3 个候选页面；优先查阅官方产品页、官方技术文档、公开专利、标准或论文等一手资料。每组记录焦点、检索式、检索日期、实际查阅页面和结果摘要；执行时必须人工检查整条检索式及结果是否与主题相关，本地脚本不会判断剩余自由文本的语义相关性。
   - 找到足以说明行业基线的可靠材料后立即停止扩散，总计只保留 1–3 项最佳证据；证据的定位地址和日期必须能回溯到检索记录。两组检索均无可用材料时记录 `searched_no_usable_evidence`，对外使用固定无具名断言结论，详细发现只留在内部检索记录中。
   - 检索工具不可用、页面无法访问或两类检索记录不完整时，暂停最终成稿并报告阻塞；不得用“待检索”占位后继续交付。

3. **确定边界与主张**
   - 先确定业务域、系统归属、拥有方、物理边界和部署触发条件，再拆组件。
   - 先写唯一的核心发明主张，再提炼 2–4 个 `I1...In` 创新点。
   - 每个创新点写全对比基线、核心机制、必要约束、实质差异、价值关联、对应 `T` 效果和正文/图示落点。
   - 每个创新点必须先绑定一条来源事实支持的已实现基础；拟扩展保护可选，但每项必须引用“发明扩展”台账中的唯一 `IE` 编号，并由该台账继续追溯来源事实。
   - 已实现内容与拟扩展保护必须分开记录，不能把扩展伪装成已经上线或验证的事实，也不能保留未被任何创新点使用的孤立 `IE`。
   - 对比基线优先使用来源事实中的现有做法；没有外部证据时只写通用技术做法，不得借此虚构具名竞品能力。

4. **建立效果映射**
   - 为每个创新点建立唯一的 `T1...Tn` 技术效果，保持一一映射。
   - 每项写全原问题、采用机制、可观察结果和验证状态。
   - 价值关联必须说明“哪一项差异为什么会产生哪一个可观察结果”，不能只写采用了什么处理方式或笼统宣称有好处。
   - `verified` 必须通过 `evidence_source_ids` 绑定已有 `SF/EM`；没有实测数据时使用 `expected_observable`。

此阶段只形成事实模型和候选写作结构，不输出最终版交底书或最终图包。

### 阶段 2：提交写作思路并等待确认

- 向用户提交精简的“写作思路”，至少包含：核心发明主张、章节论证顺序、候选 `I/T` 映射、每项创新的“已实现基础 / 带 `IE` 编号的拟扩展保护 / 与现有做法的差异 / 产生什么价值”、竞品检索范围与结论、图示规划、证据缺口与拟处理方式。
- 写作思路只给确认所需的摘要和映射，不提前扩写完整章节、最终 manifest 或图包；默认不落盘。
- 阶段 2 使用内部确认格式 `> **拟扩展保护（IEx）**`，不能只用普通列表或含混措辞标记扩展；最终对外版保留高亮块但移除 `IE` 编号。
- 阶段 2 属于内部确认材料，可以显示 `SF/IE/EM` 追溯编号；必须明确这些编号不会进入最终对外版本。
- 明确标注当前处于“思路待确认”状态，并暂停最终版本撰写。
- 只有收到用户明确的确认、同意或等价表述后，才进入阶段 3；不得把沉默、未回复或仅补充材料视为确认。
- 用户提出调整时，更新写作思路并再次等待确认；如需将写作思路或预览稿落盘，只能写入 `disclosure-workspace/working/`。确认前不得生成最终版 `disclosure.md`、完整 manifest 或最终图包，也不得把预览稿称为最终版。

### 阶段 3：撰写最终版本

5. **规划并生成图示**
   - 用户确认后先冻结 `I/T/D/E/S` 与图示职责，再把全部图交给一个 `patent_diagram_engineer`；主 agent 可同时撰写正文，双方不得改写对方负责的文件。
   - 统一调用 `$feipi-plantuml-generate-diagram`：先一次性完成全部 brief，再对各图生成 diagram package。每张图的 `validate_package.sh` 已内置 verifier，只调用一次；不得再手工重复调用 `verify_package.py`。
   - 必须且只能有 1 张 `component_overview` 和 1 张 `main_flow`。
   - 主流程由分支/状态驱动时使用 `activity`；由多方调用/回执驱动时使用 `sequence` 且设置 `numbering_scheme: process_s`。
   - 出现跨网、跨链、在线/离线、HSM、人工摆渡或人工交接时，增加 `deployment_boundary`。
   - `module_detail` 每张只展开一个父组件；`core_mechanism` 仅在有独立目的时生成，不为凑图添加。
   - 图示只呈现已实现技术路径，拟扩展保护统一在正文高亮块和内部附录中表达，不进入 PlantUML 或 SVG；视觉复核记录必须明确写出“仅呈现已实现路径”。
   - 图示使用 `D1...Dn`；结构关系使用 `E1...En`；流程使用 `S1...Sn`、`S5.1...`。专利文档不得出现 `M/R` 编号。
   - 默认只生成两张必需图；只有命中明确触发条件才增加图。已变图最多修复并重渲染 2 轮，只重跑失败的图；再次处理完全未变图包时使用 `--reuse-valid-package`，命中 hash 合同后不得访问 renderer。

6. **按模板写作**
   - 标题、使用场景、核心发明主张、关键词及 `I/T` 字段从 manifest 原样渲染，补充解释写在原字段之后。
   - 每个创新点按“对比基线 → 处理方式 → 实质差异 → 价值因果 → 对应可观察效果”连续呈现；不得把价值拆到远处后只在创新点中留下处理方式。
   - 先按 `assets/proposal_template.md` 在交底书目录根部生成对外版 `disclosure.md`：每个创新点用“已实现基础”说明经泛化后的具体技术路径，但不显示来源编号；每个可选扩展分别放入醒目的 `> **拟扩展保护**` 引用块，不显示 `IE`；无扩展时不显示空占位块。
   - 再复制完整对外正文生成 `disclosure-workspace/disclosure-internal.md`，仅按 `assets/internal_trace_appendix_template.md` 在文末追加内部追溯附录；不得在两份正文中分别改写同一段内容。
   - 正文论证以已实现基础为主，扩展保护只说明希望覆盖的等价机制、参数范围或部署变体，不得反向改写为已实现事实。
   - “是否还有其他解决方案”章节不重复裸写扩展内容；有拟扩展保护时统一写“拟扩展保护已在对应创新点下高亮列出，本节不重复”，没有时写“无”。
   - 关键词固定为 5–8 个：技术对象 1–2、核心机制 2–4、关键约束 1–2，三组互斥。
   - 顶层组件只放业务域、独立系统和物理端点；实现类、函数、JAR、处理器和表字段只能作为细节。
   - 主流程顶层保持连续 5–10 步；箭头标签只保留编号或一个动作短语，参数和异常处理写在图下。
   - 竞品部分必须展示检索范围、检索日期和结论；存在可靠证据时再列出 1–3 项。没有可用证据时写清已经查阅了什么以及为什么不能形成具名对比，不得留空或出现“待检索”。

### 阶段 4：复核、验证与交付

7. **完成语义与视觉复核**
   - 所有正文和图包冻结后只派发一次 `patent_final_reviewer`，合并完成语义与视觉复核；不要为同一工件分别启动多个高模型 reviewer。
   - 执行泛化替换测试：替换领域名词后仍适用于任意系统的内容判为失败。
   - 逐项执行因果删除测试：删除核心机制后技术效果仍成立的映射判为失败。
   - 复核 SVG 是否零交叉、零文字遮挡；复核结果绑定当前 `svg_sha256`，图变化后重新复核。
   - 机器脚本只验证复核记录及其绑定关系，不声称自动理解语义或视觉质量。
   - 复核对外版不含内部台账编号、来源定位和机器枚举；复核内部版的公开正文与对外版同源，所有追溯信息只出现在内部附录。

8. **验证并交付**
   - 图包在生成阶段已经完成一次校验；阶段 4 不再逐图重跑 renderer。视觉复核完成后只调用一次完整交底包入口，入口会在当前进程复用通用图包 v1.1 verifier 重算路径、状态、hash 与实际 metrics。
   - 只修改正文、manifest 或复核记录时，不重新渲染未变图。只有 brief/PUML/SVG 内容变化才重跑对应图包并使旧视觉复核失效。
   - 修复 `blocked` 规则后只重跑受影响入口；`review_required` 必须完成相应人工复核后再交付为 `success`，不得进行无修改的固定次数轮询。
   - 保留验证报告中的警告和验证边界；检索无可用证据时保留具体研究结论，不得为了消除空结果而改写成伪证据。
   - 生成 timing summary；若存在未结束 span，只能说明观测不完整并修复记录，不能宣称已具备完整耗时证据。

## 校验入口

兼容旧调用，仅检查单篇草稿并提示缺少完整交付包：

```bash
bash scripts/check_disclosure_format.sh <document.md>
```

完整交付的唯一主入口：

```bash
bash scripts/validate_disclosure_package.sh <disclosure-dir>
```

## 失败处理

- 输入不足：列出缺失字段并定向追问，不生成占位成稿。
- 实现与扩展边界不明：列出待确认的机制，暂停最终成稿；不得自行判断某项已经实现。
- 内外版本不一致：以对外版正文为唯一公开正文，重新生成内部版并仅追加追溯附录；不得人工维护两套不同正文。
- 来源悬空：删除断言或补齐来源；竞品资料不足时继续检索，完成两类检索后仍无可用证据则记录具体结论，不要猜测。
- 竞品检索不可用：说明检索工具或页面访问阻塞并暂停最终成稿；不得生成空章节或“待检索”占位稿。
- 图包失败：先修 diagram package，不把未通过的 PlantUML 贴入正文。
- 语义或视觉复核待完成：输出 `review_required`，不得宣称全部通过。
- 校验规则与模板冲突：以 schema 和 `references/content-quality-gates.md` 为内容合同，记录冲突并修复同源资源。

## 资源导航

- 内容质量规则：`references/content-quality-gates.md`
- subagent 分级编排：`references/subagent-orchestration.json`
- session 耗时观测：`references/session-timing.md`
- 正式文档模板：`assets/proposal_template.md`
- 内部追溯附录模板：`assets/internal_trace_appendix_template.md`
- manifest 模板与 schema：`assets/disclosure-manifest.template.json`、`assets/disclosure-manifest.schema.json`
- 草稿兼容样例：`references/cases/happy-case-full.md`
- 完整合成交付包：`references/cases/happy-package/`
