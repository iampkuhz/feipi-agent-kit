# Session 耗时观测合同

## 目标

为每次真实专利交底执行保留可聚合的 JSONL 时间线，区分阶段墙钟、资源读取、外部检索、PlantUML renderer、确定性校验和 subagent 等待。观测文件只属于内部工作区，不进入对外 `disclosure.md`。

## 落位

```text
disclosure-workspace/working/
├── session-timing.jsonl
└── session-timing-summary.json
```

先确定交底输出目录，再初始化 timing log。同一 `session-timing.jsonl` 可以连续追加多次完整执行；存在未关闭 session 时第二次 `init` 会失败，跨对话恢复必须使用 `init --resume`，避免把未闭 span 隐藏到旧 session。后续命令默认归入最新 session，`summarize` 也只汇总最新 session。

## 必记阶段

- `phase_1_material_modeling`
- `phase_2_idea_confirmation`
- `phase_3_final_drafting`
- `phase_4_review_delivery`

每个阶段必须各有一个 `activity=phase` 的 start/end span。阶段 2 的时长包含等待用户确认的墙钟时间，以便分析“系统执行慢”和“等待输入”之间的差异；汇总时不得把它伪装成模型计算耗时。

## 必记活动

- `resource_read`：用户材料及按阶段加载的 skill 资源；按连续读取批次记录，不为每个小文件单独启动 CLI。
- `retrieval`：两条竞品检索线的完整执行时间。
- `diagram_generation`：从冻结图示合同到图包就绪。
- `render`：PlantUML `/svg` 请求耗时，从图包 `validation.json.last_run_timings.render_ms` 导入。
- `validation`：确定性校验耗时；图包静态部分从 `last_run_timings.static_validation_ms` 导入，并同步导入 renderer HTTP 请求、渲染轮次、package validation、verifier 和 cache hit 次数；完整交底入口使用 `run` 包装。
- `subagent_execution`：从派发成功到 worker 结果完成。
- `subagent_wait`：主 agent 在依赖汇合点通过宿主事件机制真实阻塞等待 worker 的时间；主 agent 同时继续工作时不计入等待，状态查询、短间隔轮询和心跳不得记成等待。

不得在 label、agent id 或事件字段中记录用户原文、检索结果正文、密钥或其他敏感内容。路径使用相对工作区的稳定短名。

## 标准调用

初始化：

```bash
python3 scripts/session_timing.py init \
  --log <disclosure-dir>/disclosure-workspace/working/session-timing.jsonl \
  --runtime-session-id <宿主可用时填写>
```

跨对话继续同一交底时：

```bash
python3 scripts/session_timing.py init --resume --log <timing-log>
```

手工 span（资源读取、检索、阶段和 subagent）：

```bash
SPAN_ID="$(python3 scripts/session_timing.py start --log <timing-log> \
  --stage phase_1_material_modeling --activity resource_read --label user-materials)"

python3 scripts/session_timing.py end --log <timing-log> --span-id "$SPAN_ID" --status success
```

阶段 2 可能跨多个对话 turn；恢复后若 span id 不在当前上下文，可按 stage/activity 唯一结束当前未闭合 span：

```bash
python3 scripts/session_timing.py end --log <timing-log> \
  --stage phase_2_idea_confirmation --activity phase --status success
```

subagent 派发成功后先记录数量与配置，再分别记录执行和真实等待 span。等待 span 包住依赖汇合点的完整逻辑等待；宿主非终态超时后的长时事件等待续接仍属于同一逻辑等待，禁止为了产生观测数据而查询或短周期轮询：

```bash
python3 scripts/session_timing.py record-subagent --log <timing-log> \
  --agent-role patent_prior_art_researcher --agent-id <agent-id> \
  --model gpt-5.6-luna --reasoning-effort medium \
  --effective-model <宿主返回的实际模型> --effective-reasoning-effort <实际 effort>
```

`--model` / `--reasoning-effort` 表示请求值。宿主未暴露实际值时省略两个 `--effective-*` 参数，summary 会明确记录 `unknown`，不会把请求配置伪装成实际执行配置。

确定性命令使用 `run` 包装并透传退出码：

```bash
python3 scripts/session_timing.py run --log <timing-log> \
  --stage phase_4_review_delivery --activity validation --label disclosure-package \
  --result-json <disclosure-dir>/disclosure-workspace/disclosure-validation.json -- \
  bash scripts/validate_disclosure_package.sh <disclosure-dir>
```

`--result-json` 同时导入完整交底入口的执行次数及其内部逐图 verifier 次数；报告缺失或计数字段不完整时观测失败，不能按 0 处理。

导入图包的渲染、静态校验耗时和调用次数；只接受完整的 `last_run_timings` / `last_run_counters`。若本次命中未变图包复用，记录 `cache_hit=true`、`render_ms=0`、零 renderer 请求，不会误用首次生成的历史数据：

```bash
python3 scripts/session_timing.py ingest-diagram --log <timing-log> \
  --label D1 --validation <diagram-package>/validation.json
```

结束时输出汇总：

```bash
python3 scripts/session_timing.py summarize --log <timing-log> \
  --output <disclosure-dir>/disclosure-workspace/working/session-timing-summary.json \
  --require-complete --close-session
```

## 统计口径

- `unique_count`：当前 session 中不同 `agent_id` 数量。
- `spawn_count`：成功派发次数。
- `execution_count`：完成或失败的 `subagent_execution` span 数量。
- `wait_count` / `wait_duration_ms`：主 agent 真实阻塞等待的次数与总时长。
- `diagram_operations`：当前 session 的 renderer HTTP 请求、渲染轮次、package validation、verifier 和 cache hit 实际次数。
- `final_validation_operations`：阶段 4 完整交底校验次数，以及该入口内部逐图调用通用 verifier 的次数；`total_package_verifier_runs` 汇总生成阶段与最终阶段。
- `duration_ms` 使用单调时钟，适合分析实际执行；`wall_duration_ms` 使用阶段开始和结束墙钟，包含系统休眠或长时间用户等待。阶段和 subagent wait 同时保留两种口径。
- `activities.*.duration_ms`：允许活动重叠，不应相加后当作 session 墙钟总时长；整个 session 的墙钟时间使用 `session_wall_duration_ms`。
- `coverage`：四个阶段、五类必记活动、最终校验内部计数及未闭 span 的完整性；只有 `coverage.complete=true` 才能关闭 session。
- `incomplete_spans`：有 start 无 end 的 span；保留顶层兼容字段，同时也位于 `coverage.incomplete_spans`。

## 观测边界

- `CHECKPOINT.md` 是可恢复的当前任务状态，`session-timing.jsonl` 才是追加式观测日志；不得把 checkpoint 更新复制成 timing 微事件，也不得用 timing span 代替任务完成门禁。
- 宿主未提供模型排队、首 token、token 用量或隐藏 reasoning 时长时，本工具不能推导这些指标；阶段墙钟只代表协调流程经过时间，不等于模型计算时间。
- 每次 `session_timing.py` 进程启动和 JSONL 写入本身存在少量观测开销，该开销不计入被测 span；因此资源读取按批次记录。
- 并行活动的 `duration_ms` 会重叠，分析关键路径时使用阶段墙钟、subagent wait 和宿主 runtime session，不对活动总和作墙钟解释。
