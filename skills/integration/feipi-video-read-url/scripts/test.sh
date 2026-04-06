#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATE_SCRIPT="$SCRIPT_DIR/validate.sh"
INSTALL_SCRIPT="$SCRIPT_DIR/install_deps.sh"
DOWNLOAD_SCRIPT="$SCRIPT_DIR/download_video.sh"
EXTRACT_SCRIPT="$SCRIPT_DIR/extract_video_text.sh"
SUMMARY_SCRIPT="$SCRIPT_DIR/render_summary_prompt.sh"
BACKGROUND_SCRIPT="$SCRIPT_DIR/render_background_prompt.sh"
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
  mkdir -p "$ROOT_DIR"
else
  ROOT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/feipi-video-read-url-test.XXXXXX")"
fi

LOG_DIR="$ROOT_DIR/logs"
OUT_DIR="$ROOT_DIR/out"
mkdir -p "$LOG_DIR" "$OUT_DIR"

echo "测试配置: $CONFIG"
echo "测试输出: $ROOT_DIR"

TOTAL=0
PASSED=0
FAILED=0

run_simple_case() {
  local name="$1"
  local expect="$2"
  shift 2
  local log_file="$LOG_DIR/${name}.log"
  local code

  TOTAL=$((TOTAL + 1))
  set +e
  "$@" >"$log_file" 2>&1
  code=$?
  set -e

  if [[ "$expect" == "pass" && "$code" -eq 0 ]]; then
    echo "[PASS] $name"
    PASSED=$((PASSED + 1))
    return
  fi

  if [[ "$expect" == "fail" && "$code" -ne 0 ]]; then
    echo "[PASS] ${name}（按预期失败）"
    PASSED=$((PASSED + 1))
    return
  fi

  echo "[FAIL] $name" >&2
  echo "日志: $log_file" >&2
  FAILED=$((FAILED + 1))
}

run_simple_case "validate-self" pass bash "$VALIDATE_SCRIPT" "$SKILL_DIR"
run_simple_case "deps-check" pass bash "$INSTALL_SCRIPT" --check
run_simple_case "unsupported-source-fails" fail bash "$DOWNLOAD_SCRIPT" "https://vimeo.com/123456" "$OUT_DIR/unsupported" dryrun

