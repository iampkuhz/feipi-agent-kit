#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEMP_PARENT="$(cd "${TMPDIR:-/tmp}" && pwd -P)"
TEST_HOME="$(mktemp -d "$TEMP_PARENT/feipi-openclaw-runtime-test.XXXXXX")"

cleanup() {
  case "$TEST_HOME" in
    "$TEMP_PARENT"/feipi-openclaw-runtime-test.*)
      find "$TEST_HOME" -depth -delete 2>/dev/null || true
      ;;
  esac
}
trap cleanup EXIT

printf '%s\n' 'OPENCLAW_GATEWAY_TOKEN=test' >"$TEST_HOME/.env"

HOME="$TEST_HOME" "$REPO_DIR/scripts/install-runtime.sh" --check >/dev/null
HOME="$TEST_HOME" "$REPO_DIR/scripts/install-runtime.sh" --write --yes >/dev/null
HOME="$TEST_HOME" "$REPO_DIR/scripts/install-runtime.sh" --check >/dev/null

[[ "$(readlink "$TEST_HOME/.openclaw/.env")" == "$TEST_HOME/.env" ]]
[[ ! -L "$TEST_HOME/.openclaw/openclaw.json" ]]
cmp -s "$TEST_HOME/.openclaw/openclaw.json" "$REPO_DIR/openclaw.json"
cmp -s "$TEST_HOME/.openclaw/scripts/transcribe-audio-whispercpp-openclaw.sh" \
  "$REPO_DIR/scripts/transcribe-audio-whispercpp-openclaw.sh"

while IFS= read -r relative_path; do
  target_file="$TEST_HOME/.openclaw/workspace/$relative_path"
  [[ ! -L "$target_file" ]]
  cmp -s "$target_file" "$REPO_DIR/templates/workspace/$relative_path"
done < <(jq -r '.files[]' "$REPO_DIR/templates/workspace/manifest.json")

printf '%s\n' 'drift' >"$TEST_HOME/.openclaw/workspace/AGENTS.md"
HOME="$TEST_HOME" "$REPO_DIR/scripts/install-runtime.sh" --write --yes >/dev/null
cmp -s "$TEST_HOME/.openclaw/workspace/AGENTS.md" "$REPO_DIR/templates/workspace/AGENTS.md"

mkdir -p "$TEST_HOME/.openclaw/workspace/memory"
printf '%s\n' 'runtime-only' >"$TEST_HOME/.openclaw/workspace/memory/2099-01-01.md"
HOME="$TEST_HOME" "$REPO_DIR/scripts/install-runtime.sh" --write --yes >/dev/null
[[ -f "$TEST_HOME/.openclaw/workspace/memory/2099-01-01.md" ]]
[[ ! -e "$REPO_DIR/templates/workspace/memory/2099-01-01.md" ]]

echo "运行文件安装测试通过。"
