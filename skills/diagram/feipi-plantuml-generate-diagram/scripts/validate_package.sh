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
#   renderer 地址来自批次 preflight 的 renderer_url：
#     bash scripts/validate_package.sh ... --server-url http://127.0.0.1:8199/plantuml
#   复用完全未变且已通过当前合同校验的图包:
#     bash scripts/validate_package.sh ... --reuse-valid-package
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
REUSE_VALID_PACKAGE=false
RENDER_CONTRACT_VERSION="3"
SERVER_URL="auto"
MAX_RENDER_ATTEMPTS=2

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
    --reuse-valid-package)
      REUSE_VALID_PACKAGE=true
      shift
      ;;
    --server-url)
      SERVER_URL="$2"
      shift 2
      ;;
    -h|--help)
      cat <<'USAGE'
用法:
  Fallback 模式:
    bash scripts/validate_package.sh --diagram <diagram.puml> --out-dir <dir>
  Typed profile 模式:
    bash scripts/validate_package.sh --diagram-type <type> --brief <brief.yaml> --diagram <diagram.puml> --out-dir <dir>
  使用批次预检冻结的 renderer:
    在上述命令末尾增加 --server-url <loopback-url>
  复用未变图包:
    在上述命令末尾增加 --reuse-valid-package
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

monotonic_ns() {
  python3 -c 'import time; print(time.monotonic_ns())'
}

duration_ms() {
  python3 - "$1" "${2:-$(monotonic_ns)}" <<'PY'
import sys
print(round(max(0, int(sys.argv[2]) - int(sys.argv[1])) / 1_000_000, 3))
PY
}

file_sha256() {
  python3 - "$1" <<'PY'
import hashlib, sys
from pathlib import Path
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
}

VALIDATION_START_NS="$(monotonic_ns)"
RENDER_DURATION_MS="0"
RENDER_HTTP_REQUESTS=0
RENDER_ROUNDS=0
PACKAGE_VALIDATION_RUNS=1
PACKAGE_VERIFIER_RUNS=0
CACHE_HITS=0
PREVIOUS_RENDER_ATTEMPTS=0
BRIEF_VALIDATION_REUSED=false

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

update_last_run_observation() {
  local cache_hit="$1"
  local render_duration_ms="${2:-$RENDER_DURATION_MS}"
  local total_duration_ms=""
  local static_validation_duration_ms=""
  total_duration_ms="$(duration_ms "$VALIDATION_START_NS")"
  static_validation_duration_ms="$(python3 - "$total_duration_ms" "$render_duration_ms" <<'PY'
import sys
print(round(max(0.0, float(sys.argv[1]) - float(sys.argv[2])), 3))
PY
)"
  python3 - "$VALIDATION_OUT" "$total_duration_ms" "$render_duration_ms" "$static_validation_duration_ms" "$cache_hit" \
    "$RENDER_HTTP_REQUESTS" "$RENDER_ROUNDS" "$PACKAGE_VALIDATION_RUNS" "$PACKAGE_VERIFIER_RUNS" "$CACHE_HITS" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
timings = {
    "total_ms": round(float(sys.argv[2]), 3),
    "render_ms": round(float(sys.argv[3]), 3),
    "static_validation_ms": round(float(sys.argv[4]), 3),
}
data["last_run_timings"] = {**timings, "cache_hit": sys.argv[5] == "true"}
last_run_counters = {
    "render_http_requests": int(sys.argv[6]),
    "render_rounds": int(sys.argv[7]),
    "package_validation_runs": int(sys.argv[8]),
    "package_verifier_runs": int(sys.argv[9]),
    "cache_hits": int(sys.argv[10]),
}
data["last_run_counters"] = last_run_counters
if sys.argv[5] != "true":
    data["timings"] = timings
    data["counters"] = last_run_counters
temporary = path.with_suffix(path.suffix + ".tmp")
temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
temporary.replace(path)
PY
}

