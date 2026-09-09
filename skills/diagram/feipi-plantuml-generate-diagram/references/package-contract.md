# 图包合同与定点维护

## 验证合同

1. 必须产出 `validation.json`，不可口头声称成功。
2. `mindmap` 使用 `@startmindmap` 与 `@endmindmap`；其他现有 typed profile 与 fallback 使用 `@startuml` 与 `@enduml`。
3. typed profile 模式下必须执行对应的 brief 校验和覆盖校验。
4. 渲染可用时必须产出 `diagram.svg`。
5. 若 `render_result` 不为 `ok`、renderer 身份缺失或当前 SVG 不存在，`final_status` 必须为 `blocked`；不可复用旧 SVG。
6. `scripts/validate_package.sh` 已内置 `scripts/verify_package.py`，会双向复核 v1.2 路径、hash、状态与实际 PUML metrics；不要再手工调用 verifier。
7. `max_render_attempts=2` 表示首次生成 1 次、针对性修复 1 次，不是 2 次重试；未修改的失败图不得重复渲染。
8. `timings` / `counters` 保留最近一次完整生成数据，`last_run_timings` / `last_run_counters` 记录本次实际调用；上游应优先消费后者。命中复用时 `render_ms=0`、renderer 请求与轮次均为 0，并单独记录 cache hit，不得把首次生成的历史数据当作本次调用。
9. `scripts/test.sh` 的正向样例必须使用真实 renderer 并断言 `render_result=ok`、`final_status=success`；负例单独断言预期失败。静态或 mock 测试通过不能代替正向样例的真实渲染证明。


## 工具缺陷与授权边界

- 静态通过却语法渲染失败，或有效分支被校验器连成顺序边，属于需核对 profile、样例、解析器和测试的工具缺陷线索，不等于缺少权限。
- 普通作图任务不修改共享 skill；用户明确授权维护后，用 `feipi-skill-govern` 限定目标文件并补回归测试。此时允许读取失败直接相关的规则和实现，不能继续套用“只读 validation.json”的图面修复限制。
- 已明确授权的目标 skill 修复、回归测试和结果验证无需每一步重复确认。授权不放宽 renderer 管理、校验规则或自动重试上限，不等于允许修改全局权限。
- 保留失败批次。修复工具合同后，记录修复来源、profile 版本及新的验证批次，再验证最终源码；不得单靠换目录反复尝试同一失败图。
- 活动图统一使用标准冒号动作与 `if/else/endif`、`stop/end` 控制流。方向默认纵向，不加会改变 renderer 图型识别的通用方向声明；分支边必须按控制流而非文本相邻步骤计算。
