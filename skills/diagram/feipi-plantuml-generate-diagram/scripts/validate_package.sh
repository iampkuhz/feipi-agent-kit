#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# validate_package.sh - 统一 diagram package 验证入口
# =============================================================================
# 用法:
#   Fallback 模式:
#     bash scripts/validate_package.sh --diagram <diagram.puml> --out-dir <dir>
#     bash scripts/validate_package.sh --diagram <diagram.puml> --out-dir <dir> --diagram-type fallback
#
#   Typed profile 模式:
#     bash scripts/validate_package.sh --diagram-type <type> --brief <brief.yaml> --diagram <diagram.puml> --out-dir <dir>
#
# 产出物 (在 <out-dir> 中):
#   - diagram.puml           (输入的 diagram 原样复制)
#   - diagram.svg            (仅 render 成功时存在)
#   - validation.json        (验证结果合同)
#   - brief.normalized.yaml  (仅 typed profile，brief 复制)
#
# 退出码:
#   0 - final_status=success (所有校验通过且 render_result=ok)
#   1 - final_status=blocked (任一校验失败)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"

# 默认参数
DIAGRAM_TYPE="fallback"
BRIEF_FILE=""
DIAGRAM_FILE=""
OUT_DIR=""

# 解析参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    --diagram-type)
      DIAGRAM_TYPE="$2"
      shift 2
      ;;
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
  Fallback 模式:
    bash scripts/validate_package.sh --diagram <diagram.puml> --out-dir <dir>
  Typed profile 模式:
    bash scripts/validate_package.sh --diagram-type <type> --brief <brief.yaml> --diagram <diagram.puml> --out-dir <dir>
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
if [[ -z "$DIAGRAM_FILE" || -z "$OUT_DIR" ]]; then
  echo "缺少必需参数：--diagram, --out-dir" >&2
  exit 1
fi

if [[ ! -f "$DIAGRAM_FILE" ]]; then
  echo "diagram 文件不存在：$DIAGRAM_FILE" >&2
  exit 1
fi

# Router 真源：只有注册完成的 profile 才进入 typed 校验，未知图型明确 fallback。
IFS=$'\t' read -r PROFILE PROFILE_VERSION SCHEMA_FILE COVERAGE_MODE LAYOUT_MODE < <(
  python3 - "$LIB_DIR" "$DIAGRAM_TYPE" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from profile_registry import resolve_profile
profile = resolve_profile(sys.argv[2])
print("\t".join([
    str(profile.get("profile", "fallback")),
    str(profile.get("profile_version", "1.0")),
    str(profile.get("brief_schema") or ""),
    str(profile.get("coverage_mode", "basic")),
    str(profile.get("layout_mode", "basic")),
]))
PY
)

# Typed profile 必须有 brief；未注册类型不假装执行 typed 校验。
IS_TYPED=false
if [[ "$PROFILE" != "fallback" ]]; then
  IS_TYPED=true
  if [[ -z "$BRIEF_FILE" ]]; then
    echo "typed profile 缺少必需参数：--brief" >&2
    exit 1
  fi
  if [[ ! -f "$BRIEF_FILE" ]]; then
    echo "brief 文件不存在：$BRIEF_FILE" >&2
    exit 1
  fi
fi

# 创建输出目录
mkdir -p "$OUT_DIR"

# 输出文件路径
DIAGRAM_OUT="$OUT_DIR/diagram.puml"
SVG_OUT="$OUT_DIR/diagram.svg"
VALIDATION_OUT="$OUT_DIR/validation.json"
BRIEF_OUT=""

# 旧 SVG/合同不得被下一轮失败或缺 renderer 的运行误收录。仅清理本包的固定产物。
rm -f "$SVG_OUT" "$VALIDATION_OUT"

