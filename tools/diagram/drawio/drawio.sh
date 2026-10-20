#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE=localhost/feipi/drawio-renderer:1
REVISION=c9904435fd1a6795f6cad5c3908ec89d9afb8fb1
SHA256=90acf10c43751f245873506e6748d868e24da8bd863e96dd0aeeb48ba32baee7
ACTION="${1:-help}"
case "$ACTION" in
help|-h|--help)
  echo '用法：drawio.sh ensure|prepare|up|status|down|logs（仅 Podman 本地服务）'
  exit 0 ;;
ensure|prepare|up|status|down|logs) ;;
*) echo "未知操作：$ACTION" >&2; exit 1 ;;
esac
for dependency in python3 podman; do
  command -v "$dependency" >/dev/null || {
    echo "缺少 $dependency；请先安装 Python 3.10+ 与 Podman（macOS: brew install python podman）" >&2
    exit 1
  }
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "需要 Python 3.10+")'

if [[ "$ACTION" != prepare ]]; then
  exec python3 "$ROOT/runtime.py" "$ACTION"
fi
for dependency in curl tar; do
  command -v "$dependency" >/dev/null || { echo "准备阶段缺少 $dependency" >&2; exit 1; }
done
python3 "$ROOT/runtime.py" engine --prepare
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/feipi-drawio-build.XXXXXX")"
trap 'rm -rf "$BUILD_DIR"' EXIT
trap 'rc=$?; echo "draw.io 准备失败（exit $rc），请查看上方下载、校验或构建的具体错误。" >&2; exit "$rc"' ERR
curl --fail --location --connect-timeout 10 --max-time 180 \
  "https://codeload.github.com/jgraph/drawio/tar.gz/$REVISION" -o "$BUILD_DIR/drawio.tar.gz"
python3 - "$BUILD_DIR/drawio.tar.gz" "$SHA256" <<'HASH'
import hashlib, pathlib, sys
if hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise SystemExit('draw.io 源码校验和不匹配')
HASH
tar -xzf "$BUILD_DIR/drawio.tar.gz" -C "$BUILD_DIR" "drawio-$REVISION/src/main/webapp"
mv "$BUILD_DIR/drawio-$REVISION/src/main/webapp" "$BUILD_DIR/webapp"
cp "$ROOT/Containerfile" "$ROOT/server.py" "$ROOT/render.js" "$BUILD_DIR/"
if [[ -n "${AGENT_DRAWIO_BUILD_PROXY:-}" ]]; then
  podman build --build-arg "http_proxy=$AGENT_DRAWIO_BUILD_PROXY" \
    --build-arg "https_proxy=$AGENT_DRAWIO_BUILD_PROXY" \
    -t "$IMAGE" -f "$BUILD_DIR/Containerfile" "$BUILD_DIR"
else
  # macOS 自带 Bash 3.2 在 set -u 下不能展开空数组。
  podman build -t "$IMAGE" -f "$BUILD_DIR/Containerfile" "$BUILD_DIR"
fi
