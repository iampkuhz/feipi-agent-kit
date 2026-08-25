---
name: feipi-patent-generate-innovation-disclosure
description: 用于把零散业务与技术事实整理为带来源台账、PlantUML 图包和内容质量门禁的专利创新交底包；在需要专利交底初稿或评审材料时使用。若只需单图、创意润色、法律意见或 skill 治理，不要使用。
---

# 专利创新交底包生成

## 目标与边界

生成“唯一对外稿 + 内部可追溯工作区”。来源、实现/扩展边界、核心主张、I/T、图文编号和复核状态必须互相可追溯，内部编号不得进入对外稿。本地校验不能证明资料真实、新颖性、创造性或可专利性；仍须主动检索竞品，未找到证据时记录范围和无具名断言结论，不得留空或虚构。

## 成稿前门槛

先从对话和用户材料提取已知信息，只追问缺失项。进入最终撰写前必须具备：

- 专利名和使用场景。
- 至少一个技术对象、核心机制、必要约束或边界、现有问题事实。
- 至少一条可追溯的已实现技术路径。
- 已明确哪些内容已经实现，哪些只是拟扩展保护。

缺少任一项时定向追问并暂停成稿。不得用推测的“发明扩展”冒充来源事实或已实现内容。

## 渐进式加载（必做）

本文件是必须完整读取的轻量入口。运行时加载图以 `agents/subagents/loading-policy.json` 为机器真源：

1. 启动只读取本文件、subagent `index.json`、`runtime.json` 和 `loading-policy.json`；session timing 说明仅初始化/恢复时按需读取一次。
2. 每个阶段开始只读取 `agents/subagents/stages/phase-N.json` 和它声明的唯一阶段说明；不得预读其他阶段说明。
3. role 配置与任务包模板仅在当前角色派发/fallback 前读取；不得批量读取。任务包“需要判断/返回”只写 TaskSpec 注册的固定 `contract_id`，不内嵌上下文、JSON、路径或 URL；派发消息只传任务包路径。
4. 阶段 1/逐图 slice 必须是带 task identity 和 `source_set_sha256` 的 JSON envelope。派发/fallback 前运行 `validate-task`；成功会生成绑定任务、TaskSpec 与动态输入集合的 dispatch receipt。失败、receipt 缺失或过期不得启动，seal 会复验本阶段 receipt 并纳入 cache digest。
5. subagent 使用 `fork_turns: none`，只读自己的任务包、hash 绑定输入和专用小合同；不得读取本文件、阶段说明、配置、其他合同、完整对话或未点名材料。制图只写独占图包，其余角色只读，结果由主 agent 写入。
6. 阶段 3 的三个模板按节点延迟读取：`public-draft` 读取对外稿模板，`manifest` 读取 manifest 模板，`internal-draft` 读取内部附录模板；制图 worker 不读取这些模板。
7. Schema、catalog、校验器和测试只由脚本消费；handbook、history、案例、总索引和内容总表仅供维护者阅读。

如果声明资源与实际任务不一致，先修任务包或配置，不得用读取整个目录、总合同或其他阶段文件绕过。加载矩阵的人读说明见 `handbook/progressive-loading.md`，但该文件运行时禁止读取。

## 四阶段路由

### 阶段 1：素材确认与写作建模

读取 `references/stages/phase-1-material-modeling.md`。本阶段是既有原始材料的唯一读取者：建立材料索引、证据卡、来源/扩展/外部资料台账、实现/扩展边界、双线竞品检索、主体边界和候选创新—价值映射，最后由主 agent 收敛 `model.md` 与封存 handoff。

主体边界、两条检索 lane 与交付目标可并行；候选创新等待汇合。原始材料不得直接传给后续阶段或 subagent。

### 阶段 2：提交写作思路并等待确认

读取 `references/stages/phase-2-idea-confirmation.md`。只消费阶段 1 handoff、其中点名的模型条目和用户本轮反馈。向用户提交核心主张、I/T 映射、实现/扩展边界、差异—价值、竞品结论和图示计划，明确标记“思路待确认”，然后结束本轮。

明确确认后才能封存；沉默、补充材料或含混反馈不算确认，来源事实变化回阶段 1。

### 阶段 3：撰写最终版本

读取 `references/stages/phase-3-final-drafting.md`。只消费已确认的阶段 2 handoff，先冻结 `content-core.json` 与中心 `diagram-plan.json`，再让主 agent 的唯一对外稿与逐图 worker 并行。每张图使用独立目录、任务包、结果和动态 checkpoint `phase-3-diagram-Dn`；全图汇合后才生成 manifest、内部稿、build map 和 handoff。

逐图 worker 使用 `$feipi-plantuml-generate-diagram`，只写一张图包并返回 row。主 agent 写 Dn/聚合/build-map 行前复算对应 `diagram.svg` 的实际 SHA-256；三处一致，不使用 package hash。

### 阶段 4：复核、验证与交付

读取 `references/stages/phase-4-review-delivery.md`。只消费阶段 3 handoff 与 build map 指向的冻结工件。语义 reviewer 与逐图视觉 reviewer 并行：前者只读语义专页与文本工件，后者只读视觉专页与单图工件；每图使用动态 checkpoint `phase-4-visual-review-Dn`。

