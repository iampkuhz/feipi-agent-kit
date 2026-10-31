#!/usr/bin/env python3
"""Publish managed runtime files outside macOS's Documents privacy boundary."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

home = Path.home()
source = Path(__file__).resolve().parent.parent
target = home / '.local/share/multica/ops'
target.mkdir(mode=0o700, parents=True, exist_ok=True)
target.chmod(0o700)
files = [source / 'versions.json']
files += sorted((source / 'scripts').glob('*.py'))
files += sorted(p for p in (source / 'config').rglob('*') if p.is_file())
files += sorted(path for path in (source / 'bin').iterdir() if path.is_file())
# 发布前验证整个集合；每个文件原子替换，运行任务须事先排空。
for path in files:
    if path.suffix == '.py':
        compile(path.read_text(), str(path), 'exec')
    if path.suffix == '.json':
        json.loads(path.read_text())
for path in (source / 'bin').iterdir():
    command = home / '.local/bin' / path.name
    if command.is_symlink() and command.resolve() not in [path, target / 'bin' / path.name]:
        raise SystemExit('Refusing to replace an unrelated command: ' + path.name)
    if command.exists() and not command.is_symlink():
        raise SystemExit('Refusing to replace an existing regular file: ' + path.name)
manifest = {}
for path in files:
    relative = path.relative_to(source)
    installed = target / relative
    installed.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = installed.with_name('.' + installed.name + '.new')
    shutil.copyfile(path, temporary)
    temporary.chmod(stat.S_IMODE(path.stat().st_mode))
    os.replace(temporary, installed)
    manifest[str(relative)] = hashlib.sha256(installed.read_bytes()).hexdigest()
for path in (source / 'bin').iterdir():
    if not path.is_file():
        continue
    command = home / '.local/bin' / path.name
    if command.is_symlink():
        if command.resolve() not in [path, target / 'bin' / path.name]:
            raise SystemExit('Refusing to replace an unrelated command: ' + path.name)
        command.unlink()
    elif command.exists():
        raise SystemExit('Refusing to replace an existing regular file: ' + path.name)
    command.symlink_to(target / 'bin' / path.name)
(target / 'installed-files.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Published managed runtime files outside Documents:', target)
