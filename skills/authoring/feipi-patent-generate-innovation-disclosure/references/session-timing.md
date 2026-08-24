# Session 耗时观测合同

## 目标

为每次真实专利交底执行保留可聚合的 JSONL 时间线，区分模型工作流、外部检索、PlantUML renderer、确定性校验和 subagent 等待。观测文件只属于内部工作区，不进入对外 `disclosure.md`。

## 落位

```text
disclosure-workspace/working/
├── session-timing.jsonl
└── session-timing-summary.json
```

同一 `session-timing.jsonl` 可以连续追加多次执行。`init` 写入新的 `session_id`；后续命令默认归入最新 session，`summarize` 也只汇总最新 session。

## 必记阶段

- `phase_1_material_modeling`
- `phase_2_idea_confirmation`
- `phase_3_final_drafting`
- `phase_4_review_delivery`

每个阶段必须各有一个 `activity=phase` 的 start/end span。阶段 2 的时长包含等待用户确认的墙钟时间，以便分析“系统执行慢”和“等待输入”之间的差异；汇总时不得把它伪装成模型计算耗时。

## 必记活动

- `resource_read`：用户材料及按阶段加载的 skill 资源。
- `retrieval`：两条竞品检索线的完整执行时间。
- `diagram_generation`：从冻结图示合同到图包就绪。
- `render`：PlantUML `/svg` 请求耗时，从图包 `validation.json.timings.render_ms` 导入。
- `validation`：确定性校验耗时；图包静态部分从 `validation.json.timings.static_validation_ms` 导入，完整交底入口使用 `run` 包装。
- `subagent_execution`：从派发成功到 worker 结果完成。
- `subagent_wait`：主 agent 实际阻塞等待 worker 的时间；主 agent 同时继续工作时不计入等待。

不得在 label、agent id 或事件字段中记录用户原文、检索结果正文、密钥或其他敏感内容。路径使用相对工作区的稳定短名。

## 标准调用

初始化：

```bash
python3 scripts/session_timing.py init \
  --log <disclosure-dir>/disclosure-workspace/working/session-timing.jsonl
```

手工 span（资源读取、检索、阶段和 subagent）：

```bash
SPAN_ID="$(python3 scripts/session_timing.py start --log <timing-log> \
  --stage phase_1_material_modeling --activity resource_read --label user-materials)"

python3 scripts/session_timing.py end --log <timing-log> --span-id "$SPAN_ID" --status success
```

subagent 派发成功后先记录数量与配置，再分别记录执行和真实等待 span：

```bash
python3 scripts/session_timing.py record-subagent --log <timing-log> \
  --agent-role patent_prior_art_researcher --agent-id <agent-id> \
  --model gpt-5.6-luna --reasoning-effort medium
```

确定性命令使用 `run` 包装并透传退出码：

```bash
python3 scripts/session_timing.py run --log <timing-log> \
  --stage phase_4_review_delivery --activity validation --label disclosure-package -- \
  bash scripts/validate_disclosure_package.sh <disclosure-dir>
```

导入图包的渲染与静态校验耗时：

```bash
python3 scripts/session_timing.py ingest-diagram --log <timing-log> \
  --label D1 --validation <diagram-package>/validation.json
```

结束时输出汇总：

```bash
python3 scripts/session_timing.py summarize --log <timing-log> \
  --output <disclosure-dir>/disclosure-workspace/working/session-timing-summary.json
```

## 统计口径

- `unique_count`：当前 session 中不同 `agent_id` 数量。
- `spawn_count`：成功派发次数。
- `execution_count`：完成或失败的 `subagent_execution` span 数量。
- `wait_count` / `wait_duration_ms`：主 agent 真实阻塞等待的次数与总时长。
- `activities.*.duration_ms`：允许活动重叠，不应相加后当作 session 墙钟总时长。
- `incomplete_spans`：有 start 无 end 的 span；交付前必须为空，否则说明中断或漏记。
