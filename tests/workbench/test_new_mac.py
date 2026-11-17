"""分阶段部署的失败边界；只使用隔离 HOME、离线替身和合成数据库输入。"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('new_mac', ROOT/'scripts/workbench/new_mac.py')
mac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mac)


class Stages(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi new mac stages ')
        self.home = Path(self.temp.name)/'home'; self.home.mkdir()
        state = self.home/'.local/state/feipi-workbench'
        self.paths = patch.multiple(mac, HOME=self.home, STATE=state, BUNDLE=self.home/'feipi-mac-private',
                                    RESTORE=self.home/'feipi-restore',
                                    RECEIPT=state/'new-mac-backups.json')
        self.paths.start()
        self.quiet = patch.object(mac, 'done'); self.quiet.start()

    def tearDown(self):
        self.quiet.stop(); self.paths.stop(); self.temp.cleanup()

    def dump(self, component):
        path = mac.RESTORE/component/'database.dump'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'synthetic database')
        return path

    def test_software_failure_stops_before_apply_and_editor(self):
        with patch.object(mac, 'wb', side_effect=subprocess.CalledProcessError(42, 'install')) as wb, \
                patch.object(mac, 'run') as run:
            with self.assertRaises(subprocess.CalledProcessError):
                mac.software()
        self.assertEqual(wb.call_count, 1)
        run.assert_not_called()

    def test_corrupt_config_stops_before_restore_or_apply(self):
        with patch.object(mac, 'wb', side_effect=ValueError('checksum')) as wb:
            with self.assertRaises(ValueError):
                mac.config()
        self.assertEqual(wb.call_args.args[:2], ('private', 'verify-mac'))
        self.assertEqual(wb.call_count, 1)

    def test_receive_refuses_existing_bundle_before_remote_access(self):
        mac.BUNDLE.mkdir()
        with patch.object(mac, 'run') as run, patch.object(mac, 'remote_exists') as exists:
            with self.assertRaises(ValueError):
                mac.receive('me@192.0.2.1')
        run.assert_not_called(); exists.assert_not_called()

    def test_missing_optional_data_is_skipped_without_creating_targets(self):
        with patch.object(mac, 'remote_exists', return_value=False), patch.object(mac, 'run') as run:
            with patch('builtins.print'):
                mac.copy_data('me@192.0.2.1')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_data_copy_uses_only_allowlist_and_never_delete(self):
        with patch.object(mac, 'remote_exists', side_effect=lambda _, name, __: name == '.omlx/models'), \
                patch.object(mac, 'run') as run, patch('builtins.print'):
            mac.copy_data('me@192.0.2.1')
        copies = [call.args[0] for call in run.call_args_list if call.args[0][0] == 'rsync']
        self.assertEqual(len(copies), 1)
        self.assertIn('me@192.0.2.1:.omlx/models/', copies[0])
        self.assertNotIn('--delete', copies[0])

    def test_ssh_failure_is_not_treated_as_missing_optional_data(self):
        with patch.object(mac.subprocess, 'run', return_value=subprocess.CompletedProcess([], 255)):
            with self.assertRaises(subprocess.CalledProcessError):
                mac.remote_exists('me@host', '.omlx/models', 'd')

    def test_interrupted_config_receive_does_not_publish_partial_bundle(self):
        def fake_run(args, **kwargs):
            if args[0] == 'scp':
                (Path(args[-1])/'feipi-mac-private').mkdir()
                raise subprocess.CalledProcessError(42, args)
        with patch.object(mac, 'remote_exists', return_value=False), \
                patch.object(mac, 'run', side_effect=fake_run), patch.object(mac, 'wb'):
            with self.assertRaises(subprocess.CalledProcessError):
                mac.receive('me@192.0.2.1')
        self.assertFalse(mac.BUNDLE.exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_receive_preserves_proxy_backup_already_used_for_network_setup(self):
        proxy = self.home/'FlClash-backup.zip'; proxy.write_bytes(b'existing backup')
        def fake_run(args, **kwargs):
            if args[0] == 'scp':
                self.assertEqual(args[-2], 'me@192.0.2.1:feipi-mac-private')
                (Path(args[-1])/'feipi-mac-private').mkdir()
        with patch.object(mac, 'remote_exists', return_value=True), \
                patch.object(mac, 'run', side_effect=fake_run), patch.object(mac, 'wb'), patch('builtins.print'):
            mac.receive('me@192.0.2.1')
        self.assertTrue(mac.BUNDLE.is_dir())
        self.assertEqual(proxy.read_bytes(), b'existing backup')

    def test_remote_option_and_shell_injection_are_rejected(self):
        for value in ('-oProxyCommand=bad', 'me@host;touch /tmp/bad', 'me@host path'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mac.remote(value)
        self.assertEqual(mac.remote('me@192.0.2.1'), 'me@192.0.2.1')

    def test_backup_failure_keeps_previous_receipt_and_stops(self):
        mac.RECEIPT.parent.mkdir(parents=True); mac.RECEIPT.write_text('old batch')
        with patch.object(mac, 'wb', side_effect=subprocess.CalledProcessError(42, 'stop')), \
                patch.object(mac, 'run') as run:
            with self.assertRaises(subprocess.CalledProcessError):
                mac.backup()
        self.assertEqual(mac.RECEIPT.read_text(), 'old batch')
        run.assert_not_called()

    def test_ambiguous_backup_batch_is_rejected(self):
        batches = self.home/'batches'; batches.mkdir()
        def action():
            (batches/'one').mkdir(); (batches/'two').mkdir()
        with self.assertRaises(ValueError):
            mac.new_batch(batches, action)

    def test_untrusted_backup_receipt_does_not_create_restore_targets(self):
        for value in ([], {'multica': '/tmp/../unsafe', 'litellm': '/Users/me/l', 'openclaw': '/Users/me/o'}):
            def fake_run(args):
                Path(args[-1]).write_text(json.dumps(value))
            with self.subTest(value=value), patch.object(mac, 'run', side_effect=fake_run):
                with self.assertRaises(ValueError):
                    mac.receive_backup('me@192.0.2.1')
            self.assertFalse(mac.RESTORE.exists())

    def test_interrupted_backup_receive_does_not_publish_mixed_batches(self):
        receipt = {key: '/Users/me/'+key for key in ('multica', 'openclaw', 'litellm')}
        copied = []
        def fake_run(args, **kwargs):
            if args[0] == 'scp':
                Path(args[-1]).write_text(json.dumps(receipt))
            else:
                copied.append(args)
                if len(copied) == 2:
                    raise subprocess.CalledProcessError(42, args)
        with patch.object(mac, 'run', side_effect=fake_run):
            with self.assertRaises(subprocess.CalledProcessError):
                mac.receive_backup('me@192.0.2.1')
        self.assertEqual(list(mac.RESTORE.iterdir()), [])

    def test_multica_existing_receipts_fail_before_any_mutation(self):
        self.dump('multica')
        (mac.RESTORE/'multica/adaptation').mkdir()
        target = self.home/'.local/state/multica/adaptation'; target.mkdir(parents=True)
        with patch.object(mac, 'run') as run, patch.object(mac, 'wb') as wb:
            with self.assertRaises(ValueError):
                mac.restore_multica()
        run.assert_not_called(); wb.assert_not_called()

    def test_multica_nonempty_database_is_never_restored_or_started(self):
        self.dump('multica'); calls = []
        def fake_run(args, **kwargs):
            calls.append(list(map(str, args)))
            if kwargs.get('capture'):
                return '7' if 'psql' in args else ''
        with patch.object(mac, 'run', side_effect=fake_run), patch.object(mac, 'wb'):
            with self.assertRaisesRegex(ValueError, '已有业务表'):
                mac.restore_multica()
        self.assertFalse(any('pg_restore' in args for args in calls))
        self.assertFalse(any(args[1:] == ['up', '-d', '--pull', 'never'] for args in calls))

    def test_multica_restores_dump_and_receipts_before_starting_writers(self):
        self.dump('multica')
        receipts = mac.RESTORE/'multica/adaptation'; receipts.mkdir()
        (receipts/'request.json').write_text('fixture')
        calls = []
        def fake_run(args, **kwargs):
            args = list(map(str, args)); calls.append(args)
            if 'pg_restore' in args:
                self.assertEqual(kwargs['stdin'].read(), b'synthetic database')
            if args[1:] == ['up', '-d', '--pull', 'never']:
                self.assertTrue((self.home/'.local/state/multica/adaptation/request.json').is_file())
            if kwargs.get('capture'):
                return '0' if 'psql' in args else ''
        with patch.object(mac, 'run', side_effect=fake_run), patch.object(mac, 'wb'):
            mac.restore_multica()
        pull = next(i for i, args in enumerate(calls) if args[1:] == ['pull'])
        first_up = next(i for i, args in enumerate(calls) if args[1] == 'up')
        self.assertLess(pull, first_up)
        self.assertTrue(any('pg_restore' in args for args in calls))

    def test_startup_requires_real_readiness_before_launchagent_changes(self):
        self.dump('litellm')
        with patch.object(mac.urllib.request, 'build_opener') as opener, patch.object(mac, 'wb') as wb:
            opener.return_value.open.side_effect = OSError('not ready')
            with self.assertRaises(OSError):
                mac.startup()
        wb.assert_not_called()

    def test_binding_shows_plan_without_applying_it(self):
        with patch.object(mac, 'run') as run:
            mac.bind_multica()
        commands = [list(map(str, call.args[0])) for call in run.call_args_list]
        self.assertFalse(any('apply' in args for args in commands))
        self.assertEqual(commands[-1][-1], 'plan')

    def test_apply_requires_reviewed_digest_and_stops_on_changed_plan(self):
        with patch.object(mac, 'run') as run:
            with self.assertRaises(ValueError):
                mac.apply_multica('latest')
            run.assert_not_called()
        with patch.object(mac, 'run', side_effect=subprocess.CalledProcessError(1, 'changed plan')) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                mac.apply_multica('a'*64)
        self.assertEqual(run.call_count, 1)

    def test_openclaw_success_exit_without_exact_proof_is_rejected(self):
        marker = 'OPENCLAW_NEW_MAC_NATIVE_OK_7b0d4f92'
        for proof in (b'wrong', (marker+'\n').encode()):
            def fake_run(args, **kwargs):
                work = Path(args[args.index('--cwd')+1])
                (work/'proof.txt').write_bytes(proof)
                kwargs['stdout'].write(json.dumps({'ok': True, 'status': 'ok', 'final': marker}).encode())
            with self.subTest(proof=proof), patch.object(mac, 'run', side_effect=fake_run), patch('builtins.print'):
                if proof == b'wrong':
                    with self.assertRaises(ValueError):
                        mac.verify_openclaw()
                else:
                    mac.verify_openclaw()

    def test_run_refreshes_environment_and_preserves_literal_arguments(self):
        repo = self.home/'repo'; script = repo/'components/mac/bootstrap/environment.sh'
        script.parent.mkdir(parents=True)
        script.write_text('export NEW_MAC_ENV_READY=yes\n')
        (self.home/'.env').write_text('TEST_PRIVATE=local-fixture\n')
        with patch.object(mac, 'ROOT', repo), patch.dict(os.environ, HOME=str(self.home)):
            result = mac.run(['/usr/bin/printf', '%s', '$HOME;$(false)'], capture=True, vault=True)
        self.assertEqual(result, '$HOME;$(false)')


class ShellEntry(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi bare stage ')
        self.base = Path(self.temp.name)
        self.home = self.base/'home'; self.home.mkdir()
        self.repo = self.base/'source'; (self.repo/'scripts/bootstrap').mkdir(parents=True)
        (self.repo/'components/mac/bootstrap').mkdir(parents=True)
        shutil.copyfile(ROOT/'workbench', self.repo/'workbench')
        shutil.copyfile(ROOT/'scripts/bootstrap/new-mac.sh', self.repo/'scripts/bootstrap/new-mac.sh')
        (self.repo/'components/mac/bootstrap/environment.sh').write_text(':\n')
        self.bin = self.base/'bin'; self.bin.mkdir()
        self.log = self.base/'calls'
        fixtures = {
            'uname': 'echo Darwin', 'id': 'echo 501', 'nc': 'exit 0',
            'curl': 'echo "curl $https_proxy" >> "$TEST_LOG"; exit "${TEST_NETWORK_STATUS:-0}"',
            'python3': 'echo forbidden-python >> "$TEST_LOG"; exit 99',
            'sudo': 'echo sudo >> "$TEST_LOG"',
            'git': 'echo git >> "$TEST_LOG"; [ "$1" = clone ]; mkdir -p "$5/.git"',
        }
        for name, body in fixtures.items():
            path = self.bin/name; path.write_text('#!/bin/sh\n'+body+'\n'); path.chmod(0o755)
        pre = self.repo/'scripts/bootstrap/prerequisites.sh'
        pre.write_text('#!/bin/bash\n'
                       'echo "prerequisites $1" >> "$TEST_LOG"\n'
                       'if [[ "$1" == check ]]; then exit 1; fi\n')
        self.env = {'HOME': str(self.home), 'PATH': str(self.bin)+':/usr/bin:/bin',
                    'TEST_LOG': str(self.log)}

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, **env):
        return subprocess.run(['/bin/bash', str(self.repo/'workbench'), 'new-mac', *args],
                              env=dict(self.env, **env), text=True, capture_output=True, timeout=10)

    def test_help_needs_no_python_git_or_home_writes(self):
        proc = self.cli('help')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.log.exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_network_uses_discovered_flclash_proxy_without_installation(self):
        proc = self.cli('network')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['curl http://127.0.0.1:7890']*2)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_network_failure_stops_before_authorization_or_installation(self):
        proc = self.cli('prepare', TEST_NETWORK_STATUS='33')
        self.assertEqual(proc.returncode, 33, proc.stderr)
        self.assertNotIn('prerequisites', self.log.read_text())
        self.assertNotIn('sudo', self.log.read_text())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_network_preserves_explicit_proxy(self):
        proc = self.cli('network', https_proxy='http://127.0.0.1:17890')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['curl http://127.0.0.1:17890']*2)

    def test_prepare_bootstraps_and_clones_without_python(self):
        proc = self.cli('prepare')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.home/'Documents/tools/llm/feipi-agent-kit/.git').is_dir())
        self.assertNotIn('forbidden', self.log.read_text())
        self.assertIn('prerequisites install', self.log.read_text())
        self.assertIn('人工检查', proc.stdout)

    def test_zip_software_stops_before_any_installer(self):
        proc = self.cli('software')
        self.assertEqual(proc.returncode, 1)
        self.assertIn('正式 Git 仓库', proc.stderr)
        self.assertFalse(self.log.exists())


class LiteLLMRestore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi db stage ')
        self.base = Path(self.temp.name); self.home = self.base/'home'; self.home.mkdir()
        self.bin = self.base/'bin'; self.bin.mkdir()
        lib = self.base/'repo/tools/lib/podman.sh'; lib.parent.mkdir(parents=True)
        lib.write_text('podman_require_runtime() { :; }\n'
                       'agent_service_data_root() { export AGENT_SERVICE_DATA_DIR="$HOME/data"; }\n'
                       'podman_compose() { echo compose >> "$TEST_CALLS"; }\n')
        binary = self.bin/'podman'
        binary.write_text('''#!/bin/sh
echo "$*" >> "$TEST_CALLS"
case "$*" in
  inspect*) echo "$TEST_RUNNING" ;;
  *psql*) echo "$TEST_TABLES" ;;
  *pg_restore*) cat > "$TEST_IMPORTED" ;;
esac
'''); binary.chmod(0o755)
        (self.home/'.env').write_text('# no secrets\n')
        dump = self.home/'feipi-restore/litellm/database.dump'; dump.parent.mkdir(parents=True)
        dump.write_text('fixture database')
        self.calls = self.base/'calls'; self.imported = self.base/'imported'

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, running='false', tables='0'):
        return subprocess.run(['/bin/bash', '-c', mac.LITELLM_RESTORE, '--', str(self.base/'repo')],
                              env={'HOME': str(self.home), 'PATH': str(self.bin)+':/usr/bin:/bin',
                                   'TEST_CALLS': str(self.calls), 'TEST_IMPORTED': str(self.imported),
                                   'TEST_RUNNING': running, 'TEST_TABLES': tables},
                              text=True, capture_output=True, timeout=10)

    def test_running_proxy_is_rejected_before_compose_or_data_changes(self):
        proc = self.cli(running='true')
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn('compose', self.calls.read_text())
        self.assertFalse((self.home/'data').exists())
        self.assertFalse(self.imported.exists())

    def test_existing_business_tables_are_not_overwritten(self):
        proc = self.cli(tables='3')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('已有业务表', proc.stderr)
        self.assertFalse(self.imported.exists())

    def test_empty_database_receives_exact_dump_without_clean(self):
        proc = self.cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.imported.read_text(), 'fixture database')
        self.assertNotIn('--clean', self.calls.read_text())


if __name__ == '__main__':
    unittest.main()
