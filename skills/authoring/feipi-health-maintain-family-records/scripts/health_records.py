#!/usr/bin/env python3
"""家庭健康资料的定位、原件归档与完整性核查；只依赖 Python 标准库。"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import unquote, urlsplit, parse_qsl


DEFAULT_ROOT = Path.home() / 'Documents/life/家庭健康'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inside(root, path):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError('路径超出资料库：' + str(path))
    return resolved


def component(value):
    if not value or value in ('.', '..') or '/' in value or '\\' in value or any(ord(c) < 32 for c in value):
        raise ValueError('必须是单个安全目录名或文件名')
    return value


def library(value):
    root = Path(value).expanduser().resolve()
    for name in ('AGENTS.md', 'README.md', '家庭健康总览.md', '家庭成员', '模板'):
        if not (root / name).exists():
            raise ValueError('资料库入口缺失：' + str(root / name))
    return root


def context(root, member=None):
    members = []
    for p in sorted((root / '家庭成员').iterdir()):
        if not p.is_dir() or p.is_symlink():
            continue
        profile = p / '健康概况.md'
        text = profile.read_text() if profile.is_file() else ''
        match = re.search(r'^- 家庭称呼[：:]\s*([^；;。\n]+)', text, re.M)
        aliases = re.split(r'[、,，/]', match[1]) if match else []
        aliases = [x.strip() for x in aliases if x.strip() and x.strip() not in ('未提供', '待确认')]
        item = {'name': p.name, 'aliases': aliases, 'profile': str(profile.relative_to(root)),
                'events': sorted(str(x.relative_to(root)) for x in (p / '健康记录').glob('*/记录.md')),
                'tracking': sorted(str(x.relative_to(root)) for x in (p / '问题跟踪').glob('*/跟踪.md'))}
        members.append(item)
    candidates = [x for x in members if member in [x['name'], *x['aliases']]] if member else []
    return {'root': str(root), 'members': members if not member else [],
            'query': member, 'matches': candidates,
            'status': ('unique' if len(candidates) == 1 else 'ambiguous' if candidates else 'unresolved') if member else 'listed',
            'instructions': '先读取库规则和候选记录；称呼只做精确匹配，不能猜亲属关系。'}


def stable_source(value):
    if not value.strip():
        raise ValueError('来源不能为空')
    for raw in re.findall(r'[a-zA-Z][a-zA-Z0-9+.-]*://[^\s<>]+', value):
        url = urlsplit(raw)
        keys = {k.lower() for k, _ in parse_qsl(url.query)}
        if url.username or url.password or any(k.startswith('x-amz-') or k in
                ('token', 'access_token', 'signature', 'sig', 'expires', 'key-pair-id', 'policy') for k in keys):
            raise ValueError('来源含访问凭证或临时签名，请使用稳定页面/附件引用')
    return value.strip()


def load_manifest(path):
    if not path.exists():
        return {'files': []}
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or not isinstance(value.get('files'), list):
        raise ValueError('清单结构未知，未修改：' + str(path))
    for item in value['files']:
        if not isinstance(item, dict) or not all(k in item for k in ('local_path', 'sha256')):
            raise ValueError('清单条目结构未知，未修改：' + str(path))
    return value


def atomic_json(path, data):
    fd, name = tempfile.mkstemp(prefix='.manifest-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def archive(root, args):
    source = stable_source(args.source)
    # 核验说明同样不能混入签名 URL。
    verification = stable_source(args.verification)
    incoming = Path(args.file).expanduser().resolve(strict=True)
    if not incoming.is_file() or incoming.stat().st_size == 0:
        raise ValueError('原件必须是非空本地文件')
    member = inside(root, root / '家庭成员' / component(args.member))
    event = inside(root, member / '健康记录' / component(args.event))
    if not (member / '健康概况.md').is_file() or not (event / '记录.md').is_file():
        raise ValueError('先依据库模板建立明确成员及事件记录，再归档附件')
    name = component(args.name or incoming.name)
    original_hash = digest(incoming)
    original_size = incoming.stat().st_size
    # 全库串行化去重与清单追加，避免跨事件并发产生两份原件。
    lock_path = root / '.health-archive.lock'
    if lock_path.is_symlink():
        raise ValueError('归档锁不得是符号链接')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = event / '附件清单.json'
        if manifest.is_symlink():
            raise ValueError('清单不得是符号链接')
        data = load_manifest(manifest)
        raw_dir = inside(root, event / '原始资料')
        target = inside(root, raw_dir / name)
        if target.exists() and (not target.is_file() or digest(target) != original_hash):
            raise ValueError('同名异内容，拒绝覆盖：' + str(target))
        for p in sorted((root / '家庭成员').glob('*/健康记录/*/原始资料/*')):
            p = inside(root, p)
            if p.is_file() and p.stat().st_size == original_size and digest(p) == original_hash:
                if not p.is_relative_to(member):
                    raise ValueError('相同原件已属于另一成员，请核查归属：' + str(p.relative_to(root)))
                if p != target:
                    return {'status': 'duplicate', 'local_path': str(p.relative_to(root)), 'sha256': original_hash,
                            'next': '引用已有原件，在本次事件记录补充来源；未复制或修改清单。'}
        raw_dir.mkdir(exist_ok=True)
        copied = not target.exists()
        if copied:
            try:
                with incoming.open('rb') as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
                if digest(target) != original_hash:
                    raise ValueError('复制后哈希不符')
            except BaseException:
                target.unlink(missing_ok=True)
                raise
        item = {'local_path': str(target.relative_to(event)), 'original_filename': incoming.name,
                'source': source, 'archive_date': dt.date.today().isoformat(),
                'bytes': original_size, 'sha256': original_hash, 'verification_scope': verification}
        known = any(x['local_path'] == item['local_path'] and x['sha256'] == original_hash and
                    x.get('source') == source for x in data['files'])
        if not known:
            data['files'].append(item)
            atomic_json(manifest, data)
        return {'status': 'archived' if copied else 'already_archived',
                'local_path': str(target.relative_to(root)), 'sha256': original_hash,
                'manifest': str(manifest.relative_to(root)), 'bytes': original_size,
                'next': '补事件记录、报告索引及必要的跟踪；哈希一致不代表临床内容已核实。'}


def check(root):
    errors = []
    files = manifests = links = 0
    for path in sorted(root.rglob('*.json')):
        if path.is_symlink():
            continue
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict) or 'files' not in data:
                continue
            data = load_manifest(path)
            manifests += 1
            for item in data['files']:
                relative = Path(item['local_path'])
                if relative.is_absolute():
                    raise ValueError('清单路径必须相对资料库或清单目录')
                base = root if relative.parts and relative.parts[0] in ('家庭成员', '待整理', '共用资料') else path.parent
                original = inside(root, base / relative)
                files += 1
                if not original.is_file() or digest(original) != item['sha256']:
                    errors.append(f'{path.relative_to(root)}: 原件缺失或哈希不符 {relative}')
                elif 'bytes' in item and original.stat().st_size != item['bytes']:
                    errors.append(f'{path.relative_to(root)}: 大小不符 {relative}')
        except (OSError, ValueError, TypeError) as e:
            errors.append(f'{path.relative_to(root)}: {e}')
    for path in sorted(root.rglob('*.md')):
        if path.is_symlink():
            continue
        # 只识别实际 Markdown 链接，不检查代码块中的示例。
        content = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
        for match in re.finditer(r'\]\((?:<([^>]+)>|([^\s)]+))\)', content):
            ref = match[1] or match[2]
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', ref) or ref.startswith('#'):
                continue
            relative = unquote(ref.split('#')[0])
            links += 1
            if not (path.parent / relative).exists():
                errors.append(f'{path.relative_to(root)}: 链接缺失 {ref}')
    return {'ok': not errors, 'manifest_count': manifests, 'file_entries_checked': files,
            'local_links_checked': links, 'errors': errors,
            'scope': '本地链接存在性及清单大小/哈希；不验证身份、日期和医学内容，不覆盖未入清单原件。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('context', 'archive', 'check'):
        p = sub.add_parser(name)
        p.add_argument('--root', default=str(DEFAULT_ROOT))
        if name == 'context':
            p.add_argument('--member')
        if name == 'archive':
            for field in ('member', 'event', 'file', 'source', 'verification'):
                p.add_argument('--' + field, required=True)
            p.add_argument('--name')
    args = parser.parse_args()
    try:
        root = library(args.root)
        result = context(root, args.member) if args.action == 'context' else archive(root, args) if args.action == 'archive' else check(root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('ok') is False else 0
    except (OSError, ValueError, TypeError) as e:
        print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
