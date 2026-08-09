#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATE_SKILL="$SCRIPT_DIR/validate.sh"
VALIDATE_PACKAGE="$SCRIPT_DIR/validate_disclosure_package.sh"
CHECK_DRAFT="$SCRIPT_DIR/check_disclosure_format.sh"
FIXTURE_BUILDER="$SCRIPT_DIR/tests/generate_package.py"
DEFAULT_CONFIG="$SKILL_DIR/references/test_cases.txt"

CONFIG="$DEFAULT_CONFIG"
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
    -h|--help)
      echo "用法: bash scripts/test.sh [--config <test_cases.txt>] [--output <dir>]"
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$CONFIG" ]]; then
  echo "测试配置不存在：$CONFIG" >&2
  exit 1
fi
if [[ -n "$OUTPUT" ]]; then
  ROOT_DIR="$OUTPUT"
  mkdir -p "$ROOT_DIR"
else
  ROOT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/feipi-patent-validation-test.XXXXXX")"
fi
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

TOTAL=0
PASSED=0
FAILED=0

run_command() {
  local name="$1"
  local expected_exit="$2"
  local expected_rule="$3"
  shift 3
  local log_file="$LOG_DIR/$name.log"
  local command_exit=0
  TOTAL=$((TOTAL + 1))
  set +e
  "$@" >"$log_file" 2>&1
  command_exit=$?
  set -e
  if [[ "$command_exit" -ne "$expected_exit" ]]; then
    echo "[FAIL] ${name}：退出码=${command_exit}，期望=${expected_exit}（日志：${log_file}）" >&2
    FAILED=$((FAILED + 1))
    return
  fi
  if [[ -n "$expected_rule" ]] && ! rg -q "(^|[\" ]+)${expected_rule}([\" ]+|$)" "$log_file"; then
    echo "[FAIL] ${name}：未命中规则 ${expected_rule}（日志：${log_file}）" >&2
    FAILED=$((FAILED + 1))
    return
  fi
  echo "[PASS] ${name}"
  PASSED=$((PASSED + 1))
}

run_package_case() {
  local name="$1"
  local variant="$2"
  local expected_exit="$3"
  local expected_rule="$4"
  local package_dir="$ROOT_DIR/packages/$name"
  python3 "$FIXTURE_BUILDER" "$package_dir" --variant "$variant"
  run_command "$name" "$expected_exit" "$expected_rule" bash "$VALIDATE_PACKAGE" "$package_dir"
}

run_command "validate-self" 0 "" bash "$VALIDATE_SKILL" "$SKILL_DIR"

DRAFT_INDEX=0
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  config_line="${raw_line%%#*}"
  config_line="$(printf '%s' "$config_line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  [[ -z "$config_line" ]] && continue
  DRAFT_INDEX=$((DRAFT_INDEX + 1))
  draft_path="$config_line"
  if [[ "$draft_path" != /* ]]; then
    draft_path="$SKILL_DIR/$draft_path"
  fi
  run_command "draft-$DRAFT_INDEX" 0 "PKG-900" bash "$CHECK_DRAFT" "$draft_path"
done < "$CONFIG"
if [[ "$DRAFT_INDEX" -eq 0 ]]; then
  echo "[FAIL] 测试配置没有草稿用例" >&2
  FAILED=$((FAILED + 1))
fi

# 完整正例与两个 forward test。
run_package_case "happy-package" "happy" 0 ""
run_package_case "forward-complex-deployment" "complex_deployment" 0 ""
run_package_case "forward-pending-retrieval" "pending_retrieval" 0 "CMP-003"

# pending 不能伪装成成功：机器规则通过，但必须返回 review_required=2。
run_package_case "semantic-review-pending" "semantic_pending" 2 "REV-001"
run_package_case "visual-review-pending" "visual_pending" 2 "REV-004"

# 定点负例：每例动态生成，既断言退出码，也断言稳定 rule ID。
run_package_case "deployment-required" "deployment_missing" 1 "FIG-003"
run_package_case "deployment-trigger-omitted" "deployment_trigger_omitted" 1 "BND-006"
run_package_case "keyword-generic" "keyword_generic" 1 "KWD-004"
run_package_case "top-level-implementation" "implementation_top" 1 "BND-003"
run_package_case "top-level-table-field" "implementation_table_field" 1 "BND-003"
run_package_case "top-level-alias-not-visible" "implementation_alias_only" 0 ""
run_package_case "legacy-mr-numbering" "flow_mr" 1 "FLOW-004"
run_package_case "flow-number-jump" "flow_jump" 1 "FLOW-002"
run_package_case "flow-missing-parent" "flow_missing_parent" 1 "FLOW-003"
run_package_case "flow-long-label" "flow_long_label" 1 "FLOW-005"
run_package_case "flow-document-mismatch" "flow_text_mismatch" 1 "FLOW-006"
run_package_case "innovation-field-missing" "innovation_missing" 1 "INV-003"
run_package_case "innovation-effect-not-bijective" "effect_mismatch" 1 "EFF-003"
run_package_case "effect-causality-missing" "effect_missing" 1 "EFF-002"
run_package_case "effect-verified-without-evidence" "effect_verified_unbound" 1 "EFF-005"
run_package_case "source-anchor-missing" "source_invalid" 1 "EVD-003"
run_package_case "schema-alias-drift" "schema_alias" 1 "SCH-001"
run_package_case "competitor-evidence-incomplete" "competitor_bare" 1 "CMP-002"
run_package_case "competitor-pending-bare-claim" "competitor_pending_bare" 1 "CMP-004"
run_package_case "document-structure-missing" "document_structure_missing" 1 "DOC-002"
run_command "draft-structure-missing" 1 "PKG-904" bash "$CHECK_DRAFT" "$ROOT_DIR/packages/document-structure-missing/disclosure.md"
run_package_case "document-title-mismatch" "document_title_mismatch" 1 "DOC-001"
run_package_case "diagram-package-blocked" "diagram_blocked" 1 "FIG-006"
run_package_case "diagram-check-failed" "diagram_check_failed" 1 "FIG-006"
run_package_case "diagram-metrics-forged" "diagram_metrics_forged" 1 "PKG-010"
run_package_case "diagram-hash-tampered" "hash_tamper" 1 "PKG-008"
run_package_case "diagram-artifact-path-missing" "artifact_path_missing" 1 "PKG-008"
run_package_case "diagram-non-utf8" "non_utf8_puml" 1 "PKG-006"
run_command "diagram-non-utf8-report" 0 "" test -f "$ROOT_DIR/packages/diagram-non-utf8/disclosure-validation.json"
run_package_case "diagram-symlink-escape" "artifact_symlink_escape" 1 "PKG-006"
run_package_case "visual-review-stale" "visual_stale" 1 "REV-005"
run_package_case "diagram-path-traversal" "path_traversal" 1 "PKG-005"

echo "测试汇总：total=$TOTAL pass=$PASSED fail=$FAILED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi
echo "测试通过：feipi-patent-generate-innovation-disclosure"
