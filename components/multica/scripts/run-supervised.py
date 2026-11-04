#!/usr/bin/env python3
"""持续监督本机既有服务与唯一 daemon；不创建、升级或重启无关容器。"""
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import urllib.request

from adaptation import expand, machine

CHECK_SECONDS = 60
RETRY_SECONDS = 60
SERVICES = ('postgres', 'backend', 'frontend')
STOPPED = {'created', 'exited', 'stopped'}


class Unavailable(RuntimeError):
    pass


def log(message):
    print(datetime.now().astimezone().isoformat(timespec='seconds'),
          'supervisor:', message, flush=True)


def command(args, timeout=15):
    # 错误正文可能含环境或服务响应，不把它们转抄进守护日志。
    # VM/网络代理属于共享容器引擎，不能继承本 LaunchAgent 的进程组；
    # 否则 bootout 或 supervisor 崩溃时，launchd 会把它们一起回收。
    detached_engine = args[:3] == ['podman', 'machine', 'start']
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                            start_new_session=detached_engine)
    if result.returncode:
        raise Unavailable(Path(args[0]).name + ' ' + args[1] +
                          ' failed (exit ' + str(result.returncode) + ')')
    return result.stdout


def json_rows(text):
    if not text.strip():
        return []
    if text.lstrip().startswith('['):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class Supervisor:
    def __init__(self, binding, root):
        if binding.get('role') != 'primary':
            raise Unavailable('This machine is a temporary client; disable its managed LaunchAgent.')
        self.binding = binding
        self.service = str(root / 'bin/multica-service')
        self.child = None
        self.stopping = threading.Event()
        self.last_problem = None
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request_stop(self, *_):
        self.stopping.set()

    def ready(self, label, url):
        try:
            with self.http.open(url, timeout=3) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        raise Unavailable(label + ' readiness unavailable')

    def ensure_services(self):
        startup = self.binding.get('startup', {})
        name = startup.get('podman_machine')
        if name:
            rows = json_rows(command(['podman', 'machine', 'list', '--format', 'json']))
            selected = [row for row in rows if row['Name'] == name]
            if len(selected) != 1:
                raise Unavailable('Configured Podman machine missing; explicit setup required')
            if not selected[0]['Running']:
                # Starting 标志可能在中断后残留；互斥与状态校验交给 Podman 原生命令。
                log('Podman machine stopped; starting ' + name)
                command(['podman', 'machine', 'start', name], timeout=120)
        if self.stopping.is_set():
            return

        # start 复用原容器，不隐式应用配置或拉镜像。
        rows = json_rows(command([self.service, 'ps', '--all', '--format', 'json']))
        selected = {}
        for name in SERVICES:
            matches = [row for row in rows if row.get('Service') == name]
            if len(matches) != 1:
                raise Unavailable('Expected one existing Multica container for ' + name)
            selected[name] = matches[0]
        stopped = [name for name in SERVICES if selected[name]['State'] in STOPPED]
        if stopped:
            log('Multica containers stopped; starting ' + ', '.join(stopped))
            command([self.service, 'start', '--wait', '--wait-timeout', '60', *stopped], timeout=75)
            rows = json_rows(command([self.service, 'ps', '--all', '--format', 'json']))
            selected = {row['Service']: row for row in rows if row.get('Service') in SERVICES}
        for name in SERVICES:
            row = selected.get(name, {})
            if row.get('State') != 'running':
                raise Unavailable('Multica ' + name + ' is not running')
            if row.get('Health') not in (None, '', 'healthy'):
                raise Unavailable('Multica ' + name + ' is not healthy')

        ports = [p for p in selected['frontend'].get('Publishers') or []
                 if p.get('TargetPort') == 3000 and p.get('Protocol') == 'tcp'
                 and p.get('URL') in ('127.0.0.1', '::1')]
        if not ports:
            raise Unavailable('Multica frontend loopback port is missing')
        port = ports[0]
        host = '[' + port['URL'] + ']' if ':' in port['URL'] else port['URL']
        self.ready('Multica API', self.binding['server_url'].rstrip('/') + '/readyz')
        self.ready('Multica Web', 'http://' + host + ':' + str(port['PublishedPort']) + '/')

    def tick(self):
        if self.child is not None and self.child.poll() is not None:
            log('Daemon exited (pid ' + str(self.child.pid) + ', exit ' +
                str(self.child.returncode) + '); restarting after readiness')
            self.child = None
        self.ensure_services()
        if self.stopping.is_set():
            return
        if self.last_problem is not None:
            log('Services recovered; readiness passed')
            self.last_problem = None
        if self.child is None:
            binary = expand(self.binding['commands']['multica'])
            # 保留常驻父进程，同一时间只持有一个子进程。保持 launchd 进程组，
            # supervisor 被 SIGKILL 时由 launchd 清理旧子进程。
            self.child = subprocess.Popen(
                [binary, '--profile', self.binding['profile'], 'daemon', 'start', '--foreground'])
            log('Started daemon pid ' + str(self.child.pid) + '; monitoring every ' + str(CHECK_SECONDS) + ' seconds')

    def stop_child(self):
        if self.child is None:
            return
        if self.child.poll() is None:
            log('Stopping managed daemon pid ' + str(self.child.pid))
            try:
                self.child.terminate()
            except ProcessLookupError:
                pass
            try:
                self.child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=5)
        self.child = None

    def run(self):
        log('Continuous supervision started')
        try:
            while not self.stopping.is_set():
                delay = CHECK_SECONDS
                try:
                    self.tick()
                except (Unavailable, OSError, subprocess.SubprocessError, ValueError) as exc:
                    problem = str(exc) if isinstance(exc, Unavailable) else type(exc).__name__
                    if problem != self.last_problem:
                        log(problem + '; retrying in ' + str(RETRY_SECONDS) + ' seconds')
                    self.last_problem = problem
                    delay = RETRY_SECONDS
                self.stopping.wait(delay)
        finally:
            self.stop_child()
            log('Supervision stopped; containers left unchanged')


def main():
    binding = machine()
    directories = list(dict.fromkeys(str(Path(expand(p)).parent)
                                    for p in binding.get('commands', {}).values()))
    os.environ['PATH'] = os.pathsep.join(directories + [os.environ.get('PATH', '')])
    state = Path.home() / '.local/state/multica'
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (state / 'supervisor.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another managed supervisor is already running')
        supervisor = Supervisor(binding, Path(__file__).resolve().parent.parent)
        signal.signal(signal.SIGTERM, supervisor.request_stop)
        signal.signal(signal.SIGINT, supervisor.request_stop)
        supervisor.run()


if __name__ == '__main__':
    main()
