"""慢速判断、代理功能探测、一次回退与确认边界。"""
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools/diagram/drawio'))
import network


class NetworkTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'source.tar.gz'
        self.url = 'https://codeload.github.com/jgraph/drawio/tar.gz/example'

    def test_low_speed_window_and_existing_proxy_are_preserved(self):
        with patch.dict(os.environ, {'https_proxy': 'http://existing.example:8080'}), \
             patch.object(network.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            network._download(self.url, self.output)
            args = run.call_args.args[0]
            self.assertEqual(args[args.index('--speed-limit') + 1], '65536')
            self.assertEqual(args[args.index('--speed-time') + 1], '30')
            self.assertNotIn('--proxy', args)
            self.assertEqual(os.environ['https_proxy'], 'http://existing.example:8080')

    def test_confirmed_slow_download_has_larger_bounded_budget(self):
        with patch.dict(os.environ, {'AGENT_DRAWIO_ALLOW_SLOW_DOWNLOAD': '1'}), \
             patch.object(network.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            network._download(self.url, self.output)
            args = run.call_args.args[0]
            self.assertNotIn('--speed-limit', args)
            self.assertEqual(args[args.index('--max-time') + 1], '600')

    def test_slow_download_retries_once_with_verified_local_proxy(self):
        calls = []
        def attempt(url, output, proxy=False):
            calls.append(proxy)
            if not proxy:
                self.output.write_bytes(b'partial')
                return subprocess.CompletedProcess([], 28, '', 'Operation too slow')
            self.assertFalse(self.output.exists())
            self.output.write_bytes(b'complete')
            return subprocess.CompletedProcess([], 0, '', '')
        with patch.object(network, '_download', side_effect=attempt), \
             patch.object(network, 'probe_proxy', return_value={'available': True}):
            network.download(self.url, self.output)
        self.assertEqual(calls, [False, True])
        self.assertEqual(self.output.read_bytes(), b'complete')

    def test_unavailable_proxy_requires_confirmation_and_keeps_reason(self):
        self.output.write_bytes(b'partial')
        with patch.object(network, '_download', return_value=subprocess.CompletedProcess([], 28, '', 'download too slow')) as download, \
             patch.object(network, 'probe_proxy', return_value={'available': False, 'reason': 'connection refused'}):
            with self.assertRaises(network.NetworkError) as caught: network.download(self.url, self.output)
        error = caught.exception.details
        self.assertTrue(error['confirmation_required'])
        self.assertEqual(error['proxy_probe']['reason'], 'connection refused')
        self.assertIn('download too slow', error['reason'])
        self.assertFalse(self.output.exists())
        self.assertEqual(download.call_count, 1)
        self.assertIn('AGENT_DRAWIO_ALLOW_SLOW_DOWNLOAD=1', error['next_steps'][1])

    def test_failed_proxy_retry_does_not_loop(self):
        with patch.object(network, '_download', return_value=subprocess.CompletedProcess([], 28, '', 'still too slow')) as download, \
             patch.object(network, 'probe_proxy', return_value={'available': True}):
            with self.assertRaises(network.NetworkError) as caught: network.download(self.url, self.output)
        self.assertEqual(download.call_count, 2)
        self.assertTrue(caught.exception.details['confirmation_required'])

    def test_http_error_is_not_misclassified_as_slow(self):
        with patch.object(network, '_download', return_value=subprocess.CompletedProcess([], 22, '', 'HTTP 404')), \
             patch.object(network, 'probe_proxy') as probe:
            with self.assertRaises(network.NetworkError) as caught: network.download(self.url, self.output)
        self.assertEqual(caught.exception.details['code'], 'download_failed')
        probe.assert_not_called()

    def test_port_alone_is_insufficient_and_proxy_auth_failure_is_rejected(self):
        with patch.object(network.socket, 'create_connection'), \
             patch.object(network.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '407', '')):
            self.assertFalse(network.probe_proxy(self.url)['available'])

    def test_proxy_verification_overrides_no_proxy_without_changing_environment(self):
        requests = []
        class Proxy(BaseHTTPRequestHandler):
            def do_HEAD(self):
                requests.append(self.path)
                self.send_response(200)
                self.end_headers()
            def log_message(self, *args): pass
        server = HTTPServer(('127.0.0.1', 0), Proxy)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with patch.object(network, 'HOST_PROXY_PORT', server.server_port), patch.dict(os.environ, {'NO_PROXY': '*'}):
            result = network.probe_proxy('http://proxy-target.invalid/download')
            self.assertEqual(os.environ['NO_PROXY'], '*')
        self.assertTrue(result['available'], result)
        self.assertEqual(requests, ['http://proxy-target.invalid/download'])

    def test_real_curl_detects_slow_transfer_then_downloads_through_proxy(self):
        release = threading.Event()
        payload = b'complete proxy response' * 4096
        requests = []
        class SlowSource(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(b'x')
                self.wfile.flush()
                release.wait(5)
            def log_message(self, *args): pass
        class Proxy(BaseHTTPRequestHandler):
            def do_HEAD(self):
                requests.append('HEAD')
                self.send_response(200)
                self.end_headers()
            def do_GET(self):
                requests.append('GET')
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self, *args): pass
        source = ThreadingHTTPServer(('127.0.0.1', 0), SlowSource)
        proxy = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
        for server in [source, proxy]:
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(release.set)
        with patch.object(network, 'HOST_PROXY_PORT', proxy.server_port), patch.object(network, 'LOW_SPEED_SECONDS', 1):
            network.download(f'http://127.0.0.1:{source.server_port}/source', self.output)
        self.assertEqual(self.output.read_bytes(), payload)
        self.assertEqual(requests, ['HEAD', 'GET'])

    def test_registry_unauthorized_is_reachable_but_source_unauthorized_is_not(self):
        with patch.object(network.socket, 'create_connection'), \
             patch.object(network.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '401', '')):
            self.assertTrue(network.probe_proxy('https://quay.io/v2/')['available'])
            self.assertFalse(network.probe_proxy(self.url)['available'])

    def test_fallback_cannot_be_bypassed_by_no_proxy(self):
        with patch.object(network.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            network._download(self.url, self.output, proxy=True)
        args = run.call_args.args[0]
        self.assertEqual(args[args.index('--proxy') + 1], 'http://127.0.0.1:7890')
        self.assertEqual(args[args.index('--noproxy') + 1], '')

    def test_build_timeout_requires_confirmation_without_automatic_rebuild(self):
        with patch.object(network.subprocess, 'run', side_effect=subprocess.TimeoutExpired('podman build', 600)) as run, \
             patch.object(network, 'probe_proxy', return_value={'available': True}):
            with self.assertRaises(network.NetworkError) as caught: network.build(self.output.parent, 'test-image')
        self.assertEqual(caught.exception.details['stage'], 'image_build')
        self.assertTrue(caught.exception.details['confirmation_required'])
        self.assertEqual(run.call_count, 1)

    def test_machine_init_timeout_requires_confirmation_without_second_init(self):
        spec = importlib.util.spec_from_file_location('drawio_network_runtime', ROOT / 'tools/diagram/drawio/runtime.py')
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        calls = []
        def podman(*args, **kwargs):
            calls.append(args)
            if args == ('info',): raise runtime.ToolError('engine not ready', exit_code=125)
            if args[:2] == ('machine', 'list'): return '[]'
            if args[:2] == ('machine', 'init'):
                try: raise subprocess.TimeoutExpired('podman machine init', 300)
                except subprocess.TimeoutExpired as exc: raise runtime.ToolError('machine download slow') from exc
            self.fail(str(args))
        with patch.object(runtime.sys, 'platform', 'darwin'), patch.object(runtime, 'local_connection'), \
             patch.object(runtime, 'podman', side_effect=podman), \
             patch.object(network, 'probe_proxy', return_value={'available': True}):
            with self.assertRaises(network.NetworkError) as caught: runtime.engine(prepare=True)
        self.assertEqual(caught.exception.details['stage'], 'machine_init')
        self.assertEqual(calls.count(('machine', 'init')), 1)
        self.assertFalse(any(c[:2] == ('machine', 'start') for c in calls))


if __name__ == '__main__':
    unittest.main()
