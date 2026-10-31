#!/usr/bin/env python3
"""Create a private consistent database/uploads/config recovery batch."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from adaptation import machine, cli, agent_runs, ACTIVE


def verify(batch):
    batch = Path(batch).expanduser().resolve()
    manifest = json.loads((batch / 'SHA256SUMS.json').read_text())
    for name, expected in manifest.items():
        path = (batch / name).resolve()
        if batch not in path.parents or not path.is_file():
            raise RuntimeError('备份文件缺失或路径越界：' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('备份校验失败：' + name)
    for name in ['database.dump', 'server.env', 'versions.json', 'compose.pinned.yml']:
        if name not in manifest:
            raise RuntimeError('备份缺少必要文件：' + name)
    print('备份清单校验通过，文件数：', len(manifest))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Stop existing Web/API writers briefly and make a backup; first drain runs.')
    parser.add_argument('--verify', metavar='BATCH', help='只核对已完成备份，不恢复或修改服务')
    args = parser.parse_args()
    if args.verify:
        verify(args.verify)
        return
    if not args.apply:
        print('Preview: drain tasks; stop Web/API; pg_dump; validate dump; copy uploads/config; resume existing services. Use --apply to execute.')
        return
    root = Path(__file__).resolve().parent.parent
    m = machine()
    daemon = cli('daemon', 'status')
    if daemon.get('status') != 'stopped':
        raise SystemExit('先排空并停止受管 LaunchAgent；防止备份停写期间后台重新启动服务。')
    for agent in cli('agent', 'list'):
        if any(r.get('status') in ACTIVE for r in agent_runs(agent['id'])):
            raise SystemExit('仍存在活动任务；先排空。')
    service = str(root / 'bin/multica-service')
    batch = Path.home() / '.local/state/multica/backups' / datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    batch.mkdir(mode=0o700, parents=True, exist_ok=False)
    batch.chmod(0o700)
    active = subprocess.check_output([service, 'ps', '--services', '--status', 'running'], text=True).splitlines()
    writers = [name for name in ['frontend', 'backend'] if name in active]
    try:
        if writers:
            subprocess.run([service, 'stop', *writers], check=True)
        partial = batch / 'database.dump.partial'
        with partial.open('xb') as stream:
            os.chmod(partial, 0o600)
            subprocess.run([service, 'exec', '-T', 'postgres', 'pg_dump', '-Fc', '-U', 'multica', 'multica'], stdout=stream, check=True)
        if partial.stat().st_size == 0:
            raise RuntimeError('Empty database dump')
        with partial.open('rb') as stream:
            subprocess.run([service, 'exec', '-T', 'postgres', 'pg_restore', '--list'], stdin=stream, stdout=subprocess.DEVNULL, check=True)
        partial.rename(batch / 'database.dump')
        counts = {}
        for table in ['issue', 'comment', 'attachment', 'agent']:
            counts[table] = int(subprocess.check_output([service, 'exec', '-T', 'postgres', 'psql', '-U', 'multica', '-d', 'multica', '-Atc', 'SELECT count(*) FROM ' + table], text=True).strip())
        (batch / 'row-counts.json').write_text(json.dumps(counts, indent=2) + '\n')
        (batch / 'uploads').mkdir(mode=0o700)
        subprocess.run([service, 'cp', 'backend:/app/data/uploads/.', str(batch / 'uploads')], check=True)
        shutil.copyfile(Path.home() / '.config/multica-selfhost/server.env', batch / 'server.env')
        (batch / 'server.env').chmod(0o600)
        shutil.copyfile(root / 'versions.json', batch / 'versions.json')
        shutil.copyfile(root / 'config/compose.pinned.yml', batch / 'compose.pinned.yml')
        # 保存恢复绑定和防重回执，不复制 CLI 登录/设备身份或工具私有会话。
        config_root = Path.home() / '.config/multica-selfhost'
        shutil.copyfile(config_root / 'machine.json', batch / 'machine.reference.json')
        (batch / 'machine.reference.json').chmod(0o600)
        receipts = Path.home() / '.local/state/multica/adaptation'
        if receipts.exists():
            shutil.copytree(receipts, batch / 'adaptation', ignore=shutil.ignore_patterns('*.lock'))
        shutil.copytree(root / 'config', batch / 'declarations')
        published = Path.home() / '.local/share/multica/ops'
        installed = json.loads((published / 'installed-files.json').read_text())
        for name, expected in installed.items():
            original = published / name
            if hashlib.sha256(original.read_bytes()).hexdigest() != expected:
                raise RuntimeError('运行副本偏离发布清单：' + name)
            target = batch / 'ops-runtime' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
        shutil.copy2(published / 'installed-files.json', batch / 'ops-runtime/installed-files.json')
        checks = {}
        for path in sorted(batch.rglob('*')):
            if path.is_file():
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                checks[str(path.relative_to(batch))] = digest.hexdigest()
        (batch / 'SHA256SUMS.json').write_text(json.dumps(checks, indent=2) + '\n')
        (batch / 'RESTORE.txt').write_text(
            'Private recovery batch: database, uploads and server encryption keys belong together.\n'
            'Restore into a fresh PostgreSQL 17 instance and the same Multica version first.\n'
            'Do not copy CLI device identity. Encrypt this batch before off-machine storage.\n')
        print('Recovery batch completed:', batch)
        print('Database dump list validated; files checksummed:', len(checks))
    finally:
        if writers:
            subprocess.run([service, 'up', '-d', '--pull', 'never', *writers], check=True)


if __name__ == '__main__':
    main()
