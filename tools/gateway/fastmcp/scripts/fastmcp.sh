#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../../../lib/podman.sh
source "$root/../../../lib/podman.sh"
podman_require_runtime

case "${1:-}" in
  up) action=(up -d) ;;
  down) action=(down) ;;
  restart) action=(up -d --build --force-recreate) ;;
  status) action=(ps) ;;
  logs) action=(logs --tail 50) ;;
  *) echo '用法：workbench service fastmcp up|down|restart|status|logs' >&2; exit 2 ;;
esac
podman_compose --env-file /dev/null -f "$root/../compose/docker-compose.yml" "${action[@]}"
