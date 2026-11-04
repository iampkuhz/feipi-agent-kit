"""任务动作的可观察契约；所有 CLI 与回执均隔离，不连接个人服务。"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import adaptation as base
import work


class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.native = Mock(side_effect=AssertionError('测试未声明的 CLI 调用'))
        for target, name, value in [(base, 'STATE', self.state), (work, 'STATE', self.state),
                                    (work, 'cli', self.native), (work, 'task_context', lambda: False),
                                    (work, 'machine', lambda: {'server_url': 'isolated', 'workspace_id': 'workspace'})]:
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def file(self, name, content):
        path = self.root / name
        path.write_text(content)
        return str(path)

    def args(self, action, **values):
        data = dict(action=action, issue='issue', parent='trigger', request_id=action)
        data.update(values)
        return argparse.Namespace(**data)

    def receipts(self):
        return [json.loads(p.read_text()) for p in (self.state / 'requests').glob('*.json')]

    def handoff(self, **values):
        data = dict(objective='验证任务', scope='仅验收目录', directory=str(self.root),
                    acceptance='实际产物通过', artifacts=[], remaining=[], required_commands=[], required_mcp=[])
        data.update(values)
        return data

    def test_record_is_unassigned_backlog_and_replay_does_not_create_again(self):
        self.native.side_effect = lambda *a, **kw: {'id': 'created'}
        args = self.args('record', project='project', title='独立验收', body_file=self.file('task.md', '目标'))
        result = work.run(args)
        self.assertEqual(result['issue_id'], 'created')
        self.assertTrue(work.run(args)['replayed_receipt'])
        self.native.assert_called_once()
        command = self.native.call_args.args
        self.assertEqual(command[:2], ('issue', 'create'))
        self.assertEqual(command[command.index('--status') + 1], 'backlog')
        self.assertNotIn('--assignee', command)
        self.assertIn('request-id: record', self.native.call_args.kwargs['stdin'])

    def test_bind_busy_rejection_leaves_no_pending_and_same_intent_can_resume(self):
        args = self.args('bind', directory=str(self.root), owner='Codex 当前聊天')
        self.native.side_effect = lambda *a, **kw: [{'id': 'running'}]
        with self.assertRaisesRegex(base.AdaptError, '已有后台任务'):
            work.run(args)
        self.assertEqual(self.receipts(), [])
        self.native.side_effect = lambda *a, **kw: [] if a[1] == 'runs' else {'id': 'bound'}
        work.run(args)
        self.assertEqual(self.receipts()[0]['state'], 'done')
        self.assertTrue(self.native.call_args.kwargs['stdin'].startswith('/note\n'))
        self.native.reset_mock(side_effect=True)
        self.native.side_effect = AssertionError('已成功的绑定不再预检或写入')
        self.assertTrue(work.run(args)['replayed_receipt'])
        self.native.assert_not_called()

    def test_bind_requires_directory_and_owner_before_writing_intent(self):
        self.native.side_effect = lambda *a, **kw: []
        for directory, owner in [(str(self.root / 'absent'), 'Codex'),
                                 (self.file('ordinary-file', 'x'), 'Codex'), (str(self.root), ' ' )]:
            with self.subTest(directory=directory, owner=owner):
                with self.assertRaises((base.AdaptError, OSError)):
                    work.run(self.args('bind', directory=directory, owner=owner))
                self.assertEqual(self.receipts(), [])
        self.assertTrue(all(c.args[:2] == ('issue', 'runs') for c in self.native.call_args_list))

    def test_note_keeps_parent_and_remains_silent_even_with_mention(self):
        self.native.side_effect = lambda *a, **kw: {'id': 'note'}
        args = self.args('note', body_file=self.file('note.md', '[@Worker](mention://agent/worker)'))
        work.run(args)
        self.assertEqual(self.native.call_args.args[-2:], ('--parent', 'trigger'))
        self.assertTrue(self.native.call_args.kwargs['stdin'].startswith('/note\n'))
        self.assertTrue(work.run(args)['replayed_receipt'])
        self.assertEqual(self.native.call_count, 1)

    def test_deliver_uploads_silently_then_enters_review_without_accepting(self):
        self.native.side_effect = lambda *a, **kw: {'id': 'comment'}
        artifact = self.file('result.json', '{"verified": true}')
        args = self.args('deliver', body_file=self.file('result.md', '验证通过'), artifact=[artifact])
        result = work.run(args)
        self.assertFalse(result['accepted'])
        comment, update = self.native.call_args_list
        self.assertIn('--attachment', comment.args)
        self.assertIn(str(Path(artifact).resolve()), comment.args)
        self.assertEqual(comment.args[comment.args.index('--parent') + 1], 'trigger')
        self.assertTrue(comment.kwargs['stdin'].startswith('/note\n'))
        self.assertEqual(update.args, ('issue', 'update', 'issue', '--status', 'in_review', '--no-start'))
        self.assertTrue(work.run(args)['replayed_receipt'])
        self.assertEqual(self.native.call_count, 2)
        Path(artifact).write_text('{"changed": true}')
        with self.assertRaisesRegex(base.AdaptError, '不同输入'):
            work.run(args)
        self.assertEqual(self.native.call_count, 2)

    def test_deliver_requires_existing_artifact_before_remote_request(self):
        for artifacts in [[], [str(self.root / 'missing')]]:
            with self.subTest(artifacts=artifacts):
                with self.assertRaises(base.AdaptError):
                    work.run(self.args('deliver', body_file=self.file('result.md', '证据'), artifact=artifacts))
                self.assertEqual(self.receipts(), [])
        self.native.assert_not_called()

    def test_partial_delivery_stays_pending_and_cannot_upload_twice(self):
        self.native.side_effect = [{'id': 'uploaded'}, base.AdaptError('状态更新响应丢失')]
        args = self.args('deliver', body_file=self.file('result.md', '证据'), artifact=[self.file('result.json', '{}')])
        with self.assertRaises(base.AdaptError):
            work.run(args)
        self.assertEqual(self.receipts()[0]['state'], 'pending')
        with self.assertRaisesRegex(base.AdaptError, '请求结果未确认'):
            work.run(args)
        self.assertEqual(self.native.call_count, 2)

    def test_handoff_mentions_next_role_in_parent_thread_without_reassignment(self):
        self.native.side_effect = lambda *a, **kw: {'id': 'handoff', 'trigger_outcomes': [{'status': 'queued'}]}
        args = self.args('handoff', agent='worker', packet=self.file('handoff.json', json.dumps(self.handoff())))
        with patch.object(work, 'preflight', return_value={'id': 'worker-id', 'name': 'Worker'}) as preflight:
            work.run(args)
            self.assertTrue(preflight.call_args.args[-1])
            self.assertTrue(work.run(args)['replayed_receipt'])
            preflight.assert_called_once()
        self.native.assert_called_once()
        self.assertEqual(self.native.call_args.args[:3], ('issue', 'comment', 'add'))
        self.assertIn('--parent', self.native.call_args.args)
        self.assertTrue(self.native.call_args.kwargs['stdin'].startswith('[@Worker](mention://agent/worker-id)'))

    def test_background_dispatch_is_rejected_before_pending(self):
        args = self.args('dispatch', agent='worker', packet=self.file('handoff.json', json.dumps(self.handoff())))
        with patch.object(work, 'task_context', return_value=True):
            with self.assertRaisesRegex(base.AdaptError, 'handoff'):
                work.run(args)
        self.assertEqual(self.receipts(), [])
        self.native.assert_not_called()

    def test_recover_reads_runs_comments_and_receipts_without_replaying(self):
        with self.assertRaises(base.AdaptError):
            work.once('unknown', {'issue': 'issue'}, Mock(side_effect=base.AdaptError('响应丢失')))
        comment = dict(id='comment', parent_id='trigger', source_task_id='run', author_type='agent',
                       content='/note\n私有正文\n\nrequest-id: unknown', attachments=[{'id': 'attachment', 'filename': 'result.json'}])
        def native(*args, **kwargs):
            if args[:2] == ('issue', 'get'): return {'id': 'issue'}
            if args[:3] == ('issue', 'comment', 'list'): return [comment]
            if args[:2] == ('issue', 'runs'): return [{'id': 'run', 'status': 'completed'}]
            raise AssertionError(args)
        self.native.side_effect = native
        result = work.run(self.args('recover'))
        self.assertEqual(result['comments'][0]['request_ids'], ['unknown'])
        self.assertEqual(result['comments'][0]['attachments'][0]['id'], 'attachment')
        self.assertNotIn('content', result['comments'][0])
        self.assertEqual(result['receipts'][0]['state'], 'pending')
        self.assertEqual(self.receipts()[0]['state'], 'pending')
        self.assertEqual(self.native.call_count, 3)

    def test_malformed_handoff_is_rejected_before_cli_or_pending(self):
        for change in [dict(objective=' '), dict(directory=123), dict(required_commands=[{}]),
                       dict(required_mcp=['']), dict(artifacts='path')]:
            with self.subTest(change=change):
                args = self.args('handoff', agent='worker', packet=self.file('handoff.json', json.dumps(self.handoff(**change))))
                with self.assertRaises(base.AdaptError):
                    work.run(args)
                self.assertEqual(self.receipts(), [])
        self.native.assert_not_called()


class DispatchBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.machine = {'agents': {'worker': 'agent'}, 'daemon_id': 'daemon', 'skill_id': 'skill',
                        'runtimes': {'codex': {'id': 'runtime', 'provider': 'codex', 'profile_id': None}}}
        self.active = []
        self.mode = 'in_place'
        self.skills = [{'id': 'skill'}]
        self.handoff = {'directory': self.temp.name, 'required_commands': [], 'required_mcp': []}
        def native(*args, **kwargs):
            if args[:2] == ('agent', 'get'): return {'id': 'agent', 'runtime_id': 'runtime', 'model': 'fixed'}
            if args[:2] == ('runtime', 'list'):
                return [{'id': 'runtime', 'provider': 'codex', 'profile_id': None, 'daemon_id': 'daemon', 'status': 'online'}]
            if args[:2] == ('issue', 'runs'): return self.active
            if args[:2] == ('issue', 'get'): return {'project_id': 'project'}
            if args[:3] == ('project', 'resource', 'list'):
                return [{'resource_type': 'local_directory', 'resource_ref': {'daemon_id': 'daemon', 'local_path': self.temp.name, 'execution_mode': self.mode}}]
            if args[:3] == ('agent', 'skills', 'list'): return self.skills
            raise AssertionError(args)
        def config(path, default=None):
            return {'agents': [{'key': 'worker', 'runtime': 'codex', 'model': 'fixed'}]} if Path(path).name == 'agents.json' else {'runtimes': {}}
        for target, name, value in [(work, 'machine', lambda: self.machine), (work, 'cli', native), (work, 'read_json', config)]:
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_current_handoff_can_exclude_own_run_but_not_another_active_run(self):
        self.active = [{'id': 'current'}]
        with patch.object(work, 'task_context', return_value=True), patch.dict(os.environ, MULTICA_TASK_ID='current'):
            self.assertEqual(work.preflight('issue', 'worker', self.handoff, True)['id'], 'agent')
            self.active.append({'id': 'other'})
            with self.assertRaisesRegex(base.AdaptError, '活动 run'):
                work.preflight('issue', 'worker', self.handoff, True)

    def test_worktree_resource_requires_native_project_flow(self):
        self.mode = 'worktree'
        with self.assertRaisesRegex(base.AdaptError, 'in_place'):
            work.preflight('issue', 'worker', self.handoff)

    def test_required_mcp_is_blocked_without_actual_task_verifier(self):
        self.handoff['required_mcp'] = ['desktop-only-server']
        with self.assertRaisesRegex(base.AdaptError, 'MCP'):
            work.preflight('issue', 'worker', self.handoff)

    def test_missing_command_and_missing_shared_skill_are_blocked(self):
        self.handoff['required_commands'] = ['missing-tool']
        with patch('shutil.which', return_value=None), self.assertRaisesRegex(base.AdaptError, '缺少必需命令'):
            work.preflight('issue', 'worker', self.handoff)
        self.handoff['required_commands'] = []
        self.skills = []
        with self.assertRaisesRegex(base.AdaptError, '共享协作技能'):
            work.preflight('issue', 'worker', self.handoff)


if __name__ == '__main__':
    unittest.main()
