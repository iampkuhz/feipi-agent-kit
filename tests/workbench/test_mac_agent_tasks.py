"""真实子进程覆盖 CLI 假成功、失败隔离和私有产物保全。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT/'components/mac/bootstrap/verify-agents.py'


class AgentTasks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi agent tasks ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base/'home'; self.home.mkdir()
        self.bin = self.base/'bin'; self.bin.mkdir()
        versions = json.loads((ROOT/'components/mac/config/cli-versions.json').read_text())
        for name in ('qwen', 'claude'):
            program = self.bin/name
            program.write_text('''#!/usr/bin/env python3
import os, pathlib, sys
if '--version' in sys.argv:
    print(VERSION)
elif pathlib.Path(sys.argv[0]).name == 'qwen':
    print('{"is_error": false, "result": "Connection error: fixture_secret"}')
elif os.environ.get('TEST_PROOF_SYMLINK'):
    pathlib.Path('proof.txt').symlink_to(os.environ['TEST_PROOF_SYMLINK'])
else:
    pathlib.Path('proof.txt').write_bytes(b'FEIPI_NEW_MAC_OK\\n')
'''.replace('VERSION', repr(versions[name]['version'])))
            program.chmod(0o755)

    def verify(self, names, extra=None):
        env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin)+os.pathsep+os.environ['PATH'])
        env.update(extra or {})
        result = subprocess.run([sys.executable, str(VERIFY),
                                 *[part for name in names for part in ('--cli', name)]],
                                env=env, text=True, capture_output=True, timeout=30)
        reports = list((self.home/'.local/state/feipi-workbench/validation').glob('agent-tasks-*/report.json'))
        self.assertEqual(len(reports), 1, result.stderr)
        self.assertNotIn('fixture_secret', result.stdout+result.stderr)
        self.assertEqual(reports[0].stat().st_mode & 0o777, 0o600)
        return result, json.loads(reports[0].read_text())

    def test_zero_exit_without_artifact_fails_and_next_cli_still_runs(self):
        result, report = self.verify(['qwen', 'claude'])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report['checks']['qwen']['exit_code'], 0)
        self.assertFalse(report['checks']['qwen']['proof_matches'])
        self.assertFalse(report['checks']['qwen']['passed'])
        self.assertTrue(report['checks']['claude']['passed'])
        self.assertNotEqual(report['checks']['qwen']['workspace'], report['checks']['claude']['workspace'])

    def test_symlink_to_existing_correct_file_does_not_count_as_new_artifact(self):
        existing = self.base/'existing-proof'; existing.write_bytes(b'FEIPI_NEW_MAC_OK\n')
        result, report = self.verify(['claude'], {'TEST_PROOF_SYMLINK': str(existing)})
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['checks']['claude']['passed'])
        self.assertEqual(existing.read_bytes(), b'FEIPI_NEW_MAC_OK\n')
