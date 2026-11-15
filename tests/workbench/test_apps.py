"""桌面安装的零变更/无授权边界；真正一次授权安装另在干净 macOS 验收。"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Applications(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi app boundary ')
        self.base = Path(self.temp.name)
        self.bin = self.base/'bin'; self.bin.mkdir()
        self.log = self.base/'calls'
        for name, body in {
            'uname': 'echo Darwin', 'id': 'echo "${TEST_UID:-501}"',
            'brew': 'echo "$*" >> "$TEST_LOG"; exit "${TEST_BREW_STATUS:-0}"',
        }.items():
            target = self.bin/name
            target.write_text('#!/bin/sh\n'+body+'\n'); target.chmod(0o755)
        self.env = {'HOME':str(self.base), 'PATH':str(self.bin)+':/usr/bin:/bin',
                    'TEST_LOG':str(self.log), 'LC_ALL':'C'}

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, mode, **values):
        return subprocess.run(['/bin/bash', str(ROOT/'components/mac/bootstrap/apps.sh'), mode],
                              env=dict(self.env, **values), capture_output=True, text=True, timeout=10)

    def test_root_is_rejected_without_calling_brew(self):
        result = self.cli('install', TEST_UID='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_check_never_installs_missing_applications(self):
        result = self.cli('check', TEST_BREW_STATUS='1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)
        self.assertIn('bundle check --file', self.log.read_text())

    def test_completed_install_needs_no_authorization_or_reinstallation(self):
        result = self.cli('install')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)
        self.assertNotIn('bundle install', self.log.read_text())


if __name__ == '__main__':
    unittest.main()
