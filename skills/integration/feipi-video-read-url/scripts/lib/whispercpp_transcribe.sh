#!/usr/bin/env bash
set -euo pipefail

# whisper.cpp 转写共享脚本（当前 skill 内置）
#
# 用法：
#   bash scripts/lib/whispercpp_transcribe.sh <audio_file> <output_prefix> [language] [accurate|fast|auto]
#
# 说明：
# - 支持质量档位：
#   - accurate: 质量优先（large-v3 q5_0），需显式指定
#   - fast: 速度优先（优先使用 turbo/small/base）
#   - auto: 默认速度优先，解析为 fast
# - 先尝试 Metal（GPU）；仅初始化阶段失败时自动回退 CPU
# - 输出文件：<output_prefix>.srt

AUDIO_FILE="${1:-}"
OUTPUT_PREFIX="${2:-}"
LANGUAGE="${3:-zh}"
REQUESTED_PROFILE="${4:-auto}"
RECOVERY_NO_CONTEXT="${AGENT_VIDEO_RECOVERY_NO_CONTEXT:-0}"

WHISPER_CPP_BIN_DEFAULT="/opt/homebrew/opt/whisper-cpp/bin/whisper-cli"
WHISPER_MODEL_DIR_DEFAULT="$HOME/Library/Caches/whisper.cpp/models"
WHISPER_MODEL_FILE_ACCURATE="$WHISPER_MODEL_DIR_DEFAULT/ggml-large-v3-q5_0.bin"
WHISPER_MODEL_URL_ACCURATE="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin"
WHISPER_MODEL_URL_FAST_SUGGEST="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
WHISPER_THREADS_ACCURATE=4
WHISPER_THREADS_FAST_MAX=8
WHISPER_PROCESSORS=1
WHISPER_BEAM_SIZE_ACCURATE=3
WHISPER_BEST_OF_ACCURATE=3
WHISPER_BEAM_SIZE_FAST=2
WHISPER_BEST_OF_FAST=2
WHISPER_METAL_CACHE_TTL_SEC=3600
WHISPER_METAL_CACHE_FILE="${TMPDIR:-/tmp}/whispercpp-metal-unavailable.cache"

usage() {
  echo "用法: bash scripts/lib/whispercpp_transcribe.sh <audio_file> <output_prefix> [language] [accurate|fast|auto]" >&2
}

if [[ -z "$AUDIO_FILE" || -z "$OUTPUT_PREFIX" ]]; then
  usage
  exit 1
fi

if [[ ! -f "$AUDIO_FILE" ]]; then
  echo "音频文件不存在: $AUDIO_FILE" >&2
  exit 1
fi

if [[ "$REQUESTED_PROFILE" != "auto" && "$REQUESTED_PROFILE" != "accurate" && "$REQUESTED_PROFILE" != "fast" ]]; then
  echo "profile 仅支持 accurate|fast|auto，当前: $REQUESTED_PROFILE" >&2
  exit 1
fi

case "$RECOVERY_NO_CONTEXT" in
  0|1) ;;
  *) echo "AGENT_VIDEO_RECOVERY_NO_CONTEXT 仅支持 0|1" >&2; exit 1 ;;
esac

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "当前脚本仅支持 macOS（whisper.cpp + Metal/CPU）。" >&2
  exit 1
fi

resolve_whisper_cpp_cli() {
  if [[ -x "$WHISPER_CPP_BIN_DEFAULT" ]]; then
    echo "$WHISPER_CPP_BIN_DEFAULT"
    return 0
  fi
  if command -v whisper-cli >/dev/null 2>&1; then
    command -v whisper-cli
    return 0
  fi
  return 1
}

resolve_metal_resources_dir() {
  local prefix
  if command -v brew >/dev/null 2>&1; then
    prefix="$(brew --prefix whisper-cpp 2>/dev/null || true)"
    if [[ -n "$prefix" && -d "$prefix/share/whisper-cpp" ]]; then
      echo "$prefix/share/whisper-cpp"
      return 0
    fi
  fi

  if [[ -d "/opt/homebrew/opt/whisper-cpp/share/whisper-cpp" ]]; then
    echo "/opt/homebrew/opt/whisper-cpp/share/whisper-cpp"
    return 0
  fi

  return 1
}

cache_mtime_epoch() {
  local path="$1"

  stat -f "%m" "$path" 2>/dev/null || echo 0
}