# 复制输入文件到输出目录
cp -f "$DIAGRAM_FILE" "$DIAGRAM_OUT"
if [[ "$IS_TYPED" == "true" && -n "$BRIEF_FILE" ]]; then
  BRIEF_OUT="$OUT_DIR/brief.normalized.yaml"
  cp -f "$BRIEF_FILE" "$BRIEF_OUT"

  # module_detail 的父 overview brief 作为只读快照复制进包；后续校验只读副本。
  PARENT_BRIEF_REL="$(python3 - "$BRIEF_FILE" "$LIB_DIR" <<'PY'
import sys
from pathlib import Path, PurePosixPath
sys.path.insert(0, sys.argv[2])
from brief_loader import load_yaml
try:
    source = Path(sys.argv[1]).resolve()
    data = load_yaml(source)
    ref = data.get("parent_component_ref", {}) if isinstance(data, dict) else {}
    value = ref.get("overview_brief_path") if isinstance(ref, dict) else None
    path = PurePosixPath(value) if isinstance(value, str) and value and "\\" not in value else None
    if path and not path.is_absolute() and not any(p in {"", ".", ".."} for p in path.parts):
        candidate = (source.parent / Path(*path.parts)).resolve()
        candidate.relative_to(source.parent.resolve())
        if candidate.is_file():
            print(path.as_posix())
except Exception:
    pass
PY
)"
  if [[ -n "$PARENT_BRIEF_REL" ]]; then
    mkdir -p "$OUT_DIR/$(dirname "$PARENT_BRIEF_REL")"
    cp -f "$(dirname "$BRIEF_FILE")/$PARENT_BRIEF_REL" "$OUT_DIR/$PARENT_BRIEF_REL"
  fi
fi

file_sha256() {
  python3 - "$1" <<'PY'
import hashlib, sys
from pathlib import Path
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
}

DIAGRAM_SNAPSHOT_SHA256="$(file_sha256 "$DIAGRAM_OUT")"
BRIEF_SNAPSHOT_SHA256=""
PARENT_SNAPSHOT_SHA256=""
[[ -n "$BRIEF_OUT" ]] && BRIEF_SNAPSHOT_SHA256="$(file_sha256 "$BRIEF_OUT")"
[[ -n "${PARENT_BRIEF_REL:-}" ]] && PARENT_SNAPSHOT_SHA256="$(file_sha256 "$OUT_DIR/$PARENT_BRIEF_REL")"

snapshot_unchanged() {
  [[ -f "$DIAGRAM_OUT" ]] || return 1
  [[ "$(file_sha256 "$DIAGRAM_OUT")" == "$DIAGRAM_SNAPSHOT_SHA256" ]] || return 1
  if [[ -n "$BRIEF_OUT" ]]; then
    [[ -f "$BRIEF_OUT" ]] || return 1
    [[ "$(file_sha256 "$BRIEF_OUT")" == "$BRIEF_SNAPSHOT_SHA256" ]] || return 1
  fi
  if [[ -n "${PARENT_BRIEF_REL:-}" ]]; then
    [[ -f "$OUT_DIR/$PARENT_BRIEF_REL" ]] || return 1
    [[ "$(file_sha256 "$OUT_DIR/$PARENT_BRIEF_REL")" == "$PARENT_SNAPSHOT_SHA256" ]] || return 1
  fi
}

# =============================================================================
# 用 Python 写 validation.json，避免 shell 拼接 JSON
# =============================================================================
write_json() {
  local brief_path="${8:-}"
  python3 "$LIB_DIR/write_validation.py" \
    --output "$VALIDATION_OUT" \
    --skill-name "feipi-plantuml-generate-diagram" \
    --diagram-type "$DIAGRAM_TYPE" \
    --profile "$PROFILE" \
    --diagram-path "$DIAGRAM_OUT" \
    --svg-path "$SVG_OUT" \
    --brief-path "$brief_path" \
    --brief-check "$1" \
    --coverage-check "$2" \
    --layout-check "$3" \
    --render-result "$4" \
    --render-server "${5:-}" \
    --final-status "$6" \
    --blocked-reason "${7:-}" \
    --package-dir "$OUT_DIR"
}

