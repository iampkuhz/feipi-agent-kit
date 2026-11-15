"""验证切换与回收的边界，全部使用临时 HOME/源码。"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import subprocess
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('workbench', Path(__file__).resolve().parents[2]/'scripts/workbench/main.py')
wb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wb)


class Recovery(unittest.TestCase):
    def test_startup_failure_restores_all_managed_plists_including_session_browser(self):
        with tempfile.TemporaryDirectory(prefix='feipi startup backup ') as scratch:
            root = Path(scratch); runtime = root/'runtime'; home = root/'home'
            script = runtime/'services/tools/runtime/startup.py'
            script.parent.mkdir(parents=True); script.write_text('fixture')
            batch = root/'backup'
            with patch.object(wb, 'HOME', home), patch.object(wb, 'RUNTIME', runtime), \
                    patch.object(wb, 'backup', return_value=batch) as backup, \
                    patch.object(wb, 'run', side_effect=subprocess.CalledProcessError(1, 'install')), \
                    patch.object(wb, 'restore') as restore, patch('builtins.print'), \
                    self.assertRaises(subprocess.CalledProcessError):
                wb.service('startup', ['install'])
            paths = backup.call_args.args[1]
            self.assertIn(home/'Library/LaunchAgents/com.feipi.session-browser.plist', paths)
            self.assertEqual(len(paths), 3)
            restore.assert_called_once_with(batch)

    def test_mac_doctor_detects_installed_nvm_node_outside_inherited_path(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(prefix='feipi nvm doctor ') as scratch:
            home = Path(scratch); nvm = home/'.nvm'; nvm.mkdir(); (nvm/'nvm.sh').write_text('fixture')
            runtime = home/'runtime'; target = runtime/'mac/zsh/.zshrc'
            target.parent.mkdir(parents=True); target.write_text('fixture')
            (home/'.zshrc').symlink_to(target)
            state = home/'state'; state.mkdir(); (state/'mac.json').write_text('{}')
            with patch.object(wb, 'HOME', home), patch.object(wb, 'RUNTIME', runtime), \
                    patch.object(wb, 'STATE', state), patch.object(wb, 'differences', return_value=[]), \
                    patch.dict(wb.os.environ, {'NVM_DIR': str(nvm)}), \
                    patch.object(wb.shutil, 'which', side_effect=lambda name, **kwargs: None if name == 'node' else '/mock/'+name), \
                    patch.object(wb.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='/nvm/bin/node\nv26.13.1\n11.20.0\n')) as run, \
                    patch('builtins.print'):
                self.assertEqual(wb.doctor('mac'), 0)
                self.assertEqual(run.call_args.args[0], ['bash', str(wb.ROOT/'components/mac/bootstrap/environment.sh'), 'check'])

    def test_mac_doctor_finds_homebrew_tools_outside_ssh_path(self):
        with tempfile.TemporaryDirectory(prefix='feipi ssh doctor ') as scratch:
            home = Path(scratch); runtime = home/'runtime'; target = runtime/'mac/zsh/.zshrc'
            target.parent.mkdir(parents=True); target.write_text('fixture')
            (home/'.zshrc').symlink_to(target)
            state = home/'state'; state.mkdir(); (state/'mac.json').write_text('{}')
            def which(name, path=None):
                if name in ['brew', 'nvim', 'podman']:
                    return '/opt/homebrew/bin/'+name if path and '/opt/homebrew/bin' in path.split(':') else None
                return '/usr/bin/'+name
            with patch.object(wb, 'HOME', home), patch.object(wb, 'RUNTIME', runtime), \
                    patch.object(wb, 'STATE', state), patch.object(wb, 'differences', return_value=[]), \
                    patch.object(wb.shutil, 'which', side_effect=which), patch('builtins.print'):
                self.assertEqual(wb.doctor('mac'), 0)

    def test_mac_doctor_accepts_canonical_target_under_home_alias(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            home = root/'home'; home.mkdir()
            alias = root/'home-alias'; alias.symlink_to(home)
            runtime = alias/'.local/share/feipi-workbench'
            target = runtime/'mac/zsh/.zshrc'
            target.parent.mkdir(parents=True); target.write_text('fixture')
            (home/'.zshrc').symlink_to(target.resolve())
            state = root/'state'; state.mkdir(); (state/'mac.json').write_text('{}')
            with patch.object(wb, 'HOME', alias), patch.object(wb, 'RUNTIME', runtime), \
                 patch.object(wb, 'STATE', state), patch.object(wb, 'differences', return_value=[]), \
                 patch.object(wb.shutil, 'which', return_value='/mock/bin'), patch('builtins.print'):
                self.assertEqual(wb.doctor('mac'), 0)

    def test_mac_install_uses_shared_orchestration_and_rejects_conflict_first(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); home = root/'home'; home.mkdir()
            with patch.object(wb, 'ROOT', root), patch.object(wb, 'HOME', home), \
                 patch.object(wb, 'run') as run, patch('builtins.print'):
                wb.install('mac')
                run.assert_called_once_with(['bash', root/'components/mac/bootstrap/run.sh', 'install', '--dependencies-only'])
                run.reset_mock()
                (home/'bin').mkdir()
                with self.assertRaisesRegex(ValueError, '先合并'):
                    wb.install('mac')
                run.assert_not_called()

    def test_mac_apps_install_uses_the_authorization_aware_entry(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); home = root/'home'; home.mkdir()
            with patch.object(wb, 'ROOT', root), patch.object(wb, 'HOME', home), \
                 patch.object(wb, 'run') as run, patch.object(wb.shutil, 'which', return_value='/mock/brew'), \
                 patch('builtins.print'):
                wb.install('mac', apps=True)
                self.assertEqual([entry.args[0] for entry in run.call_args_list[-2:]], [
                    ['bash', root/'components/mac/bootstrap/apps.sh', 'install'],
                    ['bash', root/'components/mac/bootstrap/desktop-extras.sh', 'install'],
                ])
                with self.assertRaisesRegex(ValueError, '只适用于'):
                    wb.install('services', apps=True)

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
