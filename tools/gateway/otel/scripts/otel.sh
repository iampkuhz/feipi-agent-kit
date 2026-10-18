#!/usr/bin/env bash
# OTel 日志可重新生成；只从仓库配置创建服务，不迁移旧日志或容器镜像。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=../../../lib/podman.sh
source "$SERVICE_DIR/../../lib/podman.sh"
agent_service_data_root

case "${1:-up}" in
up | start | restart)
  podman_require_runtime
  # 只在明确启动时创建本机目录；status/check 不落盘。
  mkdir -p "$AGENT_SERVICE_DATA_DIR/otel"
  action=(up -d)
  # restart 显式重建，使配置与容器环境变更真正生效；不删除数据目录。
  if [[ "${1:-up}" == restart ]]; then
    action+=(--force-recreate)
  fi
  podman_compose --env-file /dev/null -f "$SERVICE_DIR/compose/docker-compose.yml" "${action[@]}"
  ;;
down | stop)
  podman_require_runtime
  podman_compose --env-file /dev/null -f "$SERVICE_DIR/compose/docker-compose.yml" down
  ;;
status | logs)
  podman_require_runtime
  if [[ "$1" == status ]]; then
    podman_compose --env-file /dev/null -f "$SERVICE_DIR/compose/docker-compose.yml" ps
  else
    podman_compose --env-file /dev/null -f "$SERVICE_DIR/compose/docker-compose.yml" logs --tail 50
  fi
  ;;
*)
  echo '用法：otel.sh up|down|restart|status|logs' >&2
  exit 2
  ;;
esac
