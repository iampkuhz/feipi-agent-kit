"""新机本地身份、异步注册与拒绝误绑；不连接实际服务或修改日常运行副本。"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import adaptation as base
import adapt


class LocalRebind(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='multica local rebind ')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.machine = self.home/'.config/feipi-multica/machine.json'
        self.machine.parent.mkdir(parents=True)
        self.did = '11111111-1111-4111-8111-111111111111'
        self.m = {'schema':1, 'role':'primary', 'profile':'personal', 'workspace_id':'restored-workspace',
                  'device_name':'new-machine', 'server_url':'https://api.multica.ai', 'app_url':'https://multica.ai',
                  'workspaces_root':str(self.home/'task workspaces'), 'daemon_id':None,
                  'runtimes':{'codex':{'id':None,'provider':'codex','profile_id':None,'keep':'logical'}},
                  'agents':{'coder':'logical-agent'}, 'projects':{'project':{'id':'logical-project'}}}
        self.machine.write_text(json.dumps(self.m))
        profile = self.home/'.multica/profiles/personal/config.json'; profile.parent.mkdir(parents=True)
        self.profile = profile
        profile.write_text(json.dumps({'server_url':self.m['server_url'], 'app_url':self.m['app_url'],
                                      'workspace_id':self.m['workspace_id'], 'device_name':'new-machine',
                                      'workspaces_root':self.m['workspaces_root'], 'max_concurrent_tasks':1,
                                      'disable_auto_update':True,'token':'mul_fixture-only'}))
        self.identity = self.home/'.multica/daemon.id'; self.identity.write_text(self.did+'\n')
        self.health = {'status':'running','profile':'personal','device_name':'new-machine',
                       'server_url':self.m['server_url'],'os':sys.platform,
                       'daemon_id':self.did,'active_task_count':0,
                       'workspaces':[{'id':self.m['workspace_id'],'runtimes':['local-runtime']}]}
        self.rows = [{'id':'other-device','provider':'codex','profile_id':None,'daemon_id':'other','status':'online'},
                     {'id':'other-profile','provider':'codex','profile_id':'isolated','daemon_id':self.did,'status':'online'},
                     {'id':'local-runtime','provider':'codex','profile_id':None,'daemon_id':self.did,'status':'online'}]
        self.clock = 0
        for manager in (patch.dict(os.environ, {'HOME':str(self.home)}),
                        patch.object(base,'MACHINE',self.machine), patch.object(adapt,'MACHINE',self.machine),
                        patch.object(base,'STATE',self.home/'state'),
                        patch.object(adapt.time,'monotonic',side_effect=lambda:self.clock),
                        patch.object(adapt.time,'sleep',side_effect=self.sleep)):
            manager.start(); self.addCleanup(manager.stop)

    def sleep(self, duration):
        self.clock += duration

    def cli(self, *args, **kwargs):
        if args == ('workspace','get'): return {'id':self.m['workspace_id']}
        if args == ('daemon','status'): return copy.deepcopy(self.health)
        if args == ('runtime','list'): return copy.deepcopy(self.rows)
        raise AssertionError('unexpected mutation: '+repr(args))

    def unchanged_after_failure(self, pattern):
        before = (self.machine.read_bytes(),self.machine.stat().st_mtime_ns)
        with self.assertRaisesRegex(base.AdaptError,pattern):
            adapt.rebind_local()
        self.assertEqual((self.machine.read_bytes(),self.machine.stat().st_mtime_ns),before)

    def test_waits_for_native_start_and_registration_then_preserves_logical_ids(self):
        statuses = [{'status':'stopped'}, {'status':'starting'}, dict(self.health,workspaces=None), self.health]
        runtimes = [[], self.rows]
        def cli(*args,**kwargs):
            if args == ('daemon','status'): return copy.deepcopy(statuses.pop(0))
            if args == ('runtime','list'): return copy.deepcopy(runtimes.pop(0))
            return self.cli(*args,**kwargs)
        with patch.object(adapt,'cli',side_effect=cli) as native:
            first = adapt.rebind_local()
        value = json.loads(self.machine.read_text())
        self.assertEqual(value['daemon_id'],self.did)
        self.assertEqual(value['runtimes']['codex'],dict(self.m['runtimes']['codex'],id='local-runtime'))
        self.assertEqual(value['agents'],self.m['agents']); self.assertEqual(value['projects'],self.m['projects'])
        self.assertTrue(first['changed']); self.assertEqual(self.clock,6)
        self.assertTrue(all(0 < call.kwargs['timeout'] <= 15 for call in native.call_args_list))
        before = (self.machine.read_bytes(),self.machine.stat().st_mtime_ns)
        with patch.object(adapt,'cli',side_effect=self.cli):
            self.assertFalse(adapt.rebind_local()['changed'])
        self.assertEqual((self.machine.read_bytes(),self.machine.stat().st_mtime_ns),before)

    def test_identity_fingerprint_conflicts_fail_before_writing(self):
        changes = [{'profile':'another'}, {'device_name':'another'}, {'server_url':'https://other.invalid'},
                   {'server_url':None}, {'os':'another'},
                   {'daemon_id':'other'}, {'port_conflict':{'profile':'other'}}]
        original = self.health
        for change in changes:
            with self.subTest(change=change), patch.object(adapt,'cli',side_effect=self.cli):
                self.health = dict(original,**change)
                self.unchanged_after_failure('不匹配|不一致|身份冲突')
                self.assertEqual(self.clock,0)
        self.health = original

    def test_missing_or_linked_machine_identity_is_never_generated_or_adopted(self):
        self.identity.unlink()
        with patch.object(adapt,'cli',side_effect=self.cli):
            self.unchanged_after_failure('缺少本机原生')
        self.assertFalse(self.identity.exists())
        outside = self.home/'old-identity'; outside.write_text(self.did)
        self.identity.symlink_to(outside)
        with patch.object(adapt,'cli',side_effect=self.cli):
            self.unchanged_after_failure('缺少本机原生')
        self.assertEqual(outside.read_text(),self.did)

    def test_duplicate_online_runtimes_fail_immediately(self):
        self.rows.append(dict(self.rows[-1],id='duplicate-runtime'))
        with patch.object(adapt,'cli',side_effect=self.cli):
            self.unchanged_after_failure('runtime 不唯一')
        self.assertEqual(self.clock,0)

    def test_stopped_busy_or_unregistered_daemon_times_out_without_partial_binding(self):
        original = self.health
        for change in ({'status':'stopped'}, {'active_task_count':1},
                       {'workspaces':[{'id':self.m['workspace_id'],'runtimes':['stale-runtime']}]}):
            with self.subTest(change=change), patch.object(adapt,'cli',side_effect=self.cli):
                self.health = dict(original,**change)
                self.clock = 0
                self.unchanged_after_failure('120 秒内未就绪')
                self.assertEqual(self.clock,120)

    def test_profile_and_workspace_must_be_valid_before_reading_daemon(self):
        with patch.object(adapt,'cli',return_value={'id':'other-workspace'}) as native:
            self.unchanged_after_failure('CLI 工作区与机器绑定不一致')
            self.assertEqual(native.call_count,1)
        self.profile.unlink()
        with patch.object(adapt,'cli') as native:
            with self.assertRaisesRegex(base.AdaptError,'profile 尚未就绪'):
                adapt.rebind_local()
            native.assert_not_called()

    def test_explicit_daemon_selection_remains_available_and_repeat_is_read_only(self):
        with patch.object(adapt,'cli',side_effect=self.cli):
            self.assertTrue(adapt.rebind(self.did)['changed'])
            before = (self.machine.read_bytes(),self.machine.stat().st_mtime_ns)
            self.assertFalse(adapt.rebind(self.did)['changed'])
            self.assertEqual((self.machine.read_bytes(),self.machine.stat().st_mtime_ns),before)

    def test_published_command_entry_runs_with_only_read_only_native_calls(self):
        executable = self.home/'fixture-cli'
        responses = self.home/'responses.json'
        responses.write_text(json.dumps({'workspace get':{'id':self.m['workspace_id']},
                                         'daemon status':self.health,'runtime list':self.rows}))
        calls = self.home/'calls'
        executable.write_text(f'#!{sys.executable}\n'+'''
import json, os, pathlib, sys
args=sys.argv[1:]
with pathlib.Path(os.environ['REBIND_TEST_CALLS']).open('a') as log: log.write(json.dumps(args)+'\\n')
assert args[2:] == ['--output','json'], args
print(json.dumps(json.loads(pathlib.Path(os.environ['REBIND_TEST_RESPONSES']).read_text())[' '.join(args[:2])]))
'''); executable.chmod(0o755)
        environment = {key:value for key,value in os.environ.items() if not key.startswith('MULTICA_')}
        environment.update(HOME=str(self.home),MULTICA_TASK_CLI=str(executable),
                           REBIND_TEST_RESPONSES=str(responses),REBIND_TEST_CALLS=str(calls),PYTHONDONTWRITEBYTECODE='1')
        publish = subprocess.run([sys.executable,str(ROOT/'scripts/install-runtime.py')],env=environment,capture_output=True,text=True)
        self.assertEqual(publish.returncode,0,publish.stderr)
        command = str(self.home/'.local/bin/multica-ops')
        first = subprocess.run([command,'rebind','--local'],env=environment,capture_output=True,text=True)
        self.assertEqual(first.returncode,0,first.stderr)
        self.assertTrue(json.loads(first.stdout)['changed'])
        second = subprocess.run([command,'rebind','--local'],env=environment,capture_output=True,text=True)
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertFalse(json.loads(second.stdout)['changed'])
        self.assertEqual({tuple(json.loads(line)[:2]) for line in calls.read_text().splitlines()},
                         {('workspace','get'),('daemon','status'),('runtime','list')})
        rejected = subprocess.run([command,'rebind','--local','--daemon-id',self.did],env=environment,capture_output=True,text=True)
        self.assertNotEqual(rejected.returncode,0)
        rejected = subprocess.run([command,'doctor','--local'],env=environment,capture_output=True,text=True)
        self.assertNotEqual(rejected.returncode,0)
        self.assertIn('只适用于 rebind',rejected.stderr)
        self.assertFalse((self.home/'Library').exists())


if __name__ == '__main__':
    unittest.main()
