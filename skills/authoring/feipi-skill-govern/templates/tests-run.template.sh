#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

[[ -f "$SKILL_DIR/SKILL.md" ]]
[[ -f "$SKILL_DIR/agents/openai.yaml" ]]
[[ -x "$SCRIPT_DIR/run.sh" ]]
[[ -s "$SKILL_DIR/maintenance/README.md" ]]
[[ -s "$SKILL_DIR/maintenance/terminology.md" ]]

! grep -Fq '{{' "$SKILL_DIR/SKILL.md" "$SKILL_DIR/agents/openai.yaml" "$SCRIPT_DIR/run.sh"
! grep -En 'make[[:space:]]+(new|test|validate)|^##[[:space:]]*维护与回归' "$SKILL_DIR/SKILL.md"
! grep -En '(^|[^A-Za-z])(maintenance|tests|evals)/|scripts/test\.sh' "$SKILL_DIR/SKILL.md"

bash -n "$SCRIPT_DIR/run.sh"
echo "测试通过: {{SKILL_NAME}}"
