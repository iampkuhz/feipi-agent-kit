"""锁定 CLI 安装的冲突、摘要与只读边界；真实下载/执行另在干净 Mac 验收。"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('mac_agents', ROOT/'components/mac/bootstrap/agents.py')
agents = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agents)


class AgentInstaller(unittest.TestCase):
    def test_conflict_is_found_before_any_install(self):
        with patch.object(agents, 'version', side_effect=[None, '9.9.9']), \
                patch.object(agents, 'command') as command, \
                patch('sys.argv', ['agents.py', 'install']), self.assertRaises(ValueError):
            agents.main()
        command.assert_not_called()

    def test_plan_does_not_download_or_install(self):
        with patch.object(agents, 'version', return_value=None), \
                patch.object(agents, 'command') as command, patch('sys.argv', ['agents.py', 'plan']):
            agents.main()
        command.assert_not_called()

    def test_registry_integrity_mismatch_stops_before_npm_install(self):
        with patch.object(agents, 'version', return_value=None), \
                patch.object(agents, 'command', return_value='"sha512-changed"') as command, \
                patch('sys.argv', ['agents.py', 'install']), self.assertRaises(ValueError):
            agents.main()
        self.assertEqual(len(command.call_args_list), 1)
        self.assertEqual(command.call_args.args[0][:2], ['npm', 'view'])

    def test_native_hash_mismatch_never_publishes_program(self):
        with tempfile.TemporaryDirectory(prefix='feipi agent integrity ') as scratch:
            home = Path(scratch)
            def download(args, **kwargs):
                Path(args[-1]).write_bytes(b'corrupt download')
            spec = next(item for item in agents.specs() if item['name'] == 'claude')
            with patch.object(agents, 'HOME', home), \
                    patch.object(agents.platform, 'system', return_value='Darwin'), \
                    patch.object(agents.platform, 'machine', return_value='arm64'), \
                    patch.object(agents, 'command', side_effect=download), self.assertRaises(ValueError):
                agents.native_install(spec)
            self.assertFalse((home/'.local/bin/claude').exists())
            self.assertFalse((home/'.local/share/feipi-workbench/cli/claude'/spec['version']).exists())


if __name__ == '__main__':
    unittest.main()
