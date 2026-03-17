#!/usr/bin/env bash
set -euo pipefail

# 统一测试入口（供 make test 调用）
# 严格模式：references/test_cases.txt 每一行（非空、非注释）都必须执行成功。
# 每行格式：<url>|<mode>|[whisper_profile]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_SCRIPT="$SCRIPT_DIR/download_youtube.sh"
DEFAULT_CONFIG="$SKILL_DIR/references/test_cases.txt"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WHISPER_HELPER="$REPO_ROOT/feipi-scripts/video/whispercpp_transcribe.sh"
WHISPER_CPP_BIN_DEFAULT="/opt/homebrew/opt/whisper-cpp/bin/whisper-cli"
WHISPER_MODEL_FILE_DEFAULT="$HOME/Library/Caches/whisper.cpp/models/ggml-large-v3-q5_0.bin"

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
  TMP_ROOT="$OUTPUT"
else
  stamp="$(date +%Y%m%d-%H%M%S)"
  TMP_ROOT="$HOME/Downloads/feipi-youtube-test-$stamp"
  if ! mkdir -p "$TMP_ROOT" 2>/dev/null; then
    TMP_ROOT="/tmp/feipi-youtube-test-$stamp"
  fi
fi
mkdir -p "$TMP_ROOT"
OUT_DIR="$TMP_ROOT/out"
LOG_DIR="$TMP_ROOT/logs"
mkdir -p "$OUT_DIR" "$LOG_DIR"

echo "测试配置: $CONFIG"
echo "测试输出根目录: $TMP_ROOT"
echo "测试产物目录: $OUT_DIR"
echo "测试日志目录: $LOG_DIR"

cleanup() {
  # 默认保留测试文件，便于人工核对产物与日志。
  # 如需清理，可手动删除 OUTPUT 或 TMP_ROOT 目录。
  :
}
trap cleanup EXIT

# 真实集成测试：直接使用系统中的 yt-dlp / ffmpeg。
if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "缺少依赖: yt-dlp（无法执行真实下载测试）" >&2
  exit 1
fi

if grep -Ev '^[[:space:]]*($|#)' "$CONFIG" | rg -q '\|(video|audio|whisper)(\||[[:space:]]*($|#))'; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "缺少依赖: ffmpeg（video/audio/whisper 用例需要）" >&2
    exit 1
  fi
fi

if grep -Ev '^[[:space:]]*($|#)' "$CONFIG" | rg -q '\|whisper(\||[[:space:]]*($|#))'; then
  if [[ ! -x "$WHISPER_HELPER" ]]; then
    echo "缺少共享转写脚本: $WHISPER_HELPER（whisper 用例需要）" >&2
    exit 1
  fi
  if [[ ! -x "$WHISPER_CPP_BIN_DEFAULT" ]] && ! command -v whisper-cli >/dev/null 2>&1; then
    echo "缺少依赖: whisper-cli（whisper.cpp，whisper 用例需要）" >&2
    exit 1
  fi
  if [[ ! -f "$WHISPER_MODEL_FILE_DEFAULT" ]]; then
    echo "缺少模型文件: $WHISPER_MODEL_FILE_DEFAULT（whisper 用例需要）" >&2
    exit 1
  fi
fi

TOTAL=0
PASSED=0
FAILED=0

