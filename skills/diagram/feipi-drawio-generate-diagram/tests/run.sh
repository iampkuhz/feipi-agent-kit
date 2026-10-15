#!/usr/bin/env bash
set -euo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == --live ]]; then
  export DRAWIO_TEST_LIVE=1
elif [[ $# -gt 0 ]]; then
  echo '用法：tests/run.sh [--live]' >&2
  exit 1
fi
python3 -m unittest discover -s "$TEST_DIR" -p 'test_*.py' -v
