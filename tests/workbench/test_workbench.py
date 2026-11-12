"""验证切换与回收的边界，全部使用临时 HOME/源码。"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('workbench', Path(__file__).resolve().parents[2]/'scripts/workbench/main.py')
wb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wb)


class Recovery(unittest.TestCase):
    def test_targeted_skill_publish_backs_up_only_selected_client_and_skill(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            name = 'feipi-test-maintain-records'
            source = root/'skills/authoring'/name
            (source/'scripts').mkdir(parents=True)
            (source/'SKILL.md').write_text('fixture')
            (source/'maintenance').mkdir()
            (source/'maintenance/setup.sh').write_text('# $REPO_ROOT/maintenance-only/resource.txt\n')
            (root/'maintenance-only').mkdir()
            home = root/'home'
            codex = home/'.codex'
            with patch.object(wb, 'ROOT', root), patch.object(wb, 'HOME', home), \
                 patch.dict(wb.os.environ, {'CODEX_HOME':str(codex)}), \
                 patch.object(wb, 'mappings', return_value={}), patch.object(wb, 'backup', return_value=root/'backup') as backup, \
                 patch.object(wb, 'run') as run, patch.object(wb, 'receipt'), patch('builtins.print'):
                wb.apply('skills', agent='codex', skill=name)
                backup.assert_called_once_with('skills', [codex/'skills'/name])
                run.assert_called_once_with(['bash', root/'scripts/install_skills.sh', '--copy', '--agent', 'codex', '--skill', name])

    def test_skill_mapping_excludes_nested_maintenance(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root/'skills/authoring/feipi-example-review-rules'
            runtime = source/'references/rules.md'
            maintenance = source/'references/examples/maintenance/design.md'
            maintenance.parent.mkdir(parents=True)
            runtime.write_text('runtime')
            maintenance.write_text('source only')
            home = root/'home'
            (home/'.codex').mkdir(parents=True)
            with patch.object(wb, 'ROOT', root), patch.object(wb, 'HOME', home), \
                 patch.object(wb, 'source_files', return_value=[runtime, maintenance]):
                pairs = wb.mappings('skills')
            self.assertEqual(list(pairs), ['codex/feipi-example-review-rules/references/rules.md'])

    def test_skill_selection_rejects_other_components_and_unsafe_names(self):
        with self.assertRaisesRegex(ValueError, '只适用'):
            wb.apply('mac', agent='codex')
        with self.assertRaisesRegex(ValueError, '无效'):
            wb.apply('skills', skill='../../escape')

    def test_multica_diff_detects_runtime_code_without_expanding_capture(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root/'components/multica/scripts/adapt.py'
            source.parent.mkdir(parents=True)
            source.write_text('old code')
            home = root/'home'
            live = home/'.local/share/multica/ops/scripts/adapt.py'
            live.parent.mkdir(parents=True)
            live.write_text('newer published code')
            with patch.object(wb, 'ROOT', root), patch.object(wb, 'HOME', home), patch.object(wb, 'mappings', side_effect=lambda _: {}), patch.object(wb, 'source_files', side_effect=lambda p: [source] if p.name == 'scripts' else []), patch('builtins.print'):
                self.assertEqual(wb.differences('multica', show=False), ['scripts/adapt.py'])
                with self.assertRaisesRegex(ValueError, '不在允许回收范围'):
                    wb.capture('multica', ['scripts/adapt.py'])
            self.assertEqual(source.read_text(), 'old code')

    def test_failed_mac_publish_restores_existing_links_and_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root/'home'; home.mkdir()
            runtime = root/'runtime'; (runtime/'mac').mkdir(parents=True)
            (runtime/'mac/keep').write_text('previous runtime')
            original = root/'original'; original.write_text('previous config')
            (home/'.zshrc').symlink_to(original)
            with patch.object(wb, 'HOME', home), patch.object(wb, 'RUNTIME', runtime), patch.object(wb, 'STATE', root/'state'), patch.object(wb, 'mappings', return_value={}), patch.object(wb, 'snapshot', side_effect=OSError('disk write failed')):
                with self.assertRaises(OSError): wb.apply('mac')
            self.assertTrue((home/'.zshrc').is_symlink())
            self.assertEqual((home/'.zshrc').read_text(), 'previous config')
            self.assertEqual((runtime/'mac/keep').read_text(), 'previous runtime')
            self.assertFalse((home/'bin').exists())

    def test_backup_restores_symlinks_files_absence_and_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root/'source'; src.write_text('source')
            link = root/'link'; link.symlink_to(src)
            file = root/'file'; file.write_text('old')
            missing = root/'missing'
            tree = root/'tree'; tree.mkdir(); (tree/'keep').write_text('data')
            with patch.object(wb, 'STATE', root/'state'):
                batch = wb.backup('test', [link, file, missing, tree])
                link.unlink(); link.write_text('new')
                file.write_text('new'); missing.write_text('added')
                (tree/'keep').write_text('new'); (tree/'extra').write_text('new')
                wb.restore(batch)
            self.assertTrue(link.is_symlink())
            self.assertEqual(file.read_text(), 'old')
            self.assertFalse(missing.exists())
            self.assertEqual((tree/'keep').read_text(), 'data')
            self.assertFalse((tree/'extra').exists())
            self.assertEqual(src.read_text(), 'source')

    def test_capture_rejects_secret_before_writing_any_selected_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root/'config.json'; src.write_text('{}')
            live = root/'live.json'; live.write_text('{"apiKey":"do-not-copy"}')
            pairs = {'config.json': (src, live)}
            with patch.object(wb, 'mappings', return_value=pairs):
                with self.assertRaises(ValueError): wb.capture('openclaw', ['config.json'])
                with self.assertRaises(ValueError): wb.capture('openclaw', ['../../anything'])
            self.assertEqual(src.read_text(), '{}')

    def test_secret_ref_is_allowed(self):
        wb.check_public(Path('openclaw.json'), b'{"apiKey":{"source":"env","id":"KEY"}}')

    def test_diff_does_not_print_private_content(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root/'source'; src.write_text('old')
            live = root/'live'; live.write_text('secret-content')
            with patch.object(wb, 'STATE', root/'state'), patch.object(wb, 'mappings', return_value={'config':(src,live)}), patch('builtins.print') as out:
                self.assertEqual(wb.differences('mac'), ['config'])
            self.assertNotIn('secret-content', str(out.call_args_list))
            self.assertIn('secret-content', (root/'state/diff/mac/config.diff').read_text())


if __name__ == '__main__':
    unittest.main()
