#!/usr/bin/env python3
"""专用 draw.io 服务的显式环境管理；不接管其他容器或远端连接。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from network import allow_slow, confirmation

ROOT = Path(__file__).resolve().parent
IMAGE = 'localhost/feipi/drawio-renderer:1'
CONTAINER = 'feipi-drawio'


class ToolError(ValueError):
    def __init__(self, reason, *, command=None, exit_code=None, stderr=''):
        self.details = {'status': 'blocked', 'reason': reason}
        if command:
            self.details['command'] = command
        if exit_code is not None:
            self.details['exit_code'] = exit_code
        if stderr:
            self.details['stderr'] = stderr[-2000:].strip()
        super().__init__(reason)


def podman(*args, missing_ok=False, timeout=30):
    command = ['podman', *args]
    try:
        result = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        stderr = getattr(exc, 'stderr', '') or ''
        if isinstance(stderr, bytes): stderr = stderr.decode(errors='replace')
        raise ToolError(f'无法完成 Podman 命令: {exc}', command=command, stderr=stderr) from exc
    if missing_ok and result.returncode == 1 and not result.stderr.strip():
        return None
    if result.returncode:
        raise ToolError('Podman 命令失败', command=command, exit_code=result.returncode,
                               stderr=result.stderr)
    return result.stdout + result.stderr if args[:1] == ('logs',) else result.stdout


def local_connection():
    for key in ('CONTAINER_HOST', 'CONTAINER_CONNECTION'):
        if os.environ.get(key):
            raise ToolError(f'请清除 {key}，使用默认本地 Podman；未修改环境')
    for connection in json.loads(podman('system', 'connection', 'list', '--format', 'json')) or []:
        if connection.get('Default'):
            uri = urlsplit(connection.get('URI', ''))
            if not (uri.scheme == 'unix' and not uri.netloc or
                    uri.scheme == 'ssh' and uri.hostname in {'localhost', '127.0.0.1', '::1'}):
                raise ToolError('默认 Podman 连接不是本地服务；未修改环境')


def engine(prepare=False):
    if prepare:
        allow_slow()
    local_connection()
    try:
        podman('info')
        return
    except ToolError as original:
        if not prepare or sys.platform != 'darwin' or 'exit_code' not in original.details:
            raise
        machines = json.loads(podman('machine', 'list', '--format', 'json')) or []
        if not machines:
            limit = 600 if allow_slow() else 300
            try:
                podman('machine', 'init', timeout=limit)
            except ToolError as exc:
                if isinstance(exc.__cause__, subprocess.TimeoutExpired):
                    raise confirmation('machine_init', f'Podman machine 初始化超过 {limit} 秒；下载或解压可能较慢，需确认后再处理已有初始化状态',
                                       'https://quay.io/v2/') from exc
                raise
            name = 'podman-machine-default'
        else:
            defaults = [m for m in machines if m.get('Default')]
            selected = defaults[0] if len(defaults) == 1 else (machines[0] if len(machines) == 1 else None)
            if selected is None or selected.get('Running') or selected.get('Starting'):
                # 引擎故障不能一律当作缺虚拟机，不能创建第二台或切换连接。
                raise original
            name = selected['Name']
        podman('machine', 'start', name, timeout=180)
        local_connection()
        deadline = time.monotonic() + 30
        while True:
            try:
                podman('info', timeout=max(0.01, min(5, deadline - time.monotonic())))
                return
            except ToolError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(min(0.5, max(0, deadline - time.monotonic())))


def port():
    raw = os.environ.get('AGENT_DRAWIO_SERVER_PORT', '8200')
    if not raw.isascii() or not raw.isdigit() or not 1024 <= int(raw) <= 65535:
        raise ToolError('AGENT_DRAWIO_SERVER_PORT 须在 1024–65535')
    return str(int(raw))


def container():
    if podman('container', 'exists', CONTAINER, missing_ok=True) is None:
        return None
    data = json.loads(podman('container', 'inspect', CONTAINER))
    if not isinstance(data, list) or len(data) != 1:
        raise ToolError('Podman 容器信息格式错误')
    c = data[0]
    expected = [{'HostIp': '127.0.0.1', 'HostPort': port()}]
    if not (c.get('Config', {}).get('Image') == IMAGE and
            (c['Config'].get('Labels') or {}).get('app') == 'feipi-drawio' and
            (c.get('HostConfig', {}).get('PortBindings') or {}).get('8080/tcp') == expected):
        raise ToolError('同名容器镜像、标签或 loopback 端口不符；请人工检查，未修改容器')
    return c


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ToolError('本地服务不得重定向')


def health():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    deadline = time.monotonic() + 30
    while True:
        try:
            with opener.open(f'http://127.0.0.1:{port()}/health',
                             timeout=max(0.01, min(3, deadline - time.monotonic()))) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ToolError('健康响应过大')
                data = json.loads(raw)
            if not (isinstance(data, dict) and data.get('status') == 'ready' and
                    data.get('service') == 'feipi-drawio' and data.get('contract') == 1 and
                    data.get('network') == 'local-only'):
                raise ToolError('renderer 健康合同不符，请检查端口及专用容器')
            return data
        except (urllib.error.URLError, OSError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (502, 503, 504):
                raise ToolError(f'renderer 健康请求 HTTP {exc.code}: {exc.read(1500).decode(errors="replace")}') from exc
            if time.monotonic() >= deadline:
                raise ToolError(f'本地 renderer 在 30 秒内未就绪: {exc}；请执行 drawio.sh logs') from exc
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))


def manage(action):
    port()
    engine(prepare=action == 'ensure')
    c = container()
    if action == 'ensure' and c is None:
        if podman('image', 'exists', IMAGE, missing_ok=True) is None:
            result = subprocess.run(['bash', str(ROOT / 'drawio.sh'), 'prepare'])
            if result.returncode:
                error = ToolError('镜像准备失败；上方保留下载/构建的原始错误', exit_code=result.returncode)
                if result.returncode == 75:
                    error.details.update(code='download_confirmation_required', confirmation_required=True)
                raise error
    if action in ('up', 'ensure'):
        if c is None:
            if podman('image', 'exists', IMAGE, missing_ok=True) is None:
                raise ToolError('专用镜像未准备；请执行 drawio.sh prepare 或 ensure')
            podman('run', '-d', '--pull=never', '--name', CONTAINER, '--label', 'app=feipi-drawio',
                   '--security-opt=no-new-privileges', '--cap-drop=all', '--read-only',
                   '--tmpfs', '/tmp:rw,size=512m', '--shm-size=256m', '--memory=2g', '--pids-limit=256',
                   '-p', f'127.0.0.1:{port()}:8080', IMAGE)
        elif not c['State']['Running']:
            podman('start', CONTAINER)
        return health()
    if c is None:
        raise ToolError('专用容器 feipi-drawio 不存在；请执行 drawio.sh ensure')
    if action == 'status':
        if not c['State']['Running']:
            raise ToolError('专用容器已停止；请执行 drawio.sh up')
        return health()
    return {'status': 'ok', 'output': podman('stop', CONTAINER) if action == 'down' else
            podman('logs', '--tail', '50', CONTAINER)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['engine', 'ensure', 'up', 'status', 'down', 'logs'])
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'engine':
            port()
            engine(args.prepare)
        else:
            print(json.dumps(manage(args.action), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps(getattr(exc, 'details', {'status': 'blocked', 'reason': str(exc)}),
                         ensure_ascii=False), file=sys.stderr)
        sys.exit(75 if getattr(exc, 'details', {}).get('confirmation_required') else 2)
