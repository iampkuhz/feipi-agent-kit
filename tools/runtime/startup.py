#!/usr/bin/env python3
"""以已发布运行副本恢复 Env Vault 快照和本地服务，不加载用户 shell。"""
import argparse
import datetime
import fcntl
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
LABELS = {'com.local.envvault': 'snapshot-env', 'com.feipi.podman-services': 'run-services'}
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


def snapshot_env():
    source = (HOME/'.env').resolve(strict=True)
    vault = HOME/'.local/env-vault'
    vault.mkdir(mode=0o700, parents=True, exist_ok=True)
    vault.chmod(0o700)
    with (vault/'.snapshot.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        before = source.stat()
        data = source.read_bytes()
        after = source.stat()
        if (before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_ino, after.st_mtime_ns, after.st_size):
            raise ValueError('env 在读取时发生变化；本次未记录，后续调度会重试。')
        # 保留既有 vault 的本地 Git 历史；仅提交 env，不触碰其他暂存内容、不执行 hooks/上传。
        git = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'user.name=Env Vault',
               '-c', 'user.email=env-vault@localhost', '-C', vault]
        # 当前 shell 可能来自业务 Git 操作；不继承其 index/worktree/config 重定向。
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        def git_run(*args, check=True):
            return subprocess.run(list(map(str, [*git, *args])), env=environment, check=check,
                                  capture_output=True, text=True, timeout=30)
        if not (vault/'.git').exists():
            git_run('init', '-q')
        if (vault/'.git').is_symlink():
            raise ValueError('vault .git 是外部链接，未写入快照。')
        actual = git_run('rev-parse', '--show-toplevel').stdout.strip()
        if Path(actual).resolve() != vault.resolve():
            raise ValueError('env vault 不在独立 Git 仓库中，未提交。')
        target = vault/'env'
        if target.is_symlink():
            raise ValueError('vault env 是链接，拒绝覆盖。')
        if not target.exists() or target.read_bytes() != data:
            atomic(target, data)
        target.chmod(0o600)
        git_run('add', '--', 'env')
        changed = git_run('diff', '--cached', '--quiet', '--', 'env', check=False)
        if changed.returncode not in (0, 1):
            raise ValueError('env Git 差异检查失败；未创建提交。')
        if changed.returncode:
            git_run('commit', '--no-gpg-sign', '--quiet', '--only', '-m',
                    'auto snapshot '+datetime.datetime.now().astimezone().isoformat(), '--', 'env')
        print('Env Vault 本地快照完成；未输出配置值或上传。', flush=True)


def definitions():
    python = next((str(p) for p in [Path('/opt/homebrew/bin/python3'), Path('/usr/local/bin/python3')]
                   if p.is_file()), sys.executable)
    paths = [str(Path(python).parent), str(HOME/'.local/bin'), '/opt/homebrew/bin',
             '/opt/homebrew/sbin', '/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin']
    result = {}
    for label, action in LABELS.items():
        definition = {'Label': label, 'ProgramArguments': [python, str(Path(__file__).resolve()), action],
                      'WorkingDirectory': str(HOME), 'RunAtLoad': True, 'ProcessType': 'Background',
                      'EnvironmentVariables': {'PATH': ':'.join(dict.fromkeys(paths))}, 'Umask': 0o077,
                      'StandardOutPath': str(STATE/'logs'/(label+'.log')),
                      'StandardErrorPath': str(STATE/'logs'/(label+'.error.log'))}
        if action == 'snapshot-env':
            # 原子替换文件也可能换 inode；原生定时调度兜底，不再依赖 fswatch/xargs 常驻管道。
            definition.update(WatchPaths=[str((HOME/'.env').resolve())], StartInterval=300,
                              ThrottleInterval=10)
        result[label] = definition
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
    if not (HOME/'.env').is_file():
        raise ValueError('先恢复 ~/.env 真源，再一次安装 Env Vault 与服务自启。')
    if not (ROOT/'tools/gateway/litellm/scripts/litellm.sh').is_file():
        raise ValueError('缺少已发布服务定义，先 workbench apply services。')
    (STATE/'logs').mkdir(mode=0o700, parents=True, exist_ok=True)
    managed = definitions()
    for label, definition in managed.items():
        atomic(HOME/'Library/LaunchAgents'/(label+'.plist'), plistlib.dumps(definition))
    snapshot_env()
    print(str(len(managed))+' 个自启定义已安装；执行 service startup start 加载，或在下次图形登录时加载。')


def start():
    managed = definitions()
    for label, expected in managed.items():
        plist = HOME/'Library/LaunchAgents'/(label+'.plist')
        if not plist.is_file() or plistlib.loads(plist.read_bytes()) != expected:
            raise ValueError('自启定义缺少或有漂移，请先 install：'+label)
    domain = 'gui/'+str(os.getuid())
    for label in managed:
        if subprocess.run(['launchctl', 'print', domain+'/'+label], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=15).returncode == 0:
            run(['launchctl', 'bootout', domain+'/'+label], capture_output=True)
        run(['launchctl', 'bootstrap', domain, HOME/'Library/LaunchAgents'/(label+'.plist')], capture_output=True)
    print('已加载 '+str(len(managed))+' 个用户自启任务；服务实际完成需检查 readiness 和日志，不以加载成功代替验收。')


def services():
    print('开始恢复本地服务：'+datetime.datetime.now().astimezone().isoformat(), flush=True)
    run([sys.executable, ROOT/'tools/runtime/podman.py', 'ensure'])
    env = dict(os.environ)
    crawl = HOME/'.config/feipi-workbench/private/services/crawl4ai.env'
    if crawl.is_file():
        env['CRAWL4AI_ENV_FILE'] = str(crawl)
    failures = []
    for name, relative, endpoint in [
            ('litellm', 'gateway/litellm/scripts/litellm.sh', 'http://localhost:4000/health/readiness'),
            ('searxng', 'search/searxng/scripts/searxng.sh', 'http://127.0.0.1:8873/healthz'),
            ('crawl4ai', 'crawl/crawl4ai/scripts/crawl4ai.sh', 'http://127.0.0.1:11235/health')]:
        try:
            run(['bash', ROOT/'tools'/relative, 'up'], env=env)
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
    parser.add_argument('action', choices=['install', 'start', 'check', 'snapshot-env', 'run-services'])
    action = parser.parse_args().action
    if action == 'install':
        install()
    elif action == 'start':
        start()
    elif action == 'snapshot-env':
        snapshot_env()
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