# =============================================================================
# Step 0: 基础结构校验（所有类型都必须通过）
# =============================================================================
echo "Step 0: Validating basic structure..."

DIAGRAM_CONTENT="$(cat "$DIAGRAM_OUT")"
if ! printf '%s\n' "$DIAGRAM_CONTENT" | grep -qE '^[[:space:]]*@startuml[[:space:]]*$'; then
  write_json "skipped" "skipped" "skipped" "skipped" "" "blocked" "missing_startuml"
  echo "[FAIL] diagram 缺少 @startuml" >&2
  exit 1
fi

if ! printf '%s\n' "$DIAGRAM_CONTENT" | grep -qE '^[[:space:]]*@enduml[[:space:]]*$'; then
  write_json "skipped" "skipped" "skipped" "skipped" "" "blocked" "missing_enduml"
  echo "[FAIL] diagram 缺少 @enduml" >&2
  exit 1
fi

echo "[OK] basic structure passed"

# =============================================================================
# Step 1: Validate Brief (仅 typed profile)
# =============================================================================
BRIEF_CHECK="skipped"
COVERAGE_CHECK="skipped"
LAYOUT_CHECK="skipped"

if [[ "$IS_TYPED" == "true" ]]; then
  echo "Step 1/4: Validating brief..."

  if [[ ! -f "$SCHEMA_FILE" ]]; then
    write_json "failed" "skipped" "skipped" "skipped" "" "blocked" "profile_registry_incomplete" "$BRIEF_OUT"
    echo "[FAIL] 已注册 profile 缺少 schema：$SCHEMA_FILE" >&2
    exit 1
  else
    BRIEF_OUTPUT="$(python3 "$LIB_DIR/validate_brief_cli.py" "$BRIEF_OUT" --schema "$SCHEMA_FILE" --type "$PROFILE" 2>&1)" || {
      write_json "failed" "skipped" "skipped" "skipped" "" "blocked" "brief_validation_failed" "$BRIEF_OUT"
      echo "[FAIL] brief validation failed" >&2
      echo "$BRIEF_OUTPUT" >&2
      exit 1
    }
    BRIEF_CHECK="ok"
    echo "[OK] brief validation passed"
  fi

  # =============================================================================
  # Step 2: Check Coverage (仅 typed profile)
  # =============================================================================
  echo "Step 2/4: Checking coverage..."

  COVERAGE_SCRIPT="$SKILL_DIR/scripts/check_coverage.py"
  if [[ -f "$COVERAGE_SCRIPT" ]]; then
    COVERAGE_OUTPUT="$(python3 "$COVERAGE_SCRIPT" --type "$COVERAGE_MODE" --brief "$BRIEF_OUT" --diagram "$DIAGRAM_OUT" 2>&1)" || {
      write_json "$BRIEF_CHECK" "failed" "skipped" "skipped" "" "blocked" "coverage_validation_failed" "$BRIEF_OUT"
      echo "[FAIL] coverage check failed" >&2
      echo "$COVERAGE_OUTPUT" >&2
      exit 1
    }
    COVERAGE_CHECK="ok"
    echo "[OK] coverage check passed"
  else
    echo "[WARN] check_coverage.py 不存在，跳过覆盖校验" >&2
    COVERAGE_CHECK="skipped"
  fi

  # =============================================================================
  # Step 3: Lint Layout (仅 typed profile)
  # =============================================================================
  echo "Step 3/4: Linting layout..."

  LINT_SCRIPT="$SKILL_DIR/scripts/lint_layout.sh"
  if [[ -f "$LINT_SCRIPT" ]]; then
    LAYOUT_OUTPUT="$(bash "$LINT_SCRIPT" --type "$LAYOUT_MODE" "$DIAGRAM_OUT" "$BRIEF_OUT" 2>&1)" || {
      write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "failed" "skipped" "" "blocked" "layout_validation_failed" "$BRIEF_OUT"
      echo "[FAIL] layout check failed" >&2
      echo "$LAYOUT_OUTPUT" >&2
      exit 1
    }
    LAYOUT_CHECK="ok"
    echo "[OK] layout check passed"
  else
    echo "[WARN] lint_layout.sh 不存在，跳过布局校验" >&2
    LAYOUT_CHECK="skipped"
  fi
