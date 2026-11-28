#!/usr/bin/env bash
set -euo pipefail

# Prompt Contract Lint：检查生成的 prompt 是否包含关键规则。
# 用法：
#   bash scripts/lint_prompt_contract.sh <prompt_file> [--mode strict|structured|review|tutorial|action]

PROMPT_FILE="${1:-}"
MODE="structured"

shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-structured}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

if [[ -z "$PROMPT_FILE" || ! -f "$PROMPT_FILE" ]]; then
  echo "prompt 文件不存在: $PROMPT_FILE" >&2
  exit 1
fi

errors=0

check() {
  local name="$1" pattern="$2"
  if ! grep -qP "$pattern" "$PROMPT_FILE" 2>/dev/null && ! grep -q "$pattern" "$PROMPT_FILE" 2>/dev/null; then
    echo "[FAIL] prompt-contract-$name: prompt 缺少 $name 规则" >&2
    errors=$((errors + 1))
  else
    echo "[PASS] prompt-contract-$name"
  fi
}

# 1. 来源状态要求
check "source-status" "来源状态"

# 2. 无时间戳降级规则
check "no-fake-timestamp" "禁止编造.*时间戳\|禁止伪造.*时间戳\|不含可靠时间戳\|HAS_TIMESTAMPS"

# 3. 外部资料边界
check "external-context-boundary" "不主动扩展背景\|不主动搜索新闻\|禁止.*外部背景\|不输出.*背景"

# 4. 禁止伪造时间戳规则
check "no-fake-timestamp-rule" "禁止编造\|禁止伪造\|禁止.*T\+00:00"

# 5. 摘要风格
check "summary-style" "strict\|structured\|review\|tutorial\|action"

# 6. 视频类型识别
check "video-type" "video_type\|演讲.*访谈.*教程\|speech.*interview.*tutorial"

# 7. 截断披露要求
check "truncation-disclosure" "截断\|truncated"

# 8. 禁止空泛免责
check "anti-empty-disclaimer" "禁止空泛免责\|禁止.*仅供参考\|必须披露.*证据"

# 9. 结构契约
check "structure-contract" "摘要概述"
check "structure-contract-attachments" "## 附件"

if [[ "$errors" -gt 0 ]]; then
  echo "Prompt contract lint 失败: $errors 项检查未通过" >&2
  exit 1
fi

echo "Prompt contract lint 通过: $PROMPT_FILE"
