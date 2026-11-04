import importlib
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import adaptation as base
import adapt
import work
import acceptance


class Acceptance(unittest.TestCase):
    def test_failed_check_exits_nonzero(self):
        result = {'codex-builder': {'probe': {}, 'runs': [], 'issue_status': 'todo', 'attachment_verified': False}}
        with patch.object(sys, 'argv', ['acceptance.py', 'check']), patch.object(acceptance, 'check', return_value=result), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                acceptance.main()
            self.assertEqual(stopped.exception.code, 1)

    def test_current_codex_only_policy_excludes_historical_roles(self):
        m = {'agents': {'codex-builder': 'agent'}, 'runtimes': {'codex': {'id': 'runtime'}}}
        c = {'agents': [{'key': 'codex-builder', 'runtime': 'codex'}]}
        with patch.object(acceptance, 'machine', return_value=m), patch.object(adapt, 'catalog', return_value=c):
            self.assertEqual(acceptance.active_agents(), ['codex-builder'])

    def test_declared_role_without_binding_is_blocked(self):
        c = {'agents': [{'key': 'qoder-worker', 'runtime': 'qoder'}]}
        with patch.object(acceptance, 'machine', return_value={'agents': {}, 'runtimes': {}}), patch.object(adapt, 'catalog', return_value=c):
            with self.assertRaisesRegex(base.AdaptError, '缺少机器绑定'):
                acceptance.active_agents()

    def test_existing_fixture_does_not_require_disabled_roles(self):
        m = {'agents': {'codex-builder': 'agent'}, 'runtimes': {'codex': {'id': 'runtime'}}}
        c = {'agents': [{'key': 'codex-builder', 'runtime': 'codex'}]}
        fixture = {'root': '/unused', 'issues': {'codex-builder': 'issue', 'qoder-worker': 'old'}}
        with patch.object(acceptance, 'machine', return_value=m), patch.object(adapt, 'catalog', return_value=c), patch.object(acceptance, 'read_json', return_value=fixture), patch.object(acceptance, 'cli', return_value=[]), patch.object(acceptance, 'prepare_files') as refresh:
            self.assertEqual(acceptance.prepare(), fixture)
            refresh.assert_called_once_with(Path('/unused'), ['codex-builder'])

    def test_old_attachment_cannot_certify_a_new_execution(self):
        report = {'task_contract': {k: True for k in ['MULTICA_TOKEN', 'MULTICA_TASK_ID', 'MULTICA_AGENT_ID', 'MULTICA_WORKSPACE_ID', 'MULTICA_SERVER_URL']},
                  'token_kind': 'task', 'calculation': 5, 'task_id': 'old'}
        expected = dict(agent_key='codex-builder', agent_id='agent', workspace_id='workspace', runtime_id='runtime', cwd='/probe', probe_sha256='sha')
        report.update({k:v for k,v in expected.items() if k != 'runtime_id'})
        value = {'probe': report, 'runs': [{'id': 'new', 'status': 'failed'}, dict(id='old', status='completed', agent_id='agent', runtime_id='runtime', workspace_id='workspace', work_dir='/probe')],
                 'issue_status': 'in_review', 'attachment_count': 2, 'attachment_verified': True,
                 'expected': expected, 'progress_verified': True, 'delivery_verified': True}
        self.assertFalse(acceptance.passed(value))
        value['runs'] = value['runs'][1:]
        self.assertTrue(acceptance.passed(value))
        value['attachment_verified'] = False
        self.assertFalse(acceptance.passed(value))


class Authentication(unittest.TestCase):
    def test_attachment_download_uses_native_flags_and_accepts_text(self):
        response = subprocess.CompletedProcess([], 0, stdout='Downloaded report.json', stderr='')
        with patch.object(base, 'task_context', return_value=True), patch.object(base.subprocess, 'run', return_value=response) as native:
            self.assertEqual(base.cli('attachment', 'download', 'attachment', '--output-dir', '/private/report'), response.stdout)
            self.assertNotIn('--output', native.call_args[0][0])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.spy = Path(self.temp.name) / 'cli'
        self.spy.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        self.spy.chmod(0o700)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('MULTICA_')}
        self.env['MULTICA_CLI_BIN'] = str(self.spy)
    def tearDown(self):
        self.temp.cleanup()
    def call(self, env):
        return subprocess.run([str(ROOT / 'bin/multica-task'), 'issue', 'list'], env=env, capture_output=True, text=True)
    def test_personal(self):
        p = self.call(self.env)
        self.assertEqual(p.stdout.splitlines(), ['--profile', 'personal', 'issue', 'list'])
    def test_complete_task_and_each_missing_field(self):
        fields = dict(MULTICA_TOKEN='mat_test_secret', MULTICA_TASK_ID='t', MULTICA_AGENT_ID='a', MULTICA_WORKSPACE_ID='w', MULTICA_SERVER_URL='http://localhost')
        p = self.call(dict(self.env, **fields))
        self.assertEqual(p.stdout.splitlines(), ['issue', 'list'])
        for field in fields:
            env = dict(self.env, **fields)
            del env[field]
            p = self.call(env)
            self.assertEqual(p.returncode, 78, field)
            self.assertNotIn('mat_test_secret', p.stderr + p.stdout)
    def test_internal_context_without_credentials(self):
        self.assertEqual(self.call(dict(self.env, MULTICA_TASK_CONFIG_ROOT='/tmp/task')).returncode, 78)


