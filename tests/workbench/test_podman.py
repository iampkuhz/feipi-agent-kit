"""默认本机 Podman 首次准备与失败保全；不启动真实虚拟机。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('podman_bootstrap', ROOT/'tools/runtime/podman.py')
podman = importlib.util.module_from_spec(spec)
spec.loader.exec_module(podman)
spec = importlib.util.spec_from_file_location('workbench_main', ROOT/'scripts/workbench/main.py')
workbench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workbench)


class PodmanBootstrap(unittest.TestCase):
    def run_case(self, machines, connections):
        calls = []
        def command(*args, **kwargs):
            calls.append(args)
            if args[:3] == ('system', 'connection', 'list'):
                return json.dumps(connections)
            if args[:2] == ('machine', 'list'):
                return json.dumps(machines)
            if args[:2] == ('machine', 'init'):
                machines.append({'Name': 'podman-machine-default', 'Default': True, 'Running': False})
                connections.append(self.connection())
            return ''
        with patch.dict(podman.os.environ, {}, clear=True), \
                patch.object(podman.platform, 'system', return_value='Darwin'), \
                patch.object(podman.subprocess, 'run', return_value=type('Result', (), {'returncode': 0, 'stdout': '1'})()), \
                patch.object(podman, 'command', side_effect=command):
            podman.ensure()
        return calls

    def connection(self, uri='ssh://core@127.0.0.1:1234/run/user/501/podman.sock'):
        return {'Name': 'podman-machine-default', 'Default': True, 'URI': uri}

    def test_blank_mac_initializes_once_then_starts(self):
        calls = self.run_case([], [])
        self.assertEqual([c for c in calls if c[:2] in [('machine', 'init'), ('machine', 'start')]],
                         [('machine', 'init'), ('machine', 'start', 'podman-machine-default')])

    def test_running_machine_is_not_restarted(self):
        calls = self.run_case([{'Name': 'podman-machine-default', 'Default': True, 'Running': True}],
                              [self.connection()])
        self.assertFalse(any(c[:2] in [('machine', 'init'), ('machine', 'start')] for c in calls))

    def test_remote_or_unrelated_connection_never_initializes(self):
        for connections in ([self.connection('ssh://user@remote/run/podman.sock')], [self.connection()]):
            with self.subTest(connections=connections), self.assertRaises(ValueError):
                self.run_case([], connections)

    def test_ambiguous_machine_is_not_selected(self):
        with self.assertRaises(ValueError):
            self.run_case([{'Name': 'another-machine', 'Default': False}], [self.connection()])

    def test_connection_override_is_rejected_before_any_command(self):
        with patch.dict(podman.os.environ, {'CONTAINER_HOST': 'unix:///tmp/another.sock'}), \
                patch.object(podman, 'command') as command, self.assertRaises(ValueError):
            podman.ensure()
        command.assert_not_called()

    def test_mac_without_hypervisor_never_creates_or_downloads_machine(self):
        result = type('Result', (), {'returncode': 0, 'stdout': '0'})()
        with patch.object(podman, 'local_connection', return_value=None), \
                patch.object(podman.platform, 'system', return_value='Darwin'), \
                patch.object(podman.subprocess, 'run', return_value=result), \
                patch.object(podman, 'command') as command, self.assertRaisesRegex(ValueError, '虚拟化'):
            podman.ensure()
        command.assert_not_called()

    def test_readiness_waits_through_slow_start_without_recreate(self):
        from unittest.mock import MagicMock
        ready = MagicMock()
        ready.__enter__.return_value.status = 200
        with patch.object(workbench.urllib.request, 'build_opener') as opener, \
                patch.object(workbench.time, 'sleep') as sleep:
            opener.return_value.open.side_effect = [OSError('starting'), ready]
            workbench.wait_service('crawl4ai', 'http://127.0.0.1:11235/health')
        sleep.assert_called_once_with(2)

    def test_readiness_timeout_remains_failure(self):
        with patch.object(workbench.urllib.request, 'build_opener') as opener, \
                patch.object(workbench.time, 'sleep'), \
                patch.object(workbench.time, 'monotonic', side_effect=[0, 1, 601]), \
                self.assertRaises(ValueError):
            opener.return_value.open.side_effect = OSError('still starting')
            workbench.wait_service('litellm', 'http://localhost:4000/health/readiness')


if __name__ == '__main__':
    unittest.main()
