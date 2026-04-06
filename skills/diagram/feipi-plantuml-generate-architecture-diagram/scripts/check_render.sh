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
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVERS_CONFIG="$SKILL_DIR/assets/server_candidates.txt"
DEFAULT_TIMEOUT=20
DEFAULT_LOCAL_PORT="${AGENT_PLANTUML_SERVER_PORT:-8199}"

trim() {
  printf '%s' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

normalize_server_url() {
  local value
  value="$(trim "$1")"
  value="${value%/}"
  [[ -z "$value" ]] && return 1
  if [[ "$value" =~ /plantuml$ ]]; then
    printf '%s\n' "$value"
  else
    printf '%s/plantuml\n' "$value"
  fi
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

declare -a CANDIDATES=()
append_candidate() {
  local value=""
  if ! value="$(normalize_server_url "$1")"; then
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
  exit 4
fi

ENCODED="$(encode_plantuml_file "$INPUT_FILE")"
LAST_ERROR=""

for candidate in "${CANDIDATES[@]}"; do
  TXT_BODY="$(mktemp)"
  TXT_CODE="$(mktemp)"
  TXT_ERR="$(mktemp)"
  if ! curl -sS --max-time "$TIMEOUT" -o "$TXT_BODY" -w '%{http_code}' "$candidate/txt/$ENCODED" >"$TXT_CODE" 2>"$TXT_ERR"; then
    LAST_ERROR="$(cat "$TXT_ERR")"
    rm -f "$TXT_BODY" "$TXT_CODE" "$TXT_ERR"
    continue
  fi

  STATUS="$(cat "$TXT_CODE")"
  BODY="$(cat "$TXT_BODY")"
  rm -f "$TXT_CODE" "$TXT_ERR" "$TXT_BODY"

  if [[ "$STATUS" == "200" ]] && printf '%s\n' "$BODY" | grep -Eqi 'syntax error|\[from string'; then
    echo "render_result=syntax_error"
    printf '%s\n' "$BODY"
    exit 2
  fi

  if [[ "$STATUS" != "200" ]]; then
    LAST_ERROR="txt 接口不可用，HTTP $STATUS"
    continue
  fi

  if [[ -z "$SVG_OUTPUT" ]]; then
    SVG_OUTPUT="$(mktemp -t plantuml-render-XXXXXX.svg)"
  fi

  SVG_CODE="$(mktemp)"
  SVG_ERR="$(mktemp)"
  if ! curl -sS --max-time "$TIMEOUT" -o "$SVG_OUTPUT" -w '%{http_code}' "$candidate/svg/$ENCODED" >"$SVG_CODE" 2>"$SVG_ERR"; then
    LAST_ERROR="$(cat "$SVG_ERR")"
    rm -f "$SVG_CODE" "$SVG_ERR"
    continue
  fi

  STATUS="$(cat "$SVG_CODE")"
  rm -f "$SVG_CODE" "$SVG_ERR"
  if [[ "$STATUS" != "200" ]] || ! grep -qi '<svg' "$SVG_OUTPUT"; then
    LAST_ERROR="svg 接口不可用，HTTP $STATUS"
    continue
  fi

  echo "render_result=ok"
  echo "render_server=$candidate"
  echo "render_svg=$SVG_OUTPUT"
  exit 0
done

echo "render_result=skipped"
echo "render_reason=${LAST_ERROR:-no_available_server}"
exit 4
