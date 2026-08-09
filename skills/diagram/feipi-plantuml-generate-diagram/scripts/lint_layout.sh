#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'USAGE'
用法:
  bash scripts/lint_layout.sh --type <architecture|sequence|component|activity|deployment> <diagram.puml> [brief.yaml]

说明:
  按 profile 执行布局校验。
  architecture：检查纵向布局、package 数量、legend、间距。
  sequence：检查参与者、box/separator、编号策略和间距。
  component/activity/deployment：检查方向、节点容器、间距及图面密度。
USAGE
}

DIAGRAM_TYPE=""
INPUT_FILE=""
BRIEF_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type)
      DIAGRAM_TYPE="$2"
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
      elif [[ -z "$BRIEF_FILE" ]]; then
        BRIEF_FILE="$1"
        shift
      else
        echo "未知参数：$1" >&2
        usage
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$DIAGRAM_TYPE" ]]; then
  echo "缺少 --type 参数" >&2
  usage
  exit 1
fi

if [[ -z "$INPUT_FILE" || ! -f "$INPUT_FILE" ]]; then
  echo "输入文件不存在：$INPUT_FILE" >&2
  exit 1
fi

CONTENT="$(awk '
  /^[[:space:]]*\x27/ {next}
  /^[[:space:]]*\/\// {next}
  /^[[:space:]]*$/ {next}
  {print}
' "$INPUT_FILE")"

brief_value() {
  local path="$1"
  local dotted="$2"
  local default="$3"
  if [[ -z "$path" || ! -f "$path" ]]; then
    printf '%s\n' "$default"
    return 0
  fi
  python3 - "$path" "$dotted" "$default" "$SCRIPT_DIR/lib" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[4])
from brief_loader import load_yaml
data = load_yaml(Path(sys.argv[1]))
value = data
for key in sys.argv[2].split("."):
    value = value.get(key) if isinstance(value, dict) else None
    if value is None:
        break
if value is None:
    value = sys.argv[3]
if isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}

require_spacing() {
  if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*skinparam[[:space:]]+nodesep[[:space:]]+[0-9]+'; then
    echo "布局校验失败：缺少 skinparam nodesep" >&2
    exit 3
  fi
  if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*skinparam[[:space:]]+ranksep[[:space:]]+[0-9]+'; then
    echo "布局校验失败：缺少 skinparam ranksep" >&2
    exit 4
  fi
}

require_declared_direction() {
  local direction="${1:-top_to_bottom}"
  local syntax="top to bottom direction"
  [[ "$direction" == "left_to_right" ]] && syntax="left to right direction"
  if ! printf '%s\n' "$CONTENT" | grep -Eiq "^[[:space:]]*${syntax}"; then
    echo "布局校验失败：必须声明 ${syntax}" >&2
    exit 2
  fi
}

require_legend_if_configured() {
  local include_legend
  include_legend="$(brief_value "$BRIEF_FILE" "layout.include_legend" "false")"
  if [[ "$include_legend" == "true" ]] && ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*legend\b'; then
    echo "布局校验失败：layout.include_legend=true 时必须包含 legend" >&2
    exit 6
  fi
}

actual_metrics() {
  python3 "$SCRIPT_DIR/lib/puml_metrics_cli.py" --type "$DIAGRAM_TYPE" "$INPUT_FILE"
}

# =============================================================================
# Architecture 布局校验
# =============================================================================
if [[ "$DIAGRAM_TYPE" == "architecture" ]]; then
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

  # Legend check
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
")" || true
  fi

  if [[ "$INCLUDE_LEGEND" == "true" ]]; then
    if ! printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*legend\b'; then
      echo "布局校验失败：缺少 legend，读者无法快速识别层级语义" >&2
      exit 6
    fi
  fi

  # Long lines
  LONG_LINES="$(awk 'length($0) > 140 {print NR ":" length($0)}' "$INPUT_FILE" || true)"
  if [[ -n "$LONG_LINES" ]]; then
    echo "布局提示：存在超过 140 字符的长行，建议拆分标签或子图。" >&2
    echo "$LONG_LINES" >&2
  fi

  echo "layout_check=ok"
  echo "layout_packages=$PACKAGE_COUNT"
  exit 0
fi

