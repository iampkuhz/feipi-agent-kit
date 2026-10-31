"""适配公共边界：机器绑定、原生 CLI、私有文件及局部互斥。"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MACHINE = Path(os.environ.get('MULTICA_MACHINE_CONFIG', str(Path.home() / '.config/multica-selfhost/machine.json')))
STATE = Path(os.environ.get('MULTICA_OPS_STATE', str(Path.home() / '.local/state/multica/adaptation')))
ACTIVE = {'queued', 'dispatched', 'running', 'waiting_local_directory', 'pending'}


class AdaptError(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_json(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def private_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextlib.contextmanager
def lock(name):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = STATE / (name + '.lock')
    with path.open('a') as stream:
        path.chmod(0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def task_context():
    return any(os.environ.get(k) for k in ['MULTICA_TOKEN', 'MULTICA_TASK_ID', 'MULTICA_AGENT_ID', 'MULTICA_WORKSPACE_ID', 'MULTICA_TASK_CONFIG_ROOT'])


def machine():
    value = read_json(MACHINE)
    if not value or value.get('schema') != 1:
        raise AdaptError('缺少有效机器绑定：' + str(MACHINE))
    return value


def expand(value):
    return str(Path(value).expanduser())


def cli(*args, stdin=None, with_cursor=False):
    command = os.environ.get('MULTICA_TASK_CLI', str(Path.home() / '.local/bin/multica-task'))
    env = dict(os.environ)
    if not task_context() and MACHINE.exists():
        env['MULTICA_PERSONAL_PROFILE'] = machine()['profile']
    result = subprocess.run([command, *map(str, args), '--output', 'json'], input=stdin,
                            text=True, capture_output=True, env=env, timeout=90)
    if result.returncode:
        # CLI 错误可能含请求正文；不把个人配置或服务返回原文转抄进日志。
        raise AdaptError('Multica ' + ' '.join(args[:2]) + ' 失败，退出码 ' + str(result.returncode) + '；请检查认证、权限和原生 CLI 状态。')
    try:
        data = json.loads(result.stdout)
        if with_cursor:
            match = re.search(r'use --before ("(?:[^"\\]|\\.)*")', result.stderr)
            return data, json.loads(match.group(1)) if match else None
        return data
    except ValueError as exc:
        raise AdaptError('Multica 返回非 JSON；不能将其视为成功。') from exc


def agent_runs(agent_id):
    cursor, seen = None, set()
    while True:
        args = ['agent', 'tasks', agent_id, '--limit', '200']
        if cursor:
            args += ['--before', cursor]
        rows, cursor = cli(*args, with_cursor=True)
        yield from rows
        if not cursor:
            return
        if cursor in seen:
            raise AdaptError('运行历史游标重复，不能证明已排空。')
        seen.add(cursor)


def render(text, bindings):
    def replace(match):
        value = bindings
        try:
            for key in match.group(1).split('.'):
                value = value[key]
        except (KeyError, TypeError) as exc:
            raise AdaptError('缺少绑定：' + match.group(1)) from exc
        return str(value)
    return re.sub(r'\$\{([a-zA-Z0-9_.-]+)\}', replace, text)


def resolve_runtime(binding, daemon_id, runtimes):
    matches = [r for r in runtimes if r['id'] == binding['id']]
    if len(matches) != 1:
        raise AdaptError('runtime 身份不存在或不唯一')
    value = matches[0]
    for field, expected in [('daemon_id', daemon_id), ('provider', binding['provider']), ('profile_id', binding.get('profile_id'))]:
        if value.get(field) != expected:
            raise AdaptError('runtime 绑定不匹配：' + field)
    if value.get('status') != 'online':
        raise AdaptError('绑定的 runtime 当前不在线：' + value['name'])
    return value


def file_inventory(root):
    root = Path(root)
    if not root.is_dir():
        return None
    result = {}
    for current, dirs, files in os.walk(root, followlinks=True):
        dirs[:] = sorted(d for d in dirs if d not in {'tests', 'evals', 'tmp', 'node_modules', '__pycache__', '.git', '.venv'} and not d.startswith('.'))
        for name in sorted(files):
            if name.startswith('.') or name.endswith('.pyc'):
                continue
            path = Path(current) / name
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result
