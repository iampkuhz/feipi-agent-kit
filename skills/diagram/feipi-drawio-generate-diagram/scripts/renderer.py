"""有界 Podman 本地预检与 HTTP 客户端；不读取 HTTP 代理。"""
import json
import os
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from core import require

CONTAINER = 'feipi-drawio'
IMAGE = 'localhost/feipi/drawio-renderer:1'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('本地服务不得重定向')


def endpoint():
    port = int(os.environ.get('AGENT_DRAWIO_SERVER_PORT', '8200'))
    require(1024 <= port <= 65535, '端口须在 1024–65535')
    return f'http://127.0.0.1:{port}'


def request(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(endpoint() + path, body, {'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=60 if data is not None else 3) as response:
            raw = response.read(32 * 1024 * 1024 + 1)
            require(len(raw) <= 32 * 1024 * 1024, '渲染响应超过 32 MiB')
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise ValueError(f'本地 renderer HTTP {exc.code}: {exc.read(1500).decode(errors="replace")}') from exc


def podman(*args):
    return subprocess.check_output(['podman', *args], text=True, stderr=subprocess.PIPE, timeout=30)


def ensure_local():
    # macOS 的 SSH 连接仅允许回环 Podman machine；远端服务不属于本地渲染。
    for key in ('CONTAINER_HOST', 'CONTAINER_CONNECTION'):
        require(not os.environ.get(key), f'请清除 {key}，使用默认本地 Podman')
    connections = json.loads(podman('system', 'connection', 'list', '--format', 'json'))
    for connection in connections:
        if connection.get('Default'):
            uri = urlsplit(connection.get('URI', ''))
            require(uri.scheme == 'unix' or (uri.scheme == 'ssh' and uri.hostname in {'localhost', '127.0.0.1', '::1'}),
                    '默认 Podman 连接不是本地服务')


def preflight(existing_only=False):
    ensure_local()
    containers = json.loads(podman('inspect', CONTAINER))
    c = containers[0]
    expected = [{'HostIp': '127.0.0.1', 'HostPort': str(urlsplit(endpoint()).port)}]
    require(c['Config']['Image'] == IMAGE and c['Config'].get('Labels', {}).get('app') == 'feipi-drawio',
            '容器来源不符，请执行工具目录的 prepare/up')
    require(c['HostConfig']['PortBindings'].get('8080/tcp') == expected, '容器必须仅绑定当前 loopback 端口')
    started = False
    if not c['State']['Running']:
        require(not existing_only, 'renderer 未运行；只读预检不允许启动')
        podman('start', CONTAINER)
        started = True
    # 首次启动等待一次，不拉镜像、不建容器、不重启或杀进程。
    if started:
        import time
        time.sleep(2)
    result = request('/health')
    require(result.get('status') == 'ready' and result.get('service') == 'feipi-drawio' and
            result.get('network') == 'local-only' and result.get('contract') == 1, 'renderer 健康合同不符')
    return {'renderer_url': endpoint(), 'podman_container': CONTAINER,
            'startup_performed': started, 'startup_policy': 'podman_once', **result}
