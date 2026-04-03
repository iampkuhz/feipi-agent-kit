#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
VALIDATE_REPO_SCRIPT="$REPO_ROOT/feipi-scripts/repo/quick_validate.sh"
VALIDATE_BRIEF_SCRIPT="$SCRIPT_DIR/validate_brief.py"
COVERAGE_SCRIPT="$SCRIPT_DIR/check_coverage.py"
LAYOUT_SCRIPT="$SCRIPT_DIR/lint_layout.sh"
RENDER_SCRIPT="$SCRIPT_DIR/check_render.sh"

VALID_BRIEF="$SKILL_DIR/assets/examples/sequence-brief.example.yaml"
VALID_DIAGRAM="$SKILL_DIR/assets/examples/sequence-diagram.example.puml"
INVALID_BRIEF="$SCRIPT_DIR/tests/invalid-brief.yaml"
INVALID_DIAGRAM="$SCRIPT_DIR/tests/invalid-diagram.puml"

if [[ -x "$VALIDATE_REPO_SCRIPT" ]]; then
  "$VALIDATE_REPO_SCRIPT" "$SKILL_DIR" >/dev/null
fi

python3 "$VALIDATE_BRIEF_SCRIPT" "$VALID_BRIEF" >/dev/null

if python3 "$VALIDATE_BRIEF_SCRIPT" "$INVALID_BRIEF" >/dev/null 2>&1; then
  echo "无效 brief 未被拦截" >&2
  exit 1
fi

python3 "$COVERAGE_SCRIPT" --brief "$VALID_BRIEF" --diagram "$VALID_DIAGRAM" >/dev/null

if python3 "$COVERAGE_SCRIPT" --brief "$VALID_BRIEF" --diagram "$INVALID_DIAGRAM" >/dev/null 2>&1; then
  echo "无效 diagram 未被覆盖校验拦截" >&2
  exit 1
fi

bash "$LAYOUT_SCRIPT" "$VALID_DIAGRAM" >/dev/null

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
SVG_OUTPUT="$TMP_DIR/render.svg"

set +e
bash "$RENDER_SCRIPT" "$VALID_DIAGRAM" --svg-output "$SVG_OUTPUT" >/dev/null
RENDER_CODE=$?
set -e

if [[ "$RENDER_CODE" -ne 0 && "$RENDER_CODE" -ne 4 ]]; then
  echo "渲染检查失败，返回码：$RENDER_CODE" >&2
  exit 1
fi

if [[ "$RENDER_CODE" -eq 0 && ! -f "$SVG_OUTPUT" ]]; then
  echo "渲染成功但未产出 svg 文件" >&2
  exit 1
fi

echo "测试通过：feipi-gen-plantuml-sequence-diagram"
