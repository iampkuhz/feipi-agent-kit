#!/usr/bin/env bash

# yt-dlp 通用能力（仓库级共享）：
# - 依赖检查
# - 通用命令组装（输出模板、cookies）
# - 通用模式（dryrun/audio/video）
# - 字幕转文本
# - whisper 模式的公共流程

YT_COMMON_ARGS=()
YT_COMMON_AUTH_ARGS=()

yt_common_require_tools() {
  local mode="${1:-video}"

  if ! command -v yt-dlp >/dev/null 2>&1; then
    echo "缺少依赖: yt-dlp" >&2
    echo "安装示例: brew install yt-dlp" >&2
    return 1
  fi

  if [[ "$mode" =~ ^(video|audio|whisper)$ ]] && ! command -v ffmpeg >/dev/null 2>&1; then
    echo "缺少依赖: ffmpeg" >&2
    echo "安装示例: brew install ffmpeg" >&2
    return 1
  fi

  return 0
}

yt_common_init() {
  local out_dir="$1"
  local chrome_profile="${2:-}"

  mkdir -p "$out_dir"

  YT_COMMON_ARGS=(
    --no-playlist
    --restrict-filenames
    --output "$out_dir/%(title).200B [%(id)s].%(ext)s"
  )

  YT_COMMON_AUTH_ARGS=()
  if [[ -n "$chrome_profile" ]]; then
    YT_COMMON_AUTH_ARGS+=(--cookies-from-browser "$chrome_profile")
  fi
}

yt_common_run_cmd() {
  local err_file="$1"
  shift

  local -a cmd
  cmd=(yt-dlp "${YT_COMMON_ARGS[@]}")
  if [[ ${#YT_COMMON_AUTH_ARGS[@]} -gt 0 ]]; then
    cmd+=("${YT_COMMON_AUTH_ARGS[@]}")
  fi
  cmd+=("$@")

  if [[ -n "$err_file" ]]; then
    "${cmd[@]}" 2>"$err_file"
  else
    "${cmd[@]}"
  fi
}

yt_common_run() {
  local err_file
  err_file="$(mktemp)"

  if yt_common_run_cmd "$err_file" "$@"; then
    rm -f "$err_file"
    return 0
  fi

  if type yt_common_on_error >/dev/null 2>&1; then
    if yt_common_on_error "$err_file" "$@"; then
      rm -f "$err_file"
      return 0
    fi
  fi

  cat "$err_file" >&2
  rm -f "$err_file"
  return 1
}

yt_common_try() {
  local err_file
  err_file="$(mktemp)"

  if yt_common_run_cmd "$err_file" "$@"; then
    rm -f "$err_file"
    return 0
  fi

  if type yt_common_on_error >/dev/null 2>&1; then
    if yt_common_on_error "$err_file" "$@"; then
      rm -f "$err_file"
      return 0
    fi
  fi

  rm -f "$err_file"
  return 1
}

yt_common_mode_dryrun() {
  local url="$1"
  yt_common_run --simulate --print title --print id "$url"
}

yt_common_mode_audio() {
  local url="$1"
  yt_common_run \
    --format "bestaudio/best" \
    --extract-audio \
    --audio-format mp3 \
    --audio-quality 0 \
    "$url"
}

yt_common_mode_whisper_audio() {
  local url="$1"
  # 转写优先速度：优先拉取中低码率音频，减小下载与后续转写耗时。
  yt_common_run \
    --format "bestaudio[abr<=96]/bestaudio/best" \
    --extract-audio \
    --audio-format mp3 \
    --audio-quality 7 \
    "$url"
}

yt_common_mode_video() {
  local url="$1"
  yt_common_run \
    --format "bv*+ba/b" \
    --merge-output-format mp4 \
    "$url"
}

yt_common_find_new_audio_file() {
  local out_dir="$1"
  local marker="$2"

  find "$out_dir" -type f -name '*.mp3' -newer "$marker" | sort | head -n1 || true
}

yt_common_rank_subtitle_file() {
  local file="$1"
  local base stem lang_tag

  base="$(basename "$file")"
  stem="${base%.*}"
  lang_tag="${stem##*.}"

  case "$lang_tag" in
    zh|zh-*|cmn|cmn-*)
      echo "01"
      ;;
    en|en-*|en-orig)
      echo "02"
      ;;
    *-en)
      echo "03"
      ;;
    *)
      echo "09"
      ;;
  esac
}

yt_common_find_new_subtitle_file() {
  local out_dir="$1"
  local marker="$2"
  local file rank

  while IFS= read -r file; do
    rank="$(yt_common_rank_subtitle_file "$file")"
    printf "%s\t%s\n" "$rank" "$file"
  done < <(find "$out_dir" -type f \( -name '*.vtt' -o -name '*.srt' \) -newer "$marker" | sort) \
    | sort -t $'\t' -k1,1 -k2,2 \
    | head -n1 \
    | cut -f2- || true
}

yt_common_find_new_danmaku_file() {
  local out_dir="$1"
  local marker="$2"

  find "$out_dir" -type f -name '*.danmaku.xml' -newer "$marker" | sort | head -n1 || true
}

