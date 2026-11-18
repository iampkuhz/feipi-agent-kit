#!/usr/bin/env bash
# 复用已经选择的 Node；安装器不运行用户启动文件，也不改写全局 npm prefix。
set -euo pipefail
BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bootstrap/environment.sh
source "$BOOTSTRAP_DIR/environment.sh"
export PATH="$HOME/.local/bin:$PATH"
python3 "$BOOTSTRAP_DIR/agents.py" "$@"
