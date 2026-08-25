# Subagent 任务包

- role：`{{role_name}}`
- checkpoint：`{{checkpoint_binding}}`
- timing log：`{{timing_log}}`
- 关键事件：`{{key_event_contract}}`

## 输入

{{input_references}}

- 只读取上述引用，不复制完整对话或未点名的原始材料。
- 允许写入：{{allowed_writes}}
- 禁止动作：{{forbidden_actions}}

## 需要判断

{{judgment_contract}}

## 返回

{{return_contract}}

- 只返回结构化结果与一行终态关键事件，不返回日志、正文副本或推理过程。