class Bindings(unittest.TestCase):
    def test_codex_evidence_does_not_require_retired_openclaw_state(self):
        with tempfile.TemporaryDirectory() as root:
            m = {'agent_kit': root}
            c = {'agents': [{'runtime': 'codex'}], 'skill_checks': []}
            self.assertIsInstance(adapt.evidence_fingerprint(m, c), str)

    def test_codex_doctor_does_not_probe_disabled_runtimes(self):
        with tempfile.TemporaryDirectory() as root:
            m = {'agent_kit': root, 'server_url': 'http://localhost', 'workspace_id': 'workspace',
                 'profile': 'personal', 'commands': {'codex': '/test/codex'}, 'projects': {}}
            c = {'agents': [{'key': 'codex-builder', 'runtime': 'codex'}],
                 'compatibility': {'codex': 'test-version'}, 'skill_checks': []}
            def read(path, default=None):
                return {'server_url': m['server_url'], 'workspace_id': 'workspace', 'max_concurrent_tasks': 1} if str(path).endswith('config.json') else (default or {})
            response = subprocess.CompletedProcess([], 0, stdout='test-version', stderr='')
            with patch.object(adapt, 'machine', return_value=m), patch.object(adapt, 'catalog', return_value=c), patch.object(adapt, 'read_json', side_effect=read), patch.object(adapt.subprocess, 'run', return_value=response), patch.object(adapt.urllib.request, 'urlopen') as http, patch.object(adapt.shutil, 'which', return_value='/test/codex'), patch.object(adapt, 'build_plan', return_value={'actions': []}), patch.object(adapt, 'public_plan', return_value={}), patch.object(adapt, 'evidence_fingerprint', return_value='fingerprint'):
                http.return_value.__enter__.return_value.status = 200
                result = adapt.doctor()
            self.assertTrue(result['static_ok'])
            self.assertEqual(http.call_count, 1)
            self.assertNotIn('openclaw-isolated', [v['check'] for v in result['checks']])

    def test_dispatch_rejects_runtime_and_model_drift_before_execution(self):
        m={'agents':{'worker':'a'},'runtimes':{'codex':{'id':'r'}}}
        c={'agents':[{'key':'worker','runtime':'codex','model':'fixed'}]}
        for actual in [{'id':'a','runtime_id':'another-known-runtime','model':'fixed'}, {'id':'a','runtime_id':'r','model':'unexpected'}]:
            with patch.object(work,'machine',return_value=m), patch.object(work,'read_json',return_value=c), patch.object(work,'cli',return_value=actual) as fake:
                with self.assertRaises(base.AdaptError): work.preflight('issue','worker',{})
                self.assertEqual(fake.call_count,1)
    def test_idle_audit_reads_later_pages(self):
        with patch.object(base,'cli',side_effect=[([{'status':'completed'}],'next'),([{'status':'running'}],None)]) as fake:
            self.assertEqual([r['status'] for r in base.agent_runs('agent')],['completed','running'])
            self.assertIn('--before',fake.call_args[0])
    def test_same_provider_wrong_identity(self):
        runtime = dict(id='correct', daemon_id='d', provider='openclaw', profile_id='isolated', status='online')
        for change in [dict(id='other'), dict(daemon_id='other'), dict(profile_id='personal'), dict(provider='codex')]:
            binding = dict(id='correct', provider='openclaw', profile_id='isolated', **{})
            candidate = dict(runtime, **change)
            with self.assertRaises(base.AdaptError):
                base.resolve_runtime(binding, 'd', [candidate])
    def test_full_skill_inventory_detects_old_entry_new_script(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source'; installed = Path(directory) / 'installed'
            (source / 'scripts').mkdir(parents=True); installed.mkdir()
            (source / 'SKILL.md').write_text('new instructions')
            (source / 'scripts/a.py').write_text('new implementation')
            (installed / 'SKILL.md').write_text('old instructions')
            (installed / 'scripts').symlink_to(source / 'scripts')
            before = base.file_inventory(source); after = base.file_inventory(installed)
            self.assertEqual(before['scripts/a.py'], after['scripts/a.py'])
            self.assertNotEqual(before['SKILL.md'], after['SKILL.md'])


class Receipts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(base, 'STATE', Path(self.temp.name)), patch.object(work, 'STATE', Path(self.temp.name)), patch.object(work, 'machine', return_value={'server_url':'local', 'workspace_id':'w'})]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in self.patches: p.stop()
        self.temp.cleanup()
    def test_duplicate_has_one_side_effect(self):
        called = []
        def mutate(): called.append(1); return {'id':'run1'}
        work.once('stable', {'issue':'i'}, mutate)
        result = work.once('stable', {'issue':'i'}, mutate)
        self.assertTrue(result['replayed_receipt'])
        self.assertEqual(called, [1])
        with self.assertRaises(base.AdaptError): work.once('stable', {'issue':'other'}, mutate)
    def test_lost_response_never_replayed(self):
        called = []
        def mutate(): called.append(1); raise base.AdaptError('response lost')
        with self.assertRaises(base.AdaptError): work.once('stable', {}, mutate)
        with self.assertRaises(base.AdaptError): work.once('stable', {}, mutate)
        self.assertEqual(called, [1])
    def test_read_only_preflight_failure_does_not_poison_request_id(self):
        called = []
        def reject(): raise base.AdaptError('runtime offline')
        def mutate(): called.append(1); return {'id':'run1'}
        with self.assertRaises(base.AdaptError):
            work.once('retry-ready', {}, mutate, reject)
        self.assertEqual(called, [])
        self.assertEqual(work.once('retry-ready', {}, mutate)['id'], 'run1')
        self.assertTrue(work.once('retry-ready', {}, mutate, reject)['replayed_receipt'])
        self.assertEqual(called, [1])
    def test_note_always_silent_and_preserves_parent(self):
        import argparse
        path = Path(self.temp.name) / 'note.md'; path.write_text('@agent completed')
        calls = []
        def fake(*args, **kwargs): calls.append((args, kwargs)); return {'id':'comment'}
        with patch.object(work, 'cli', side_effect=fake):
            work.run(argparse.Namespace(action='note', issue='i', body_file=str(path), parent='trigger', request_id='note'))
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1]['stdin'].startswith('/note\n'))
        self.assertEqual(calls[0][0][-2:], ('--parent', 'trigger'))
    def test_dispatch_backlog_uses_one_explicit_comment(self):
        import argparse
        calls = []
        def fake(*args, **kwargs): calls.append((args,kwargs)); return {'id':'comment','trigger_outcomes':[{'status':'queued'}]}
        data = dict(objective='probe',scope='here',directory=self.temp.name,acceptance='pass',artifacts=[],remaining=[],required_commands=[],required_mcp=[])
        path=Path(self.temp.name)/'packet.json';path.write_text(json.dumps(data))
        args=argparse.Namespace(action='dispatch',issue='i',agent='worker',packet=str(path),request_id='dispatch',parent=None)
        with patch.object(work,'preflight',return_value={'id':'a','name':'Worker'}), patch.object(work,'cli',side_effect=fake), patch.object(work,'task_context',return_value=False):
            work.run(args); work.run(args)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0][0][-1], '--no-start')
        self.assertIn('(mention://agent/a)',calls[1][1]['stdin'])
        self.assertFalse(calls[1][1]['stdin'].startswith('/note'))


