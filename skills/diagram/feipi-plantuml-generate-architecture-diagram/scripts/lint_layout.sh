#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  bash scripts/lint_layout.sh <diagram.puml> [brief.optimized.yaml]

说明:
  针对架构图检查纵向布局、图例和基础间距设置。
  可选提供 brief.optimized.yaml 以检查 include_legend 字段和优化后的配置。
USAGE
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

INPUT_FILE="$1"
BRIEF_FILE="${2:-}"
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

if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*top to bottom direction'; then
  echo "布局校验失败：架构图必须显式声明 top to bottom direction" >&2
  exit 2
fi

if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*skinparam[[:space:]]+nodesep[[:space:]]+[0-9]+'; then
  echo "布局校验失败：缺少 skinparam nodesep" >&2
  exit 3
fi

if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*skinparam[[:space:]]+ranksep[[:space:]]+[0-9]+'; then
  echo "布局校验失败：缺少 skinparam ranksep" >&2
  exit 4
fi

PACKAGE_COUNT="$(printf '%s\n' "$CONTENT" | grep -Eic '^[[:space:]]*package[[:space:]]+"[^"]+"' || true)"
if [[ "$PACKAGE_COUNT" -lt 3 ]]; then
  echo "布局校验失败：架构图至少需要 3 个 package 作为层容器，当前：$PACKAGE_COUNT" >&2
  exit 5
fi

# Check if brief file is provided and include_legend is false
INCLUDE_LEGEND="true"
if [[ -n "$BRIEF_FILE" && -f "$BRIEF_FILE" ]]; then
  INCLUDE_LEGEND="$(python3 -c "
import yaml, sys
try:
    with open('$BRIEF_FILE') as f:
        data = yaml.safe_load(f)
    layout = data.get('layout', {})
    val = layout.get('include_legend', True)
    print('false' if val == False else 'true')
except:
    print('true')
")"
fi

if [[ "$INCLUDE_LEGEND" == "true" ]]; then
  if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*legend\b'; then
    echo "布局校验失败：缺少 legend，读者无法快速识别层级语义" >&2
    exit 6
  fi
fi

# === 黄金比例布局校验规则 ===

# 检查 Package ID 是否为简短单词（禁止连字符长名）
PACKAGE_IDS="$(printf '%s\n' "$CONTENT" | grep -Eo 'package "[^"]+" as [a-zA-Z_]+' | sed 's/package "[^"]*" as //' || true)"
if [[ -n "$PACKAGE_IDS" ]]; then
  INVALID_IDS="$(echo "$PACKAGE_IDS" | grep -E '^[a-z]+-[a-z]+' || true)"
  if [[ -n "$INVALID_IDS" ]]; then
    echo "布局校验失败：Package ID 使用了连字符长名：$INVALID_IDS" >&2
    echo "请使用简短单词 ID，如 user_as, protocol, ext_sys" >&2
    exit 7
  fi
fi

# 检查同域组件对齐（当 package 内组件数 >= 2 时，必须有 [hidden] 线或组件已垂直排列）
# 注意：这是一个 soft check，只警告不报错
while IFS= read -r line; do
  if [[ "$line" =~ ^package ]]; then
    pkg_name="$(echo "$line" | sed -nE 's/.*[[:space:]]as[[:space:]]+([A-Za-z_][A-Za-z0-9_]*).*/\1/p' || true)"
    if [[ -n "$pkg_name" ]]; then
      # 提取该 package 内的组件数量
      comp_count="$(awk -v pkg="$pkg_name" '
        $0 ~ "package.*as " pkg ".*\\{" { found=1; next }
        found && /^}/ { found=0; next }
        found && /^[[:space:]]*(component|actor|database|cloud|boundary)/ { count++ }
        END { print count+0 }
      ' "$INPUT_FILE")"

      # 检查是否有 [hidden] 线
      if [[ "$comp_count" -ge 2 ]]; then
        hidden_count="$(grep -c "\[hidden\]" "$INPUT_FILE" || echo "0")"
        if [[ "$hidden_count" -lt 1 ]]; then
          echo "布局提示：package '$pkg_name' 内有 $comp_count 个组件，建议添加 [hidden] 对齐线" >&2
          echo "  示例：${pkg_name}_comp1 -down[hidden]- ${pkg_name}_comp2" >&2
          # 不退出，只是提示
        fi
      fi
    fi
  fi
done <<< "$CONTENT"

LONG_LINES="$(awk 'length($0) > 140 {print NR ":" length($0)}' "$INPUT_FILE" || true)"
if [[ -n "$LONG_LINES" ]]; then
  echo "布局提示：存在超过 140 字符的长行，建议拆分标签或子图。" >&2
  echo "$LONG_LINES" >&2
fi

echo "layout_check=ok"
echo "layout_packages=$PACKAGE_COUNT"
echo "include_legend=$INCLUDE_LEGEND"
