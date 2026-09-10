#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT=""
SERVER_URL="auto"
CONNECT_TIMEOUT=1
TOTAL_TIMEOUT=2
PODMAN_START_TIMEOUT="${PLANTUML_PODMAN_START_TIMEOUT_SECONDS:-30}"
PODMAN_READINESS_DELAY="${PLANTUML_PODMAN_READINESS_DELAY_SECONDS:-1}"
DEFAULT_LOCAL_PORT="${AGENT_PLANTUML_SERVER_PORT:-8199}"

usage() {
  cat <<'USAGE'
用法:
  bash scripts/preflight_renderer.sh [--out <renderer-preflight.json>] [--server-url <loopback-url>|auto]

返回码:
  0 - 本地 renderer 可用
  4 - 首次探测和一次 Podman 启动后的复检均失败；调用方必须 blocked
  5 - 连接被明确拒绝访问；不启动 Podman，调用方必须 blocked
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      OUTPUT="$2"
      shift 2
      ;;
    --server-url)
      SERVER_URL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! [[ "$PODMAN_START_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
  echo "PLANTUML_PODMAN_START_TIMEOUT_SECONDS 必须是正整数" >&2
  exit 1
fi
if ! [[ "$PODMAN_READINESS_DELAY" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "PLANTUML_PODMAN_READINESS_DELAY_SECONDS 必须是非负数" >&2
  exit 1
fi

TEMP_DIR="$(mktemp -d -t plantuml-preflight.XXXXXX)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT
PROBE_FILE="$TEMP_DIR/probe.puml"
PROBE_SVG="$TEMP_DIR/probe.svg"
cat >"$PROBE_FILE" <<'PUML'
@startuml
Alice -> Bob: preflight
@enduml
PUML

START_NS="$(python3 -c 'import time; print(time.monotonic_ns())')"

PROBE_ATTEMPTS=0
HTTP_REQUESTS=0
RENDER_OUTPUT=""
RENDER_EXIT=4
RENDERER_URL=""
REASON=""
FAILURE_KIND=""
RENDER_TARGET=""
CURL_EXIT_CODE=""
HTTP_STATUS=""

run_probe() {
  local request_count=0
  PROBE_ATTEMPTS=$((PROBE_ATTEMPTS + 1))
  set +e
  RENDER_OUTPUT="$(bash "$SCRIPT_DIR/check_render.sh" "$PROBE_FILE" \
    --svg-output "$PROBE_SVG" --server-url "$SERVER_URL" --timeout "$TOTAL_TIMEOUT" 2>&1)"
  RENDER_EXIT=$?
  set -e
  RENDERER_URL="$(printf '%s\n' "$RENDER_OUTPUT" | awk -F= '/^render_server=/{print $2; exit}')"
  request_count="$(printf '%s\n' "$RENDER_OUTPUT" | awk -F= '/^render_http_requests=/{print $2; exit}')"
  REASON="$(printf '%s\n' "$RENDER_OUTPUT" | awk -F= '/^render_reason=/{sub(/^render_reason=/, ""); print; exit}')"
  FAILURE_KIND="$(printf '%s\n' "$RENDER_OUTPUT" | awk -F= '/^render_failure_kind=/{print $2; exit}')"
  RENDER_TARGET="$(printf '%s\n' "$RENDER_OUTPUT" | awk '/^render_target=/{sub(/^render_target=/, ""); print; exit}')"
  CURL_EXIT_CODE="$(printf '%s\n' "$RENDER_OUTPUT" | awk -F= '/^render_curl_exit_code=/{print $2; exit}')"
  HTTP_STATUS="$(printf '%s\n' "$RENDER_OUTPUT" | awk -F= '/^render_http_status=/{print $2; exit}')"
  [[ "$request_count" =~ ^[0-9]+$ ]] || request_count=0
  HTTP_REQUESTS=$((HTTP_REQUESTS + request_count))
}

run_podman_once() {
  python3 - "$PODMAN_START_TIMEOUT" <<'PY'
import os
import signal
import subprocess
import sys

command = [
    "podman", "run", "--rm", "-d", "-p", "8199:8080", "--name", "plantuml",
    "docker.io/plantuml/plantuml-server:jetty",
]
process = subprocess.Popen(
    command,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    start_new_session=True,
)
try:
    output, _ = process.communicate(timeout=int(sys.argv[1]))
except subprocess.TimeoutExpired:
    os.killpg(process.pid, signal.SIGTERM)
    try:
        output, _ = process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
    if output:
        print(output, end="")
    raise SystemExit(124)
if output:
    print(output, end="")
raise SystemExit(process.returncode)
PY
}

run_probe

PODMAN_START_ATTEMPTED=false
# 首次探测已经取得有效 SVG；明确 renderer 可用，而不是笼统地说无需启动。
PODMAN_START_RESULT="renderer_available"
PODMAN_START_EXIT_CODE=""
PODMAN_START_ELIGIBLE=false
if [[ "$SERVER_URL" == "auto" && "$DEFAULT_LOCAL_PORT" == "8199" ]]; then
  PODMAN_START_ELIGIBLE=true
elif [[ "${SERVER_URL%/}" == "http://127.0.0.1:8199" \
  || "${SERVER_URL%/}" == "http://localhost:8199" ]]; then
  PODMAN_START_ELIGIBLE=true
fi
if [[ "$RENDER_EXIT" -eq 4 && "$PODMAN_START_ELIGIBLE" == "true" ]]; then
  if command -v podman >/dev/null 2>&1; then
    PODMAN_START_ATTEMPTED=true
    set +e
    PODMAN_OUTPUT="$(run_podman_once 2>&1)"
    PODMAN_START_EXIT_CODE=$?
    set -e
    if [[ "$PODMAN_START_EXIT_CODE" -eq 0 ]]; then
      PODMAN_START_RESULT="started"
      sleep "$PODMAN_READINESS_DELAY"
    elif [[ "$PODMAN_START_EXIT_CODE" -eq 124 ]]; then
      PODMAN_START_RESULT="timeout"
    else
      PODMAN_START_RESULT="failed"
    fi
    run_probe
  else
    PODMAN_START_RESULT="podman_unavailable"
  fi
fi

END_NS="$(python3 -c 'import time; print(time.monotonic_ns())')"

FINAL_STATUS="blocked"
BLOCKED_REASON="render_server_unavailable"
if [[ "$RENDER_EXIT" -eq 5 ]]; then
  BLOCKED_REASON="render_access_denied"
  if [[ "$PODMAN_START_ATTEMPTED" == "false" ]]; then
    PODMAN_START_RESULT="skipped_access_denied"
  fi
fi
if [[ "$RENDER_EXIT" -eq 0 && -n "$RENDERER_URL" && -s "$PROBE_SVG" ]]; then
  FINAL_STATUS="success"
  BLOCKED_REASON=""
fi

JSON_OUTPUT="$(python3 - "$FINAL_STATUS" "$RENDERER_URL" "$BLOCKED_REASON" "$REASON" \
  "$CONNECT_TIMEOUT" "$TOTAL_TIMEOUT" "$START_NS" "$END_NS" "$HTTP_REQUESTS" \
  "$PROBE_ATTEMPTS" "$PODMAN_START_ATTEMPTED" "$PODMAN_START_RESULT" \
  "$PODMAN_START_EXIT_CODE" "$PODMAN_START_TIMEOUT" "$PODMAN_READINESS_DELAY" \
  "$FAILURE_KIND" "$RENDER_TARGET" "$CURL_EXIT_CODE" "$HTTP_STATUS" <<'PY'
import json
import sys

status, renderer, blocked, reason = sys.argv[1:5]
elapsed_ms = round(max(0, int(sys.argv[8]) - int(sys.argv[7])) / 1_000_000, 3)
podman_exit = int(sys.argv[13]) if sys.argv[13] else None
print(json.dumps({
    "schema_version": "1",
    "final_status": status,
    "renderer_url": renderer,
    "blocked_reason": blocked,
    "issue": reason or blocked,
    "failure_kind": sys.argv[16],
    "render_target": sys.argv[17],
    "curl_exit_code": int(sys.argv[18]) if sys.argv[18] else None,
    "http_status": sys.argv[19],
    "connect_timeout_seconds": int(sys.argv[5]),
    "total_timeout_seconds": int(sys.argv[6]),
    "elapsed_ms": elapsed_ms,
    "http_requests": int(sys.argv[9]),
    "probe_attempts": int(sys.argv[10]),
    "podman_start_attempted": sys.argv[11] == "true",
    "podman_start_result": sys.argv[12],
    "podman_start_exit_code": podman_exit,
    "podman_start_timeout_seconds": int(sys.argv[14]),
    "podman_readiness_delay_seconds": int(sys.argv[15]),
    "startup_policy": "podman_once",
    "process_management_allowed": False,
}, indent=2, ensure_ascii=False))
PY
)"

if [[ -n "$OUTPUT" ]]; then
  mkdir -p "$(dirname "$OUTPUT")"
  printf '%s\n' "$JSON_OUTPUT" >"$OUTPUT"
fi
printf '%s\n' "$JSON_OUTPUT"

if [[ "$FINAL_STATUS" != "success" ]]; then
  [[ "$BLOCKED_REASON" == "render_access_denied" ]] && exit 5
  exit 4
fi
