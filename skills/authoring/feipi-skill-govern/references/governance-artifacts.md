# 治理记录与正式交接

需要恢复执行、跨阶段交接或多功能汇总时，使用一份 `governance-record.json` 保存本轮状态。简单任务可在报告中采用同样的信息关系，不强制增加文件。模板为 `../templates/governance-record.template.json`；模板不是实际报告，也不能直接作为完成证据。

## 输入绑定

在唯一的仓库 `tmp/` 子目录或系统临时目录保存本轮用户请求原文和输入材料快照，再复制模板。指纹用 Python 标准库 `hashlib.sha256(path.read_bytes()).hexdigest()` 计算。记录与被引用文件必须一起保存，路径相对记录文件解析；可引用显式指定的外部文件。

- `schema_version` 固定为整数 `1`。
- `target_skill` 写本轮目标；全仓任务明确填写 registry 范围。
- `request_sha256` 绑定请求文件的原始字节，校验时必须重新提供当前请求文件，不能只信记录中的旧请求。
- `inputs`：每项有 `id`、`path`、`sha256`，保存来源材料的快照。`request` 为保留来源 ID，不重复声明。
- 不把待修改的源码文件当作不可变输入直接绑定；保存其基线快照或记录基线 Git revision。恢复时另查当前源码，避免预期修改被误判为材料污染。

输入变化后先重建绑定，重做依赖该输入的分析及下游交付；禁止只改哈希来让旧结果通过。

## 问题、验证与产物

`problems` 逐项保存用户需求及审计发现，不只保存目标名称：

| 字段 | 内容 |
|---|---|
| `id`、`source_ids` | 稳定问题 ID，以及 `request` 或 `inputs` 中的来源 ID |
| `observation` | 具体症状、影响及可定位的来源位置 |
| `expected`、`failure_case` | 修改前独立确定的业务预期及暴露损失的案例 |
| `owner` | 首次失败所属环节：规约 / 材料 / Agent 交付 / 脚本处理 / 展示 |
| `status` | `open` / `fixed` / `not_applicable` |
| `outcome` | 实际修复和所属文件，或未解决的具体原因、影响；不能只写“完成” |
| `check_ids` | 对应 `checks` 中的证据 ID；已修复项至少引用一项通过的实测 |

`checks` 每项有 `id`、`kind`（`technical` / `semantic` / `integration`）、`status`（`passed` / `failed` / `not_run` / `not_applicable`）、`method`、`result`、`evidence`。`method` 写实际命令或审阅方法，`result` 写结果或不足，`evidence` 引用 `artifacts` 中的文件路径。通过和失败都保存实际证据；未验证、不适用说明理由，不伪造日志。

`artifacts` 每项有 `path`、`sha256`，保存阶段实际产出与验证证据。缺交时保留问题和具体不足，不能拿空文件代替交付。允许问题或验证列表暂为空，但不能据此宣称已验收。

## 最终报告和用户通知

- `report` 在未生成时为 `null`；生成后有 `path`、`problem_ids`，文件也登记到 `artifacts`。
- `notification` 在未准备时为 `null`；准备后有 `status`（`prepared` / `delivered` / `not_requested`）、`text`、`problem_ids`、`evidence`。`text` 是实际用户摘要或不需通知的理由。已送达必须引用接收证据；`prepared` 只说明已准备，不能声称已外发。对话答复可以保存待回复文本，不因此新增通知渠道。
- 报告及需要通知的摘要分别覆盖每个问题，并包含足够具体的结果、未解决原因和验证限制。问题可合并叙述，但保留来源关系；不能只罗列 ID 或 Skill 名称。
- 最终记录声明三类验证各自的状态；不适用或未验证也必须明示。部分失败可以形成真实的最终报告，不能因此标成全部修复。

## 技术检查

从治理 Skill 目录执行：

```bash
python3 scripts/check_delivery.py "$record" --request-file "$current_request"
python3 scripts/check_delivery.py "$record" --request-file "$current_request" --final
```

前者检查输入绑定、字段、引用及已登记产物；后者额外检查报告/通知的逐问题覆盖和三类验证声明。它不判定业务分析正确，不证明摘要真的保留了含义，也不替你决定用户目标已经完成。Agent 仍须对照原始材料审阅实际报告与通知内容。
