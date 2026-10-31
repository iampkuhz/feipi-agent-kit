#!/usr/bin/env python3
"""将备份还原到无网络临时 PostgreSQL，比较记录数；不接触正式数据卷。"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import uuid

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('backup', root / 'scripts/backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('batch')
a = p.parse_args()
batch = Path(a.batch).expanduser().resolve()
backup.verify(batch)
expected = json.loads((batch / 'row-counts.json').read_text())
service = str(root / 'bin/multica-service')
image = subprocess.check_output([service, 'images', '-q', 'postgres'], text=True).strip()
if not image or len(image.splitlines()) != 1:
    raise SystemExit('无法确定已运行 PostgreSQL 的唯一镜像。')
name = 'multica-restore-check-' + uuid.uuid4().hex[:12]
container = subprocess.check_output(['docker', 'run', '--rm', '-d', '--network', 'none', '--name', name,
                                     '-e', 'POSTGRES_USER=multica', '-e', 'POSTGRES_DB=multica',
                                     '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image], text=True).strip()
try:
    for _ in range(30):
        # 初始化临时服务只监听 Unix socket；TCP 就绪才表示最终 PostgreSQL 已启动。
        result = subprocess.run(['docker', 'exec', container, 'pg_isready', '-h', '127.0.0.1', '-U', 'multica'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError('临时恢复数据库未就绪。')
    with (batch / 'database.dump').open('rb') as stream:
        subprocess.run(['docker', 'exec', '-i', container, 'pg_restore', '-U', 'multica', '-d', 'multica', '--exit-on-error'], stdin=stream, check=True)
    actual = {}
    for table in ['issue', 'comment', 'attachment', 'agent']:
        actual[table] = int(subprocess.check_output(['docker', 'exec', container, 'psql', '-U', 'multica', '-d', 'multica', '-Atc', 'SELECT count(*) FROM ' + table], text=True).strip())
    if actual != expected:
        raise RuntimeError('恢复后的记录数不一致。')
    print(json.dumps({'restored': True, 'network': 'none', 'counts': actual}, ensure_ascii=False))
finally:
    subprocess.run(['docker', 'rm', '-f', '-v', container], stdout=subprocess.DEVNULL, check=True)
