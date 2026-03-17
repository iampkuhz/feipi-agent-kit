#!/usr/bin/env bash
set -euo pipefail

# 统一测试入口（供 make test 调用）
# 测试目标：回放 3+ 场景，验证配置审计脚本能正确识别通过/失败。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AUDIT_SCRIPT="$SCRIPT_DIR/audit_openclaw_config.sh"
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

if [[ ! -x "$AUDIT_SCRIPT" ]]; then
  echo "缺少可执行脚本: $AUDIT_SCRIPT" >&2
  exit 1
fi

if [[ -n "$OUTPUT" ]]; then
  ROOT_DIR="$OUTPUT"
else
  stamp="$(date +%Y%m%d-%H%M%S)"
  ROOT_DIR="$HOME/Downloads/feipi-ops-openclaw-config-test-$stamp"
  if ! mkdir -p "$ROOT_DIR" 2>/dev/null; then
    ROOT_DIR="/tmp/feipi-ops-openclaw-config-test-$stamp"
  fi
fi

mkdir -p "$ROOT_DIR/cases" "$ROOT_DIR/logs"

trim() {
  printf '%s' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

build_fixture() {
  local fixture="$1"
  local out="$2"

  case "$fixture" in
    good-env-ref)
      cat >"$out" <<'EOF'
{
  "models": {
    "providers": {
      "qwen": {
        "baseUrl": "${CHAT_API_BASE}",
        "apiKey": "${CHAT_API_KEY}"
      }
    }
  },
  "channels": {
    "telegram": {
      "botToken": "${OPENCLAW_TG_BOT_TOKEN}"
    }
  },
  "agents": {
    "defaults": {
      "workspace": "~/Documents/Obsidian Vault/OpenClaw"
    }
  }
}
EOF
      ;;
    bad-plain-secret)
      cat >"$out" <<'EOF'
{
  "models": {
    "providers": {
      "qwen": {
        "baseUrl": "${CHAT_API_BASE}",
        "apiKey": "sk-plain-text"
      }
    }
  },
  "channels": {
    "telegram": {
      "botToken": "123456:ABCDEF"
    }
  }
}
EOF
      ;;
    bad-legacy-path)
      cat >"$out" <<'EOF'
{
  "agents": {
    "defaults": {
      "workspace": "/Users/zhehan/第二大脑/OpenClaw"
    }
  }
}
EOF
      ;;
    good-extra-dirs)
      cat >"$out" <<'EOF'
{
  "skills": {
    "load": {
      "extraDirs": [
        "~/Documents/tools/llm/skills/agent-skills/skills",
        "/Users/zhehan/custom-skills"
      ]
    }
  },
  "agents": {
    "defaults": {
      "workspace": "~/Documents/Obsidian Vault/OpenClaw"
    }
  }
}
EOF
      ;;
    *)
      echo "未知 fixture: $fixture" >&2
      return 1
      ;;
  esac
}

TOTAL=0
PASSED=0
FAILED=0

run_case() {
  local case_id="$1"
  local expect="$2"
  local fixture="$3"
  local assert_text="$4"

  local cfg="$ROOT_DIR/cases/${case_id}.json"
  local log="$ROOT_DIR/logs/${case_id}.log"
  build_fixture "$fixture" "$cfg"

  local output=""
  local code=0
  set +e
  output="$(bash "$AUDIT_SCRIPT" --config "$cfg" 2>&1)"
  code=$?
  set -e

  {
    echo "case_id=$case_id"
    echo "expect=$expect"
    echo "fixture=$fixture"
    echo "code=$code"
    echo "output_start"
    printf '%s\n' "$output"
    echo "output_end"
  } > "$log"

  if [[ "$expect" == "ok" ]]; then
    if [[ "$code" -eq 0 ]] && [[ -z "$assert_text" || "$output" == *"$assert_text"* ]]; then
      echo "[PASS] $case_id"
      PASSED=$((PASSED + 1))
    else
      echo "[FAIL] ${case_id}（预期通过，实际失败）" >&2
      echo "日志: $log" >&2
      FAILED=$((FAILED + 1))
    fi
    return
  fi

  if [[ "$expect" == "fail" ]]; then
    if [[ "$code" -ne 0 ]] && [[ -z "$assert_text" || "$output" == *"$assert_text"* ]]; then
      echo "[PASS] ${case_id}（预期失败）"
      PASSED=$((PASSED + 1))
    else
      echo "[FAIL] ${case_id}（预期失败，实际通过）" >&2
      echo "日志: $log" >&2
      FAILED=$((FAILED + 1))
    fi
    return
  fi

  echo "[FAIL] ${case_id}（未知 expect: $expect）" >&2
  FAILED=$((FAILED + 1))
}

while IFS= read -r raw || [[ -n "$raw" ]]; do
  line="${raw%%#*}"
  line="$(trim "$line")"
  [[ -z "$line" ]] && continue

  IFS='|' read -r case_id expect fixture assert_text extra <<< "$line"
  case_id="$(trim "${case_id:-}")"
  expect="$(trim "${expect:-}")"
  fixture="$(trim "${fixture:-}")"
  assert_text="$(trim "${assert_text:-}")"
  extra="$(trim "${extra:-}")"

  TOTAL=$((TOTAL + 1))

  if [[ -n "$extra" || -z "$case_id" || -z "$expect" || -z "$fixture" ]]; then
    echo "[FAIL] case-$TOTAL 用例格式错误: $line" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  run_case "$case_id" "$expect" "$fixture" "$assert_text"
done < "$CONFIG"

echo "测试汇总: total=$TOTAL, passed=$PASSED, failed=$FAILED"
echo "测试输出: $ROOT_DIR"

if [[ "$TOTAL" -eq 0 || "$FAILED" -gt 0 ]]; then
  exit 1
fi
