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

  # 记录当前进程实际命中的程序，避免同机多个版本造成误判。
  echo "yt_dlp_path=$(command -v yt-dlp)" >&2
  echo "yt_dlp_version=$(yt-dlp --version 2>/dev/null || echo unknown)" >&2
  return 0
}

# 仅清理输出副本；错误判断仍读取原始 stderr，避免脱敏影响重试策略。
yt_common_print_diagnostic() {
  sed -E 's#https?://[^[:space:]]+#<url-redacted>#g' "$1"
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
    local attempt_code=0
    "${cmd[@]}" 2>"$err_file" || attempt_code=$?
    # 每次失败立即进入来源日志，后续重试覆盖 err_file 也不会丢失历史。
    if [[ "$attempt_code" -ne 0 ]]; then
      echo "yt_dlp_attempt_exit=$attempt_code" >&2
      yt_common_print_diagnostic "$err_file" >&2
    fi
    return "$attempt_code"
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

  yt_common_print_diagnostic "$err_file" >&2
  rm -f "$err_file"
  return 1
}

# 与 yt_common_run 的区别：成功时将 err_file 输出到 stdout。
# 仅用于音频下载链路，便于从日志中回填音频文件路径。
yt_common_run_with_success_log() {
  local err_file
  err_file="$(mktemp)"

  if yt_common_run_cmd "$err_file" "$@"; then
    yt_common_print_diagnostic "$err_file"
    rm -f "$err_file"
    return 0
  fi

  if type yt_common_on_error >/dev/null 2>&1; then
    if yt_common_on_error "$err_file" "$@"; then
      yt_common_print_diagnostic "$err_file"
      rm -f "$err_file"
      return 0
    fi
  fi

  yt_common_print_diagnostic "$err_file" >&2
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
  yt_common_run_with_success_log \
    --format "bestaudio[abr<=96]/bestaudio/best" \
    --extract-audio \
    --audio-format mp3 \
    --audio-quality 7 \
    "$url"
}

