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
if ! rg -q '^version:[[:space:]]*5[[:space:]]*$' "$TARGET_DIR/agents/openai.yaml"; then
  echo "agents/openai.yaml version 必须为 5" >&2
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
assert data.get("schema_version") == "1.0", "subagent schema_version 必须为 1.0"
assert data.get("max_active_subagents") == 1, "同时只能启用一个 subagent"
assert data.get("max_total_subagents") == 3, "累计 subagent 必须为 3"
assert data.get("allow_recursive_spawn") is False, "禁止 subagent 递归派生"
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
models = {item.get("model") for item in roles}
assert models == {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"}, "model 分级不符合合同"
efforts = [item.get("reasoning_effort") for item in roles]
assert all(value in {"low", "medium", "high"} for value in efforts), "reasoning_effort 只允许 low/medium/high"
assert efforts.count("high") == 1, "只有最终 reviewer 使用 high"
assert all(item.get("fork_turns") == "none" for item in roles), "subagent 必须使用精简上下文"
assert all(item.get("permission") in {"read_only", "workspace_write"} for item in roles), "permission 非法"
diagram = next(item for item in roles if item.get("name") == "patent_diagram_engineer")
assert diagram.get("writes") == ["disclosure-workspace/diagrams/"], "diagram engineer 写入边界不正确"
assert data.get("fallback", {}).get("forbid_silent_upgrade_to_highest") is True, "必须禁止静默升级最高模型"
telemetry = data.get("telemetry", {})
assert telemetry.get("coordinator") == "main_agent", "timing log 必须由 main agent 协调"
assert telemetry.get("log_path") == "disclosure-workspace/working/session-timing.jsonl", "timing log 路径不正确"
assert all(telemetry.get(field) is True for field in ("record_spawn", "record_execution", "record_wait")), "subagent timing 字段不完整"
PY

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
