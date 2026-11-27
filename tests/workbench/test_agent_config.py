"""验证档位发布、配置归属和会话解析，所有写入都在临时目录。"""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts/workbench'))

from agent_config import BINDING, current_project, initialize_project, session_brief


class AgentConfig(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='feipi config ')
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name).resolve()
        self.home = self.scratch/'home'
        self.home.mkdir()
        self.codex = self.scratch/'custom-codex-home'
        self.codex.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.codex),
                        PYTHONDONTWRITEBYTECODE='1')

    def cli(self, *args, success=True):
        run = subprocess.run([str(ROOT/'workbench'), *map(str, args)], env=self.env,
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0 if success else 1, run.stdout+run.stderr)
        return run

    def fixture(self, name, ignored=True):
        project = self.scratch/name
        project.mkdir()
        subprocess.run(['git', 'init', '-q', str(project)], check=True)
        subprocess.run(['git', '-C', str(project), 'config', 'remote.origin.url',
                        f'git@github.com:iampkuhz/{name}.git'], check=True)
        (project/'.gitignore').write_text('/tmp/\n' if ignored else '')
        catalog = json.loads((ROOT/'templates/agent/projects.json').read_text())
        for entry in catalog[f'github.com/iampkuhz/{name}'].values():
            target = project/entry
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('项目自己的入口\n')
        return project

    def test_codex_profiles_use_custom_home_and_preserve_user_files(self):
        config = self.codex/'config.toml'
        config.write_text('model = "kept-local"\n')
        self.cli('doctor', 'codex', success=False)
        self.cli('install', 'codex')
        review = self.codex/'feipi-review.config.toml'
        first_mtime = review.stat().st_mtime_ns
        self.cli('install', 'codex')
        self.cli('doctor', 'codex')
        self.assertEqual(first_mtime, review.stat().st_mtime_ns)
        self.assertEqual(config.read_text(), 'model = "kept-local"\n')
        self.assertFalse((self.home/'.codex').exists())
        review.write_text('# personal edit\n')
        self.cli('doctor', 'codex', success=False)
        self.assertIn('保留原文件', self.cli('install', 'codex', success=False).stderr)
        self.assertEqual(review.read_text(), '# personal edit\n')

    def test_codex_collision_leaves_other_profile_untouched(self):
        review = self.codex/'feipi-review.config.toml'
        review.symlink_to(self.scratch/'foreign')
        self.cli('install', 'codex', success=False)
        self.assertTrue(review.is_symlink())
        self.assertFalse((self.codex/'feipi-develop.config.toml').exists())

    def test_project_binds_existing_entries_and_selects_mode(self):
        repository = self.fixture('lexiflow')
        self.cli('session', 'review', repository, success=False)
        self.cli('project', 'init', repository/'harness')
        document = repository/BINDING
        mtime = document.stat().st_mtime_ns
        self.cli('project', 'init', repository)
        self.assertEqual(document.stat().st_mtime_ns, mtime)
        self.cli('project', 'doctor', repository)
        result = self.cli('session', 'review', repository).stdout
        self.assertIn(str(repository), result)
        self.assertIn('docs/reference/delivery-gate.md', result)
        self.assertIn('--sandbox read-only --ask-for-approval never', result)
        result = self.cli('session', 'verify', repository).stdout
        self.assertIn('--sandbox workspace-write --ask-for-approval on-request', result)
        self.assertIn('验收身份', result)

    def test_linked_checkout_gets_its_own_binding(self):
        repository = self.fixture('feipi-session-browser')
        def git(*args):
            return subprocess.run(['git', '-C', str(repository), *map(str, args)],
                                  capture_output=True, text=True, check=True)
        git('add', '.')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            'commit', '-m', 'test project')
        linked = self.scratch/'linked checkout'
        git('worktree', 'add', '--detach', linked, 'HEAD')
        self.cli('project', 'init', linked/'harness')
        self.assertTrue((linked/BINDING).is_file())
        self.assertFalse((repository/BINDING).exists())
        self.assertIn(str(linked), self.cli('session', 'review', linked).stdout)

    def test_project_bundle_upgrade_requires_reinitialization(self):
        source = self.scratch/'source'
        shutil.copytree(ROOT/'templates/agent', source/'templates/agent')
        shutil.copytree(ROOT/'components/codex', source/'components/codex')
        project = self.fixture('feipi-session-browser')
        with redirect_stdout(io.StringIO()):
            initialize_project(source, project)
            old = (project/BINDING).read_bytes()
            (source/'templates/agent/review.md').write_text('新版审阅模板\n')
            with self.assertRaisesRegex(ValueError, '配置缺失或过期'):
                session_brief(source, project, 'review')
            initialize_project(source, project)
        self.assertNotEqual((project/BINDING).read_bytes(), old)
        _, document = current_project(source, project)
        self.assertEqual(document['entries']['evidence'], 'docs/gates/gate-control-plane.md')

    def test_project_rejects_unignored_path_and_foreign_config(self):
        project = self.fixture('feipi-agent-kit', ignored=False)
        self.assertIn('忽略目录', self.cli('project', 'init', project, success=False).stderr)
        (project/'.gitignore').write_text('/tmp/\n')
        binding = project/BINDING
        binding.parent.mkdir(parents=True)
        binding.write_text('{"owner": "another tool"}')
        self.assertIn('保留原文件', self.cli('project', 'init', project, success=False).stderr)
        self.assertEqual(binding.read_text(), '{"owner": "another tool"}')

    def test_project_rejects_writing_through_symlink(self):
        project = self.fixture('feipi-agent-kit')
        other = self.scratch/'unrelated'
        other.mkdir()
        (project/'tmp').symlink_to(other, target_is_directory=True)
        self.assertIn('符号链接', self.cli('project', 'init', project, success=False).stderr)
        self.assertEqual(list(other.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
