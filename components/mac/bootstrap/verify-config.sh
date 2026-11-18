#!/usr/bin/env bash
# 使用工作台的发布清单核对 Stow 链接与源码内容。
set -euo pipefail
WORKBENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../scripts/workbench" && pwd)"
if [[ -z "${HOME:-}" || "$HOME" != /* || "$HOME" == / ]]; then
  echo "HOME 必须是非根目录的绝对路径。" >&2
  exit 1
fi
if ! command -v git >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  echo "未核实：来源验证需要 Git 和 Python 3。" >&2
  exit 1
fi

PYTHONDONTWRITEBYTECODE=1 python3 - "$WORKBENCH_DIR" <<'PY'
import sys

sys.path.insert(0, sys.argv[1])
from main import differences

raise SystemExit(bool(differences('mac')))
PY
