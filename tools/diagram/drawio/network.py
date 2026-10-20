"""准备阶段的慢下载判断、宿主代理验证与人工确认回执。"""
import argparse
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys

HOST_PROXY_PORT = 7890
LOW_SPEED_BYTES = 64 * 1024
LOW_SPEED_SECONDS = 30
ROOT = Path(__file__).resolve().parent


class NetworkError(ValueError):
    def __init__(self, code, reason, **details):
        self.details = {'status': 'blocked', 'code': code, 'reason': reason, **details}
        super().__init__(reason)


def allow_slow():
    value = os.environ.get('AGENT_DRAWIO_ALLOW_SLOW_DOWNLOAD', '0')
    if value not in ('0', '1'):
        raise NetworkError('invalid_network_config', 'AGENT_DRAWIO_ALLOW_SLOW_DOWNLOAD 只能为 0 或 1')
    return value == '1'


def host_proxy():
    return f'http://127.0.0.1:{HOST_PROXY_PORT}'


def probe_proxy(url):
    """TCP 通过后必须再验证代理到实际目标的 HTTP 通路；不改系统设置。"""
    try:
        with socket.create_connection(('127.0.0.1', HOST_PROXY_PORT), timeout=1):
            pass
    except OSError as exc:
        return {'available': False, 'reason': f'宿主代理端口不可连接: {exc}'}
    command = ['curl', '--disable', '--head', '--location', '--silent', '--show-error',
               '--proxy', host_proxy(), '--noproxy', '', '--connect-timeout', '2', '--max-time', '8',
               '-o', os.devnull, '--write-out', '%{http_code}', url]
    try:
        result = subprocess.run(command, text=True, errors='replace', capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'available': False, 'reason': f'宿主代理 HTTP 验证失败: {exc}'}
    code = result.stdout.strip()
    # OCI registry 的 401 表示已连通认证端点；407 表示代理不可直接使用。
    accepted = code.isdigit() and (200 <= int(code) < 400 or code == '401' and url.endswith('/v2/'))
    return {'available': result.returncode == 0 and accepted, 'http_status': code,
            'reason': '代理到目标站点可用' if result.returncode == 0 and accepted else
            f'代理到目标站点不可用（HTTP {code}）: {result.stderr[-1500:].strip()}'}


def confirmation(stage, reason, url, *, probe=None):
    proxy = probe_proxy(url) if probe is None else probe
    retry = shlex.join(['env', 'AGENT_DRAWIO_ALLOW_SLOW_DOWNLOAD=1', 'bash', str(ROOT / 'drawio.sh'), 'ensure'])
    return NetworkError('download_confirmation_required', reason, stage=stage,
                        confirmation_required=True, host_proxy=host_proxy(), proxy_probe=proxy,
                        question='是否检查/启用代理后重试，或确认继续等待慢速下载？',
                        choices=['检查/启用代理后重试', '确认继续慢速下载'],
                        next_steps=['请先取得用户确认，再选择准备网络策略', retry],
                        build_proxy_hint='构建代理须使用虚拟机/容器可达地址；宿主 127.0.0.1 可用不代表 host.containers.internal 可用')


def _download(url, output, proxy=False):
    limit = 600 if allow_slow() else 180
    command = ['curl', '--disable', '--fail', '--location', '--connect-timeout', '10', '--max-time', str(limit)]
    if not allow_slow():
        command += ['--speed-limit', str(LOW_SPEED_BYTES), '--speed-time', str(LOW_SPEED_SECONDS)]
    if proxy:
        command += ['--proxy', host_proxy(), '--noproxy', '']
    command += [url, '-o', str(output)]
    try:
        return subprocess.run(command, text=True, errors='replace', capture_output=True, timeout=limit + 10)
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr or b''
        if isinstance(stderr, bytes): stderr = stderr.decode(errors='replace')
        return subprocess.CompletedProcess(command, 28, '', f'{stderr}\n下载总时限耗尽')
    except OSError as exc:
        raise NetworkError('download_failed', f'无法执行 curl: {exc}', command=command) from exc


def download(url, output):
    output = Path(output)
    result = _download(url, output)
    if result.returncode == 0:
        return
    initial = result.stderr[-2000:].strip()
    output.unlink(missing_ok=True)
    if result.returncode != 28:
        raise NetworkError('download_failed', f'源码下载失败: {initial}', exit_code=result.returncode)
    policy = '达到下载总时限' if allow_slow() else f'触发 {LOW_SPEED_BYTES // 1024} KiB/s、{LOW_SPEED_SECONDS} 秒低速限制或下载总时限'
    print(f'源码下载{policy}；正在检测宿主代理。\n{initial}', file=sys.stderr)
    probe = probe_proxy(url)
    if not probe['available']:
        raise confirmation('source_download', f'下载过慢且宿主代理不可用: {initial}', url, probe=probe)
    print(f'宿主代理 {host_proxy()} 已通过目标站点验证，使用该代理重试一次源码下载。', file=sys.stderr)
    result = _download(url, output, proxy=True)
    if result.returncode:
        output.unlink(missing_ok=True)
        raise confirmation('source_download', f'代理重试失败: {result.stderr[-2000:].strip()}', url, probe=probe)


def build(context, image):
    limit = 1200 if allow_slow() else 600
    command = ['podman', 'build']
    proxy = os.environ.get('AGENT_DRAWIO_BUILD_PROXY')
    if proxy:
        command += ['--build-arg', f'http_proxy={proxy}', '--build-arg', f'https_proxy={proxy}']
    command += ['-t', image, '-f', str(Path(context) / 'Containerfile'), str(context)]
    try:
        # 保留实时构建日志；总耗时不能等同下载速率，所以超时后不自动重建。
        result = subprocess.run(command, timeout=limit)
    except subprocess.TimeoutExpired as exc:
        raise confirmation('image_build', f'镜像构建超过 {limit} 秒，可能是下载慢或安装耗时；需确认下一步，未自动重建',
                           'https://registry-1.docker.io/v2/') from exc
    except OSError as exc:
        raise NetworkError('build_failed', f'无法执行 Podman 构建: {exc}') from exc
    if result.returncode:
        raise NetworkError('build_failed', '镜像构建失败；上方保留原始日志', exit_code=result.returncode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['download', 'build'])
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    try:
        if args.action == 'download': download(args.source, args.destination)
        else: build(args.source, args.destination)
    except NetworkError as exc:
        print(json.dumps(exc.details, ensure_ascii=False), file=sys.stderr)
        sys.exit(75 if exc.details.get('confirmation_required') else 2)
