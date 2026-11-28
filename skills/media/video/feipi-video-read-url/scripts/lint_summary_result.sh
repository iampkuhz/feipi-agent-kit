#!/usr/bin/env bash
set -euo pipefail

# Summary Result Lint：检查最终摘要结果是否符合契约。
# 用法：
#   bash scripts/lint_summary_result.sh <summary_result_file> [--mode strict|structured|review]

SUMMARY_FILE="${1:-}"
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

if [[ -z "$SUMMARY_FILE" || ! -f "$SUMMARY_FILE" ]]; then
  echo "摘要文件不存在: $SUMMARY_FILE" >&2
  exit 1
fi

errors=0

check() {
  local name="$1" pattern="$2"
  if ! grep -qP "$pattern" "$SUMMARY_FILE" 2>/dev/null && ! grep -q "$pattern" "$SUMMARY_FILE" 2>/dev/null; then
    echo "[FAIL] summary-result-$name: 摘要缺少 $name" >&2
    errors=$((errors + 1))
  else
    echo "[PASS] summary-result-$name"
  fi
}

# 必须检查项
check "has-summary-overview" "^## 摘要概述"
check "has-source-status" "^## 来源状态"
check "has-attachments" "^## 附件"
check "has-video-url" "原始视频.*http\|http.*原始视频\|原始视频："
check "has-transcript-path" "转写文本.*\/\|转写文本："

# 截断披露
check "discloses-truncation" "是否完整.*完整\|是否完整.*已截断\|是否完整.*局部\|是否完整.*分段"

# 外部资料披露
check "discloses-external-context" "是否使用外部资料"

# 条件检查
if grep -q "是否带时间戳.*否" "$SUMMARY_FILE" 2>/dev/null; then
  # 无时间戳：不得出现疑似伪造 [MM:SS]（除了"是否带时间戳"行）
  fake_ts_count=$(grep -cP '\[\d{2}:\d{2}\]' "$SUMMARY_FILE" 2>/dev/null || true)
  if [[ "$fake_ts_count" -gt 0 ]]; then
    echo "[FAIL] no-fake-timestamp: 无时间戳但出现疑似 [MM:SS] 格式" >&2
    errors=$((errors + 1))
  else
    echo "[PASS] no-fake-timestamp"
  fi
fi

# strict 模式检查
if [[ "$MODE" == "strict" ]]; then
  if grep -q "背景补充\|外部背景\|网络资料显示\|相关新闻\|模型分析\|模型评价" "$SUMMARY_FILE" 2>/dev/null; then
    echo "[FAIL] strict-mode-no-external: strict 模式出现外部背景/评价/新闻" >&2
    errors=$((errors + 1))
  else
    echo "[PASS] strict-mode-no-external"
  fi
fi

# review 模式检查
if [[ "$MODE" == "review" ]]; then
  if grep -q "模型分析" "$SUMMARY_FILE" 2>/dev/null; then
    echo "[PASS] review-mode-marked"
  fi
fi

if [[ "$errors" -gt 0 ]]; then
  echo "Summary result lint 失败: $errors 项检查未通过" >&2
  exit 1
fi

echo "Summary result lint 通过: $SUMMARY_FILE"
