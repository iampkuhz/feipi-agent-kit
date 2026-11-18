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
SESSION_BROWSER_LABEL = 'com.feipi.session-browser'


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


def definitions():
    python = next((str(p) for p in [Path('/opt/homebrew/bin/python3'), Path('/usr/local/bin/python3')]
                   if p.is_file()), sys.executable)
    paths = [str(Path(python).parent), str(HOME/'.local/bin'), '/opt/homebrew/bin',
             '/opt/homebrew/sbin', '/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin']
    result = {SERVICE_LABEL: {
        'Label': SERVICE_LABEL,
        'ProgramArguments': [python, str(Path(__file__).resolve()), 'run-services'],
        'WorkingDirectory': str(HOME), 'RunAtLoad': True, 'ProcessType': 'Background',
        'EnvironmentVariables': {'PATH': ':'.join(dict.fromkeys(paths))}, 'Umask': 0o077,
        'StandardOutPath': str(STATE/'logs'/(SERVICE_LABEL+'.log')),
        'StandardErrorPath': str(STATE/'logs'/(SERVICE_LABEL+'.error.log')),
    }}
    launcher = HOME/'.local/bin/session-browser'
    if launcher.is_file() and os.access(launcher, os.X_OK):
        # 原生 serve 常驻前台；独立任务避免 Podman 不可用时阻断会话浏览器。
        # 使用原生默认索引目录，不复制旧缓存，也不经用户 shell 或额外守护进程。
        result[SESSION_BROWSER_LABEL] = {
            'Label': SESSION_BROWSER_LABEL,
            'ProgramArguments': [str(launcher), 'serve', '--host', '127.0.0.1', '--port', '8848'],
            'WorkingDirectory': str(HOME), 'RunAtLoad': True, 'ProcessType': 'Background',
            'EnvironmentVariables': {'PATH': ':'.join(dict.fromkeys(paths))}, 'Umask': 0o077,
            'StandardOutPath': str(STATE/'logs'/(SESSION_BROWSER_LABEL+'.log')),
            'StandardErrorPath': str(STATE/'logs'/(SESSION_BROWSER_LABEL+'.error.log')),
        }
    return result


def install():
    if not (ROOT/'tools/gateway/litellm/scripts/litellm.sh').is_file():
        raise ValueError('缺少已发布服务定义，先 workbench install services。')
    (STATE/'logs').mkdir(mode=0o700, parents=True, exist_ok=True)
    managed = definitions()
    for label, definition in managed.items():
        atomic(HOME/'Library/LaunchAgents'/(label+'.plist'), plistlib.dumps(definition))
    print(str(len(managed))+' 个自启定义已安装；执行 service startup start 加载，或在下次图形登录时加载。')


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


def start():
    managed = definitions()
    for label, expected in managed.items():
        plist = HOME/'Library/LaunchAgents'/(label+'.plist')
        if not plist.is_file() or plistlib.loads(plist.read_bytes()) != expected:
            raise ValueError('自启定义缺少或有漂移，请先 install：'+label)
    domain = 'gui/'+str(os.getuid())
    retire_vault_job(domain)
    for label in managed:
        if subprocess.run(['launchctl', 'print', domain+'/'+label], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=15).returncode == 0:
            run(['launchctl', 'bootout', domain+'/'+label], capture_output=True)
        run(['launchctl', 'bootstrap', domain, HOME/'Library/LaunchAgents'/(label+'.plist')], capture_output=True)
    print('已加载 '+str(len(managed))+' 个用户自启任务；服务实际完成需检查 readiness 和日志，不以加载成功代替验收。')


def services():
    print('开始恢复本地服务：'+datetime.datetime.now().astimezone().isoformat(), flush=True)
    run([sys.executable, ROOT/'tools/runtime/podman.py', 'ensure'])
    failures = []
    for name, relative, endpoint in [
            ('litellm', 'gateway/litellm/scripts/litellm.sh', 'http://localhost:4000/health/readiness'),
            ('searxng', 'search/searxng/scripts/searxng.sh', 'http://127.0.0.1:8873/healthz'),
            ('crawl4ai', 'crawl/crawl4ai/scripts/crawl4ai.sh', 'http://127.0.0.1:11235/health')]:
        try:
            run(['bash', ROOT/'tools'/relative, 'up'])
            wait_service(name, endpoint)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append(name)
            print(name+' 启动/就绪失败：'+str(error)+'；继续准备其他独立服务。', flush=True)
    if failures:
        raise ValueError('部分服务未就绪：'+', '.join(failures)+'；保留运行现场与日志，未停止其他服务。')
    print('三个本地服务 readiness 通过；业务请求、图表服务和其他组件仍须各自验收。', flush=True)


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
        for label, expected in definitions().items():
            path = HOME/'Library/LaunchAgents'/(label+'.plist')
            if not path.is_file() or plistlib.loads(path.read_bytes()) != expected:
                raise ValueError('自启文件缺失或漂移：'+label)
        print('自启文件检查通过；完整重启与真实业务另行验收。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
