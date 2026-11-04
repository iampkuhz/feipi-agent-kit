"""运行发布在隔离 HOME 验证；监督逻辑不触碰真实容器或 launchd。"""
import importlib.util
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('supervised', ROOT / 'scripts/run-supervised.py')
supervised = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervised)


class Publication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        for name in ['scripts', 'config', 'bin']:
            (self.source / name).mkdir(parents=True)
        self.script = self.source / 'scripts/install-runtime.py'
        shutil.copy2(ROOT / 'scripts/install-runtime.py', self.script)
        (self.source / 'versions.json').write_text('{}')
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
        before = (self.target / 'versions.json').read_bytes()
        (self.source / 'config/managed.json').write_text('{"version": 2}')
        result = self.publish('--only', 'config/managed.json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.target / 'config/managed.json').read_text())['version'], 2)
        self.assertEqual((self.target / 'versions.json').read_bytes(), before)
        self.assertTrue((self.home / '.local/bin/test-worker').is_symlink())

    def test_scoped_update_refuses_runtime_drift(self):
        self.assertEqual(self.publish().returncode, 0)
        (self.target / 'versions.json').write_text('{"local": true}')
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


class Supervision(unittest.TestCase):
    def setUp(self):
        self.supervisor = supervised.Supervisor(
            {'role': 'primary', 'server_url': 'http://localhost:8000',
             'profile': 'personal', 'commands': {'multica': '/test/multica'}}, ROOT)

    def test_tick_keeps_exactly_one_daemon(self):
        child = Mock()
        child.poll.return_value = None
        with patch.object(self.supervisor, 'ensure_services'), patch.object(supervised.subprocess, 'Popen', return_value=child) as start, patch.object(supervised, 'log'):
            self.supervisor.tick()
            self.supervisor.tick()
        self.assertEqual(start.call_count, 1)

    def test_unready_services_cannot_start_a_daemon(self):
        with patch.object(self.supervisor, 'ensure_services', side_effect=supervised.Unavailable('not ready')), patch.object(supervised.subprocess, 'Popen') as start:
            with self.assertRaises(supervised.Unavailable):
                self.supervisor.tick()
            start.assert_not_called()

    def test_only_stopped_existing_containers_are_started(self):
        rows = [{'Service': name, 'State': 'running', 'Health': 'healthy'} for name in supervised.SERVICES]
        rows[-1]['Publishers'] = [{'TargetPort': 3000, 'PublishedPort': 3000, 'Protocol': 'tcp', 'URL': '127.0.0.1'}]
        stopped = [dict(row) for row in rows]
        stopped[0]['State'] = 'exited'
        with patch.object(supervised, 'command', side_effect=[json.dumps(stopped), '', json.dumps(rows)]) as command, patch.object(self.supervisor, 'ready') as ready, patch.object(supervised, 'log'):
            self.supervisor.ensure_services()
        self.assertEqual(command.call_args_list[1].args[0][1:], ['start', '--wait', '--wait-timeout', '60', 'postgres'])
        self.assertEqual(ready.call_count, 2)

    def test_missing_container_requires_explicit_setup(self):
        with patch.object(supervised, 'command', return_value='[]') as command:
            with self.assertRaisesRegex(supervised.Unavailable, 'Expected one existing'):
                self.supervisor.ensure_services()
        self.assertEqual(command.call_count, 1)

    def test_shared_engine_start_is_detached_from_launchagent(self):
        result = subprocess.CompletedProcess([], 0, stdout='', stderr='')
        with patch.object(supervised.subprocess, 'run', return_value=result) as command:
            supervised.command(['podman', 'machine', 'start', 'configured'])
            self.assertTrue(command.call_args.kwargs['start_new_session'])
            supervised.command(['/test/service', 'ps'])
            self.assertFalse(command.call_args.kwargs['start_new_session'])

    def test_stop_waits_for_launchagent_to_unload(self):
        results = [subprocess.CompletedProcess([], status) for status in [0, 0, 1]]
        with patch.object(sys, 'argv', ['manage-runtime.py', 'stop']), patch.object(subprocess, 'run', side_effect=results) as native, patch('time.sleep') as sleep:
            runpy.run_path(str(ROOT / 'scripts/manage-runtime.py'), run_name='__main__')
        self.assertEqual(native.call_count, 3)
        sleep.assert_called_once()


if __name__ == '__main__':
    unittest.main()
