#!/usr/bin/env bash
# 直接运行 whisper.cpp；GPU 失败时使用同一模型回退 CPU。
set -euo pipefail
if [[ $# -lt 1 || ! -f "$1" ]]; then
  echo 'usage: transcribe-audio-whispercpp-openclaw.sh AUDIO [zh] [accurate|fast|auto]' >&2
  exit 2
fi
AUDIO_FILE="$1"
LANGUAGE="${2:-zh}"
PROFILE="${3:-accurate}"
FFMPEG_BIN="${FFMPEG_BIN:-/opt/homebrew/bin/ffmpeg}"
WHISPERCPP_BIN="${WHISPERCPP_BIN:-/opt/homebrew/bin/whisper-cli}"
case "$PROFILE" in
  accurate|auto) MODEL="${WHISPERCPP_MODEL_ACCURATE:-$HOME/Library/Caches/whisper.cpp/models/ggml-large-v3.bin}" ;;
  fast) MODEL="${WHISPERCPP_MODEL_FAST:-$HOME/Library/Caches/whisper.cpp/models/ggml-base.bin}" ;;
  *) echo 'unknown transcription profile' >&2; exit 2 ;;
esac
if [[ ! -x "$FFMPEG_BIN" || ! -x "$WHISPERCPP_BIN" || ! -f "$MODEL" ]]; then
  echo '缺少 ffmpeg、whisper-cli 或指定模型；不自动降级到小模型。' >&2
  exit 1
fi
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/openclaw-whispercpp.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT
"$FFMPEG_BIN" -nostdin -y -i "$AUDIO_FILE" -ar 16000 -ac 1 -c:a pcm_s16le "$WORK_DIR/input.wav" >"$WORK_DIR/ffmpeg.log" 2>&1
ARGS=(-m "$MODEL" -f "$WORK_DIR/input.wav" -l "$LANGUAGE" -t 4 -otxt -of "$WORK_DIR/transcript" -nt)
if [[ -n "${WHISPERCPP_PROMPT:-}" ]]; then ARGS+=(--prompt "$WHISPERCPP_PROMPT"); fi
if ! "$WHISPERCPP_BIN" "${ARGS[@]}" >"$WORK_DIR/recognition.log" 2>&1; then
  if ! "$WHISPERCPP_BIN" "${ARGS[@]}" -ng >"$WORK_DIR/recognition.log" 2>&1; then
    tail -n 12 "$WORK_DIR/recognition.log" >&2
    exit 1
  fi
fi
if [[ ! -s "$WORK_DIR/transcript.txt" ]]; then
  echo '语音识别没有生成文字，保留原音频等待重试。' >&2
  exit 1
fi
cat "$WORK_DIR/transcript.txt"