# 显式复用只接受“输入、profile、渲染合同均未变化”的完整成功图包。
# verify_package.py 会先重算包内路径、hash、metrics 和 SVG 合同；任一项失效即回退全量校验。
if [[ "$REUSE_VALID_PACKAGE" == "true" && -f "$VALIDATION_OUT" && -f "$SVG_OUT" ]]; then
  # 先做廉价输入身份检查；输入已变化时不启动完整 package verifier。
  if python3 - "$VALIDATION_OUT" "$DIAGRAM_FILE" "$BRIEF_FILE" "$DIAGRAM_TYPE" "$PROFILE" "$PROFILE_VERSION" "$RENDER_CONTRACT_VERSION" "$LIB_DIR" <<'PY'
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

validation_path, diagram_path, brief_path, diagram_type, profile, profile_version, render_contract_version, lib_dir = sys.argv[1:]
sys.path.insert(0, lib_dir)
from brief_loader import load_yaml


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


data = json.loads(Path(validation_path).read_text(encoding="utf-8"))
if data.get("final_status") != "success" or data.get("render_result") != "ok":
    raise SystemExit(1)
if data.get("diagram_type") != diagram_type or data.get("profile") != profile:
    raise SystemExit(1)
if str(data.get("profile_version")) != profile_version:
    raise SystemExit(1)
if str(data.get("render_contract_version")) != render_contract_version:
    raise SystemExit(1)
if sha256(Path(diagram_path)) != data.get("puml_sha256"):
    raise SystemExit(1)

if profile != "fallback":
    source_brief = Path(brief_path)
    if not source_brief.is_file() or sha256(source_brief) != data.get("brief_sha256"):
        raise SystemExit(1)
    brief = load_yaml(source_brief)
    ref = brief.get("parent_component_ref", {}) if isinstance(brief, dict) else {}
    relative = ref.get("overview_brief_path") if isinstance(ref, dict) else None
    if isinstance(relative, str) and relative:
        rel = PurePosixPath(relative)
        if rel.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in rel.parts):
            raise SystemExit(1)
        parent = (source_brief.resolve().parent / Path(*rel.parts)).resolve()
        parent.relative_to(source_brief.resolve().parent)
        if not parent.is_file() or sha256(parent) != data.get("parent_brief_sha256"):
            raise SystemExit(1)
elif data.get("brief_sha256"):
    raise SystemExit(1)
PY
  then
    PACKAGE_VERIFIER_RUNS=$((PACKAGE_VERIFIER_RUNS + 1))
    if python3 "$SCRIPT_DIR/verify_package.py" "$OUT_DIR" >/dev/null 2>&1; then
      CACHE_HITS=1
      update_last_run_observation "true" "0"
      echo "cache_hit=true"
      echo "final_status=success"
      exit 0
    fi
  fi
fi

# 失败合同是下一轮定点修复的唯一入口：相同 brief/profile 下，未修改图、
# 非可修复失败或已经耗尽两次 renderer 调用时都禁止重复执行。
if [[ -f "$VALIDATION_OUT" ]]; then
  CURRENT_DIAGRAM_SHA256="$(file_sha256 "$DIAGRAM_FILE")"
  CURRENT_BRIEF_SHA256=""
  [[ -n "$BRIEF_FILE" && -f "$BRIEF_FILE" ]] && CURRENT_BRIEF_SHA256="$(file_sha256 "$BRIEF_FILE")"
  IFS='|' read -r PREV_STATUS PREV_PROFILE PREV_PROFILE_VERSION PREV_RENDER_CONTRACT \
    PREV_BRIEF_SHA256 PREV_PUML_SHA256 PREV_ATTEMPT PREV_REPAIRABLE PREV_FAILURE_CLASS < <(
    python3 - "$VALIDATION_OUT" <<'PY'
import json
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    data = {}
values = [
    data.get("final_status", ""),
    data.get("profile", ""),
    str(data.get("profile_version", "")),
    str(data.get("render_contract_version", "")),
    data.get("brief_sha256", ""),
    data.get("puml_sha256", ""),
    str(data.get("attempt_index", 0)),
    "true" if data.get("repairable") is True else "false",
    data.get("failure_class", ""),
]
print("|".join(values))
PY
  )
  if [[ "$PREV_STATUS" == "blocked" \
    && "$PREV_PROFILE" == "$PROFILE" \
    && "$PREV_PROFILE_VERSION" == "$PROFILE_VERSION" \
    && "$PREV_RENDER_CONTRACT" == "$RENDER_CONTRACT_VERSION" \
    && "$PREV_BRIEF_SHA256" == "$CURRENT_BRIEF_SHA256" ]]; then
    [[ "$PREV_ATTEMPT" =~ ^[0-9]+$ ]] || PREV_ATTEMPT=0
    if [[ "$PREV_REPAIRABLE" != "true" ]]; then
      echo "上次失败不可自动修复：$PREV_FAILURE_CLASS；请处理 blocker 或更换输出目录" >&2
      exit 1
    fi
    if [[ "$PREV_PUML_SHA256" == "$CURRENT_DIAGRAM_SHA256" ]]; then
      echo "失败图未发生变化，禁止重复校验和渲染" >&2
      exit 1
    fi
    if [[ "$PREV_ATTEMPT" -ge "$MAX_RENDER_ATTEMPTS" ]]; then
      echo "已达到每图最多 $MAX_RENDER_ATTEMPTS 次 renderer 调用，禁止继续" >&2
      exit 1
    fi
    PREVIOUS_RENDER_ATTEMPTS="$PREV_ATTEMPT"
  fi
