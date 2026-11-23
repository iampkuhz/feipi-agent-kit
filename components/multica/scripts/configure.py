"""读取指定的 env vault 项，并原子写入私有运行配置。"""
import os
import re
import shlex
import tempfile


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
