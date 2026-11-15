"""原生配置命令的编排与启动前检查；真实子进程均限制在独立 HOME。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PersonalProfile(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='multica personal profile ')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.binding = self.home/'.config/multica-selfhost/machine.json'
        self.binding.parent.mkdir(parents=True)
        self.binding.write_text(json.dumps({
            'schema': 1, 'role': 'primary', 'profile': 'personal', 'workspace_id': 'restored-workspace',
            'server_url': 'http://localhost:8080', 'app_url': 'http://localhost:3000',
            'device_name': 'new-machine', 'workspaces_root': str(self.home/'task workspaces'),
        }))
        self.target = self.home/'.multica/profiles/personal/config.json'
        self.calls = self.home/'native-calls.jsonl'
        self.launch_calls = self.home/'launch-calls'
        binary = self.home/'.local/bin/multica'; binary.parent.mkdir(parents=True)
        binary.write_text(f'#!{sys.executable}\n'+'''
import json, os, pathlib, sys
args=sys.argv[1:]
if args == ['--version']:
    print('multica '+os.environ.get('PERSONAL_TEST_VERSION','0.6.3')); sys.exit(0)
assert args[:4] == ['--profile','personal','config','set'], args
key,value=args[4:]
with pathlib.Path(os.environ['PERSONAL_TEST_CALLS']).open('a') as log: log.write(json.dumps(key)+'\\n')
if key == os.environ.get('PERSONAL_TEST_FAIL'): sys.exit(42)
target=pathlib.Path.home()/'.multica/profiles/personal/config.json'
target.parent.mkdir(parents=True,exist_ok=True)
current=json.loads(target.read_text()) if target.exists() else {}
current[key]=int(value) if key == 'max_concurrent_tasks' else (value == 'true' if key == 'disable_auto_update' else value)
target.write_text(json.dumps(current)); target.chmod(0o600)
''')
        binary.chmod(0o755)
        launch = binary.with_name('launchctl')
        launch.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$PERSONAL_TEST_LAUNCH"\n'
                          'if [ "$1" = print ]; then exit 1; fi\nexit 0\n')
        launch.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1',
                        PERSONAL_TEST_CALLS=str(self.calls), PERSONAL_TEST_LAUNCH=str(self.launch_calls),
                        PATH=str(binary.parent)+os.pathsep+os.defpath)

    def configure(self, *args):
        return subprocess.run([sys.executable, str(ROOT/'scripts/configure.py'), '--personal-profile', *args],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def startup(self, action):
        return subprocess.run([sys.executable, str(ROOT/'scripts/manage-runtime.py'), action],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def save_profile(self, value):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_text(json.dumps(value))

    def test_prepare_without_env_or_login_and_repeat_does_not_rewrite_profile(self):
        proc = self.configure(); self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(self.target.read_text()), {
            'server_url':'http://localhost:8080', 'app_url':'http://localhost:3000',
            'device_name':'new-machine', 'workspaces_root':str(self.home/'task workspaces'),
            'max_concurrent_tasks':1, 'disable_auto_update':True,
        })
        before = (self.target.read_bytes(), self.target.stat().st_mtime_ns)
        proc = self.configure(); self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.target.read_bytes(), self.target.stat().st_mtime_ns), before)
        self.assertEqual(len(self.calls.read_text().splitlines()), 6)
        self.assertFalse((self.home/'.env').exists())
        self.assertFalse((self.binding.parent/'server.env').exists())
        self.assertFalse((self.home/'Library').exists())

    def test_existing_native_login_and_other_native_settings_are_preserved(self):
        self.save_profile({'token':'mul_fixture-only', 'workspace_id':'restored-workspace', 'poll_interval':'5s'})
        proc = self.configure(); self.assertEqual(proc.returncode, 0, proc.stderr)
        value = json.loads(self.target.read_text())
        self.assertEqual(value['token'], 'mul_fixture-only')
        self.assertEqual(value['workspace_id'], 'restored-workspace')
        self.assertEqual(value['poll_interval'], '5s')
        self.assertNotIn('fixture', proc.stdout+proc.stderr)

    def test_foreign_server_or_incompatible_binary_does_not_modify_profile(self):
        self.save_profile({'server_url':'https://other.invalid', 'token':'mul_fixture-only'})
        before = self.target.read_bytes()
        proc = self.configure(); self.assertNotEqual(proc.returncode, 0)
        self.assertIn('未覆盖', proc.stderr)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse(self.calls.exists())
        self.target.unlink(); self.env['PERSONAL_TEST_VERSION'] = '0.6.30'
        proc = self.configure(); self.assertNotEqual(proc.returncode, 0)
        self.assertIn('固定基线不同', proc.stderr)
        self.assertFalse(self.target.exists())

    def test_partial_native_failure_can_be_retried_without_rewriting_completed_keys(self):
        self.env['PERSONAL_TEST_FAIL'] = 'device_name'
        proc = self.configure(); self.assertNotEqual(proc.returncode, 0)
        self.assertIn('device_name', proc.stderr)
        self.env.pop('PERSONAL_TEST_FAIL')
        proc = self.configure(); self.assertEqual(proc.returncode, 0, proc.stderr)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls.count('server_url'), 1)
        self.assertEqual(calls.count('app_url'), 1)
        self.assertEqual(calls.count('device_name'), 2)

    def test_service_secret_arguments_cannot_be_mixed_with_personal_configuration(self):
        proc = self.configure('--init-secrets')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('不与服务密钥参数混用', proc.stderr)
        self.assertFalse(self.calls.exists())

    def test_startup_refuses_incomplete_profile_before_writing_or_calling_launchctl(self):
        self.assertEqual(self.configure().returncode, 0)
        ready = json.loads(self.target.read_text())
        ready.update(token='mul_fixture-only', workspace_id='restored-workspace')
        for changed in ({'token':''}, {'workspace_id':'other'}, {'max_concurrent_tasks':3},
                        {'disable_auto_update':False}, {'server_url':'http://other.invalid'}):
            for action in ('install', 'start'):
                with self.subTest(changed=changed, action=action):
                    self.save_profile(dict(ready, **changed))
                    proc = self.startup(action)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn('本机 profile 尚未就绪', proc.stderr)
                    self.assertNotIn('mul_fixture', proc.stdout+proc.stderr)
                    self.assertFalse(self.launch_calls.exists())
                    self.assertFalse((self.home/'Library/LaunchAgents').exists())

    def test_ready_profile_allows_existing_install_entry(self):
        self.assertEqual(self.configure().returncode, 0)
        current = json.loads(self.target.read_text())
        current.update(token='mul_fixture-only', workspace_id='restored-workspace')
        self.save_profile(current)
        before = self.target.read_bytes()
        proc = self.startup('install'); self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.home/'Library/LaunchAgents/local.multica.personal.plist').is_file())
        self.assertIn('bootstrap', self.launch_calls.read_text())
        self.assertEqual(self.target.read_bytes(), before)

    def test_stop_remains_available_without_binding_or_login(self):
        self.binding.unlink()
        proc = self.startup('stop'); self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.launch_calls.read_text().splitlines()[0].split()[0], 'bootout')


if __name__ == '__main__':
    unittest.main()
