#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  bash scripts/lint_layout.sh <diagram.puml>

说明:
  针对时序图检查布局、参与者声明和基础间距设置。
USAGE
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

INPUT_FILE="$1"
if [[ ! -f "$INPUT_FILE" ]]; then
  echo "输入文件不存在：$INPUT_FILE" >&2
  exit 1
fi

CONTENT="$(awk '
  /^[[:space:]]*\x27/ {next}
  /^[[:space:]]*\/\// {next}
  /^[[:space:]]*$/ {next}
  {print}
' "$INPUT_FILE")"

PARTICIPANT_COUNT="$(printf '%s\n' "$CONTENT" | grep -Eic '^[[:space:]]*(participant|actor|database)[[:space:]]+"[^"]+"' || true)"
if [[ "$PARTICIPANT_COUNT" -lt 2 ]]; then
  echo "布局校验失败：时序图至少需要 2 个参与者，当前：$PARTICIPANT_COUNT" >&2
  exit 2
fi

# Check for box/separator structure if groups are used
BOX_COUNT="$(printf '%s\n' "$CONTENT" | grep -Eic '^[[:space:]]*box[[:space:]]' || true)"
ENDBOX_COUNT="$(printf '%s\n' "$CONTENT" | grep -Eic '^[[:space:]]*endbox' || true)"
if [[ "$BOX_COUNT" -gt 0 && "$BOX_COUNT" -ne "$ENDBOX_COUNT" ]]; then
  echo "布局校验失败：box 和 endbox 数量不匹配，box=$BOX_COUNT, endbox=$ENDBOX_COUNT" >&2
  exit 5
fi

if [[ "$BOX_COUNT" -gt 0 ]] && printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*left[[:space:]]+to[[:space:]]+right[[:space:]]+direction'; then
  echo "布局校验失败：sequence diagram 中 box 与 left to right direction 互斥" >&2
  exit 6
fi

if printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*separator\b'; then
  echo "布局校验失败：不要使用 PlantUML separator 关键字；请改用 == 组名 == 分隔线" >&2
  exit 7
fi

AUTONUMBER_LINE="$(grep -nE '^[[:space:]]*autonumber\b' "$INPUT_FILE" | head -1 | cut -d: -f1 || true)"
LAST_PARTICIPANT_LINE="$(grep -nE '^[[:space:]]*(participant|actor|database)[[:space:]]+"[^"]+"' "$INPUT_FILE" | tail -1 | cut -d: -f1 || true)"
if [[ -z "$AUTONUMBER_LINE" ]]; then
  echo "布局提示：建议包含 autonumber 以自动编号消息" >&2
elif [[ -n "$LAST_PARTICIPANT_LINE" && "$AUTONUMBER_LINE" -le "$LAST_PARTICIPANT_LINE" ]]; then
  echo "布局校验失败：autonumber 必须放在所有参与者声明之后、第一条消息之前" >&2
  exit 8
fi

if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*skinparam[[:space:]]+nodesep[[:space:]]+[0-9]+'; then
  echo "布局校验失败：缺少 skinparam nodesep" >&2
  exit 3
fi

if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*skinparam[[:space:]]+ranksep[[:space:]]+[0-9]+'; then
  echo "布局校验失败：缺少 skinparam ranksep" >&2
  exit 4
fi

LONG_LINES="$(awk 'length($0) > 140 {print NR ":" length($0)}' "$INPUT_FILE" || true)"
if [[ -n "$LONG_LINES" ]]; then
  echo "布局提示：存在超过 140 字符的长行，建议拆分标签或子图。" >&2
  echo "$LONG_LINES" >&2
fi

echo "layout_check=ok"
echo "layout_participants=$PARTICIPANT_COUNT"
