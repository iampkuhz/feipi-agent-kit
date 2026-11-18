#!/usr/bin/env bash
# 从固定 Compose 定义管理本地服务；不安装软件、不导出容器。
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=../../../lib/podman.sh
source "$SERVICE_DIR/../../lib/podman.sh"
case "${1:-up}" in
up | down | restart | logs | status)
  podman_require_runtime
  case "${1:-up}" in
  up) action=(up -d) ;;
  down) action=(down) ;;
  restart) action=(up -d --force-recreate) ;;
  logs) action=(logs --tail 50) ;;
  status) action=(ps) ;;
  esac
  # 配置由 Compose 和版本化的 config.yml 提供。
  podman_compose --env-file /dev/null -f "$SERVICE_DIR/compose/docker-compose.yml" "${action[@]}"
  ;;
*)
  echo '用法：crawl4ai.sh up|down|restart|logs|status' >&2
  exit 2
  ;;
esac
