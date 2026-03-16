#!/usr/bin/env bash
set -euo pipefail

# feipi-gen-skills 自测入口。
# 目标：校验当前 skill 的结构有效，且“版本递增/同日合并/changelog 极简”规则保持一致。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
DEFAULT_CONFIG="$SKILL_DIR/references/test_cases.txt"

CONFIG="${1:-$DEFAULT_CONFIG}"
if [[ ! -f "$CONFIG" ]]; then
  echo "测试配置不存在: $CONFIG" >&2
  exit 1
fi

TOTAL=0
PASSED=0
FAILED=0

run_case() {
  local case_name="$1"

  case "$case_name" in
    validate-self)
      "$REPO_ROOT/feipi-scripts/repo/quick_validate.sh" "$SKILL_DIR" >/dev/null
      ;;
    check-version-rule)
      rg -Fq "当天首次修改时递增" "$SKILL_DIR/SKILL.md"
      rg -Fq "当天首次修改时递增" "$SKILL_DIR/agents/openai.yaml"
      rg -Fq "当天首次修改时递增" "$SKILL_DIR/references/repo-constraints.md"
      ;;
    check-changelog-rule)
      rg -Fq "极致精简（强制）" "$SKILL_DIR/references/changelog-policy.md"
      rg -Fq "同一天同一个 skill 只允许 **1 条**记录" "$SKILL_DIR/references/changelog-policy.md"
      rg -Fq "建议不超过 **18 个汉字**" "$SKILL_DIR/references/changelog-policy.md"
      ;;
    *)
      echo "未知测试项: $case_name" >&2
      return 1
      ;;
  esac
}

while IFS= read -r raw || [[ -n "$raw" ]]; do
  line="${raw%%#*}"
  line="$(printf '%s' "$line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  [[ -z "$line" ]] && continue

  TOTAL=$((TOTAL + 1))
  if run_case "$line"; then
    echo "[PASS] $line"
    PASSED=$((PASSED + 1))
  else
    echo "[FAIL] $line" >&2
    FAILED=$((FAILED + 1))
  fi
done < "$CONFIG"

if [[ "$TOTAL" -eq 0 ]]; then
  echo "未执行任何测试项" >&2
  exit 1
fi

echo "测试汇总: total=$TOTAL pass=$PASSED fail=$FAILED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "测试通过: feipi-gen-skills"
