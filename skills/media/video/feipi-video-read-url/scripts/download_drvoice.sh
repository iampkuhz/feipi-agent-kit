#!/usr/bin/env bash
set -euo pipefail
URL="${1:-}"
OUT_DIR="${2:-./downloads}"
MODE="${3:-video}"
LANGUAGE="${AGENT_VIDEO_LANGUAGE:-auto}"
if [[ -z "$URL" || $# -gt 3 ]]; then
  echo "用法：bash scripts/download_drvoice.sh <url> [output_dir] [mode]" >&2
  exit 1
fi
case "$LANGUAGE" in auto|zh|en) ;; *) echo 'AGENT_VIDEO_LANGUAGE 仅支持 auto|zh|en' >&2; exit 1;; esac
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$MODE" in dryrun|video|audio|subtitle|whisper) ;; *) echo 'mode 无效' >&2; exit 1;; esac
mkdir -p "$OUT_DIR"
trap 'rm -f "$OUT_DIR/.drvoice-media-url"' EXIT
python3 "$SCRIPT_DIR/lib/drvoice_metadata.py" "$URL" "$OUT_DIR"
if [[ "$MODE" == dryrun ]]; then exit 0; fi
if [[ "$MODE" == subtitle ]]; then
  echo 'diagnostic_code=drvoice_subtitles_not_exposed' >&2
  exit 1
fi
command -v ffmpeg >/dev/null
MEDIA_URL="$(cat "$OUT_DIR/.drvoice-media-url")"
VIDEO="$OUT_DIR/video.mp4"
if [[ ! -s "$VIDEO" ]]; then
  ffmpeg -nostdin -v error -y -rw_timeout 30000000 -i "$MEDIA_URL" -c copy -movflags +faststart "$OUT_DIR/video.partial.mp4"
  mv "$OUT_DIR/video.partial.mp4" "$VIDEO"
fi
if [[ "$MODE" == video ]]; then echo "video_file=$VIDEO"; exit 0; fi
AUDIO="$OUT_DIR/audio.whisper.wav"
if [[ -s "$AUDIO" ]]; then
  # 流式重解码比较PCM，不重写已归档音频；不匹配时停止，保留原件待查。
  python3 "$SCRIPT_DIR/lib/verify_cached_audio.py" "$VIDEO" "$AUDIO" "$OUT_DIR/audio_cache_validation.json"
  echo "audio_cache=verified_reused"
else
  ffmpeg -nostdin -v error -y -i "$VIDEO" -vn -ac 1 -ar 16000 -c:a pcm_s16le "$AUDIO"
fi
if [[ "$MODE" == audio ]]; then echo "audio_file=$AUDIO"; exit 0; fi
python3 "$SCRIPT_DIR/lib/omlx_transcribe.py" "$AUDIO" "$OUT_DIR/transcript" "$LANGUAGE"
python3 "$SCRIPT_DIR/lib/subtitle_to_text.py" "$OUT_DIR/transcript.srt" "$OUT_DIR/transcript.txt"
echo "text_file=$OUT_DIR/transcript.txt"
