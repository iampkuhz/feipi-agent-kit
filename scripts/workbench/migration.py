#!/usr/bin/env python3
"""集中准备迁机资料：复用原生一致性备份，保留项目、模型和 env 历史，校验后才标记完成。"""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from mac_bundle import export_bundle, verify_bundle
from migration_projects import (IGNORED_CACHE_NAMES, archive_paths, digest, export_project,
                                relative, restore_project, extract_archive, validate_archive)

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
MODELS = ('Qwen3.5-0.8B-MLX-4bit', 'Qwen3-ASR-1.7B-4bit', 'SenseVoiceSmall')
BUSINESS = ('Documents/life/child-growth-diary', 'Documents/life/家庭健康',
            'Documents/life/2028.装修/home-renovation-playbook-2028', 'Documents/life/2030.房地产')


def command(args, log, **options):
    with log.open('ab') as output:
        result = subprocess.run([str(a) for a in args], stdout=output, stderr=subprocess.STDOUT, **options)
    if result.returncode:
        raise RuntimeError('准备阶段失败，日志：'+str(log))


def native_backup(component, destination):
    native_root = HOME/('.local/state/multica/backups' if component == 'multica' else
                        '.local/state/feipi-workbench/openclaw-backups')
    before = set(native_root.iterdir()) if native_root.exists() else set()
    if component == 'multica':
        args = [sys.executable, ROOT/'components/multica/scripts/backup.py', '--apply']
    else:
        args = ['bash', ROOT/'components/openclaw/scripts/backup-state.sh']
    command(args, destination/(component+'-backup.log'))
    created = set(native_root.iterdir())-before
    if len(created) != 1:
        raise RuntimeError('无法确定本轮唯一原生备份批次：'+component)
    batch = created.pop()
    if component == 'multica':
        command([sys.executable, ROOT/'components/multica/scripts/backup.py', '--verify', batch],
                destination/'multica-backup.log')
    else:
        command(['shasum', '-a', '256', '-c', 'SHA256SUMS'], destination/'openclaw-backup.log', cwd=batch)
    shutil.copytree(batch, destination/component)


