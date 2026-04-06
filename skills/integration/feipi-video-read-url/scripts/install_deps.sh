#!/usr/bin/env bash
set -euo pipefail

# 视频 URL 读取 skill 的统一依赖安装/检查脚本
# 依赖：yt-dlp, ffmpeg, whisper.cpp(whisper-cli), large-v3-q5_0 模型
#
# 用法：
#   bash scripts/install_deps.sh            # 自动安装缺失依赖（支持 macOS + Homebrew）
#   bash scripts/install_deps.sh --check    # 仅检查，不安装

WHISPER_CPP_BIN_DEFAULT="/opt/homebrew/opt/whisper-cpp/bin/whisper-cli"
WHISPER_MODEL_DIR_DEFAULT="$HOME/Library/Caches/whisper.cpp/models"
WHISPER_MODEL_FILE_DEFAULT="$WHISPER_MODEL_DIR_DEFAULT/ggml-large-v3-q5_0.bin"
WHISPER_MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin"

usage() {
  cat <<'USAGE'
用法:
  bash scripts/install_deps.sh [--check]

参数:
  --check   仅检查依赖，不执行安装
USAGE
}

CHECK_ONLY=0
if [[ $# -gt 0 ]]; then
  case "$1" in
    --check)
      CHECK_ONLY=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
fi

need_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1
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
  local tmp_file
  if [[ -f "$WHISPER_MODEL_FILE_DEFAULT" ]]; then
    echo "[OK] whisper 模型: $WHISPER_MODEL_FILE_DEFAULT"
    return 0
  fi

  echo "[MISS] whisper 模型: $WHISPER_MODEL_FILE_DEFAULT"
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    return 1
  fi

  echo "正在下载模型（large-v3 q5_0，首次下载较慢）..."
  mkdir -p "$WHISPER_MODEL_DIR_DEFAULT"
  tmp_file="${WHISPER_MODEL_FILE_DEFAULT}.partial.$$"
  if ! curl -L --fail "$WHISPER_MODEL_URL" -o "$tmp_file"; then
    rm -f "$tmp_file"
    echo "[FAIL] whisper 模型下载失败" >&2
    return 1
  fi
  mv "$tmp_file" "$WHISPER_MODEL_FILE_DEFAULT"
  echo "[OK] whisper 模型下载完成: $WHISPER_MODEL_FILE_DEFAULT"
  return 0
}

install_yt_dlp() {
  install_with_brew yt-dlp
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
