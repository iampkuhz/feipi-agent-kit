#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATE_SCRIPT="$SCRIPT_DIR/validate.sh"
CHECK_SCRIPT="$SCRIPT_DIR/check_disclosure_format.sh"
DEFAULT_CONFIG="$SKILL_DIR/references/test_cases.txt"

CONFIG=""
OUTPUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$CONFIG" ]]; then
  CONFIG="$DEFAULT_CONFIG"
fi
if [[ ! -f "$CONFIG" ]]; then
  echo "测试配置不存在: $CONFIG" >&2
  exit 1
fi

if [[ -n "$OUTPUT" ]]; then
  ROOT_DIR="$OUTPUT"
else
  TMP_BASE="${TMPDIR:-/tmp}"
  ROOT_DIR="$(mktemp -d "$TMP_BASE/feipi-patent-generate-innovation-disclosure-test.XXXXXX")"
fi
mkdir -p "$ROOT_DIR"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "测试配置: $CONFIG"
echo "测试输出: $ROOT_DIR"

TOTAL=0
PASSED=0
FAILED=0

run_case() {
  local name="$1"
  local expect="$2"
  shift 2
  local log_file="$LOG_DIR/${name}.log"
  local output=""
  local code=0

  TOTAL=$((TOTAL + 1))

  set +e
  output="$("$@" 2>&1)"
  code=$?
  set -e
  printf "%s\n" "$output" > "$log_file"

  if [[ "$expect" == "pass" && "$code" -eq 0 ]]; then
    echo "[PASS] $name"
    PASSED=$((PASSED + 1))
    return
  fi

  if [[ "$expect" == "fail" && "$code" -ne 0 ]]; then
    echo "[PASS] ${name}（按预期失败）"
    PASSED=$((PASSED + 1))
    return
  fi

  echo "[FAIL] $name" >&2
  echo "日志: $log_file" >&2
  FAILED=$((FAILED + 1))
}

run_case "validate-self" pass bash "$VALIDATE_SCRIPT" "$SKILL_DIR"

CASE_INDEX=0
while IFS= read -r raw || [[ -n "$raw" ]]; do
  line="${raw%%#*}"
  line="$(printf '%s' "$line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  [[ -z "$line" ]] && continue

  CASE_INDEX=$((CASE_INDEX + 1))
  doc_path="$line"
  if [[ "$doc_path" != /* ]]; then
    doc_path="$SKILL_DIR/$doc_path"
  fi

  if [[ ! -f "$doc_path" ]]; then
    echo "[FAIL] happy-case-$CASE_INDEX 文件不存在: $doc_path" >&2
    FAILED=$((FAILED + 1))
    TOTAL=$((TOTAL + 1))
    continue
  fi

  run_case "happy-case-$CASE_INDEX" pass bash "$CHECK_SCRIPT" "$doc_path"
done < "$CONFIG"

if [[ "$CASE_INDEX" -eq 0 ]]; then
  echo "未执行任何测试用例" >&2
  exit 1
fi

PLACEHOLDER_DOC="$ROOT_DIR/invalid-placeholder.md"
cp "$SKILL_DIR/assets/proposal_template.md" "$PLACEHOLDER_DOC"
run_case "placeholder-template-fails" fail bash "$CHECK_SCRIPT" "$PLACEHOLDER_DOC"

MISSING_HEADING_DOC="$ROOT_DIR/invalid-missing-heading.md"
rg -v '^### 技术效果总结$' "$SKILL_DIR/references/cases/happy-case-full.md" > "$MISSING_HEADING_DOC"
run_case "missing-heading-fails" fail bash "$CHECK_SCRIPT" "$MISSING_HEADING_DOC"

echo "测试汇总: total=$TOTAL pass=$PASSED fail=$FAILED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "测试通过: feipi-patent-generate-innovation-disclosure"
