#!/usr/bin/env bash
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for suite in deploy runtime-install bootstrap weixin-login; do
  bash "$TEST_DIR/test-$suite.sh"
done
