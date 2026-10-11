#!/usr/bin/env bash
set -euo pipefail

# 保留 Shell 入口；Python 编排在同一进程内采样所有计时读数。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PLANTUML_PYTHON:-python3}" "$SCRIPT_DIR/preflight_renderer.py" "$@"
