#!/usr/bin/env bash
# 激活已有 Homebrew、用户 CLI、nvm default 与 Cargo 路径；不安装、不加载 shell 启动文件。
# 供 bootstrap/check/Agent 安装共用；直接执行 check 时实际核验 Node/npm。
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  set -euo pipefail
  if [[ "${1:-check}" != check || $# -gt 1 ]]; then
    echo '用法：bash bootstrap/environment.sh check' >&2
    exit 2
  fi
fi
if ! command -v brew >/dev/null 2>&1; then
  # SSH 和非交互 Bash 不读交互 Zsh 配置，仍应发现机器上已安装的原生 Homebrew。
  for bootstrap_brew_prefix in /opt/homebrew /usr/local; do
    if [[ -x "$bootstrap_brew_prefix/bin/brew" ]]; then
      export PATH="$bootstrap_brew_prefix/bin:$bootstrap_brew_prefix/sbin:$PATH"
      break
    fi
  done
  unset bootstrap_brew_prefix
fi
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
# oMLX 首次打开会创建原生入口并检查 PATH；预先保留目录位置，避免重复入口触发弹窗。
# 通用 ~/.local/bin 仍可在应用尚未打开时提供已安装 CLI。
export PATH="$HOME/.omlx/bin:$HOME/.local/bin:${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # nvm 不兼容 nounset；恢复调用方原有选项，且检查时不维护 current 链接。
  bootstrap_had_nounset=0
  case "$-" in *u*) bootstrap_had_nounset=1 ;; esac
  set +u
  # shellcheck source=/dev/null
  source "$NVM_DIR/nvm.sh" --no-use
  NVM_SYMLINK_CURRENT=false nvm use --silent default
  if [[ "$bootstrap_had_nounset" == 1 ]]; then set -u; fi
  unset bootstrap_had_nounset
fi
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  command -v node
  node --version
  npm --version
fi
