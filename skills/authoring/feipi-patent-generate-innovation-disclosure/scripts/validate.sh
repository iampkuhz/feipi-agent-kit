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
  "MAINTAINER_HISTORY.md"
  "agents/openai.yaml"
  "agents/subagents/index.json"
  "agents/subagents/runtime.json"
  "agents/subagents/checkpoint-task-catalog.json"
  "agents/subagents/task-packet.template.md"
  "handbook/workflow-and-parallelism.md"
  "assets/proposal_template.md"
  "assets/internal_trace_appendix_template.md"
  "assets/disclosure-manifest.template.json"
  "assets/disclosure-manifest.schema.json"
  "references/content-quality-gates.md"
  "references/stage-delivery-contract.md"
  "references/session-timing.md"
  "references/cases/happy-case-full.md"
  "references/cases/happy-package/disclosure.md"
  "references/cases/happy-package/disclosure-workspace/disclosure-internal.md"
  "references/cases/happy-package/disclosure-workspace/disclosure-manifest.json"
  "references/cases/happy-package/disclosure-workspace/disclosure-validation.json"
  "scripts/check_disclosure_format.sh"
  "scripts/validate_disclosure_package.sh"
  "scripts/validate_disclosure.py"
  "scripts/validate_orchestration.py"
  "scripts/session_timing.py"
  "scripts/stage_handoff.py"
  "scripts/checkpoint.py"
  "scripts/tests/test_checkpoint.py"
  "scripts/tests/test_orchestration.py"
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
if ! rg -q '^version:[[:space:]]*8[[:space:]]*$' "$TARGET_DIR/agents/openai.yaml"; then
  echo "agents/openai.yaml version 必须为 8" >&2
  exit 1
fi
if [[ -e "$TARGET_DIR/references/subagent-orchestration.json" || -e "$TARGET_DIR/references/checkpoint-task-catalog.json" ]]; then
  echo "references/ 中仍残留旧 subagent 配置真源" >&2
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

VALIDATION_TMP="$(mktemp -d "${TMPDIR:-/tmp}/feipi-patent-validate.XXXXXX")"
trap 'rm -rf "$VALIDATION_TMP"' EXIT
while IFS= read -r python_file; do
  [[ -z "$python_file" ]] && continue
  PYTHONPYCACHEPREFIX="$VALIDATION_TMP/pycache" python3 -m py_compile "$python_file"
done < <(rg --files "$TARGET_DIR/scripts" -g '*.py' | LC_ALL=C sort)

python3 -c 'import json,sys; [json.load(open(path, encoding="utf-8")) for path in sys.argv[1:]]' \
  "$TARGET_DIR/assets/disclosure-manifest.template.json" \
  "$TARGET_DIR/assets/disclosure-manifest.schema.json"
python3 "$TARGET_DIR/scripts/validate_orchestration.py" "$TARGET_DIR"

rg -q '^## 2\. 四阶段交付矩阵$' "$TARGET_DIR/references/stage-delivery-contract.md"
rg -q '^## 4\. subagent 三段式交付$' "$TARGET_DIR/references/stage-delivery-contract.md"
rg -q '^## 5\. 关键事件与非轮询汇合$' "$TARGET_DIR/references/stage-delivery-contract.md"
rg -q '^## 7\. 任务检查点与恢复$' "$TARGET_DIR/references/stage-delivery-contract.md"
rg -q 'agents/subagents/index\.json' "$TARGET_DIR/SKILL.md"
rg -q 'phase-3-diagram-Dn' "$TARGET_DIR/SKILL.md"
rg -q 'phase-4-visual-review-Dn' "$TARGET_DIR/SKILL.md"
rg -q 'Skill 运行时不得读取' "$TARGET_DIR/handbook/workflow-and-parallelism.md"

bash "$TARGET_DIR/scripts/check_disclosure_format.sh" \
  "$TARGET_DIR/references/cases/happy-case-full.md" >/dev/null
cp -R "$TARGET_DIR/references/cases/happy-package" "$VALIDATION_TMP/package"
bash "$TARGET_DIR/scripts/validate_disclosure_package.sh" "$VALIDATION_TMP/package" >/dev/null

echo "校验通过：$TARGET_DIR"
