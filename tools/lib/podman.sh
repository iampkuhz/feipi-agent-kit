#!/usr/bin/env bash
# 本地服务共用的 Podman 检查与 Compose 调用；不安装软件、不启动或切换虚拟机。

podman_require_cli() {
  if ! command -v podman >/dev/null 2>&1; then
    echo '未找到 Podman，请先通过 Dotfiles 安装 podman 和 podman-compose。' >&2
    return 1
  fi
}

agent_service_data_root() {
  # bind mount 和 mkdir 必须解释成同一个绝对路径，不能随调用目录漂移。
  export AGENT_SERVICE_DATA_DIR="${AGENT_SERVICE_DATA_DIR:-$HOME/Documents/service-data}"
  if [[ "$AGENT_SERVICE_DATA_DIR" != /* ]]; then
    echo 'AGENT_SERVICE_DATA_DIR 必须是绝对路径。' >&2
    return 1
  fi
}

podman_require_runtime() {
  podman_require_cli || return 1
  # 连接和就绪探测限时执行，避免新机尚未准备 machine 时长时间等待。
  # 只允许默认本地连接，防止本机启动命令意外操作另一台机器。
  python3 - <<'PY'
import json
import os
import subprocess
import urllib.parse

try:
    if os.environ.get("CONTAINER_HOST") or os.environ.get("CONTAINER_CONNECTION"):
        raise ValueError("请清除 CONTAINER_HOST/CONTAINER_CONNECTION，使用默认本地 Podman")
    result = subprocess.run(
        ["podman", "system", "connection", "list", "--format", "json"],
        check=True, capture_output=True, text=True, timeout=10,
    )
    for connection in (json.loads(result.stdout) or []):
        if connection.get("Default"):
            uri = urllib.parse.urlsplit(connection.get("URI", ""))
            if not (uri.scheme == "unix" or
                    (uri.scheme == "ssh" and uri.hostname in {"localhost", "127.0.0.1", "::1"})):
                raise ValueError("默认 Podman 连接不是本机，未修改任何服务")
    subprocess.run(["podman", "info"], check=True, capture_output=True, timeout=10)
except (OSError, ValueError, subprocess.SubprocessError):
    raise SystemExit("本地 Podman 未就绪或连接不是本机。macOS 首次执行 podman machine init，再执行 podman machine start；已有 machine 只需启动。未修改任何服务。")
PY
}

podman_compose() {
  podman_require_cli || return 1
  # Podman 自身负责传递 socket；优先使用 Dotfiles 提供的 podman-compose。
  # 用户显式指定的标准 PODMAN_COMPOSE_PROVIDER 优先，不改写其持久配置。
  if [[ -z "${PODMAN_COMPOSE_PROVIDER:-}" ]] && command -v podman-compose >/dev/null 2>&1; then
    PODMAN_COMPOSE_PROVIDER="$(command -v podman-compose)" podman compose "$@"
  else
    podman compose "$@"
  fi
}
