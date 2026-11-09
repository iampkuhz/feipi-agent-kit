"""项目定位、读入边界与显式启用；不访问个人 Multica。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/project.py'
spec = importlib.util.spec_from_file_location('project_context', SCRIPT)
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)


class Project(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.release = self.base / 'release'
        self.release.mkdir()
        self.config = {'schema': 1, 'profile': 'isolated', 'server_url': 'http://localhost:8080',
                       'app_url': 'http://localhost:3000', 'workspace_id': 'workspace',
                       'projects': {'demo': {'id': 'project', 'root': str(self.repo), 'release': str(self.release)}}}
        self.config_file = self.base / 'machine.json'
        self.config_file.write_text(json.dumps(self.config))
        clean = {k: v for k, v in os.environ.items() if not k.startswith('MULTICA_')}
        clean.update(MULTICA_MACHINE_CONFIG=str(self.config_file), MULTICA_ENTRY_BACKUPS=str(self.base / 'backups'))
        patcher = patch.dict(os.environ, clean, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = []

    def native(self, config, *args):
        self.calls.append(args)
        if args == ('workspace', 'get'):
            return {'id': 'workspace', 'slug': 'my-space'}
        if args == ('project', 'get', 'project'):
            return {'id': 'project', 'workspace_id': 'workspace', 'title': '演示项目'}
        raise AssertionError(args)

    def ctx(self, directory=None):
        with patch.object(project, 'cli', side_effect=self.native):
            return project.context(self.config, directory or self.repo)

    def test_subdirectory_and_release_resolve_without_enabling(self):
        child = self.repo / 'child'
        child.mkdir()
        ctx = self.ctx(child)
        self.assertEqual(ctx['project_url'], 'http://localhost:3000/my-space/projects/project')
        self.assertEqual(ctx['directory'], str(child))
        self.assertEqual(ctx['entry_file'], str(self.repo / 'AGENTS.md'))
        self.assertFalse(ctx['enabled'])
        release = self.ctx(self.release)
        self.assertEqual(release['directory_role'], 'release')
        self.assertEqual(release['entry_file'], str(self.release / 'AGENTS.md'))

    def test_unknown_directory_and_explicit_wrong_project_fail_before_network(self):
        for directory, key in [(self.base, None), (self.repo, 'unknown')]:
            with patch.object(project, 'cli') as cli, self.assertRaises(project.ContextError):
                project.context(self.config, directory, key)
            cli.assert_not_called()

    def test_same_path_ambiguity_requires_real_explicit_selection(self):
        self.config['projects']['other'] = dict(self.config['projects']['demo'])
        with self.assertRaises(project.ContextError):
            project.locate(self.config, self.repo)
        self.assertEqual(project.locate(self.config, self.repo, 'demo')['project_key'], 'demo')

    def test_project_key_conflict_and_duplicates_fail(self):
        for text in ['Multica 项目键：`other`\n', 'Multica 项目键：`demo`\nMultica 项目键：`demo`\n']:
            (self.repo / 'AGENTS.md').write_text(text)
            with self.assertRaises(project.ContextError):
                project.locate(self.config, self.repo)

    def test_symlink_directory_resolves_to_actual_root(self):
        link = self.base / 'linked'
        link.symlink_to(self.repo, target_is_directory=True)
        self.assertEqual(self.ctx(link)['directory'], str(self.repo))

    def test_worktree_is_same_project_but_not_original_directory(self):
        def git(*args):
            subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)
        git('init', '-q')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture')
        worktree = self.base / 'worktree'
        git('worktree', 'add', '--detach', str(worktree))
        child = worktree / 'child'
        child.mkdir()
        ctx = self.ctx(child)
        self.assertEqual(ctx['directory_role'], 'root-worktree')
        self.assertEqual(ctx['directory'], str(child))
        self.assertEqual(ctx['entry_file'], str(worktree / 'AGENTS.md'))
        nested = self.repo / 'nested'
        nested.mkdir()
        subprocess.run(['git', '-C', str(nested), 'init', '-q'], check=True)
        with self.assertRaises(project.ContextError):
            project.locate(self.config, nested)

    def test_bound_subdirectory_does_not_modify_outer_repository_entry(self):
        subprocess.run(['git', '-C', str(self.base), 'init', '-q'], check=True)
        self.assertEqual(self.ctx()['entry_file'], str(self.repo / 'AGENTS.md'))

    def test_cli_default_workspace_must_match_without_silent_switch(self):
        with patch.object(project, 'cli', return_value={'id': 'wrong', 'slug': 'wrong'}) as cli:
            with self.assertRaisesRegex(project.ContextError, '当前工作区'):
                project.context(self.config, self.repo)
            self.assertEqual(cli.call_args.args[1:], ('workspace', 'get'))
            cli.assert_called_once()

    def test_project_identity_mismatch_is_not_accepted(self):
        with patch.object(project, 'cli', side_effect=[{'id': 'workspace', 'slug': 'x'},
                                                     {'id': 'project', 'workspace_id': 'other'}]):
            with self.assertRaises(project.ContextError):
                project.context(self.config, self.repo)

    def test_authentication_partial_and_cross_server_fail_without_exposing_secret(self):
        with patch.dict(os.environ, {'MULTICA_TOKEN': 'mat_private-test'}):
            with self.assertRaises(project.ContextError) as error:
                project.machine()
            self.assertNotIn('mat_private-test', str(error.exception))
        env = dict(zip(project.TASK_FIELDS, ['mat_private-test', 'run', 'agent', 'workspace', 'http://wrong']))
        with patch.dict(os.environ, env), self.assertRaises(project.ContextError):
            project.machine()

    def test_connection_url_cannot_embed_credentials(self):
        self.config['app_url'] = 'https://name:private@example.invalid'
        self.config_file.write_text(json.dumps(self.config))
        with self.assertRaises(project.ContextError) as error:
            project.machine()
        self.assertNotIn('private', str(error.exception))

    def test_native_wrapper_preserves_task_identity_and_redacts_error(self):
        result = subprocess.CompletedProcess([], 1, '', 'secret-token-should-not-print')
        with patch.object(project.subprocess, 'run', return_value=result) as run:
            with self.assertRaises(project.ContextError) as error:
                project.cli(self.config, 'workspace', 'get')
            self.assertNotIn('secret-token', str(error.exception))
            self.assertEqual(run.call_args.kwargs['env']['MULTICA_PERSONAL_PROFILE'], 'isolated')
        env = dict(zip(project.TASK_FIELDS, ['mat_test', 'run', 'agent', 'workspace', 'http://localhost:8080']))
        with patch.dict(os.environ, env), patch.object(project.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{}', '')) as run:
            project.cli(self.config, 'workspace', 'get')
            self.assertNotIn('MULTICA_PERSONAL_PROFILE', run.call_args.kwargs['env'])
            self.assertEqual(run.call_args.kwargs['env']['MULTICA_TASK_ID'], 'run')

    def test_enable_preview_backup_idempotency_and_release_separation(self):
        path = self.repo / 'AGENTS.md'
        original = b'# Existing rules\nKeep everything.\n'
        path.write_bytes(original)
        ctx = self.ctx()
        self.assertFalse(project.enable(ctx)['applied'])
        self.assertEqual(path.read_bytes(), original)
        applied = project.enable(ctx, True)
        self.assertEqual(Path(applied['backup']).read_bytes(), original)
        self.assertTrue(path.read_bytes().startswith(original))
        ctx = self.ctx()
        self.assertTrue(ctx['enabled'])
        self.assertFalse(project.enable(ctx, True)['changed'])
        self.assertEqual(path.read_text().count(project.BEGIN), 1)
        self.assertFalse(self.ctx(self.release)['enabled'])

    def test_enable_does_not_overwrite_broken_or_symlink_rules(self):
        path = self.repo / 'AGENTS.md'
        path.write_text(project.BEGIN + '\nnot finished')
        with self.assertRaises(project.ContextError):
            project.enable(self.ctx(), True)
        path.unlink()
        target = self.base / 'rules.md'
        target.write_text('original')
        path.symlink_to(target)
        with self.assertRaises(project.ContextError):
            project.enable(self.ctx(), True)
        self.assertEqual(target.read_text(), 'original')

    def test_enable_refuses_background_task(self):
        ctx = self.ctx()
        with patch.dict(os.environ, {'MULTICA_TASK_ID': 'run'}), self.assertRaises(project.ContextError):
            project.enable(ctx, True)
        self.assertFalse((self.repo / 'AGENTS.md').exists())

    def issue(self, **values):
        return dict(id='issue', project_id='project', workspace_id='workspace', identifier='TASK-1',
                    title='修复进度查询', status='backlog', **values)

    def test_find_is_project_scoped_and_marks_incomplete_empty_matches(self):
        ctx = self.ctx()
        with patch.object(project, 'cli', return_value={'issues': [self.issue()], 'has_more': True}) as cli:
            result = project.find(self.config, ctx, 'unmatched', 1, 0)
        self.assertEqual(result['issues'], [])
        self.assertTrue(result['has_more'])
        self.assertEqual(result['next_offset'], 1)
        self.assertIn('--fields', cli.call_args.args)
        self.assertEqual(cli.call_args.args[cli.call_args.args.index('--project') + 1], 'project')

    def test_read_refuses_issue_from_other_project_before_reading_comments(self):
        ctx = self.ctx()
        issue = self.issue()
        issue['project_id'] = 'other'
        with patch.object(project, 'cli', return_value=issue) as cli:
            with self.assertRaises(project.ContextError):
                project.read(self.config, ctx, 'TASK-1')
            cli.assert_called_once()

    def test_read_bounds_body_comments_and_uses_only_active_runs(self):
        ctx = self.ctx()
        comments = [{'id': str(n), 'content': 'x' * 2000, 'reply_count': 3,
                     'created_at': '2026-11-%02d' % n} for n in range(1, 9)]
        with patch.object(project, 'cli', side_effect=[self.issue(description='d' * 3000),
                                                     [{'id': 'run', 'status': 'running', 'error_message': 'private'}], comments]) as cli:
            result = project.read(self.config, ctx, 'TASK-1')
        self.assertEqual(len(result['description']), 1600)
        self.assertTrue(result['description_truncated'])
        self.assertEqual(len(result['comments']), 5)
        self.assertTrue(result['comments_may_be_incomplete'])
        self.assertEqual(result['comments'][0]['id'], '8')
        self.assertEqual(cli.call_args_list[1].args[1:], ('issue', 'runs', 'issue', '--active'))
        self.assertEqual(cli.call_args_list[2].args[-2:], ('--roots-only', '--summary'))
        self.assertNotIn('error_message', result['active_runs'][0])

    def test_read_expands_selected_thread_with_bounded_native_tail(self):
        ctx = self.ctx()
        with patch.object(project, 'cli', side_effect=[self.issue(description='d' * 3000), [], []]) as cli:
            result = project.read(self.config, ctx, 'TASK-1', 'thread', 3, True)
        self.assertEqual(len(result['description']), 3000)
        self.assertFalse(result['description_truncated'])
        self.assertEqual(cli.call_args.args[-4:], ('--thread', 'thread', '--tail', '3'))
        self.assertTrue(result['comments_may_be_incomplete'])


if __name__ == '__main__':
    unittest.main()
