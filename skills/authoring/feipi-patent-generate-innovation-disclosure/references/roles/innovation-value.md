# 创新与价值分析合同

> 仅供 `patent_innovation_value_analyst` 执行当前任务时读取。输入 slice 必须由主体边界、交付目标和双线研究汇合后生成。

## 输入边界

- 只读取已通过 `validate-task` 且有当前 dispatch receipt 的 `innovation-value-task.md`、唯一绑定的 `innovation-value-input.json` envelope 和本合同。envelope 的 `slice_version/task_type/role/checkpoint` 必须与任务一致，`source_set_sha256` 必须按规范集合 hash 验证；不一致即 `BLOCKED`。
- 只消费 slice 中列明的稳定 `SF / IE / EM`、主体边界、交付目标和 canonical research 摘要；不得回读这些完整文件或原始材料。
- 必要来源、对比基线或实现/扩展归属缺失、冲突时返回 `BLOCKED`，不得自行补造。

## 必须判断

任务包只以 `JUDGMENT-INNOVATION-VALUE-V1` 引用本节，不得内嵌上下文、JSON、路径或 URL。

1. 每个候选必须形成连续链：`problem → mechanism → necessary constraint → baseline → substantial difference → value causality → observable effect`。
2. `difference_hypothesis` 必须说明技术对象、关系、状态或约束相对基线发生的变化；普通模块新增、步骤复述或“更智能/更高效”等泛化词不能单独构成差异。
3. `value_chain` 必须解释“该差异为什么导致该结果”。删除核心机制后效果仍成立，或换成任意行业仍成立时，候选应降级或拒绝。
4. 每项已实现基础至少绑定一个 slice 中已有 `SF`；拟扩展内容只能绑定已有 `IE`，且与已实现内容分栏。外部基线只使用有 locator 的 `EM` 或不指向具名对象的诚实结论。
5. 效果必须可观察并带 `validation_status`；无实测材料时使用 `expected_observable`，不得伪造数据或把预期写成已验证。

## 返回合同

任务包只以 `RETURN-INNOVATION-VALUE-TSV-V1` 引用本节。

仅返回与候选 TSV 同构的 row，字段顺序固定为：

`candidate_id\tsource_fact_ids\textension_ids\tproblem\tmechanism\tconstraint\tbaseline\tdifference_hypothesis\tvalue_chain\teffect\tvalidation_status\tdiagram_landing`

- 候选 ID、来源绑定和 D/E/S 落点必须来自输入 slice 的允许集合。
- 只给候选，不决定最终核心主张、正式 I/T、全局编号或图职责；由 main agent 收敛。
- 不写目标文件；末尾最多附一行 `MILESTONE / DECISION / BLOCKED / COMPLETE` 终态事件。

## 专属禁令

- 禁止读取原始材料、完整阶段结果、其他角色合同或未列任务 slice。
- 禁止承诺专利新颖性、创造性或法律可专利性。
- 禁止合并已实现与拟扩展内容，或用无因果泛化收益填补证据缺口。

`read_only` / `result_owner=main_agent` 是行为合同，不等于宿主 sandbox 或真实写入 provenance；无法施加只读时仍按合同执行，并由真实 trace 核验。
