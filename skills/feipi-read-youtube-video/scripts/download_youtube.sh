#!/usr/bin/env bash
set -euo pipefail

# YouTube 下载脚本（简化版）
#
# 用法：
#   bash scripts/download_youtube.sh <url> [output_dir] [mode] [whisper_profile]
#
# mode: video | audio | dryrun | subtitle | whisper
# whisper_profile: auto | fast | accurate（仅 mode=whisper 时生效）
#
# 样例（whisper 快/慢档）：
#   bash scripts/download_youtube.sh "<youtube_url>" "./downloads" whisper fast
#   bash scripts/download_youtube.sh "<youtube_url>" "./downloads" whisper accurate
#
# 认证配置：
# - 支持 AGENT_CHROME_PROFILE（浏览器 profile）
# - 支持 AGENT_YOUTUBE_COOKIE_FILE（cookies.txt 文件，Netscape 格式）
# - 默认不提示；仅在触发 bot 检测时给出配置建议
#
# 网络回退配置：
# - 若检测到本地代理端口可用，优先使用代理 http://127.0.0.1:<port>
# - 代理失败再回退直连
# - 未检测到代理时，先尝试直连，再回退代理
# - 可通过 AGENT_VIDEO_PROXY_PORT 覆盖默认端口

URL="${1:-}"
OUT_DIR_RAW="${2:-./downloads}"
MODE="${3:-video}"
WHISPER_PROFILE="${4:-auto}"

normalize_out_dir() {
  local raw="$1"
  if [[ "$raw" == "~" ]]; then
    echo "$HOME"
    return 0
  fi
  if [[ "$raw" == "~/"* ]]; then
    echo "$HOME/${raw:2}"
    return 0
  fi
  echo "$raw"
}

OUT_DIR="$(normalize_out_dir "$OUT_DIR_RAW")"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WHISPER_HELPER="$REPO_ROOT/feipi-scripts/video/whispercpp_transcribe.sh"
YT_COMMON_LIB="$REPO_ROOT/feipi-scripts/video/yt_dlp_common.sh"

AGENT_CHROME_PROFILE="${AGENT_CHROME_PROFILE:-}"
AGENT_YOUTUBE_COOKIE_FILE_RAW="${AGENT_YOUTUBE_COOKIE_FILE:-}"
AGENT_VIDEO_PROXY_PORT="${AGENT_VIDEO_PROXY_PORT:-}"
AGENT_YOUTUBE_COOKIE_FILE="$(normalize_out_dir "$AGENT_YOUTUBE_COOKIE_FILE_RAW")"

# YouTube 反爬重试策略固定值（不通过环境变量暴露）。
YT_REMOTE_COMPONENTS_DEFAULT="ejs:github"
YT_EXTRACTOR_ARGS_DEFAULT="youtube:player_client=android,web_safari"
YT_BOT_HIT=0
WHISPER_AUTO_ACCURATE_MAX_SEC=480
YT_CONNECT_TEST_URL="https://www.youtube.com/generate_204"
YT_CONNECT_TIMEOUT_SEC=8
YT_PROXY_SCHEME_DEFAULT="http"
YT_PROXY_HOST_DEFAULT="127.0.0.1"
YT_PROXY_PORT_DEFAULT="7890"
YT_DLP_NETWORK_ARGS=()
ACTIVE_PROXY_URL=""
YT_NETWORK_ROUTE="direct"

if [[ -z "$URL" ]]; then
  echo "用法: bash scripts/download_youtube.sh <url> [output_dir] [video|audio|dryrun|subtitle|whisper] [auto|fast|accurate]" >&2
  exit 1
fi

if [[ "$WHISPER_PROFILE" != "auto" && "$WHISPER_PROFILE" != "fast" && "$WHISPER_PROFILE" != "accurate" ]]; then
  echo "whisper_profile 仅支持 auto|fast|accurate，当前: $WHISPER_PROFILE" >&2
  exit 1
fi

is_valid_port() {
  local value="${1:-}"
  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    return 1
  fi
  if (( value < 1 || value > 65535 )); then
    return 1
  fi
  return 0
}

if [[ -n "$AGENT_VIDEO_PROXY_PORT" ]] && ! is_valid_port "$AGENT_VIDEO_PROXY_PORT"; then
  echo "AGENT_VIDEO_PROXY_PORT 必须是 1~65535 的整数，当前: $AGENT_VIDEO_PROXY_PORT" >&2
  exit 1
