"""原生任务操作、范围与分步回执；不连接个人平台。"""
import argparse
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
sys.path.insert(0, str(ROOT / 'scripts'))
import adaptation as base
import work
NATIVE_CLI = work.cli


class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / 'state'
        self.item = dict(id='issue', workspace_id='workspace', project_id='project', status='in_progress', assignee_id=None)
        self.agents = [dict(id='outside-managed-list', name='Platform Worker', workspace_id='workspace', runtime_id='runtime', model='any-model')]
        self.runs, self.comments, self.writes, self.reads = [], [], [], []
        self.fail_comment_after = self.fail_status_before = self.fail_status_after = False
        for obj, name, value in [(base, 'STATE', self.state), (work, 'STATE', self.state), (work, 'cli', self.native)]:
            patcher = patch.object(obj, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.dict(os.environ, {k:v for k,v in os.environ.items() if not k.startswith('MULTICA_')}, clear=True)
        patcher.start(); self.addCleanup(patcher.stop)
        cwd = patch.object(Path, 'cwd', return_value=self.root)
        cwd.start(); self.addCleanup(cwd.stop)

    def native(self, *a, with_cursor=False):
        self.reads.append(a)
        if a == ('workspace', 'get'): return {'id':'workspace'}
        if a[:2] == ('project', 'get'): return {'id':a[2], 'workspace_id':'workspace'}
        if a == ('user', 'profile', 'get'): return {'id':'operator'}
        if a == ('config', 'show'): return 'server_url: http://fixture.invalid\n'
        if a[:2] == ('issue', 'get'): return copy.deepcopy(self.item)
        if a[:2] == ('agent', 'list'): return self.agents
        if a[:2] == ('agent', 'get'): return next(x for x in self.agents if x['id']==a[2])
        if a[:3] == ('project', 'resource', 'list'):
            return [dict(resource_type='local_directory',resource_ref=dict(daemon_id='remote-daemon',local_path='/remote/repo',execution_mode='worktree'))]
        if a[:2] == ('runtime', 'list'): return [dict(id='runtime',daemon_id='remote-daemon')]
        if a[:2] == ('issue', 'runs'): return self.runs
        if a[:3] == ('issue', 'comment', 'list'):
            return (copy.deepcopy(self.comments), None) if with_cursor else copy.deepcopy(self.comments)
        if a[:2] == ('issue', 'create'):
            self.writes.append(a)
            self.item.update(status='backlog',assignee_id=None)
            return copy.deepcopy(self.item)
        if a[:2] == ('issue', 'assign'):
            self.writes.append(a)
            self.item['assignee_id']=a[a.index('--to-id')+1]
            return copy.deepcopy(self.item)
        if a[:3] == ('issue', 'comment', 'add'):
            self.writes.append(a)
            self.assertNotIn('--content-stdin',a)
            file=Path(a[a.index('--content-file')+1])
            self.assertEqual(file.parent,self.root)
            row=dict(id='comment-'+str(len(self.comments)),content=file.read_text(),
                     parent_id=a[a.index('--parent')+1] if '--parent' in a else None,
                     source_task_id=os.environ.get('MULTICA_TASK_ID'),attachments=[])
            self.comments.append(row)
            if self.fail_comment_after:
                self.fail_comment_after=False
                raise base.AdaptError('评论响应丢失')
            return copy.deepcopy(row)
        if a[:2] == ('issue', 'update'):
            self.writes.append(a)
            if self.fail_status_before:
                self.fail_status_before=False
                raise base.AdaptError('状态未写入')
            self.item['status']=a[a.index('--status')+1]
            if self.fail_status_after:
                self.fail_status_after=False
                raise base.AdaptError('状态响应丢失')
            return copy.deepcopy(self.item)
        raise AssertionError(a)

    def file(self, name, text):
        file=self.root/name; file.write_text(text,encoding='utf-8'); return str(file)

    def args(self, action='deliver', **values):
        base=dict(action=action,issue='issue',project='project',profile=None,server_url=None,workspace_id=None,
                  request_id='request',parent=None,body_file=self.file('body.md','实际结果，仍有剩余'),artifact=[],status=None)
        base.update(values); return argparse.Namespace(**base)

    def packet(self, **values):
        handoff=dict(objective='交付实际产物',scope='仅目标仓库',directory='/remote/repo',acceptance='验证通过',
                     required_executables=['not-on-dispatcher'],validation_commands=['git diff HEAD --check'],required_mcp=['remote-mcp'])
        handoff.update(values); return self.file('handoff.json',json.dumps(handoff))

    def receipts(self):
        return [json.loads(p.read_text()) for p in (self.state/'requests').glob('*.json')]

    def test_deliver_is_materials_only_without_forced_attachment_or_status(self):
        out=work.run(self.args())
        self.assertFalse(out['accepted'])
        self.assertEqual(self.item['status'],'in_progress')
        self.assertEqual(len(self.writes),1)
        self.assertTrue(self.comments[0]['content'].startswith('/note\nreceipt-key:'))
        self.assertNotIn('--attachment',self.writes[0])

    def test_all_writes_refuse_foreign_issue_before_sending(self):
        for action in ('note','deliver','dispatch','handoff','bind'):
            with self.subTest(action=action):
                self.item['project_id']='other-project'
                with self.assertRaisesRegex(base.AdaptError,'Issue 不属于'):
                    work.run(self.args(action))
                self.assertEqual(self.writes,[])
                self.assertEqual(self.receipts(),[])

    def test_dynamic_agent_worktree_and_unverified_remote_capabilities_are_allowed(self):
        out=work.run(self.args('dispatch',agent='Platform Worker',packet=self.packet()))
        self.assertEqual(out['execution_checks']['state'],'verify-in-runtime')
        self.assertEqual(out['execution_checks']['required_mcp'],['remote-mcp'])
        self.assertEqual(len(self.writes),2)
        self.assertIn('--no-start',self.writes[0])
        self.assertIn('mention://agent/outside-managed-list',self.comments[0]['content'])
        self.assertFalse(any(a[:3]==('agent','skills','list') for a in self.reads))

    def test_ambiguous_agent_busy_run_and_wrong_remote_directory_block(self):
        args=self.args('dispatch',agent='Platform Worker',packet=self.packet())
        self.agents.append({**self.agents[0],'id':'duplicate'})
        with self.assertRaisesRegex(base.AdaptError,'不唯一'): work.run(args)
        self.agents.pop(); self.runs=[{'id':'running'}]
        with self.assertRaisesRegex(base.AdaptError,'活动 run'): work.run(args)
        self.runs=[]; args.packet=self.packet(directory='/outside/scope')
        with self.assertRaisesRegex(base.AdaptError,'目录'): work.run(args)
        self.assertEqual(self.writes,[]); self.assertEqual(self.receipts(),[])

    def test_same_content_new_path_replays_after_verifying_remote_comment(self):
        args=self.args(); work.run(args)
        args.body_file=self.file('renamed.md','实际结果，仍有剩余')
        self.assertTrue(work.run(args)['replayed_receipt'])
        self.assertEqual(len(self.writes),1)
        self.comments=[]
        with self.assertRaisesRegex(base.AdaptError,'无法确认'): work.run(args)
        self.assertEqual(len(self.writes),1)

    def test_partial_delivery_retries_only_missing_status_and_never_uploads_twice(self):
        args=self.args(status='in_review',artifact=[self.file('result.json','{}')])
        self.fail_status_before=True
        with self.assertRaises(base.AdaptError): work.run(args)
        receipt=self.receipts()[0]
        self.assertEqual(receipt['steps']['comment']['state'],'done')
        self.assertEqual(receipt['steps']['status']['state'],'pending')
        args.body_file=self.file('moved.md','实际结果，仍有剩余')
        work.run(args)
        self.assertEqual(self.item['status'],'in_review')
        self.assertEqual(len(self.comments),1)
        self.assertEqual(sum('--attachment' in x for x in self.writes),1)

    def test_unknown_comment_response_is_reconciled_from_original_thread(self):
        args=self.args(parent='original-thread',status='in_review')
        self.fail_comment_after=True
        with self.assertRaises(base.AdaptError): work.run(args)
        work.run(args)
        self.assertEqual(len(self.comments),1)
        self.assertEqual(self.item['status'],'in_review')
        self.assertTrue(any('--thread' in x and 'original-thread' in x for x in self.reads))

    def test_unknown_status_response_is_read_back_without_another_update(self):
        args=self.args(status='in_review'); self.fail_status_after=True
        with self.assertRaises(base.AdaptError): work.run(args)
        work.run(args)
        self.assertEqual(sum(x[:2]==('issue','update') for x in self.writes),1)

    def test_foreign_status_change_and_changed_content_are_not_overwritten(self):
        args=self.args(status='in_review'); self.fail_status_before=True
        with self.assertRaises(base.AdaptError): work.run(args)
        self.item['status']='done'
        with self.assertRaisesRegex(base.AdaptError,'状态已'): work.run(args)
        args.body_file=self.file('changed.md','另一项结果')
        with self.assertRaisesRegex(base.AdaptError,'不同输入'): work.run(args)
        self.assertEqual(len(self.comments),1)

    def test_incomplete_task_identity_never_reaches_cli_or_personal_profile(self):
        valid=dict(zip(work.TASK_FIELDS,['mat_fixture','run','agent','workspace','http://fixture.invalid']))
        for missing in work.TASK_FIELDS:
            with self.subTest(missing=missing), patch.dict(os.environ,{k:v for k,v in valid.items() if k!=missing}):
                with self.assertRaisesRegex(base.AdaptError,'身份不完整'): work.run(self.args())
        with patch.dict(os.environ,{'MULTICA_DAEMON_PORT':'9000'}):
            with self.assertRaisesRegex(base.AdaptError,'身份不完整'): work.run(self.args())
        self.assertEqual(self.reads,[])

    def test_background_parent_and_receipts_are_bound_to_current_run(self):
        valid=dict(zip(work.TASK_FIELDS,['mat_fixture','run-a','agent','workspace','http://fixture.invalid']))
        with patch.dict(os.environ,valid):
            self.runs=[dict(id='run-a',trigger_comment_id='trigger')]
            with self.assertRaisesRegex(base.AdaptError,'trigger_comment_id'): work.run(self.args())
            work.run(self.args(parent='trigger'))
        with patch.dict(os.environ,{**valid,'MULTICA_TASK_ID':'run-b'}):
            self.runs=[dict(id='run-b',trigger_comment_id='trigger')]
            work.run(self.args(parent='trigger'))
        self.assertEqual(len(self.comments),2)
        self.assertEqual(len(self.receipts()),2)
        self.assertNotEqual(self.receipts()[0]['principal']['run_id'],self.receipts()[1]['principal']['run_id'])

    def test_record_and_bind_are_only_comments_or_unassigned_creation(self):
        args=self.args('record',title='独立任务'); work.run(args)
        self.assertEqual(self.item['status'],'backlog'); self.assertIsNone(self.item['assignee_id'])
        self.assertNotIn('--assignee',self.writes[0])
        args=self.args('bind',request_id='bind',directory=str(self.root),owner='当前聊天')
        work.run(args)
        self.assertIn('当前交互处理',self.comments[0]['content'])

    def test_recover_keeps_all_light_threads_and_only_requested_receipt(self):
        self.comments=[dict(id=str(i),content='摘要') for i in range(12)]
        out=work.run(self.args('recover'))
        self.assertEqual(len(out['threads']),12)
        self.assertEqual(out['runs'],[])
        self.assertTrue(all('--full' not in a for a in self.reads))
        self.assertEqual(self.writes,[])

    def test_legacy_pending_is_reported_and_cannot_be_resent_as_new_receipt(self):
        legacy=self.state/'requests'/(work.digest(['http://fixture.invalid','workspace','request'])+'.json')
        base.private_write(legacy,{'state':'pending','old':True})
        with self.assertRaisesRegex(base.AdaptError,'旧版回执'): work.run(self.args())
        self.assertTrue(work.run(self.args('recover'))['receipt']['old'])
        self.assertEqual(self.writes,[])

    def test_receipt_cursor_pages_and_distinguishes_executables_from_validation_commands(self):
        value=work.packet(self.packet())
        self.assertEqual(value['validation_commands'],['git diff HEAD --check'])
        with self.assertRaisesRegex(base.AdaptError,'可执行文件名'):
            work.packet(self.packet(required_executables=['git diff HEAD --check']))
        with patch.object(work,'cli',side_effect=[([{'id':'root'}],('time','cursor')),([{'id':'old'}],None)]) as call:
            self.assertEqual([r['id'] for r in work.thread_comments('issue','root')],['root','old'])
            self.assertIn('--before-id',call.call_args.args)

    def test_native_transport_redacts_failure_and_requires_content_file(self):
        with patch.object(work.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','forbidden secret-value')):
            with self.assertRaises(base.AdaptError) as error:
                NATIVE_CLI('issue','get','issue')
            self.assertIn('[permission]',str(error.exception))
            self.assertNotIn('secret-value',str(error.exception))


if __name__ == '__main__':
    unittest.main()
