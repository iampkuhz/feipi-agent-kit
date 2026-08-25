# 双线现有技术研究合同

> 供 `patent_prior_art_researcher` 的 object/mechanism 两个实例共用。任务实例由已校验任务包的 `task_type` 唯一决定，不能跨 lane 扩读。

## 实例与输入边界

- `prior-art-object` 只研究技术对象/使用场景，只读 `prior-art-object-input` slice。
- `prior-art-mechanism` 只研究核心机制/现有问题，只读 `prior-art-mechanism-input` slice。
- 只读取有当前 dispatch receipt 的任务包、唯一绑定的 JSON envelope 和本合同。envelope 的 `slice_version/task_type/role/checkpoint` 与任务必须一致，`source_set_sha256` 必须按规范集合 hash 验证；不得读取另一 lane 的任务包、slice、页面集合或结果。

## 检索合同

object 任务包只引用 `JUDGMENT-PRIOR-ART-OBJECT-V1`，mechanism 只引用 `JUDGMENT-PRIOR-ART-MECHANISM-V1`；任务包不得内嵌上下文、JSON、路径或 URL，检索 URL 只允许存在当前 envelope 的 `payload`。

1. 查询同时包含 slice 给出的 `basis_terms`、`context_terms` 和官方、产品、专利、论文、标准或相似方案等限定词；两类术语必须以纯文本原样进入查询。
2. 禁止把内部产品名、未授权标识、HTML entity、零宽字符或控制字符带入查询。
3. 每个 lane 最多打开 3 个候选页面，优先官方页面/文档、公开专利、标准和论文；证据已足以说明该 lane 的行业基线时立即停止。
4. 只摘录与当前 lane 直接相关、可由 locator 复核的事实，并区分页面明示事实与合理推断。不得从摘要片段或相邻产品推导具名能力。
5. 找不到可用证据时返回 `searched_no_usable_evidence`，写清实际查询范围、打开页面和不指向具名对象的结论；检索工具不可用或页面均不可访问时返回 `BLOCKED`，不能伪装成“无证据”。

## 返回合同

对应任务包只引用 `RETURN-PRIOR-ART-OBJECT-TSV-V1` 或 `RETURN-PRIOR-ART-MECHANISM-TSV-V1`。

仅返回与 lane TSV 同构的紧凑 row，字段顺序固定为：

`lane\tquery_id\tsource_id\tevidence_status\tlocator\tconclusion`

- `lane` 必须与当前 `task_type` 一致；object/mechanism 各自使用独立 `query_id`、`source_id` 和 slice。
- 不合并两条 lane，不写 canonical `research.tsv` 或目标文件；由 main agent 校验、去重并落盘。
- 末尾最多附一行 `MILESTONE / DECISION / BLOCKED / COMPLETE` 终态事件。

## 专属禁令

- 禁止读取未列原始材料、完整 evidence cards、另一 lane 或其他角色资源。
- 禁止无来源断言竞品能力、发布日期或市场状态，禁止承诺新颖性/创造性。
- 禁止超过页面上限继续扩散检索，或为了凑数量保留低相关结果。

`read_only` / `result_owner=main_agent` 是行为合同，不等于宿主 sandbox 或真实写入 provenance；无法施加只读时仍按合同执行，并由真实 trace 核验。
