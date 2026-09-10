#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  bash scripts/check_render.sh <input.puml> [--svg-output <path>] [--server-url <url>|auto] [--timeout <sec>]

返回码:
  0 - 渲染成功
  2 - 语法或渲染内容错误
  4 - 没有可用渲染后端
  5 - 连接被明确拒绝访问（可能是沙箱或系统权限）
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVERS_CONFIG="$SKILL_DIR/assets/server_candidates.txt"
DEFAULT_TIMEOUT=20
DEFAULT_CONNECT_TIMEOUT=1
DEFAULT_LOCAL_PORT="${AGENT_PLANTUML_SERVER_PORT:-8199}"
REQUEST_COUNT=0

trim() {
  printf '%s' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

normalize_server_url() {
  local value
  value="$(trim "$1")"
  value="${value%/}"
  [[ -z "$value" ]] && return 1
  printf '%s\n' "$value"
}

is_loopback_server_url() {
  python3 - "$1" <<'PY'
import sys
from urllib.parse import urlparse

value = urlparse(sys.argv[1])
if value.scheme not in {"http", "https"} or value.hostname not in {"127.0.0.1", "localhost", "::1"}:
    raise SystemExit(1)
if value.username or value.password:
    raise SystemExit(1)
PY
}

encode_plantuml_file() {
  local input_file="$1"
  python3 - "$input_file" <<'PY'
import sys
import zlib
from pathlib import Path


def encode6bit(value: int) -> str:
    if value < 10:
        return chr(48 + value)
    value -= 10
    if value < 26:
        return chr(65 + value)
    value -= 26
    if value < 26:
        return chr(97 + value)
    value -= 26
    return "-" if value == 0 else "_"


def append3bytes(b1: int, b2: int, b3: int) -> str:
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    return "".join(
        [
            encode6bit(c1 & 0x3F),
            encode6bit(c2 & 0x3F),
            encode6bit(c3 & 0x3F),
            encode6bit(c4 & 0x3F),
        ]
    )


def encode_plantuml_text(text: bytes) -> str:
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(text) + compressor.flush()
    out = []
    for idx in range(0, len(compressed), 3):
      chunk = compressed[idx : idx + 3]
      if len(chunk) == 3:
          out.append(append3bytes(chunk[0], chunk[1], chunk[2]))
      elif len(chunk) == 2:
          out.append(append3bytes(chunk[0], chunk[1], 0))
      else:
          out.append(append3bytes(chunk[0], 0, 0))
    return "".join(out)


payload = Path(sys.argv[1]).read_bytes()
print(encode_plantuml_text(payload))
PY
}

INPUT_FILE=""
SVG_OUTPUT=""
SERVER_URL="auto"
TIMEOUT="$DEFAULT_TIMEOUT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --svg-output)
      SVG_OUTPUT="$2"
      shift 2
      ;;
    --server-url)
      SERVER_URL="$2"
      shift 2
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$INPUT_FILE" ]]; then
        INPUT_FILE="$1"
        shift
      else
        echo "未知参数: $1" >&2
        usage
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$INPUT_FILE" || ! -f "$INPUT_FILE" ]]; then
  echo "输入文件不存在: $INPUT_FILE" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "缺少依赖: curl" >&2
  exit 4
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "缺少依赖: python3" >&2
  exit 4
fi

if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]] || [[ "$TIMEOUT" -lt 1 ]]; then
  echo "--timeout 必须是正整数" >&2
  exit 1
fi

# 调用者显式指定的旧产物不能在本轮失败后继续存在。
if [[ -n "$SVG_OUTPUT" ]]; then
  rm -f -- "$SVG_OUTPUT"
fi

declare -a CANDIDATES=()
append_candidate() {
  local value=""
  if ! value="$(normalize_server_url "$1")"; then
    return 0
  fi
  if ! is_loopback_server_url "$value"; then
    echo "拒绝非本地 renderer：$value" >&2
    return 0
  fi

  local item=""
  for item in "${CANDIDATES[@]:-}"; do
    [[ "$item" == "$value" ]] && return 0
  done
  CANDIDATES+=("$value")
}

if [[ "$SERVER_URL" == "auto" ]]; then
  if [[ -f "$SERVERS_CONFIG" ]]; then
    while IFS= read -r raw || [[ -n "$raw" ]]; do
      line="${raw%%#*}"
      line="$(trim "$line")"
      [[ -z "$line" ]] && continue
      line="${line//\$\{AGENT_PLANTUML_SERVER_PORT\}/$DEFAULT_LOCAL_PORT}"
      line="${line//\$AGENT_PLANTUML_SERVER_PORT/$DEFAULT_LOCAL_PORT}"
      append_candidate "$line"
    done < "$SERVERS_CONFIG"
  fi