class Reconcile(unittest.TestCase):
    def test_readback_idempotence_and_ui_runtime_drift(self):
        m = dict(schema=1, role='primary', workspace_id='w', daemon_id='d', agents={'worker':'a'}, skill_id='s', runtimes={'codex':dict(id='r',provider='codex',profile_id=None)}, projects={})
        c = {'agents':[{'key':'worker','runtime':'codex','name':'Worker','model':'model','thinking_level':'high','max_concurrent_tasks':1}], 'projects':[], 'skill':{'name':'shared'}}
        desired = dict(name='Worker', model='model', thinking_level='high', max_concurrent_tasks=1, instructions='body', runtime_id='r')
        current = dict(desired)
        def fake(*args, **kwargs):
            if args[:2] == ('workspace','get'): return {'id':'w'}
            if args[:2] == ('runtime','list'): return [dict(id='r',provider='codex',profile_id=None,daemon_id='d',status='online')]
            if args[:2] == ('agent','list'): return [{'id':'a','name':'Worker'}]
            if args[:2] == ('agent','get'): return current
            if args[:2] == ('skill','list'): return [{'id':'s','name':'shared'}]
            if args[:2] == ('skill','get'): return {'id':'s','content':'skill'}
            if args[:3] == ('agent','skills','list'): return [{'id':'s'}]
            raise AssertionError(args)
        with patch.object(adapt,'machine',return_value=m), patch.object(adapt,'catalog',return_value=c), patch.object(adapt,'desired_agent',return_value=desired), patch.object(adapt,'skill_body',return_value='skill'), patch.object(adapt,'cli',side_effect=fake):
            first = adapt.build_plan(); self.assertEqual(first['actions'], [])
            self.assertEqual(first['plan_id'], adapt.build_plan()['plan_id'])
            current['runtime_id'] = 'other-codex-on-another-machine'
            plan = adapt.build_plan()
            self.assertEqual(plan['actions'][0]['desired'], {'runtime_id':'r'})
            self.assertNotEqual(plan['plan_id'], first['plan_id'])


if __name__ == '__main__': unittest.main()
