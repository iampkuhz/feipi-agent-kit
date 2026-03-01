#!/usr/bin/env bash
set -euo pipefail

# 统一测试入口（供 make test 调用）
# 覆盖范围：自动选档 + 文本提取 + 第一轮请求包 + 第二轮请求包
# 每行用例格式：<url>|<instruction>|<expected_profile>|<run_type>
# - expected_profile: fast|accurate（可空，默认 fast）
# - run_type: selection|extract（可空，默认 extract）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EXTRACT_SCRIPT="$SCRIPT_DIR/extract_video_text.sh"
REQUEST_SCRIPT="$SCRIPT_DIR/render_summary_prompt.sh"
BACKGROUND_REQUEST_SCRIPT="$SCRIPT_DIR/render_background_prompt.sh"
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

if [[ -n "$OUTPUT" ]]; then
  ROOT_DIR="$OUTPUT"
else
  stamp="$(date +%Y%m%d-%H%M%S)"
  ROOT_DIR="$HOME/Downloads/feipi-summarize-video-url-test-$stamp"
fi
mkdir -p "$ROOT_DIR"
LOG_DIR="$ROOT_DIR/logs"
OUT_DIR="$ROOT_DIR/out"
mkdir -p "$LOG_DIR" "$OUT_DIR"

echo "测试配置: $CONFIG"
echo "测试输出: $ROOT_DIR"

TOTAL=0
PASSED=0
FAILED=0

# 依赖检查：存在
TOTAL=$((TOTAL + 1))
log_file="$LOG_DIR/case-$TOTAL-deps-ok.log"
set +e
bash "$EXTRACT_SCRIPT" "https://www.youtube.com/watch?v=abc" "$OUT_DIR/deps" auto --check-deps >"$log_file" 2>&1
code=$?
set -e
if [[ $code -eq 0 ]]; then
  echo "[PASS] case-$TOTAL deps-check-ok"
  PASSED=$((PASSED + 1))
else
  echo "[FAIL] case-$TOTAL deps-check-ok" >&2
  echo "日志: $log_file" >&2
  FAILED=$((FAILED + 1))
fi

# 依赖检查：缺失
TOTAL=$((TOTAL + 1))
log_file="$LOG_DIR/case-$TOTAL-deps-missing.log"
set +e
AGENT_SKILLS_ROOT="$ROOT_DIR/not-exists" bash "$EXTRACT_SCRIPT" "https://www.youtube.com/watch?v=abc" "$OUT_DIR/deps-missing" auto --check-deps >"$log_file" 2>&1
code=$?
set -e
if [[ $code -ne 0 ]]; then
  echo "[PASS] case-$TOTAL deps-check-missing（预期失败）"
  PASSED=$((PASSED + 1))
else
  echo "[FAIL] case-$TOTAL deps-check-missing（预期失败，实际成功）" >&2
  echo "日志: $log_file" >&2
  FAILED=$((FAILED + 1))
fi

