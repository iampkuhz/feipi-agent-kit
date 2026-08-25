#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  bash scripts/validate.sh [skill-dir]
USAGE
}

if [[ $# -gt 1 ]]; then
  usage >&2
  exit 1
fi
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_INPUT="${1:-$SKILL_DIR}"
if [[ ! -d "$TARGET_INPUT" ]]; then
  REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
  if [[ -d "$REPO_ROOT/$TARGET_INPUT" ]]; then
    TARGET_INPUT="$REPO_ROOT/$TARGET_INPUT"
  fi
fi
if [[ ! -d "$TARGET_INPUT" ]]; then
  echo "目录不存在：$TARGET_INPUT" >&2
  exit 1
fi
TARGET_DIR="$(cd "$TARGET_INPUT" && pwd)"

if [[ "$(basename "$TARGET_DIR")" != "feipi-patent-generate-innovation-disclosure" ]]; then
  echo "目标目录名不正确：$(basename "$TARGET_DIR")" >&2
  exit 1
fi

REQUIRED_FILES=(
  "SKILL.md"
  "agents/openai.yaml"
  "assets/proposal_template.md"
  "assets/internal_trace_appendix_template.md"
  "assets/disclosure-manifest.template.json"
  "assets/disclosure-manifest.schema.json"
  "references/content-quality-gates.md"
  "references/stage-delivery-contract.md"
  "references/subagent-orchestration.json"
  "references/session-timing.md"
  "references/cases/happy-case-full.md"
  "references/cases/happy-package/disclosure.md"
  "references/cases/happy-package/disclosure-workspace/disclosure-internal.md"
  "references/cases/happy-package/disclosure-workspace/disclosure-manifest.json"
  "references/cases/happy-package/disclosure-workspace/disclosure-validation.json"
  "scripts/check_disclosure_format.sh"
  "scripts/validate_disclosure_package.sh"
  "scripts/validate_disclosure.py"
  "scripts/session_timing.py"
  "scripts/stage_handoff.py"
  "scripts/tests/test_stage_handoff.py"
  "scripts/tests/test_session_timing.py"
  "scripts/tests/generate_package.py"
  "scripts/test.sh"
)
for relative_path in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "$TARGET_DIR/$relative_path" ]]; then
    echo "缺少文件：$TARGET_DIR/$relative_path" >&2
    exit 1
  fi
done

FRONTMATTER_NAME="$(sed -nE '2,/^---$/s/^name:[[:space:]]*(.+)$/\1/p' "$TARGET_DIR/SKILL.md" | head -n 1)"
if [[ "$FRONTMATTER_NAME" != "feipi-patent-generate-innovation-disclosure" ]]; then
  echo "SKILL.md name 与目录名不一致：$FRONTMATTER_NAME" >&2
  exit 1
fi
if ! rg -q '^version:[[:space:]]*6[[:space:]]*$' "$TARGET_DIR/agents/openai.yaml"; then
  echo "agents/openai.yaml version 必须为 6" >&2
  exit 1
fi

while IFS= read -r shell_file; do
  [[ -z "$shell_file" ]] && continue
  bash -n "$shell_file"
  if [[ ! -x "$shell_file" ]]; then
    echo "Shell 脚本缺少可执行权限：$shell_file" >&2
    exit 1
  fi
done < <(rg --files "$TARGET_DIR/scripts" -g '*.sh' | LC_ALL=C sort)

PY_CACHE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/feipi-patent-pycache.XXXXXX")"
while IFS= read -r python_file; do
  [[ -z "$python_file" ]] && continue
  PYTHONPYCACHEPREFIX="$PY_CACHE_DIR" python3 -m py_compile "$python_file"
done < <(rg --files "$TARGET_DIR/scripts" -g '*.py' | LC_ALL=C sort)

python3 -c 'import json,sys; json.load(open(sys.argv[1], encoding="utf-8")); json.load(open(sys.argv[2], encoding="utf-8"))' \
  "$TARGET_DIR/assets/disclosure-manifest.template.json" \
  "$TARGET_DIR/assets/disclosure-manifest.schema.json"

python3 - "$TARGET_DIR/references/subagent-orchestration.json" <<'PY'
import json
import sys

