#!/usr/bin/env bash
# 复用已安装的视频 skill，并将块级转写还原为语音消息正文。
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo '用法：transcribe-audio-omlx.sh <音频文件>' >&2
  exit 2
fi

STATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENTRY="$STATE_DIR/skills/feipi-video-read-url/scripts/extract_video_text.sh"
if [[ ! -f "$ENTRY" ]]; then
  echo '缺少 feipi-video-read-url，请用 workbench install skills --agent openclaw --skill feipi-video-read-url 安装。' >&2
  exit 1
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/openclaw-omlx.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT
if ! bash "$ENTRY" "$1" "$WORK_DIR" whisper >"$WORK_DIR/result.log"; then
  exit 1
fi
TEXT_PATH="$(sed -n 's/^text_path=//p' "$WORK_DIR/result.log")"
python3 - "$TEXT_PATH" <<'TRANSCRIPT'
import json
from pathlib import Path
import sys

with Path(sys.argv[1]).with_suffix(".asr.json").open(encoding="utf-8") as source:
    record = json.load(source)
for chunk in record["chunks"]:
    if chunk["text"]:
        print(chunk["text"])
TRANSCRIPT
