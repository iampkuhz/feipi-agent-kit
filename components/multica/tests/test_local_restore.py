"""通过组件恢复脚本验证小配置恢复；数据卷、登录和项目目录均不参与。"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
COMPONENT = ROOT/'components/multica'
sys.path.insert(0, str(COMPONENT/'scripts'))
spec = importlib.util.spec_from_file_location('multica_backup', COMPONENT/'scripts/backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class LocalRestore(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='multica local restore ')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base/'new home'; self.home.mkdir()
        self.batch = self.base/'backup'; self.batch.mkdir()
        self.target = self.home/'.config/multica-selfhost'
        self.bin = self.base/'bin'; self.bin.mkdir()
        self.executable(self.bin/'python3', link=Path(sys.executable))
        self.executable(self.bin/'podman', 'printf "%s\\n" "$PODMAN_ROWS"\n')
        self.executable(self.home/'.local/bin/multica')
        # 保留 nvm 的入口目录；不能 resolve 到 symlink 指向的 codex.js。
        self.codex = self.home/'.nvm/versions/node/v24/bin/codex'
        payload = self.base/'codex.js'; self.executable(payload)
        self.executable(self.codex, link=payload)
        self.docker = self.home/'brew/bin/docker'; self.executable(self.docker)
        self.plugin = self.home/'brew/lib/docker/cli-plugins/docker-compose'
        self.executable(self.plugin)
        self.private_docker = self.home/'.docker/config.json'
        self.private_docker.parent.mkdir()
        self.private_docker.write_text(json.dumps({'auths': {'example.invalid': {'auth': 'fixture-only'}}}))
        self.env = dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1',
                        PATH=os.pathsep.join(map(str, (self.bin, self.codex.parent, self.docker.parent)))+os.pathsep+os.defpath,
                        PODMAN_ROWS='[]')
        self.server = b'JWT_SECRET=fixture-jwt\nPOSTGRES_PASSWORD=fixture-db\nMULTICA_VCS_SECRET_KEY=fixture-vcs\nCUSTOM_SETTING=preserve\n'
        (self.home/'.env').write_text('MULTICA_SELFHOST_JWT_SECRET=fixture-jwt\n'
                                    'MULTICA_SELFHOST_POSTGRES_PASSWORD=fixture-db\n'
                                    'MULTICA_VCS_SECRET_KEY=fixture-vcs\n')
        self.machine = {
            'schema': 1, 'role': 'primary', 'profile': 'personal', 'workspace_id': 'logical-workspace',
            'daemon_id': 'old-device', 'device_name': 'old-machine', 'agent_kit': '/Users/old/old-kit',
            'server_url': 'http://localhost:8080', 'app_url': 'http://127.0.0.1:3000',
            'workspaces_root': '/Users/old/multica_workspaces',
            'openclaw_source': '/Users/old/old-kit/openclaw.json', 'openclaw_state': '~/.openclaw-multica',
            'runtimes': {'codex': {'id': 'old-runtime', 'provider': 'codex', 'profile_id': 'logical-profile'}},
            'agents': {'coder': {'id': 'logical-agent'}}, 'protected_skill_ids': ['logical-skill'],
            'projects': {'project': {'root': '/Users/old/Documents/project', 'id': 'logical-project',
                                     'resource_id': 'logical-resource', 'release': {'keep': True}}},
            'commands': {'multica': '/old/bin/multica', 'codex': '/opt/homebrew/bin/codex'},
            'startup': {'podman_machine': 'old-machine', 'other_setting': 'keep'},
        }
        (self.batch/'source-home.json').write_text(json.dumps({'schema': 1, 'source_home': '/Users/old'}))
        (self.batch/'server.env').write_bytes(self.server)
        shutil.copyfile(COMPONENT/'versions.json', self.batch/'versions.json')
        shutil.copyfile(COMPONENT/'config/compose.pinned.yml', self.batch/'compose.pinned.yml')
        self.seal()

    def executable(self, path, body='exit 71\n', link=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        if link:
            path.symlink_to(link)
        else:
            path.write_text('#!/bin/sh\n'+body); path.chmod(0o755)

    def seal(self):
        (self.batch/'machine.reference.json').write_text(json.dumps(self.machine))
        checks = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.batch.iterdir() if path.name != 'SHA256SUMS.json'}
        # 不存在的数据文件不会被小配置恢复读取；完整数据恢复另行验证。
        checks['database.dump'] = 'invalid-data-fixture'
        (self.batch/'SHA256SUMS.json').write_text(json.dumps(checks))

    def run_restore(self):
        return subprocess.run([sys.executable, str(COMPONENT/'scripts/restore-local.py'),
                               str(self.batch), '--agent-kit', str(ROOT)],
                              env=self.env, cwd=self.base, capture_output=True, text=True, timeout=30)

    def assert_failed(self, message):
        proc = self.run_restore()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(message, proc.stderr)
        self.assertNotIn('Traceback', proc.stderr)
        self.assertFalse(self.target.exists())
        return proc

    def test_real_entry_rebuilds_local_paths_preserves_logical_ids_and_clears_device_ids(self):
        private_before = self.private_docker.read_bytes()
        proc = self.run_restore()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        value = json.loads((self.target/'machine.json').read_text())
        self.assertEqual(value['workspaces_root'], str(self.home/'multica_workspaces'))
        self.assertEqual(value['openclaw_state'], str(self.home/'.openclaw-multica'))
        self.assertEqual(value['openclaw_source'], str(ROOT/'components/openclaw/openclaw.json'))
        self.assertEqual(value['agent_kit'], str(ROOT))
        self.assertEqual(value['workspace_id'], 'logical-workspace')
        self.assertEqual(value['agents'], self.machine['agents'])
        self.assertEqual(value['protected_skill_ids'], ['logical-skill'])
        expected_project = dict(self.machine['projects']['project'], root=str(self.home/'Documents/project'))
        self.assertEqual(value['projects']['project'], expected_project)
        self.assertIsNone(value['daemon_id'])
        self.assertEqual(value['runtimes']['codex'], {'id': None, 'provider': 'codex', 'profile_id': 'logical-profile'})
        self.assertEqual(value['commands']['codex'], str(self.codex))
        self.assertEqual(value['commands']['multica'], str(self.home/'.local/bin/multica'))
        self.assertEqual(value['startup'], {'podman_machine': 'podman-machine-default', 'other_setting': 'keep'})
        self.assertEqual((self.target/'server.env').read_bytes(), self.server)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        for name in ('machine.json', 'server.env', 'docker-public/config.json'):
            self.assertEqual((self.target/name).stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads((self.target/'docker-public/config.json').read_text()),
                         {'auths': {}, 'cliPluginsExtraDirs': [str(self.plugin.parent)]})
        self.assertEqual(self.private_docker.read_bytes(), private_before)
        for name in ('Documents/project', '.multica', 'Library/LaunchAgents', '.local/state/multica'):
            self.assertFalse((self.home/name).exists(), name)

    def test_existing_default_machine_and_external_mount_are_preserved(self):
        self.env['PODMAN_ROWS'] = '[{"Name":"new-default","Default":true}]'
        self.machine['projects']['project']['root'] = '/Volumes/shared/project'
        self.seal()
        proc = self.run_restore(); self.assertEqual(proc.returncode, 0, proc.stderr)
        value = json.loads((self.target/'machine.json').read_text())
        self.assertEqual(value['startup']['podman_machine'], 'new-default')
        self.assertEqual(value['projects']['project']['root'], '/Volumes/shared/project')

    def test_repeat_rejects_existing_configuration(self):
        self.assertEqual(self.run_restore().returncode, 0)
        before = (self.target/'machine.json').read_bytes()
        repeated = self.run_restore()
        self.assertNotEqual(repeated.returncode, 0)
        self.assertIn('未覆盖', repeated.stderr)
        self.assertEqual((self.target/'machine.json').read_bytes(), before)

    def test_corrupt_control_file_fails_before_writing(self):
        (self.batch/'server.env').write_bytes(b'corrupted')
        self.assert_failed('校验失败：server.env')

    def test_old_batch_without_source_home_requires_regeneration(self):
        (self.batch/'source-home.json').unlink()
        self.assert_failed('用当前入口重新备份')

    def test_mismatched_vault_does_not_print_or_replace_keys(self):
        (self.home/'.env').write_text('MULTICA_VCS_SECRET_KEY=wrong-fixture\n')
        proc = self.assert_failed('同批服务密钥')
        self.assertNotIn('fixture', proc.stdout+proc.stderr)

    def test_parent_symlink_is_rejected(self):
        outside = self.base/'outside'; outside.mkdir()
        (self.home/'.config').symlink_to(outside, target_is_directory=True)
        self.assert_failed('父路径冲突')
        self.assertEqual(list(outside.iterdir()), [])

    def test_malformed_json_structures_fail_cleanly_before_writing(self):
        for key in ('startup', 'runtimes', 'projects'):
            with self.subTest(key=key):
                before = self.machine[key]
                self.machine[key] = [] if key == 'startup' else {'invalid': []}
                self.seal(); self.assert_failed('无效')
                self.machine[key] = before
        self.seal()
        (self.batch/'source-home.json').write_text('[]'); self.seal()
        self.assert_failed('原 HOME 记录无效')

    def test_missing_native_cli_fails_before_writing(self):
        (self.home/'.local/bin/multica').unlink()
        self.assert_failed('缺少新机程序入口：multica')

    def test_ambiguous_or_malformed_podman_list_fails_before_writing(self):
        for rows in ('{}', '[null]', '[{"Name":"a","Default":true},{"Name":"b","Default":true}]'):
            with self.subTest(rows=rows):
                self.env['PODMAN_ROWS'] = rows
                self.assert_failed('Podman')

    def test_remote_service_address_fails_before_writing(self):
        self.machine['server_url'] = 'https://old-machine.invalid'
        self.seal(); self.assert_failed('不是本机回环地址')


class BackupHomeMetadata(unittest.TestCase):
    def test_native_backup_records_source_home_inside_verified_manifest(self):
        with tempfile.TemporaryDirectory(prefix='multica backup metadata ') as directory:
            home = Path(directory).resolve()
            config = home/'.config/multica-selfhost'; config.mkdir(parents=True)
            (config/'server.env').write_text('JWT_SECRET=fixture\n')
            binding = {'schema': 1, 'device_name': 'old-host', 'daemon_id': 'old-daemon',
                       'runtimes': {'codex': {'id': 'old-runtime', 'provider': 'codex'}},
                       'startup': {'podman_machine': 'old-vm'}, 'workspace_id': 'workspace'}
            (config/'machine.json').write_text(json.dumps(binding))
            published = home/'.local/share/multica/ops'; published.mkdir(parents=True)
            (published/'fixture.py').write_bytes(b'# published fixture\n')
            (published/'installed-files.json').write_text(json.dumps(
                {'fixture.py': hashlib.sha256((published/'fixture.py').read_bytes()).hexdigest()}))

            def run(args, **kwargs):
                if 'pg_dump' in args:
                    kwargs['stdout'].write(b'fixture-dump')
                return subprocess.CompletedProcess(args, 0)

            def output(args, **kwargs):
                return '' if 'ps' in args else '0\n'

            with patch.dict(os.environ, {'HOME': str(home)}), patch.object(sys, 'argv', ['backup.py', '--apply']), \
                    patch.object(backup, 'machine', side_effect=lambda: json.loads((config/'machine.json').read_text())), \
                    patch.object(backup, 'cli', side_effect=lambda *args: {'status':'stopped'} if args[0] == 'daemon' else []), \
                    patch.object(backup.subprocess, 'run', side_effect=run), \
                    patch.object(backup.subprocess, 'check_output', side_effect=output), \
                    contextlib.redirect_stdout(io.StringIO()):
                backup.main()
                batch = next((home/'.local/state/multica/backups').iterdir())
                backup.verify(batch)
            metadata = batch/'source-home.json'
            self.assertEqual(json.loads(metadata.read_text()), {'schema':1, 'source_home':str(home)})
            self.assertEqual(metadata.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads((batch/'SHA256SUMS.json').read_text())[metadata.name],
                             hashlib.sha256(metadata.read_bytes()).hexdigest())
            reference = json.loads((batch/'machine.reference.json').read_text())
            self.assertEqual(reference, {'schema': 1, 'runtimes': {'codex': {'provider': 'codex'}},
                                         'startup': {}, 'workspace_id': 'workspace'})
            self.assertEqual(json.loads((config/'machine.json').read_text()), binding)


if __name__ == '__main__':
    unittest.main()
