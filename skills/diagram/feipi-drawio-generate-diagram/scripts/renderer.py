"""有界 Podman 本地预检与 HTTP 客户端；不读取 HTTP 代理。"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from core import require

CONTAINER = 'feipi-drawio'
IMAGE = 'localhost/feipi/drawio-renderer:1'
HEALTH_TIMEOUT = 30


class RendererError(ValueError):
    def __init__(self, code, reason, *, command=None, exit_code=None, stderr='', next_steps=()):
        self.details = {'code': code}
        if command:
            self.details['command'] = command
        if exit_code is not None:
            self.details['exit_code'] = exit_code
        if stderr:
            self.details['stderr'] = stderr[-2000:].strip()
            reason += ': ' + self.details['stderr']
        if next_steps:
            self.details['next_steps'] = list(next_steps)
        super().__init__(reason)


def failure(exc):
    return {'status': 'blocked', 'reason': str(exc), **getattr(exc, 'details', {})}


def preparation_command():
    return shlex.join(['python3', str(Path(__file__).resolve().with_name('prepare_renderer.py'))])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('本地服务不得重定向')


def endpoint():
    raw = os.environ.get('AGENT_DRAWIO_SERVER_PORT', '8200')
    if not raw.isascii() or not raw.isdigit() or not 1024 <= int(raw) <= 65535:
        raise RendererError('invalid_port', 'AGENT_DRAWIO_SERVER_PORT 须在 1024–65535')
    port = int(raw)
    return f'http://127.0.0.1:{port}'


def request(path, data=None, *, timeout=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(endpoint() + path, body, {'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout if timeout is not None else (60 if data is not None else 3)) as response:
            raw = response.read(32 * 1024 * 1024 + 1)
            require(len(raw) <= 32 * 1024 * 1024, '渲染响应超过 32 MiB')
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        reason = f'本地 renderer HTTP {exc.code}: {exc.read(1500).decode(errors="replace")}'
        if path == '/health' and exc.code in (502, 503, 504):
            raise urllib.error.URLError(reason) from exc
        raise RendererError('renderer_http_error', reason) from exc


def podman(*args, missing_ok=False):
    command = ['podman', *args]
    try:
        result = subprocess.run(command, text=True, errors='replace', capture_output=True, timeout=30)
    except FileNotFoundError as exc:
        raise RendererError('podman_missing', '未找到 Podman；请先安装 Podman', command=command,
                            next_steps=['macOS: brew install podman', preparation_command()]) from exc
    except subprocess.TimeoutExpired as exc:
        detail = exc.stderr or ''
        if isinstance(detail, bytes):
            detail = detail.decode(errors='replace')
        raise RendererError('podman_timeout', 'Podman 命令超过 30 秒', command=command, stderr=detail) from exc
    except OSError as exc:
        raise RendererError('podman_failed', f'无法执行 Podman: {exc}', command=command) from exc
    if missing_ok and result.returncode == 1 and not result.stderr.strip():
        return None
    if result.returncode:
        raise RendererError('engine_unavailable' if args == ('info',) else 'podman_failed',
                            f'Podman 命令失败（exit {result.returncode}）', command=command,
                            exit_code=result.returncode, stderr=result.stderr,
                            next_steps=[preparation_command()] if args == ('info',) else [])
    return result.stdout


def podman_json(*args):
    try:
        return json.loads(podman(*args))
    except json.JSONDecodeError as exc:
        raise RendererError('podman_invalid_response', f'Podman 返回无效 JSON: {exc}',
                            command=['podman', *args]) from exc


def ensure_local():
    # macOS 的 SSH 连接仅允许回环 Podman machine；远端服务不属于本地渲染。
    for key in ('CONTAINER_HOST', 'CONTAINER_CONNECTION'):
        if os.environ.get(key):
            raise RendererError('connection_rejected', f'请清除 {key}，使用默认本地 Podman')
    connections = podman_json('system', 'connection', 'list', '--format', 'json')
    require(connections is None or isinstance(connections, list), 'Podman 连接列表格式错误')
    for connection in connections or []:
        if connection.get('Default'):
            uri = urlsplit(connection.get('URI', ''))
            if not (uri.scheme == 'unix' and not uri.netloc or
                    uri.scheme == 'ssh' and uri.hostname in {'localhost', '127.0.0.1', '::1'}):
                raise RendererError('connection_rejected', '默认 Podman 连接不是本地服务')


def wait_ready():
    deadline = time.monotonic() + HEALTH_TIMEOUT
    while True:
        try:
            result = request('/health', timeout=max(0.01, min(3, deadline - time.monotonic())))
            if not (isinstance(result, dict) and result.get('status') == 'ready' and
                    result.get('service') == 'feipi-drawio' and result.get('network') == 'local-only' and
                    result.get('contract') == 1):
                raise RendererError('health_contract_mismatch', 'renderer 健康合同不符；请检查端口及专用容器')
            return result
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RendererError('health_contract_mismatch', f'renderer 健康响应格式无效: {exc}') from exc
        except (urllib.error.URLError, OSError) as exc:
            if time.monotonic() >= deadline:
                raise RendererError('health_unavailable', f'本地 renderer 在 {HEALTH_TIMEOUT} 秒内未就绪: {exc}',
                                    next_steps=[shlex.join(['podman', 'logs', '--tail', '50', CONTAINER])]) from exc
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))


def preflight(existing_only=False):
    endpoint()  # 输入错误先于任何服务操作。
    ensure_local()
    podman('info')
    if podman('container', 'exists', CONTAINER, missing_ok=True) is None:
        image_missing = podman('image', 'exists', IMAGE, missing_ok=True) is None
        raise RendererError('image_missing' if image_missing else 'container_missing',
                            f'专用容器 {CONTAINER} 不存在' + (f'，镜像 {IMAGE} 也未准备' if image_missing else '，镜像已准备'),
                            next_steps=[preparation_command()])
    containers = podman_json('container', 'inspect', CONTAINER)
    require(isinstance(containers, list) and len(containers) == 1, 'Podman 容器信息格式错误')
    c = containers[0]
    expected = [{'HostIp': '127.0.0.1', 'HostPort': str(urlsplit(endpoint()).port)}]
    if not (c.get('Config', {}).get('Image') == IMAGE and
            (c['Config'].get('Labels') or {}).get('app') == 'feipi-drawio' and
            (c.get('HostConfig', {}).get('PortBindings') or {}).get('8080/tcp') == expected):
        raise RendererError('container_mismatch', '同名容器镜像、标签或 loopback 端口不符；请人工检查，未修改容器')
    started = False
    if not c['State']['Running']:
        if existing_only:
            raise RendererError('container_stopped', 'renderer 未运行；只读预检不允许启动',
                                next_steps=[preparation_command()])
        podman('start', CONTAINER)
        started = True
    # 仅重试只读健康探测，渲染请求不重试；不拉镜像、不建容器、不重启。
    result = wait_ready()
    return {'renderer_url': endpoint(), 'podman_container': CONTAINER,
            'startup_performed': started, 'startup_policy': 'podman_once', **result}
