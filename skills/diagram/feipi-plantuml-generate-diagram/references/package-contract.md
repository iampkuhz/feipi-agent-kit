# 图包合同与定点维护

## 验证合同

1. 必须产出 `validation.json`，不可口头声称成功。
2. `mindmap` 使用 `@startmindmap` 与 `@endmindmap`；其他现有 typed profile 与 fallback 使用 `@startuml` 与 `@enduml`。
3. typed profile 模式下必须执行对应的 brief 校验和覆盖校验。
4. 渲染可用时必须产出 `diagram.svg`。
5. 若 `render_result` 不为 `ok`、renderer 身份缺失或当前 SVG 不存在，`final_status` 必须为 `blocked`；不可复用旧 SVG。
6. `scripts/validate_package.sh` 保留 Shell 入口，内部由 Python 编排。写入冻结的观测后，内置 `scripts/verify_package.py` 双向复核最终 v1.2 路径、hash、状态、timing 与实际 PUML metrics；只有通过才输出 success，此后不改写图包。正常作图不要再手工调用 verifier；维护测试可独立复核最终文件。
7. `max_render_attempts=2` 表示首次生成 1 次、针对性修复 1 次，不是 2 次重试；未修改的失败图不得重复渲染。
8. `timings` / `counters` 保留最近一次完整生成数据，`last_run_timings` / `last_run_counters` 记录本次实际调用；上游应优先消费后者。命中复用时 `render_ms=0`、renderer 请求与轮次均为 0，并单独记录 cache hit，不得把首次生成的历史数据当作本次调用。
9. 明确连接权限错误记录为 `blocked_reason=render_access_denied`、`failure_class=renderer`、`repairable=false`；`issues` 保留底层错误、目标地址和 curl/HTTP 诊断。它只说明访问被拒绝，不证明服务宕机或沙箱是唯一原因；本合同不增加提权或自动恢复。
10. 真实渲染后必须通过 `rendered_layout` 遮挡检查；success 报告的几何证据必须与当前 SVG 重算结果一致。连线穿字归可修复的 layout；无法检查归不可自动修复的 visual_review。规则与局限见 [rendered-layout.md](rendered-layout.md)。

## 计时与最终复核

- `render_contract_version=5` 增加渲染后遮挡门禁，并固定以下计时范围；旧合同不命中缓存，不修补历史 timing/hash 使其通过。
- 所有区间起止均由同一编排进程的 `time.monotonic_ns()` 采样，不比较不同进程的时钟原点，不依赖某个 Python 补丁版本。要求 Python 3.9 或更高；Shell 子脚本沿用编排器的 Python，允许通过 `PLANTUML_PYTHON` 显式选择解释器。
- `total_ms` 从编排入口参数解析前开始，截止于报告物化前，覆盖输入身份、静态校验、快照及渲染证据检查。模块导入、最终报告物化（含 hash/metrics 计算、序列化与落盘）、最终 verifier 和 stdout 输出在截止点外；它不是整条命令的墙钟耗时。
- `render_ms` 是整个 `check_render.sh` 子进程的耗时，包括启动、编码、curl SVG 请求、响应检查与文件移动；不称为纯 HTTP/SVG 请求时间。
- `static_validation_ms = total_ms - render_ms` 表示计时区间内的其余工作，包括输入处理和进程开销。负数、非有限数或不满足加和关系的观测直接失败，不能用截断掩盖异常。
- 完整生成先冻结 timing 与将要执行的最终 verifier 计数，再写报告并复核最终文件，verifier 计数为 1。失败将具体错误写入 stderr 与 `issues`，将报告标为 blocked，绝不输出 success。
- 缓存先按原样复核旧报告，再只更新 `last_run_*`，最后复核最终文件，verifier 计数为 2；第一次复核计入本次 static，第二次复核在截止点外。`timings` / `counters` 历史生成数据保持原样。缓存原报告失败时保留具体诊断并回退完整验证，不能修正旧记录冒充命中。
- 不把最终 verifier 耗时写回它所验证的报告，避免“写时间后需要再校验”的自引用循环。


## 工具缺陷与授权边界

- 静态通过却语法渲染失败，或有效分支被校验器连成顺序边，属于需核对 profile、样例和解析器的工具缺陷线索，不等于缺少权限。
- 普通作图任务不修改共享 skill；用户明确授权维护后，用 `feipi-skill-govern` 限定目标文件。此时允许读取失败直接相关的规则和实现，不能继续套用“只读 validation.json”的图面修复限制。
- 已明确授权的目标 skill 修复和结果验证无需每一步重复确认。授权不放宽 renderer 管理、校验规则或自动重试上限，不等于允许修改全局权限。
- 保留失败批次。修复工具合同后，记录修复来源、profile 版本及新的验证批次，再验证最终源码；不得单靠换目录反复尝试同一失败图。
- 活动图统一使用标准冒号动作与 `if/else/endif`、`stop/end` 控制流。方向默认纵向，不加会改变 renderer 图型识别的通用方向声明；分支边必须按控制流而非文本相邻步骤计算。
