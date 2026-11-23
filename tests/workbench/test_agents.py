"""覆盖 Agent CLI 查找、补装渠道和只读边界。"""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('mac_agents', ROOT/'components/mac/bootstrap/agents.py')
agents = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agents)


class AgentInstaller(unittest.TestCase):
    def test_existing_codex_is_preserved_while_missing_qwen_is_installed(self):
        paths = ['/brew/bin/codex', None, '/local/bin/claude', '/local/bin/qodercli', '/npm/bin/qwen']
        with patch.object(agents.shutil, 'which', side_effect=paths), \
                patch.object(agents.subprocess, 'run') as run, \
                patch('sys.argv', ['agents.py', 'install']):
            agents.main()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0],
                         ('npm', 'install', '-g', '--no-audit', '--no-fund', '@qwen-code/qwen-code@latest'))

    def test_missing_codex_is_installed_with_homebrew(self):
        paths = [None, '/npm/bin/qwen', '/local/bin/claude', '/local/bin/qodercli', '/brew/bin/codex']
        with patch.object(agents.shutil, 'which', side_effect=paths), \
                patch.object(agents.subprocess, 'run') as run, \
                patch('sys.argv', ['agents.py', 'install']):
            agents.main()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ('brew', 'install', '--cask', 'codex'))

    def test_plan_does_not_download_or_install(self):
        with patch.object(agents.shutil, 'which', return_value=None), \
                patch.object(agents.subprocess, 'run') as run, patch('sys.argv', ['agents.py', 'plan']):
            agents.main()
        run.assert_not_called()

    def test_check_fails_without_installing_missing_tools(self):
        with patch.object(agents.shutil, 'which', return_value=None), \
                patch.object(agents.subprocess, 'run') as run, \
                patch('sys.argv', ['agents.py', 'check']), self.assertRaisesRegex(ValueError, '缺少 Agent CLI'):
            agents.main()
        run.assert_not_called()

    def test_successful_install_must_put_command_on_path(self):
        paths = [None, '/npm/bin/qwen', '/local/bin/claude', '/local/bin/qodercli', None]
        with patch.object(agents.shutil, 'which', side_effect=paths), \
                patch.object(agents.subprocess, 'run'), patch('sys.argv', ['agents.py', 'install']), \
                self.assertRaisesRegex(ValueError, 'codex 安装后未出现在 PATH'):
            agents.main()


if __name__ == '__main__':
    unittest.main()