fi

if [[ -n "$AGENT_YOUTUBE_COOKIE_FILE" ]]; then
  if [[ ! -f "$AGENT_YOUTUBE_COOKIE_FILE" ]]; then
    echo "AGENT_YOUTUBE_COOKIE_FILE 指向的文件不存在: $AGENT_YOUTUBE_COOKIE_FILE" >&2
    exit 1
  fi
  if [[ ! -r "$AGENT_YOUTUBE_COOKIE_FILE" ]]; then
    echo "AGENT_YOUTUBE_COOKIE_FILE 不可读: $AGENT_YOUTUBE_COOKIE_FILE" >&2
    exit 1
  fi
fi

if [[ ! -r "$YT_COMMON_LIB" ]]; then
  echo "缺少仓库级通用脚本: $YT_COMMON_LIB" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$YT_COMMON_LIB"

yt_common_require_tools "$MODE"
yt_common_init "$OUT_DIR" "$AGENT_CHROME_PROFILE"
AUTH_SOURCE="none"
if [[ -n "$AGENT_CHROME_PROFILE" ]]; then
  AUTH_SOURCE="browser_profile"
fi
if [[ -n "$AGENT_YOUTUBE_COOKIE_FILE" ]]; then
  # 若同时配置 profile 与 cookie 文件，优先 cookie 文件，便于跨主机复用。
  YT_COMMON_AUTH_ARGS=(--cookies "$AGENT_YOUTUBE_COOKIE_FILE")
  AUTH_SOURCE="cookie_file"
fi

build_proxy_url() {
  local port
  port="${AGENT_VIDEO_PROXY_PORT:-$YT_PROXY_PORT_DEFAULT}"
  echo "$YT_PROXY_SCHEME_DEFAULT://$YT_PROXY_HOST_DEFAULT:$port"
}

is_proxy_port_listening() {
  local port="$1"

  if command -v nc >/dev/null 2>&1; then
    nc -z -w 1 "$YT_PROXY_HOST_DEFAULT" "$port" >/dev/null 2>&1
    return $?
  fi

  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi

  return 1
}

enable_proxy_for_yt_dlp() {
  local proxy_url="$1"

  if [[ -z "$proxy_url" ]]; then
    return 1
  fi

  if [[ "$ACTIVE_PROXY_URL" == "$proxy_url" ]]; then
    return 0
  fi

  YT_COMMON_ARGS+=(--proxy "$proxy_url")
  YT_DLP_NETWORK_ARGS=(--proxy "$proxy_url")
  ACTIVE_PROXY_URL="$proxy_url"
  YT_NETWORK_ROUTE="proxy"
}

probe_youtube_connectivity() {
  local proxy_url="${1:-}"
  local -a curl_cmd

  if ! command -v curl >/dev/null 2>&1; then
    # macOS 默认有 curl；若缺失则回退到 yt-dlp 轻量探测。
    local -a ytdlp_cmd
    ytdlp_cmd=(
      yt-dlp
      --skip-download
      --no-playlist
      --socket-timeout "$YT_CONNECT_TIMEOUT_SEC"
    )
    if [[ -n "$proxy_url" ]]; then
      ytdlp_cmd+=(--proxy "$proxy_url")
    fi
    ytdlp_cmd+=(--print id "https://www.youtube.com/watch?v=BaW_jenozKc")
    "${ytdlp_cmd[@]}" >/dev/null 2>&1
    return $?
  fi

  curl_cmd=(
    curl
    --silent
    --show-error
    --head
    --location
    --max-time "$YT_CONNECT_TIMEOUT_SEC"
    --connect-timeout "$YT_CONNECT_TIMEOUT_SEC"
  )
  if [[ -n "$proxy_url" ]]; then
    curl_cmd+=(--proxy "$proxy_url")
  fi
  curl_cmd+=("$YT_CONNECT_TEST_URL")

  "${curl_cmd[@]}" >/dev/null 2>&1
}

