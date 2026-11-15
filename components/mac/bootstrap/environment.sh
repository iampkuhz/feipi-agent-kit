#!/usr/bin/env bash
# 仅激活已有的 nvm default 与 Cargo 路径；不安装、不加载 shell 启动文件。
# 供 bootstrap/check/Agent 安装共用；直接执行 check 时实际核验 Node/npm。
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  set -euo pipefail
  if [[ "${1:-check}" != check || $# -gt 1 ]]; then
    echo '用法：bash bootstrap/environment.sh check' >&2
    exit 2
  fi
fi
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
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
