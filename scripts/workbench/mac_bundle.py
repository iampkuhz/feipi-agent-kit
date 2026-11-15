#!/usr/bin/env python3
"""迁机配置包：固定白名单、完整校验、私有备份与原子恢复，不包含运行中数据库。"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FILES = (
    ('.env', '.local/env-vault/.env'),
    ('.gitconfig', '.gitconfig'),
    ('.ssh/config', '.ssh/config'),
    ('.qwen/settings.json', '.qwen/settings.json'),
    ('.qoder/.config.json', '.qoder/.config.json'),
    ('.codex/config.toml', '.codex/config.toml'),
    ('.claude/settings.json', '.claude/settings.json'),
    ('.omlx/settings.json', '.omlx/settings.json'),
    ('.omlx/model_settings.json', '.omlx/model_settings.json'),
    ('.config/feipi-workbench/private/services/crawl4ai.env',
     '.config/feipi-workbench/private/services/crawl4ai.env'),
    ('.config/feipi-workbench/private/openclash/router.json',
     '.config/feipi-workbench/private/openclash/router.json'),
)
ALLOWED = {target for _, target in FILES}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or str(path) != value or value not in ALLOWED:
        raise ValueError('配置包包含非白名单路径，未写入。')
    return Path(value)


def write_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix='.mac-restore-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def export_bundle(destination):
    home = Path.home().resolve()
    destination = destination.expanduser().absolute()
    # 秘密不可进入任何公开源码目录，也不覆盖已存在批次。
    if destination.resolve().is_relative_to(ROOT):
        raise ValueError('配置包必须保存在仓库之外的私有目录。')
    if not (home/'.env').is_file():
        raise ValueError('缺少 ~/.env，不能导出完整的基础配置。')
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(destination, 0o700)
    entries = []
    try:
        for source, target in FILES:
            path = home/source
            if not path.is_file():
                continue
            before = path.stat()
            data = path.read_bytes()
            after = path.stat()
            if (before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_ino, after.st_mtime_ns, after.st_size):
                raise ValueError('导出期间配置发生变化，请重试本次导出。')
            write_private(destination/'payload'/target, data)
            entries.append({'path': target, 'sha256': sha(data), 'size': len(data)})
        manifest = {
            'schema': 1, 'scope': 'configuration-only', 'source_home': str(home),
            'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'files': entries,
            'separate_restore_required': ['SSH private keys or fresh authorization',
                'Codex/Claude/Qoder authentication', 'OpenClaw consistent state backup',
                'Multica database, uploads and service secrets from one backup',
                'oMLX models', 'project code and private business data'],
        }
        write_private(destination/'manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode())
        verify_bundle(destination)
    except Exception:
        # 保留失败包供定位；它不是可供恢复的完整批次。
        print('配置导出未完成；保留私有目录，不得作为完整恢复包。', file=sys.stderr)
        raise
    print(f'配置包已导出：{destination}；{len(entries)} 个文件，未包含业务数据库/会话。')


def verify_bundle(bundle):
    bundle = bundle.expanduser().resolve()
    manifest = json.loads((bundle/'manifest.json').read_text())
    if manifest.get('schema') != 1 or manifest.get('scope') != 'configuration-only':
        raise ValueError('配置包版本或范围无效。')
    entries = manifest.get('files')
    if not isinstance(entries, list) or not entries:
        raise ValueError('配置包没有文件。')
    pending = []
    seen = set()
    for entry in entries:
        relative = checked_relative(entry['path'])
        if str(relative) in seen:
            raise ValueError('配置包包含重复路径。')
        seen.add(str(relative))
        source = bundle/'payload'/relative
        if source.is_symlink() or not source.resolve().is_relative_to(bundle/'payload'):
            raise ValueError('配置包链接越界，未写入。')
        data = source.read_bytes()
        if sha(data) != entry['sha256'] or len(data) != entry['size']:
            raise ValueError('配置包摘要或长度不符：'+str(relative))
        pending.append((relative, data))
    if '.local/env-vault/.env' not in seen:
        raise ValueError('配置包缺少 env 真源。')
    print(f'配置包完整性通过：{len(pending)} 个文件；凭据有效性和业务恢复另行验证。')
    return manifest, pending


def relocate(data, source_home, home, relative):
    if not source_home or source_home == str(home):
        return data
    # 仅替换引号/赋值后开头的 HOME 路径，不求值 env，不更改 URL 或密钥中间内容。
    text = data.decode('utf-8')
    prefix = re.escape(source_home.rstrip('/'))
    if relative.suffix == '.json':
        def visit(value):
            if isinstance(value, str) and value.startswith(source_home+'/'):
                return str(home)+value[len(source_home):]
            if isinstance(value, dict):
                return {key: visit(child) for key, child in value.items()}
            if isinstance(value, list):
                return [visit(child) for child in value]
            return value
        return (json.dumps(visit(json.loads(text)), ensure_ascii=False, indent=2)+'\n').encode()
    return re.sub(r'(?m)([=\s][\"\']?)'+prefix+r'(?=/|[\"\']?\s*$)',
                  lambda match: match[1]+str(home), text).encode()


def restore_bundle(bundle):
    from main import backup, restore
    home = Path.home().resolve()
    manifest, entries = verify_bundle(bundle)
    pending = []
    for relative, data in entries:
        target = home/relative
        for parent in target.parents:
            if parent == home:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError('恢复目标父路径冲突，未写入：'+str(parent))
        if target.exists() and target.is_dir():
            raise ValueError('恢复目标被目录占用，未写入：'+str(target))
        pending.append((target, relocate(data, manifest.get('source_home'), home, relative)))
    paths = [path for path, _ in pending]+[home/'.env']
    if (home/'.env').is_dir():
        raise ValueError('~/.env 被目录占用，未写入。')
    batch = backup('mac-private-restore', paths)
    print('私有配置回退：./workbench restore '+str(batch))
    try:
        for target, data in pending:
            write_private(target, data)
        link = home/'.env'
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to('.local/env-vault/.env')
    except Exception:
        restore(batch)
        raise
    print('私有配置已恢复；~/.env 指向本机 vault。业务数据、登录和模型仍需独立验收。')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export', 'verify', 'restore'])
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    try:
        {'export': export_bundle, 'verify': verify_bundle, 'restore': restore_bundle}[args.action](args.bundle)
    except (OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
