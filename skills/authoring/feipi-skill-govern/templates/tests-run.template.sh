#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

[[ -f "$SKILL_DIR/SKILL.md" ]]
[[ -f "$SKILL_DIR/agents/openai.yaml" ]]
[[ -x "$SCRIPT_DIR/run.sh" ]]

! rg -Fq '{{' "$SKILL_DIR/SKILL.md" "$SKILL_DIR/agents/openai.yaml" "$SCRIPT_DIR/run.sh"
! rg -n 'make[[:space:]]+(new|test|validate)|^##[[:space:]]*维护与回归' "$SKILL_DIR/SKILL.md"
! rg -n '(^|[^A-Za-z])(tests|evals)/|scripts/test\.sh' "$SKILL_DIR/SKILL.md"

bash -n "$SCRIPT_DIR/run.sh"
echo "测试通过: {{SKILL_NAME}}"
