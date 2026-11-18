"""裸机前置入口的离线边界；实际 Homebrew/CLT 冷安装另在干净 macOS 验收。"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Prerequisites(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi bare mac ')
        self.base = Path(self.temp.name)
        self.home = self.base/'home'; self.home.mkdir()
        self.bin = self.base/'bin'; self.bin.mkdir()
        self.scratch = self.base/'scratch'; self.scratch.mkdir()
        self.log = self.base/'calls'
        fixtures = {
            'uname': 'echo Darwin', 'id': 'echo "${TEST_UID:-501}"',
            'xcode-select': 'exit "${TEST_CLT_MISSING:-0}"', 'xcrun': 'exit 0',
            'python3': 'exit 0', 'git': 'exit 0',
            'brew': '''if [ "$1" = shellenv ]; then
  echo shellenv >> "$TEST_LOG"
  printf 'export PATH="%s"\n' "${TEST_BREW_BIN:+$TEST_BREW_BIN:}$PATH"
elif [ "$1" = bundle ]; then
  printf '%s\n' "$*" >> "$TEST_LOG"
else exit 97; fi''',
            'curl': 'echo forbidden-network >> "$TEST_LOG"; exit 99',
            'sudo': 'echo forbidden-sudo >> "$TEST_LOG"; exit 99',
        }
        for name, body in fixtures.items():
            path = self.bin/name
            path.write_text('#!/bin/sh\n'+body+'\n'); path.chmod(0o755)
        self.env = {'HOME': str(self.home), 'PATH': str(self.bin)+':/usr/bin:/bin',
                    'TMPDIR': str(self.scratch), 'TEST_LOG': str(self.log), 'LC_ALL': 'C'}

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, action, **values):
        return subprocess.run(['/bin/bash', str(ROOT/'scripts/bootstrap/prerequisites.sh'), action],
                              env=dict(self.env, **values), capture_output=True, text=True, timeout=10)

    def test_check_reports_missing_clt_without_installation(self):
        proc = self.cli('check', TEST_CLT_MISSING='1')
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_check_uses_homebrew_python_before_older_system_python(self):
        (self.bin/'python3').write_text('#!/bin/sh\nexit 1\n')
        brew_bin = self.base/'homebrew bin'; brew_bin.mkdir()
        python = brew_bin/'python3'
        python.write_text('#!/bin/sh\necho checked-homebrew-python >> "$TEST_LOG"\n')
        python.chmod(0o755)

        proc = self.cli('check', TEST_BREW_BIN=str(brew_bin))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.log.read_text(), 'shellenv\nchecked-homebrew-python\n')
        self.assertFalse(list(self.scratch.iterdir()))
        self.assertFalse(list(self.home.iterdir()))

    def test_check_stops_when_homebrew_environment_fails(self):
        (self.bin/'brew').write_text('#!/bin/sh\nexit 44\n')
        (self.bin/'python3').write_text('#!/bin/sh\necho unexpected >> "$TEST_LOG"\n')
        proc = self.cli('check')
        self.assertEqual(proc.returncode, 44, proc.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse(list(self.scratch.iterdir()))

    def test_root_is_rejected_before_installation(self):
        proc = self.cli('install', TEST_UID='0')
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_existing_brew_path_uses_no_upgrade_bundle_and_cleans_temp(self):
        proc = self.cli('install')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('bundle install --no-upgrade --file', self.log.read_text())
        self.assertNotIn('forbidden', self.log.read_text())
        self.assertFalse(list(self.scratch.iterdir()))
        self.assertFalse(list(self.home.iterdir()))


if __name__ == '__main__':
    unittest.main()
