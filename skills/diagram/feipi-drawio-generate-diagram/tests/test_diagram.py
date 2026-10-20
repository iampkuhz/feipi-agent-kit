"""确定性负例验证：输入/覆盖/布局/本地边界，而非只验证脚本退出。"""
import base64
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.parse
import zlib

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
import core
import renderer
import run_diagram
from argparse import Namespace


class DiagramTests(unittest.TestCase):
    def setUp(self):
        self.brief = core.read_json(SKILL / 'assets/brief.example.json')

    def test_round_trip(self):
        core.inspect_source(core.validate_brief(self.brief), core.generate(self.brief))

    def test_literal_text(self):
        self.brief['nodes'][0]['label'] = '中文 <接口> & "路径"\nC:\\demo'
        core.inspect_source(self.brief, core.generate(self.brief))

    def test_duplicate_id(self):
        self.brief['nodes'][1]['id'] = 'client'
        with self.assertRaises(ValueError): core.validate_brief(self.brief)

    def test_missing_endpoint(self):
        self.brief['edges'][0]['target'] = 'missing'
        with self.assertRaises(ValueError): core.validate_brief(self.brief)

    def test_unknown_field(self):
        self.brief['url'] = 'https://example.org'
        with self.assertRaises(ValueError): core.validate_brief(self.brief)

    def test_nonfinite_and_boolean(self):
        for value in [float('nan'), float('inf'), True]:
            with self.subTest(value=value):
                self.brief['nodes'][0]['x'] = value
                with self.assertRaises(ValueError): core.validate_brief(self.brief)

    def test_parent_cycle(self):
        self.brief['nodes'][0].update(parent='client', shape='group')
        with self.assertRaises(ValueError): core.validate_brief(self.brief)

    def test_wrong_label(self):
        raw = core.generate(self.brief).replace('订单数据库', '错误数据')
        with self.assertRaises(ValueError): core.inspect_source(self.brief, raw)

    def test_reversed_edge(self):
        raw = core.generate(self.brief).replace('source="client" target="api"', 'source="api" target="client"')
        with self.assertRaises(ValueError): core.inspect_source(self.brief, raw)

    def test_missing_node(self):
        other = copy.deepcopy(self.brief)
        other['nodes'].pop()
        with self.assertRaises(ValueError): core.inspect_source(self.brief, core.generate(other))

    def test_changed_geometry(self):
        raw = core.generate(self.brief).replace('x="40"', 'x="42"')
        with self.assertRaises(ValueError): core.inspect_source(self.brief, raw)

    def test_xml_entity(self):
        with self.assertRaises(ValueError): core.parse_xml('<!DOCTYPE foo [<!ENTITY x "x">]><mxGraphModel/>')

    def test_external_style(self):
        raw = core.generate(self.brief).replace('html=0', 'image=https://example.org/a.png;html=0')
        with self.assertRaises(ValueError): core.parse_xml(raw)

    def test_html_and_hidden(self):
        for marker in ['html=1', 'html=0;image=data:image/png;base64,x']:
            with self.assertRaises(ValueError): core.parse_xml(core.generate(self.brief).replace('html=0', marker))
        with self.assertRaises(ValueError): core.parse_xml(core.generate(self.brief).replace('vertex="1"', 'vertex="1" visible="0"'))

    def test_compressed_xml(self):
        model = core.inspect_source(self.brief, core.generate(self.brief))
        encoder = zlib.compressobj(wbits=-15)
        data = encoder.compress(urllib.parse.quote(model).encode()) + encoder.flush()
        raw = '<mxfile><diagram>' + base64.b64encode(data).decode() + '</diagram></mxfile>'
        core.inspect_source(self.brief, raw)

    def test_multi_page(self):
        with self.assertRaises(ValueError): core.parse_xml('<mxfile><diagram/><diagram/></mxfile>')

    def test_decompression_budget(self):
        encoder = zlib.compressobj(wbits=-15)
        data = encoder.compress(b'A' * (core.MAX_BYTES+10)) + encoder.flush()
        with self.assertRaises(ValueError):
            core.parse_xml('<mxfile><diagram>' + base64.b64encode(data).decode() + '</diagram></mxfile>')

    def test_segment_intersections(self):
        self.assertTrue(core.segment_hits([0, 5], [20, 5], [5, 0, 10, 10]))
        self.assertFalse(core.segment_hits([0, 0], [20, 0], [5, 0, 10, 10]))
        self.assertFalse(core.segment_hits([0, 5], [3, 5], [5, 0, 10, 10]))

    def test_layout_overflow_and_overlap(self):
        self.brief['edges'] = []
        geometry = [{'id': n['id'], 'edge': False, 'rect': [n['x'], n['y'], n['width'], n['height']],
                     'text': [n['x']+8, n['y']+8, 100, 20], 'points': []} for n in self.brief['nodes']]
        self.assertEqual(core.layout_issues(self.brief, geometry), [])
        geometry[0]['text'][2] = 300
        self.assertTrue(any('文字超出' in x for x in core.layout_issues(self.brief, geometry)))
        geometry[1]['rect'] = geometry[0]['rect']
        self.assertTrue(any('节点重叠' in x for x in core.layout_issues(self.brief, geometry)))

    def test_local_connection_guard(self):
        with patch.dict(os.environ, {'CONTAINER_HOST': 'ssh://remote.example'}):
            with self.assertRaises(ValueError): renderer.ensure_local()
        with patch.dict(os.environ, {}, clear=True), patch.object(renderer, 'podman', return_value=json.dumps([
                {'Default': True, 'URI': 'ssh://user@remote.example/run/podman.sock'}])):
            with self.assertRaises(ValueError): renderer.ensure_local()

    def test_port_guard(self):
        for value in ['80', '65536', 'http://example.org', '1/../../']:
            with patch.dict(os.environ, {'AGENT_DRAWIO_SERVER_PORT': value}):
                with self.assertRaises(ValueError): renderer.endpoint()

    def test_redirect_denied(self):
        with self.assertRaises(ValueError): renderer.NoRedirect().redirect_request(None, None, None, None, None, None)

    def test_static_failure_never_calls_renderer(self):
        with tempfile.TemporaryDirectory() as folder:
            brief_path = Path(folder) / 'bad.json'
            self.brief['edges'][0]['target'] = 'missing'
            brief_path.write_text(json.dumps(self.brief))
            args = Namespace(brief=brief_path, out_dir=Path(folder)/'out', diagram=None,
                             reuse_valid_package=False, existing_only=True)
            with patch.object(run_diagram, 'preflight') as service:
                code, report = run_diagram.run(args)
                service.assert_not_called()
            self.assertEqual(code, 1)
            self.assertEqual(report['stage'], 'input')

    def test_stopped_container_existing_only(self):
        container = {'Config': {'Image': renderer.IMAGE, 'Labels': {'app': 'feipi-drawio'}},
                     'HostConfig': {'PortBindings': {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8200'}]}},
                     'State': {'Running': False}}
        with patch.dict(os.environ, {}, clear=True), patch.object(renderer, 'ensure_local'), \
             patch.object(renderer, 'podman', return_value=json.dumps([container])) as podman:
            with self.assertRaises(ValueError): renderer.preflight(True)
            self.assertFalse(any(call.args[0] == 'start' for call in podman.call_args_list))


if __name__ == '__main__':
    unittest.main()