metal_cache_is_fresh() {
  local now_epoch cached_epoch

  if [[ ! -f "$WHISPER_METAL_CACHE_FILE" ]]; then
    return 1
  fi

  now_epoch="$(date +%s)"
  cached_epoch="$(cache_mtime_epoch "$WHISPER_METAL_CACHE_FILE")"
  if ! [[ "$cached_epoch" =~ ^[0-9]+$ ]]; then
    return 1
  fi

  if (( now_epoch - cached_epoch < WHISPER_METAL_CACHE_TTL_SEC )); then
    return 0
  fi

  return 1
}

record_metal_unavailable() {
  local reason="$1"

  printf "reason=%s\nts=%s\n" "$reason" "$(date +%s)" > "$WHISPER_METAL_CACHE_FILE"
}

clear_metal_unavailable_cache() {
  rm -f "$WHISPER_METAL_CACHE_FILE"
}

print_setup_guidance() {
  echo "whisper.cpp 需要以下环境：" >&2
  echo "1) 安装 whisper-cpp: brew install whisper-cpp" >&2
  echo "2) 下载质量模型（accurate，一次性）:" >&2
  echo "   mkdir -p \"$WHISPER_MODEL_DIR_DEFAULT\"" >&2
  echo "   curl -L --fail \"$WHISPER_MODEL_URL_ACCURATE\" -o \"$WHISPER_MODEL_FILE_ACCURATE\"" >&2
  echo "3) 建议额外下载快速模型（fast）:" >&2
  echo "   curl -L --fail \"$WHISPER_MODEL_URL_FAST_SUGGEST\" -o \"$WHISPER_MODEL_DIR_DEFAULT/ggml-base.bin\"" >&2
}

clamp_threads() {
  local wanted="$1"
  local detected="4"

  detected="$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)"
  if ! [[ "$detected" =~ ^[0-9]+$ ]]; then
    detected=4
  fi
  if [[ "$detected" -lt 1 ]]; then
    detected=1
  fi

  if [[ "$wanted" -gt "$detected" ]]; then
    echo "$detected"
    return 0
  fi

  echo "$wanted"
}

resolve_effective_profile() {
  if [[ "$REQUESTED_PROFILE" == "auto" ]]; then
    echo "fast"
    return 0
  fi
  echo "$REQUESTED_PROFILE"
}