yt_common_mode_whisper_audio_with_format_fallback() {
  local url="$1"
  # 最多 2 次 format 尝试：优先低码率音频，再回退 18（通常含音频的 mp4）。
  # 不再尝试第 3 种 "best"，以避免重复下载增加耗时。
  local -a format_variants=(
    "bestaudio[abr<=96]/bestaudio"
    "18"
  )
  local format_var log_file

  for format_var in "${format_variants[@]}"; do
    echo "yt_common_whisper_audio: 尝试 format=\"$format_var\"" >&2
    log_file="$(mktemp)"
    if yt_common_run_with_success_log \
      --format "$format_var" \
      --extract-audio \
      --audio-format mp3 \
      --audio-quality 7 \
      "$url" >"$log_file" 2>&1; then
      cat "$log_file"
      rm -f "$log_file"
      return 0
    fi

    if rg -qi "403|HTTP Error|Requested format is not available|Only images" "$log_file"; then
      echo "yt_common_whisper_audio: format=$format_var 下载失败" >&2
    fi
    yt_common_print_diagnostic "$log_file" >&2
    rm -f "$log_file"
  done

  return 1
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
  local audio_download_fn="${6:-yt_common_mode_whisper_audio}"

  local marker audio_file transcribe_audio_file base text_file srt_file output_prefix
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

  # 残留产物处理：若已存在完整的 whisper 转写结果，检查 metadata 侧车
  # 文件再决定是否复用，避免 accurate 请求静默复用 fast 结果。
  local existing_wav existing_srt existing_meta existing_profile existing_model
  existing_wav="$(find "$out_dir" -maxdepth 1 -name '*.whisper.wav' -type f 2>/dev/null | sort | tail -n1 || true)"
  if [[ -n "$existing_wav" && -f "$existing_wav" ]]; then
    existing_srt="${existing_wav%.whisper.wav}.srt"
    existing_meta="${existing_wav%.whisper.wav}.meta"
    if [[ -f "$existing_srt" ]]; then
      existing_profile=""
      existing_model=""
      if [[ -f "$existing_meta" ]]; then
        existing_profile="$(sed -n 's/^profile=//p' "$existing_meta" | tail -n1)"
        existing_model="$(sed -n 's/^model=//p' "$existing_meta" | tail -n1)"
      fi

      # accurate 请求必须复用来源匹配的结果；若 meta 缺失或不匹配，不复用。
      # fast 请求可以复用任意来源的结果（降级可接受）。
      if [[ "$whisper_profile" == "accurate" ]]; then
        if [[ "$existing_profile" == "accurate" ]]; then
          base="$(basename "${existing_wav%.whisper.wav}")"
          output_prefix="$out_dir/$base"
          text_file="$output_prefix.txt"
          if [[ ! -f "$text_file" ]]; then
            yt_common_subtitle_to_text "$existing_srt" "$text_file"
          fi
          echo "复用已有 accurate whisper 转写结果: wav=$existing_wav, model=${existing_model:-unknown}" >&2
          echo "requested_profile=$whisper_profile"
          echo "profile=reused"
          echo "model=${existing_model:-reused}"
          echo "device=reused"
          echo "audio_file=reused"
          echo "transcribe_audio_file=$existing_wav"
          echo "text_file=$text_file"
          return 0
        else
          echo "准确模式请求，但已有转写为 ${existing_profile:-未知} 模式，不复用: $existing_srt" >&2
        fi
      else
        base="$(basename "${existing_wav%.whisper.wav}")"
        output_prefix="$out_dir/$base"
        text_file="$output_prefix.txt"
        if [[ ! -f "$text_file" ]]; then
          yt_common_subtitle_to_text "$existing_srt" "$text_file"
        fi
        echo "复用已有 whisper 转写结果（fast）: wav=$existing_wav, model=${existing_model:-unknown}" >&2
        echo "requested_profile=$whisper_profile"
        echo "profile=reused"
        echo "model=${existing_model:-reused}"
        echo "device=reused"
        echo "audio_file=reused"
        echo "transcribe_audio_file=$existing_wav"
        echo "text_file=$text_file"
        return 0
      fi
    fi
  fi

  # 仅清理孤立的 .whisper.wav（无匹配 .srt），这些是中断残留。
  local orphan
  while IFS= read -r -d '' orphan; do
    if [[ ! -f "${orphan%.whisper.wav}.srt" ]]; then
      echo "清理残留的孤立 WAV 文件: $orphan" >&2
      rm -f "$orphan"
    fi
  done < <(find "$out_dir" -maxdepth 1 -name '*.whisper.wav' -type f -print0 2>/dev/null)

  marker="$(mktemp "$out_dir/.audio-marker.XXXXXX")"
  audio_download_log="$(mktemp "$out_dir/.audio-download-log.XXXXXX")"

  if ! "$audio_download_fn" "$url" >"$audio_download_log" 2>&1; then
    cat "$audio_download_log" >&2
    rm -f "$audio_download_log"
    rm -f "$marker"
    return 1
  fi
  cat "$audio_download_log"

  audio_file="$(yt_common_find_new_audio_file "$out_dir" "$marker")"

  # 若文件已存在，yt-dlp 可能不会生成"新文件"；从日志回填音频路径。
  if [[ -z "$audio_file" ]]; then
    audio_file="$(sed -nE \
      -e 's#^\[download\] Destination: (.*)$#\1#p' \
      -e 's#^\[download\] (.*) has already been downloaded$#\1#p' \
      -e 's#^\[ExtractAudio\] Destination: (.*)$#\1#p' \
      -e 's#^\[ExtractAudio\] Not converting audio (.*)[; ].*$#\1#p' \
      "$audio_download_log" | grep '\.mp3$' | tail -n1)"
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

  transcribe_audio_file="$out_dir/$base.whisper.wav"
  rm -f "$transcribe_audio_file"
  echo "转换音频为 whisper.cpp 兼容 WAV: $transcribe_audio_file" >&2
  if ! ffmpeg -y -hide_banner -loglevel error -i "$audio_file" -ar 16000 -ac 1 -f wav "$transcribe_audio_file" >&2; then
    echo "whisper 模式失败：音频转 WAV 失败: $audio_file" >&2
    return 1
  fi

  transcribe_log="$(mktemp "$out_dir/.whispercpp-log.XXXXXX")"
  set +e
  bash "$whisper_helper" "$transcribe_audio_file" "$output_prefix" "$language" "$whisper_profile" >"$transcribe_log" 2>&1
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

  # 写入 metadata 侧车文件，供后续复用判断。
  local meta_file="${transcribe_audio_file%.whisper.wav}.meta"
  printf "profile=%s\nmodel=%s\nlanguage=%s\n" "$used_profile" "$used_model" "$language" > "$meta_file"

  yt_common_subtitle_to_text "$srt_file" "$text_file"
  echo "requested_profile=$requested_profile"
  echo "profile=$used_profile"
  echo "model=$used_model"
  echo "device=$used_device"
  echo "audio_file=$audio_file"
  echo "transcribe_audio_file=$transcribe_audio_file"
  echo "text_file=$text_file"
}
