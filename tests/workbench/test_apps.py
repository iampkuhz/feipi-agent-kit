"""隔离验证批量桌面安装的权限与清单边界。"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Applications(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi app boundary ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bin = self.base/'bin'
        self.bin.mkdir()
        self.log = self.base/'calls'
        self.entry = self.base/'apps.sh'
        omlx = self.base/'omlx keg'
        source = (ROOT/'components/mac/bootstrap/apps.sh').read_text()
        # 若将来重新引入系统 sudo，也必须走替身并立即报错。
        self.entry.write_text(source.replace('/usr/bin/sudo', 'sudo'))
        for name, body in {
            'uname': 'echo Darwin', 'id': 'echo "${TEST_UID:-501}"',
            'brew': '''echo "$*" >> "$TEST_LOG"
test "$HOMEBREW_NO_SUDO" = 1 || exit 97
if [ "$1" = --prefix ]; then
  test "$2" = jundot/omlx/omlx || exit 96
  echo "$HOME/omlx keg"
  exit 0
fi
case "$2" in
  check) test -f "$HOME/installed" || exit "${TEST_BREW_STATUS:-0}" ;;
  install) test "${TEST_INSTALL_STATUS:-0}" = 0 && touch "$HOME/installed" ;;
  list) echo temurin@25 ;;
esac''',
            'sudo': 'echo "sudo $*" >> "$TEST_LOG"; exit 98',
        }.items():
            target = self.bin/name
            target.write_text('#!/bin/sh\n'+body+'\n')
            target.chmod(0o755)
        for relative, body in {
            'bin/omlx': 'test "$1" = --version && echo 0.8.0',
            'libexec/bin/python': 'test "$*" = "-B -" || exit 95\ncat >/dev/null\nexit "${TEST_KERNEL_STATUS:-0}"',
        }.items():
            target = omlx/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('#!/bin/sh\n'+body+'\n')
            target.chmod(0o755)
        self.env = {'HOME': str(self.base), 'PATH': str(self.bin)+':/usr/bin:/bin',
                    'TEST_LOG': str(self.log), 'LC_ALL': 'C'}

    def cli(self, mode, **values):
        return subprocess.run(['/bin/bash', str(self.entry), mode], stdin=subprocess.DEVNULL,
                              env=dict(self.env, **values), capture_output=True, text=True, timeout=10)

    def test_root_is_rejected_without_calling_brew(self):
        result = self.cli('install', TEST_UID='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_check_never_installs_missing_applications(self):
        result = self.cli('check', TEST_BREW_STATUS='1')
        self.assertEqual(result.returncode, 1)
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), 1)
        self.assertIn('bundle check --no-upgrade --verbose --file', calls[0])

    def test_completed_install_verifies_omlx_without_launching_it(self):
        result = self.cli('install')
        self.assertEqual(result.returncode, 0, result.stderr)
        check, prefix, admin_list = self.log.read_text().splitlines()
        self.assertTrue(check.startswith('bundle check '))
        self.assertEqual(prefix, '--prefix jundot/omlx/omlx')
        self.assertTrue(admin_list.startswith('bundle list --cask --file'))
        self.assertTrue(admin_list.endswith('/Brewfile.apps.admin'))
        self.assertIn('oMLX 0.8.0', result.stdout)

    def test_missing_apps_install_without_sudo_and_admin_packages_are_only_listed(self):
        result = self.cli('install', TEST_BREW_STATUS='1', HOMEBREW_NO_SUDO='0')
        self.assertEqual(result.returncode, 0, result.stderr)
        first_check, install, final_check, prefix, admin_list = self.log.read_text().splitlines()
        self.assertTrue(install.startswith('bundle install --no-upgrade --verbose --file'))
        self.assertTrue(install.endswith('/Brewfile.apps'))
        self.assertEqual(first_check, final_check)
        self.assertEqual(prefix, '--prefix jundot/omlx/omlx')
        self.assertTrue(admin_list.startswith('bundle list --cask --file'))
        self.assertTrue(admin_list.endswith('/Brewfile.apps.admin'))
        self.assertIn('open "$(brew --caskroom sogouinput)"', result.stdout)

    def test_unavailable_kernel_reports_failure_even_when_bundle_is_satisfied(self):
        result = self.cli('install', TEST_KERNEL_STATUS='1')
        self.assertEqual(result.returncode, 1)
        self.assertIn('brew reinstall jundot/omlx/omlx --with-custom-kernel', result.stderr)
        check, prefix = self.log.read_text().splitlines()
        self.assertTrue(check.startswith('bundle check '))
        self.assertEqual(prefix, '--prefix jundot/omlx/omlx')

    def test_failed_install_does_not_retry_with_sudo(self):
        result = self.cli('install', TEST_BREW_STATUS='1', TEST_INSTALL_STATUS='1')
        self.assertEqual(result.returncode, 1)
        check, install = self.log.read_text().splitlines()
        self.assertTrue(check.startswith('bundle check '))
        self.assertTrue(install.startswith('bundle install '))


if __name__ == '__main__':
    unittest.main()