fi

# =============================================================================
# Step 4: Check Render
# =============================================================================
echo "Step 4/4: Checking render..."

if ! snapshot_unchanged; then
  write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "skipped" "" "blocked" "package_snapshot_changed" "$BRIEF_OUT"
  echo "[FAIL] 校验期间 package 副本发生变化" >&2
  exit 1
fi

RENDER_SCRIPT="$SCRIPT_DIR/check_render.sh"
if [[ -f "$RENDER_SCRIPT" ]]; then
  RENDER_OUTPUT="$(bash "$RENDER_SCRIPT" "$DIAGRAM_OUT" --svg-output "$SVG_OUT" 2>&1)" || {
    render_exit=$?
    if [[ "$render_exit" -eq 2 ]]; then
      write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "syntax_error" "" "blocked" "render_syntax_error" "$BRIEF_OUT"
      echo "[FAIL] render syntax error" >&2
      echo "$RENDER_OUTPUT" >&2
      exit 1
    elif [[ "$render_exit" -eq 4 ]]; then
      write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "skipped" "" "blocked" "render_server_unavailable" "$BRIEF_OUT"
      echo "[FAIL] no render server available" >&2
      echo "$RENDER_OUTPUT" >&2
      exit 1
    else
      write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "failed" "" "blocked" "render_failed" "$BRIEF_OUT"
      echo "[FAIL] render failed" >&2
      echo "$RENDER_OUTPUT" >&2
      exit 1
    fi
  }

  if echo "$RENDER_OUTPUT" | grep -q "render_result=ok"; then
    RENDER_RESULT="ok"
    RENDER_SERVER="$(echo "$RENDER_OUTPUT" | grep "render_server=" | cut -d'=' -f2 || true)"
    if [[ -z "$RENDER_SERVER" || ! -f "$SVG_OUT" ]] || ! grep -qi '<svg' "$SVG_OUT"; then
      write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "failed" "$RENDER_SERVER" "blocked" "render_evidence_missing" "$BRIEF_OUT"
      echo "[FAIL] renderer 未提供可绑定的 server 或当前 SVG" >&2
      exit 1
    fi
    echo "[OK] render passed, server: $RENDER_SERVER"
  else
    write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "failed" "" "blocked" "render_failed" "$BRIEF_OUT"
    echo "[FAIL] render failed" >&2
    exit 1
  fi
else
  write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "skipped" "" "blocked" "renderer_missing" "$BRIEF_OUT"
  echo "[FAIL] check_render.sh 不存在，不能产出 success" >&2
  exit 1
fi

# =============================================================================
# All checks passed
# =============================================================================
if ! snapshot_unchanged; then
  write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "$RENDER_RESULT" "$RENDER_SERVER" "blocked" "package_snapshot_changed" "$BRIEF_OUT"
  echo "[FAIL] 渲染期间 package 副本发生变化" >&2
  exit 1
fi
write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "$RENDER_RESULT" "$RENDER_SERVER" "success" "" "$BRIEF_OUT"

if ! python3 "$SCRIPT_DIR/verify_package.py" "$OUT_DIR" >/dev/null 2>&1; then
  write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "$RENDER_RESULT" "$RENDER_SERVER" "blocked" "package_verification_failed" "$BRIEF_OUT"
  echo "[FAIL] package v1.1 自校验失败" >&2
  exit 1
fi

echo ""
echo "=== Validation Complete ==="
echo "Package output: $OUT_DIR"
echo "  - diagram.puml"
if [[ "$IS_TYPED" == "true" ]]; then
  echo "  - brief.normalized.yaml"
fi
if [[ "$RENDER_RESULT" == "ok" ]]; then
  echo "  - diagram.svg"
fi
echo "  - validation.json"
echo ""
echo "final_status=success"

exit 0