# =============================================================================
# Sequence 布局校验
# =============================================================================
if [[ "$DIAGRAM_TYPE" == "sequence" ]]; then
  PARTICIPANT_COUNT="$(printf '%s\n' "$CONTENT" | grep -Eic '^[[:space:]]*(participant|actor|database)[[:space:]]+"[^"]+"' || true)"
  if [[ "$PARTICIPANT_COUNT" -lt 2 ]]; then
    echo "布局校验失败：时序图至少需要 2 个参与者，当前：$PARTICIPANT_COUNT" >&2
    exit 2
  fi

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

  NUMBERING_SCHEME="$(brief_value "$BRIEF_FILE" "numbering_scheme" "interaction_mr")"
  AUTONUMBER_LINE="$(grep -nE '^[[:space:]]*autonumber\b' "$INPUT_FILE" | head -1 | cut -d: -f1 || true)"
  LAST_PARTICIPANT_LINE="$(grep -nE '^[[:space:]]*(participant|actor|database)[[:space:]]+"[^"]+"' "$INPUT_FILE" | tail -1 | cut -d: -f1 || true)"
  if [[ "$NUMBERING_SCHEME" == "process_s" ]]; then
    if [[ -n "$AUTONUMBER_LINE" ]]; then
      echo "布局校验失败：process_s 已显式使用 S 编号，禁止 autonumber" >&2
      exit 8
    fi
  else
    if [[ -z "$AUTONUMBER_LINE" ]]; then
      echo "布局提示：建议包含 autonumber 以自动编号消息" >&2
    elif [[ -n "$LAST_PARTICIPANT_LINE" && "$AUTONUMBER_LINE" -le "$LAST_PARTICIPANT_LINE" ]]; then
      echo "布局校验失败：autonumber 必须放在所有参与者声明之后、第一条消息之前" >&2
      exit 8
    fi
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
  exit 0
fi

# =============================================================================
# Component 布局校验
# =============================================================================
if [[ "$DIAGRAM_TYPE" == "component" ]]; then
  DIRECTION="$(brief_value "$BRIEF_FILE" "layout.direction" "top_to_bottom")"
  require_declared_direction "$DIRECTION"
  require_spacing
  require_legend_if_configured
  IFS=$'\t' read -r NODE_COUNT EDGE_COUNT MAX_DEGREE < <(actual_metrics)
  PACKAGE_COUNT="$(printf '%s\n' "$CONTENT" | grep -Eic '^[[:space:]]*package[[:space:]]+"[^"]+"' || true)"
  if [[ "$PACKAGE_COUNT" -lt 1 || "$NODE_COUNT" -lt 2 || "$NODE_COUNT" -gt 8 || "$EDGE_COUNT" -gt 10 || "$MAX_DEGREE" -gt 4 ]]; then
    echo "布局校验失败：component 要求 package>=1、节点 2–8、边<=10、连接度<=4；实际 package=$PACKAGE_COUNT node=$NODE_COUNT edge=$EDGE_COUNT degree=$MAX_DEGREE" >&2
    exit 9
  fi
  echo "layout_check=ok"
  echo "layout_nodes=$NODE_COUNT"
  echo "layout_edges=$EDGE_COUNT"
  exit 0
fi

# =============================================================================
# Activity 布局校验
# =============================================================================
if [[ "$DIAGRAM_TYPE" == "activity" ]]; then
  DIRECTION="$(brief_value "$BRIEF_FILE" "layout.direction" "top_to_bottom")"
  require_declared_direction "$DIRECTION"
  require_spacing
  require_legend_if_configured
  if printf '%s\n' "$CONTENT" | grep -Eiq '^[[:space:]]*autonumber\b'; then
    echo "布局校验失败：activity 使用 S 编号，禁止 autonumber" >&2
    exit 8
  fi
  IFS=$'\t' read -r STEP_COUNT EDGE_COUNT MAX_DEGREE < <(actual_metrics)
  if [[ "$STEP_COUNT" -lt 5 ]]; then
    echo "布局校验失败：activity 至少需要 5 个已编号步骤，实际：$STEP_COUNT" >&2
    exit 9
  fi
  echo "layout_check=ok"
  echo "layout_steps=$STEP_COUNT"
  exit 0
fi

# =============================================================================
# Deployment 布局校验
# =============================================================================
if [[ "$DIAGRAM_TYPE" == "deployment" ]]; then
  DIRECTION="$(brief_value "$BRIEF_FILE" "layout.direction" "top_to_bottom")"
  require_declared_direction "$DIRECTION"
  require_spacing
  require_legend_if_configured
  ZONE_COUNT="$(printf '%s\n' "$CONTENT" | grep -Eic '^[[:space:]]*node[[:space:]]+"[^"]+"[[:space:]]+as[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\{' || true)"
  IFS=$'\t' read -r NODE_COUNT EDGE_COUNT MAX_DEGREE < <(actual_metrics)
  if [[ "$ZONE_COUNT" -lt 2 || "$NODE_COUNT" -lt 2 || "$NODE_COUNT" -gt 8 || "$EDGE_COUNT" -lt 1 || "$EDGE_COUNT" -gt 10 || "$MAX_DEGREE" -gt 4 ]]; then
    echo "布局校验失败：deployment 要求物理区>=2、节点 2–8、边 1–10、连接度<=4；实际 zone=$ZONE_COUNT node=$NODE_COUNT edge=$EDGE_COUNT degree=$MAX_DEGREE" >&2
    exit 9
  fi
  echo "layout_check=ok"
  echo "layout_zones=$ZONE_COUNT"
  echo "layout_edges=$EDGE_COUNT"
  exit 0
fi

echo "不支持的图类型：$DIAGRAM_TYPE" >&2
exit 1
