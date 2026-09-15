#!/usr/bin/env bash
set -euo pipefail

# 视频 URL 读取 skill 的统一依赖安装/检查脚本
# 依赖：yt-dlp, ffmpeg, whisper.cpp(whisper-cli), fast 基础模型
#
# 用法：
#   bash scripts/install_deps.sh              # 默认仅检查/安装 fast 档模型
#   bash scripts/install_deps.sh --accurate   # 额外要求 accurate（large-v3-q5_0）模型
#   bash scripts/install_deps.sh --check      # 仅检查，不安装
#   bash scripts/install_deps.sh --check --accurate  # 仅检查，要求 accurate

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/yt_dlp_common.sh"

WHISPER_CPP_BIN_DEFAULT="/opt/homebrew/opt/whisper-cpp/bin/whisper-cli"
WHISPER_MODEL_DIR_DEFAULT="$HOME/Library/Caches/whisper.cpp/models"
WHISPER_MODEL_FILE_ACCURATE="$WHISPER_MODEL_DIR_DEFAULT/ggml-large-v3-q5_0.bin"
WHISPER_MODEL_URL_ACCURATE="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin"

# fast 档候选模型（whispercpp_transcribe.sh 按此顺序查找）
WHISPER_FAST_MODELS=(
  "ggml-large-v3-turbo-q5_0.bin|https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
  "ggml-small.bin|https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
  "ggml-base.bin|https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
)

usage() {
  cat <<'USAGE'
用法:
  bash scripts/install_deps.sh [--check] [--accurate]

参数:
  --check     仅检查依赖，不执行安装
  --accurate  额外要求 accurate（large-v3-q5_0）模型
USAGE
}

CHECK_ONLY=0
REQUIRE_ACCURATE=0
if [[ $# -gt 0 ]]; then
  for arg in "$@"; do
    case "$arg" in
      --check)
        CHECK_ONLY=1
        ;;
      --accurate)
        REQUIRE_ACCURATE=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "未知参数: $arg" >&2
        usage
        exit 1
        ;;
    esac
  done
fi

need_cmd() {
  local cmd="$1"
  if [[ "$cmd" == "yt-dlp" ]]; then
    yt_common_select_ytdlp || return 1
    yt_common_report_ytdlp_provenance
  else
    command -v "$cmd" >/dev/null 2>&1
  fi
}

install_with_brew() {
  local pkg="$1"
  if ! command -v brew >/dev/null 2>&1; then
    echo "未安装 Homebrew，无法自动安装 $pkg。" >&2
    echo "请先安装 Homebrew 或手动安装 $pkg。" >&2
    return 1
  fi
  brew list "$pkg" >/dev/null 2>&1 || brew install "$pkg"
}

has_whisper_cpp() {
  if [[ -x "$WHISPER_CPP_BIN_DEFAULT" ]]; then
    return 0
  fi
  if need_cmd whisper-cli; then
    return 0
  fi
  return 1
}

install_whisper_cpp() {
  install_with_brew whisper-cpp
}

ensure_whisper_model() {
  local tmp_file model_entry model_name fast_path

  # 确保 fast 档至少有一个模型（默认必检项）。
  local fast_found=0
  for model_entry in "${WHISPER_FAST_MODELS[@]}"; do
    model_name="${model_entry%%|*}"
    fast_path="$WHISPER_MODEL_DIR_DEFAULT/$model_name"
    if [[ -f "$fast_path" ]]; then
      echo "[OK] whisper 模型(fast): $fast_path"
      fast_found=1
    else
      echo "[MISS] whisper 模型(fast): $fast_path"
    fi
  done

  if [[ "$fast_found" -eq 0 ]]; then
    if [[ "$CHECK_ONLY" -eq 1 ]]; then
      return 1
    fi
    echo "正在下载 fast 基础模型: ggml-base.bin ..."
    mkdir -p "$WHISPER_MODEL_DIR_DEFAULT"
    local default_url="${WHISPER_FAST_MODELS[2]#*|}"
    tmp_file="${WHISPER_MODEL_DIR_DEFAULT}/ggml-base.bin.partial.$$"
    if ! curl -L --fail "$default_url" -o "$tmp_file"; then
      rm -f "$tmp_file"
      echo "[FAIL] whisper fast 模型下载失败" >&2
      return 1
    fi
    mv "$tmp_file" "$WHISPER_MODEL_DIR_DEFAULT/ggml-base.bin"
    echo "[OK] whisper fast 模型下载完成: $WHISPER_MODEL_DIR_DEFAULT/ggml-base.bin"
  fi

  # accurate 模型仅在显式要求时检查/安装。
  if [[ "$REQUIRE_ACCURATE" -eq 1 ]]; then
    if [[ -f "$WHISPER_MODEL_FILE_ACCURATE" ]]; then
      echo "[OK] whisper 模型(accurate): $WHISPER_MODEL_FILE_ACCURATE"
    else
      echo "[MISS] whisper 模型(accurate): $WHISPER_MODEL_FILE_ACCURATE"
      if [[ "$CHECK_ONLY" -eq 1 ]]; then
        return 1
      fi
      echo "正在下载模型（large-v3 q5_0，首次下载较慢）..."
      mkdir -p "$WHISPER_MODEL_DIR_DEFAULT"
      tmp_file="${WHISPER_MODEL_FILE_ACCURATE}.partial.$$"
      if ! curl -L --fail "$WHISPER_MODEL_URL_ACCURATE" -o "$tmp_file"; then
        rm -f "$tmp_file"
        echo "[FAIL] whisper accurate 模型下载失败" >&2
        return 1
      fi
      mv "$tmp_file" "$WHISPER_MODEL_FILE_ACCURATE"
      echo "[OK] whisper accurate 模型下载完成: $WHISPER_MODEL_FILE_ACCURATE"
    fi
  fi

  return 0
}

install_yt_dlp() {
  install_with_brew yt-dlp
}

install_python() {
  install_with_brew python
}

install_ffmpeg() {
  install_with_brew ffmpeg
}

check_and_install() {
  local cmd="$1"
  local installer="$2"

  if need_cmd "$cmd"; then
    echo "[OK] $cmd"
    return 0
  fi

  echo "[MISS] $cmd"
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    return 1
  fi

  echo "正在安装 $cmd ..."
  if "$installer"; then
    if need_cmd "$cmd"; then
      echo "[OK] $cmd 安装完成"
      return 0
    fi
  fi

  echo "[FAIL] $cmd 安装失败" >&2
  return 1
}

FAILED=0

check_and_install yt-dlp install_yt_dlp || FAILED=1
check_and_install ffmpeg install_ffmpeg || FAILED=1
check_and_install python3 install_python || FAILED=1

if has_whisper_cpp; then
  echo "[OK] whisper-cli"
else
  echo "[MISS] whisper-cli"
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    FAILED=1
  else
    echo "正在安装 whisper-cpp ..."
    if install_whisper_cpp && has_whisper_cpp; then
      echo "[OK] whisper-cli 安装完成"
    else
      echo "[FAIL] whisper-cli 安装失败" >&2
      FAILED=1
    fi
  fi
fi

ensure_whisper_model || FAILED=1

if [[ "$FAILED" -ne 0 ]]; then
  echo "依赖检查/安装未完全通过。" >&2
  exit 1
fi

echo "依赖已就绪。"