def multica_module():
    directory = ROOT/'components/multica/scripts'
    spec = importlib.util.spec_from_file_location('migration_adaptation', directory/'adaptation.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project_sources(machine):
    sources = {ROOT.resolve(): False}
    for name in BUSINESS:
        path = (HOME/name).resolve()
        if not path.is_dir():
            raise ValueError('缺少迁移所需资料目录：'+name)
        if (path/'.git').exists():
            sources[path] = True
    for project in machine.get('projects', {}).values():
        source = Path(project['root']).expanduser().resolve()
        if (source/'.git').exists():
            sources.setdefault(source, False)
    vault = (HOME/'.env').resolve().parent
    if (vault/'.git').exists():
        sources.setdefault(vault, False)
    for source in sources:
        relative(str(source.relative_to(HOME.resolve())))
        if not source.is_dir() or not (source/'.git').exists():
            raise ValueError('缺少迁移所需 Git 来源：'+str(source))
    return sources


def snapshot_documents(destination):
    entries = []
    directory = destination/'documents'
    directory.mkdir(mode=0o700)
    for name in BUSINESS:
        source = HOME/name
        if (source/'.git').exists():
            continue
        names = [str(p.relative_to(source)) for p in source.rglob('*')
                 if (p.is_file() or p.is_symlink()) and
                 not any(part in IGNORED_CACHE_NAMES for part in p.relative_to(source).parts)]
        archive = str(len(entries))+'.tar.gz'
        archive_paths(source, names, directory/archive)
        entries.append({'home_relative': name, 'archive': archive, 'files': len(names)})
    return entries


def snapshot_models(destination):
    root = HOME/'.omlx/models'
    names = []
    for name in MODELS:
        candidates = [root/name, root/'mlx-community'/name]
        candidates = [path for path in candidates if (path/'config.json').is_file()]
        if len(candidates) != 1:
            raise ValueError('当前模型目录缺失或歧义：'+name)
        model = candidates[0]
        for path in model.rglob('*'):
            if path.is_file() and '.cache' not in path.relative_to(model).parts:
                if path.is_symlink():
                    raise ValueError('模型使用外部链接，请先用官方工具物化：'+name)
                names.append(str(path.relative_to(root)))
    archive_paths(root, names, destination/'omlx-models.tar.gz')


def litellm_backup(destination):
    directory = destination/'litellm'
    directory.mkdir(mode=0o700)
    # pg_dump 自身使用一致性事务；不复制在线 PostgreSQL 数据目录。
    with (directory/'database.dump').open('xb') as output, (directory/'backup.log').open('ab') as errors:
        subprocess.run(['podman', 'exec', 'litellm-db-podman', 'pg_dump', '-Fc', '-U', 'litellm', 'litellm'],
                       stdout=output, stderr=errors, check=True, timeout=300)
    with (directory/'database.dump').open('rb') as stream:
        command(['podman', 'exec', '-i', 'litellm-db-podman', 'pg_restore', '--list'],
                directory/'backup.log', stdin=stream, timeout=60)
    metadata = subprocess.check_output(['podman', 'inspect', 'litellm-db-podman', '--format', '{{.ImageName}}'], text=True).strip()
    (directory/'database-image.txt').write_text(metadata+'\n')
    # OAuth 状态位置从真实容器挂载反推，兼容 AGENT_SERVICE_DATA_DIR 的现有覆盖。
    mounts = json.loads(subprocess.check_output(['podman', 'inspect', 'litellm-proxy-podman'], text=True))[0]['Mounts']
    token_dirs = [Path(item['Source']) for item in mounts if item['Destination'] == '/app/chatgpt-tokens']
    if len(token_dirs) != 1 or not token_dirs[0].is_dir():
        raise ValueError('无法确定 LiteLLM 原生 OAuth 状态目录。')
    source = token_dirs[0]
    names = [str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() or p.is_symlink()]
    archive_paths(source, names, directory/'chatgpt-tokens.tar.gz')


def prepare(destination, proxy_backup):
    if platform.system() != 'Darwin':
        raise ValueError('当前业务一致性备份入口仅支持原机 macOS。')
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.resolve().is_relative_to(ROOT):
        raise ValueError('请指定仓库外尚不存在的私有目录。')
    proxy_backup = proxy_backup.expanduser().resolve()
    with zipfile.ZipFile(proxy_backup) as archive:
        if archive.testzip() is not None:
            raise ValueError('代理官方备份损坏。')
    for executable in ('git', 'podman', 'openclaw', 'launchctl', 'shasum'):
        if not shutil.which(executable):
            raise ValueError('缺少原机命令：'+executable)
    command_root = ROOT/'tools/runtime/podman.py'
    subprocess.run([sys.executable, str(command_root), 'check'], check=True, stdout=subprocess.DEVNULL)
    multica = multica_module()
    daemon = multica.cli('daemon', 'status')
    if daemon.get('active_task_count', 0) or any(
            run.get('status') in multica.ACTIVE for agent in multica.cli('agent', 'list')
            for run in multica.agent_runs(agent['id'])):
        raise ValueError('Multica 仍有活动任务；先完成任务并暂停新派发，再执行同一准备命令。')
    machine = multica.machine()
    projects = project_sources(machine)
    if any(destination.resolve().is_relative_to(source) for source in projects):
        raise ValueError('迁移包不能保存在任一被导出的项目内。')
    if any(destination.resolve().is_relative_to(HOME/name) for name in BUSINESS):
        raise ValueError('迁移包不能保存在被导出的资料目录内。')
    protected = ('.openclaw', '.omlx/models', '.local/state/multica/backups',
                 '.local/state/feipi-workbench/openclaw-backups')
    if any(destination.resolve().is_relative_to((HOME/name).resolve()) for name in protected):
        raise ValueError('迁移包不能保存在原业务数据或原生备份目录内。')
    # 先做来源和空间预检，尚未停止任何业务组件。
    for name in MODELS:
        if not any((HOME/'.omlx/models'/prefix/name/'config.json').is_file() for prefix in ('', 'mlx-community')):
            raise ValueError('缺少当前使用模型：'+name)
    existing_parent = destination.parent
    while not existing_parent.exists():
        existing_parent = existing_parent.parent
    if shutil.disk_usage(existing_parent).free < 8*1024**3:
        raise ValueError('迁移包含约 3 GiB 模型和业务备份；目标至少需要 8 GiB 可用空间。')
    destination.mkdir(parents=True, mode=0o700)
    destination.chmod(0o700)
    env_before = digest(HOME/'.env')
    target = 'gui/'+str(os.getuid())+'/local.multica.personal'
    was_loaded = subprocess.run(['launchctl', 'print', target], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL).returncode == 0
    try:
        print('准备基础配置与业务一致性备份；日志和秘密仅保存在私有批次。', flush=True)
        export_bundle(destination/'mac-private')
        try:
            if was_loaded:
                command([sys.executable, ROOT/'components/multica/scripts/manage-runtime.py', 'stop'], destination/'multica-maintenance.log')
            native_backup('multica', destination)
        finally:
            if was_loaded:
                command([sys.executable, ROOT/'components/multica/scripts/manage-runtime.py', 'start'], destination/'multica-maintenance.log')
        native_backup('openclaw', destination)
        litellm_backup(destination)
        shutil.copyfile(proxy_backup, destination/'flclash-native.zip')
        print('业务备份通过，继续保存 Git 历史、未提交改动、资料原件与模型。', flush=True)
        (destination/'projects').mkdir(mode=0o700)
        entries = []
        for index, (source, business) in enumerate(sorted(projects.items())):
            entry = export_project(source, destination/'projects'/str(index), HOME, business)
            entries.append({'directory': str(index), **entry})
        documents = snapshot_documents(destination)
        snapshot_models(destination)
        if digest(HOME/'.env') != env_before:
            raise RuntimeError('准备期间 env 发生变化，批次未完成；请重新导出。')
        manifest = {'schema': 1, 'scope': 'new-mac-migration', 'status': 'complete-export',
                    'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'source_home': str(HOME), 'projects': entries, 'documents': documents,
                    'separate_preparation': ['新机账号登录、代理节点同步及系统权限',
                        'Multica CLI/runtime 使用新设备身份', '切换前停止旧机主力，避免双主'],
                    'files': {str(path.relative_to(destination)): digest(path)
                              for path in sorted(destination.rglob('*')) if path.is_file()}}
        (destination/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
        verify(destination)
    except BaseException:
        (destination/'INCOMPLETE').write_text('本批次失败，不得作为完整恢复包。检查私有日志后重新导出至新目录。\n')
        raise
    print('迁机资料已集中准备并完成字节校验：'+str(destination))


def verify(destination):
    destination = destination.expanduser().resolve()
    manifest = json.loads((destination/'manifest.json').read_text())
    if ((destination/'INCOMPLETE').exists() or manifest.get('schema') != 1 or
            manifest.get('scope') != 'new-mac-migration' or manifest.get('status') != 'complete-export'):
        raise ValueError('这不是已完成的完整迁移包。')
    required = {'mac-private/manifest.json', 'multica/database.dump', 'multica/server.env',
                'openclaw/state.tar.gz', 'openclaw/SHA256SUMS', 'litellm/database.dump',
                'flclash-native.zip', 'omlx-models.tar.gz'}
    files = manifest['files']
    if not required.issubset(files):
        raise ValueError('迁移包缺少必要资产。')
    for name, expected in files.items():
        path = destination/relative(name)
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(destination):
            raise ValueError('迁移包文件缺失或越界。')
        if digest(path) != expected:
            raise ValueError('迁移包摘要不符：'+name)
    verify_bundle(destination/'mac-private')
    if not manifest.get('projects'):
        raise ValueError('迁移包没有项目来源记录。')
    seen = set()
    for project in manifest['projects']:
        directory = destination/'projects'/relative(project['directory'])
        key = str(relative(project['home_relative']))
        if key in seen:
            raise ValueError('迁移包项目目标重复。')
        seen.add(key)
        for name in ('repository.bundle', 'staged.patch', 'unstaged.patch', 'project.json',
                     'untracked.tar.gz', 'private-overrides.tar.gz'):
            if str((directory/name).relative_to(destination)) not in files:
                raise ValueError('迁移包项目文件不完整。')
        metadata = json.loads((directory/'project.json').read_text())
        if 'stashes' not in metadata:
            raise ValueError('项目记录没有完整 stash 清单，请使用当前版本重新准备。')
        if metadata != {k: v for k, v in project.items() if k != 'directory'}:
            raise ValueError('项目记录与主清单不一致。')
        subprocess.run(['git', '-C', ROOT, 'bundle', 'verify', directory/'repository.bundle'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for name in ('untracked.tar.gz', 'private-overrides.tar.gz', 'business-data.tar.gz'):
            if (directory/name).exists():
                validate_archive(directory/name)
    for document in manifest['documents']:
        key = str(relative(document['home_relative']))
        name = 'documents/'+str(relative(document['archive']))
        if key in seen or name not in files:
            raise ValueError('资料目标重复或归档缺失。')
        seen.add(key)
        validate_archive(destination/name)
    with zipfile.ZipFile(destination/'flclash-native.zip') as archive:
        if archive.testzip() is not None:
            raise ValueError('代理备份 CRC 检查失败。')
    print('完整迁移包清单及摘要通过；数据库/业务功能仍须在目标环境恢复验收。')
    return manifest


def restore_sources(destination, only):
    """先校验整包和全部选中目标，再恢复到空目录；不启动业务或复制设备身份。"""
    destination = destination.expanduser().resolve()
    manifest = verify(destination)
    entries = [('project', item) for item in manifest['projects']]
    entries += [('document', item) for item in manifest['documents']]
    if only:
        selected = set(only)
        if selected-set(item['home_relative'] for _, item in entries):
            raise ValueError('--only 包含清单中不存在的来源。')
        entries = [(kind, item) for kind, item in entries if item['home_relative'] in selected]
    home = HOME.resolve()
    for _, item in entries:
        target = home/relative(item['home_relative'])
        if os.path.lexists(target) or not target.resolve().is_relative_to(home):
            raise ValueError('来源目标已存在或父级越界；未写入：'+str(target))
    for kind, item in entries:
        if kind == 'project':
            restore_project(destination/'projects'/relative(item['directory']), home,
                            Path(manifest['source_home']))
        else:
            target = home/relative(item['home_relative'])
            target.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix='.migration-', dir=target.parent))
            try:
                extract_archive(destination/'documents'/relative(item['archive']), stage, target,
                                home, Path(manifest['source_home']))
                stage.rename(target)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        print('来源已恢复：'+item['home_relative'])
    print('代码和资料原件恢复完成；配置、数据库和服务须按各自恢复流程继续。')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'verify', 'restore-sources'])
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--proxy-backup', type=Path)
    parser.add_argument('--only', action='append', help='仅恢复指定 HOME 相对来源；可重复使用')
    args = parser.parse_args()
    if args.action == 'prepare' and not args.proxy_backup:
        parser.error('prepare 必须指定 --proxy-backup 官方本地 ZIP 备份。')
    try:
        if args.action == 'prepare':
            prepare(args.bundle, args.proxy_backup)
        elif args.action == 'verify':
            verify(args.bundle)
        else:
            restore_sources(args.bundle, args.only)
    except KeyboardInterrupt:
        raise SystemExit('准备已中断；未完成批次不能用于恢复。原业务恢复结果见该批次私有日志。')
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, zipfile.BadZipFile, tarfile.TarError,
            subprocess.SubprocessError) as error:
        raise SystemExit(str(error))


if __name__ == '__main__':
    main()
