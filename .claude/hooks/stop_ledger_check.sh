#!/usr/bin/env bash
# Stop — 任务结束前账本格式检查
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LEDGER="$REPO_ROOT/tmp/task-ledger.md"
FAIL=0

# 1. 账本文件存在
if [[ ! -f "$LEDGER" ]]; then
  hook_log "WARN" "账本文件不存在: $LEDGER"
  FAIL=1
fi

# 2. 表格结构存在（至少一行任务表）
if ! grep -q '|.*ID.*任务.*状态' "$LEDGER" 2>/dev/null; then
  hook_log "WARN" "账本缺少任务表头"
  FAIL=1
fi

# 3. 检查当前任务是否标记为 done
CURRENT_TASK="$(grep '当前任务编号：' "$LEDGER" | sed 's/.*当前任务编号：//' | grep -oE '[0-9]+' | head -1 || true)"
if [[ -n "$CURRENT_TASK" ]]; then
  padded=$(printf "%03d" "$((10#$CURRENT_TASK))")
  if ! grep -q "| $padded |.*| done |" "$LEDGER" 2>/dev/null; then
    hook_log "WARN" "当前任务 #${padded} 状态不是 done"
    FAIL=1
  fi
fi

# 4. 结果文件存在性
if [[ -n "$CURRENT_TASK" ]]; then
  padded=$(printf "%03d" "$((10#$CURRENT_TASK))")
  RESULT="$REPO_ROOT/tmp/task-results/${padded}-*.md"
  if ! ls $RESULT >/dev/null 2>&1; then
    hook_log "WARN" "缺少结果文件: ${padded}-*.md"
    FAIL=1
  fi
fi

if [[ "$HOOK_DRY_RUN" == "1" ]]; then
  hook_log "DRY-RUN" "账本检查完成: $([[ $FAIL -eq 0 ]] && echo '通过' || echo '有告警')"
  exit $EXIT_WARN
fi

# Stop hook 永远不阻塞，只告警
[[ $FAIL -ne 0 ]] && exit $EXIT_WARN
exit $EXIT_OK