print_proxy_port_guidance() {
  local tested_proxy="$1"
  local retry_cmd

  if [[ "$MODE" == "whisper" ]]; then
    retry_cmd="AGENT_VIDEO_PROXY_PORT=7891 bash scripts/download_youtube.sh \"$URL\" \"$OUT_DIR_RAW\" \"$MODE\" \"$WHISPER_PROFILE\""
  else
    retry_cmd="AGENT_VIDEO_PROXY_PORT=7891 bash scripts/download_youtube.sh \"$URL\" \"$OUT_DIR_RAW\" \"$MODE\""
  fi

  echo "直连 YouTube 失败，且默认代理也不可用: $tested_proxy" >&2
  echo "请提供可用代理端口后重试，例如:" >&2
  echo "  $retry_cmd" >&2
}

ensure_youtube_network_ready() {
  local fallback_proxy proxy_port

  proxy_port="${AGENT_VIDEO_PROXY_PORT:-$YT_PROXY_PORT_DEFAULT}"
  fallback_proxy="$(build_proxy_url)"

  if is_proxy_port_listening "$proxy_port"; then
    echo "检测到本地代理端口可用，优先尝试代理: $fallback_proxy" >&2
    if probe_youtube_connectivity "$fallback_proxy"; then
      enable_proxy_for_yt_dlp "$fallback_proxy"
      echo "已启用代理下载: $fallback_proxy" >&2
      return 0
    fi
    echo "代理可用但访问 YouTube 失败，回退直连探测。" >&2
  fi

  if probe_youtube_connectivity; then
    YT_NETWORK_ROUTE="direct"
    return 0
  fi

  echo "检测到 YouTube 直连不可用，开始尝试代理: $fallback_proxy" >&2
  if probe_youtube_connectivity "$fallback_proxy"; then
    enable_proxy_for_yt_dlp "$fallback_proxy"
    echo "已启用代理下载: $fallback_proxy" >&2
    return 0
  fi

  print_proxy_port_guidance "$fallback_proxy"
  return 1
}

if ! ensure_youtube_network_ready; then
  exit 1
fi

is_challenge_error() {
  local err_file="$1"
  rg -qi "n challenge solving failed|Remote components challenge solver script|Only images are available|Requested format is not available|Sign in to confirm|confirm you're not a bot" "$err_file"
}

print_bot_guidance() {
  echo "检测到可能的 YouTube bot/风控拦截。" >&2
  echo "处理建议:" >&2
  echo "1) 临时方式（推荐先试其一）:" >&2
  echo "   export AGENT_CHROME_PROFILE='chrome:Profile 1'" >&2
  echo "   export AGENT_YOUTUBE_COOKIE_FILE='/path/to/cookies.txt'" >&2
  echo "   # cookies.txt 需为 Netscape Cookie File 格式" >&2
  echo "2) 若同时配置 profile 与 cookie 文件，默认优先 cookie 文件" >&2
  echo "3) 配置后先执行 dryrun，再重试下载" >&2
}

# 可选回调：yt_common_run 在失败时会调用该函数。
yt_common_on_error() {
  local err_file="$1"
  shift

  # YouTube JS challenge 失败时，使用远程组件与提取器参数重试一次。
  if is_challenge_error "$err_file"; then
    if yt_common_run_cmd "$err_file" \
      --remote-components "$YT_REMOTE_COMPONENTS_DEFAULT" \
      --extractor-args "$YT_EXTRACTOR_ARGS_DEFAULT" \
      "$@"; then
      return 0
    fi
  fi

  if rg -qi "confirm you're not a bot|Sign in to confirm|403 Forbidden|HTTP Error 429" "$err_file"; then
    YT_BOT_HIT=1
    print_bot_guidance
  fi

  return 1
}

run_subtitle_mode() {
  local marker subtitle_file text_file

  marker="$(mktemp "$OUT_DIR/.subtitle-marker.XXXXXX")"

  # 一次请求同时覆盖中英字幕，减少多次网络探测耗时。
  yt_common_try \
    --skip-download \
    --write-subs \
    --write-auto-subs \
    --convert-subs vtt \
    --sub-langs "zh.*,en.*" \
    --sub-format "vtt/srt" \
    "$URL" || true

  subtitle_file="$(yt_common_find_new_subtitle_file "$OUT_DIR" "$marker")"
  if [[ -z "$subtitle_file" ]]; then
    # 兜底：拉取全部语言，防止站点语言标签不规范。
    yt_common_try \
      --skip-download \
      --write-subs \
      --write-auto-subs \
      --convert-subs vtt \
      --sub-langs "all" \
      --sub-format "vtt/srt" \
      "$URL" || true
    subtitle_file="$(yt_common_find_new_subtitle_file "$OUT_DIR" "$marker")"
  fi
  rm -f "$marker"

  if [[ -z "$subtitle_file" ]]; then
    if [[ "$YT_BOT_HIT" -eq 1 ]]; then
      print_bot_guidance
    fi
    echo "未获取到字幕文件（vtt/srt）。" >&2
    return 1
  fi

  text_file="${subtitle_file%.*}.txt"
  yt_common_subtitle_to_text "$subtitle_file" "$text_file"
  echo "完成: mode=subtitle, subtitle=$subtitle_file, text=$text_file"
}

