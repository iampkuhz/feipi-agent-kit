#!/usr/bin/env bash
# 继承当前凭据环境；原生 CLI 继续读取各自迁入的用户设置。
set -euo pipefail
BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bootstrap/environment.sh
source "$BOOTSTRAP_DIR/environment.sh"
export PATH="$HOME/.local/bin:$PATH"
python3 "$BOOTSTRAP_DIR/verify-agents.py" "$@"
