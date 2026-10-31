#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DEPLOY_SCRIPT="$REPO_DIR/scripts/deploy.sh"

bash -n "$DEPLOY_SCRIPT"

help_output="$(bash "$DEPLOY_SCRIPT" --help)"
if [[ "$help_output" != *"scripts/deploy.sh --check"* ]]; then
  echo "deploy 帮助缺少 check 入口。" >&2
  exit 1
fi
if [[ "$help_output" != *"scripts/deploy.sh --yes"* ]]; then
  echo "deploy 帮助缺少非交互入口。" >&2
  exit 1
fi

echo "deploy 入口测试通过。"
