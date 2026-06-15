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
  export LITELLM_CODEX_MODEL="${LITELLM_CODEX_MODEL:-codex-chatgpt}"
  export LITELLM_UPSTREAM_CODEX_MODEL="${LITELLM_UPSTREAM_CODEX_MODEL:-chatgpt/gpt-5.5}"
  export LITELLM_CONTAINER_HTTP_PROXY="${LITELLM_CONTAINER_HTTP_PROXY-http://host.containers.internal:7890}"
  export LITELLM_CONTAINER_HTTPS_PROXY="${LITELLM_CONTAINER_HTTPS_PROXY-http://host.containers.internal:7890}"
}

print_chatgpt_env() {
  cat <<'EOF'
# ~/.env
# 网关访问密钥。默认可本地启动；建议替换为：openssl rand -hex 16
export LITELLM_MASTER_KEY=<替换为随机 token>

# Codex 默认只走 ChatGPT 订阅。只有需要换上游模型时才覆盖：
# export LITELLM_UPSTREAM_CODEX_MODEL=chatgpt/gpt-5.5

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
model_reasoning_effort = "medium"
model_catalog_json = "${catalog_path}"

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

  local failed=0

  if env_is_set LITELLM_CODEX_MODEL && [[ "$(env_value LITELLM_CODEX_MODEL)" != "codex-chatgpt" ]]; then
    echo "❌ LITELLM_CODEX_MODEL 当前为 '$(env_value LITELLM_CODEX_MODEL)'，ChatGPT 订阅模式需要 codex-chatgpt"
    failed=1
  fi

  if env_is_set LITELLM_UPSTREAM_CODEX_MODEL && [[ "$(env_value LITELLM_UPSTREAM_CODEX_MODEL)" != chatgpt/* ]]; then
    echo "❌ LITELLM_UPSTREAM_CODEX_MODEL 当前为 '$(env_value LITELLM_UPSTREAM_CODEX_MODEL)'，ChatGPT 订阅模式需要 chatgpt/... 模型"
    failed=1
  fi

  if env_is_set LITELLM_UPSTREAM_CODEX_MODEL && [[ "$(env_value LITELLM_UPSTREAM_CODEX_MODEL)" == "chatgpt/gpt-5.3-codex" ]]; then
    echo "❌ chatgpt/gpt-5.3-codex 不能用于当前 ChatGPT Codex 账号链路，请改用 chatgpt/gpt-5.5 或 chatgpt/gpt-5.4"
    failed=1
  fi

  if env_is_set LITELLM_UPSTREAM_CODEX_MODEL && [[ "$(env_value LITELLM_UPSTREAM_CODEX_MODEL)" == "chatgpt/gpt-5.3-codex-spark" ]]; then
    echo "⚠️  chatgpt/gpt-5.3-codex-spark 可用于基础 Responses API 验证，但 Codex CLI 会发送 image_generation 等工具；建议改用 chatgpt/gpt-5.5 或 chatgpt/gpt-5.4"
  fi

  if [[ "$failed" -ne 0 ]]; then
    echo
    echo "请修正 ~/.env 中覆盖的变量，并打开一个新的 zsh 后重试。可参考："
    print_chatgpt_env
    exit 1
  fi

  echo "✅ ChatGPT 订阅配置已就绪（未设置的变量使用内置默认值）"
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

  echo "宿主当前 zsh 环境："
  echo "  LITELLM_CODEX_MODEL=$(env_value LITELLM_CODEX_MODEL)"
  echo "  LITELLM_UPSTREAM_CODEX_MODEL=$(env_value LITELLM_UPSTREAM_CODEX_MODEL)"
  echo

  echo "Compose 展开环境："
  compose config | awk '
    /LITELLM_CODEX_MODEL:/ ||
    /LITELLM_UPSTREAM_CODEX_MODEL:/ {
      print "  " $0
    }
  '
  echo

  if ! container_is_running; then
    echo "❌ litellm-proxy-podman 未运行。请先执行：./scripts/litellm.sh restart-chatgpt"
    exit 1
  fi

  echo "容器运行态环境："
  podman_exec_litellm sh -lc '
    printf "  LITELLM_CODEX_MODEL=%s\n" "${LITELLM_CODEX_MODEL:-<unset>}"
    printf "  LITELLM_UPSTREAM_CODEX_MODEL=%s\n" "${LITELLM_UPSTREAM_CODEX_MODEL:-<unset>}"
  '
  echo

  echo "容器内 /app/config.yaml 的 Codex 配置："
  podman_exec_litellm sh -lc "grep -n 'LITELLM_CODEX\\|LITELLM_UPSTREAM_CODEX_MODEL\\|model_group_alias\\|gpt-5' /app/config.yaml || true" | sed 's/^/  /'
  echo

  if [[ "$(podman_exec_litellm sh -lc 'printf "%s" "${LITELLM_CODEX_MODEL:-}"')" != "codex-chatgpt" ]]; then
    echo "❌ 容器内 LITELLM_CODEX_MODEL 不是 codex-chatgpt。请执行：./scripts/litellm.sh restart-chatgpt"
    exit 1
  fi

  echo "LiteLLM /v1/models 暴露状态："
  local models_json
  if ! models_json="$(model_list_json 2>/dev/null)"; then
    echo "❌ 无法读取 /v1/models，请先确认 LiteLLM 已就绪：curl http://localhost:${LITELLM_PORT:-4000}/health/readiness"
    exit 1
  fi

  printf "%s" "$models_json" | print_model_ids_from_json | sed 's/^/  /'
  if ! printf "%s" "$models_json" | grep -Eq '"id"[[:space:]]*:[[:space:]]*"codex-chatgpt"'; then
    echo
    echo "❌ 容器环境已加载 codex-chatgpt，但 LiteLLM 没有把它暴露到 /v1/models。"
    echo "常见原因：启动时 ChatGPT OAuth 轮询 auth.openai.com 超时，LiteLLM 会忽略该 deployment。"
    echo "请执行："
    echo "  ./scripts/litellm.sh check-chatgpt-network"
    echo "  ./scripts/litellm.sh restart-chatgpt"
    echo "  ./scripts/litellm.sh logs litellm"
    exit 1
  fi

  local codex_model
  local missing_codex_models=()
  for codex_model in gpt-5.5 gpt-5.4 gpt-5.4-mini gpt-5.3-codex gpt-5.2; do
    if ! printf "%s" "$models_json" | grep -Eq '"id"[[:space:]]*:[[:space:]]*"'"$codex_model"'"'; then
      missing_codex_models+=("$codex_model")
    fi
  done

  if [[ "${#missing_codex_models[@]}" -eq 0 ]]; then
    echo "✅ Codex CLI/App 可见模型名已映射到 codex-chatgpt：gpt-5.5 gpt-5.4 gpt-5.4-mini gpt-5.3-codex gpt-5.2"
  else
    echo "⚠️  /v1/models 缺少 Codex 候选模型：${missing_codex_models[*]}；如果 Codex CLI 仍报 key not allowed，请执行：./scripts/litellm.sh restart-chatgpt"
  fi

  echo "✅ 容器运行态已加载并暴露 codex-chatgpt"
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
