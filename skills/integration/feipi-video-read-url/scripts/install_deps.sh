#!/usr/bin/env bash
set -euo pipefail

# 视频 URL 读取 skill 的统一依赖安装/检查脚本
# 依赖：yt-dlp、ffmpeg、Python 3、本地 oMLX 服务与 ASR 模型
#
# 用法：
#   bash scripts/install_deps.sh              # 安装下载依赖并检查 oMLX fast 模型
#   bash scripts/install_deps.sh --accurate   # 额外检查 oMLX Qwen3-ASR-1.7B 模型
#   bash scripts/install_deps.sh --check      # 仅检查，不安装
#   bash scripts/install_deps.sh --check --accurate  # 仅检查，要求 accurate

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/yt_dlp_common.sh"

usage() {
  cat <<'USAGE'
用法:
  bash scripts/install_deps.sh [--check] [--accurate]

参数:
  --check     仅检查依赖，不执行安装
  --accurate  额外检查 oMLX Qwen3-ASR-1.7B 模型
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

python3 "$SCRIPT_DIR/lib/omlx_transcribe.py" --check fast || FAILED=1
if [[ "$REQUIRE_ACCURATE" -eq 1 ]]; then
  python3 "$SCRIPT_DIR/lib/omlx_transcribe.py" --check accurate || FAILED=1
fi

if [[ "$FAILED" -ne 0 ]]; then
  echo "依赖检查/安装未完全通过。请启动 oMLX 并在服务中配置 SenseVoiceSmall（fast）及 Qwen3-ASR-1.7B（accurate）；本脚本不修改服务配置或下载模型。" >&2
  exit 1
fi

echo "依赖已就绪。"
