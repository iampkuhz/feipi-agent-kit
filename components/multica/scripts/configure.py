#!/usr/bin/env python3
"""配置 Multica 的本机 CLI，或从既有 env vault 投影服务密钥。"""
import argparse
import base64
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import tempfile
from container_engine import public_config

SECRET_MAP = {
    'JWT_SECRET': 'MULTICA_SELFHOST_JWT_SECRET',
    'POSTGRES_PASSWORD': 'MULTICA_SELFHOST_POSTGRES_PASSWORD',
    'MULTICA_VCS_SECRET_KEY': 'MULTICA_VCS_SECRET_KEY',
}


def personal_settings(home):
    binding = json.loads((home/'.config/multica-selfhost/machine.json').read_text())
    keys = ('profile', 'server_url', 'app_url', 'workspace_id', 'device_name', 'workspaces_root')
    if (not isinstance(binding, dict) or binding.get('schema') != 1 or binding.get('role') != 'primary'
            or any(not isinstance(binding.get(key), str) or not binding[key] for key in keys)):
        raise ValueError('缺少有效主机绑定，先恢复 Multica 本机配置。')
    profile = binding['profile']
    if profile in ('.', '..') or Path(profile).name != profile:
        raise ValueError('Multica profile 名称无效。')
    workspaces = Path(binding['workspaces_root']).expanduser()
    if not workspaces.is_absolute():
        raise ValueError('workspaces_root 必须是绝对路径或 ~/ 路径。')
    settings = {key: binding[key] for key in ('server_url', 'app_url', 'device_name')}
    settings.update(workspaces_root=str(workspaces.resolve()),
                    max_concurrent_tasks=1, disable_auto_update=True)
    return binding, home/'.multica/profiles'/profile/'config.json', settings


