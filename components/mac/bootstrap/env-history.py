#!/usr/bin/env python3
"""将 ~/.env 的稳定版本记录在仅供本机访问的裸 Git 仓库。"""
import fcntl
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile

LABEL = 'com.feipi.env-history'


def read_env(source):
    def fingerprint(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns

    try:
        with os.fdopen(os.open(source, os.O_RDONLY | os.O_NONBLOCK), 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                return None
            data = stream.read()
            after = os.fstat(stream.fileno())
        if fingerprint(before) == fingerprint(after) == fingerprint(source.stat()):
            return data
    except FileNotFoundError:
        pass
    return None  # 文件不存在或仍在写入，等待下次调度。


def snapshot(home):
    source = home/'.env'
    if not source.is_file():
        return
    repo = home/'.local/state/feipi-workbench/env-history.git'
    if repo.resolve() != repo:
        raise ValueError('环境历史路径经过符号链接，未写入。')
    repo.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = repo.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('环境历史仓库必须由当前用户独占。')
    with os.fdopen(os.open(repo/'snapshot.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'rb') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        data = read_env(source)
        if data is None:
            return
        binary = shutil.which('git', path='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin')
        if not binary:
            raise ValueError('缺少 Git，无法记录环境历史。')
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        command = [binary, '--git-dir='+str(repo), '-c', 'core.hooksPath='+os.devnull,
                   '-c', 'protocol.allow=never', '-c', 'commit.gpgSign=false',
                   '-c', 'user.name=Local Env History', '-c', 'user.email=env-history@localhost']

        def git(*args, data=None, allowed=(0,)):
            result = subprocess.run([*command, *args], input=data, env=env, capture_output=True, timeout=30)
            if result.returncode not in allowed:
                raise ValueError('环境历史 Git 操作失败：'+args[0])
            return os.fsdecode(result.stdout.strip())

        if not (repo/'HEAD').exists():
            git('init', '--bare', '--template=', '--initial-branch=main')
            git('config', '--local', 'protocol.allow', 'never')
        previous = git('rev-parse', '--verify', '--quiet', 'refs/heads/main', allowed=(0, 1))
        blob = git('hash-object', '-w', '--stdin', data=data)
        tree = git('mktree', data=f'100644 blob {blob}\t.env\n'.encode('ascii'))
        if previous and tree == git('rev-parse', f'{previous}^{{tree}}'):
            return
        parents = ('-p', previous) if previous else ()
        commit = git('commit-tree', tree, *parents, '-m', 'Record local .env')
        git('update-ref', 'refs/heads/main', commit, previous or '0'*len(commit))


def install(home, program):
    snapshot(home)
    plist = home/'Library/LaunchAgents'/(LABEL+'.plist')
    plist.parent.mkdir(parents=True, exist_ok=True)
    python = next((str(path) for path in (Path('/opt/homebrew/bin/python3'), Path('/usr/local/bin/python3'))
                   if path.is_file()), sys.executable)
    source = home/'.env'
    definition = plistlib.dumps({
        'Label': LABEL,
        'ProgramArguments': [python, str(program)],
        'RunAtLoad': True,
        'WatchPaths': list(dict.fromkeys([str(source), str(source.resolve())])),
        'StartInterval': 60,
        'ProcessType': 'Background',
        'Umask': 0o077,
    })
    if plist.is_symlink():
        raise ValueError('环境历史的自启文件是符号链接，未替换。')
    changed = not plist.is_file() or plist.read_bytes() != definition
    if changed:
        with tempfile.TemporaryDirectory(prefix='.env-history-', dir=plist.parent) as directory:
            temporary = Path(directory)/plist.name
            temporary.write_bytes(definition)
            os.replace(temporary, plist)

    def launch(*args, check=True):
        return subprocess.run(['/bin/launchctl', *map(str, args)], check=check, capture_output=True, timeout=30)

    domain = 'gui/'+str(os.getuid())
    if launch('print', domain, check=False).returncode:
        print('.env 本地历史已安装，将在下次图形登录时启用。')
        return
    job = domain+'/'+LABEL
    loaded = launch('print', job, check=False).returncode == 0
    if loaded and changed:
        launch('bootout', job)
    if changed or not loaded:
        launch('bootstrap', domain, plist)
    print('.env 本地历史已启用。')


def main():
    os.umask(0o077)
    home = Path.home().resolve()
    if sys.argv[1:] == ['install'] and sys.platform == 'darwin':
        install(home, Path(__file__).resolve())
    elif len(sys.argv) == 1:
        snapshot(home)
    else:
        raise ValueError('环境历史自启由 macOS 工作台安装。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
