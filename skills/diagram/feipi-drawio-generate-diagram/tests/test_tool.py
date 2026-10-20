"""真实工具入口的隔离冷启动：临时 HOME、伪 Podman、离线源码包和 loopback 健康服务。"""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[4]
TOOL = ROOT / 'tools/diagram/drawio'
REVISION = 'c9904435fd1a6795f6cad5c3908ec89d9afb8fb1'
SHA = '90acf10c43751f245873506e6748d868e24da8bd863e96dd0aeeb48ba32baee7'


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='drawio first use ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.tool = self.base / 'tool source'
        self.tool.mkdir()
        for file in TOOL.iterdir():
            if file.is_file(): shutil.copy2(file, self.tool / file.name)
        self.archive = self.base / 'offline-source.tar.gz'
        with tarfile.open(self.archive, 'w:gz') as archive:
            body = b'<html>offline build fixture</html>'
            entry = tarfile.TarInfo(f'drawio-{REVISION}/src/main/webapp/export3.html')
            entry.size = len(body)
            archive.addfile(entry, io.BytesIO(body))
        script = self.tool / 'drawio.sh'
        script.write_text(script.read_text().replace(SHA, hashlib.sha256(self.archive.read_bytes()).hexdigest()))
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        (self.bin / 'python3').symlink_to(sys.executable)
        self.state = self.base / 'state.json'
        self.state.write_text(json.dumps({'engine': True, 'container': False, 'image': False, 'running': False}))
        self.calls = self.base / 'calls.jsonl'
        self.env = {'PATH': f'{self.bin}:/usr/bin:/bin', 'HOME': str(self.base / 'home'),
                    'STATE': str(self.state), 'CALLS': str(self.calls), 'ARCHIVE': str(self.archive),
                    'http_proxy': 'http://127.0.0.1:1', 'https_proxy': 'http://127.0.0.1:1'}
        stub = f'''#!{sys.executable}
import json, os, pathlib, shutil, sys
args = sys.argv[1:]
name = pathlib.Path(sys.argv[0]).name
with open(os.environ['CALLS'], 'a') as f: f.write(json.dumps([name, *args])+'\\n')
if name == 'curl':
    if '--head' in args:
        print('200')
        sys.exit(0)
    if os.environ.get('DOWNLOAD_FAIL'):
        print('curl: download timed out', file=sys.stderr)
        sys.exit(28)
    shutil.copyfile(os.environ['ARCHIVE'], args[args.index('-o')+1])
    sys.exit(0)
state_path = pathlib.Path(os.environ['STATE'])
s = json.loads(state_path.read_text())
def done(code=0, output=''):
    state_path.write_text(json.dumps(s))
    print(output)
    sys.exit(code)
if args[:3] == ['system','connection','list']:
    done(output=json.dumps([{{'Default': True, 'URI': os.environ.get('CONNECTION', 'unix:///tmp/podman.sock')}}]))
if args == ['info']:
    if not s['engine']:
        print('Error: connection refused', file=sys.stderr)
        done(125)
    done()
if args[:2] == ['machine','list']: done(output=json.dumps(s.get('machines', [])))
if args[:2] == ['machine','init']:
    s['machines'] = [{{'Name':'podman-machine-default','Default':True,'Running':False}}]
    done()
if args[:2] == ['machine','start']:
    s['engine'] = True
    done()
if args[:2] == ['container','exists']:
    if os.environ.get('EXISTS_FAIL'):
        print('Error: permission denied', file=sys.stderr)
        done(125)
    done(0 if s['container'] else 1)
if args[:2] == ['image','exists']: done(0 if s['image'] else 1)
if args[:2] == ['container','inspect']:
    done(output=json.dumps([{{'Config':{{'Image':'localhost/feipi/drawio-renderer:1', 'Labels':{{'app':s.get('label','feipi-drawio')}}}},
         'HostConfig':{{'PortBindings':{{'8080/tcp':[{{'HostIp':'127.0.0.1','HostPort':os.environ['AGENT_DRAWIO_SERVER_PORT']}}]}}}},
         'State':{{'Running':s['running']}}}}]))
if args[:1] == ['build']:
    if os.environ.get('BUILD_FAIL'):
        print('Error: registry temporarily unavailable', file=sys.stderr)
        done(125)
    s['image'] = True
    done()
if args[:1] == ['run']:
    s['container'] = s['running'] = True
    done()
if args[:1] == ['start']:
    s['running'] = True
    done()
if args[:1] == ['stop']:
    s['running'] = False
    done()
if args[:1] == ['logs']:
    print('renderer startup diagnostic', file=sys.stderr)
    done()
print('unexpected command: '+repr(args), file=sys.stderr)
sys.exit(99)
'''
        for name in ['podman', 'curl']:
            p = self.bin / name
            p.write_text(stub)
            p.chmod(0o755)
        owner = self
        self.service = 'feipi-drawio'
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                data = json.dumps({'status': 'ready', 'service': owner.service, 'contract': 1, 'network': 'local-only'}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(data)
            def log_message(self, *args): pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        self.env['AGENT_DRAWIO_SERVER_PORT'] = str(server.server_port)
        network = self.tool / 'network.py'
        network.write_text(network.read_text().replace('HOST_PROXY_PORT = 7890', f'HOST_PROXY_PORT = {server.server_port}'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

    def run_tool(self, action, **overrides):
        return subprocess.run(['bash', str(self.tool / 'drawio.sh'), action], env={**self.env, **overrides},
                              text=True, errors='replace', capture_output=True, timeout=20)

    def commands(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def update_state(self, **values):
        self.state.write_text(json.dumps({**json.loads(self.state.read_text()), **values}))

    def test_cold_prepare_build_create_and_reuse(self):
        if sys.platform == 'darwin': self.update_state(engine=False)
        result = self.run_tool('ensure')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('ready', result.stdout)
        calls = self.commands()
        self.assertEqual(sum(c[:2] == ['podman', 'build'] for c in calls), 1)
        self.assertEqual(sum(c[:2] == ['podman', 'run'] for c in calls), 1)
        if sys.platform == 'darwin': self.assertIn(['podman', 'machine', 'init'], calls)
        count = len(calls)
        result = self.run_tool('ensure')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(c[:2] in [['podman', 'build'], ['podman', 'run'], ['podman', 'start']] or c[0] == 'curl'
                             for c in self.commands()[count:]))

    def test_prepared_image_only_creates_container(self):
        self.update_state(image=True)
        result = self.run_tool('ensure')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(c[0] == 'curl' or c[:2] == ['podman', 'build'] for c in self.commands()))
        self.assertEqual(sum(c[:2] == ['podman', 'run'] for c in self.commands()), 1)

    def test_stopped_container_starts_once(self):
        self.update_state(image=True, container=True)
        result = self.run_tool('ensure')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(c[:2] == ['podman', 'start'] for c in self.commands()), 1)

    def test_proxy_build_and_stderr_logs(self):
        result = self.run_tool('ensure', AGENT_DRAWIO_BUILD_PROXY='http://host.containers.internal:7890')
        self.assertEqual(result.returncode, 0, result.stderr)
        build = next(c for c in self.commands() if c[:2] == ['podman', 'build'])
        self.assertEqual(build.count('--build-arg'), 2)
        result = self.run_tool('logs')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('renderer startup diagnostic', result.stdout)

    def test_existing_wrong_container_is_preserved(self):
        self.update_state(container=True, label='drawio-local')
        result = self.run_tool('ensure')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('未修改容器', result.stderr)
        self.assertFalse(any(c[:2] in [['podman', 'run'], ['podman', 'start'], ['podman', 'build']] for c in self.commands()))

    def test_engine_error_is_not_container_missing(self):
        result = self.run_tool('ensure', EXISTS_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('permission denied', result.stderr)
        self.assertFalse(any(c[0] == 'curl' or c[:2] == ['podman', 'run'] for c in self.commands()))

    def test_remote_connection_rejected_for_all_actions(self):
        for action in ['ensure', 'prepare', 'up', 'status', 'down', 'logs']:
            result = self.run_tool(action, CONNECTION='ssh://user@remote.example/run/podman.sock')
            self.assertNotEqual(result.returncode, 0, action)
            self.assertIn('不是本地', result.stderr)
        self.assertTrue(all(c[1:4] == ['system', 'connection', 'list'] for c in self.commands()))

    def test_status_and_health_contract(self):
        self.update_state(container=True, running=True)
        self.service = 'drawio-local'
        result = self.run_tool('status')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('健康合同不符', result.stderr)
        self.assertFalse(any(c[:2] in [['podman', 'start'], ['podman', 'run']] for c in self.commands()))

    def test_download_build_and_checksum_failures_preserve_reason(self):
        for override, expected in [({'DOWNLOAD_FAIL': '1'}, 'download timed out'),
                                   ({'BUILD_FAIL': '1'}, 'registry temporarily unavailable')]:
            result = self.run_tool('ensure', **override)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected, result.stderr)
            if 'DOWNLOAD_FAIL' in override:
                self.assertEqual(result.returncode, 75)
                self.assertIn('"confirmation_required": true', result.stderr)
        self.archive.write_bytes(b'corrupted source')
        result = self.run_tool('ensure')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('源码校验和不匹配', result.stderr)
        self.assertFalse(json.loads(self.state.read_text())['container'])

    def test_skill_prepare_keeps_nested_proxy_confirmation_details(self):
        entry = ROOT / 'skills/diagram/feipi-drawio-generate-diagram/scripts/prepare_renderer.py'
        result = subprocess.run([sys.executable, str(entry), '--tool-dir', str(self.tool)],
                                env={**self.env, 'DOWNLOAD_FAIL': '1'}, capture_output=True,
                                text=True, errors='replace', timeout=20)
        self.assertEqual(result.returncode, 2, result.stderr)
        error = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(error['code'], 'download_confirmation_required')
        self.assertEqual(error['stage'], 'source_download')
        self.assertIn('proxy_probe', error)
        self.assertTrue(error['confirmation_required'])
        self.assertIn('download timed out', error['reason'])


if __name__ == '__main__':
    unittest.main()
