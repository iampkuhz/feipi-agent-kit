# 主体边界分析合同

> 仅供 `patent_subject_boundary_analyst` 执行当前任务时读取。它不是阶段说明，也不授权读取其他 Skill 资源。

## 输入边界

- 只读取已通过 `validate-task` 且有当前 dispatch receipt 的 `subject-boundary-task.md`、唯一绑定的 `subject-boundary-input.json` envelope 和本合同。envelope 的 `slice_version/task_type/role/checkpoint` 必须与任务一致，`source_set_sha256` 必须按规范集合 hash 验证；不一致即 `BLOCKED`。
- slice 中的 `SF` 是来源事实，`IE` 是拟扩展保护；缺少稳定 ID、边界事实或事实互相冲突时返回 `BLOCKED`，不得回读完整材料补齐。

## 必须判断

任务包只以 `JUDGMENT-SUBJECT-BOUNDARY-V1` 引用本节，不得内嵌上下文、JSON、路径或 URL。

1. 提炼可泛化的 `technical_object`、`use_scenario` 和一句 `core_mechanism`，不得暴露类名、字段、JAR、内部产品名或代码结构。
2. 先确定 `business_domain`、`system_owner` 和 `physical_boundary`，再判断系统内外关系。组件总览的顶层候选只允许业务域、独立系统和物理端点；库、处理器、接口实现只能作为下层细节。
3. `implemented_scope` 只能绑定 slice 中已有 `SF`；`extension_scope` 只能绑定已有 `IE`。同一内容不得同时归入两者，不能把计划能力写成当前实现。
4. 只输出证据足以支持的边界。拥有方、物理位置或跨系统关系不明确时显式标记缺口，不用常识猜测。

## 返回合同

任务包只以 `RETURN-SUBJECT-BOUNDARY-TSV-V1` 引用本节。

仅返回与目标 TSV 同构的候选 row，字段顺序固定为：

`subject_id\ttechnical_object\tuse_scenario\tbusiness_domain\tsystem_owner\tphysical_boundary\timplemented_scope\textension_scope\tcore_mechanism`

- ID、范围与结论必须能回指输入 slice 中的稳定 ID。
- 不写目标文件；由 main agent 校验、收敛并落盘。
- 末尾最多附一行 `MILESTONE / DECISION / BLOCKED / COMPLETE` 终态事件。

## 专属禁令

- 禁止读取原始材料、完整 evidence cards、阶段 guide、其他角色合同或其他任务 slice。
- 禁止发明实现事实、替用户决定拟扩展内容、判断专利新颖性，或撰写最终交底正文。
- 禁止把业务目标、技术效果或普通模块拆分冒充主体边界结论。

`read_only` / `result_owner=main_agent` 是行为合同，不等于宿主文件系统 sandbox 或真实写入 provenance；宿主不能施加只读时仍按合同执行，真实遵守须由 trace 核验。