else
  append_candidate "$SERVER_URL"
fi

if [[ "${#CANDIDATES[@]}" -eq 0 ]]; then
  echo "render_result=skipped"
  echo "render_reason=no_server_candidates"
  echo "render_http_requests=$REQUEST_COUNT"
  exit 4
fi

ENCODED="$(encode_plantuml_file "$INPUT_FILE")"
LAST_ERROR=""

for candidate in "${CANDIDATES[@]}"; do
  REQUEST_SVG="$(mktemp -t plantuml-render-response.XXXXXX.svg)"
  SVG_CODE="$(mktemp)"
  SVG_ERR="$(mktemp)"
  SVG_HEADERS="$(mktemp)"
  REQUEST_COUNT=$((REQUEST_COUNT + 1))
  CURL_EXIT=0
  LC_ALL=C curl -sS --connect-timeout "$DEFAULT_CONNECT_TIMEOUT" --max-time "$TIMEOUT" -D "$SVG_HEADERS" -o "$REQUEST_SVG" -w '%{http_code}' "$candidate/svg/$ENCODED" >"$SVG_CODE" 2>"$SVG_ERR" || CURL_EXIT=$?
  if [[ "$CURL_EXIT" -ne 0 ]]; then
    LAST_ERROR="$(cat "$SVG_ERR")"
    # 仅将连接阶段的明确权限错误归类为访问被拒绝；curl 7 本身不能证明沙箱限制。
    # 排除本地输出写入等错误，避免把文件权限问题误认成网络权限问题。
    if [[ "$CURL_EXIT" -eq 7 ]] && printf '%s\n' "$LAST_ERROR" | grep -Eqi 'Operation not permitted|Permission denied'; then
      echo "render_result=skipped"
      echo "render_reason=$LAST_ERROR"
      echo "render_failure_kind=permission_denied"
      echo "render_target=$candidate"
      echo "render_curl_exit_code=$CURL_EXIT"
      echo "render_http_status=$(cat "$SVG_CODE")"
      echo "render_http_requests=$REQUEST_COUNT"
      rm -f "$REQUEST_SVG" "$SVG_CODE" "$SVG_ERR" "$SVG_HEADERS"
      exit 5
    fi
    rm -f "$REQUEST_SVG" "$SVG_CODE" "$SVG_ERR" "$SVG_HEADERS"
    continue
  fi

  STATUS="$(cat "$SVG_CODE")"
  rm -f "$SVG_CODE" "$SVG_ERR"
  set +e
  SVG_STATE="$(python3 "$SCRIPT_DIR/lib/svg_validation.py" "$REQUEST_SVG" 2>/dev/null)"
  SVG_CHECK_EXIT=$?
  set -e
  HAS_ERROR_HEADER=false
  grep -Eqi '^X-PlantUML-Diagram-Error:' "$SVG_HEADERS" && HAS_ERROR_HEADER=true
  HAS_SVG_CONTENT_TYPE=false
  grep -Eqi '^Content-Type:[[:space:]]*image/svg\+xml([[:space:];]|$)' "$SVG_HEADERS" && HAS_SVG_CONTENT_TYPE=true
  rm -f "$SVG_HEADERS"

  if [[ "$SVG_CHECK_EXIT" -ne 1 && ("$HAS_ERROR_HEADER" == "true" || "$SVG_STATE" == "error") \
    && ("$STATUS" =~ ^2[0-9][0-9]$ || "$STATUS" == "400") ]]; then
    echo "render_result=syntax_error"
    echo "render_http_requests=$REQUEST_COUNT"
    rm -f "$REQUEST_SVG"
    exit 2
  fi
  if [[ ! "$STATUS" =~ ^2[0-9][0-9]$ || "$SVG_STATE" != "valid" || "$HAS_SVG_CONTENT_TYPE" != "true" ]]; then
    LAST_ERROR="svg 响应无效，HTTP $STATUS"
    rm -f "$REQUEST_SVG"
    continue
  fi

  if [[ -z "$SVG_OUTPUT" ]]; then
    SVG_OUTPUT="$(mktemp -t plantuml-render-XXXXXX.svg)"
  fi
  mv -f "$REQUEST_SVG" "$SVG_OUTPUT"

  echo "render_result=ok"
  echo "render_server=$candidate"
  echo "render_svg=$SVG_OUTPUT"
  echo "render_http_requests=$REQUEST_COUNT"
  exit 0
done

echo "render_result=skipped"
echo "render_reason=${LAST_ERROR:-no_available_server}"
echo "render_http_requests=$REQUEST_COUNT"
exit 4
