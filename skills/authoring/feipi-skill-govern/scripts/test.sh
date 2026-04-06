#!/usr/bin/env bash
set -euo pipefail

# feipi-skill-govern 自测入口。
# 目标：除了校验自身结构，还验证初始化、命名规则、layer 归位和治理模板是否真的可用。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
INIT_SCRIPT="$SCRIPT_DIR/init_skill.sh"
VALIDATE_SCRIPT="$SCRIPT_DIR/validate.sh"

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/feipi-skill-govern-test.XXXXXX")"
REPO_FLAT_DIR="$REPO_ROOT/skills/feipi-video-read-youtube"

cleanup() {
  rm -rf "$TMP_ROOT"
  rm -rf "$REPO_FLAT_DIR"
}
trap cleanup EXIT

TOTAL=0
PASSED=0
FAILED=0

run_case() {
  local case_name="$1"
  local gen_dir=""
  local output=""
  local code=0
  local -a normative_files=(
    "$SKILL_DIR/SKILL.md"
    "$SKILL_DIR/agents/openai.yaml"
    "$SKILL_DIR/scripts/init_skill.sh"
    "$SKILL_DIR/scripts/init_skill_internal.sh"
    "$SKILL_DIR/scripts/quick_validate_internal.sh"
    "$SKILL_DIR/scripts/validate.sh"
    "$SKILL_DIR/references/naming-conventions.md"
    "$SKILL_DIR/references/skill-layering-policy.md"
    "$SKILL_DIR/references/workflow.md"
    "$SKILL_DIR/references/governance-process.md"
    "$SKILL_DIR/references/quality-checklist.md"
    "$SKILL_DIR/templates/SKILL.template.md"
    "$SKILL_DIR/templates/test.template.sh"
  )

  case "$case_name" in
    validate-self)
      bash "$VALIDATE_SCRIPT" "$SKILL_DIR" >/dev/null
      ;;
    init-generated-skill)
      bash "$INIT_SCRIPT" "video-read-youtube" --resources "references,assets" --layer integration --target "$TMP_ROOT/skills" >/dev/null
      gen_dir="$TMP_ROOT/skills/integration/feipi-video-read-youtube"
      [[ -d "$gen_dir" ]]
      [[ -d "$gen_dir/references" ]]
      [[ -d "$gen_dir/assets" ]]
      [[ -x "$gen_dir/scripts/test.sh" ]]
      ! rg -q 'make[[:space:]]+validate[[:space:]]+DIR=|make[[:space:]]+test[[:space:]]+SKILL=' "$gen_dir/SKILL.md"
      ! rg -Fq '{{' "$gen_dir/SKILL.md" "$gen_dir/agents/openai.yaml" "$gen_dir/scripts/test.sh"
      ! rg -Fq '<skill-name>' "$gen_dir/SKILL.md" "$gen_dir/agents/openai.yaml" "$gen_dir/scripts/test.sh"
      bash "$VALIDATE_SCRIPT" "$gen_dir" >/dev/null
      bash "$gen_dir/scripts/test.sh" >/dev/null
      ;;
    reject-v1-name)
      set +e
      output="$(bash "$INIT_SCRIPT" "read-youtube-video" --layer integration --target "$TMP_ROOT/legacy" 2>&1)"
      code=$?
      set -e
      [[ "$code" -ne 0 ]]
      grep -Fq "旧 action-first" <<<"$output"
      ;;
    reject-low-signal-action)
      set +e
      output="$(bash "$INIT_SCRIPT" "dingtalk-web-webhook" --layer integration --target "$TMP_ROOT/bad-action" 2>&1)"
      code=$?
      set -e
      [[ "$code" -ne 0 ]]
      grep -Fq "低语义词" <<<"$output"
      ;;
    validate-detects-placeholder)
      bash "$INIT_SCRIPT" "video-review-transcript" --layer integration --target "$TMP_ROOT/placeholder" >/dev/null
      gen_dir="$TMP_ROOT/placeholder/integration/feipi-video-review-transcript"
      placeholder="$(printf '%s%s%s' '{{' 'SKILL_NAME' '}}')"
      printf '\n%s\n' "$placeholder" >> "$gen_dir/SKILL.md"
      set +e
      output="$(bash "$VALIDATE_SCRIPT" "$gen_dir" 2>&1)"
      code=$?
      set -e
      [[ "$code" -ne 0 ]]
      grep -Fq "未替换模板占位符" <<<"$output"
      ;;
    validate-detects-maintenance-command)
      bash "$INIT_SCRIPT" "video-test-transcript" --layer integration --target "$TMP_ROOT/maint" >/dev/null
      gen_dir="$TMP_ROOT/maint/integration/feipi-video-test-transcript"
      printf '\n## 维护命令\n\n```bash\nmake validate DIR=%s\n```\n' "$gen_dir" >> "$gen_dir/SKILL.md"
      set +e
      output="$(bash "$VALIDATE_SCRIPT" "$gen_dir" 2>&1)"
      code=$?
      set -e
      [[ "$code" -ne 0 ]]
      grep -Fq "repo 维护命令" <<<"$output"
      ;;
    validate-detects-flat-repo-path)
      bash "$INIT_SCRIPT" "video-read-youtube" --layer integration --target "$TMP_ROOT/flat-source" >/dev/null
      gen_dir="$TMP_ROOT/flat-source/integration/feipi-video-read-youtube"
      rm -rf "$REPO_FLAT_DIR"
      cp -R "$gen_dir" "$REPO_FLAT_DIR"
      set +e
      output="$(bash "$VALIDATE_SCRIPT" "$REPO_FLAT_DIR" 2>&1)"
      code=$?
      set -e
      [[ "$code" -ne 0 ]]
      grep -Fq "skills/<layer>/<skill-name>" <<<"$output"
      ;;
    governance-templates-present)
      [[ -f "$SKILL_DIR/assets/governance/step-1-audit.template.md" ]]
      [[ -f "$SKILL_DIR/assets/governance/step-1-5-rename-review.template.md" ]]
      [[ -f "$SKILL_DIR/assets/governance/step-2-execution-checklist.template.md" ]]
      [[ -f "$SKILL_DIR/assets/governance/rename-plan.template.md" ]]
      [[ -f "$SKILL_DIR/assets/governance/governance-report.template.md" ]]
      [[ -f "$SKILL_DIR/assets/governance/anti-pattern.template.md" ]]
      ;;
    legacy-rule-scan)
      ! rg -n 'feipi-<action>-<target\.\.\.>|domain-action-object|prefix-domain-action-object' "${normative_files[@]}"
      ! rg -n 'action 白名单|第二段固定|web：前端与页面|ops：运维与发布|automate：自动化流程' "${normative_files[@]}"
      ;;
    *)
      echo "未知测试项：$case_name" >&2
      return 1
      ;;
  esac
}

for case_name in \
  validate-self \
  init-generated-skill \
  reject-v1-name \
  reject-low-signal-action \
  validate-detects-placeholder \
  validate-detects-maintenance-command \
  validate-detects-flat-repo-path \
  governance-templates-present \
  legacy-rule-scan
do
  TOTAL=$((TOTAL + 1))
  if run_case "$case_name"; then
    echo "[PASS] $case_name"
    PASSED=$((PASSED + 1))
  else
    echo "[FAIL] $case_name" >&2
    FAILED=$((FAILED + 1))
  fi
done

echo "测试汇总：total=$TOTAL pass=$PASSED fail=$FAILED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "测试通过：feipi-skill-govern"
