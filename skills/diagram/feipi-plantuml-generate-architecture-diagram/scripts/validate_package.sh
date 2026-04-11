#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# validate_package.sh - 架构图 package 验证入口
# =============================================================================
# 用法:
#   bash scripts/validate_package.sh --brief <brief.yaml> --diagram <diagram.puml> --out-dir <dir>
#
# 产出物 (在 <out-dir> 中):
#   - brief.optimized.yaml   (优化后的 brief)
#   - diagram.puml           (输入的 diagram 原样复制)
#   - diagram.svg            (仅 render 成功时存在)
#   - validation.json        (验证结果合同)
#
# 退出码:
#   0 - final_status=success (所有校验通过且 render_result=ok)
#   1 - final_status=blocked (任一校验失败)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 默认参数
BRIEF_FILE=""
DIAGRAM_FILE=""
OUT_DIR=""

# 解析参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    --brief)
      BRIEF_FILE="$2"
      shift 2
      ;;
    --diagram)
      DIAGRAM_FILE="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      cat <<'USAGE'
用法:
  bash scripts/validate_package.sh --brief <brief.yaml> --diagram <diagram.puml> --out-dir <dir>

产出物 (在 <out-dir> 中):
  - brief.normalized.yaml  (规范化后的 brief)
  - diagram.puml           (输入的 diagram 原样复制)
  - diagram.svg            (仅 render 成功时存在)
  - validation.json        (验证结果合同)
USAGE
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      exit 1
      ;;
  esac
done

# 参数校验
if [[ -z "$BRIEF_FILE" || -z "$DIAGRAM_FILE" || -z "$OUT_DIR" ]]; then
  echo "缺少必需参数：--brief, --diagram, --out-dir" >&2
  exit 1
fi

if [[ ! -f "$BRIEF_FILE" ]]; then
  echo "brief 文件不存在：$BRIEF_FILE" >&2
  exit 1
fi

if [[ ! -f "$DIAGRAM_FILE" ]]; then
  echo "diagram 文件不存在：$DIAGRAM_FILE" >&2
  exit 1
fi

# 创建输出目录
mkdir -p "$OUT_DIR"

# 初始化验证状态
BRIEF_CHECK="pending"
COVERAGE_CHECK="pending"
LAYOUT_CHECK="pending"
RENDER_RESULT="pending"
RENDER_SERVER=""
BLOCKED_REASON=""
FINAL_STATUS="pending"

# 输出文件路径
SVG_OUT="$OUT_DIR/diagram.svg"
VALIDATION_OUT="$OUT_DIR/validation.json"

# 清理函数
cleanup() {
  local exit_code=$?
  if [[ "$FINAL_STATUS" != "success" ]]; then
    if [[ -z "$BLOCKED_REASON" ]]; then
      BLOCKED_REASON="unknown_error"
    fi
    FINAL_STATUS="blocked"
  fi

  # 写入 validation.json
  python3 - "$OUT_DIR/validation.json" "$BRIEF_FILE" "$DIAGRAM_FILE" "$SVG_OUT" \
    "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "$RENDER_RESULT" "$RENDER_SERVER" \
    "$FINAL_STATUS" "$BLOCKED_REASON" <<PY
import json
import hashlib
from pathlib import Path

def sha256_file(path):
    if not Path(path).exists():
        return ""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

output_path = Path("$OUT_DIR/validation.json")
brief_path = Path("$BRIEF_FILE")
diagram_path = Path("$DIAGRAM_FILE")
svg_path = Path("$SVG_OUT")
brief_check = "$BRIEF_CHECK"
coverage_check = "$COVERAGE_CHECK"
layout_check = "$LAYOUT_CHECK"
render_result = "$RENDER_RESULT"
render_server = "$RENDER_SERVER"
final_status = "$FINAL_STATUS"
blocked_reason = "$BLOCKED_REASON"

# 读取现有 JSON 如果存在
if output_path.exists():
    try:
        existing = json.loads(output_path.read_text())
    except:
        existing = {}
else:
    existing = {}

result = {
    "schema_version": "1.0",
    "skill_name": "feipi-plantuml-generate-architecture-diagram",
    "diagram_type": "architecture",
    "brief_path": str(brief_path),
    "diagram_path": str(diagram_path),
    "svg_path": str(svg_path) if svg_path.exists() else "",
    "brief_check": brief_check,
    "coverage_check": coverage_check,
    "layout_check": layout_check,
    "render_result": render_result,
    "render_server": render_server,
    "puml_sha256": sha256_file(diagram_path),
    "svg_sha256": sha256_file(svg_path),
    "final_status": final_status,
    "blocked_reason": blocked_reason
}

result.update(existing)
output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
PY
  exit "$exit_code"
}

