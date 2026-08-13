#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATE_SKILL="$SCRIPT_DIR/validate.sh"
VALIDATE_PACKAGE="$SCRIPT_DIR/validate_disclosure_package.sh"
CHECK_DRAFT="$SCRIPT_DIR/check_disclosure_format.sh"
FIXTURE_BUILDER="$SCRIPT_DIR/tests/generate_package.py"
DEFAULT_CONFIG="$SKILL_DIR/references/test_cases.txt"
WORKSPACE_DIR_NAME="disclosure-workspace"

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
  local disclosure_dir="$ROOT_DIR/packages/$name"
  python3 "$FIXTURE_BUILDER" "$disclosure_dir" --variant "$variant"
  run_command "$name" "$expected_exit" "$expected_rule" bash "$VALIDATE_PACKAGE" "$disclosure_dir"
}

check_confirmation_contract() {
  rg -q '^### 阶段 2：提交写作思路并等待确认$' "$SKILL_DIR/SKILL.md" \
    && rg -q '只有收到用户明确的确认.*才进入阶段 3' "$SKILL_DIR/SKILL.md" \
    && rg -q '先整理技术事实.*提交写作思路供我确认；收到确认后再生成' "$SKILL_DIR/agents/openai.yaml"
}

check_happy_audience_contract() {
  local disclosure_dir="$ROOT_DIR/packages/happy-package"
  ! rg -q '(SF|IE|EM|C|BD|SYS|PB)[1-9][0-9]*|expected_observable|verified|public_fact|reasonable_inference|pending_retrieval|evidence_found|searched_no_usable_evidence|来源依据' \
    "$disclosure_dir/disclosure.md" \
    && rg -q '^## 内部追溯附录（禁止对外）$' "$disclosure_dir/$WORKSPACE_DIR_NAME/disclosure-internal.md" \
    && rg -q '^- I1｜已实现依据：SF2｜拟扩展：IE1｜效果：T1$' "$disclosure_dir/$WORKSPACE_DIR_NAME/disclosure-internal.md" \
    && rg -q '^- I2｜已实现依据：SF3｜拟扩展：无｜效果：T2$' "$disclosure_dir/$WORKSPACE_DIR_NAME/disclosure-internal.md"
}

check_output_layout_contract() {
  rg -q '^└── disclosure-workspace/$' "$SKILL_DIR/SKILL.md" \
    && rg -q '\*\*/disclosure-workspace/' "$SKILL_DIR/SKILL.md" \
    && ! test -e "$ROOT_DIR/packages/happy-package/$WORKSPACE_DIR_NAME/disclosure.md" \
    && test -f "$ROOT_DIR/packages/happy-package/disclosure.md" \
    && test -f "$ROOT_DIR/packages/happy-package/$WORKSPACE_DIR_NAME/disclosure-manifest.json" \
    && test -f "$ROOT_DIR/packages/happy-package/$WORKSPACE_DIR_NAME/disclosure-validation.json" \
    && ! test -e "$ROOT_DIR/packages/happy-package/disclosure-validation.json"
}

check_competitor_research_contract() {
  rg -q '无论用户是否提供竞品材料，都使用公开资料检索' "$SKILL_DIR/SKILL.md" \
    && rg -Fq '"status": {"enum": ["evidence_found", "searched_no_usable_evidence"]}' "$SKILL_DIR/assets/disclosure-manifest.schema.json" \
    && rg -q '"search_records"' "$SKILL_DIR/assets/disclosure-manifest.schema.json" \
    && rg -q '主动检索行业竞品' "$SKILL_DIR/agents/openai.yaml" \
    && ! rg -q '^或：待检索' "$SKILL_DIR/assets/proposal_template.md" \
    && ! rg -q '"status": "pending_retrieval"' \
      "$SKILL_DIR/assets/disclosure-manifest.template.json" \
      "$SKILL_DIR/references/cases/happy-package/$WORKSPACE_DIR_NAME/disclosure-manifest.json"
}

