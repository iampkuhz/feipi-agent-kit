#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  bash scripts/validate_disclosure_package.sh <disclosure-dir>

目录要求:
  <disclosure-dir>/disclosure.md
  <disclosure-dir>/disclosure-workspace/...

退出码:
  0  success
  1  blocked
  2  review_required
USAGE
}

if [[ $# -eq 1 && ( "$1" == "-h" || "$1" == "--help" ) ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/validate_disclosure.py" --package "$1"
