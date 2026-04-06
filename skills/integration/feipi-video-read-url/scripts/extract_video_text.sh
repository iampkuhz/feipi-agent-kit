#!/usr/bin/env bash
set -euo pipefail

# 依据 URL 来源统一提取带时间戳文本。
# 用法：
#   bash scripts/extract_video_text.sh <url> [output_root_dir] [auto|subtitle|whisper] \
#     [--instruction "用户原始指令"] [--quality auto|fast|accurate] [--check-deps]

CHECK_ONLY="0"
INSTRUCTION_TEXT=""
QUALITY_HINT="auto"
PROFILE_REASON="default_fast"
WHISPER_PROFILE="fast"
URL=""
OUT_ROOT_DIR="./tmp/video-text"
RUN_DIR=""
MODE="auto"
AUTH_PRESENT="0"

usage() {
  echo "用法: bash scripts/extract_video_text.sh <url> [output_root_dir] [auto|subtitle|whisper] [--instruction \"文本\"] [--quality auto|fast|accurate] [--check-deps]" >&2
}

contains_any() {
  local haystack="$1"
  shift

  local keyword
  for keyword in "$@"; do
    if [[ -n "$keyword" && "$haystack" == *"$keyword"* ]]; then
      return 0
    fi
  done

  return 1
}

resolve_whisper_profile() {
  local quality_hint="$1"
  local instruction="$2"
  local normalized

  case "$quality_hint" in
    fast)
      PROFILE_REASON="explicit_fast"
      echo "fast"
      return 0
      ;;
    accurate)
      PROFILE_REASON="explicit_accurate"
      echo "accurate"
      return 0
      ;;
    auto)
      ;;
    *)
      echo "invalid_quality"
      return 1
      ;;
  esac

  if [[ -z "$instruction" ]]; then
    PROFILE_REASON="auto_default_fast"
    echo "fast"
    return 0
  fi

  normalized="$(printf "%s" "$instruction" | tr '[:upper:]' '[:lower:]')"
  if contains_any "$normalized" \
    "高质量" "高精度" "高准确" "准确率" "精确" "逐字" "逐句" "完整转写" "高保真" "质量优先" \
    "high quality" "accurate" "precision" "verbatim"; then
    PROFILE_REASON="auto_high_quality_instruction"
    echo "accurate"
    return 0
  fi

  if contains_any "$normalized" \
    "快速" "尽快" "速度优先" "低延迟" "先粗略" "快一点" \
    "fast" "quick" "speed first" "low latency"; then
    PROFILE_REASON="auto_speed_instruction"
    echo "fast"
    return 0
  fi

  PROFILE_REASON="auto_default_fast"
  echo "fast"
}

POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-deps)
      CHECK_ONLY="1"
      shift
      ;;
    --instruction)
      if [[ -z "${2:-}" ]]; then
        echo "--instruction 缺少参数" >&2
        usage
        exit 1
      fi
      INSTRUCTION_TEXT="$2"
      shift 2
      ;;
    --quality)
      if [[ -z "${2:-}" ]]; then
        echo "--quality 缺少参数" >&2
        usage
        exit 1
      fi
      QUALITY_HINT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "${#POSITIONAL_ARGS[@]}" -lt 1 ]]; then
  usage
  exit 1
fi

if [[ "${#POSITIONAL_ARGS[@]}" -gt 3 ]]; then
  echo "位置参数过多，仅支持 <url> [output_dir] [mode]" >&2
  usage
  exit 1
fi

URL="${POSITIONAL_ARGS[0]}"
if [[ "${#POSITIONAL_ARGS[@]}" -ge 2 ]]; then
  OUT_ROOT_DIR="${POSITIONAL_ARGS[1]}"
fi
if [[ "${#POSITIONAL_ARGS[@]}" -ge 3 ]]; then
  MODE="${POSITIONAL_ARGS[2]}"
fi

if [[ "$MODE" != "auto" && "$MODE" != "subtitle" && "$MODE" != "whisper" ]]; then
  echo "mode 仅支持 auto|subtitle|whisper，当前: $MODE" >&2
  exit 1
fi

if [[ "$QUALITY_HINT" != "auto" && "$QUALITY_HINT" != "fast" && "$QUALITY_HINT" != "accurate" ]]; then
  echo "quality 仅支持 auto|fast|accurate，当前: $QUALITY_HINT" >&2
  exit 1
fi

WHISPER_PROFILE="$(resolve_whisper_profile "$QUALITY_HINT" "$INSTRUCTION_TEXT" || true)"
if [[ "$WHISPER_PROFILE" != "fast" && "$WHISPER_PROFILE" != "accurate" ]]; then
  echo "无法解析 whisper 档位，请检查 quality 或 instruction 输入。" >&2
  exit 1
fi

if [[ -n "${AGENT_CHROME_PROFILE:-}" || -n "${AGENT_YOUTUBE_COOKIE_FILE:-}" ]]; then
  AUTH_PRESENT="1"
fi

