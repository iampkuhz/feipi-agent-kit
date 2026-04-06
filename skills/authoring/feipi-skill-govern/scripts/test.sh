#!/usr/bin/env bash
set -euo pipefail

# feipi-skill-govern 自测入口。
# 目标：除了校验自身结构，还验证初始化、校验与模板产物是否真的可用。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INIT_SCRIPT="$SCRIPT_DIR/init_skill.sh"
VALIDATE_SCRIPT="$SCRIPT_DIR/validate.sh"

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/feipi-skill-govern-test.XXXXXX")"
cleanup() {
  rm -rf "$TMP_ROOT"
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

  case "$case_name" in
    validate-self)
      bash "$VALIDATE_SCRIPT" "$SKILL_DIR" >/dev/null
      ;;
    init-generated-skill)
      bash "$INIT_SCRIPT" "analyze-demo-skill" "references,assets" "$TMP_ROOT" >/dev/null
      gen_dir="$TMP_ROOT/feipi-analyze-demo-skill"
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
    validate-detects-placeholder)
      bash "$INIT_SCRIPT" "review-demo-skill" "scripts,references" "$TMP_ROOT/placeholder" >/dev/null
      gen_dir="$TMP_ROOT/placeholder/feipi-review-demo-skill"
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
      bash "$INIT_SCRIPT" "test-demo-skill" "scripts,references" "$TMP_ROOT/maint" >/dev/null
      gen_dir="$TMP_ROOT/maint/feipi-test-demo-skill"
      printf '\n## 维护命令\n\n```bash\nmake validate DIR=%s\n```\n' "$gen_dir" >> "$gen_dir/SKILL.md"
      set +e
      output="$(bash "$VALIDATE_SCRIPT" "$gen_dir" 2>&1)"
      code=$?
      set -e
      [[ "$code" -ne 0 ]]
      grep -Fq "repo 维护命令" <<<"$output"
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
  validate-detects-placeholder \
  validate-detects-maintenance-command
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
