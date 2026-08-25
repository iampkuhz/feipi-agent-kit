# Subagent 任务包

- contract_version: `2`
- task_type: `{{task_type}}`
- role: `{{role_name}}`
- checkpoint: `{{checkpoint_binding}}`
- result: `{{result_path}}`
- result_owner: `{{result_owner}}`
- minimum_check: `{{minimum_check}}`
- timing: `{{timing_log}}`
- 关键事件: `{{key_event_contract}}`
- 允许写入: `{{allowed_writes}}`
- 本 Skill 资源: `{{allowed_skill_resources}}`
- 依赖 Skill: `{{dependency_skills}}`
- 禁止动作: `{{forbidden_actions}}`

## 输入

### 动态输入

{{dynamic_inputs}}

- 只读取上述动态输入；禁止读取完整阶段缓存、原始材料、未列出的会话文件或其他任务的输入切片。
- 除“本 Skill 资源”所列文件外，禁止读取本 Skill 其他资源。
- 除“依赖 Skill”所列 Skill 外，禁止加载其他 Skill。

## 需要判断

- contract_id: `{{judgment_contract_id}}`

## 返回

- contract_id: `{{return_contract_id}}`

- `result_owner=main_agent` 时，subagent 只返回符合 `minimum_check` 的结构化内容，由主 agent 校验后写入 `result`。
- 只返回结构化结果与一行终态关键事件，不返回日志、正文副本或推理过程。