trap cleanup EXIT

# 复制输入文件到输出目录
DIAGRAM_OUT="$OUT_DIR/diagram.puml"
BRIEF_OUT="$OUT_DIR/brief.optimized.yaml"  # 优化后的 brief

if [[ "$DIAGRAM_FILE" != "$DIAGRAM_OUT" ]]; then
  cp -f "$DIAGRAM_FILE" "$DIAGRAM_OUT"
fi

# =============================================================================
# Step 0: Optimize Brief (布局优化)
# =============================================================================
echo "Step 0/5: Optimizing brief for layout..."

OPTIMIZE_SCRIPT="$SCRIPT_DIR/optimize_brief.py"
if [[ -f "$OPTIMIZE_SCRIPT" ]]; then
  python3 "$OPTIMIZE_SCRIPT" "$BRIEF_FILE" "$BRIEF_OUT"
  echo "  Brief optimized: $BRIEF_OUT"
else
  echo "  Warning: optimize_brief.py not found, using original brief" >&2
  if [[ "$BRIEF_FILE" != "$BRIEF_OUT" ]]; then
    cp -f "$BRIEF_FILE" "$BRIEF_OUT"
  fi
fi

# 临时 JSON 文件用于累积状态
TMP_JSON="$(mktemp)"
echo '{}' > "$TMP_JSON"

update_json() {
  python3 - "$TMP_JSON" <<PY
import json
from pathlib import Path

path = Path("$TMP_JSON")
data = json.loads(path.read_text() or "{}")

# 更新字段
$1

path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
PY
}

# =============================================================================
# Step 1: Validate Brief
# =============================================================================
echo "Step 1/4: Validating brief..."

BRIEF_OUTPUT="$(python3 "$SCRIPT_DIR/validate_brief.py" "$BRIEF_FILE" 2>&1)" || {
  BRIEF_CHECK="failed"
  BLOCKED_REASON="brief_validation_failed"
  echo "[FAIL] brief validation failed" >&2
  echo "$BRIEF_OUTPUT" >&2
  exit 1
}

BRIEF_CHECK="ok"
echo "[OK] brief validation passed"

# =============================================================================
# Step 2: Check Coverage
# =============================================================================
echo "Step 2/4: Checking coverage..."

COVERAGE_OUTPUT="$(python3 "$SCRIPT_DIR/check_coverage.py" --brief "$BRIEF_FILE" --diagram "$DIAGRAM_FILE" 2>&1)" || {
  COVERAGE_CHECK="failed"
  BLOCKED_REASON="coverage_validation_failed"
  echo "[FAIL] coverage check failed" >&2
  echo "$COVERAGE_OUTPUT" >&2
  exit 1
}

COVERAGE_CHECK="ok"
echo "[OK] coverage check passed"

# =============================================================================
# Step 3: Lint Layout
# =============================================================================
echo "Step 3/4: Linting layout..."

