#!/usr/bin/env bash
# 使用 dotfiles 的 Brewfile 安装、检查或升级 Homebrew 环境。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SHARED_BREWFILE="$REPO_ROOT/Brewfile"
LOCAL_BREWFILE="$REPO_ROOT/Brewfile.local"
MODE="${1:-install}"

usage() {
  cat <<'USAGE'
用法：
  bash bootstrap/brew.sh install  # 补装缺失依赖，不主动升级
  bash bootstrap/brew.sh check    # 检查依赖是否齐全
  bash bootstrap/brew.sh upgrade  # 显式升级清单内依赖
USAGE
}

if [[ "$MODE" != "install" && "$MODE" != "check" && "$MODE" != "upgrade" ]]; then
  echo "不支持的模式：$MODE" >&2
  usage >&2
  exit 2
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "该脚本仅支持 macOS。" >&2
  exit 1
fi

if [[ ! -f "$SHARED_BREWFILE" ]]; then
  echo "缺少共享依赖清单：$SHARED_BREWFILE" >&2
  exit 1
fi

# 新 Mac 上 Homebrew 可能已安装，但当前 shell 尚未加载它的 PATH。
if ! command -v brew >/dev/null 2>&1; then
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  else
    echo "未检测到 Homebrew。请先按 https://brew.sh/ 的官方说明安装。" >&2
    exit 1
  fi
fi

# 安装与检查不触发 Homebrew 自动更新；显式 upgrade 才允许更新元数据。
if [[ "$MODE" != "upgrade" ]]; then
  export HOMEBREW_NO_AUTO_UPDATE=1
fi

# 共享清单和单机清单使用同一模式处理，避免两套安装逻辑逐渐分叉。
run_bundle() {
  local brewfile="$1"
  local label="$2"

  echo "==> $label: $brewfile"
  case "$MODE" in
  install)
    brew bundle install --no-upgrade --file "$brewfile"
    ;;
  check)
    brew bundle check --no-upgrade --verbose --file "$brewfile"
    ;;
  upgrade)
    brew bundle upgrade --file "$brewfile"
    ;;
  esac
}

run_bundle "$SHARED_BREWFILE" "处理跨机器共享依赖"

if [[ -f "$LOCAL_BREWFILE" ]]; then
  run_bundle "$LOCAL_BREWFILE" "处理当前机器依赖"
else
  echo "==> 未发现 Brewfile.local，跳过当前机器依赖"
fi

if [[ "$MODE" != "check" ]]; then
  echo "==> 验证 Homebrew 依赖"
  brew bundle check --no-upgrade --verbose --file "$SHARED_BREWFILE"
  if [[ -f "$LOCAL_BREWFILE" ]]; then
    brew bundle check --no-upgrade --verbose --file "$LOCAL_BREWFILE"
  fi
fi

echo "✅ Homebrew 依赖处理完成"
