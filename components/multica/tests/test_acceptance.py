"""实机验收器的反例：错误身份、旧探针、错误评论线程不能产生通过证据。"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import acceptance
import adapt
from adaptation import AdaptError


class Evidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.key = 'codex-builder'
        self.fixture = {'root': str(self.root), 'issues': {self.key: 'issue'}}
        self.index = self.root / 'fixture.json'
        self.index.write_text(json.dumps(self.fixture))
        self.machine = {'agents': {self.key: 'agent'}, 'workspace_id': 'workspace', 'runtimes': {'codex': {'id': 'runtime'}}}
        self.report = {'agent_key': self.key, 'agent_id': 'agent', 'workspace_id': 'workspace',
                       'cwd': str(self.root), 'task_id': 'run', 'token_kind': 'task', 'calculation': 5,
                       'probe_sha256': hashlib.sha256(acceptance.PROBE.encode()).hexdigest(),
                       'task_contract': {k: True for k in ['MULTICA_TOKEN','MULTICA_TASK_ID','MULTICA_AGENT_ID','MULTICA_WORKSPACE_ID','MULTICA_SERVER_URL']}}
        (self.root / (self.key+'.json')).write_text(json.dumps(self.report))
        self.runs = [{'id': 'run', 'status': 'completed', 'agent_id': 'agent', 'runtime_id': 'runtime',
                      'workspace_id': 'workspace', 'work_dir': str(self.root), 'trigger_comment_id': 'trigger'}]
        self.comments = [self.comment('delivery', 'deliver')]
        self.comments[0]['attachments'] = [{'id': 'attachment', 'filename': self.key+'.json'}]
        for target, name, value in [(acceptance, 'STATE', self.root/'state'), (acceptance, 'INDEX', self.index),
                                    (acceptance, 'machine', lambda: self.machine), (acceptance, 'active_agents', lambda: [self.key]),
                                    (acceptance, 'cli', self.native)]:
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def comment(self, identity, action):
        return {'id': identity, 'parent_id': 'trigger', 'source_task_id': 'run',
                'author_type': 'agent', 'author_id': 'agent', 'attachments': [],
                'content': '/note\n验收证据\n\nrequest-id: run-'+action}

    def native(self, *args, **kwargs):
        if args[:2] == ('issue', 'runs'): return self.runs
        if args[:2] == ('issue', 'get'): return {'status': 'in_review'}
        if args[:3] == ('issue', 'comment', 'list'): return self.comments
        if args[:2] == ('attachment', 'download'):
            (Path(args[-1])/(self.key+'.json')).write_text(json.dumps(self.report))
            return 'downloaded'
        raise AssertionError(args)

    def value(self):
        return acceptance.check()[self.key]

    def test_complete_current_task_evidence_passes(self):
        value = self.value()
        self.assertTrue(acceptance.passed(value))
        self.assertEqual(value['comment_ids'], ['delivery'])

    def test_report_identity_directory_and_probe_version_must_match(self):
        good = self.value()
        for field in ['agent_key', 'agent_id', 'workspace_id', 'cwd', 'probe_sha256']:
            with self.subTest(field=field):
                value = copy.deepcopy(good)
                value['probe'][field] = 'unrelated'
                self.assertFalse(acceptance.passed(value))
        for field in ['agent_id', 'runtime_id', 'workspace_id', 'work_dir']:
            with self.subTest(run_field=field):
                value = copy.deepcopy(good)
                value['runs'][0][field] = 'unrelated'
                self.assertFalse(acceptance.passed(value))

    def test_comment_actor_source_and_parent_are_required(self):
        for field, bad in [('author_type', 'member'), ('author_id', 'other'),
                           ('source_task_id', 'old'), ('parent_id', 'wrong-thread')]:
            with self.subTest(field=field):
                original = copy.deepcopy(self.comments)
                for comment in self.comments: comment[field] = bad
                self.assertFalse(acceptance.passed(self.value()))
                self.comments = original

    def test_duplicate_final_or_missing_current_request_marker_fails(self):
        self.comments.append(copy.deepcopy(self.comments[0]))
        self.assertFalse(acceptance.passed(self.value()))
        self.comments.pop()
        self.comments[0]['content'] = '只有旧的完成说明'
        self.assertFalse(acceptance.passed(self.value()))

    def test_non_silent_comment_and_prefix_request_marker_cannot_certify_final(self):
        self.comments[0]['content'] = '普通回复\nrequest-id: run-deliver'
        self.assertFalse(acceptance.passed(self.value()))
        self.comments[0]['content'] = '/note\nrequest-id: run-deliver-other'
        self.assertFalse(acceptance.passed(self.value()))

    def test_old_attachment_content_cannot_replace_current_report(self):
        native = self.native
        def mismatch(*args, **kwargs):
            result = native(*args, **kwargs)
            if args[:2] == ('attachment', 'download'):
                (Path(args[-1])/(self.key+'.json')).write_text('{"task_id":"old"}')
            return result
        with patch.object(acceptance, 'cli', side_effect=mismatch):
            self.assertFalse(acceptance.passed(self.value()))

    def test_prepare_refreshes_existing_probe_without_creating_remote_objects(self):
        (self.root/'probe.py').write_text('old probe')
        with patch.object(acceptance, 'cli', return_value=[]) as native:
            self.assertEqual(acceptance.prepare(), self.fixture)
        self.assertEqual((self.root/'probe.py').read_text(), acceptance.PROBE)
        native.assert_called_once_with('issue', 'runs', 'issue', '--active')
        self.assertTrue((self.root/(self.key+'-packet.json')).exists())

    def test_prepare_cannot_overwrite_probe_during_active_run(self):
        (self.root/'probe.py').write_text('keep active probe')
        with patch.object(acceptance, 'cli', return_value=[{'id': 'running'}]):
            with self.assertRaisesRegex(AdaptError, '活动 run'):
                acceptance.prepare()
        self.assertEqual((self.root/'probe.py').read_text(), 'keep active probe')

    def test_runtime_code_changes_invalidate_previous_acceptance(self):
        (self.root/'scripts').mkdir()
        script = self.root/'scripts/work.py'
        script.write_text('version one')
        with patch.object(adapt, 'ROOT', self.root):
            m = {'agent_kit': str(self.root)}
            c = {'agents': [{'runtime': 'codex'}], 'skill_checks': []}
            previous = adapt.evidence_fingerprint(m, c)
            script.write_text('version two')
            self.assertNotEqual(previous, adapt.evidence_fingerprint(m, c))


if __name__ == '__main__':
    unittest.main()