LAYOUT_OUTPUT="$(bash "$SCRIPT_DIR/lint_layout.sh" "$DIAGRAM_FILE" "$BRIEF_FILE" 2>&1)" || {
  LAYOUT_CHECK="failed"
  BLOCKED_REASON="layout_validation_failed"
  echo "[FAIL] layout check failed" >&2
  echo "$LAYOUT_OUTPUT" >&2
  exit 1
}

LAYOUT_CHECK="ok"
echo "[OK] layout check passed"

# =============================================================================
# Step 4: Check Render
# =============================================================================
echo "Step 4/4: Checking render..."

RENDER_OUTPUT="$(bash "$SCRIPT_DIR/check_render.sh" "$DIAGRAM_FILE" --svg-output "$SVG_OUT" 2>&1)" || {
  render_exit=$?
  if [[ "$render_exit" -eq 2 ]]; then
    RENDER_RESULT="syntax_error"
    BLOCKED_REASON="render_syntax_error"
    echo "[FAIL] render syntax error" >&2
    echo "$RENDER_OUTPUT" >&2
    exit 1
  elif [[ "$render_exit" -eq 4 ]]; then
    RENDER_RESULT="skipped"
    # 渲染后端不可用 - 这也是一种 blocked 状态
    BLOCKED_REASON="render_server_unavailable"
    echo "[FAIL] no render server available" >&2
    echo "$RENDER_OUTPUT" >&2
    exit 1
  else
    RENDER_RESULT="failed"
    BLOCKED_REASON="render_failed"
    echo "[FAIL] render failed" >&2
    echo "$RENDER_OUTPUT" >&2
    exit 1
  fi
}

# 解析 render 输出
if echo "$RENDER_OUTPUT" | grep -q "render_result=ok"; then
  RENDER_RESULT="ok"
  RENDER_SERVER="$(echo "$RENDER_OUTPUT" | grep "render_server=" | cut -d'=' -f2)"
  echo "[OK] render passed, server: $RENDER_SERVER"
else
  RENDER_RESULT="failed"
  BLOCKED_REASON="render_failed"
  echo "[FAIL] render failed" >&2
  echo "$RENDER_OUTPUT" >&2
  exit 1
fi

# =============================================================================
# All checks passed - write final validation.json
# =============================================================================
FINAL_STATUS="success"
BLOCKED_REASON=""

# 写入最终的 validation.json
python3 - "$VALIDATION_OUT" "$BRIEF_FILE" "$DIAGRAM_FILE" "$SVG_OUT" \
  "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "$RENDER_RESULT" "$RENDER_SERVER" "$FINAL_STATUS" <<PY
import json
import hashlib
from pathlib import Path
from datetime import datetime

def sha256_file(path):
    if not Path(path).exists():
        return ""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

validation_path = Path("$VALIDATION_OUT")
brief_path = Path("$BRIEF_FILE")
diagram_path = Path("$DIAGRAM_FILE")
svg_path = Path("$SVG_OUT")

result = {
    "schema_version": "1.0",
    "skill_name": "feipi-plantuml-generate-architecture-diagram",
    "diagram_type": "architecture",
    "brief_path": str(brief_path),
    "diagram_path": str(diagram_path),
    "svg_path": str(svg_path) if svg_path.exists() else "",
    "brief_check": "$BRIEF_CHECK",
    "coverage_check": "$COVERAGE_CHECK",
    "layout_check": "$LAYOUT_CHECK",
    "render_result": "$RENDER_RESULT",
    "render_server": "$RENDER_SERVER",
    "puml_sha256": sha256_file(diagram_path),
    "svg_sha256": sha256_file(svg_path),
    "final_status": "$FINAL_STATUS",
    "blocked_reason": "",
    "validated_at": datetime.now().isoformat()
}

validation_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
PY

echo ""
echo "=== Validation Complete ==="
echo "Package output: $OUT_DIR"
echo "  - brief.normalized.yaml"
echo "  - diagram.puml"
echo "  - diagram.svg"
echo "  - validation.json"
echo ""
echo "final_status=success"

exit 0
