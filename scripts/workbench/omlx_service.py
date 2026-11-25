#!/usr/bin/env python3
"""把仓库内 oMLX 服务配置合并到当前数据目录，并管理 Homebrew 服务。"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT/'components/mac/config/omlx-service.json'
FORMULA = 'jundot/omlx/omlx'
APP_BASE_PATH = Path.home()/'Library/Application Support/oMLX/base-path'


def managed_settings():
    data = json.loads(CONFIG.read_text(encoding='utf-8'))
    server = data.get('server')
    scheduler = data.get('scheduler', {})
    if not isinstance(server, dict) or not isinstance(scheduler, dict):
        raise ValueError('oMLX 配置必须包含 server 对象，可选 scheduler 对象。')
    host = server.get('host', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('工作台只允许本机回环监听，避免无意暴露未认证的推理接口。')
    port = server.get('port', 8037)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('oMLX server.port 必须是 1 到 65535 的整数。')
    level = server.get('log_level', 'info')
    if level not in ('debug', 'info', 'warning', 'error', 'critical'):
        raise ValueError('oMLX server.log_level 无效。')
    if set(server)-{'host', 'port', 'log_level'}:
        raise ValueError('oMLX server 只允许管理 host、port、log_level。')
    concurrent = scheduler.get('max_concurrent_requests', 8)
    if isinstance(concurrent, bool) or not isinstance(concurrent, int) or not 1 <= concurrent <= 256:
        raise ValueError('oMLX scheduler.max_concurrent_requests 必须是 1 到 256 的整数。')
    if set(scheduler)-{'max_concurrent_requests'}:
        raise ValueError('oMLX scheduler 只允许管理 max_concurrent_requests。')
    return data


def settings_path():
    """按 oMLX 的 base-path 环境变量、应用标记、默认目录顺序定位配置。"""
    configured = os.environ.get('OMLX_BASE_PATH')
    if configured:
        base = Path(configured).expanduser()
    elif APP_BASE_PATH.is_file():
        configured = APP_BASE_PATH.read_text(encoding='utf-8').strip()
        if not configured:
            raise ValueError('oMLX base-path 文件为空：'+str(APP_BASE_PATH))
        base = Path(configured).expanduser()
    else:
        base = Path.home()/'.omlx'
    return base.resolve()/'settings.json'


def apply_config(data):
    path = settings_path()
    if path.is_symlink():
        raise ValueError('拒绝覆盖符号链接形式的 oMLX 设置文件：'+str(path))
    current = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError('无法安全读取现有 oMLX 设置：'+str(path)) from exc
        if not isinstance(current, dict):
            raise ValueError('oMLX 设置文件顶层必须是 JSON 对象：'+str(path))
    # 仅覆盖仓库明确管理的键；保留模型、缓存、API key、MCP、UI 等本机设置。
    for section, values in data.items():
        existing = current.get(section, {})
        if not isinstance(existing, dict):
            existing = {}
        current[section] = {**existing, **values}
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp_name = tempfile.mkstemp(prefix='settings.', suffix='.json', dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(current, output, ensure_ascii=False, indent=2)
            output.write('\n')
        temp.chmod(0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def brew_command():
    found = shutil.which('brew')
    if found:
        return found
    for candidate in ('/opt/homebrew/bin/brew', '/usr/local/bin/brew'):
        if Path(candidate).is_file():
            return candidate
    raise ValueError('找不到 Homebrew；请先 workbench install mac。')


def brew(*args, capture=False):
    result = subprocess.run([brew_command(), *args], check=True, text=True,
                            capture_output=capture)
    return result.stdout if capture else ''


def service_info():
    return brew('services', 'info', FORMULA, capture=True)


def service_pid(info):
    match = re.search(r'^PID:\s*(\d+)\s*$', info, re.MULTILINE)
    return match.group(1) if match else None


def listener(port, pid=None):
    command = ['lsof', '-nP']
    if pid:
        command += ['-a', '-p', pid]
    command += ['-iTCP:'+str(port), '-sTCP:LISTEN']
    result = subprocess.run(command, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ''


def api_status(host, port):
    if host == '::1':
        url = f'http://[::1]:{port}/v1/models'
    else:
        url = f'http://127.0.0.1:{port}/v1/models'
    try:
        with urlopen(url, timeout=3) as response:
            return response.status
    except HTTPError as exc:
        # 401 表示服务已响应，只是请求缺少本地 API key。
        return exc.code if exc.code < 500 else None
    except (OSError, URLError, TimeoutError):
        return None


def ready(data, wait=False):
    server = data['server']
    port = server['port']
    info = ''
    active_listener = ''
    status = None
    attempts = 30 if wait else 1
    for _ in range(attempts):
        info = service_info()
        active_listener = listener(port, service_pid(info))
        status = api_status(server['host'], port) if active_listener else None
        if active_listener and status is not None:
            break
        if wait:
            time.sleep(1)
    print(info.strip())
    print('配置文件：'+str(settings_path()))
    print('配置端口：'+str(port))
    if active_listener:
        print(active_listener.rstrip())
    if status is not None:
        print(f'oMLX API：可访问（HTTP {status}）')
        return True
    print('oMLX 未在配置端口监听或 API 尚未就绪。请查看 workbench service omlx logs。', file=sys.stderr)
    return False


def main(args):
    if len(args) != 1 or args[0] not in ('up', 'down', 'restart', 'status', 'logs'):
        raise ValueError('用法：workbench service omlx up|down|restart|status|logs')
    action = args[0]
    if action == 'logs':
        prefix = Path(brew('--prefix', capture=True).strip())
        log = prefix/'var/log/omlx.log'
        if not log.is_file():
            raise ValueError('未找到 Homebrew 服务日志：'+str(log))
        return subprocess.run(['tail', '-n', '50', str(log)]).returncode
    if action == 'status':
        return 0 if ready(managed_settings()) else 1
    data = managed_settings()
    if action in ('up', 'restart'):
        path = apply_config(data)
        print('已应用工作台 oMLX 配置：'+str(path))
    brew('services', {'up': 'start', 'down': 'stop', 'restart': 'restart'}[action], FORMULA)
    if action in ('up', 'restart'):
        return 0 if ready(data, wait=True) else 1
    print(service_info().strip())
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print('未完成：'+str(exc), file=sys.stderr)
        sys.exit(1)
