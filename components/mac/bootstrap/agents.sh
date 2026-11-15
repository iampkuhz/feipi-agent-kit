#!/usr/bin/env bash
# 复用已经选择的 Node；安装器不运行用户启动文件，也不改写全局 npm prefix。
set -euo pipefail
BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  set +u
  # shellcheck source=/dev/null
  source "$NVM_DIR/nvm.sh" --no-use
  nvm use --silent default
  set -u
fi
export PATH="$HOME/.local/bin:$PATH"
exec python3 "$BOOTSTRAP_DIR/agents.py" "$@"