yt_common_subtitle_to_text() {
  local subtitle_file="$1"
  local text_file="$2"
  awk '
    BEGIN {
      IGNORECASE=1
      current_ts=""
      last_out_ts=""
    }
    /^[[:space:]]*$/ { next }
    /^WEBVTT/ { next }
    /^NOTE/ { next }
    /^[0-9]+$/ { next }
    /-->/ {
      ts=$1
      gsub(/,/, ".", ts)
      gsub(/[[:space:]]/, "", ts)
      split(ts, a, ":")
      if (length(a)==3) {
        current_ts=sprintf("%02d:%02d:%02d", a[1]+0, a[2]+0, int(a[3]))
      } else if (length(a)==2) {
        current_ts=sprintf("%02d:%02d", a[1]+0, a[2]+0)
      } else {
        current_ts="00:00"
      }
      next
    }
    {
      line=$0
      gsub(/\r/, "", line)
      gsub(/<[^>]*>/, "", line)
      gsub(/[[:space:]]+/, " ", line)
      sub(/^[[:space:]]+/, "", line)
      sub(/[[:space:]]+$/, "", line)
      if (line=="") next
      if (line ~ /^(Kind:|Language:|Source:|Style:)/) next
      if (current_ts=="") current_ts="00:00"
      if (current_ts != last_out_ts) {
        print "- [" current_ts "] " line
        last_out_ts=current_ts
      } else {
        print "  " line
      }
    }
  ' "$subtitle_file" > "$text_file"
}

yt_common_run_whisper_mode_from_url() {
  local url="$1"
  local out_dir="$2"
  local whisper_helper="$3"
  local language="${4:-zh}"
  local whisper_profile="${5:-auto}"

  local marker audio_file base text_file srt_file output_prefix
  local audio_download_log
  local transcribe_log used_device used_model used_profile requested_profile
  local run_code

  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "whisper 模式当前仅支持 macOS。" >&2
    return 1
  fi

  if [[ ! -x "$whisper_helper" ]]; then
    echo "缺少共享转写脚本: $whisper_helper" >&2
    return 1
  fi

  marker="$(mktemp "$out_dir/.audio-marker.XXXXXX")"
  audio_download_log="$(mktemp "$out_dir/.audio-download-log.XXXXXX")"
  if ! yt_common_mode_whisper_audio "$url" >"$audio_download_log" 2>&1; then
    cat "$audio_download_log" >&2
    rm -f "$audio_download_log"
    rm -f "$marker"
    return 1
  fi
  cat "$audio_download_log"

  audio_file="$(yt_common_find_new_audio_file "$out_dir" "$marker")"

  # 若文件已存在，yt-dlp 可能不会生成“新文件”；从日志回填音频路径。
  if [[ -z "$audio_file" ]]; then
    audio_file="$(sed -nE \
      -e 's#^\[download\] Destination: (.*\.mp3)$#\1#p' \
      -e 's#^\[download\] (.*\.mp3) has already been downloaded$#\1#p' \
      -e 's#^\[ExtractAudio\] Destination: (.*\.mp3)$#\1#p' \
      -e 's#^\[ExtractAudio\] Not converting audio (.*\.mp3);.*$#\1#p' \
      "$audio_download_log" | tail -n1)"
    if [[ -n "$audio_file" && ! -f "$audio_file" ]]; then
      audio_file=""
    fi
  fi

  rm -f "$audio_download_log"
  rm -f "$marker"

  if [[ -z "$audio_file" ]]; then
    echo "whisper 模式失败：未找到新生成的 mp3 文件。" >&2
    return 1
  fi

  base="$(basename "${audio_file%.*}")"
  output_prefix="$out_dir/$base"
  srt_file="$output_prefix.srt"
  text_file="$output_prefix.txt"
  rm -f "$srt_file" "$text_file"

  transcribe_log="$(mktemp "$out_dir/.whispercpp-log.XXXXXX")"
  set +e
  bash "$whisper_helper" "$audio_file" "$output_prefix" "$language" "$whisper_profile" >"$transcribe_log" 2>&1
  run_code=$?
  set -e
  cat "$transcribe_log"
  if [[ $run_code -ne 0 ]]; then
    rm -f "$transcribe_log"
    return 1
  fi
  used_device="$(sed -n 's/^device=//p' "$transcribe_log" | tail -n1)"
  used_model="$(sed -n 's/^model=//p' "$transcribe_log" | tail -n1)"
  used_profile="$(sed -n 's/^profile=//p' "$transcribe_log" | tail -n1)"
  requested_profile="$(sed -n 's/^requested_profile=//p' "$transcribe_log" | tail -n1)"
  rm -f "$transcribe_log"
  if [[ -z "$used_device" ]]; then
    used_device="unknown"
  fi
  if [[ -z "$used_profile" ]]; then
    used_profile="unknown"
  fi
  if [[ -z "$requested_profile" ]]; then
    requested_profile="$whisper_profile"
  fi
  if [[ -z "$used_model" ]]; then
    used_model="unknown"
  fi

  if [[ ! -f "$srt_file" ]]; then
    echo "whisper.cpp 已执行，但未找到转写结果: $srt_file" >&2
    return 1
  fi

  yt_common_subtitle_to_text "$srt_file" "$text_file"
  echo "requested_profile=$requested_profile"
  echo "profile=$used_profile"
  echo "model=$used_model"
  echo "device=$used_device"
  echo "audio_file=$audio_file"
  echo "text_file=$text_file"
}