reviewer 只读并返回 row。语义九行绑定其四个输入的规范集合 hash；visual row 绑定阶段 3 同一 SVG 实际 hash。主 agent 落盘、汇合并只执行一次完整校验；脚本通过不等于复核通过。

## 主代理与 subagent 边界

主 agent 保留输入门槛、用户确认、核心主张、全局编号、正文同源、任务包/envelope/receipt、row 落盘、回退、join、最终校验和交付。subagent 只做单一职责；结果通过最低检查前不能完成。

`permission` / `result_owner` 是可校验行为合同，不等于宿主文件系统 sandbox 或真实写入 provenance。宿主不能施加只读/独占写目录时仍按合同执行，并用真实 trace 核验；本地脚本不能证明真实写入者。

同时最多三个 subagent，整个任务最多创建九个，禁止递归派生。运行环境不支持 subagent 时，主 agent 只为当前 fallback 节点加载同一任务包、该 role 的专用小合同和依赖 skill，并按同一合同执行；不能批量加载其他 role，也不能降低确认、来源、复核或验证门禁。

事件只允许 `MILESTONE / DECISION / BLOCKED / COMPLETE`；subagent 只报主 agent，普通进度静默。派发后继续独立工作，到依赖屏障才长时等待；禁止短轮询。阶段 2 等用户确认时结束本轮。

## 检查点、封存与恢复

每次真实任务维护 `<disclosure-dir>/disclosure-workspace/working/CHECKPOINT.md`。它只记录当前阶段、输入、任务、已交付、下一步和阻塞项，只在阶段开始、任务完成、等待用户或阻塞时更新；禁止记录微步骤、工具过程或重复进度。

任务仅在唯一结果存在、非空、最低检查通过且绑定当前 SHA-256 后完成。恢复先执行 checkpoint `validate/resume`，从首个 pending/失效项继续，再用 handoff `status` 核对封存链；不得手改 CHECKPOINT 或读取 catalog 替代脚本。

用户修改输入或冻结计划时，由主 agent 选择回退阶段并说明理由，先执行 checkpoint `rollback-stage`，再对同一阶段执行 handoff `rewind`。第一版不自动分析依赖，不能静默猜测回退范围。

每阶段以 handoff `status` 取输入、以 `seal` 封存；上游未封存不得启动下游。handoff 不超过 24 KiB，只传 ID、相对路径、hash、决策和未决项。

具体命令以 `scripts/checkpoint.py --help`、`scripts/stage_handoff.py --help` 和当前阶段说明为准。

## 输出与编号合同

稳定输出根只保留唯一外发稿，其余产物进入固定工作区：

```text
<disclosure-dir>/
├── disclosure.md
└── disclosure-workspace/
    ├── disclosure-internal.md
    ├── disclosure-manifest.json
    ├── disclosure-validation.json
    ├── working/
    │   ├── CHECKPOINT.md
    │   └── stages/
    └── diagrams/<D编号>-<用途>/
```

- `disclosure.md` 是唯一对外版本，不得出现 `SF/IE/EM/C/BD/SYS/PB`、内部定位、机器枚举或内部附录。
- 内部稿的公开正文必须与对外稿一致，只能在文末追加“内部追溯附录（禁止对外）”。
- 工作区固定命名为 `disclosure-workspace/`；需要统一忽略时使用 `**/disclosure-workspace/`，不得追加专利名、日期或随机后缀。
- 拟扩展内容在对外稿使用 `> **拟扩展保护**` 高亮，不显示 `IE`；图示只呈现已实现路径。
- 可见编号统一为 `D` 图示、`E` 结构关系、`S` 主流程/子调用、`I` 创新点、`T` 技术效果。专利文档不得出现 `M/R`。
- 每个 PlantUML 块前写 `<!-- diagram-id: Dn -->`；外发稿必须自包含，不能依赖被忽略工作区的 SVG。

最终验证状态只有：`success`（确定性检查和必做复核通过）、`review_required`（机器通过但复核待完成）、`blocked`（确定性失败或复核失败）。

## 校验与失败处理

草稿兼容检查：

```bash
bash scripts/check_disclosure_format.sh <document.md>
```

完整交付唯一入口：

```bash
bash scripts/validate_disclosure_package.sh <disclosure-dir>
```

- 输入不足、实现/扩展边界不明或竞品检索不可用：说明缺口并暂停最终成稿。
- 来源悬空或竞品证据不足：删除断言、补证据，或保留已检索无可用证据的诚实结论；不得猜测。
- 图包失败：只修失败图，不把未通过的 PlantUML 写入正文。
- 检查点结果失效：从 `resume` 返回的首个任务重做，不伪造完成状态。
- 语义或视觉复核待完成：保持 `review_required`，不得宣称全部通过。
- 规则、模板和脚本冲突：停止交付，按稳定规则编号定位并修复同源资源。

## 资源路由

- 当前阶段说明：`references/stages/`
- subagent 专用小合同：`references/roles/`、`references/reviews/`
- subagent 配置入口与加载策略：`agents/subagents/index.json`、`agents/subagents/loading-policy.json`
- session timing：`references/session-timing.md`（主 agent 初始化/恢复时按需读取一次）
- 模板：`assets/`（仅阶段 3 对应节点按需读取）
- 阶段总索引、内容规则总表、handbook、历史和案例：仅维护者使用，运行时禁止读取。