fi

# 旧 SVG/合同不得被下一轮失败或缺 renderer 的运行误收录。仅清理本包的固定产物。
rm -f "$SVG_OUT" "$VALIDATION_OUT"

# 按文件身份判断：兼容相对/绝对路径、符号链接与硬链接；同文件仍参与后续快照校验。
copy_snapshot() {
  if [[ ! "$1" -ef "$2" ]]; then
    cp -f "$1" "$2"
  fi
}

copy_snapshot "$DIAGRAM_FILE" "$DIAGRAM_OUT"
if [[ "$IS_TYPED" == "true" && -n "$BRIEF_FILE" ]]; then
  BRIEF_OUT="$OUT_DIR/brief.normalized.yaml"
  copy_snapshot "$BRIEF_FILE" "$BRIEF_OUT"

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
    copy_snapshot "$(dirname "$BRIEF_FILE")/$PARENT_BRIEF_REL" "$OUT_DIR/$PARENT_BRIEF_REL"
  fi
fi

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

BRIEF_LOCK_OUT="$OUT_DIR/.brief-lock.json"
BRIEF_RULESET_SHA256=""
if [[ "$IS_TYPED" == "true" ]]; then
  BRIEF_RULESET_SHA256="$(python3 - "$SCHEMA_FILE" "$LIB_DIR/profile_registry.py" \
    "$LIB_DIR/brief_loader.py" "$LIB_DIR/validate_brief_cli.py" "$LIB_DIR/profile_validators.py" "$LIB_DIR/mindmap.py" <<'PY'
import hashlib
import sys
from pathlib import Path

digest = hashlib.sha256()
for value in sys.argv[1:]:
    path = Path(value)
    digest.update(path.name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\n")
print(digest.hexdigest())
PY
)"
fi

brief_lock_matches() {
  [[ "$IS_TYPED" == "true" && -f "$BRIEF_LOCK_OUT" ]] || return 1
  python3 - "$BRIEF_LOCK_OUT" "$BRIEF_SNAPSHOT_SHA256" "$PROFILE" "$PROFILE_VERSION" "$BRIEF_RULESET_SHA256" <<'PY'
import json
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)
expected = {
    "brief_sha256": sys.argv[2],
    "profile": sys.argv[3],
    "profile_version": sys.argv[4],
    "brief_ruleset_sha256": sys.argv[5],
    "brief_check": "ok",
}
raise SystemExit(0 if all(data.get(key) == value for key, value in expected.items()) else 1)
PY
}

write_brief_lock() {
  python3 - "$BRIEF_LOCK_OUT" "$BRIEF_SNAPSHOT_SHA256" "$PROFILE" "$PROFILE_VERSION" "$BRIEF_RULESET_SHA256" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
value = {
    "brief_sha256": sys.argv[2],
    "profile": sys.argv[3],
    "profile_version": sys.argv[4],
    "brief_ruleset_sha256": sys.argv[5],
    "brief_check": "ok",
}
temporary = path.with_suffix(path.suffix + ".tmp")
temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
temporary.replace(path)
PY
}

