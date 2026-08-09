#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  bash scripts/check_disclosure_format.sh <document.md>

说明:
  兼容旧调用，仅检查草稿标题、基础章节、占位符、图示标识与编号。
  完整交付必须改用 validate_disclosure_package.sh。
USAGE
}

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/validate_disclosure.py" --draft "$1"
