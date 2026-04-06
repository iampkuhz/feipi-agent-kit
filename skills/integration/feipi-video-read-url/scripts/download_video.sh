#!/usr/bin/env bash
set -euo pipefail

URL="${1:-}"
OUT_DIR="${2:-./downloads}"
MODE="${3:-video}"
WHISPER_PROFILE="${4:-auto}"

usage() {
  cat <<'USAGE'
用法:
  bash scripts/download_video.sh <url> [output_dir] [mode] [whisper_profile]

参数:
  mode: dryrun | video | audio | subtitle | whisper
  whisper_profile: auto | fast | accurate
USAGE
}

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

if [[ -z "$URL" ]]; then
  usage
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$(detect_source "$URL")"

case "$SOURCE" in
  youtube)
    TARGET_SCRIPT="$SCRIPT_DIR/download_youtube.sh"
    ;;
  bilibili)
    TARGET_SCRIPT="$SCRIPT_DIR/download_bilibili.sh"
    ;;
  *)
    echo "未知来源: $SOURCE" >&2
    exit 1
    ;;
esac

if [[ ! -x "$TARGET_SCRIPT" ]]; then
  echo "缺少来源适配脚本或不可执行: $TARGET_SCRIPT" >&2
  exit 1
fi

echo "source=$SOURCE"
exec bash "$TARGET_SCRIPT" "$URL" "$OUT_DIR" "$MODE" "$WHISPER_PROFILE"
