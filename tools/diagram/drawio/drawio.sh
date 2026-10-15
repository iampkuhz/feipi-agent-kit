#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE=localhost/feipi/drawio-renderer:1
CONTAINER=feipi-drawio
PORT="${AGENT_DRAWIO_SERVER_PORT:-8200}"
REVISION=c9904435fd1a6795f6cad5c3908ec89d9afb8fb1
SHA256=90acf10c43751f245873506e6748d868e24da8bd863e96dd0aeeb48ba32baee7
[[ "$PORT" =~ ^[0-9]+$ ]] && ((PORT > 1023 && PORT < 65536)) || {
  echo '端口须在 1024–65535' >&2
  exit 1
}
command -v podman >/dev/null || {
  echo '请先安装 Podman（macOS: brew install podman）' >&2
  exit 1
}
python3 - <<'PY'
import json, os, subprocess, urllib.parse
if os.environ.get('CONTAINER_HOST') or os.environ.get('CONTAINER_CONNECTION'):
    raise SystemExit('请清除 CONTAINER_HOST/CONTAINER_CONNECTION，使用默认本地 Podman')
connections = json.loads(subprocess.check_output(['podman', 'system', 'connection', 'list', '--format', 'json'], timeout=10))
for connection in connections:
    if connection.get('Default'):
        uri = urllib.parse.urlsplit(connection.get('URI', ''))
        if not (uri.scheme == 'unix' or (uri.scheme == 'ssh' and uri.hostname in {'localhost', '127.0.0.1', '::1'})):
            raise SystemExit('默认 Podman 连接不是本地服务，未修改环境')
PY

case "${1:-help}" in
prepare)
  # 只在显式准备阶段初始化/启动本地虚拟机，不修改远程连接或代理配置。
  if ! podman info >/dev/null 2>&1; then
    if [[ "$(uname -s)" == Darwin ]]; then
      podman machine inspect podman-machine-default >/dev/null 2>&1 || podman machine init
      podman machine start podman-machine-default
    else
      echo 'Podman 不可用，请先修复本地 Podman 环境' >&2
      exit 1
    fi
  fi
  BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/feipi-drawio-build.XXXXXX")"
  trap 'rm -rf "$BUILD_DIR"' EXIT
  curl --fail --location --connect-timeout 10 --max-time 180 \
    "https://codeload.github.com/jgraph/drawio/tar.gz/$REVISION" -o "$BUILD_DIR/drawio.tar.gz"
  python3 - "$BUILD_DIR/drawio.tar.gz" "$SHA256" <<'PY'
import hashlib, pathlib, sys
if hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise SystemExit('draw.io 源码校验和不匹配')
PY
  tar -xzf "$BUILD_DIR/drawio.tar.gz" -C "$BUILD_DIR" "drawio-$REVISION/src/main/webapp"
  mv "$BUILD_DIR/drawio-$REVISION/src/main/webapp" "$BUILD_DIR/webapp"
  cp "$ROOT/Containerfile" "$ROOT/server.py" "$ROOT/render.js" "$BUILD_DIR/"
  BUILD_ARGS=()
  if [[ -n "${AGENT_DRAWIO_BUILD_PROXY:-}" ]]; then
    BUILD_ARGS+=(--build-arg "http_proxy=$AGENT_DRAWIO_BUILD_PROXY" --build-arg "https_proxy=$AGENT_DRAWIO_BUILD_PROXY")
  fi
  podman build "${BUILD_ARGS[@]}" -t "$IMAGE" -f "$BUILD_DIR/Containerfile" "$BUILD_DIR"
  ;;
up)
  podman info >/dev/null
  if podman container exists "$CONTAINER"; then
    # 不接管同名但不同镜像/端口的容器。
    python3 - "$CONTAINER" "$IMAGE" "$PORT" <<'PY'
import json, subprocess, sys
c = json.loads(subprocess.check_output(['podman', 'inspect', sys.argv[1]]))[0]
bindings = c['HostConfig']['PortBindings'].get('8080/tcp', [])
if c['Config']['Image'] != sys.argv[2] or c['Config'].get('Labels', {}).get('app') != 'feipi-drawio' or bindings != [{'HostIp': '127.0.0.1', 'HostPort': sys.argv[3]}]:
    raise SystemExit('同名容器配置不符，请人工检查；未修改容器')
PY
    podman start "$CONTAINER" >/dev/null
  else
    podman image exists "$IMAGE" || {
      echo '请先执行 drawio.sh prepare' >&2
      exit 1
    }
    podman run -d --name "$CONTAINER" --label app=feipi-drawio \
      --security-opt=no-new-privileges --cap-drop=all --read-only \
      --tmpfs /tmp:rw,size=512m --shm-size=256m --memory=2g --pids-limit=256 \
      -p "127.0.0.1:$PORT:8080" "$IMAGE" >/dev/null
  fi
  for ((i = 0; i < 30; i++)); do
    if curl --noproxy '*' -fsS --max-time 2 "http://127.0.0.1:$PORT/health" 2>/dev/null; then
      printf '\n'
      exit 0
    fi
    sleep 1
  done
  echo '本地渲染服务未就绪；请查看 drawio.sh logs' >&2
  exit 1
  ;;
status)
  curl --noproxy '*' -fsS --max-time 3 "http://127.0.0.1:$PORT/health"
  printf '\n'
  ;;
down) podman stop "$CONTAINER" ;;
logs) podman logs --tail 50 "$CONTAINER" ;;
*) echo '用法：drawio.sh prepare|up|status|down|logs（仅 Podman 本地服务）' ;;
esac
