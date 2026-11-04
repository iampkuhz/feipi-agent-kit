#!/usr/bin/env bash
set -euo pipefail
# 保留既有站点脚本的四参数转写接口；实际识别统一由本地 oMLX 提供。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/omlx_transcribe.py" "$@"
