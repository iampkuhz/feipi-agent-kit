#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATE_SCRIPT="$SCRIPT_DIR/validate.sh"
VALIDATE_BRIEF_SCRIPT="$SCRIPT_DIR/validate_brief.py"
COVERAGE_SCRIPT="$SCRIPT_DIR/check_coverage.py"
LAYOUT_SCRIPT="$SCRIPT_DIR/lint_layout.sh"
RENDER_SCRIPT="$SCRIPT_DIR/check_render.sh"

VALID_BRIEF="$SKILL_DIR/assets/examples/architecture-brief.example.yaml"
VALID_DIAGRAM="$SKILL_DIR/assets/examples/architecture-diagram.example.puml"
INVALID_BRIEF="$SCRIPT_DIR/tests/invalid-brief.yaml"
INVALID_DIAGRAM="$SCRIPT_DIR/tests/invalid-diagram.puml"
MOCK_RENDER_SERVER="$SCRIPT_DIR/tests/mock_plantuml_server.py"

bash "$VALIDATE_SCRIPT" "$SKILL_DIR" >/dev/null

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
MOCK_PORT="$(python3 - <<'PY'
import socket

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
)"

cleanup() {
  if [[ -n "${MOCK_PID:-}" ]]; then
    kill "$MOCK_PID" >/dev/null 2>&1 || true
    wait "$MOCK_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}

python3 "$MOCK_RENDER_SERVER" --port "$MOCK_PORT" >"$TMP_DIR/mock-render.log" 2>&1 &
MOCK_PID=$!
trap cleanup EXIT

for _ in $(seq 1 30); do
  if curl -sS "http://127.0.0.1:$MOCK_PORT/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

SVG_OUTPUT="$TMP_DIR/render.svg"

if ! bash "$RENDER_SCRIPT" \
  "$VALID_DIAGRAM" \
  --server-url "http://127.0.0.1:$MOCK_PORT/plantuml" \
  --svg-output "$SVG_OUTPUT" >/dev/null; then
  echo "渲染检查未通过 mock 服务验证" >&2
  exit 1
fi

if [[ ! -f "$SVG_OUTPUT" ]]; then
  echo "渲染成功但未产出 svg 文件" >&2
  exit 1
fi

echo "测试通过：feipi-plantuml-generate-architecture-diagram"
