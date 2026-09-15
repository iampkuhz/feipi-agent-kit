#!/usr/bin/env bash

# yt-dlp 通用能力（仓库级共享）：
# - 依赖检查
# - 通用命令组装（输出模板、cookies）
# - 通用模式（dryrun/audio/video）
# - 字幕转文本
# - whisper 模式的公共流程

YT_COMMON_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

YT_COMMON_ARGS=()
YT_COMMON_AUTH_ARGS=()
YT_DLP_STALE_AFTER_DAYS=90
YT_DLP_BIN=""
YT_DLP_VERSION=""
YT_DLP_SELECTION_REASON=""
YT_DLP_CANDIDATES=()

yt_common_add_ytdlp_candidate() {
  local candidate="$1"
  local existing

  [[ -n "$candidate" && -x "$candidate" && ! -d "$candidate" ]] || return 0
  if [[ "$candidate" != /* ]]; then
    candidate="$(cd "$(dirname "$candidate")" && pwd)/${candidate##*/}"
  fi
  for existing in "${YT_DLP_CANDIDATES[@]-}"; do
    [[ "$existing" == "$candidate" ]] && return 0
  done
  YT_DLP_CANDIDATES+=("$candidate")
}

# 稳定版日期、nightly 的六位构建号及明确的打包后缀；不从任意输出提取数字。
yt_common_version_key() {
  local version="$1"
  if [[ "$version" =~ ^([0-9]{4})\.([0-9]{2})\.([0-9]{2})(\.([0-9]{6}))?([+-][a-zA-Z0-9._-]+)?$ ]]; then
    printf '%s.%s.%s.%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" "${BASH_REMATCH[5]:-0}"
  else
    return 1
  fi
}

yt_common_version_is_newer() {
  local candidate_clean baseline_clean idx candidate_part baseline_part
  local -a candidate_parts baseline_parts
  candidate_clean="$(yt_common_version_key "$1")" || return 1
  [[ -z "$2" ]] && return 0
  baseline_clean="$(yt_common_version_key "$2")" || return 0
  IFS='.' read -r -a candidate_parts <<< "$candidate_clean"
  IFS='.' read -r -a baseline_parts <<< "$baseline_clean"
  for idx in 0 1 2 3; do
    candidate_part="${candidate_parts[$idx]}"
    baseline_part="${baseline_parts[$idx]}"
    (( 10#$candidate_part > 10#$baseline_part )) && return 0
    (( 10#$candidate_part < 10#$baseline_part )) && return 1
  done
  return 1
}

# 自动选择可用候选中的最高版本：PATH 候选与已安装 Homebrew formula 都会参与，
# 但不会改写用户环境、安装软件或依赖固定 Homebrew 路径。
yt_common_select_ytdlp() {
  local path_candidate brew_prefix candidate candidate_version
  local selected_bin="" selected_version="" candidate_count=0

  YT_DLP_BIN=""
  YT_DLP_VERSION=""
  YT_DLP_SELECTION_REASON=""
  YT_DLP_CANDIDATES=()
  while IFS= read -r path_candidate; do
    yt_common_add_ytdlp_candidate "$path_candidate"
  done < <(type -a -p yt-dlp 2>/dev/null || true)

  if command -v brew >/dev/null 2>&1; then
    brew_prefix="$(brew --prefix yt-dlp 2>/dev/null || true)"
    yt_common_add_ytdlp_candidate "${brew_prefix:+$brew_prefix/bin/yt-dlp}"
  fi

  for candidate in "${YT_DLP_CANDIDATES[@]-}"; do
    [[ -n "$candidate" ]] || continue
    if ! candidate_version="$("$candidate" --version 2>/dev/null)"; then
      echo "yt_dlp_candidate_rejected=$candidate|version_command_failed" >&2
      continue
    fi
    if ! yt_common_version_key "$candidate_version" >/dev/null; then
      echo "yt_dlp_candidate_rejected=$candidate|unrecognized_version" >&2
      continue
    fi
    echo "yt_dlp_candidate=$candidate|$candidate_version" >&2
    candidate_count=$((candidate_count + 1))
    if [[ -z "$selected_bin" ]] || yt_common_version_is_newer "$candidate_version" "$selected_version"; then
      selected_bin="$candidate"
      selected_version="$candidate_version"
    fi
  done

  if [[ -z "$selected_bin" ]]; then
    echo "缺少可运行且版本可识别的依赖: yt-dlp" >&2
    echo "安装示例: brew install yt-dlp" >&2
    return 1
  fi

  YT_DLP_BIN="$selected_bin"
  YT_DLP_VERSION="$selected_version"
  if [[ "$candidate_count" -gt 1 ]]; then
    YT_DLP_SELECTION_REASON="highest_detected_version"
  else
    YT_DLP_SELECTION_REASON="only_detected_candidate"
  fi
}

# yt-dlp 的版本通常是 YYYY.MM.DD；YouTube 的提取规则变化较快，超过 90 天的
# 版本只标记为过旧，不在执行中静默升级或改写 PATH。
yt_common_release_epoch() {
  local release_date="$1"

  date -j -f "%Y-%m-%d" "$release_date" +%s 2>/dev/null \
    || date -d "$release_date" +%s 2>/dev/null \
    || true
}

yt_common_report_ytdlp_provenance() {
  local ytdlp_path ytdlp_version release_date release_epoch now_epoch age_days

  ytdlp_path="$YT_DLP_BIN"
  ytdlp_version="$YT_DLP_VERSION"
  echo "yt_dlp_path=$ytdlp_path" >&2
  echo "yt_dlp_version=$ytdlp_version" >&2
  echo "yt_dlp_selection_reason=$YT_DLP_SELECTION_REASON" >&2

  if [[ "$ytdlp_version" =~ ^([0-9]{4})\.([0-9]{2})\.([0-9]{2}) ]]; then
    release_date="${BASH_REMATCH[1]}-${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
    release_epoch="$(yt_common_release_epoch "$release_date")"
    now_epoch="$(date +%s)"
    if [[ "$release_epoch" =~ ^[0-9]+$ && "$now_epoch" =~ ^[0-9]+$ && "$now_epoch" -ge "$release_epoch" ]]; then
      age_days=$(( (now_epoch - release_epoch) / 86400 ))
      echo "yt_dlp_release_date=$release_date" >&2
      echo "yt_dlp_age_days=$age_days" >&2
      if [[ "$age_days" -gt "$YT_DLP_STALE_AFTER_DAYS" ]]; then
        echo "yt_dlp_stale=1" >&2
        echo "yt-dlp 版本已超过 ${YT_DLP_STALE_AFTER_DAYS} 天；不会自动升级。若 YouTube 媒体下载失败，请按当前安装来源更新后，使用同一统一入口重试。" >&2
      else
        echo "yt_dlp_stale=0" >&2
      fi
      return 0
    fi
  fi

  echo "yt_dlp_release_date=unknown" >&2
  echo "yt_dlp_age_days=unknown" >&2
  echo "yt_dlp_stale=unknown" >&2
}

yt_common_require_tools() {
  local mode="${1:-video}"

  if ! yt_common_select_ytdlp; then
    return 1
  fi

  if [[ "$mode" =~ ^(video|audio|whisper)$ ]] && ! command -v ffmpeg >/dev/null 2>&1; then
    echo "缺少依赖: ffmpeg" >&2
    echo "安装示例: brew install ffmpeg" >&2
    return 1
  fi

  if [[ "$mode" =~ ^(subtitle|whisper)$ ]] && ! command -v python3 >/dev/null 2>&1; then
    echo "缺少依赖: python3，请运行 scripts/install_deps.sh" >&2
    return 1
  fi

  # 记录当前进程实际命中的程序及版本新鲜度，避免同机多个版本造成误判。
  yt_common_report_ytdlp_provenance
  return 0
}

# 仅清理输出副本；错误判断仍读取原始 stderr，避免脱敏影响重试策略。
yt_common_print_diagnostic() {
  LC_ALL=C sed -E 's#https?://[^[:space:]]+#<url-redacted>#g' "$1"
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
  cmd=("${YT_DLP_BIN:-yt-dlp}" "${YT_COMMON_ARGS[@]}")
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
  echo "pipeline_stage=text_conversion" >&2
  python3 "$YT_COMMON_LIB_DIR/subtitle_to_text.py" "$1" "$2"
}

# 从当前尝试中取最后推进到的阶段，历史错误不能覆盖已经恢复的步骤。
yt_common_last_stage() {
  LC_ALL=C sed -n 's/^pipeline_stage=//p' "$1" | tail -n1
}

# 只接收本轮最后一次失败的日志；已恢复阶段的 warning 只作为历史保留。
yt_common_report_youtube_failure() {
  local log_file="$1" stage stale po_token=0
  [[ -f "$log_file" ]] || return 1
  stage="$(yt_common_last_stage "$log_file")"
  stage="${stage:-unknown}"
  echo "failure_log=$log_file" >&2
  echo "failure_stage=$stage" >&2
  if [[ "$stage" != "media_download" ]] || ! rg -aqi 'HTTP Error 403|403 Forbidden|Requested format is not available|Only images are available' "$log_file"; then
    echo "diagnostic_code=youtube_text_extraction_failed" >&2
    echo "retry_action=inspect_current_youtube_log" >&2
    return 0
  fi
  stale="$(LC_ALL=C sed -n 's/^yt_dlp_stale=//p' "$log_file" | tail -n1)"
  case "$stale" in 0|1) ;; *) stale=unknown ;; esac
  if rg -aqi 'GVS PO Token' "$log_file"; then
    po_token=1
  fi
  echo "diagnostic_code=youtube_media_download_blocked" >&2
  echo "yt_dlp_stale=$stale" >&2
  echo "gvs_po_token_observed=$po_token" >&2
  if [[ "$stale" == "1" ]]; then
    echo "retry_action=update_yt_dlp_then_rerun_same_unified_command" >&2
    echo "说明：当前 yt-dlp 版本过旧，请按实际安装来源更新后重跑同一统一入口。" >&2
  else
    echo "retry_action=inspect_current_youtube_log" >&2
    if [[ "$po_token" == "1" ]]; then
      echo "说明：某客户端出现 PO Token 提示，不代表整条链路必须提供 Token；请结合最终错误检查。" >&2
    fi
  fi
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

  echo "pipeline_stage=dependency" >&2
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
        existing_profile="$(LC_ALL=C sed -n 's/^profile=//p' "$existing_meta" | tail -n1)"
        existing_model="$(LC_ALL=C sed -n 's/^model=//p' "$existing_meta" | tail -n1)"
      fi

      # accurate 请求必须复用来源匹配的结果；若 meta 缺失或不匹配，不复用。
      # fast 请求可以复用任意来源的结果（降级可接受）。
      if [[ "$whisper_profile" == "accurate" ]]; then
        if [[ "$existing_profile" == "accurate" ]]; then
          base="$(basename "${existing_wav%.whisper.wav}")"
          output_prefix="$out_dir/$base"
          text_file="$output_prefix.txt"
          yt_common_subtitle_to_text "$existing_srt" "$text_file" || return 1
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
        yt_common_subtitle_to_text "$existing_srt" "$text_file" || return 1
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

  echo "pipeline_stage=media_download" >&2
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
    audio_file="$(LC_ALL=C sed -nE \
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

  echo "pipeline_stage=audio_conversion" >&2
  transcribe_audio_file="$out_dir/$base.whisper.wav"
  rm -f "$transcribe_audio_file"
  echo "转换音频为 whisper.cpp 兼容 WAV: $transcribe_audio_file" >&2
  if ! ffmpeg -y -hide_banner -loglevel error -i "$audio_file" -ar 16000 -ac 1 -f wav "$transcribe_audio_file" >&2; then
    echo "whisper 模式失败：音频转 WAV 失败: $audio_file" >&2
    return 1
  fi

  echo "pipeline_stage=transcription" >&2
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
  used_device="$(LC_ALL=C sed -n 's/^device=//p' "$transcribe_log" | tail -n1)"
  used_model="$(LC_ALL=C sed -n 's/^model=//p' "$transcribe_log" | tail -n1)"
  used_profile="$(LC_ALL=C sed -n 's/^profile=//p' "$transcribe_log" | tail -n1)"
  requested_profile="$(LC_ALL=C sed -n 's/^requested_profile=//p' "$transcribe_log" | tail -n1)"
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

  yt_common_subtitle_to_text "$srt_file" "$text_file" || return 1
  echo "requested_profile=$requested_profile"
  echo "profile=$used_profile"
  echo "model=$used_model"
  echo "device=$used_device"
  echo "audio_file=$audio_file"
  echo "transcribe_audio_file=$transcribe_audio_file"
  echo "text_file=$text_file"
}
