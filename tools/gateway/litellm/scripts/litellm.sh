#!/bin/bash
# LiteLLM 启动/停止脚本
# 用法：./scripts/litellm.sh {up|down|restart|restart-chatgpt|recreate|logs|status|check-chatgpt-env|check-chatgpt-runtime|check-chatgpt-network|check-dashboard-auth|print-chatgpt-env|print-client-env|print-codex-config|write-codex-model-catalog|check-client-env}

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$COMPOSE_DIR/compose/docker-compose.yml"

cd "$COMPOSE_DIR"

apply_defaults() {
  LITELLM_PORT="4000"
  POSTGRES_DATA_DIR="/Users/zhehan/Documents/service-data/postgres"
  CHATGPT_TOKEN_HOST_DIR="/Users/zhehan/Documents/service-data/litellm/chatgpt-tokens"
  export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-litellm-local-dev}"
  export LITELLM_UPSTREAM_CODE_MODEL_OPENAI_NAME="${LITELLM_UPSTREAM_CODE_MODEL_OPENAI_NAME:-openai/qwen-plus}"
  export LITELLM_UPSTREAM_CODE_MODEL_OPENAI_BASE="${LITELLM_UPSTREAM_CODE_MODEL_OPENAI_BASE:-${BAILIAN_CODING_PLAN_OPENAI_BASE_URL:-${BAILIAN_OPENAI_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}}}"
  export LITELLM_UPSTREAM_CODE_MODEL_OPENAI_KEY="${LITELLM_UPSTREAM_CODE_MODEL_OPENAI_KEY:-${BAILIAN_CODING_PLAN_API_KEY:-${BAILIAN_API_KEY:-dummy-key}}}"
  export LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_NAME="${LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_NAME:-anthropic/qwen-plus}"
  export LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_BASE="${LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_BASE:-${BAILIAN_CODING_PLAN_ANTHROPIC_BASE_URL:-${BAILIAN_ANTHROPIC_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}}}"
  export LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_KEY="${LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_KEY:-${BAILIAN_CODING_PLAN_API_KEY:-${BAILIAN_API_KEY:-dummy-key}}}"
  export LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_NAME="${LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_NAME:-openai/qwen-turbo}"
  export LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_BASE="${LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_BASE:-http://host.containers.internal:11434/v1}"
  export LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_KEY="${LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_KEY:-dummy-key}"
  export LITELLM_CONTAINER_HTTP_PROXY="${LITELLM_CONTAINER_HTTP_PROXY-http://host.containers.internal:7890}"
  export LITELLM_CONTAINER_HTTPS_PROXY="${LITELLM_CONTAINER_HTTPS_PROXY-http://host.containers.internal:7890}"
}

print_chatgpt_env() {
  cat <<'EOF'
# ~/.env
# 网关访问密钥。默认可本地启动；建议替换为：openssl rand -hex 16
export LITELLM_MASTER_KEY=<替换为随机 token>

# Codex 标准模型名在 config.yaml 中严格转发到同名 chatgpt/... 上游。
# 不需要配置 LITELLM_CODEX_MODEL 或 LITELLM_UPSTREAM_CODEX_MODEL。

# 可选：只有宿主机代理端口不是 7890，或需要禁用代理时才配置。
# export LITELLM_CONTAINER_HTTP_PROXY=http://host.containers.internal:7890
# export LITELLM_CONTAINER_HTTPS_PROXY=http://host.containers.internal:7890
EOF
}

print_client_env() {
  cat <<'EOF'
# ~/.env
# 客户端访问 LiteLLM 的 private key，来自 Dashboard -> Virtual Keys 手工创建。
# OpenAI / Codex / OpenAI-compatible 客户端使用：
export LITELLM_API_KEY_OPENAI=<替换为 key-for-openai 的 secret key>

# Anthropic / Claude-code / Anthropic-compatible 客户端使用：
export LITELLM_API_KEY_ANTHROPIC=<替换为 key-for-claude-code 的 secret key>
EOF
}

print_codex_config() {
  local catalog_path="${HOME}/.codex/model-catalogs/litellm-local.json"

  cat <<EOF
# ~/.codex/config.toml
# 根级配置必须写在 [model_providers.*] 表之前。
model = "gpt-5.5"
model_provider = "litellm-local"
model_reasoning_effort = "xhigh"
service_tier = "priority"
model_catalog_json = "${catalog_path}"

[features]
fast_mode = true

[model_providers.litellm-local]
name = "LiteLLM Local"
base_url = "http://localhost:4000/v1"
env_key = "LITELLM_API_KEY_OPENAI"
wire_api = "responses"
EOF
}

