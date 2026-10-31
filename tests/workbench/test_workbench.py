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