path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
assert data.get("schema_version") == "1.1", "subagent schema_version 必须为 1.1"
assert data.get("max_active_subagents") == 1, "同时只能启用一个 subagent"
assert data.get("max_total_subagents") == 3, "累计 subagent 必须为 3"
assert data.get("allow_recursive_spawn") is False, "禁止 subagent 递归派生"
assert data.get("permission_enforcement") == "task_contract_not_os_sandbox", "必须声明 permission 的执行边界"
assert data.get("handoff_contract") == "references/stage-delivery-contract.md", "阶段交付合同路径不正确"
assert set(data.get("task_packet_required_fields", [])) == {
    "task_file", "input_reference", "allowed_writes",
    "forbidden_actions", "return_format", "timing_log", "key_event_contract",
}, "subagent 精简任务包字段不完整"
reporting = data.get("event_reporting", {})
critical_events = ["MILESTONE", "DECISION", "BLOCKED", "COMPLETE"]
silent_events = [
    "STARTED", "RUNNING", "HEARTBEAT", "STATUS", "TOOL_CALL",
    "FILE_READ", "FILE_WRITE", "CACHE_HIT", "WAIT_TIMEOUT", "RETRYING", "UNCHANGED",
]
assert reporting.get("critical_events") == critical_events, "关键事件必须恰好为 MILESTONE/DECISION/BLOCKED/COMPLETE"
assert reporting.get("silent_events") == silent_events, "非关键事件静默集合不完整"
assert reporting.get("unknown_event_policy") == "reject_not_forward", "未知事件不得转发给用户"
assert set(critical_events).isdisjoint(silent_events), "关键事件与静默事件不得重叠"
profiles = reporting.get("profiles", {})
assert set(profiles) == {"main_to_user", "subagent_to_main"}, "关键事件上报 profile 不完整"
assert profiles.get("main_to_user", {}).get("audience") == "user", "主 agent 上报对象必须为用户"
assert profiles.get("subagent_to_main", {}).get("audience") == "main_agent", "subagent 上报对象必须为主 agent"
assert all(profile.get("emit_on") == critical_events for profile in profiles.values()), "主子 agent 只能上报关键事件"
assert data.get("main_agent_reporting_profile") == "main_to_user", "主 agent 必须绑定 main_to_user"
envelope = reporting.get("envelope", {})
assert envelope.get("format") == "[<EVENT>] <scope>｜<outcome>｜<next_or_artifact>", "关键事件 envelope 格式不正确"
assert envelope.get("max_lines") == 1, "关键事件 envelope 必须限制为一行"
assert envelope.get("max_chars") == 240, "关键事件 envelope 必须限制为 240 字符"
assert envelope.get("overflow_policy") == "shorten_outcome", "关键事件超长时必须压缩结果"
lifecycle = reporting.get("lifecycle", {})
assert lifecycle == {
    "max_milestones_per_scope": 1,
    "final_events": ["BLOCKED", "COMPLETE"],
    "final_response_is_event": True,
    "duplicate_final_notification": False,
}, "关键事件生命周期约束不完整"
assert reporting.get("classification") == {
    "complete_over_milestone": True,
    "decision_when_receiver_choice_can_unblock": True,
    "blocked_when_no_receiver_choice_can_unblock": True,
}, "关键事件重叠分类规则不完整"
deduplicate = reporting.get("deduplicate", {})
assert deduplicate.get("enabled") is True, "关键事件必须去重"
assert deduplicate.get("key_fields") == [
    "profile", "event", "scope", "outcome",
], "关键事件去重键不正确"
wait_policy = reporting.get("wait_policy", {})
assert wait_policy.get("mode") == "event_driven_join", "subagent 等待必须为事件驱动"
assert wait_policy.get("main_agent_work_while_subagent_runs") is True, "主 agent 必须先执行独立工作"
assert wait_policy.get("dependency_barrier_wait") == "long_event_wait_with_nonterminal_timeout_continuation", "依赖屏障必须使用可续接的长时事件等待"
assert all(wait_policy.get(field) is False for field in ("busy_wait", "periodic_poll", "heartbeat")), "禁止 busy wait、轮询和心跳"
assert all(wait_policy.get(field) is False for field in ("status_probe_between_waits", "short_wait_loop")), "长等待续接之间禁止状态查询和短周期等待"
assert wait_policy.get("nonterminal_timeout_policy") == "continue_long_event_wait_without_status_probe", "宿主非终态超时后只能无查询续接长等待"
roles = data.get("roles")
assert isinstance(roles, list) and len(roles) == 3, "必须配置三个分级角色"
names = [item.get("name") for item in roles]
assert len(names) == len(set(names)), "subagent role 不得重复"
required = {
    "patent_prior_art_researcher",
    "patent_diagram_engineer",
    "patent_final_reviewer",
}
assert set(names) == required, "subagent role 集合不完整"
assert {item.get("stage") for item in roles} == {
    "phase_1_material_modeling", "phase_3_final_drafting", "phase_4_review_delivery",
}, "subagent stage 必须与 timing stage 同源"
models = {item.get("model") for item in roles}
assert models == {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"}, "model 分级不符合合同"
efforts = [item.get("reasoning_effort") for item in roles]
assert all(value in {"low", "medium", "high"} for value in efforts), "reasoning_effort 只允许 low/medium/high"
assert efforts.count("high") == 1, "只有最终 reviewer 使用 high"
assert all(item.get("fork_turns") == "none" for item in roles), "subagent 必须使用精简上下文"
assert all(item.get("permission") in {"read_only", "workspace_write"} for item in roles), "permission 非法"
assert all(item.get("reporting_profile") == "subagent_to_main" for item in roles), "每个 subagent 必须引用 subagent_to_main"
role_map = {item["name"]: item for item in roles}
expected_roles = {
    "patent_prior_art_researcher": (
        "phase_1_material_modeling", "gpt-5.6-luna", "medium", "none", "read_only", [],
    ),
    "patent_diagram_engineer": (
        "phase_3_final_drafting", "gpt-5.6-terra", "medium", "none", "workspace_write",
        ["disclosure-workspace/diagrams/"],
    ),
    "patent_final_reviewer": (
        "phase_4_review_delivery", "gpt-5.6-sol", "high", "none", "read_only", [],
    ),
}
for name, expected in expected_roles.items():
    item = role_map[name]
    actual = (
        item.get("stage"), item.get("model"), item.get("reasoning_effort"),
        item.get("fork_turns"), item.get("permission"), item.get("writes"),
    )
    assert actual == expected, f"{name} 分级或权限映射不正确：{actual}"
expected_deliveries = {
    "patent_prior_art_researcher": (
        "disclosure-workspace/working/stages/agents/prior-art-task.md",
        "research.tsv rows",
        "disclosure-workspace/working/stages/phase-1/research.tsv",
        "main_agent",
    ),
    "patent_diagram_engineer": (
        "disclosure-workspace/working/stages/agents/diagram-task.md",
        "build-map.tsv rows",
        "disclosure-workspace/working/stages/phase-3/build-map.tsv",
        "main_agent",
    ),
    "patent_final_reviewer": (
        "disclosure-workspace/working/stages/agents/final-review-task.md",
        "review.tsv rows",
        "disclosure-workspace/working/stages/phase-4/review.tsv",
        "main_agent",
    ),
}
for name, expected in expected_deliveries.items():
    item = role_map[name]
    output = item.get("output_contract", {})
    actual = (
        item.get("task_file"), output.get("format"), output.get("cache_path"), output.get("writer"),
    )
    assert actual == expected, f"{name} 的输入/输出文件链不正确：{actual}"
    assert len(item.get("input_contract", [])) == 3, f"{name} 必须声明三个紧凑输入"
    assert len(item.get("judgment_contract", [])) == 3, f"{name} 必须声明三个判断范围"
    assert output.get("message") in {"final_event_and_row_count_only", "final_event_and_paths_only"}, f"{name} 返回消息不够紧凑"
diagram = next(item for item in roles if item.get("name") == "patent_diagram_engineer")
assert diagram.get("writes") == ["disclosure-workspace/diagrams/"], "diagram engineer 写入边界不正确"
assert data.get("fallback", {}).get("forbid_silent_upgrade_to_highest") is True, "必须禁止静默升级最高模型"
telemetry = data.get("telemetry", {})
assert telemetry.get("coordinator") == "main_agent", "timing log 必须由 main agent 协调"
assert telemetry.get("log_path") == "disclosure-workspace/working/session-timing.jsonl", "timing log 路径不正确"
assert all(telemetry.get(field) is True for field in ("record_spawn", "record_execution", "record_wait")), "subagent timing 字段不完整"
PY

rg -q '^## 2\. 四阶段交付矩阵$' "$TARGET_DIR/references/stage-delivery-contract.md"
rg -q '^## 4\. subagent 三段式交付$' "$TARGET_DIR/references/stage-delivery-contract.md"
rg -q '^## 5\. 关键事件与非轮询汇合$' "$TARGET_DIR/references/stage-delivery-contract.md"
rg -q '^### 5\.2 必须上报的触发点$' "$TARGET_DIR/references/stage-delivery-contract.md"
rg -q '^## 关键事件上报与等待纪律（必做）$' "$TARGET_DIR/SKILL.md"
rg -q '长时、事件驱动等待' "$TARGET_DIR/SKILL.md"
rg -q '禁止用短间隔.*循环查询 subagent' "$TARGET_DIR/SKILL.md"
rg -q '非终态超时.*继续同类长等待.*不得查询状态' "$TARGET_DIR/SKILL.md"
rg -q 'handoff 不超过 24 KiB' "$TARGET_DIR/SKILL.md"

bash "$TARGET_DIR/scripts/check_disclosure_format.sh" \
  "$TARGET_DIR/references/cases/happy-case-full.md" >/dev/null

HAPPY_COPY_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/feipi-patent-happy-package.XXXXXX")"
cp -R "$TARGET_DIR/references/cases/happy-package" "$HAPPY_COPY_ROOT/package"
set +e
bash "$TARGET_DIR/scripts/validate_disclosure_package.sh" "$HAPPY_COPY_ROOT/package" >/dev/null 2>&1
PACKAGE_EXIT=$?
set -e
if [[ "$PACKAGE_EXIT" -ne 0 ]]; then
  echo "happy-package 未通过完整交付校验，退出码=$PACKAGE_EXIT" >&2
  bash "$TARGET_DIR/scripts/validate_disclosure_package.sh" "$HAPPY_COPY_ROOT/package" || true
  exit 1
fi

echo "校验通过：$TARGET_DIR"