while IFS= read -r raw || [[ -n "$raw" ]]; do
  line="${raw%%#*}"
  line="$(echo "$line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  [[ -z "$line" ]] && continue

  IFS='|' read -r URL INSTRUCTION EXPECTED_PROFILE RUN_TYPE <<< "$line"
  URL="$(echo "${URL:-}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  INSTRUCTION="$(echo "${INSTRUCTION:-}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  EXPECTED_PROFILE="$(echo "${EXPECTED_PROFILE:-fast}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  RUN_TYPE="$(echo "${RUN_TYPE:-extract}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"

  if [[ -z "$URL" ]]; then
    TOTAL=$((TOTAL + 1))
    echo "[FAIL] case-$TOTAL URL 为空" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if [[ "$EXPECTED_PROFILE" != "fast" && "$EXPECTED_PROFILE" != "accurate" ]]; then
    TOTAL=$((TOTAL + 1))
    echo "[FAIL] case-$TOTAL expected_profile 非法: $EXPECTED_PROFILE" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if [[ "$RUN_TYPE" != "selection" && "$RUN_TYPE" != "extract" ]]; then
    TOTAL=$((TOTAL + 1))
    echo "[FAIL] case-$TOTAL run_type 非法: $RUN_TYPE" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  TOTAL=$((TOTAL + 1))
  case_id="case-$TOTAL"
  case_dir="$OUT_DIR/$case_id"
  mkdir -p "$case_dir"
  log_file="$LOG_DIR/$case_id.log"

  echo "----"
  echo "开始执行 $case_id"
  echo "URL: $URL"
  echo "instruction: ${INSTRUCTION:-<empty>}"
  echo "expected_profile: $EXPECTED_PROFILE"
  echo "run_type: $RUN_TYPE"

  selection_cmd=(bash "$EXTRACT_SCRIPT" "$URL" "$case_dir/selection" auto --quality auto --check-deps)
  if [[ -n "$INSTRUCTION" ]]; then
    selection_cmd+=(--instruction "$INSTRUCTION")
  fi

  set +e
  selection_output="$("${selection_cmd[@]}" 2>&1)"
  selection_code=$?
  set -e
  printf "[selection]\n%s\n" "$selection_output" > "$log_file"

  if [[ $selection_code -ne 0 ]]; then
    echo "[FAIL] $case_id 选档检查失败" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  selected_profile="$(printf "%s\n" "$selection_output" | sed -n 's/^whisper_profile=//p' | tail -n1)"
  selected_run_dir="$(printf "%s\n" "$selection_output" | sed -n 's/^run_dir=//p' | tail -n1)"
  if [[ "$selected_profile" != "$EXPECTED_PROFILE" ]]; then
    echo "[FAIL] $case_id 选档不符合预期（expect=$EXPECTED_PROFILE actual=$selected_profile）" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if [[ -z "$selected_run_dir" || "$selected_run_dir" != "$case_dir/selection/"* ]]; then
    echo "[FAIL] $case_id 选档阶段 run_dir 异常（actual=$selected_run_dir）" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if [[ "$RUN_TYPE" == "selection" ]]; then
    echo "[PASS] $case_id selection-only profile=$selected_profile"
    PASSED=$((PASSED + 1))
    continue
  fi

  extract_cmd=(bash "$EXTRACT_SCRIPT" "$URL" "$case_dir" auto --quality auto)
  if [[ -n "$INSTRUCTION" ]]; then
    extract_cmd+=(--instruction "$INSTRUCTION")
  fi
  set +e
  extract_output="$("${extract_cmd[@]}" 2>&1)"
  extract_code=$?
  set -e
  printf "[selection]\n%s\n\n[extract]\n%s\n" "$selection_output" "$extract_output" > "$log_file"

  if [[ $extract_code -ne 0 ]]; then
    echo "[FAIL] $case_id 文本提取失败" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  text_path="$(printf "%s\n" "$extract_output" | sed -n 's/^text_path=//p' | tail -n1)"
  run_dir="$(printf "%s\n" "$extract_output" | sed -n 's/^run_dir=//p' | tail -n1)"
  source="$(printf "%s\n" "$extract_output" | sed -n 's/^source=//p' | tail -n1)"
  whisper_profile="$(printf "%s\n" "$extract_output" | sed -n 's/^whisper_profile=//p' | tail -n1)"

  if [[ "$whisper_profile" != "$EXPECTED_PROFILE" ]]; then
    echo "[FAIL] $case_id 提取阶段选档不符合预期（expect=$EXPECTED_PROFILE actual=$whisper_profile）" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if [[ -z "$text_path" || ! -f "$text_path" ]]; then
    echo "[FAIL] $case_id 未产出文本文件" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if [[ "$text_path" == *" "* ]]; then
    echo "[FAIL] $case_id 文本文件路径包含空格（text_path=$text_path）" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if [[ -z "$run_dir" || ! -d "$run_dir" ]]; then
    echo "[FAIL] $case_id 未产出 URL 子目录 run_dir" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if [[ "$run_dir" != "$case_dir/"* || "$run_dir" == "$case_dir" ]]; then
    echo "[FAIL] $case_id run_dir 未落在测试目录子层级（run_dir=$run_dir）" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if [[ "$text_path" != "$run_dir/"* ]]; then
    echo "[FAIL] $case_id text_path 未落在 run_dir 内（text_path=$text_path run_dir=$run_dir）" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '^- \[[0-9]{2}:[0-9]{2}(:[0-9]{2})?\] ' "$text_path"; then
    echo "[FAIL] $case_id 文本不含时间戳" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  set +e
  meta_line="$(yt-dlp --skip-download --no-playlist --print "%(duration)s|%(title)s" "$URL" 2>>"$log_file" | head -n1)"
  meta_code=$?
  set -e

  duration_sec=""
  video_title="未命名视频"
  if [[ $meta_code -eq 0 && -n "$meta_line" ]]; then
    duration_sec="${meta_line%%|*}"
    video_title="${meta_line#*|}"
  fi
  if ! [[ "$duration_sec" =~ ^[0-9]+$ ]]; then
    duration_sec=900
  fi

  request_path="$run_dir/summary_request.md"
  set +e
  request_output="$(bash "$REQUEST_SCRIPT" "$URL" "$video_title" "$duration_sec" "$text_path" > "$request_path" 2>&1)"
  request_code=$?
  set -e
  printf "\n[request]\n%s\n" "$request_output" >> "$log_file"

  if [[ $request_code -ne 0 || ! -f "$request_path" ]]; then
    echo "[FAIL] $case_id 请求包生成失败" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '^## 摘要概述$' "$request_path" || ! rg -q '^## 附件$' "$request_path"; then
    echo "[FAIL] $case_id 请求包缺少输出结构约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '不允许输出“## 核心观点时间线”章节|不允许输出 `## 核心观点时间线` 章节|不要输出 `## 核心观点时间线` 章节' "$request_path"; then
    echo "[FAIL] $case_id 请求包缺少“摘要与时间线合并”约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '\[MM:SS\]|\[HH:MM:SS\]' "$request_path"; then
    echo "[FAIL] $case_id 请求包缺少“时间锚点格式”约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '禁止使用 T\+00:00:00|禁止 T\+00:00:00' "$request_path"; then
    echo "[FAIL] $case_id 请求包缺少“禁止 T+ 时间格式”约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '原始视频：' "$request_path" || ! rg -q '转写文本：' "$request_path"; then
    echo "[FAIL] $case_id 请求包缺少附件输出要求（原始视频 + 转写文本）" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if rg -q '字幕文件：' "$request_path"; then
    echo "[FAIL] $case_id 请求包附件仍包含字幕文件（当前规范不要求该项）" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '<TRANSCRIPT_START>' "$request_path" || ! rg -q '<TRANSCRIPT_END>' "$request_path"; then
    echo "[FAIL] $case_id 请求包未包含文本片段" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '绝对禁止出现以下表达|禁止出现以下模板句' "$request_path"; then
    echo "[FAIL] $case_id 请求包缺少反套话约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  inside_lines="$(awk '
    /<TRANSCRIPT_START>/ {inside=1; next}
    /<TRANSCRIPT_END>/ {inside=0}
    inside {c++}
    END {print c+0}
  ' "$request_path")"
  if [[ -z "$inside_lines" || "$inside_lines" -lt 5 ]]; then
    echo "[FAIL] $case_id 请求包文本内容过少" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  summary_result_path="$run_dir/summary_result.md"
  cat > "$summary_result_path" <<EOF
## 摘要概述
示例：该视频讨论了关税裁决争议及制度影响。

1. [00:05] 最高法院给出关键裁决。
2. [01:48] 讨论“是否构成宪政危机”。

## 附件
- 原始视频：$URL
- 转写文本：$text_path
EOF

  background_request_path="$run_dir/background_request.md"
  set +e
  background_output="$(bash "$BACKGROUND_REQUEST_SCRIPT" "$URL" "$video_title" "$summary_result_path" "$text_path" > "$background_request_path" 2>&1)"
  background_code=$?
  set -e
  printf "\n[background_request]\n%s\n" "$background_output" >> "$log_file"

  if [[ $background_code -ne 0 || ! -f "$background_request_path" ]]; then
    echo "[FAIL] $case_id 第二次请求包生成失败" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '^## 相关影响和背景分析$' "$background_request_path"; then
    echo "[FAIL] $case_id 第二次请求包缺少输出章节约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '<FIRST_ROUND_SUMMARY_START>' "$background_request_path" || ! rg -q '<FIRST_ROUND_SUMMARY_END>' "$background_request_path"; then
    echo "[FAIL] $case_id 第二次请求包未包含第一轮摘要输入" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '不要重复第一轮内容|不得重复第一轮|新增信息价值' "$background_request_path"; then
    echo "[FAIL] $case_id 第二次请求包缺少去重约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '背景知识补充（约2/3）|关键影响（约1/3）|关键术语/人物/机构/事件|时间 \\+ 主体/机构 \\+ 关键动作 \\+ 直接结果 \\+ 含义|触发点 -> 作用机制 -> 受影响对象 -> 可观察结果' "$background_request_path"; then
    echo "[FAIL] $case_id 第二次请求包缺少“背景优先 + 视频关键词 + 关键影响”约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '视频外公开资料' "$background_request_path" || ! rg -q '来源清单' "$background_request_path"; then
    echo "[FAIL] $case_id 第二次请求包缺少“外部背景 + 来源清单”约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '新闻原文|原始文件' "$background_request_path"; then
    echo "[FAIL] $case_id 第二次请求包缺少“新闻原文/原始文件”约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '关键不确定性|后续观察点是否有诉讼' "$background_request_path"; then
    echo "[FAIL] $case_id 第二次请求包缺少“禁止空洞小节”约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  if ! rg -q '禁止使用 T\+00:00:00|禁止使用字幕行号' "$background_request_path"; then
    echo "[FAIL] $case_id 第二次请求包缺少时间锚点简化约束" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  echo "[PASS] $case_id source=$source request=$request_path background=$background_request_path"
  PASSED=$((PASSED + 1))
done < "$CONFIG"

if [[ "$TOTAL" -eq 0 ]]; then
  echo "未执行任何测试用例" >&2
  exit 1
fi

echo "测试汇总: total=$TOTAL pass=$PASSED fail=$FAILED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "测试通过: feipi-summarize-video-url（提取 + 两阶段请求包链路通过）"
