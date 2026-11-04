#!/usr/bin/env python3
"""Publish managed runtime files outside macOS's Documents privacy boundary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

home = Path.home()
source = Path(__file__).resolve().parent.parent
target = home / '.local/share/multica/ops'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--only', action='append', metavar='RELATIVE_FILE',
                    help='Publish only this source file; repeat for a scoped update of an existing runtime.')
parser.add_argument('--remove', action='append', default=[], metavar='RELATIVE_FILE',
                    help='Remove an unchanged file owned by the installed manifest; repeat as needed.')
args = parser.parse_args()
target.mkdir(mode=0o700, parents=True, exist_ok=True)
target.chmod(0o700)
files = [source / 'versions.json']
files += sorted((source / 'scripts').glob('*.py'))
files += sorted(p for p in (source / 'config').rglob('*') if p.is_file())
files += sorted(path for path in (source / 'bin').iterdir() if path.is_file())
manifest = {}
if args.only or args.remove:
    manifest_path = target / 'installed-files.json'
    if not manifest_path.exists():
        raise SystemExit('Scoped publication requires an existing installed manifest.')
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest.items():
        if hashlib.sha256((target / name).read_bytes()).hexdigest() != expected:
            raise SystemExit('Runtime differs from installed manifest: ' + name)
    allowed = {str(path.relative_to(source)): path for path in files}
    if any(name not in allowed for name in args.only or []):
        raise SystemExit('--only must name an exact managed source file.')
    if any(name not in manifest or (source / name).exists() for name in args.remove):
        raise SystemExit('--remove requires an installed file already retired from its source path.')
    for name in args.remove:
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise SystemExit('Invalid managed removal path.')
        if path.parent == Path('bin'):
            command = home / '.local/bin' / path.name
            if command.exists() or command.is_symlink():
                if not command.is_symlink() or command.resolve() != (target / name).resolve():
                    raise SystemExit('Refusing to remove an unrelated command: ' + path.name)
    files = [allowed[name] for name in dict.fromkeys(args.only or [])]
bin_files = [path for path in files if path.parent == source / 'bin']
# 发布前验证整个集合；每个文件原子替换，运行任务须事先排空。
for path in files:
    if path.suffix == '.py':
        compile(path.read_text(), str(path), 'exec')
    if path.suffix == '.json':
        json.loads(path.read_text())
for path in bin_files:
    command = home / '.local/bin' / path.name
    if command.is_symlink() and command.resolve() not in [path.resolve(), (target / 'bin' / path.name).resolve()]:
        raise SystemExit('Refusing to replace an unrelated command: ' + path.name)
    if command.exists() and not command.is_symlink():
        raise SystemExit('Refusing to replace an existing regular file: ' + path.name)
for path in files:
    relative = path.relative_to(source)
    installed = target / relative
    installed.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = installed.with_name('.' + installed.name + '.new')
    shutil.copyfile(path, temporary)
    temporary.chmod(stat.S_IMODE(path.stat().st_mode))
    os.replace(temporary, installed)
    manifest[str(relative)] = hashlib.sha256(installed.read_bytes()).hexdigest()
for path in bin_files:
    if not path.is_file():
        continue
    command = home / '.local/bin' / path.name
    if command.is_symlink():
        if command.resolve() not in [path.resolve(), (target / 'bin' / path.name).resolve()]:
            raise SystemExit('Refusing to replace an unrelated command: ' + path.name)
        command.unlink()
    elif command.exists():
        raise SystemExit('Refusing to replace an existing regular file: ' + path.name)
    command.symlink_to(target / 'bin' / path.name)
for name in dict.fromkeys(args.remove):
    path = Path(name)
    if path.parent == Path('bin'):
        command = home / '.local/bin' / path.name
        if command.is_symlink():
            command.unlink()
    (target / name).unlink()
    del manifest[name]
manifest_temp = target / '.installed-files.json.new'
manifest_temp.write_text(json.dumps(manifest, indent=2) + '\n')
os.replace(manifest_temp, target / 'installed-files.json')
print('Published managed runtime files outside Documents:', target)
if args.only:
    print('Published files:', ', '.join(args.only))
if args.remove:
    print('Removed retired managed files:', ', '.join(args.remove))
