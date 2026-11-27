"""发布 Codex 命名档位，生成项目绑定及一次性会话简报。"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from urllib.parse import urlsplit


PROFILE_FILES = ('feipi-develop.config.toml', 'feipi-review.config.toml')
MODES = {'develop': 'feipi-develop', 'review': 'feipi-review', 'verify': 'feipi-develop'}
ENTRY_LABELS = {
    'instructions': '根规则',
    'workflow': '工程入口',
    'verification': '验证入口',
    'evidence': '证据接收',
}
BINDING = Path('tmp/feipi-agent-kit/project.json')
OWNER = 'feipi-workbench'


def profile_mappings(root, codex_home):
    base = root/'components/codex/profiles'
    return {name: (base/name, codex_home/name) for name in PROFILE_FILES}


@contextmanager
def installation_lock(directory):
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    with os.fdopen(os.open(directory/'.install.lock',
                           os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def read_regular(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f'配置目标须为普通文件：{path}')
    if path.is_file():
        return path.read_bytes()
    return None


def write_atomic(path, content):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.')
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as staged:
            staged.write(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def profile_receipt(path):
    raw = read_regular(path)
    record = json.loads(raw) if raw is not None else {}
    if not isinstance(record, dict) or not isinstance(record.get('files', {}), dict):
        raise ValueError(f'安装回执格式无效：{path}')
    return record


def profile_updates(pairs, receipt, codex_home):
    owned = (receipt.get('files', {})
             if receipt.get('codex_home') == str(codex_home) else {})
    updates = {}
    for name, (source, target) in pairs.items():
        wanted = source.read_bytes()
        installed = read_regular(target)
        if installed == wanted:
            continue
        if installed is not None and hashlib.sha256(installed).hexdigest() != owned.get(name):
            raise ValueError(f'发现个人配置或本机修改，保留原文件：{target}')
        updates[target] = wanted
    return updates


def git(project, *args):
    return subprocess.run(['git', '-C', str(project), *args], check=False,
                          text=True, capture_output=True)


def project_identity(path):
    result = git(path, 'rev-parse', '--show-toplevel')
    if result.returncode:
        raise ValueError('请从 Git 项目内运行，或传入项目目录')
    project = Path(result.stdout.strip()).resolve()
    origin = git(project, 'config', '--local', '--get', 'remote.origin.url')
    if origin.returncode:
        raise ValueError('项目缺少可匹配的 origin')
    remote = origin.stdout.strip()
    if '://' in remote:
        parts = urlsplit(remote)
        host, remote_path = parts.hostname, parts.path
    else:
        match = re.fullmatch(r'(?:[^@:\s]+@)?([^:\s]+):([^\s]+)', remote)
        host, remote_path = match.groups() if match else (None, '')
    identity = (str(host)+'/'+remote_path.strip('/').removesuffix('.git')).lower()
    return project, identity


def binding_document(source, path):
    project, identity = project_identity(path)
    templates = source/'templates/agent'
    catalog = json.loads((templates/'projects.json').read_text())
    if identity not in catalog:
        raise ValueError('该项目尚未在 templates/agent/projects.json 注册')
    entries = catalog[identity]
    for key in ENTRY_LABELS:
        relative = Path(entries[key])
        candidate = project/relative
        if relative.is_absolute() or not candidate.resolve().is_relative_to(project) or not candidate.is_file():
            raise ValueError(f'项目入口缺失或越界：{key}')
    target = project/BINDING
    if any((project/relative).is_symlink() for relative in BINDING.parents):
        raise ValueError(f'项目绑定目录不可为符号链接：{target.parent}')
    ignored = git(project, 'check-ignore', '-q', '--', str(BINDING))
    if ignored.returncode != 0:
        raise ValueError(f'项目绑定须位于 Git 忽略目录：{BINDING}')
    session_sources = {mode: (templates/(mode+'.md')).read_text() for mode in MODES}
    profiles = {name: (source/'components/codex/profiles'/name).read_text() for name in PROFILE_FILES}
    bundle = {'entries': entries, 'sessions': session_sources, 'profiles': profiles, 'modes': MODES}
    version = hashlib.sha256(json.dumps(bundle, sort_keys=True).encode()).hexdigest()
    return project, target, {'schema': 1, 'owner': OWNER, 'repository': identity,
                             'bundle': version, 'entries': entries}


def encode_binding(document):
    return (json.dumps(document, ensure_ascii=False, indent=2)+'\n').encode()


def initialize_project(source, path):
    project, target, desired = binding_document(source, path)
    with installation_lock(target.parent):
        existing = read_regular(target)
        updated = encode_binding(desired)
        if existing == updated:
            print(f'项目配置已是当前版本：{project}')
            return
        if existing is not None:
            record = json.loads(existing)
            if (not isinstance(record, dict) or record.get('owner') != OWNER
                    or record.get('repository') != desired['repository'] or record.get('schema') != 1):
                raise ValueError(f'现有配置归属或版本不同，保留原文件：{target}')
        write_atomic(target, updated)
    print(f'项目配置已初始化：{target}')


def current_project(source, path):
    project, target, desired = binding_document(source, path)
    if read_regular(target) != encode_binding(desired):
        raise ValueError(f'项目配置缺失或过期；运行 workbench project init {shlex.quote(str(project))}')
    return project, desired


def session_brief(source, path, mode):
    project, config = current_project(source, path)
    instructions = (source/'templates/agent'/(mode+'.md')).read_text().strip()
    profile = MODES[mode]
    if mode == 'review':
        options = ['--sandbox', 'read-only', '--ask-for-approval', 'never']
    else:
        options = ['--sandbox', 'workspace-write', '--ask-for-approval', 'on-request', '-c',
                   'approvals_reviewer="user"', '-c', 'sandbox_workspace_write.network_access=false']
    command = shlex.join(['codex', '--profile', profile, '-C', str(project), *options])
    print(f'# Feipi 会话简报 · {mode}\n')
    print(f'目标 checkout：{project}')
    for key, label in ENTRY_LABELS.items():
        print(f'- {label}：`{config["entries"][key]}`')
    print(f'\n{instructions}\n')
    print('从本轮用户输入获取任务、候选与权限。本简报不代替项目规则或验收身份。')
    print(f'\nCodex CLI 启动建议\n\n```bash\n{command}\n```')
