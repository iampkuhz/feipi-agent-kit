#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  bash scripts/lint_layout.sh <diagram.puml>

说明:
  针对架构图检查纵向布局、图例和基础间距设置。
USAGE
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

INPUT_FILE="$1"
if [[ ! -f "$INPUT_FILE" ]]; then
  echo "输入文件不存在: $INPUT_FILE" >&2
  exit 1
fi

CONTENT="$(awk '
  /^[[:space:]]*\x27/ {next}
  /^[[:space:]]*\/\// {next}
  /^[[:space:]]*$/ {next}
  {print}
' "$INPUT_FILE")"

if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*top to bottom direction'; then
  echo "布局校验失败: 架构图必须显式声明 top to bottom direction" >&2
  exit 2
fi

if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*skinparam[[:space:]]+nodesep[[:space:]]+[0-9]+'; then
  echo "布局校验失败: 缺少 skinparam nodesep" >&2
  exit 3
fi

if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*skinparam[[:space:]]+ranksep[[:space:]]+[0-9]+'; then
  echo "布局校验失败: 缺少 skinparam ranksep" >&2
  exit 4
fi

PACKAGE_COUNT="$(printf '%s\n' "$CONTENT" | grep -Eic '^[[:space:]]*package[[:space:]]+"[^"]+"' || true)"
if [[ "$PACKAGE_COUNT" -lt 3 ]]; then
  echo "布局校验失败: 架构图至少需要 3 个 package 作为层容器，当前: $PACKAGE_COUNT" >&2
  exit 5
fi

if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*legend\b'; then
  echo "布局校验失败: 缺少 legend，读者无法快速识别层级语义" >&2
  exit 6
fi

LONG_LINES="$(awk 'length($0) > 140 {print NR ":" length($0)}' "$INPUT_FILE" || true)"
if [[ -n "$LONG_LINES" ]]; then
  echo "布局提示: 存在超过 140 字符的长行，建议拆分标签或子图。" >&2
  echo "$LONG_LINES" >&2
fi

echo "layout_check=ok"
echo "layout_packages=$PACKAGE_COUNT"