write_codex_model_catalog() {
  local catalog_path="${HOME}/.codex/model-catalogs/litellm-local.json"

  if ! command -v codex >/dev/null 2>&1; then
    echo "❌ 未找到 codex 命令，无法生成 Codex 模型候选元数据"
    exit 1
  fi

  if ! command -v jq >/dev/null 2>&1; then
    echo "❌ 未找到 jq，无法生成 Codex 模型候选元数据"
    exit 1
  fi

  mkdir -p "$(dirname "$catalog_path")"
  local tmp_path
  tmp_path="$(mktemp "${catalog_path}.tmp.XXXXXX")"

  if ! codex debug models --bundled | jq '
    {
      models: [
        .models[]
        | select((.slug // "") as $slug
          | [
              "gpt-5.5",
              "gpt-5.4",
              "gpt-5.4-mini",
              "gpt-5.3-codex",
              "gpt-5.2"
            ]
          | index($slug))
      ]
    }
  ' > "$tmp_path"; then
    rm -f "$tmp_path"
    echo "❌ 生成 Codex 模型候选元数据失败"
    exit 1
  fi

  mv "$tmp_path" "$catalog_path"

  echo "✅ 已生成 Codex 模型候选元数据：$catalog_path"
  echo "   当前候选：gpt-5.5 gpt-5.4 gpt-5.4-mini gpt-5.3-codex gpt-5.2"
}

env_is_set() {
  printenv "$1" >/dev/null 2>&1
}

env_value() {
  printenv "$1" 2>/dev/null || true
}

check_chatgpt_env() {
  apply_defaults

  for deprecated_key in LITELLM_CODEX_MODEL LITELLM_UPSTREAM_CODEX_MODEL; do
    if env_is_set "$deprecated_key"; then
      echo "⚠️  $deprecated_key 已不再参与 Codex 严格转发配置，当前值会被忽略：$(env_value "$deprecated_key")"
    fi
  done

  echo "✅ ChatGPT 订阅配置已就绪（Codex 标准模型名由 config.yaml 严格转发）"
}

check_client_env() {
  local mode="${1:-all}"
  local failed=0
  local keys=()
  local key

  case "$mode" in
    openai)
      keys=(LITELLM_API_KEY_OPENAI)
      ;;
    anthropic)
      keys=(LITELLM_API_KEY_ANTHROPIC)
      ;;
    all)
      keys=(LITELLM_API_KEY_OPENAI LITELLM_API_KEY_ANTHROPIC)
      ;;
    *)
      echo "用法：$0 check-client-env [openai|anthropic|all]"
      exit 1
      ;;
  esac

  for key in "${keys[@]}"; do
    if ! env_is_set "$key"; then
      echo "❌ 缺少客户端 private key 环境变量：$key"
      failed=1
    fi
  done

  if env_is_set LITELLM_MASTER_KEY; then
    for key in "${keys[@]}"; do
      if env_is_set "$key" && [[ "$(env_value "$key")" == "$(env_value LITELLM_MASTER_KEY)" ]]; then
        echo "⚠️  $key 当前与 LITELLM_MASTER_KEY 相同。建议客户端使用 Dashboard -> Virtual Keys 创建的 private key，不要直接使用 master key。"
      fi
    done
  fi

  if [[ "$failed" -ne 0 ]]; then
    echo
    echo "请把下面配置放到 ~/.env，并打开一个新的 zsh 后重试："
    print_client_env
    exit 1
  fi

  echo "✅ 客户端 private key 环境变量已就绪 ($mode)"
}

prepare_dirs() {
  mkdir -p "$POSTGRES_DATA_DIR" "$CHATGPT_TOKEN_HOST_DIR"
}

prepare_runtime() {
  apply_defaults
  check_chatgpt_env
  prepare_dirs
}