run_whisper_mode() {
  local whisper_log used_device used_profile used_model audio_file text_file
  local resolved_profile profile_reason profile_pair

  resolve_whisper_profile_auto() {
    local requested="$1"
    local duration_raw duration_int

    if [[ "$requested" != "auto" ]]; then
      echo "$requested|explicit"
      return 0
    fi

    set +e
    duration_raw="$(yt-dlp "${YT_DLP_NETWORK_ARGS[@]}" --skip-download --no-playlist --print "%(duration)s" "$URL" 2>/dev/null | head -n1)"
    set -e

    if [[ "$duration_raw" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
      duration_int="${duration_raw%.*}"
      if (( duration_int <= WHISPER_AUTO_ACCURATE_MAX_SEC )); then
        echo "accurate|auto_duration_short_${duration_int}s"
      else
        echo "fast|auto_duration_long_${duration_int}s"
      fi
      return 0
    fi

    # 无法获取时长时默认快档，优先保障速度。
    echo "fast|auto_duration_unknown_default_fast"
  }

  profile_pair="$(resolve_whisper_profile_auto "$WHISPER_PROFILE")"
  resolved_profile="${profile_pair%%|*}"
  profile_reason="${profile_pair#*|}"

  whisper_log="$(mktemp "$OUT_DIR/.whisper-mode.XXXXXX")"
  if ! yt_common_run_whisper_mode_from_url "$URL" "$OUT_DIR" "$WHISPER_HELPER" zh "$resolved_profile" >"$whisper_log" 2>&1; then
    cat "$whisper_log"
    rm -f "$whisper_log"
    return 1
  fi

  cat "$whisper_log"
  used_device="$(sed -n 's/^device=//p' "$whisper_log" | tail -n1)"
  used_profile="$(sed -n 's/^profile=//p' "$whisper_log" | tail -n1)"
  used_model="$(sed -n 's/^model=//p' "$whisper_log" | tail -n1)"
  audio_file="$(sed -n 's/^audio_file=//p' "$whisper_log" | tail -n1)"
  text_file="$(sed -n 's/^text_file=//p' "$whisper_log" | tail -n1)"
  rm -f "$whisper_log"

  if [[ -z "$used_device" ]]; then
    used_device="unknown"
  fi
  if [[ -z "$used_profile" ]]; then
    used_profile="unknown"
  fi
  if [[ -z "$used_model" ]]; then
    used_model="unknown"
  fi

  echo "whisper_profile_requested=$WHISPER_PROFILE"
  echo "whisper_profile_resolved=$resolved_profile"
  echo "whisper_profile_reason=$profile_reason"
  echo "完成: mode=whisper, engine=whisper.cpp, profile=$used_profile, model=$used_model, device=$used_device, audio=$audio_file, text=$text_file"
}

case "$MODE" in
  dryrun)
    yt_common_mode_dryrun "$URL"
    ;;
  audio)
    yt_common_mode_audio "$URL"
    ;;
  video)
    yt_common_mode_video "$URL"
    ;;
  subtitle)
    run_subtitle_mode
    ;;
  whisper)
    run_whisper_mode
    ;;
  *)
    echo "不支持的 mode: $MODE (可选: video|audio|dryrun|subtitle|whisper)" >&2
    exit 1
    ;;
esac

echo "network_route=$YT_NETWORK_ROUTE"
if [[ -n "$ACTIVE_PROXY_URL" ]]; then
  echo "proxy_url=$ACTIVE_PROXY_URL"
fi
echo "auth_source=$AUTH_SOURCE"
echo "完成: mode=$MODE, output_dir=$OUT_DIR"
