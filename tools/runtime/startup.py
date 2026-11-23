#!/usr/bin/env python3
"""以已发布运行副本启动本地服务，不加载用户 shell。"""
import argparse
import datetime
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
from service_health import wait_service

HOME = Path.home()
ROOT = Path(__file__).resolve().parents[2]
STATE = HOME/'.local/state/feipi-workbench'
SERVICE_LABEL = 'com.feipi.podman-services'


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, timeout=1800, **kwargs)


def atomic(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.'+path.name+'-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def definition():
    python = next((str(p) for p in [Path('/opt/homebrew/bin/python3'), Path('/usr/local/bin/python3')]
                   if p.is_file()), sys.executable)
    paths = [str(Path(python).parent), str(HOME/'.local/bin'), '/opt/homebrew/bin',
             '/opt/homebrew/sbin', '/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin']
    return {
        'Label': SERVICE_LABEL,
        'ProgramArguments': [python, str(Path(__file__).resolve()), 'run-services'],
        'WorkingDirectory': str(HOME), 'RunAtLoad': True, 'ProcessType': 'Background',
        'EnvironmentVariables': {'PATH': ':'.join(dict.fromkeys(paths))}, 'Umask': 0o077,
        'StandardOutPath': str(STATE/'logs'/(SERVICE_LABEL+'.log')),
        'StandardErrorPath': str(STATE/'logs'/(SERVICE_LABEL+'.error.log')),
    }


def install():
    if not (ROOT/'tools/gateway/litellm/scripts/litellm.sh').is_file():
        raise ValueError('缺少已发布服务定义，先 workbench install services。')
    (STATE/'logs').mkdir(mode=0o700, parents=True, exist_ok=True)
    plist = HOME/'Library/LaunchAgents'/(SERVICE_LABEL+'.plist')
    atomic(plist, plistlib.dumps(definition()))
    print('Podman 服务自启定义已安装；执行 service startup start 加载，或在下次图形登录时加载。')


def retire_vault_job(domain):
    label = 'com.local.envvault'
    plist = HOME/'Library/LaunchAgents'/(label+'.plist')
    if not plist.is_file() or plist.is_symlink():
        return
    try:
        definition = plistlib.loads(plist.read_bytes())
    except (plistlib.InvalidFileException, ValueError):
        return
    # 同名的自定义任务由用户管理。这里只清理本运行副本过去生成的任务。
    if not isinstance(definition, dict) or definition.get('Label') != label:
        return
    command = definition.get('ProgramArguments')
    if not isinstance(command, list) or command[1:] != [str(Path(__file__).resolve()), 'snapshot-env']:
        return
    if subprocess.run(['launchctl', 'print', domain+'/'+label], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL, timeout=15).returncode == 0:
        run(['launchctl', 'bootout', domain+'/'+label], capture_output=True)
    plist.unlink()


def checked_definition():
    plist = HOME/'Library/LaunchAgents'/(SERVICE_LABEL+'.plist')
    if not plist.is_file() or plistlib.loads(plist.read_bytes()) != definition():
        raise ValueError(f'自启任务 {SERVICE_LABEL} 的定义缺失或漂移，请先运行 workbench service startup install。')
    return plist


def start():
    plist = checked_definition()
    domain = 'gui/'+str(os.getuid())
    retire_vault_job(domain)
    target = domain+'/'+SERVICE_LABEL
    if subprocess.run(['launchctl', 'print', target], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL, timeout=15).returncode == 0:
        run(['launchctl', 'bootout', target], capture_output=True)
    run(['launchctl', 'bootstrap', domain, plist], capture_output=True)
    print('已加载 Podman 服务自启任务；服务实际完成需检查 readiness 和日志。')


def services():
    print('开始恢复本地服务：'+datetime.datetime.now().astimezone().isoformat(), flush=True)
    run([sys.executable, ROOT/'tools/runtime/podman.py', 'ensure'])
    failures = []
    for name, relative, endpoint in [
            ('litellm', 'gateway/litellm/scripts/litellm.sh', 'http://localhost:4000/health/readiness'),
            ('searxng', 'search/searxng/scripts/searxng.sh', 'http://127.0.0.1:8873/healthz'),
            ('fastmcp', 'gateway/fastmcp/scripts/fastmcp.sh', 'http://127.0.0.1:18080/healthz'),
            ('crawl4ai', 'crawl/crawl4ai/scripts/crawl4ai.sh', 'http://127.0.0.1:11235/health'),
            ('diagrams', 'diagram/diagrams.sh', None)]:
        try:
            run(['bash', ROOT/'tools'/relative, 'up'])
            # 图表入口已依次确认三个 HTTP 渲染器可用。
            if endpoint:
                wait_service(name, endpoint)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append(name)
            print(name+' 启动/就绪失败：'+str(error)+'；继续准备其他独立服务。', flush=True)
    if failures:
        raise ValueError('部分服务未就绪：'+', '.join(failures)+'；保留运行现场与日志，未停止其他服务。')
    print('本地自启服务的就绪检查通过。', flush=True)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'start', 'check', 'run-services'])
    action = parser.parse_args().action
    if action == 'install':
        install()
    elif action == 'start':
        start()
    elif action == 'run-services':
        services()
    else:
        checked_definition()
        print('自启文件检查通过；完整重启与真实业务另行验收。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