compose() {
  local compose_env_file="${LITELLM_COMPOSE_ENV_FILE:-/dev/null}"

  if [[ -n "${LITELLM_COMPOSE_COMMAND:-}" ]]; then
    # shellcheck disable=SC2086
    $LITELLM_COMPOSE_COMMAND --env-file "$compose_env_file" -f "$COMPOSE_FILE" "$@"
  elif command -v podman-compose >/dev/null 2>&1; then
    podman-compose --env-file "$compose_env_file" -f "$COMPOSE_FILE" "$@"
  else
    podman compose --env-file "$compose_env_file" -f "$COMPOSE_FILE" "$@"
  fi
}

podman_exec_litellm() {
  podman exec litellm-proxy-podman "$@"
}

podman_exec_postgres() {
  podman exec litellm-db-podman "$@"
}

container_is_running() {
  [[ "$(podman inspect -f '{{.State.Running}}' litellm-proxy-podman 2>/dev/null || true)" == "true" ]]
}

db_container_is_running() {
  [[ "$(podman inspect -f '{{.State.Running}}' litellm-db-podman 2>/dev/null || true)" == "true" ]]
}

container_master_key() {
  podman_exec_litellm sh -lc 'printf "%s" "${LITELLM_MASTER_KEY:-}"'
}

print_model_ids_from_json() {
  if command -v jq >/dev/null 2>&1; then
    jq -r '.data[]?.id' 2>/dev/null || true
  else
    python3 -c 'import json,sys; data=json.load(sys.stdin); [print(x.get("id","")) for x in data.get("data", [])]' 2>/dev/null || true
  fi
}

model_list_json() {
  local key
  key="$(container_master_key)"
  curl -fsS "http://127.0.0.1:${LITELLM_PORT:-4000}/v1/models" \
    -H "Authorization: Bearer ${key}"
}

check_chatgpt_network() {
  if ! container_is_running; then
    echo "❌ litellm-proxy-podman 未运行。请先执行：./scripts/litellm.sh restart-chatgpt"
    exit 1
  fi

  echo "容器代理环境："
  podman_exec_litellm sh -lc '
    for key in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy NO_PROXY no_proxy; do
      value="$(printenv "$key" 2>/dev/null || true)"
      if [ -n "$value" ]; then
        printf "  %s=%s\n" "$key" "$value"
      else
        printf "  %s=<empty>\n" "$key"
      fi
    done
  '
  echo

  echo "容器内 ChatGPT OAuth 网络检查："
  podman_exec_litellm sh -lc 'python - <<'"'"'PY'"'"'
import httpx
import os
import socket
import sys
from urllib.parse import urlparse

failed = False

proxy_url = (
    os.environ.get("HTTPS_PROXY")
    or os.environ.get("https_proxy")
    or os.environ.get("HTTP_PROXY")
    or os.environ.get("http_proxy")
)
checks = []
if proxy_url:
    parsed = urlparse(proxy_url)
    if parsed.hostname and parsed.port:
        checks.append((f"proxy {parsed.hostname}:{parsed.port}", parsed.hostname, parsed.port))
    else:
        failed = True
        print(f"  proxy parse fail: {proxy_url}")
checks.append(("auth.openai.com:443", "auth.openai.com", 443))

for label, host, port in checks:
    try:
        with socket.create_connection((host, port), timeout=5):
            print(f"  tcp {label} ok")
    except Exception as exc:
        failed = True
        print(f"  tcp {label} fail: {type(exc).__name__}: {exc}")

try:
    response = httpx.get(
        "https://auth.openai.com/codex/device",
        timeout=10,
        follow_redirects=False,
        trust_env=True,
    )
    print(f"  https://auth.openai.com/codex/device -> {response.status_code}")
    if response.status_code not in (200, 302):
        failed = True
except Exception as exc:
    failed = True
    print(f"  https://auth.openai.com/codex/device fail: {type(exc).__name__}: {exc}")

sys.exit(1 if failed else 0)
PY'

  echo
  echo "如果浏览器授权页提示“在 ChatGPT 安全设置中为 Codex 启用设备代码授权”，这是账号侧开关未开启。"
  echo "请先在 ChatGPT 安全设置里开启 Codex 设备代码授权，然后重新执行：./scripts/litellm.sh restart-chatgpt"
}

