#!/usr/bin/env bash
set -euo pipefail

# feipi-automate-dingtalk-webhook 统一测试入口。
# 目标：做离线自测，覆盖目录有效性、文本/Markdown 脚本的基础报错路径。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
CONFIG="$SKILL_DIR/references/test_cases.txt"

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
    text-missing-env)
      set +e
      output="$(env -u DINGTALK_TEST_URL bash "$SKILL_DIR/scripts/send_dingtalk.sh" DINGTALK_TEST_URL "hello" 2>&1)"
      code=$?
      set -e
      [[ "$code" -ne 0 ]]
      grep -Fq "环境变量 DINGTALK_TEST_URL 未设置或为空" <<<"$output"
      ;;
    markdown-missing-env)
      set +e
      output="$(env -u DINGTALK_TEST_URL bash "$SKILL_DIR/scripts/send_dingtalk_md.sh" DINGTALK_TEST_URL "title" "body" 2>&1)"
      code=$?
      set -e
      [[ "$code" -ne 0 ]]
      grep -Fq "环境变量 DINGTALK_TEST_URL 未设置或为空" <<<"$output"
      ;;
    markdown-missing-secret)
      set +e
      output="$(env -u DINGTALK_TEST_SECRET DINGTALK_TEST_URL='https://oapi.dingtalk.com/robot/send?access_token=dummy' bash "$SKILL_DIR/scripts/send_dingtalk_md.sh" DINGTALK_TEST_URL "title" "body" DINGTALK_TEST_SECRET 2>&1)"
      code=$?
      set -e
      [[ "$code" -ne 0 ]]
      grep -Fq "加签密钥环境变量 DINGTALK_TEST_SECRET 未设置或为空" <<<"$output"
      ;;
    markdown-unsupported-strip)
      output="$(printf '%s\n' '| 服务 | 状态 |' '| --- | --- |' '| api | 成功 |' '| worker | 失败 |' | python3 "$SKILL_DIR/scripts/normalize_dingtalk_markdown.py")"
      [[ -z "$output" ]]
      output="$(printf '%s\n' '```bash' 'echo hello' '```' '<font color=\"red\">告警</font>' '---' | python3 "$SKILL_DIR/scripts/normalize_dingtalk_markdown.py")"
      grep -Fq "echo hello" <<<"$output"
      grep -Fq "告警" <<<"$output"
      ! grep -Fq '```' <<<"$output"
      ! grep -Fq '<font' <<<"$output"
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

echo "测试通过: feipi-automate-dingtalk-webhook"
