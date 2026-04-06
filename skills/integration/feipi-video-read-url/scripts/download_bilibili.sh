#!/usr/bin/env bash
set -euo pipefail

# Bilibili 下载脚本（简化版）
#
# 用法：
#   bash scripts/download_bilibili.sh <url> [output_dir] [mode] [whisper_profile]
#
# mode: video | audio | dryrun | subtitle | whisper
# whisper_profile: auto | fast | accurate（仅 mode=whisper 时生效）
#
# 样例（whisper 快/慢档）：
#   bash scripts/download_bilibili.sh "<bilibili_url>" "./downloads" whisper fast
#   bash scripts/download_bilibili.sh "<bilibili_url>" "./downloads" whisper accurate
#
# 认证配置：
# - 支持 AGENT_CHROME_PROFILE（浏览器 profile）
# - 支持 AGENT_BILIBILI_COOKIE_FILE（cookies.txt 文件，Netscape 格式）
# - 默认不提示；仅在触发权限/风控问题时给出配置建议
#
# 网络回退配置（与 YouTube 相反）：
# - 默认不使用代理，优先直连
# - 直连失败后，若检测到本地代理端口可用，则尝试代理
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
WHISPER_HELPER="$SCRIPT_DIR/lib/whispercpp_transcribe.sh"
YT_COMMON_LIB="$SCRIPT_DIR/lib/yt_dlp_common.sh"

AGENT_CHROME_PROFILE="${AGENT_CHROME_PROFILE:-}"
AGENT_BILIBILI_COOKIE_FILE_RAW="${AGENT_BILIBILI_COOKIE_FILE:-}"
AGENT_BILIBILI_COOKIE_FILE="$(normalize_out_dir "$AGENT_BILIBILI_COOKIE_FILE_RAW")"
AGENT_VIDEO_PROXY_PORT="${AGENT_VIDEO_PROXY_PORT:-}"
BILI_AUTH_HIT=0
WHISPER_AUTO_ACCURATE_MAX_SEC=480
YT_CONNECT_TEST_URL="https://www.bilibili.com"
YT_CONNECT_TIMEOUT_SEC=8
YT_PROXY_SCHEME_DEFAULT="http"
YT_PROXY_HOST_DEFAULT="127.0.0.1"
YT_PROXY_PORT_DEFAULT="7890"
YT_DLP_NETWORK_ARGS=()
ACTIVE_PROXY_URL=""
YT_NETWORK_ROUTE="direct"

if [[ -z "$URL" ]]; then
  echo "用法: bash scripts/download_bilibili.sh <url> [output_dir] [video|audio|dryrun|subtitle|whisper] [auto|fast|accurate]" >&2
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

if [[ ! -r "$YT_COMMON_LIB" ]]; then
  echo "缺少当前 skill 的通用脚本: $YT_COMMON_LIB" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$YT_COMMON_LIB"

yt_common_require_tools "$MODE"
yt_common_init "$OUT_DIR" "$AGENT_CHROME_PROFILE"
if [[ -n "$AGENT_BILIBILI_COOKIE_FILE" ]]; then
  if [[ ! -f "$AGENT_BILIBILI_COOKIE_FILE" ]]; then
    echo "AGENT_BILIBILI_COOKIE_FILE 指向的文件不存在: $AGENT_BILIBILI_COOKIE_FILE" >&2
    exit 1
  fi
  if [[ ! -r "$AGENT_BILIBILI_COOKIE_FILE" ]]; then
    echo "AGENT_BILIBILI_COOKIE_FILE 不可读: $AGENT_BILIBILI_COOKIE_FILE" >&2
    exit 1
  fi
  # 若同时配置 profile 与 cookie 文件，优先 cookie 文件，便于跨主机复用。
  YT_COMMON_AUTH_ARGS=(--cookies "$AGENT_BILIBILI_COOKIE_FILE")
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

probe_bilibili_connectivity() {
  local proxy_url="${1:-}"
  local -a curl_cmd

  if ! command -v curl >/dev/null 2>&1; then
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
    ytdlp_cmd+=(--print id "https://www.bilibili.com/video/BV1Q5411x7LJ")
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
    retry_cmd="AGENT_VIDEO_PROXY_PORT=7891 bash scripts/download_bilibili.sh \"$URL\" \"$OUT_DIR_RAW\" \"$MODE\" \"$WHISPER_PROFILE\""
  else
    retry_cmd="AGENT_VIDEO_PROXY_PORT=7891 bash scripts/download_bilibili.sh \"$URL\" \"$OUT_DIR_RAW\" \"$MODE\""
  fi

  echo "直连 Bilibili 失败，且本地代理不可用: $tested_proxy" >&2
  echo "如需走代理，请提供可用端口后重试，例如:" >&2
  echo "  $retry_cmd" >&2
}

