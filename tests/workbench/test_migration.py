"""用真实 Git 和 tar 验证迁机资料保全，不访问个人 HOME 或在线业务。"""
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts/workbench'))
from migration_projects import export_project, git, restore_project, validate_archive


class MigrationProjects(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi migration ')
        self.base = Path(self.temp.name).resolve()
        self.old = self.base/'old home'; self.old.mkdir()
        self.new = self.base/'new home'; self.new.mkdir()
        self.source = self.old/'Documents/project with spaces'; self.source.mkdir(parents=True)
        git(self.source, 'init', '--quiet', '--initial-branch=main')
        git(self.source, 'config', 'user.name', 'Migration Test')
        git(self.source, 'config', 'user.email', 'migration@example.invalid')
        (self.source/'.gitignore').write_text('.env\nprivate/\nnode_modules/\n')
        (self.source/'tracked').write_text('base\n')
        (self.source/'deleted').write_text('remove me\n')
        git(self.source, 'add', '.')
        git(self.source, 'commit', '--quiet', '-m', 'fixture')
        git(self.source, 'branch', 'other-local-branch')
        git(self.source, 'remote', 'add', 'origin', 'https://example.invalid/source.git')
        self.bundle = self.base/'project bundle'

    def tearDown(self):
        self.temp.cleanup()

    def test_real_roundtrip_preserves_index_worktree_refs_private_data_and_home_links(self):
        (self.source/'tracked').write_text('staged\n')
        git(self.source, 'add', 'tracked')
        (self.source/'tracked').write_text('unstaged\n')
        (self.source/'deleted').unlink()
        (self.source/'untracked').write_bytes(b'\x00binary\xff')
        (self.source/'.env').symlink_to(self.old/'.local/env-vault/.env')
        (self.source/'private').mkdir()
        (self.source/'private/original.pdf').write_bytes(b'private original')
        (self.source/'node_modules').mkdir()
        (self.source/'node_modules/cache').write_text('rebuild')
        metadata = export_project(self.source, self.bundle, self.old, business_data=True)
        target = restore_project(self.bundle, self.new, self.old)
        self.assertEqual(git(target, 'rev-parse', 'HEAD'), git(self.source, 'rev-parse', 'HEAD'))
        self.assertEqual(git(target, 'diff', '--cached', '--binary'), git(self.source, 'diff', '--cached', '--binary'))
        self.assertEqual(git(target, 'diff', '--binary'), git(self.source, 'diff', '--binary'))
        self.assertEqual(git(target, 'remote', 'get-url', 'origin').strip(), b'https://example.invalid/source.git')
        self.assertEqual(git(target, 'rev-parse', 'other-local-branch'), git(self.source, 'rev-parse', 'other-local-branch'))
        self.assertEqual((target/'untracked').read_bytes(), b'\x00binary\xff')
        self.assertEqual((target/'private/original.pdf').read_bytes(), b'private original')
        self.assertEqual((target/'.env').resolve(), self.new/'.local/env-vault/.env')
        self.assertFalse((target/'node_modules').exists())
        self.assertGreater(metadata['business_data_files'], 0)

    def test_detached_head_preserved(self):
        git(self.source, 'checkout', '--quiet', '--detach')
        export_project(self.source, self.bundle, self.old)
        target = restore_project(self.bundle, self.new, self.old)
        result = subprocess.run(['git', '-C', target, 'symbolic-ref', 'HEAD'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(git(target, 'rev-parse', 'HEAD'), git(self.source, 'rev-parse', 'HEAD'))

    def test_bundle_including_init_default_branch_restores_all_branches(self):
        probe = self.base/'default branch probe'; probe.mkdir()
        git(probe, 'init', '--quiet')
        default = git(probe, 'symbolic-ref', '--short', 'HEAD').decode().strip()
        if default != 'main':
            git(self.source, 'branch', default)
        export_project(self.source, self.bundle, self.old)
        target = restore_project(self.bundle, self.new, self.old)
        self.assertEqual(git(target, 'rev-parse', default), git(self.source, 'rev-parse', default))

    def test_all_stashes_and_order_are_preserved(self):
        for value in ('first stash', 'second stash'):
            (self.source/'tracked').write_text(value)
            git(self.source, 'stash', 'push', '--quiet', '--message', value)
        export_project(self.source, self.bundle, self.old)
        target = restore_project(self.bundle, self.new, self.old)
        self.assertEqual(git(target, 'stash', 'list', '--format=%H %gs'),
                         git(self.source, 'stash', 'list', '--format=%H %gs'))
        self.assertEqual(git(target, 'show', 'stash@{1}:tracked'), b'first stash')

    def test_existing_project_is_preserved(self):
        export_project(self.source, self.bundle, self.old)
        target = self.new/'Documents/project with spaces'
        target.mkdir(parents=True)
        (target/'keep').write_text('existing')
        with self.assertRaises(ValueError):
            restore_project(self.bundle, self.new, self.old)
        self.assertEqual((target/'keep').read_text(), 'existing')

    def test_export_inside_source_rejected(self):
        with self.assertRaises(ValueError):
            export_project(self.source, self.source/'export', self.old)
        self.assertFalse((self.source/'export').exists())

    def test_traversal_archive_rejected(self):
        path = self.base/'bad.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            item = tarfile.TarInfo('../escape'); item.size = 1
            archive.addfile(item, io.BytesIO(b'x'))
        with self.assertRaises(ValueError):
            validate_archive(path)

    def test_unsafe_link_leaves_no_partial_project(self):
        (self.source/'unsafe').symlink_to('/outside-home')
        export_project(self.source, self.bundle, self.old)
        with self.assertRaises(ValueError):
            restore_project(self.bundle, self.new, self.old)
        parent = self.new/'Documents'
        self.assertFalse((parent/'project with spaces').exists())
        self.assertEqual(list(parent.glob('.migration-*')), [])

    def test_parent_link_outside_home_rejected(self):
        export_project(self.source, self.bundle, self.old)
        outside = self.base/'outside'; outside.mkdir()
        (self.new/'Documents').symlink_to(outside)
        with self.assertRaises(ValueError):
            restore_project(self.bundle, self.new, self.old)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
