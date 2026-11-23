#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib/podman.sh
source "$root/../lib/podman.sh"
podman_require_runtime

compose() {
  podman_compose --env-file /dev/null -f "$root/compose/docker-compose.yml" "$@"
}

drawio() {
  bash "$root/drawio/drawio.sh" "$@"
}

ready() {
  local curl_args=(--noproxy '*' -fsS --retry 12 --retry-connrefused --retry-delay 1 --max-time 10
    -H 'Content-Type: text/plain; charset=utf-8' -o /dev/null)
  curl "${curl_args[@]}" --data-binary @- 'http://127.0.0.1:8199/svg' <<< $'@startuml\nAlice -> Bob\n@enduml'
  curl "${curl_args[@]}" --data-binary $'flowchart TD\n  A --> B' 'http://127.0.0.1:8201/svg'
  echo 'draw.io、PlantUML 和 Mermaid 已就绪。'
}

case "${1:-}" in
  up) compose up -d; drawio ensure; ready ;;
  down) compose down; drawio down ;;
  restart) compose up -d --force-recreate; drawio restart; ready ;;
  status) compose ps; drawio status; ready ;;
  logs) compose logs --tail 50; drawio logs ;;
  *) echo '用法：workbench service diagrams up|down|restart|status|logs' >&2; exit 2 ;;
esac
