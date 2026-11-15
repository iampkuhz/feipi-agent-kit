"""用原生 Git bundle/patch 和标准 tar 保留项目，不复制构建缓存或设备身份。"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile
import tempfile
import shutil

IGNORED_CACHE_NAMES = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.cache', '.gradle', '.DS_Store'}
PRIVATE_OVERRIDES = ('.mcp.json', '.claude/settings.local.json', '.codex/config.toml', '.env',
                     '.env.local', 'components/mac/Brewfile.local')


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args])


def relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or str(path) != value:
        raise ValueError('迁移记录包含越界或非规范路径。')
    return Path(value)


def signature(path):
    value = path.lstat()
    return (value.st_ino, value.st_size, value.st_mtime_ns, value.st_mode)


def archive_paths(source, names, destination):
    """不跟随符号链接；捕获前后核对本次每个文件，避免归档正在变化的资料。"""
    snapshots = {}
    with tarfile.open(destination, 'w:gz', dereference=False, compresslevel=1) as output:
        # 每个文件单独保存，避免 tar 将硬链接转成额外的归档成员类型。
        for name in sorted(set(names)):
            path = source/relative(name)
            before = signature(path)
            mode = before[3]
            if not (stat.S_ISREG(mode) or stat.S_ISLNK(mode)):
                raise ValueError('资料只允许普通文件和符号链接：'+name)
            output.inodes.clear()
            output.add(path, arcname=name, recursive=False)
            if signature(path) != before:
                raise RuntimeError('导出期间文件变化，请重跑：'+name)
            snapshots[name] = before
    for name, before in snapshots.items():
        if signature(source/name) != before:
            raise RuntimeError('导出期间文件变化，请重跑：'+name)
    return snapshots


def export_project(source, destination, home, business_data=False):
    source = source.resolve()
    home_relative = str(source.relative_to(home.resolve()))
    relative(home_relative)
    if destination.resolve().is_relative_to(source):
        raise ValueError('导出目录不能位于被导出的项目内。')
    destination.mkdir(mode=0o700)
    head = git(source, 'rev-parse', 'HEAD').decode().strip()
    branch = subprocess.run(['git', '-C', str(source), 'symbolic-ref', '--short', 'HEAD'],
                            capture_output=True, text=True, check=False).stdout.strip() or None
    # Git bundle 保留全部本地 refs；两个补丁分别保留暂存和未暂存的状态。
    staged = git(source, 'diff', '--cached', '--binary')
    unstaged = git(source, 'diff', '--binary')
    refs = git(source, 'show-ref')
    stashes = []
    for index, head_value in enumerate(git(source, 'stash', 'list', '--format=%H').decode().splitlines()):
        message = git(source, 'log', '-g', '-1', '--format=%gs', 'stash@{'+str(index)+'}').decode().rstrip('\n')
        stashes.append({'head': head_value, 'message': message})
    remotes = {}
    for name in git(source, 'remote').decode().splitlines():
        remotes[name] = {'fetch': git(source, 'remote', 'get-url', '--all', name).decode().splitlines(),
                         'push': git(source, 'remote', 'get-url', '--push', '--all', name).decode().splitlines()}
    # 较早 stash 只存在于 reflog；--all 单独使用会漏掉它们。
    git(source, 'bundle', 'create', str(destination/'repository.bundle'), '--all', '--reflog')
    (destination/'staged.patch').write_bytes(staged)
    (destination/'unstaged.patch').write_bytes(unstaged)
    names = [name for name in git(source, 'ls-files', '--others', '--exclude-standard', '-z').decode().split('\0') if name]
    snapshots = archive_paths(source, names, destination/'untracked.tar.gz')
    overrides = [name for name in PRIVATE_OVERRIDES if os.path.lexists(source/name)]
    snapshots.update(archive_paths(source, overrides, destination/'private-overrides.tar.gz'))
    ignored_count = 0
    if business_data:
        ignored = [name for name in git(source, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z').decode().split('\0')
                   if name and not any(part in IGNORED_CACHE_NAMES for part in PurePosixPath(name).parts)]
        snapshots.update(archive_paths(source, ignored, destination/'business-data.tar.gz'))
        ignored_count = len(ignored)
    if (git(source, 'rev-parse', 'HEAD').decode().strip() != head or
            git(source, 'diff', '--cached', '--binary') != staged or git(source, 'diff', '--binary') != unstaged or
            git(source, 'ls-files', '--others', '--exclude-standard', '-z').decode().split('\0') != names+[''] or
            git(source, 'show-ref') != refs or
            git(source, 'stash', 'list', '--format=%H').decode().splitlines() != [s['head'] for s in stashes] or
            any(signature(source/name) != before for name, before in snapshots.items())):
        raise RuntimeError('导出期间项目状态变化，未形成完整批次：'+home_relative)
    metadata = {'home_relative': home_relative, 'head': head, 'branch': branch, 'remotes': remotes, 'stashes': stashes,
                'untracked_files': len(names), 'business_data_files': ignored_count,
                'private_overrides': overrides}
    (destination/'project.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
    return metadata


def validate_archive(path):
    """校验成员和完整压缩流；这里不解包、不求值归档中的任何内容。"""
    with tarfile.open(path, 'r:*') as archive:
        for member in archive:
            relative(member.name.rstrip('/'))
            if not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError('归档含不允许的成员类型。')
            if member.isfile():
                stream = archive.extractfile(member)
                while stream.read(1024*1024):
                    pass


def extract_archive(path, destination, final_target, home, old_home):
    """兼容 Python 3.10 的有限解包：不经过父级链接写文件，链接只能落在新 HOME。"""
    validate_archive(path)
    with tarfile.open(path) as archive:
        for member in archive:
            name = relative(member.name.rstrip('/'))
            target = destination/name
            parent = target.parent
            while parent != destination:
                if parent.is_symlink():
                    raise ValueError('归档成员的父目录是符号链接。')
                parent = parent.parent
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                target.mkdir(exist_ok=True)
                continue
            if member.issym():
                link = Path(member.linkname)
                if link.is_absolute():
                    try:
                        link = home/link.relative_to(old_home)
                    except ValueError as error:
                        raise ValueError('项目包含 HOME 外的绝对链接。') from error
                else:
                    link = final_target/name.parent/link
                link = Path(os.path.normpath(link))
                if not link.is_relative_to(home):
                    raise ValueError('归档链接超出新 HOME。')
                if target.is_dir() and not target.is_symlink():
                    raise ValueError('归档链接与目录冲突。')
                if os.path.lexists(target):
                    target.unlink()
                target.symlink_to(os.path.relpath(link, (final_target/name).parent))
            else:
                # 原子替换也用于已跟踪的私有覆写项，避免跟随原目标链接。
                fd, temporary = tempfile.mkstemp(prefix='.migration-', dir=target.parent)
                try:
                    with os.fdopen(fd, 'wb') as output, archive.extractfile(member) as stream:
                        shutil.copyfileobj(stream, output)
                    os.chmod(temporary, member.mode & 0o777)
                    os.replace(temporary, target)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)


def restore_project(project, home, old_home):
    """只向不存在的目标恢复；每个补丁失败都停止，不覆盖用户已有项目。"""
    home = home.resolve()
    metadata = json.loads((project/'project.json').read_text())
    target = home/relative(metadata['home_relative'])
    if not target.resolve().is_relative_to(home):
        raise ValueError('项目目标父级越出 HOME。')
    if target.exists() or target.is_symlink():
        raise ValueError('项目目标已存在，未覆盖：'+str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.migration-', dir=target.parent))
    try:
        git(stage, 'init', '--quiet')
        # 全部 refs 包括本地分支、远端跟踪和 stash；不把 bundle 本身保留为 origin。
        git(stage, 'fetch', '--quiet', str(project/'repository.bundle'), '+refs/*:refs/*')
        if metadata['stashes']:
            git(stage, 'update-ref', '-d', 'refs/stash')
            for stash in reversed(metadata['stashes']):
                git(stage, 'stash', 'store', '--message', stash['message'], stash['head'])
        if metadata['branch']:
            git(stage, 'symbolic-ref', 'HEAD', 'refs/heads/'+metadata['branch'])
        else:
            git(stage, 'update-ref', '--no-deref', 'HEAD', metadata['head'])
        git(stage, 'reset', '--hard', '--quiet', metadata['head'])
        for name, urls in metadata['remotes'].items():
            for key, values in [('url', urls['fetch']), ('pushurl', urls['push'])]:
                for url in values:
                    git(stage, 'config', '--add', 'remote.'+name+'.'+key, url)
            git(stage, 'config', 'remote.'+name+'.fetch', '+refs/heads/*:refs/remotes/'+name+'/*')
        for name, flags in [('staged.patch', ['--index']), ('unstaged.patch', [])]:
            if (project/name).stat().st_size:
                git(stage, 'apply', *flags, str(project/name))
        for name in ['untracked.tar.gz', 'private-overrides.tar.gz', 'business-data.tar.gz']:
            if (project/name).exists():
                extract_archive(project/name, stage, target, home, old_home)
        if git(stage, 'rev-parse', 'HEAD').decode().strip() != metadata['head']:
            raise RuntimeError('Git bundle 的 HEAD 与导出记录不一致。')
        stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return target


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()