detect_source() {
  local url="$1"
  if [[ "$url" =~ ^https?://([a-zA-Z0-9-]+\.)?(youtube\.com|youtu\.be)(/|$) ]]; then
    echo "youtube"
    return 0
  fi
  if [[ "$url" =~ ^https?://([a-zA-Z0-9-]+\.)?(bilibili\.com|b23\.tv)(/|$) ]]; then
    echo "bilibili"
    return 0
  fi
  echo "不支持的视频来源: $url（当前仅支持 YouTube / Bilibili）" >&2
  return 1
}

sanitize_key() {
  local raw="$1"
  local normalized

  normalized="$(printf "%s" "$raw" | tr -c 'A-Za-z0-9._-' '-')"
  normalized="$(printf "%s" "$normalized" | sed -E 's/-+/-/g; s/^-+//; s/-+$//')"
  if [[ -z "$normalized" ]]; then
    echo "unknown"
    return 0
  fi

  echo "$normalized"
}

sanitize_filename() {
  local raw="$1"
  local normalized

  normalized="${raw// /_}"
  normalized="$(printf "%s" "$normalized" | tr -s '_')"
  if [[ -z "$normalized" ]]; then
    echo "$raw"
    return 0
  fi

  echo "$normalized"
}

rename_recent_files() {
  local marker="$1"
  local file dir base normalized newpath stem ext suffix

  while IFS= read -r -d '' file; do
    dir="$(dirname "$file")"
    base="$(basename "$file")"
    normalized="$(sanitize_filename "$base")"
    if [[ "$normalized" == "$base" ]]; then
      continue
    fi

    newpath="$dir/$normalized"
    if [[ -e "$newpath" ]]; then
      stem="${normalized%.*}"
      ext="${normalized##*.}"
      if [[ "$stem" == "$normalized" ]]; then
        ext=""
      fi
      suffix=1
      while [[ -e "$newpath" ]]; do
        if [[ -n "$ext" ]]; then
          newpath="$dir/${stem}_$suffix.$ext"
        else
          newpath="$dir/${stem}_$suffix"
        fi
        suffix=$((suffix + 1))
      done
    fi

    mv "$file" "$newpath"
  done < <(find "$RUN_DIR" -maxdepth 1 -type f -newer "$marker" -print0)
}

fallback_url_hash() {
  local url="$1"

  if command -v shasum >/dev/null 2>&1; then
    printf "%s" "$url" | shasum -a 1 | awk '{print substr($1,1,12)}'
    return 0
  fi

  if command -v sha1sum >/dev/null 2>&1; then
    printf "%s" "$url" | sha1sum | awk '{print substr($1,1,12)}'
    return 0
  fi

  if command -v md5 >/dev/null 2>&1; then
    printf "%s" "$url" | md5 | awk '{print substr($NF,1,12)}'
    return 0
  fi

  echo "nohash"
}

extract_youtube_key() {
  local url="$1"
  local key

  key="$(printf "%s" "$url" | sed -nE 's#.*[?&]v=([A-Za-z0-9_-]{6,}).*#\1#p' | head -n1)"
  if [[ -n "$key" ]]; then
    echo "$key"
    return 0
  fi

  key="$(printf "%s" "$url" | sed -nE 's#^https?://([a-zA-Z0-9-]+\.)?youtu\.be/([^?&/]+).*$#\2#p' | head -n1)"
  if [[ -n "$key" ]]; then
    echo "$key"
    return 0
  fi

  key="$(printf "%s" "$url" | sed -nE 's#^https?://([a-zA-Z0-9-]+\.)?youtube\.com/(shorts|live)/([^?&/]+).*$#\3#p' | head -n1)"
  if [[ -n "$key" ]]; then
    echo "$key"
    return 0
  fi

  return 1
}

extract_bilibili_key() {
  local url="$1"
  local key

  key="$(printf "%s" "$url" | sed -nE 's#.*(BV[0-9A-Za-z]+).*#\1#p' | head -n1)"
  if [[ -n "$key" ]]; then
    echo "$key"
    return 0
  fi

  return 1
}

resolve_url_key() {
  local source="$1"
  local url="$2"
  local key=""

  if [[ "$source" == "youtube" ]]; then
    key="$(extract_youtube_key "$url" || true)"
  elif [[ "$source" == "bilibili" ]]; then
    key="$(extract_bilibili_key "$url" || true)"
  fi

  if [[ -z "$key" ]]; then
    key="url-$(fallback_url_hash "$url")"
  fi

  sanitize_key "$key"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_SCRIPT="$SCRIPT_DIR/install_deps.sh"
SOURCE="$(detect_source "$URL")"
URL_KEY="$(resolve_url_key "$SOURCE" "$URL")"
RUN_DIR="$OUT_ROOT_DIR/${SOURCE}-${URL_KEY}"

case "$SOURCE" in
  youtube)
    SOURCE_SCRIPT="$SCRIPT_DIR/download_youtube.sh"
    ;;
  bilibili)
    SOURCE_SCRIPT="$SCRIPT_DIR/download_bilibili.sh"
    ;;
  *)
    echo "未知来源: $SOURCE" >&2
    exit 1
    ;;
esac

if [[ ! -x "$INSTALL_SCRIPT" ]]; then
  echo "缺少依赖安装脚本或不可执行: $INSTALL_SCRIPT" >&2
  exit 1
fi

if [[ ! -x "$SOURCE_SCRIPT" ]]; then
  echo "缺少来源脚本或不可执行: $SOURCE_SCRIPT" >&2
  exit 1
fi

if [[ "$CHECK_ONLY" == "1" ]]; then
  bash "$INSTALL_SCRIPT" --check >/dev/null
  echo "dependency_ok=1"
  echo "source=$SOURCE"
  echo "run_dir=$RUN_DIR"
  echo "script=$SOURCE_SCRIPT"
  echo "whisper_profile=$WHISPER_PROFILE"
  echo "selection_reason=$PROFILE_REASON"
  exit 0
fi

mkdir -p "$RUN_DIR"
LOG_DIR="$RUN_DIR/logs"
mkdir -p "$LOG_DIR"

run_mode() {
  local mode="$1"
  local auth_mode="${2:-auth}"
  local marker log_file newest_txt

  if [[ "$auth_mode" == "no_auth" ]]; then
    log_file="$LOG_DIR/${SOURCE}-${mode}-noauth.log"
  else
    log_file="$LOG_DIR/${SOURCE}-${mode}.log"
  fi

  marker="$(mktemp "$RUN_DIR/.txt-marker.XXXXXX")"

  set +e
  if [[ "$mode" == "whisper" ]]; then
    if [[ "$auth_mode" == "no_auth" && "$SOURCE" == "youtube" ]]; then
      env AGENT_CHROME_PROFILE= AGENT_YOUTUBE_COOKIE_FILE= bash "$SOURCE_SCRIPT" "$URL" "$RUN_DIR" "$mode" "$WHISPER_PROFILE" >"$log_file" 2>&1
    else
      bash "$SOURCE_SCRIPT" "$URL" "$RUN_DIR" "$mode" "$WHISPER_PROFILE" >"$log_file" 2>&1
    fi
  else
    if [[ "$auth_mode" == "no_auth" && "$SOURCE" == "youtube" ]]; then
      env AGENT_CHROME_PROFILE= AGENT_YOUTUBE_COOKIE_FILE= bash "$SOURCE_SCRIPT" "$URL" "$RUN_DIR" "$mode" >"$log_file" 2>&1
    else
      bash "$SOURCE_SCRIPT" "$URL" "$RUN_DIR" "$mode" >"$log_file" 2>&1
    fi
  fi
  local code=$?
  set -e

  rename_recent_files "$marker"
  newest_txt="$(find "$RUN_DIR" -maxdepth 1 -type f -name '*.txt' -newer "$marker" | sort | tail -n1 || true)"
  rm -f "$marker"

  if [[ $code -eq 0 && -n "$newest_txt" ]]; then
    echo "$newest_txt"
    return 0
  fi

  return 1
}

run_mode_with_fallback() {
  local mode="$1"

  if TEXT_FILE="$(run_mode "$mode" "auth")"; then
    return 0
  fi

  if [[ "$SOURCE" == "youtube" && "$AUTH_PRESENT" -eq 1 ]]; then
    echo "检测到 Cookie 或浏览器认证可能导致失败，尝试无 Cookie 重试: mode=$mode" >&2
    if TEXT_FILE="$(run_mode "$mode" "no_auth")"; then
      return 0
    fi
  fi

  return 1
}

TEXT_FILE=""
USED_MODE=""
STRATEGY=""

if [[ "$MODE" == "auto" ]]; then
  if [[ "$WHISPER_PROFILE" == "accurate" ]]; then
    STRATEGY="whisper_first"
    if run_mode_with_fallback whisper; then
      USED_MODE="whisper"
    elif run_mode_with_fallback subtitle; then
      USED_MODE="subtitle"
    fi
  else
    STRATEGY="subtitle_first"
    if run_mode_with_fallback subtitle; then
      USED_MODE="subtitle"
    elif run_mode_with_fallback whisper; then
      USED_MODE="whisper"
    fi
  fi
elif [[ "$MODE" == "subtitle" ]]; then
  STRATEGY="subtitle_only"
  if run_mode_with_fallback subtitle; then
    USED_MODE="subtitle"
  fi
else
  STRATEGY="whisper_only"
  if run_mode_with_fallback whisper; then
    USED_MODE="whisper"
  fi
fi

if [[ -z "$TEXT_FILE" ]]; then
  echo "文本提取失败: source=$SOURCE mode=$MODE strategy=$STRATEGY whisper_profile=$WHISPER_PROFILE" >&2
  echo "请检查日志目录: $LOG_DIR" >&2
  exit 1
fi

echo "source=$SOURCE"
echo "run_dir=$RUN_DIR"
echo "mode=$USED_MODE"
echo "text_path=$TEXT_FILE"
echo "log_dir=$LOG_DIR"
echo "strategy=$STRATEGY"
echo "whisper_profile=$WHISPER_PROFILE"
echo "selection_reason=$PROFILE_REASON"
