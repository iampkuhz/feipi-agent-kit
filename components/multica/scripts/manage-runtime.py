#!/usr/bin/env python3
"""One owner for the personal profile's macOS LaunchAgent."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['install', 'start', 'stop', 'status'])
args = parser.parse_args()
home = Path.home()
root = Path(__file__).resolve().parent.parent
label = 'local.multica.personal'
domain = 'gui/' + str(os.getuid())
target = domain + '/' + label
plist = home / 'Library/LaunchAgents' / (label + '.plist')
if args.action == 'install':
    log_dir = home / '.local/state/multica'
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_dir.chmod(0o700)
    log = log_dir / 'supervisor.log'
    log.touch(mode=0o600, exist_ok=True)
    log.chmod(0o600)
    data = {
        'Label': label,
        'ProgramArguments': ['/usr/bin/python3', str(home / '.local/share/multica/ops/scripts/run-supervised.py')],
        'WorkingDirectory': str(home / '.local/share/multica/ops'),
        'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 20,
        'ProcessType': 'Background',
        'EnvironmentVariables': {'PATH': str(home / '.local/bin') + ':/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'},
        'StandardOutPath': str(log), 'StandardErrorPath': str(log),
        'MulticaOpsManaged': True,
    }
    if plist.exists() and not plistlib.loads(plist.read_bytes()).get('MulticaOpsManaged'):
        raise SystemExit('Refusing to overwrite an unmanaged LaunchAgent.')
    if subprocess.run(['launchctl', 'print', target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        raise SystemExit('Stop the managed runtime before reinstalling its definition.')
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(plistlib.dumps(data))
    plist.chmod(0o600)
    subprocess.run(['launchctl', 'bootstrap', domain, str(plist)], check=True)
    print('Installed login startup and crash recovery:', label)
elif args.action == 'start':
    subprocess.run(['launchctl', 'bootstrap', domain, str(plist)], check=True)
elif args.action == 'stop':
    subprocess.run(['launchctl', 'bootout', target], check=True)
    # bootout 返回时进程组可能仍在退出；等注册项消失再允许发布和 bootstrap。
    deadline = time.monotonic() + 45
    while subprocess.run(['launchctl', 'print', target], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL).returncode == 0:
        if time.monotonic() >= deadline:
            raise SystemExit('LaunchAgent is still unloading; do not publish or start another instance yet.')
        time.sleep(0.2)
    print('Stopped managed runtime; Web/API remain available.')
else:
    subprocess.run(['launchctl', 'print', target], check=True)
