#!/usr/bin/env bash
set -euo pipefail

URL="${1:-}"
OUT_DIR="${2:-./downloads}"
MODE="${3:-video}"
PROFILE="${4:-fast}"
LANGUAGE="${AGENT_VIDEO_LANGUAGE:-zh}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$MODE" in dryrun|video|audio|subtitle|whisper) ;; *) echo 'mode 无效' >&2; exit 1;; esac
case "$PROFILE" in auto|fast) PROFILE=fast;; accurate) ;; *) echo 'profile 无效' >&2; exit 1;; esac
case "$LANGUAGE" in auto|zh|en) ;; *) echo 'AGENT_VIDEO_LANGUAGE 仅支持 auto|zh|en' >&2; exit 1;; esac

source "$SCRIPT_DIR/lib/yt_dlp_common.sh"
command -v python3 >/dev/null
yt_common_require_tools "$MODE"
yt_common_init "$OUT_DIR"
trap 'yt_common_finish_identity' EXIT

echo 'pipeline_stage=source_resolution' >&2
SOURCE_URL="$(python3 "$SCRIPT_DIR/lib/xiaohongshu_url.py" "$URL")"
YT_COMMON_ARGS+=(--socket-timeout 15 --retries 1 --extractor-retries 1
  --referer 'https://www.xiaohongshu.com/')

run_subtitle_mode() {
  local marker subtitle_file code=0
  echo 'pipeline_stage=subtitle_download' >&2
  marker="$(mktemp "$OUT_DIR/.subtitle-marker.XXXXXX")"
  yt_common_run --skip-download --write-subs --write-auto-subs --sub-langs all \
    --sub-format 'vtt/srt' "$SOURCE_URL" || code=$?
  subtitle_file="$(yt_common_find_new_subtitle_file "$OUT_DIR" "$marker")"
  rm -f "$marker"
  [[ "$code" -eq 0 ]] || return "$code"
  if [[ -z "$subtitle_file" ]]; then
    echo 'diagnostic_code=xiaohongshu_subtitles_not_exposed' >&2
    echo '未获得独立字幕；auto 模式将回退内置 whisper.cpp。笔记描述不作为转写。' >&2
    return 1
  fi
  yt_common_subtitle_to_text "$subtitle_file" "${subtitle_file%.*}.txt"
  echo "text_file=${subtitle_file%.*}.txt"
}

case "$MODE" in
  dryrun) yt_common_mode_dryrun "$SOURCE_URL" ;;
  video) yt_common_mode_video "$SOURCE_URL" ;;
  audio) yt_common_mode_audio "$SOURCE_URL" ;;
  subtitle) run_subtitle_mode ;;
  whisper)
    yt_common_run_whisper_mode_from_url "$SOURCE_URL" "$OUT_DIR" \
      "$SCRIPT_DIR/lib/whispercpp_transcribe.sh" "$LANGUAGE" "$PROFILE"
    ;;
esac
