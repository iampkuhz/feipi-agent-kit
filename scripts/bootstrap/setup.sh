#!/usr/bin/env bash
# 只读检查新机所需依赖，不安装软件、不启动虚拟机、不生成个人配置。
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=../../tools/lib/podman.sh
source "$REPO_ROOT/tools/lib/podman.sh"

printf '%s\n' 'Feipi Agent Kit 新机检查（只读）'
if ! command -v python3 >/dev/null 2>&1; then
  echo '请先通过 Dotfiles 安装 Python 3.10+。' >&2
  exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "需要 Python 3.10+")'
python3 --version
podman_require_cli
podman --version
# 直接运行 provider 的版本命令，不把 docker 客户端存在当成 Compose 已安装。
if [[ -n "${PODMAN_COMPOSE_PROVIDER:-}" ]]; then
  "$PODMAN_COMPOSE_PROVIDER" --version
elif command -v podman-compose >/dev/null 2>&1; then
  podman-compose --version
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose version
else
  echo '缺少 Compose provider，请通过 Dotfiles 安装 podman-compose。' >&2
  exit 1
fi
podman_require_runtime

# 只核实固定服务的定义存在；按需启动，不把所有服务设为必需项。
for config in \
  tools/search/searxng/compose/docker-compose.yml \
  tools/crawl/crawl4ai/compose/docker-compose.yml \
  tools/gateway/litellm/compose/docker-compose.yml \
  tools/gateway/otel/compose/docker-compose.yml; do
  [[ -f "$REPO_ROOT/$config" ]] || {
    echo "缺少服务定义：$config" >&2
    exit 1
  }
done
if command -v uv >/dev/null 2>&1; then
  uv --version
else
  echo 'uv 未安装：部分 skill/MCP 需要时再通过 Dotfiles 安装。'
fi
printf '%s\n' '检查通过。按需执行 make searxng-up / crawl4ai-up / litellm-up / otel-up。' \
  '新机恢复说明：docs/setup-new-mac.md；不需要复制容器镜像或 Podman VM。'