while IFS= read -r raw || [[ -n "$raw" ]]; do
  line="${raw%%#*}"
  line="$(echo "$line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"

  if [[ -z "$line" ]]; then
    continue
  fi

  TOTAL=$((TOTAL + 1))

  IFS='|' read -r URL MODE WHISPER_PROFILE <<< "$line"
  URL="$(echo "${URL:-}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  MODE="$(echo "${MODE:-dryrun}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  WHISPER_PROFILE="$(echo "${WHISPER_PROFILE:-auto}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  if [[ -z "$MODE" ]]; then
    MODE="dryrun"
  fi
  if [[ -z "$WHISPER_PROFILE" ]]; then
    WHISPER_PROFILE="auto"
  fi

  case "$MODE" in
    dryrun|video|audio|subtitle|whisper) ;;
    *)
      echo "[FAIL] 第 $TOTAL 行 mode 非法: $MODE" >&2
      FAILED=$((FAILED + 1))
      continue
      ;;
  esac

  if [[ "$MODE" == "whisper" ]]; then
    case "$WHISPER_PROFILE" in
      auto|fast|accurate) ;;
      *)
        echo "[FAIL] 第 $TOTAL 行 whisper_profile 非法: $WHISPER_PROFILE" >&2
        FAILED=$((FAILED + 1))
        continue
        ;;
    esac
  fi

  log_file="$LOG_DIR/case-$TOTAL.log"
  case_out_dir="$OUT_DIR/case-$TOTAL"
  mkdir -p "$case_out_dir"
  marker="$LOG_DIR/case-$TOTAL.marker"
  : > "$marker"
  echo "----"
  echo "开始执行 case-$TOTAL"
  echo "模式: $MODE"
  echo "URL: $URL"
  echo "产物目录: $case_out_dir"
  cmd=(bash "$TARGET_SCRIPT" "$URL" "$case_out_dir" "$MODE")
  if [[ "$MODE" == "whisper" ]]; then
    echo "whisper_profile: $WHISPER_PROFILE"
    cmd+=("$WHISPER_PROFILE")
  fi
  if "${cmd[@]}" >"$log_file" 2>&1; then
    # 严格要求：各模式必须产出预期结果。
    if [[ "$MODE" == "video" ]]; then
      if find "$case_out_dir" -type f -name '*.mp4' -newer "$marker" | grep -q .; then
        mp4_file="$(find "$case_out_dir" -type f -name '*.mp4' -newer "$marker" | head -n1)"
        echo "[PASS] 第 $TOTAL 行: mode=$MODE url=$URL (已检测到 mp4 产物)"
        echo "产物文件: $mp4_file"
        PASSED=$((PASSED + 1))
      else
        echo "[FAIL] 第 $TOTAL 行: mode=$MODE url=$URL (未检测到 mp4 产物)" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
      fi
    elif [[ "$MODE" == "audio" ]]; then
      if find "$case_out_dir" -type f -name '*.mp3' -newer "$marker" | grep -q .; then
        mp3_file="$(find "$case_out_dir" -type f -name '*.mp3' -newer "$marker" | head -n1)"
        echo "[PASS] 第 $TOTAL 行: mode=$MODE url=$URL (已检测到 mp3 产物)"
        echo "产物文件: $mp3_file"
        PASSED=$((PASSED + 1))
      else
        echo "[FAIL] 第 $TOTAL 行: mode=$MODE url=$URL (未检测到 mp3 产物)" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
      fi
    elif [[ "$MODE" == "subtitle" || "$MODE" == "whisper" ]]; then
      if find "$case_out_dir" -type f -name '*.txt' -newer "$marker" | grep -q .; then
        txt_file="$(find "$case_out_dir" -type f -name '*.txt' -newer "$marker" | head -n1)"
        echo "[PASS] 第 $TOTAL 行: mode=$MODE url=$URL (已检测到 txt 产物)"
        echo "产物文件: $txt_file"
        PASSED=$((PASSED + 1))
      else
        echo "[FAIL] 第 $TOTAL 行: mode=$MODE url=$URL (未检测到 txt 产物)" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
      fi
    else
      # dryrun 模式不应产生媒体文件。
      if find "$case_out_dir" -type f \( -name '*.mp4' -o -name '*.mp3' \) -newer "$marker" | grep -q .; then
        echo "[FAIL] 第 $TOTAL 行: mode=$MODE url=$URL (dryrun 不应生成媒体文件)" >&2
        echo "日志: $log_file" >&2
        FAILED=$((FAILED + 1))
      else
        echo "[PASS] 第 $TOTAL 行: mode=$MODE url=$URL"
        PASSED=$((PASSED + 1))
      fi
    fi
    echo "日志文件: $log_file"
  else
    echo "[FAIL] 第 $TOTAL 行: mode=$MODE url=$URL" >&2
    echo "日志: $log_file" >&2
    FAILED=$((FAILED + 1))
  fi
done < "$CONFIG"

if [[ "$TOTAL" -eq 0 ]]; then
  echo "测试配置为空: $CONFIG（至少需要一行用例）" >&2
  exit 1
fi

echo "测试汇总: total=$TOTAL pass=$PASSED fail=$FAILED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "测试通过: feipi-read-youtube-video（每行用例均成功）"
if [[ -z "$OUTPUT" ]]; then
  echo "提示: 当前未指定 OUTPUT，测试文件已保留在: $TMP_ROOT"
else
  echo "提示: 已保留测试文件，路径: $TMP_ROOT"
fi
