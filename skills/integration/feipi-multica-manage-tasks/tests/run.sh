#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"

[[ -f "$SKILL_DIR/SKILL.md" ]]
[[ -f "$SKILL_DIR/agents/openai.yaml" ]]
[[ -x "$SCRIPT_DIR/run.sh" ]]

! rg -Fq '{{' "$SKILL_DIR/SKILL.md" "$SKILL_DIR/agents/openai.yaml" "$SCRIPT_DIR/run.sh"
! rg -n 'make[[:space:]]+(new|test|validate)|^##[[:space:]]*维护与回归' "$SKILL_DIR/SKILL.md"
! rg -n '(^|[^A-Za-z])(tests|evals)/|scripts/test\.sh' "$SKILL_DIR/SKILL.md"

bash -n "$SCRIPT_DIR/run.sh"
python3 -B -m unittest discover -s "$SCRIPT_DIR" -p 'test_*.py'
# 复用组件的真实命令契约测试；不把文件存在等同于任务行为正确。
python3 -m unittest discover -s "$REPO_ROOT/components/multica/tests" -p 'test_*.py'
echo "确定性契约通过: feipi-multica-manage-tasks；真实 Agent 验收另做。"