ensure_bilibili_network_ready() {
  local fallback_proxy proxy_port

  if probe_bilibili_connectivity; then
    YT_NETWORK_ROUTE="direct"
    return 0
  fi

  proxy_port="${AGENT_VIDEO_PROXY_PORT:-$YT_PROXY_PORT_DEFAULT}"
  fallback_proxy="$(build_proxy_url)"
  if is_proxy_port_listening "$proxy_port"; then
    echo "直连失败，检测到代理端口可用，尝试代理: $fallback_proxy" >&2
    if probe_bilibili_connectivity "$fallback_proxy"; then
      enable_proxy_for_yt_dlp "$fallback_proxy"
      echo "已启用代理下载: $fallback_proxy" >&2
      return 0
    fi
  fi

  print_proxy_port_guidance "$fallback_proxy"
  return 1
}

if ! ensure_bilibili_network_ready; then
  exit 1
fi

print_auth_guidance() {
  echo "检测到可能的 Bilibili 权限限制或风控拦截。" >&2
  echo "处理建议:" >&2
  echo "1) 临时方式（推荐先试其一）:" >&2
  echo "   export AGENT_CHROME_PROFILE='chrome:Profile 1'" >&2
  echo "   export AGENT_BILIBILI_COOKIE_FILE='/path/to/cookies.txt'" >&2
  echo "   # cookies.txt 需为 Netscape Cookie File 格式" >&2
  echo "2) 若同时配置 profile 与 cookie 文件，默认优先 cookie 文件" >&2
  echo "3) 配置后先执行 dryrun，再重试下载" >&2
}

is_auth_related_error() {
  local err_file="$1"
  rg -qi "login required|logged in|Subtitles are only available when logged in|会员|大会员|403 Forbidden|HTTP Error 403|HTTP Error 412|HTTP Error 429|Too Many Requests|请先登录|限地区" "$err_file"
}

# 可选回调：yt_common_run 在失败时会调用该函数。
yt_common_on_error() {
  local err_file="$1"
  shift

  if is_auth_related_error "$err_file"; then
    BILI_AUTH_HIT=1
    print_auth_guidance
  fi

  return 1
}

precheck_subtitle_auth() {
  local check_file
  check_file="$(mktemp)"

  # list-subs 主要用于探测是否存在“需登录才有字幕”的限制。
  yt_common_run_cmd "$check_file" --skip-download --list-subs "$URL" || true

  if is_auth_related_error "$check_file"; then
    BILI_AUTH_HIT=1
    print_auth_guidance
    cat "$check_file" >&2
    rm -f "$check_file"
    return 1
  fi

  rm -f "$check_file"
  return 0
}

run_subtitle_mode() {
  local marker subtitle_file text_file danmaku_file

  marker="$(mktemp "$OUT_DIR/.subtitle-marker.XXXXXX")"

  if ! precheck_subtitle_auth; then
    rm -f "$marker"
    return 1
  fi

  # 一次请求覆盖常见中英字幕标签，减少多次重试带来的耗时。
  yt_common_try \
    --skip-download \
    --write-subs \
    --write-auto-subs \
    --convert-subs vtt \
    --sub-langs "zh-TW,zh-Hant,zh-HK,zh-Hans,zh-CN,zh,ai-zh,ai-en,en" \
    --sub-format "vtt/srt" \
    "$URL" || true
  subtitle_file="$(yt_common_find_new_subtitle_file "$OUT_DIR" "$marker")"

  # 最后兜底：直接拉取全部字幕语言，避免站点语言标签差异导致漏抓。
  if [[ -z "$subtitle_file" ]]; then
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

  subtitle_file="$(yt_common_find_new_subtitle_file "$OUT_DIR" "$marker")"
  danmaku_file="$(yt_common_find_new_danmaku_file "$OUT_DIR" "$marker")"
  rm -f "$marker"

  if [[ -z "$subtitle_file" ]]; then
    if [[ "$BILI_AUTH_HIT" -eq 1 ]]; then
      print_auth_guidance
    fi
    if [[ -n "$danmaku_file" ]]; then
      echo "仅检测到弹幕文件（${danmaku_file}），未获取到标准字幕（vtt/srt）。" >&2
      echo "建议改用 whisper 模式做语音转写。" >&2
    else
      echo "未获取到字幕文件（vtt/srt）。" >&2
    fi
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
    duration_raw="$(yt-dlp --skip-download --no-playlist --print "%(duration)s" "$URL" 2>/dev/null | head -n1)"
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
echo "完成: mode=$MODE, output_dir=$OUT_DIR"