resolve_fast_model_file() {
  local candidate
  local -a candidates=(
    "$WHISPER_MODEL_DIR_DEFAULT/ggml-large-v3-turbo-q5_0.bin"
    "$WHISPER_MODEL_DIR_DEFAULT/ggml-small.bin"
    "$WHISPER_MODEL_DIR_DEFAULT/ggml-base.bin"
  )

  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

WHISPER_CLI="$(resolve_whisper_cpp_cli || true)"
if [[ -z "$WHISPER_CLI" ]]; then
  echo "缺少依赖: whisper-cli（whisper.cpp）" >&2
  print_setup_guidance
  exit 1
fi

EFFECTIVE_PROFILE="$(resolve_effective_profile)"
WHISPER_MODEL_FILE=""

if [[ "$EFFECTIVE_PROFILE" == "fast" ]]; then
  WHISPER_MODEL_FILE="$(resolve_fast_model_file || true)"
  if [[ -z "$WHISPER_MODEL_FILE" ]]; then
    echo "缺少 fast 档模型（未检测到 turbo/small/base）。" >&2
    echo "请勿静默回退到 accurate 模型，以避免意外触发高耗时转写。" >&2
    echo "请先执行: bash scripts/install_deps.sh 下载所需模型。" >&2
    exit 1
  fi
else
  WHISPER_MODEL_FILE="$WHISPER_MODEL_FILE_ACCURATE"
fi

if [[ ! -f "$WHISPER_MODEL_FILE" ]]; then
  echo "缺少模型文件: $WHISPER_MODEL_FILE" >&2
  print_setup_guidance
  exit 1
fi

METAL_RESOURCES="$(resolve_metal_resources_dir || true)"
if [[ -z "$METAL_RESOURCES" ]]; then
  echo "未发现独立 Metal 资源目录，尝试当前 whisper.cpp 的内嵌资源；初始化失败仍按原规则回退 CPU。" >&2
fi

SRT_FILE="${OUTPUT_PREFIX}.srt"
rm -f "$SRT_FILE"

if [[ "$EFFECTIVE_PROFILE" == "fast" ]]; then
  WHISPER_THREADS="$(clamp_threads "$WHISPER_THREADS_FAST_MAX")"
  WHISPER_BEAM_SIZE="$WHISPER_BEAM_SIZE_FAST"
  WHISPER_BEST_OF="$WHISPER_BEST_OF_FAST"
else
  WHISPER_THREADS="$(clamp_threads "$WHISPER_THREADS_ACCURATE")"
  WHISPER_BEAM_SIZE="$WHISPER_BEAM_SIZE_ACCURATE"
  WHISPER_BEST_OF="$WHISPER_BEST_OF_ACCURATE"
fi

WHISPER_ARGS=(
  -m "$WHISPER_MODEL_FILE"
  -f "$AUDIO_FILE"
  -l "$LANGUAGE"
  -osrt
  -of "$OUTPUT_PREFIX"
  -t "$WHISPER_THREADS"
  -p "$WHISPER_PROCESSORS"
  -bs "$WHISPER_BEAM_SIZE"
  -bo "$WHISPER_BEST_OF"
  -np
)
if [[ "$RECOVERY_NO_CONTEXT" == 1 ]]; then
  # 只用于既有循环稿的独立对照，限制前段文字上下文，不改变模型或质量档位。
  WHISPER_ARGS+=(-mc 0)
  echo "text_context=disabled"
else
  echo "text_context=default"
fi

USED_DEVICE="metal"
METAL_REASON=""
RUN_CODE=1
METAL_EARLY_FAIL=1  # 1=允许 CPU fallback, 0=已开始转写，禁止完整重跑

if metal_cache_is_fresh; then
  METAL_REASON="cached_unavailable"
  echo "检测到近期 Metal 初始化失败，跳过 GPU 直试，直接回退 CPU。" >&2
else
  METAL_LOG="$(mktemp "${TMPDIR:-/tmp}/whisper-metal-log.XXXXXX")"
  set +e
  if [[ -n "$METAL_RESOURCES" ]]; then
    GGML_METAL_PATH_RESOURCES="$METAL_RESOURCES" "$WHISPER_CLI" "${WHISPER_ARGS[@]}" >"$METAL_LOG" 2>&1
  else
    "$WHISPER_CLI" "${WHISPER_ARGS[@]}" >"$METAL_LOG" 2>&1
  fi
  RUN_CODE=$?
  set -e
  cat "$METAL_LOG"

  if [[ $RUN_CODE -eq 0 && -f "$SRT_FILE" ]]; then
    clear_metal_unavailable_cache
    METAL_EARLY_FAIL=1
  else
    # 只要 Metal 日志已经出现转写时间戳，就认为进入实质性转写阶段。
    # 此后失败不自动 CPU 重跑，避免长视频被完整执行第二遍。
    if grep -qE '^\[[0-9]{2}:[0-9]{2}(:[0-9]{2})?\.[0-9]{3} --> [0-9]{2}:[0-9]{2}(:[0-9]{2})?\.[0-9]{3}\]' "$METAL_LOG" 2>/dev/null; then
      METAL_EARLY_FAIL=0
    fi
    if [[ $RUN_CODE -ge 128 ]]; then
      METAL_REASON="metal_process_crashed"
      record_metal_unavailable "$METAL_REASON"
    elif grep -Eiq "ggml_metal_buffer_init: error: failed to allocate buffer" "$METAL_LOG"; then
      METAL_REASON="metal_buffer_alloc_failed"
      record_metal_unavailable "$METAL_REASON"
    elif grep -Eiq "Segmentation fault|Abort trap|metal.*fail" "$METAL_LOG"; then
      METAL_REASON="metal_runtime_failed"
      record_metal_unavailable "$METAL_REASON"
    fi
  fi
  rm -f "$METAL_LOG"
fi

if [[ $RUN_CODE -ne 0 || ! -f "$SRT_FILE" ]]; then
  if [[ "$METAL_EARLY_FAIL" -eq 0 ]]; then
    echo "Metal 已开始转写但中途失败，不自动回退 CPU 重跑（避免长视频完整重复）。" >&2
    echo "请检查 Metal/GPU 环境或显式指定 fast 档位重试。" >&2
    exit 1
  fi
  echo "Metal 转写失败，回退 CPU 转写。" >&2
  rm -f "$SRT_FILE"
  USED_DEVICE="cpu"
  "$WHISPER_CLI" "${WHISPER_ARGS[@]}" -ng
fi

if [[ ! -f "$SRT_FILE" ]]; then
  echo "whisper.cpp 已执行，但未找到转写结果: $SRT_FILE" >&2
  exit 1
fi

echo "requested_profile=$REQUESTED_PROFILE"
echo "profile=$EFFECTIVE_PROFILE"
echo "device=$USED_DEVICE"
if [[ -n "$METAL_REASON" ]]; then
  echo "metal_reason=$METAL_REASON"
fi
echo "model=$(basename "$WHISPER_MODEL_FILE")"
echo "srt_path=$SRT_FILE"
