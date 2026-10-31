#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v openclaw >/dev/null 2>&1; then
  echo "未检测到 openclaw 命令。" >&2
  exit 1
fi

expected_openclaw="$(jq -r '.openclaw' "$REPO_DIR/versions.json")"
actual_openclaw="$(openclaw --version | awk 'NR == 1 {print $2}')"

if [[ "$actual_openclaw" != "$expected_openclaw" ]]; then
  echo "OpenClaw 版本不匹配：expected=$expected_openclaw actual=$actual_openclaw" >&2
  exit 1
fi
while IFS=$'\t' read -r plugin_id expected_version; do
  actual_version="$(openclaw plugins inspect "$plugin_id" --json | jq -r '.plugin.packageVersion // .plugin.version // empty')"
  if [[ "$actual_version" != "$expected_version" ]]; then
    echo "$plugin_id 版本不匹配：expected=$expected_version actual=${actual_version:-missing}" >&2
    exit 1
  fi
done < <(jq -r '.plugins | to_entries[] | [.key, .value.version] | @tsv' "$REPO_DIR/versions.json")

"$REPO_DIR/scripts/install-runtime.sh" --check
openclaw config validate --json
openclaw secrets audit --check --json
# MCP 连通性由 make mcp-probe 单独负责；Gateway 仅对本机开放是本仓库的安全选择。
openclaw doctor --lint --severity-min warning \
  --skip core/doctor/runtime-tool-schemas \
  --skip core/doctor/node-hosting-preconditions
openclaw mcp doctor
openclaw gateway status
openclaw channels status --probe
