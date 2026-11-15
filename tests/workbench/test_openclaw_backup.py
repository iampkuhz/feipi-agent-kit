"""真实 WAL SQLite 与 tar 验证停写备份；只替换进程管理命令。"""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class OpenClawBackup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi openclaw backup ')
        self.base = Path(self.temp.name).resolve()
        self.home = self.base/'home'; self.home.mkdir()
        self.bin = self.base/'bin'; self.bin.mkdir()
        self.calls = self.base/'calls'
        for name, body in [('launchctl', 'exit 0\n'),
                           ('openclaw', 'echo "$*" >> "$BACKUP_TEST_CALLS"\n')]:
            path = self.bin/name
            path.write_text('#!/bin/sh\n'+body); path.chmod(0o755)
        self.db = self.home/'.openclaw/openclaw-weixin/ref-messages.sqlite'
        self.db.parent.mkdir(parents=True)
        self.env = dict(os.environ, HOME=str(self.home),
                        PATH=str(self.bin)+os.pathsep+os.environ['PATH'], BACKUP_TEST_CALLS=str(self.calls))
        (self.home/'.env').write_text('TEST_SECRET=fixture\n')

    def tearDown(self):
        self.temp.cleanup()

    def run_backup(self):
        return subprocess.run(['bash', str(ROOT/'components/openclaw/scripts/backup-state.sh')],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def test_wal_database_after_last_connection_closes_can_be_backed_up_and_restored(self):
        with sqlite3.connect(self.db) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE fixture (value TEXT)')
            db.execute("INSERT INTO fixture VALUES ('preserved')")
        db.close()
        proc = self.run_backup()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn('fixture', proc.stdout)
        batch = next((self.home/'.local/state/feipi-workbench/openclaw-backups').iterdir())
        self.assertEqual(json.loads((batch/'env-location.json').read_text())['source_home'], str(self.home))
        target = self.base/'restored'; target.mkdir()
        with tarfile.open(batch/'state.tar.gz') as archive:
            member = archive.getmember('.openclaw/openclaw-weixin/ref-messages.sqlite')
            (target/'state.sqlite').write_bytes(archive.extractfile(member).read())
        with sqlite3.connect(target/'state.sqlite') as restored:
            self.assertEqual(restored.execute('SELECT value FROM fixture').fetchall(), [('preserved',)])
            self.assertEqual(restored.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
        restored.close()
        self.assertEqual(self.calls.read_text().splitlines(), ['gateway stop --force', 'gateway start'])

    def test_corrupt_database_stops_backup_and_resumes_gateway(self):
        self.db.write_bytes(b'corrupt database')
        proc = self.run_backup()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('SQLite 停写检查失败', proc.stderr)
        self.assertEqual(self.db.read_bytes(), b'corrupt database')
        self.assertEqual(self.calls.read_text().splitlines(), ['gateway stop --force', 'gateway start'])
        self.assertFalse(list((self.home/'.local/state/feipi-workbench/openclaw-backups').glob('*/state.tar.gz')))


if __name__ == '__main__':
    unittest.main()
