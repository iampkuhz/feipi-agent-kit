#!/usr/bin/env bash
# scripts/repo/check_agent_checkpoint.sh
# 检查 tmp/ 任务状态与 task-results 的一致性
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
REPO_ROOT="$(find_git_root)"

warns=0
blocks=0

# --- 前置检查：tmp/ 目录存在性 ---
if [[ ! -d "$REPO_ROOT/tmp" ]]; then
  log_skip "tmp/" "directory not found"
  exit_with_status "$warns" "$blocks"
fi

LEDGER="$REPO_ROOT/tmp/task-ledger.md"
RESULTS_DIR="$REPO_ROOT/tmp/task-results"

if [[ ! -f "$LEDGER" ]]; then
  log_block "task-ledger.md" "not found"
  ((blocks++))
  exit_with_status "$warns" "$blocks"
fi

# --- 1. 读取当前任务编号 ---
current_task="$(grep '当前任务编号：' "$LEDGER" | sed 's/.*当前任务编号：//' | grep -oE '[0-9]+' | head -1 || true)"
if [[ -z "$current_task" ]]; then
  log_warn "task-ledger.md" "cannot parse current task number"
  ((warns++))
else
  padded=$(printf "%03d" "$((10#$current_task))")
  # 检查当前任务结果文件是否存在（任意以 编号 开头的 .md）
  if ls "$RESULTS_DIR/${padded}-"*.md >/dev/null 2>&1; then
    log_pass "task-results/${padded}-*.md" "result file exists for current task #${padded}"
  else
    log_block "task-results/" "missing result file for current task #${padded}"
    ((blocks++))
  fi
fi

# --- 2. 状态一致性：遍历 done 任务 ---
while IFS= read -r line; do
  # 解析表格行: | 001 | 初始化任务账本 | done | 00 | ...
  task_id=$(echo "$line" | sed -E 's/^\|[[:space:]]*([0-9]+)[[:space:]]*\|.*/\1/' | grep -E '^[0-9]+$' | head -1 || true)
  status=$(echo "$line" | awk -F'|' '{print $4}' | tr -d ' ' || true)
  [[ -z "$task_id" ]] && continue
  [[ "$status" != "done" ]] && continue

  padded=$(printf "%03d" "$((10#$task_id))")
  # 检查是否存在对应的结果文件
  found=false
  if ls "$RESULTS_DIR/${padded}-"*.md >/dev/null 2>&1; then
    found=true
  fi
  if ! $found; then
    log_warn "task-ledger.md" "task #${padded} is done but no result file found"
    ((warns++))
  else
    log_pass "task-ledger.md" "task #${padded} has result file"
  fi
done < <(grep -E '^\|[[:space:]]*[0-9]+[[:space:]]*\|' "$LEDGER" 2>/dev/null)

# --- 3. 孤立结果文件检测 ---
if [[ -d "$RESULTS_DIR" ]]; then
  for result_file in "$RESULTS_DIR"/*.md; do
    [[ -f "$result_file" ]] || continue
    base=$(basename "$result_file")
    # 提取前缀编号（如 001-ledger-bootstrap.md -> 001）
    prefix="${base%%-*}"
    if ! grep -q "| ${prefix} " "$LEDGER" 2>/dev/null; then
      log_warn "$base" "orphan result file (not referenced in task-ledger.md)"
      ((warns++))
    fi
  done
fi

# --- 4. checkpoint 最新性 ---
last_checkpoint_date="$(grep -oE '\*\*20[0-9]{2}-[0-9]{2}-[0-9]{2}\*' "$LEDGER" | tail -1 | tr -d '*' || true)"
if [[ -n "$last_checkpoint_date" ]]; then
  today=$(date +%Y-%m-%d)
  last_ts=$(date -d "$last_checkpoint_date" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$last_checkpoint_date" +%s 2>/dev/null || echo 0)
  today_ts=$(date -d "$today" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$today" +%s 2>/dev/null || echo 0)
  if [[ "$last_ts" -gt 0 && "$today_ts" -gt 0 ]]; then
    diff_days=$(( (today_ts - last_ts) / 86400 ))
    if [[ "$diff_days" -gt 1 ]]; then
      log_info "task-ledger.md" "last checkpoint is ${diff_days} days old (${last_checkpoint_date})"
      ((warns++))
    fi
  fi
fi

exit_with_status "$warns" "$blocks"
