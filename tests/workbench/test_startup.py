"""在隔离 HOME 中验证自启文件，不加载真实 LaunchAgent 或启停服务。"""
import importlib.util
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('workbench_startup', ROOT/'tools/runtime/startup.py')
startup = importlib.util.module_from_spec(spec)
# 工作台测试先前已导入同目录的 service_health；单独运行本文件也须可加载。
import sys
sys.path.insert(0, str(ROOT/'tools/runtime'))
spec.loader.exec_module(startup)


class Startup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi startup ')
        self.home = Path(self.temp.name)
        self.home_patch = patch.object(startup, 'HOME', self.home); self.home_patch.start()
        self.state_patch = patch.object(startup, 'STATE', self.home/'state'); self.state_patch.start()

    def tearDown(self):
        self.home_patch.stop(); self.state_patch.stop(); self.temp.cleanup()

    def test_install_writes_only_service_plists_without_requiring_env(self):
        with patch.object(startup, 'run') as run:
            startup.install()
        run.assert_not_called()
        agents = self.home/'Library/LaunchAgents'
        path = agents/(startup.SERVICE_LABEL+'.plist')
        self.assertEqual(list(agents.iterdir()), [path])
        self.assertEqual(plistlib.loads(path.read_bytes()), startup.definitions()[startup.SERVICE_LABEL])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.home/'.local/env-vault').exists())

    def test_start_retires_only_the_previous_workbench_vault_job(self):
        startup.install()
        path = self.home/'Library/LaunchAgents/com.local.envvault.plist'
        old = {'Label': 'com.local.envvault', 'ProgramArguments': ['/usr/bin/python3', str(Path(startup.__file__).resolve()), 'snapshot-env']}
        target = 'gui/'+str(os.getuid())+'/com.local.envvault'
        with patch.object(startup.subprocess, 'run') as status, patch.object(startup, 'run') as run:
            status.side_effect = lambda args, **kwargs: subprocess.CompletedProcess(args, 0 if args[-1] == target else 1)
            path.write_bytes(plistlib.dumps(old))
            startup.start()
            self.assertFalse(path.exists())
            self.assertIn(['launchctl', 'bootout', target], [call.args[0] for call in run.call_args_list])
            run.reset_mock()
            old['ProgramArguments'][1] = '/other/startup.py'
            path.write_bytes(plistlib.dumps(old))
            startup.start()
            self.assertTrue(path.is_file())
            self.assertNotIn(['launchctl', 'bootout', target], [call.args[0] for call in run.call_args_list])

    def test_installed_session_browser_gets_an_independent_loopback_job(self):
        launcher = self.home/'.local/bin/session-browser'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/sh\nexit 0\n'); launcher.chmod(0o700)
        with patch.object(startup, 'run') as run:
            startup.install()
        run.assert_not_called()
        path = self.home/'Library/LaunchAgents'/(startup.SESSION_BROWSER_LABEL+'.plist')
        actual = plistlib.loads(path.read_bytes())
        self.assertEqual(actual['ProgramArguments'],
                         [str(launcher), 'serve', '--host', '127.0.0.1', '--port', '8848'])
        self.assertNotIn('KeepAlive', actual)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with patch.object(startup.subprocess, 'run') as launchctl, \
                patch.object(startup, 'run') as load:
            launchctl.return_value.returncode = 1
            startup.start()
        self.assertEqual([call.args[0][-1].name for call in load.call_args_list],
                         [label+'.plist' for label in startup.definitions()])

    def test_absent_or_non_executable_session_browser_is_not_required(self):
        self.assertNotIn(startup.SESSION_BROWSER_LABEL, startup.definitions())
        launcher = self.home/'.local/bin/session-browser'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('not executable\n'); launcher.chmod(0o600)
        self.assertNotIn(startup.SESSION_BROWSER_LABEL, startup.definitions())

    def test_session_browser_drift_fails_before_loading_any_job(self):
        launcher = self.home/'.local/bin/session-browser'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/sh\nexit 0\n'); launcher.chmod(0o700)
        startup.install()
        path = self.home/'Library/LaunchAgents'/(startup.SESSION_BROWSER_LABEL+'.plist')
        data = plistlib.loads(path.read_bytes()); data['ProgramArguments'][-1] = '9999'
        path.write_bytes(plistlib.dumps(data))
        with patch.object(startup.subprocess, 'run') as launchctl, \
                patch.object(startup, 'run') as load, self.assertRaisesRegex(ValueError, 'session-browser'):
            startup.start()
        launchctl.assert_not_called(); load.assert_not_called()

    def test_start_refuses_drift_before_touching_loaded_jobs(self):
        startup.install()
        path = self.home/'Library/LaunchAgents'/(startup.SERVICE_LABEL+'.plist')
        data = plistlib.loads(path.read_bytes()); data['RunAtLoad'] = False
        path.write_bytes(plistlib.dumps(data))
        with patch.object(startup, 'run') as run, self.assertRaises(ValueError):
            startup.start()
        run.assert_not_called()

    def test_failed_service_does_not_prevent_independent_services_from_starting(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if any('litellm.sh' in str(item) for item in args):
                raise subprocess.CalledProcessError(1, 'litellm')
        with patch.object(startup, 'run', side_effect=run), \
                patch.object(startup, 'wait_service') as wait, self.assertRaisesRegex(ValueError, 'litellm'):
            startup.services()
        self.assertEqual([call.args[0] for call in wait.call_args_list], ['searxng', 'crawl4ai'])
        self.assertTrue(any('crawl4ai.sh' in str(item) for call in calls for item in call))


if __name__ == '__main__':
    unittest.main()
