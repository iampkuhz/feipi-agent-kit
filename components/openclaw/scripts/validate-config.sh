#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v openclaw >/dev/null 2>&1; then
  echo "未检测到 openclaw 命令。" >&2
  exit 1
fi

for command_name in jq git rg; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "未检测到命令：$command_name" >&2
    exit 1
  fi
done

export OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-$REPO_DIR/openclaw.json}"

# 仅供离线校验；已有真实环境变量时绝不覆盖。
export LITELLM_BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000}"
export LITELLM_CODE_MODEL_OPENAI="${LITELLM_CODE_MODEL_OPENAI:-validation-model}"
export LITELLM_API_KEY_OPENAI="${LITELLM_API_KEY_OPENAI:-validation-placeholder}"
export OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:-validation-placeholder}"
export OPENCLAW_TG_BOT_TOKEN="${OPENCLAW_TG_BOT_TOKEN:-validation-placeholder}"
export CLASH_PROXY="${CLASH_PROXY:-http://127.0.0.1:7890}"
export HOME="${HOME:-/Users/zhehan}"

jq empty "$OPENCLAW_CONFIG_PATH"
jq empty "$REPO_DIR/versions.json"

manifest_files=("$REPO_DIR"/skill-list/*.json)
if [[ ! -e "${manifest_files[0]}" ]]; then
  echo "skill-list/ 中没有 manifest。" >&2
  exit 1
fi
jq -e -s '
  all(.[];
    (if has("enabled") then .enabled else true end) as $enabled
    | .version == 1
    and (.name | type == "string" and test("^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$"))
    and (.source.type == "git-subdirectory")
    and (.source.repository | type == "string" and length > 0 and (startswith("-") | not))
    and (.source.ref | type == "string" and length > 0 and (startswith("-") | not))
    and (.source.path
      | type == "string"
      and length > 0
      and (startswith("/") | not)
      and (contains("\\") | not)
      and (split("/") | all(. != "..")))
    and ($enabled | type == "boolean")
    and (($enabled == true) or (.disabledReason | type == "string" and length > 0))
    and ((.setup.npmInstall // false) | type == "boolean")
    and ((.setup.useLocalWorkingTree // false) | type == "boolean")
    and ((.runtime.requiredEnv // []) | type == "array")
    and all((.runtime.requiredEnv // [])[]; type == "string" and test("^[A-Z_][A-Z0-9_]*$"))
  )
  and ([.[].name] | length == (unique | length))
' "${manifest_files[@]}" >/dev/null

workspace_manifest="$REPO_DIR/templates/workspace/manifest.json"
jq -e '
  .version == 1
  and .target == "~/.openclaw/workspace"
  and (.files | type == "array" and length > 0)
  and all(.files[];
    type == "string" and length > 0
    and (startswith("/") | not)
    and (contains("\\") | not)
    and (split("/") | all(. != ".."))
  )
  and (.files | length == (unique | length))
' "$workspace_manifest" >/dev/null
while IFS= read -r relative_path; do
  if [[ ! -f "$REPO_DIR/templates/workspace/$relative_path" ]]; then
    echo "workspace manifest 来源不存在：$relative_path" >&2
    exit 1
  fi
done < <(jq -r '.files[]' "$workspace_manifest")

runtime_roots=(
  agents browser cache canvas completions credentials cron delivery-queue
  devices flows identity logs media memory npm plugin-skills plugins sandboxes
  service-env sessions skill-workshop skills state tasks telegram tmp workspace
  workspace-attestations openclaw-weixin extensions
)
for runtime_root in "${runtime_roots[@]}"; do
  if git -C "$REPO_DIR" ls-files "$runtime_root/**" | rg -q .; then
    echo "Git 仍在跟踪 OpenClaw 运行目录：$runtime_root/" >&2
    exit 1
  fi
done

jq -e '
  (.channels.telegram.customCommands | map(.command)) == ["housing", "growth"]
  and (.channels.telegram.direct["7026716907"].systemPrompt | contains("/housing"))
  and (.channels.telegram.direct["7026716907"].systemPrompt | contains("$feipi-housing-capture-inbox"))
  and (.channels.telegram.direct["7026716907"].systemPrompt | contains("$feipi-video-read-url"))
  and (.channels.telegram.direct["7026716907"].systemPrompt | contains("$feipi-xiaohongshu-read-note"))
  and (.channels.telegram.direct["7026716907"].systemPrompt | contains("housing_tool.py receive"))
  and (.channels.telegram.direct["7026716907"].systemPrompt | contains("不下载完整原视频"))
  and (.channels.telegram.direct["7026716907"].systemPrompt | contains("$feipi-growth-record-diary"))
  and (.channels.telegram.direct["7026716907"].systemPrompt | contains("/Users/zhehan/Documents/life/child-growth-diary/AGENTS.md"))
  and (.agents | has("list") | not)
  and (.agents.entries.main.identity.name == "feipi_claw")
  and (.agents.defaults | has("workspace") | not)
  and (.agents.defaults | has("imageGenerationModel") | not)
  and (.agents.defaults.mediaModels.image.primary | type == "string")
  and (.browser | has("executablePath") | not)
  and ([.browser.profiles[]?.color] | length == 0)
  and (.browser.ssrfPolicy.dangerouslyAllowPrivateNetwork == false)
  and (.browser.ssrfPolicy.allowedHostnames | sort == (["www.xiaohongshu.com", "xiaohongshu.com", "xhslink.com", "xhslink.cn"] | sort))
  and ([.browser.extraArgs[]? | select(startswith("--proxy-"))] | length == 0)
  and (.commands | has("ownerDisplay") | not)
  and (.tools.sessions.visibility == "tree")
  and (.tools.agentToAgent.enabled == false)
  and (.mcp.servers["fastmcp-gateway"].enabled == false)
  and ((.mcp.servers.crawl4ai.enabled // true) == true)
  and (.tools.media.audio | has("models") | not)
  and any(.tools.media.models[];
    (.capabilities | index("audio") != null)
    and (.args | index("{{AttachmentPath}}") != null)
  )
' "$OPENCLAW_CONFIG_PATH" >/dev/null

expected_openclaw_version="$(jq -r '.openclaw' "$REPO_DIR/versions.json")"
actual_openclaw_version="$(openclaw --version | awk '{print $2}')"
if [[ "$actual_openclaw_version" != "$expected_openclaw_version" ]]; then
  echo "OpenClaw 版本不匹配: expected=$expected_openclaw_version actual=$actual_openclaw_version" >&2
  exit 1
fi

while IFS=$'\t' read -r plugin_id expected_version; do
  actual_version="$(openclaw plugins inspect "$plugin_id" --json | jq -r '.plugin.packageVersion // .plugin.version // empty')"
  if [[ "$actual_version" != "$expected_version" ]]; then
    echo "$plugin_id 版本不匹配: expected=$expected_version actual=${actual_version:-missing}" >&2
    exit 1
  fi
done < <(jq -r '.plugins | to_entries[] | [.key, .value.version] | @tsv' "$REPO_DIR/versions.json")

openclaw config validate --json
openclaw secrets audit --check --json
openclaw mcp doctor --json
