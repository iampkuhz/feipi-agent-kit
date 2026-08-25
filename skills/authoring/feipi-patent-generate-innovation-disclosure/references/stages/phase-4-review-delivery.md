# 阶段 4：复核、验证与交付

> 仅供阶段 4 主 agent 加载。语义和视觉 reviewer 不读取本文件，也不读取完整质量总表。

## 输入与复核计划

只读取已封存的 `phase-3/handoff.md`、`build-map.tsv` 指向的冻结工件及其当前 hash。不得读取原始材料、旧阶段 guide、竞品网页、handbook、案例或 schema 文本。

主 agent 先生成 `phase-4/review-plan.json`：

- 正文、manifest 和内部稿放语义工件字段。
- `diagrams` 只列连续 `D1...Dn`，每项绑定 SVG、brief、validation、冻结职责和当前 hash。
- 非图工件不得混入逐图数组。

计划通过最低检查后，语义复核与逐图视觉复核才可并行。

## 并行派发

- 语义任务包直接逐项列出 `disclosure.md`、内部稿、manifest 和阶段 3 handoff 的相对路径与 SHA-256；不传原始材料、完整 content core/diagram plan 或本阶段 guide。
- 每张图的视觉任务包只逐项列出该 D 的 brief、PUML、SVG、validation、冻结职责与各自 SHA-256；不得引用完整 diagram plan、其他图或目录通配符，最多两个并行实例。
- 任务包“需要判断/返回”只写注册合同 ID：语义为 `JUDGMENT-SEMANTIC-REVIEW-V1` / `RETURN-SEMANTIC-REVIEW-TSV-V1`，逐图视觉为 `JUDGMENT-VISUAL-REVIEW-Dn-V1` / `RETURN-VISUAL-REVIEW-Dn-TSV-V1`；不得内嵌上下文、JSON、路径或 URL。
- 每次派发或 fallback 前必须运行 `validate-task`；成功时原子写入 `stages/agents/receipts/<task-basename>.dispatch.json`，绑定任务 hash、TaskSpec 和动态输入集合 hash。失败或 receipt 缺失/过期不得启动。
- 语义 reviewer 和视觉 reviewer 均为 `read_only`：语义 reviewer 恰好返回 `SEM-IMPLEMENTATION`、`SEM-SYSTEM-BOUNDARY`、`SEM-INNOVATION-VALUE`、`SEM-GENERALIZATION`、`SEM-CAUSALITY`、`SEM-FLOW`、`SEM-KEYWORDS`、`SEM-EVIDENCE`、`SEM-PUBLIC-LEAK` 九行；每个视觉 reviewer 返回当前 D 的一行。主 agent 校验后分别写 `semantic-review.tsv` 与 `visual/Dn-review.tsv`，reviewer 不落盘。
- subagent 可用时，主 agent 不读取 review 专用 guide 来替 worker 执行，也不轮询；它继续准备验证入口与 timing 汇总，到真实 join 屏障才长时事件等待。只有运行环境不支持 subagent 时，主 agent 才为当前 fallback 节点加载已校验任务包和对应 review guide；不得顺带读取另一类 review guide。

语义职责覆盖实现/扩展边界、创新—价值、泛化替换、逐 I/T 因果删除、对外泄漏与图文 ID 一致性；视觉职责覆盖单图交叉、遮挡、唯一目的、已实现路径边界和 SVG hash。两者互不替代。

语义九行的 `bound_sha256` 是四项动态输入的规范化集合 hash：路径去重后按 UTF-8 字典序排序，逐项输入 `path UTF-8 + NUL + 当前文件 sha256 ASCII + LF`，再计算 SHA-256。逐图 visual row 的 `bound_sha256` 必须等于阶段 3 三类 D 行共同绑定的对应 `diagram.svg` 当前实际 SHA-256；不得使用任务包、receipt 或任意 package hash 代替。

`read_only` 与 `result_owner=main_agent` 是行为合同，不等于宿主已施加文件系统 sandbox 或证明写入 provenance；宿主无法施加时仍按合同执行，并在真实 trace 核验。本地脚本只能证明声明、receipt 和工件 hash 自洽。

## 汇合与确定性验证

1. 主 agent 写入后校验 `semantic-review.tsv` 和全部 `visual/Dn-review.tsv` 均存在、格式有效且绑定当前工件 hash；语义结果必须恰好覆盖固定九个 check ID。
2. 任一计划图缺少视觉结果、hash 过期或职责不匹配时，不得 join。
3. 主 agent 汇合为唯一 `phase-4/review.tsv`；subagent 不能直接追加该文件。
4. 所有复核结果到齐后，调用一次完整交付入口：

```bash
bash scripts/validate_disclosure_package.sh <disclosure-dir>
```

图包在阶段 3 已渲染和自校验；阶段 4 不逐图重跑 renderer。完整入口复用图包 verifier 复算路径、状态、hash 和 metrics，但不自动证明语义或视觉质量。

状态解释：

- `success`：确定性检查与必做复核均通过；可保留诚实警告。
- `review_required`：机器检查通过，但语义或视觉复核仍 pending。
- `blocked`：确定性规则失败或任一必做复核 fail。

只修改正文、manifest 或复核记录时不重渲染未变图；brief/PUML/SVG 变化时，回阶段 3 重跑对应图并使旧视觉复核失效。

## timing 与交付

- 完整校验后生成 timing summary；存在未结束 span 时只能说明观测不完整，不能宣称已有完整性能证据。
- `phase-4/handoff.md` 写最终工件相对路径、状态、警告、验证边界和 timing summary 路径，不复制工件正文。
- seal 会复验本阶段全部 dispatch receipt 并纳入 cache digest；随后运行 `stage_handoff.py validate --working <disclosure-workspace/working> --require-complete`，确认四阶段封存链完整后再交付。
- 最终答复承担主任务 `COMPLETE`，只给外发稿、必要内部工件路径、状态、警告和验证边界，不重复发送完成事件。

本地脚本不能证明外部资料真实/最新、专利新颖性或法律可专利性、真实组织边界、机制效果在生产环境成立，也不能静态证明 SVG 绝对零交叉/零遮挡。未获得脱敏真实 Session 前，只能声明合成回归通过。

复核 fail 且没有可继续的本阶段动作时记录 `BLOCKED`；需要用户选择不同处置才可继续时记录 `DECISION`。禁止通过无修改重复运行把 fail/pending 变为 success。