def configure_personal(home):
    binding, target, settings = personal_settings(home)
    current = json.loads(target.read_text()) if target.exists() else {}
    if not isinstance(current, dict):
        raise ValueError('本机 profile 格式无效，未修改。')
    if any(current.get(key) not in (None, '', settings[key]) for key in ('server_url', 'app_url')):
        raise ValueError('同名 profile 已连接其他服务，未覆盖；先核对本机绑定。')
    binary = home/'.local/bin/multica'
    release = json.loads((Path(__file__).resolve().parents[1]/'versions.json').read_text())['release'].lstrip('v')
    version = subprocess.run([str(binary), '--version'], capture_output=True, text=True, timeout=15)
    if version.returncode or not re.search(r'^multica '+re.escape(release)+r'(?:\s|$)', version.stdout):
        raise ValueError('本机 Multica CLI 与固定基线不同，未修改 profile。')
    for key, value in settings.items():
        if current.get(key) == value:
            continue
        literal = str(value).lower() if isinstance(value, bool) else str(value)
        result = subprocess.run([str(binary), '--profile', binding['profile'], 'config', 'set', key, literal],
                                capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise ValueError('原生 CLI 配置失败：'+key+'；未登录或启动 daemon，可修复后重跑。')
    print('本机 profile 设置已就绪：并发 1、禁自动升级；未登录或启动 daemon。')


def require_personal_ready(home):
    binding, target, settings = personal_settings(home)
    current = json.loads(target.read_text()) if target.exists() else {}
    expected = dict(settings, workspace_id=binding['workspace_id'])
    if (not isinstance(current, dict) or any(current.get(key) != value for key, value in expected.items())
            or not isinstance(current.get('token'), str) or not current['token'].startswith(('mul_', 'mcn_'))):
        raise ValueError('本机 profile 尚未就绪：先 configure.py --personal-profile，再原生登录并 workspace switch 到恢复的工作区。')


def read_values(path, keys):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$', line)
        if not match or match.group(1) not in keys:
            continue
        name, raw = match.groups()
        words = shlex.split(raw, comments=True)
        if len(words) != 1 or name in values:
            raise SystemExit('Missing, duplicate, or unsupported assignment for ' + name)
        values[name] = words[0]
    return values


def atomic_private_write(path, text):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--init-secrets', action='store_true')
    parser.add_argument('--email')
    parser.add_argument('--lock-signup', action='store_true')
    parser.add_argument('--personal-profile', action='store_true', help='只配置本机 CLI；不读写 env、不登录或启动服务')
    args = parser.parse_args()
    if args.personal_profile:
        if args.init_secrets or args.email or args.lock_signup:
            parser.error('--personal-profile 不与服务密钥参数混用')
        configure_personal(Path.home())
        return
    if args.email and not re.fullmatch(r'[^\s@,=]+@[^\s@,=]+\.[^\s@,=]+', args.email):
        parser.error('Expected one email address')
    vault = (Path.home() / '.env').resolve(strict=True)
    directory = Path.home() / '.config/multica-selfhost'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    with (directory / 'configure.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        original = vault.read_text()
        values = read_values(vault, set(SECRET_MAP.values()))
        missing = set(SECRET_MAP.values()) - values.keys()
        if missing and not args.init_secrets:
            raise SystemExit('Multica secrets are absent; initialize explicitly with --init-secrets')
        if missing:
            backup_dir = vault.parent / 'backups'
            backup_dir.mkdir(mode=0o700, exist_ok=True)
            backup_dir.chmod(0o700)
            timestamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
            backup = backup_dir / ('before-multica-' + timestamp + '.env')
            atomic_private_write(backup, original)
            generated = {
                'MULTICA_SELFHOST_JWT_SECRET': secrets.token_hex(32),
                'MULTICA_SELFHOST_POSTGRES_PASSWORD': secrets.token_hex(32),
                'MULTICA_VCS_SECRET_KEY': base64.b64encode(secrets.token_bytes(32)).decode(),
            }
            additions = '\n# Multica self-host secrets; generated by multica-ops.\n'
            additions += ''.join(name + '=' + generated[name] + '\n' for name in sorted(missing))
            atomic_private_write(vault, original + ('' if original.endswith('\n') else '\n') + additions)
            values.update({name: generated[name] for name in missing})
            print('Created missing Multica secrets in the existing env vault; private rollback copy saved.')
        vault.chmod(0o600)
        for name in ['MULTICA_SELFHOST_JWT_SECRET', 'MULTICA_SELFHOST_POSTGRES_PASSWORD']:
            if len(values[name]) < 32 or re.search(r'[\s\x00-\x1f]', values[name]):
                raise SystemExit('Invalid secret format: ' + name)
        if len(base64.b64decode(values['MULTICA_VCS_SECRET_KEY'], validate=True)) != 32:
            raise SystemExit('MULTICA_VCS_SECRET_KEY must decode to 32 bytes')
        target = directory / 'server.env'
        current = read_values(target, {'ALLOWED_EMAILS', 'ALLOW_SIGNUP'})
        email = args.email or current.get('ALLOWED_EMAILS', '')
        signup = 'false' if args.lock_signup else current.get('ALLOW_SIGNUP', 'true')
        if signup == 'false' and not email:
            raise SystemExit('Refusing to lock signup without an allowed account')
        settings = {
            'POSTGRES_DB': 'multica', 'POSTGRES_USER': 'multica',
            'PORT': '8080', 'FRONTEND_PORT': '3000',
            'FRONTEND_ORIGIN': 'http://localhost:3000',
            'MULTICA_APP_URL': 'http://localhost:3000',
            'MULTICA_PUBLIC_URL': 'http://localhost:8080',
            'APP_ENV': 'production', 'MULTICA_IMAGE_TAG': 'v0.6.3',
            'MULTICA_VCS_INTEGRATION_ENABLED': 'true', 'DO_NOT_TRACK': '1',
            'ALLOW_SIGNUP': signup, 'ALLOWED_EMAILS': email,
        }
        settings.update({name: values[source] for name, source in SECRET_MAP.items()})
        atomic_private_write(target, '# Generated projection; edit the source or rerun configure.py.\n' +
                             ''.join(name + '=' + shlex.quote(value) + '\n' for name, value in settings.items()))
        public_docker = directory / 'docker-public'
        public_docker.mkdir(mode=0o700, exist_ok=True)
        public_docker.chmod(0o700)
        atomic_private_write(public_docker / 'config.json', json.dumps(public_config()) + '\n')
        print('Generated private server.env; secret values were not printed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