# =============================================================================
# 用 Python 写 validation.json，避免 shell 拼接 JSON
# =============================================================================
write_json() {
  local brief_path="${8:-}"
  local issue_text="${9:-${7:-}}"
  local attempt_index=$((PREVIOUS_RENDER_ATTEMPTS + RENDER_ROUNDS))
  local total_duration_ms=""
  local static_validation_duration_ms=""
  total_duration_ms="$(duration_ms "$VALIDATION_START_NS")"
  static_validation_duration_ms="$(python3 - "$total_duration_ms" "$RENDER_DURATION_MS" <<'PY'
import sys
print(round(max(0.0, float(sys.argv[1]) - float(sys.argv[2])), 3))
PY
)"
  python3 "$LIB_DIR/write_validation.py" \
    --output "$VALIDATION_OUT" \
    --skill-name "feipi-plantuml-generate-diagram" \
    --render-contract-version "$RENDER_CONTRACT_VERSION" \
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
    --issue-text "$issue_text" \
    --attempt-index "$attempt_index" \
    --max-render-attempts "$MAX_RENDER_ATTEMPTS" \
    --brief-validation-reused "$BRIEF_VALIDATION_REUSED" \
    --package-dir "$OUT_DIR" \
    --total-duration-ms "$total_duration_ms" \
    --render-duration-ms "$RENDER_DURATION_MS" \
    --static-validation-duration-ms "$static_validation_duration_ms" \
    --render-http-requests "$RENDER_HTTP_REQUESTS" \
    --render-rounds "$RENDER_ROUNDS" \
    --package-validation-runs "$PACKAGE_VALIDATION_RUNS" \
    --package-verifier-runs "$PACKAGE_VERIFIER_RUNS" \
    --cache-hits "$CACHE_HITS"
}

read_render_request_count() {
  local output="$1"
  local value=""
  value="$(printf '%s\n' "$output" | awk -F= '/^render_http_requests=[0-9]+$/ {count=$2} END {if (count != "") print count}')"
  if [[ "$value" =~ ^[0-9]+$ ]]; then
    RENDER_HTTP_REQUESTS="$value"
  fi
}

# =============================================================================
# Step 0: 基础结构校验（所有类型都必须通过）
# =============================================================================
echo "Step 0: Validating basic structure..."

DIAGRAM_CONTENT="$(cat "$DIAGRAM_OUT")"
START_MARKER="startuml"
END_MARKER="enduml"
if [[ "$DIAGRAM_TYPE" == "mindmap" ]]; then
  START_MARKER="startmindmap"
  END_MARKER="endmindmap"
fi
for marker in "$START_MARKER" "$END_MARKER"; do
  if ! printf '%s\n' "$DIAGRAM_CONTENT" | grep -qE "^[[:space:]]*@${marker}[[:space:]]*$"; then
    write_json "skipped" "skipped" "skipped" "skipped" "" "blocked" "missing_${marker}" "" "diagram 缺少 @${marker}"
    echo "[FAIL] diagram 缺少 @${marker}" >&2
    exit 1
  fi
done

echo "[OK] basic structure passed"

# =============================================================================
# Step 1: Validate Brief (仅 typed profile)
# =============================================================================
BRIEF_CHECK="skipped"
COVERAGE_CHECK="skipped"
LAYOUT_CHECK="skipped"