run_command "validate-self" 0 "" bash "$VALIDATE_SKILL" "$SKILL_DIR"
run_command "confirmation-gate-contract" 0 "" check_confirmation_contract
run_command "competitor-research-contract" 0 "" check_competitor_research_contract

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
run_command "happy-audience-contract" 0 "" check_happy_audience_contract
run_command "output-layout-contract" 0 "" check_output_layout_contract
run_package_case "legacy-flat-layout" "legacy_flat_layout" 0 "PKG-013"
run_package_case "ambiguous-layout" "ambiguous_layout" 1 "PKG-012"
run_package_case "workspace-duplicate-public" "workspace_duplicate_public" 1 "PKG-012"
run_package_case "workspace-root-internal-leak" "workspace_root_internal_leak" 1 "PKG-012"
run_package_case "workspace-symlink-escape" "workspace_symlink_escape" 1 "PKG-012"
run_package_case "forward-complex-deployment" "complex_deployment" 0 ""
run_package_case "forward-searched-no-evidence" "searched_no_evidence" 0 ""

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
run_package_case "implementation-basis-missing" "implementation_basis_missing" 1 "INV-007"
run_package_case "implementation-source-invalid" "implementation_source_invalid" 1 "INV-007"
run_package_case "implementation-internal-identifier" "implementation_internal_identifier" 1 "INV-007"
run_package_case "implementation-internal-identifier-casefold" "implementation_internal_identifier_casefold" 1 "INV-007"
run_package_case "implementation-fields-quoted" "implementation_fields_quoted" 1 "INV-007"
run_package_case "implementation-field-before-label" "implementation_field_before_label" 1 "INV-007"
run_package_case "protection-extension-field-missing" "protection_extension_field_missing" 1 "INV-007"
run_package_case "protection-extension-id-missing" "protection_extension_id_missing" 1 "INV-007"
run_package_case "protection-extension-unknown-id" "protection_extension_unknown_id" 1 "INV-007"
run_package_case "protection-extension-duplicate-id" "protection_extension_duplicate_id" 1 "INV-007"
run_package_case "protection-extension-orphan-ledger" "protection_extension_orphan_ledger" 1 "INV-007"
run_package_case "protection-extension-ledger-missing" "protection_extension_ledger_missing" 1 "INV-007"
run_package_case "protection-internal-identifier-casefold" "protection_internal_identifier_casefold" 1 "INV-007"
run_package_case "protection-extension-unhighlighted" "protection_extension_unhighlighted" 1 "INV-007"
run_package_case "protection-extension-body-unquoted" "protection_extension_body_unquoted" 1 "INV-007"
run_package_case "external-unexpected-no-extension-marker" "external_unexpected_no_extension_marker" 1 "DOC-004"
run_package_case "alternative-extension-unhighlighted" "alternative_extension_unhighlighted" 1 "INV-008"
run_package_case "innovation-comparison-missing" "innovation_comparison_missing" 1 "INV-003"
run_package_case "innovation-value-missing" "innovation_value_missing" 1 "INV-003"
run_package_case "innovation-value-generic" "innovation_value_generic" 1 "INV-006"
run_package_case "innovation-value-scattered" "innovation_value_scattered" 1 "INV-006"
run_package_case "innovation-effect-link-mismatch" "innovation_effect_link_mismatch" 1 "EFF-003"
run_package_case "innovation-effect-not-bijective" "effect_mismatch" 1 "EFF-003"
run_package_case "effect-causality-missing" "effect_missing" 1 "EFF-002"
run_package_case "effect-verified-without-evidence" "effect_verified_unbound" 1 "EFF-005"
run_package_case "source-anchor-missing" "source_invalid" 1 "EVD-003"
run_package_case "multiline-source-fact" "multiline_source_fact" 0 ""
run_package_case "schema-alias-drift" "schema_alias" 1 "SCH-001"
run_package_case "competitor-evidence-incomplete" "competitor_bare" 1 "CMP-002"
run_package_case "competitor-evidence-unlinked" "competitor_evidence_unlinked" 1 "CMP-002"
run_package_case "competitor-search-missing" "competitor_search_missing" 1 "CMP-003"
run_package_case "competitor-search-focus-missing" "competitor_search_focus_missing" 1 "CMP-003"
run_package_case "competitor-search-duplicate" "competitor_search_duplicate" 1 "CMP-003"
run_package_case "competitor-search-zero-width-duplicate" "competitor_search_zero_width_duplicate" 1 "CMP-003"
run_package_case "competitor-search-unrelated" "competitor_search_unrelated" 1 "CMP-005"
run_package_case "competitor-basis-stuffed-unrelated" "competitor_basis_stuffed_unrelated" 1 "CMP-005"
run_package_case "competitor-basis-html-entity" "competitor_basis_html_entity" 1 "CMP-005"
run_package_case "competitor-basis-self-poisoned" "competitor_basis_self_poisoned" 1 "INP-004"
run_package_case "competitor-basis-zero-width" "competitor_basis_zero_width" 1 "INP-002"
run_package_case "competitor-search-locator-invalid" "competitor_search_locator_invalid" 1 "CMP-003"
run_package_case "competitor-summary-placeholder" "competitor_summary_placeholder" 1 "CMP-003"
run_package_case "competitor-summary-english-placeholder" "competitor_summary_english_placeholder" 1 "CMP-003"
run_package_case "competitor-summary-zero-width" "competitor_summary_zero_width" 1 "CMP-003"
run_package_case "competitor-no-evidence-named-claim" "competitor_no_evidence_named_claim" 1 "CMP-003"
run_package_case "competitor-fake-url" "competitor_fake_url" 1 "CMP-003"
run_package_case "competitor-placeholder" "competitor_placeholder" 1 "CMP-004"
run_package_case "competitor-no-evidence-bare-claim" "competitor_no_evidence_bare" 1 "CMP-004"
run_package_case "competitor-legacy-pending" "competitor_legacy_pending" 1 "CMP-001"
run_package_case "document-structure-missing" "document_structure_missing" 1 "DOC-002"
run_command "draft-structure-missing" 1 "PKG-904" bash "$CHECK_DRAFT" "$ROOT_DIR/packages/document-structure-missing/disclosure.md"
run_package_case "document-title-mismatch" "document_title_mismatch" 1 "DOC-001"
run_package_case "internal-document-missing" "internal_missing" 1 "PKG-011"
run_package_case "internal-appendix-missing" "internal_appendix_missing" 1 "DOC-005"
run_package_case "public-body-drift" "public_body_drift" 1 "DOC-005"
run_package_case "internal-trace-mapping-missing" "internal_trace_mapping_missing" 1 "DOC-005"
run_package_case "internal-appendix-commented" "internal_appendix_commented" 1 "DOC-005"
run_package_case "internal-extra-trace" "internal_extra_trace" 1 "DOC-005"
run_package_case "public-trace-ids-leak" "public_trace_ids_leak" 1 "DOC-004"
run_command "draft-public-trace-ids-leak" 1 "DOC-004" bash "$CHECK_DRAFT" "$ROOT_DIR/packages/public-trace-ids-leak/disclosure.md"
run_package_case "public-source-locator-leak" "public_source_locator_leak" 1 "DOC-004"
run_package_case "public-term-original-leak" "public_term_original_leak" 1 "DOC-004"
run_package_case "public-raw-enum-leak" "public_raw_enum_leak" 1 "DOC-004"
run_package_case "public-html-comment-leak" "public_html_comment_leak" 1 "DOC-004"
run_package_case "public-entity-leak" "public_entity_leak" 1 "DOC-004"
run_package_case "public-encoded-comment-leak" "public_encoded_comment_leak" 1 "DOC-004"
run_package_case "puml-trace-leak" "puml_trace_leak" 1 "FIG-010"
run_package_case "puml-extension-leak" "puml_extension_leak" 1 "FIG-010"
run_package_case "svg-term-leak" "svg_term_leak" 1 "FIG-010"
run_package_case "diagram-scope-review-missing" "diagram_scope_review_missing" 1 "FIG-010"
run_package_case "diagram-package-blocked" "diagram_blocked" 1 "FIG-006"
run_package_case "diagram-check-failed" "diagram_check_failed" 1 "FIG-006"
run_package_case "diagram-metrics-forged" "diagram_metrics_forged" 1 "PKG-010"
run_package_case "diagram-hash-tampered" "hash_tamper" 1 "PKG-008"
run_package_case "diagram-artifact-path-missing" "artifact_path_missing" 1 "PKG-008"
run_package_case "diagram-non-utf8" "non_utf8_puml" 1 "PKG-006"
run_command "diagram-non-utf8-report" 0 "" test -f "$ROOT_DIR/packages/diagram-non-utf8/$WORKSPACE_DIR_NAME/disclosure-validation.json"
run_package_case "diagram-symlink-escape" "artifact_symlink_escape" 1 "PKG-006"
run_package_case "visual-review-stale" "visual_stale" 1 "REV-005"
run_package_case "diagram-path-traversal" "path_traversal" 1 "PKG-005"

echo "测试汇总：total=$TOTAL pass=$PASSED fail=$FAILED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi
echo "测试通过：feipi-patent-generate-innovation-disclosure"