while IFS= read -r raw || [[ -n "$raw" ]]; do
  line="${raw%%#*}"
  line="$(printf '%s' "$line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  [[ -z "$line" ]] && continue

  IFS='|' read -r KIND URL ARG3 ARG4 ARG5 <<< "$line"
  KIND="$(printf '%s' "${KIND:-}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  URL="$(printf '%s' "${URL:-}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  ARG3="$(printf '%s' "${ARG3:-}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  ARG4="$(printf '%s' "${ARG4:-}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  ARG5="$(printf '%s' "${ARG5:-}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"

  TOTAL=$((TOTAL + 1))
  case_id="case-$TOTAL"
  case_dir="$OUT_DIR/$case_id"
  log_file="$LOG_DIR/$case_id.log"
  mkdir -p "$case_dir"

  case "$KIND" in
    download)
      MODE="${ARG3:-dryrun}"
      WHISPER_PROFILE="${ARG4:-auto}"
      set +e
      bash "$DOWNLOAD_SCRIPT" "$URL" "$case_dir" "$MODE" "$WHISPER_PROFILE" >"$log_file" 2>&1
      code=$?
      set -e

      if [[ "$code" -ne 0 ]]; then
        echo "[FAIL] $case_id download-$MODE" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
        continue
      fi

      case "$MODE" in
        dryrun)
          if find "$case_dir" -type f \( -name '*.mp4' -o -name '*.mp3' -o -name '*.txt' \) | grep -q .; then
            echo "[FAIL] $case_id dryrun 不应生成媒体或文本文件" >&2
            echo "日志: $log_file" >&2
            FAILED=$((FAILED + 1))
            continue
          fi
          ;;
        video)
          if ! find "$case_dir" -type f -name '*.mp4' | grep -q .; then
            echo "[FAIL] $case_id video 未生成 mp4" >&2
            echo "日志: $log_file" >&2
            FAILED=$((FAILED + 1))
            continue
          fi
          ;;
        audio)
          if ! find "$case_dir" -type f -name '*.mp3' | grep -q .; then
            echo "[FAIL] $case_id audio 未生成 mp3" >&2
            echo "日志: $log_file" >&2
            FAILED=$((FAILED + 1))
            continue
          fi
          ;;
        subtitle|whisper)
          if ! find "$case_dir" -type f -name '*.txt' | grep -q .; then
            echo "[FAIL] $case_id $MODE 未生成 txt" >&2
            echo "日志: $log_file" >&2
            FAILED=$((FAILED + 1))
            continue
          fi
          ;;
      esac

      echo "[PASS] $case_id download-$MODE"
      PASSED=$((PASSED + 1))
      ;;
    summary)
      INSTRUCTION="$ARG3"
      EXPECTED_PROFILE="${ARG4:-fast}"
      RUN_TYPE="${ARG5:-extract}"

      selection_cmd=(bash "$EXTRACT_SCRIPT" "$URL" "$case_dir/selection" auto --quality auto --check-deps)
      if [[ -n "$INSTRUCTION" ]]; then
        selection_cmd+=(--instruction "$INSTRUCTION")
      fi

      set +e
      selection_output="$("${selection_cmd[@]}" 2>&1)"
      selection_code=$?
      set -e
      printf "[selection]\n%s\n" "$selection_output" >"$log_file"

      if [[ "$selection_code" -ne 0 ]]; then
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
      printf "[selection]\n%s\n\n[extract]\n%s\n" "$selection_output" "$extract_output" >"$log_file"

      if [[ "$extract_code" -ne 0 ]]; then
        echo "[FAIL] $case_id 文本提取失败" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
        continue
      fi

      text_path="$(printf "%s\n" "$extract_output" | sed -n 's/^text_path=//p' | tail -n1)"
      run_dir="$(printf "%s\n" "$extract_output" | sed -n 's/^run_dir=//p' | tail -n1)"
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

      if [[ "$text_path" == *" "* || "$run_dir" == *" "* ]]; then
        echo "[FAIL] $case_id 路径包含空格" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
        continue
      fi

      if [[ -z "$run_dir" || ! -d "$run_dir" || "$text_path" != "$run_dir/"* ]]; then
        echo "[FAIL] $case_id run_dir 或 text_path 归位异常" >&2
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

      summary_request="$run_dir/summary_request.md"
      set +e
      summary_output="$(bash "$SUMMARY_SCRIPT" "$URL" "$video_title" "$duration_sec" "$text_path" >"$summary_request" 2>&1)"
      summary_code=$?
      set -e
      printf "\n[summary_request]\n%s\n" "$summary_output" >> "$log_file"

      if [[ "$summary_code" -ne 0 || ! -f "$summary_request" ]]; then
        echo "[FAIL] $case_id 摘要请求包生成失败" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
        continue
      fi

      if ! rg -q '^## 摘要概述$' "$summary_request" || ! rg -q '^## 附件$' "$summary_request"; then
        echo "[FAIL] $case_id 摘要请求包缺少结构约束" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
        continue
      fi

      summary_result="$run_dir/summary_result.md"
      printf '## 摘要概述\n- [00:12] 示例摘要。\n\n## 附件\n- 原始视频：%s\n- 转写文本：%s\n' "$URL" "$text_path" > "$summary_result"

      background_expand="$run_dir/background_request_expand.md"
      set +e
      expand_output="$(bash "$BACKGROUND_SCRIPT" "$URL" "$video_title" "$summary_result" "$text_path" --mode expand --news off >"$background_expand" 2>&1)"
      expand_code=$?
      set -e
      printf "\n[background_expand]\n%s\n" "$expand_output" >> "$log_file"

      if [[ "$expand_code" -ne 0 || ! -f "$background_expand" ]]; then
        echo "[FAIL] $case_id expand 背景请求包生成失败" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
        continue
      fi

      if ! rg -q '## 相关影响和背景分析' "$background_expand" || ! rg -q '背景知识补充（约2/3）' "$background_expand"; then
        echo "[FAIL] $case_id expand 背景请求包缺少章节结构" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
        continue
      fi

      background_only="$run_dir/background_request_only.md"
      set +e
      only_output="$(bash "$BACKGROUND_SCRIPT" "$URL" "$video_title" "-" "$text_path" --mode background-only --news off >"$background_only" 2>&1)"
      only_code=$?
      set -e
      printf "\n[background_only]\n%s\n" "$only_output" >> "$log_file"

      if [[ "$only_code" -ne 0 || ! -f "$background_only" ]]; then
        echo "[FAIL] $case_id background-only 请求包生成失败" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
        continue
      fi

      if ! rg -q '## 上下文背景' "$background_only" || ! rg -q '关键背景脉络' "$background_only"; then
        echo "[FAIL] $case_id background-only 请求包缺少章节结构" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
        continue
      fi

      echo "[PASS] $case_id summary-extract"
      PASSED=$((PASSED + 1))
      ;;
    *)
      echo "[FAIL] $case_id 未知 kind: $KIND" >&2
      FAILED=$((FAILED + 1))
      ;;
  esac
done < "$CONFIG"

echo "测试汇总: total=$TOTAL pass=$PASSED fail=$FAILED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "测试通过: feipi-video-read-url"