check_chatgpt_runtime() {
  check_chatgpt_env

  if ! container_is_running; then
    echo "❌ litellm-proxy-podman 未运行。请先执行：./scripts/litellm.sh restart-chatgpt"
    exit 1
  fi

  echo "Compose 中已废弃 Codex 环境变量检查："
  if compose config | grep -Eq 'LITELLM_CODEX_MODEL:|LITELLM_UPSTREAM_CODEX_MODEL:'; then
    echo "❌ compose 展开结果仍包含 LITELLM_CODEX_MODEL 或 LITELLM_UPSTREAM_CODEX_MODEL"
    exit 1
  fi
  echo "  未发现 LITELLM_CODEX_MODEL / LITELLM_UPSTREAM_CODEX_MODEL"
  echo

  echo "容器内 /app/config.yaml 的 Codex 配置："
  podman_exec_litellm sh -lc "grep -n 'codex-chatgpt\\|model_group_alias\\|model_name: gpt-5\\|model: chatgpt/gpt-5' /app/config.yaml || true" | sed 's/^/  /'
  echo

  if ! podman_exec_litellm sh -lc "python - <<'PY'
import yaml
with open('/app/config.yaml') as f:
    data = yaml.safe_load(f)
models = [m.get('model_name') for m in data.get('model_list', [])]
upstreams = [m.get('litellm_params', {}).get('model') for m in data.get('model_list', [])]
if any(value == 'codex-chatgpt' for value in models + upstreams) or 'router_settings' in data:
    raise SystemExit(1)
PY"; then
    echo "❌ 容器配置仍包含 codex-chatgpt 或 model_group_alias。请执行：./scripts/litellm.sh restart-chatgpt"
    exit 1
  fi

  echo "LiteLLM /v1/models 暴露状态："
  local models_json
  if ! models_json="$(model_list_json 2>/dev/null)"; then
    echo "❌ 无法读取 /v1/models，请先确认 LiteLLM 已就绪：curl http://localhost:${LITELLM_PORT:-4000}/health/readiness"
    exit 1
  fi

  printf "%s" "$models_json" | print_model_ids_from_json | sed 's/^/  /'
  if printf "%s" "$models_json" | grep -Eq '"id"[[:space:]]*:[[:space:]]*"codex-chatgpt"'; then
    echo
    echo "❌ /v1/models 仍暴露 codex-chatgpt。请确认容器已按最新 config.yaml 重建。"
    echo "请执行："
    echo "  ./scripts/litellm.sh restart-chatgpt"
    echo "  ./scripts/litellm.sh logs litellm"
    exit 1
  fi

  local codex_model
  local missing_codex_models=()
  for codex_model in gpt-5.5 gpt-5.4 gpt-5.4-mini gpt-5.3-codex gpt-5.3-codex-spark gpt-5.2; do
    if ! printf "%s" "$models_json" | grep -Eq '"id"[[:space:]]*:[[:space:]]*"'"$codex_model"'"'; then
      missing_codex_models+=("$codex_model")
    fi
  done

  if [[ "${#missing_codex_models[@]}" -eq 0 ]]; then
    echo "✅ Codex CLI/App 可见模型名均为标准模型名：gpt-5.5 gpt-5.4 gpt-5.4-mini gpt-5.3-codex gpt-5.3-codex-spark gpt-5.2"
  else
    echo "❌ /v1/models 缺少 Codex 标准模型：${missing_codex_models[*]}"
    echo "请执行：./scripts/litellm.sh restart-chatgpt"
    exit 1
  fi

  echo "✅ 容器运行态已加载 Codex 严格转发配置"
}

check_dashboard_auth() {
  local token_hash="${1:-}"

  if ! container_is_running; then
    echo "❌ litellm-proxy-podman 未运行。请先执行：./scripts/litellm.sh up"
    exit 1
  fi

  if ! db_container_is_running; then
    echo "❌ litellm-db-podman 未运行。请先执行：./scripts/litellm.sh up"
    exit 1
  fi

  echo "Dashboard 鉴权诊断："
  local token_count
  token_count="$(podman_exec_postgres psql -U litellm -d litellm -tAc 'select count(*) from "LiteLLM_VerificationToken";' 2>/dev/null || true)"
  echo "  LiteLLM_VerificationToken 记录数：${token_count:-<unknown>}"

  if [[ -n "$token_hash" ]]; then
    if [[ ! "$token_hash" =~ ^[0-9a-fA-F]{64}$ ]]; then
      echo "❌ token hash 格式不正确，应为 64 位十六进制字符串"
      exit 1
    fi

    local match_count
    match_count="$(podman_exec_postgres psql -U litellm -d litellm -tAc "select count(*) from \"LiteLLM_VerificationToken\" where token='${token_hash}';" 2>/dev/null || true)"
    echo "  指定 token hash 匹配数：${match_count:-<unknown>}"
  fi

  echo
  echo "如果 Dashboard 控制台报 Invalid proxy server token / token not found in db："
  echo "1. 关闭 http://localhost:${LITELLM_PORT:-4000}/ui 页面。"
  echo "2. 在该站点 DevTools Console 执行下面片段，清掉旧登录态："
  cat <<'EOF'
