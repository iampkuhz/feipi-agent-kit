"""运行发布在隔离 HOME 验证；验证发布与清理边界。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Publication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        for name in ['scripts', 'config', 'bin']:
            (self.source / name).mkdir(parents=True)
        self.script = self.source / 'scripts/install-runtime.py'
        shutil.copy2(ROOT / 'scripts/install-runtime.py', self.script)
        (self.source / 'config/other.json').write_text('{}')
        (self.source / 'config/managed.json').write_text('{"version": 1}')
        (self.source / 'bin/test-worker').write_text('#!/bin/sh\nexit 0\n')
        self.home = self.root / 'home'
        (self.home / '.local/bin').mkdir(parents=True)
        self.target = self.home / '.local/share/multica/ops'

    def tearDown(self):
        self.temp.cleanup()

    def publish(self, *args):
        return subprocess.run([sys.executable, str(self.script), *args],
                              env=dict(os.environ, HOME=str(self.home)), capture_output=True, text=True)

    def test_scoped_update_preserves_other_installed_files(self):
        self.assertEqual(self.publish().returncode, 0)
        before = (self.target / 'config/other.json').read_bytes()
        (self.source / 'config/managed.json').write_text('{"version": 2}')
        result = self.publish('--only', 'config/managed.json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.target / 'config/managed.json').read_text())['version'], 2)
        self.assertEqual((self.target / 'config/other.json').read_bytes(), before)
        self.assertTrue((self.home / '.local/bin/test-worker').is_symlink())

    def test_fresh_home_does_not_require_an_existing_local_bin(self):
        (self.home / '.local/bin').rmdir()
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / '.local/bin/test-worker').is_symlink())
        self.assertEqual((self.home / '.local/bin').stat().st_mode & 0o777, 0o700)

    def test_scoped_update_refuses_runtime_drift(self):
        self.assertEqual(self.publish().returncode, 0)
        (self.target / 'config/other.json').write_text('{"local": true}')
        result = self.publish('--only', 'config/managed.json')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('differs from installed manifest', result.stderr)

    def test_retired_command_removal_preserves_unrelated_commands(self):
        self.assertEqual(self.publish().returncode, 0)
        (self.source / 'bin/test-worker').unlink()
        unrelated = self.home / '.local/bin/other-worker'
        unrelated.write_text('private local command')
        result = self.publish('--remove', 'bin/test-worker')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.home / '.local/bin/test-worker').is_symlink())
        self.assertEqual(unrelated.read_text(), 'private local command')

    def test_scoped_update_rejects_paths_outside_managed_source(self):
        self.assertEqual(self.publish().returncode, 0)
        result = self.publish('--only', '../private')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exact managed source file', result.stderr)
