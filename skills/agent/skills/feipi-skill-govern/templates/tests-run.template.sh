#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

[[ -f "$SKILL_DIR/SKILL.md" ]] || exit 1
[[ -f "$SKILL_DIR/agents/openai.yaml" ]] || exit 1
[[ -x "$SCRIPT_DIR/run.sh" ]] || exit 1
[[ -s "$SKILL_DIR/maintenance/README.md" ]] || exit 1
[[ -s "$SKILL_DIR/maintenance/terminology.md" ]] || exit 1

placeholder_start="$(printf '%s%s' '{' '{')"
! grep -Fq "$placeholder_start" "$SKILL_DIR/SKILL.md" "$SKILL_DIR/agents/openai.yaml" "$SCRIPT_DIR/run.sh" || exit 1
! grep -En 'make[[:space:]]+(new|test|validate)|^##[[:space:]]*维护与回归' "$SKILL_DIR/SKILL.md" || exit 1
! grep -En '(^|[^A-Za-z])(maintenance|tests|evals)/|scripts/test\.sh' "$SKILL_DIR/SKILL.md" || exit 1

bash -n "$SCRIPT_DIR/run.sh"
# 这里只验证脚手架结构。维护者应从原始需求补业务正反例，不能把当前输出直接当作预期。
echo "结构自检通过: {{SKILL_NAME}}；业务行为与 Agent 效果尚未验证"
