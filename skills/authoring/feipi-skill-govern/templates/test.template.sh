#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
VALIDATE_SCRIPT="$REPO_ROOT/feipi-scripts/repo/quick_validate.sh"

if [[ -x "$VALIDATE_SCRIPT" ]]; then
  "$VALIDATE_SCRIPT" "$SKILL_DIR" >/dev/null
else
  [[ -f "$SKILL_DIR/SKILL.md" ]]
  [[ -f "$SKILL_DIR/agents/openai.yaml" ]]
fi

echo "测试通过: {{SKILL_NAME}}"
