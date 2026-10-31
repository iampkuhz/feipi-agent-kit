#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
STATE_DIR="$HOME/.openclaw"
GLOBAL_ENV="$HOME/.env"
MODE="deploy"
ASSUME_YES=0

usage() {
  cat <<'EOF'
用法：
  scripts/deploy.sh
  scripts/deploy.sh --check
  scripts/deploy.sh --yes

从空的 ~/.openclaw 一次部署 OpenClaw、锁定的 provider/微信插件、受管运行文件、
workspace 模板、managed skills 和 macOS LaunchAgent。

参数：
  --check  只检查前提和当前状态
  --yes    跳过部署前确认
  -h       显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      MODE="check"
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "本仓库只支持 macOS。" >&2
  exit 1
fi

for command_name in awk git jq make node npm shasum; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "未检测到部署依赖：$command_name" >&2
    exit 1
  fi
done

for required_file in \
  "$REPO_DIR/openclaw.json" \
  "$REPO_DIR/versions.json" \
  "$REPO_DIR/templates/workspace/manifest.json"; do
  if [[ ! -f "$required_file" ]]; then
    echo "部署文件不存在：$required_file" >&2
    exit 1
  fi
done

if ! jq -e '
  (.openclaw | type == "string" and length > 0)
  and (.plugins | has("qwen") and has("openclaw-weixin"))
  and all(.plugins[];
    (.package | type == "string" and length > 0)
    and (.version | type == "string" and length > 0))
' "$REPO_DIR/versions.json" >/dev/null; then
  echo "无效的版本基线：$REPO_DIR/versions.json" >&2
  exit 1
fi

if [[ ! -f "$GLOBAL_ENV" ]]; then
  echo "全局环境文件不存在：$GLOBAL_ENV" >&2
  exit 1
fi

has_env_key() {
  local key="$1"
  awk -v key="$key" '
    $0 ~ "^[[:space:]]*" key "[[:space:]]*=" { found = 1; exit }
    $0 ~ "^[[:space:]]*export[[:space:]]+" key "[[:space:]]*=" { found = 1; exit }
    END { exit(found ? 0 : 1) }
  ' "$GLOBAL_ENV"
}

required_env=(
  HTTPS_PROXY
  NO_PROXY
  CLASH_PROXY
  LITELLM_API_KEY_OPENAI
  LITELLM_BASE_URL
  LITELLM_CODE_MODEL_OPENAI
  OPENCLAW_GATEWAY_TOKEN
  OPENCLAW_TG_BOT_TOKEN
)
missing_env=()
for key in "${required_env[@]}"; do
  if ! has_env_key "$key"; then
    missing_env+=("$key")
  fi
done
if [[ "${#missing_env[@]}" -gt 0 ]]; then
  echo "~/.env 缺少必填变量：" >&2
  printf '  - %s\n' "${missing_env[@]}" >&2
  exit 1
fi

required_openclaw="$(jq -r '.openclaw' "$REPO_DIR/versions.json")"

echo "配置仓库：$REPO_DIR"
echo "运行目录：$STATE_DIR"
echo "OpenClaw：$required_openclaw"
jq -r '.plugins | to_entries[] | "插件：\(.key) \(.value.version)"' "$REPO_DIR/versions.json"
echo

make -C "$REPO_DIR" test
"$REPO_DIR/scripts/install-runtime.sh" --check

if [[ "$MODE" == "check" ]]; then
  if command -v openclaw >/dev/null 2>&1; then
    echo "当前 OpenClaw：$(openclaw --version | awk 'NR == 1 {print $2}')"
  else
    echo "当前未安装 OpenClaw。"
  fi
  echo "部署检查完成，未修改本机。"
  exit 0
fi

if [[ "$ASSUME_YES" -eq 0 ]]; then
  if [[ ! -t 0 ]]; then
    echo "非交互部署必须显式添加 --yes。" >&2
    exit 2
  fi
  read -r -p "确认一次部署并重启 OpenClaw Gateway？[y/N] " answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *)
      echo "已取消。"
      exit 0
      ;;
  esac
fi

current_openclaw=""
if command -v openclaw >/dev/null 2>&1; then
  current_openclaw="$(openclaw --version | awk 'NR == 1 {print $2}')"
fi
if [[ "$current_openclaw" == "$required_openclaw" ]]; then
  echo "[1/7] OpenClaw $required_openclaw 已安装"
else
  echo "[1/7] 安装 OpenClaw $required_openclaw"
  npm install --global "openclaw@$required_openclaw"
  hash -r
fi

echo "[2/7] 安装受管运行文件"
"$REPO_DIR/scripts/install-runtime.sh" --write --yes

while IFS=$'\t' read -r plugin_id plugin_package required_version; do
  current_version="$(openclaw plugins inspect "$plugin_id" --json 2>/dev/null \
    | jq -r '.plugin.packageVersion // .plugin.version // empty' 2>/dev/null || true)"
  if [[ "$current_version" == "$required_version" ]]; then
    echo "[3/7] $plugin_id $required_version 已安装"
  else
    echo "[3/7] 安装 $plugin_id $required_version"
    openclaw plugins install "$plugin_package@$required_version" --force --pin
  fi
done < <(jq -r '.plugins | to_entries[] | [.key, .value.package, .value.version] | @tsv' "$REPO_DIR/versions.json")

echo "[4/7] 校验配置和 SecretRef"
# provider 安装会向运行配置写入版本 meta；仓库配置始终覆盖该生成内容。
"$REPO_DIR/scripts/install-runtime.sh" --write --yes
make -C "$REPO_DIR" validate

echo "[5/7] 安装 managed skills"
OPENCLAW_CONFIG_PATH="$REPO_DIR/openclaw.json" \
  "$REPO_DIR/scripts/bootstrap.sh" --yes

echo "[6/7] 安装并重启 macOS LaunchAgent"
env -u OPENCLAW_CONFIG_PATH openclaw gateway install --force
env -u OPENCLAW_CONFIG_PATH openclaw gateway restart

echo "[7/7] 检查 Gateway 和消息渠道"
env -u OPENCLAW_CONFIG_PATH make -C "$REPO_DIR" doctor

echo "部署完成。MCP 外部服务连通性请另行执行：make mcp-probe"
echo "首次微信接入请执行 make weixin-login，并用手机微信扫码。"