localStorage.clear();
sessionStorage.clear();
["/", "/ui"].forEach((path) => {
  document.cookie.split(";").forEach((cookie) => {
    document.cookie = cookie
      .replace(/^ +/, "")
      .replace(/=.*/, `=;expires=${new Date(0).toUTCString()};path=${path}`);
  });
});
location.href = "/ui";
EOF
  echo "3. 用当前 LITELLM_MASTER_KEY 重新登录 Dashboard。"
  echo "4. 若刚改过 LITELLM_MASTER_KEY，先执行 ./scripts/litellm.sh restart 再重新登录。"
}

case "${1:-up}" in
  print-chatgpt-env|chatgpt-env)
    print_chatgpt_env
    ;;

  print-client-env|client-env)
    print_client_env
    ;;

  print-codex-config|codex-config)
    print_codex_config
    ;;

  write-codex-model-catalog|codex-model-catalog)
    write_codex_model_catalog
    ;;

  check-chatgpt-env|doctor-chatgpt)
    check_chatgpt_env
    ;;

  check-client-env|doctor-client)
    check_client_env "${2:-all}"
    ;;

  check-chatgpt-runtime|doctor-chatgpt-runtime)
    check_chatgpt_runtime
    ;;

  check-chatgpt-network|doctor-chatgpt-network)
    check_chatgpt_network
    ;;

  check-dashboard-auth|doctor-dashboard)
    check_dashboard_auth "${2:-}"
    ;;

  up|start)
    prepare_runtime

    echo "🚀 启动 LiteLLM..."
    echo "📁 PostgreSQL 数据目录：$POSTGRES_DATA_DIR"
    echo "📁 ChatGPT token 目录：$CHATGPT_TOKEN_HOST_DIR"
    echo "🌐 容器代理：HTTP=$LITELLM_CONTAINER_HTTP_PROXY HTTPS=$LITELLM_CONTAINER_HTTPS_PROXY"
    compose up -d
    echo "✅ LiteLLM 已启动"
    echo "📌 访问地址：http://localhost:${LITELLM_PORT}"
    echo "📌 就绪检查：curl http://localhost:${LITELLM_PORT}/health/readiness"
    ;;

  down|stop)
    echo "🛑 停止 LiteLLM..."
    compose down
    echo "✅ LiteLLM 已停止"
    ;;

  restart)
    prepare_runtime
    echo "🔄 重新创建 LiteLLM（应用镜像、配置和资源限制变更）..."
    compose up -d --force-recreate litellm
    echo "✅ LiteLLM 已重新创建"
    ;;

  restart-chatgpt)
    check_chatgpt_env
    prepare_runtime
    echo "🔄 重新创建 LiteLLM（ChatGPT 订阅模式）..."
    compose up -d --force-recreate litellm
    echo "✅ LiteLLM 已重新创建"
    ;;

  recreate)
    prepare_runtime
    echo "🔄 重新创建 LiteLLM 和 PostgreSQL..."
    compose up -d --force-recreate
    echo "✅ LiteLLM 栈已重新创建"
    ;;

  logs)
    # 查看特定服务日志，默认查看 litellm 服务
    # 用法：./litellm.sh logs [litellm|postgres|all]
    case "${2:-litellm}" in
      litellm)
        compose logs -f litellm
        ;;
      postgres)
        compose logs -f postgres
        ;;
      all)
        compose logs -f
        ;;
      *)
        echo "用法：$0 logs [litellm|postgres|all]"
        exit 1
        ;;
    esac
    ;;

  status)
    compose ps
    ;;

  *)
    echo "用法：$0 {up|down|restart|restart-chatgpt|recreate|logs|status|check-chatgpt-env|check-chatgpt-runtime|check-chatgpt-network|check-dashboard-auth|print-chatgpt-env|print-client-env|print-codex-config|write-codex-model-catalog|check-client-env}"
    exit 1
    ;;
esac
