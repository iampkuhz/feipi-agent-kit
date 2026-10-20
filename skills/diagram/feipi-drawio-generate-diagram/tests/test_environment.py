"""环境状态、错误传播、准备工具发现与有界健康等待。"""
from argparse import Namespace
import copy
import importlib.util
import json
import os
from pathlib import Path
import runpy
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
import urllib.error

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
import renderer
import run_diagram
import prepare_renderer

spec = importlib.util.spec_from_file_location('drawio_runtime', SKILL.parents[2] / 'tools/diagram/drawio/runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
READY = {'status': 'ready', 'service': 'feipi-drawio', 'network': 'local-only', 'contract': 1}
CONTAINER = {'Config': {'Image': renderer.IMAGE, 'Labels': {'app': 'feipi-drawio'}},
             'HostConfig': {'PortBindings': {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8200'}]}},
             'State': {'Running': False}}


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_missing_states_only_suggest_preparation(self):
        for missing, code in [(True, 'image_missing'), (False, 'container_missing')]:
            def podman(*args, **kwargs):
                if args[:2] == ('container', 'exists'): return None
                if args[:2] == ('image', 'exists'): return None if missing else ''
                if args == ('info',): return ''
                self.fail(f'缺环境不应执行操作: {args}')
            with patch.object(renderer, 'ensure_local'), patch.object(renderer, 'podman', side_effect=podman):
                for existing_only in [True, False]:
                    with self.assertRaises(renderer.RendererError) as caught:
                        renderer.preflight(existing_only)
                    error = renderer.failure(caught.exception)
                    self.assertEqual(error['code'], code)
                    self.assertIn('prepare_renderer.py', error['next_steps'][0])

    def test_exists_125_is_not_missing(self):
        for exit_code in [1, 125]:
            result = subprocess.CompletedProcess([], exit_code, '', 'Error: permission denied')
            with patch.object(renderer.subprocess, 'run', return_value=result):
                with self.assertRaises(renderer.RendererError) as caught:
                    renderer.podman('container', 'exists', renderer.CONTAINER, missing_ok=True)
            error = renderer.failure(caught.exception)
            self.assertEqual(error['code'], 'podman_failed')
            self.assertEqual(error['exit_code'], exit_code)
            self.assertIn('permission denied', error['reason'])

    def test_different_stderr_is_preserved_and_bounded(self):
        for stderr in ['Error: no such object', 'Error: connection refused', 'Error: permission denied', 'x' * 4000]:
            with patch.object(renderer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 125, '', stderr)):
                with self.assertRaises(renderer.RendererError) as caught:
                    renderer.podman('info')
            error = renderer.failure(caught.exception)
            self.assertEqual(error['stderr'], stderr[-2000:])
            self.assertEqual(error['command'], ['podman', 'info'])

    def test_missing_cli_and_timeout(self):
        for exc, code in [(FileNotFoundError('podman'), 'podman_missing'),
                          (subprocess.TimeoutExpired(['podman', 'info'], 30, stderr=b'original timeout'), 'podman_timeout')]:
            with patch.object(renderer.subprocess, 'run', side_effect=exc):
                with self.assertRaises(renderer.RendererError) as caught:
                    renderer.podman('info')
            self.assertEqual(renderer.failure(caught.exception)['code'], code)
        self.assertEqual(renderer.failure(caught.exception)['stderr'], 'original timeout')

    def test_engine_failure_stops_before_container_queries(self):
        error = renderer.RendererError('engine_unavailable', 'connection refused')
        with patch.object(renderer, 'ensure_local'), patch.object(renderer, 'podman', side_effect=error) as podman:
            with self.assertRaises(renderer.RendererError): renderer.preflight()
        self.assertEqual(podman.call_args_list[0].args, ('info',))
        self.assertEqual(podman.call_count, 1)

    def test_bad_config_never_starts_container(self):
        for key in ['image', 'label', 'port']:
            container = copy.deepcopy(CONTAINER)
            if key == 'image': container['Config']['Image'] = 'drawio-local'
            if key == 'label': container['Config']['Labels'] = None
            if key == 'port': container['HostConfig']['PortBindings']['8080/tcp'][0]['HostIp'] = '0.0.0.0'
            with patch.object(renderer, 'ensure_local'), patch.object(renderer, 'podman', return_value=json.dumps([container])) as podman:
                with self.assertRaises(renderer.RendererError) as caught: renderer.preflight()
            self.assertEqual(caught.exception.details['code'], 'container_mismatch')
            self.assertFalse(any(c.args[0] == 'start' for c in podman.call_args_list))

    def test_slow_health_starts_once_and_retries_only_health(self):
        with patch.object(renderer, 'ensure_local'), patch.object(renderer, 'podman', return_value=json.dumps([CONTAINER])) as podman, \
             patch.object(renderer, 'request', side_effect=[urllib.error.URLError('starting'), READY]) as request, \
             patch.object(renderer.time, 'sleep'):
            self.assertTrue(renderer.preflight()['startup_performed'])
        self.assertEqual(sum(c.args == ('start', renderer.CONTAINER) for c in podman.call_args_list), 1)
        self.assertEqual(request.call_count, 2)
        self.assertTrue(all(c.args == ('/health',) for c in request.call_args_list))

    def test_health_timeout_retains_last_error(self):
        with patch.object(renderer, 'request', side_effect=urllib.error.URLError('connection refused')), \
             patch.object(renderer.time, 'monotonic', side_effect=[0, 0, 31]):
            with self.assertRaises(renderer.RendererError) as caught: renderer.wait_ready()
        self.assertEqual(caught.exception.details['code'], 'health_unavailable')
        self.assertIn('connection refused', str(caught.exception))
        self.assertEqual(caught.exception.details['next_steps'], ['podman logs --tail 50 feipi-drawio'])

    def test_foreign_health_is_fatal(self):
        with patch.object(renderer, 'request', return_value={**READY, 'service': 'drawio-local'}) as request:
            with self.assertRaises(renderer.RendererError) as caught: renderer.wait_ready()
        self.assertEqual(caught.exception.details['code'], 'health_contract_mismatch')
        self.assertEqual(request.call_count, 1)

    def test_cli_and_package_keep_same_diagnostics(self):
        error = renderer.RendererError('podman_failed', '命令失败', command=['podman', 'inspect', 'feipi-drawio'],
                                       exit_code=125, stderr='Error: permission denied')
        output = io.StringIO()
        with patch.object(renderer, 'preflight', side_effect=error), patch.object(sys, 'argv', ['preflight_renderer.py']), redirect_stdout(output):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(str(SKILL / 'scripts/preflight_renderer.py'), run_name='__main__')
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(json.loads(output.getvalue()), renderer.failure(error))
        with tempfile.TemporaryDirectory() as folder, patch.object(run_diagram, 'preflight', side_effect=error):
            args = Namespace(brief=SKILL / 'assets/brief.example.json', out_dir=Path(folder),
                             diagram=None, existing_only=True, reuse_valid_package=False)
            code, report = run_diagram.run(args)
            self.assertEqual(code, 2)
            self.assertEqual(report['renderer_error'], renderer.failure(error))
            self.assertEqual(report['render_attempts'], 0)
            self.assertTrue((Path(folder) / 'diagram.drawio').is_file())

    def test_prepare_discovers_source_and_rechecks(self):
        tool = prepare_renderer.find_tool_dir()
        self.assertEqual(tool, runtime.ROOT)
        with patch.object(prepare_renderer.subprocess, 'Popen') as launch, \
             patch.object(prepare_renderer, 'preflight', return_value=READY) as check:
            launch.return_value.wait.return_value = 0
            self.assertEqual(prepare_renderer.prepare(), READY)
        check.assert_called_once_with(existing_only=True)

    def test_copied_skill_finds_source_marker_and_missing_tool_has_instructions(self):
        with tempfile.TemporaryDirectory(prefix='copied skill ') as folder:
            skill = Path(folder) / 'skill'
            (skill / 'scripts').mkdir(parents=True)
            (skill / '.feipi-agent-kit-source').write_text(str(SKILL))
            with patch.object(prepare_renderer, '__file__', str(skill / 'scripts/prepare_renderer.py')):
                self.assertEqual(prepare_renderer.find_tool_dir(), runtime.ROOT)
                (skill / '.feipi-agent-kit-source').unlink()
                with self.assertRaises(renderer.RendererError) as caught: prepare_renderer.find_tool_dir()
                self.assertEqual(caught.exception.details['code'], 'preparation_tool_missing')
                self.assertIn('git clone', caught.exception.details['next_steps'][0])
                self.assertIn('--tool-dir', caught.exception.details['next_steps'][1])

    def test_preparation_failure_never_rechecks(self):
        with patch.object(prepare_renderer.subprocess, 'Popen') as launch, \
             patch.object(prepare_renderer, 'preflight') as check:
            launch.return_value.wait.return_value = 2
            with self.assertRaises(renderer.RendererError): prepare_renderer.prepare()
        check.assert_not_called()

    def test_preparation_timeout_cleans_client_process_group(self):
        with patch.object(prepare_renderer.subprocess, 'Popen') as launch, \
             patch.object(prepare_renderer.os, 'killpg') as kill, patch.object(prepare_renderer, 'preflight') as check:
            launch.return_value.pid = 12345
            launch.return_value.wait.side_effect = [subprocess.TimeoutExpired('ensure', 1200), 0]
            with self.assertRaises(renderer.RendererError) as caught: prepare_renderer.prepare()
            self.assertEqual(caught.exception.details['code'], 'preparation_timeout')
            self.assertEqual(kill.call_args.args[0], 12345)
            launch.assert_called_once_with(['bash', str(runtime.ROOT / 'drawio.sh'), 'ensure'], start_new_session=True)
        check.assert_not_called()

    def test_darwin_cold_machine_and_stopped_machine(self):
        for machines, expected in [([], [('machine', 'init'), ('machine', 'start', 'podman-machine-default')]),
                                   ([{'Name': 'custom', 'Default': True, 'Running': False}], [('machine', 'start', 'custom')])]:
            calls = []
            def podman(*args, **kwargs):
                calls.append(args)
                if args == ('info',) and calls.count(('info',)) == 1:
                    raise runtime.ToolError('引擎连接失败', exit_code=125, stderr='connection refused')
                return json.dumps(machines) if args[:2] == ('machine', 'list') else ''
            with patch.object(runtime.sys, 'platform', 'darwin'), patch.object(runtime, 'local_connection'), \
                 patch.object(runtime, 'podman', side_effect=podman): runtime.engine(prepare=True)
            self.assertEqual([c for c in calls if c[:2] in [('machine', 'init'), ('machine', 'start')]], expected)

    def test_running_broken_machine_is_not_reinitialized(self):
        calls = []
        def podman(*args, **kwargs):
            calls.append(args)
            if args == ('info',): raise runtime.ToolError('permission denied', exit_code=125, stderr='permission denied')
            return json.dumps([{'Name': 'default', 'Default': True, 'Running': True}])
        with patch.object(runtime.sys, 'platform', 'darwin'), patch.object(runtime, 'local_connection'), patch.object(runtime, 'podman', side_effect=podman):
            with self.assertRaises(runtime.ToolError) as caught: runtime.engine(prepare=True)
        self.assertEqual(caught.exception.details['stderr'], 'permission denied')
        self.assertNotIn(('machine', 'init'), calls)


if __name__ == '__main__':
    unittest.main()