if [[ "$IS_TYPED" == "true" ]]; then
  echo "Step 1/4: Validating brief..."

  if brief_lock_matches; then
    BRIEF_CHECK="ok"
    BRIEF_VALIDATION_REUSED=true
    echo "[OK] frozen brief validation reused"
  elif [[ ! -f "$SCHEMA_FILE" ]]; then
    write_json "failed" "skipped" "skipped" "skipped" "" "blocked" "profile_registry_incomplete" "$BRIEF_OUT"
    echo "[FAIL] 已注册 profile 缺少 schema：$SCHEMA_FILE" >&2
    exit 1
  else
    BRIEF_OUTPUT="$(python3 "$LIB_DIR/validate_brief_cli.py" "$BRIEF_OUT" --schema "$SCHEMA_FILE" --type "$PROFILE" 2>&1)" || {
      write_json "failed" "skipped" "skipped" "skipped" "" "blocked" "brief_validation_failed" "$BRIEF_OUT" "$BRIEF_OUTPUT"
      echo "[FAIL] brief validation failed" >&2
      echo "$BRIEF_OUTPUT" >&2
      exit 1
    }
    BRIEF_CHECK="ok"
    write_brief_lock
    echo "[OK] brief validation passed"
  fi

  # =============================================================================
  # Step 2: Check Coverage (仅 typed profile)
  # =============================================================================
  echo "Step 2/4: Checking coverage..."

  COVERAGE_SCRIPT="$SKILL_DIR/scripts/check_coverage.py"
  if [[ -f "$COVERAGE_SCRIPT" ]]; then
    COVERAGE_OUTPUT="$(python3 "$COVERAGE_SCRIPT" --type "$COVERAGE_MODE" --brief "$BRIEF_OUT" --diagram "$DIAGRAM_OUT" 2>&1)" || {
      write_json "$BRIEF_CHECK" "failed" "skipped" "skipped" "" "blocked" "coverage_validation_failed" "$BRIEF_OUT" "$COVERAGE_OUTPUT"
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
      write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "failed" "skipped" "" "blocked" "layout_validation_failed" "$BRIEF_OUT" "$LAYOUT_OUTPUT"
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
  if [[ $((PREVIOUS_RENDER_ATTEMPTS + 1)) -gt "$MAX_RENDER_ATTEMPTS" ]]; then
    write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "skipped" "" "blocked" "attempt_limit_exceeded" "$BRIEF_OUT"
    echo "[FAIL] render attempt limit exceeded" >&2
    exit 1
  fi
  RENDER_ROUNDS=$((RENDER_ROUNDS + 1))
  RENDER_START_NS="$(monotonic_ns)"
  RENDER_OUTPUT="$(bash "$RENDER_SCRIPT" "$DIAGRAM_OUT" --svg-output "$SVG_OUT" --server-url "$SERVER_URL" 2>&1)" || {
    render_exit=$?
    RENDER_DURATION_MS="$(duration_ms "$RENDER_START_NS")"
    read_render_request_count "$RENDER_OUTPUT"
    if [[ "$render_exit" -eq 2 ]]; then
      write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "syntax_error" "" "blocked" "render_syntax_error" "$BRIEF_OUT" "$RENDER_OUTPUT"
      echo "[FAIL] render syntax error" >&2
      echo "$RENDER_OUTPUT" >&2
      exit 1
    elif [[ "$render_exit" -eq 4 ]]; then
      write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "skipped" "" "blocked" "render_server_unavailable" "$BRIEF_OUT" "$RENDER_OUTPUT"
      echo "[FAIL] no render server available" >&2
      echo "$RENDER_OUTPUT" >&2
      exit 1
    else
      write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "failed" "" "blocked" "render_failed" "$BRIEF_OUT" "$RENDER_OUTPUT"
      echo "[FAIL] render failed" >&2
      echo "$RENDER_OUTPUT" >&2
      exit 1
    fi
  }
  RENDER_DURATION_MS="$(duration_ms "$RENDER_START_NS")"
  read_render_request_count "$RENDER_OUTPUT"

  if echo "$RENDER_OUTPUT" | grep -q "render_result=ok"; then
    RENDER_RESULT="ok"
    RENDER_SERVER="$(echo "$RENDER_OUTPUT" | grep "render_server=" | cut -d'=' -f2 || true)"
    if [[ -z "$RENDER_SERVER" || ! -f "$SVG_OUT" ]] \
      || ! python3 "$LIB_DIR/svg_validation.py" "$SVG_OUT" >/dev/null 2>&1; then
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
PACKAGE_VERIFIER_RUNS=$((PACKAGE_VERIFIER_RUNS + 1))
write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "$RENDER_RESULT" "$RENDER_SERVER" "success" "" "$BRIEF_OUT"

if ! python3 "$SCRIPT_DIR/verify_package.py" "$OUT_DIR" >/dev/null 2>&1; then
  write_json "$BRIEF_CHECK" "$COVERAGE_CHECK" "$LAYOUT_CHECK" "$RENDER_RESULT" "$RENDER_SERVER" "blocked" "package_verification_failed" "$BRIEF_OUT"
  echo "[FAIL] package v1.2 自校验失败" >&2
  exit 1
fi

# 将内置 verifier 的实际耗时与调用次数纳入本次观测；这些字段不参与工件 hash。
update_last_run_observation "false"

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
