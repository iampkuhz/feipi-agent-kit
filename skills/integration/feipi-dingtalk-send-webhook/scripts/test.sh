#!/usr/bin/env bash
set -euo pipefail

# feipi-dingtalk-send-webhook 统一测试入口。
# 目标：做离线自测，覆盖目录有效性、文本/Markdown 脚本的基础报错路径。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATE_SCRIPT="$SCRIPT_DIR/validate.sh"
CONFIG="$SKILL_DIR/references/test_cases.txt"
MOCK_SERVER="$SCRIPT_DIR/tests/mock_dingtalk_server.py"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/feipi-dingtalk-send-webhook-test.XXXXXX")"

cleanup() {
  if [[ -n "${MOCK_PID:-}" ]]; then
    kill "$MOCK_PID" >/dev/null 2>&1 || true
    wait "$MOCK_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if [[ ! -f "$CONFIG" ]]; then
  echo "测试配置不存在: $CONFIG" >&2
  exit 1
fi

TOTAL=0
PASSED=0
FAILED=0

ensure_mock_server() {
  if [[ -n "${MOCK_PORT:-}" && -n "${MOCK_PID:-}" ]] && kill -0 "$MOCK_PID" >/dev/null 2>&1; then
    return 0
  fi

  MOCK_PORT="$(python3 - <<'PY'
import socket

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
)"
  MOCK_RECORD_FILE="$TMP_DIR/mock-request.json"
  : > "$MOCK_RECORD_FILE"

  python3 "$MOCK_SERVER" --port "$MOCK_PORT" --record-file "$MOCK_RECORD_FILE" >"$TMP_DIR/mock-server.log" 2>&1 &
  MOCK_PID=$!

  for _ in $(seq 1 30); do
    if curl -sS "http://127.0.0.1:$MOCK_PORT/healthz" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.1
  done

  echo "mock webhook 服务启动失败" >&2
  return 1
}

run_case() {
  local case_name="$1"
  local output=""
  local code=0

  case "$case_name" in
    validate-self)
      bash "$VALIDATE_SCRIPT" "$SKILL_DIR" >/dev/null
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
    text-send-success)
      ensure_mock_server
      output="$(DINGTALK_TEST_URL="http://127.0.0.1:$MOCK_PORT/robot/send?access_token=dummy" \
        bash "$SKILL_DIR/scripts/send_dingtalk.sh" DINGTALK_TEST_URL "部署完成：服务已上线" 2>&1)"
      grep -Fq "✓ 消息发送成功" <<<"$output"
      python3 - "$MOCK_RECORD_FILE" <<'PY'
import json
import sys
from pathlib import Path

record = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert record["payload"]["msgtype"] == "text"
assert record["payload"]["text"]["content"] == "部署完成：服务已上线"
PY
      ;;
    markdown-send-success)
      ensure_mock_server
      output="$(DINGTALK_TEST_URL="http://127.0.0.1:$MOCK_PORT/robot/send?access_token=dummy" \
        bash "$SKILL_DIR/scripts/send_dingtalk_md.sh" DINGTALK_TEST_URL "巡检结果" $'| 服务 | 状态 |\n| --- | --- |\n| api | 成功 |\n<font color=\"red\">告警</font>' 2>&1)"
      grep -Fq "✓ 消息发送成功" <<<"$output"
      grep -Fq "已删除钉钉不支持的 Markdown 语法" <<<"$output"
      python3 - "$MOCK_RECORD_FILE" <<'PY'
import json
import sys
from pathlib import Path

record = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert record["payload"]["msgtype"] == "markdown"
assert record["payload"]["markdown"]["title"] == "巡检结果"
text = record["payload"]["markdown"]["text"]
assert "告警" in text
assert "|" not in text
assert "<font" not in text
PY
      ;;
    markdown-send-with-sign)
      ensure_mock_server
      output="$(DINGTALK_TEST_URL="http://127.0.0.1:$MOCK_PORT/robot/send?access_token=dummy" \
        DINGTALK_TEST_SECRET="secret-value" \
        bash "$SKILL_DIR/scripts/send_dingtalk_md.sh" DINGTALK_TEST_URL "部署通知" "#### 部署完成" DINGTALK_TEST_SECRET 2>&1)"
      grep -Fq "✓ 消息发送成功" <<<"$output"
      python3 - "$MOCK_RECORD_FILE" <<'PY'
import json
import sys
from pathlib import Path

record = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
query = record["query"]
assert "timestamp" in query
assert "sign" in query
PY
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

echo "测试通过: feipi-dingtalk-send-webhook"
