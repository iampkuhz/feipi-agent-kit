"""自启文件和 env 本地历史；隔离 HOME，不加载真实 LaunchAgent 或启停服务。"""
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
        self.vault = self.home/'.local/env-vault'; self.vault.mkdir(parents=True)
        self.source = self.vault/'.env'; self.source.write_text('TOKEN=fixture-one\n')
        (self.home/'.env').symlink_to(self.source)
        self.home_patch = patch.object(startup, 'HOME', self.home); self.home_patch.start()
        self.state_patch = patch.object(startup, 'STATE', self.home/'state'); self.state_patch.start()

    def tearDown(self):
        self.home_patch.stop(); self.state_patch.stop(); self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.vault), *args], text=True).strip()

    def test_snapshots_are_private_idempotent_and_preserve_unrelated_staging(self):
        startup.snapshot_env()
        first = self.git('rev-parse', 'HEAD')
        startup.snapshot_env()
        self.assertEqual(self.git('rev-parse', 'HEAD'), first)
        (self.vault/'unrelated').write_text('keep staged\n')
        self.git('add', 'unrelated')
        self.source.write_text('TOKEN=fixture-two\n')
        startup.snapshot_env()
        self.assertNotEqual(self.git('rev-parse', 'HEAD'), first)
        self.assertEqual(self.git('diff', '--cached', '--name-only'), 'unrelated')
        self.assertEqual((self.vault/'env').read_text(), self.source.read_text())
        self.assertEqual((self.vault/'env').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.vault.stat().st_mode & 0o777, 0o700)

    def test_git_environment_cannot_redirect_snapshot_into_business_repository(self):
        other = self.home/'business'; other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        with patch.dict(os.environ, {'GIT_DIR': str(other/'.git'), 'GIT_WORK_TREE': str(other)}):
            startup.snapshot_env()
        self.assertTrue((self.vault/'.git').is_dir())
        self.assertFalse((other/'env').exists())
        self.assertFalse((other/'.git/index').exists())

    def test_install_only_writes_native_plists_without_loading(self):
        with patch.object(startup, 'run') as run:
            startup.install()
        run.assert_not_called()
        for label in startup.LABELS:
            path = self.home/'Library/LaunchAgents'/(label+'.plist')
            self.assertEqual(plistlib.loads(path.read_bytes()), startup.definitions()[label])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        definition = startup.definitions()['com.local.envvault']
        self.assertEqual(definition['StartInterval'], 300)
        self.assertNotIn('KeepAlive', definition)

    def test_missing_env_fails_before_installing_any_plist(self):
        (self.home/'.env').unlink()
        with self.assertRaises(ValueError):
            startup.install()
        self.assertFalse((self.home/'Library').exists())

    def test_start_refuses_drift_before_touching_loaded_jobs(self):
        startup.install()
        path = self.home/'Library/LaunchAgents/com.local.envvault.plist'
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
