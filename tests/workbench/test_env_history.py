import importlib.util
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2]/'components/mac/bootstrap/env-history.py'
spec = importlib.util.spec_from_file_location('env_history', SCRIPT)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


class EnvHistory(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.home = Path(self.scratch.name).resolve()/'新用户'
        self.home.mkdir()
        self.repo = self.home/'.local/state/feipi-workbench/env-history.git'

    def snapshot(self):
        result = subprocess.run([sys.executable, SCRIPT], check=True, capture_output=True,
                                env=dict(os.environ, HOME=str(self.home), GIT_DIR=str(self.home/'other.git')))
        self.assertEqual(result.stdout + result.stderr, b'')

    def git(self, *args):
        return subprocess.check_output(['git', '--git-dir='+str(self.repo), *args])

    def test_records_distinct_versions_without_worktree_or_remote(self):
        self.snapshot()
        self.assertFalse(self.repo.exists())
        source = self.home/'.env'
        target = self.home/'env-vault'
        target.write_bytes(b'TEST_VALUE=first\n')
        source.symlink_to(target)
        self.snapshot()
        self.snapshot()
        replacement = self.home/'env-new'
        replacement.write_bytes(b'TEST_VALUE=second\n')
        replacement.replace(target)
        self.snapshot()
        source.unlink()
        self.snapshot()
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), b'2\n')
        self.assertEqual(self.git('show', 'HEAD~1:.env'), b'TEST_VALUE=first\n')
        self.assertEqual(self.git('show', 'HEAD:.env'), b'TEST_VALUE=second\n')
        self.assertEqual(self.git('ls-tree', '--name-only', 'HEAD'), b'.env\n')
        self.assertEqual(self.git('remote'), b'')
        self.assertEqual(self.git('config', '--local', '--get', 'protocol.allow'), b'never\n')
        self.assertEqual(self.repo.stat().st_mode & 0o777, 0o700)
        self.assertFalse((self.home/'other.git').exists())
        self.assertFalse((self.repo/'.env').exists())

    def test_install_writes_schedule_even_without_env_and_loads_it_once(self):
        domain = 'gui/'+str(os.getuid())
        label = domain+'/'+history.LABEL
        calls = []

        def launch(args, **kwargs):
            calls.append(args)
            if args[1:3] == ['print', label]:
                status = 0 if any(command[1] == 'bootstrap' for command in calls) else 1
            else:
                status = 0
            return subprocess.CompletedProcess(args, status)

        with patch.object(history.subprocess, 'run', side_effect=launch):
            history.install(self.home, SCRIPT)
            history.install(self.home, SCRIPT)
        plist = self.home/'Library/LaunchAgents'/(history.LABEL+'.plist')
        definition = plistlib.loads(plist.read_bytes())
        self.assertEqual(definition['ProgramArguments'][1:], [str(SCRIPT)])
        self.assertEqual(definition['WatchPaths'], [str(self.home/'.env')])
        self.assertTrue(definition['RunAtLoad'])
        self.assertEqual(definition['StartInterval'], 60)
        self.assertEqual([args[1:] for args in calls if args[1] != 'print'], [['bootstrap', domain, str(plist)]])
        self.assertFalse(self.repo.exists())
