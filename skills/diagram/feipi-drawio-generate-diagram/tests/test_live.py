"""真实 Podman 渲染集成测试；显式 --live 开启，不自动准备环境。"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from argparse import Namespace

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL/'scripts'))
import core
import run_diagram
import renderer


@unittest.skipUnless(os.environ.get('DRAWIO_TEST_LIVE') == '1', '需要 tests/run.sh --live')
class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.brief = core.read_json(SKILL/'assets/brief.example.json')
        self.input = self.root/'input.json'
        self.args = Namespace(brief=self.input, out_dir=self.root/'package', diagram=None,
                              reuse_valid_package=False, existing_only=True)

    def tearDown(self):
        self.tmp.cleanup()

    def execute(self):
        self.input.write_text(json.dumps(self.brief, ensure_ascii=False))
        return run_diagram.run(self.args)

    def test_render_cache_and_tamper(self):
        code, report = self.execute()
        self.assertEqual(code, 0, report)
        core.verify_package(self.args.out_dir)
        self.args.reuse_valid_package = True
        code, cached = self.execute()
        self.assertEqual(code, 0, cached)
        self.assertTrue(cached['cache_reused'])
        (self.args.out_dir/'diagram.svg').write_text('<svg/>')
        with self.assertRaises(ValueError): core.verify_package(self.args.out_dir)

    def test_group_and_existing_xml(self):
        self.brief = {'title': '分组示例', 'diagram_type': 'component', 'nodes': [
            {'id':'domain','label':'业务域','shape':'group','x':20,'y':20,'width':620,'height':220},
            {'id':'api','label':'接口服务','parent':'domain','x':30,'y':70,'width':180,'height':80},
            {'id':'db','label':'数据存储','parent':'domain','x':360,'y':70,'width':180,'height':80}],
            'edges':[{'id':'store','source':'api','target':'db','label':'持久化'}]}
        source = self.root/'existing.drawio'
        source.write_text(core.generate(self.brief))
        self.args.diagram = source
        code, report = self.execute()
        self.assertEqual(code, 0, report)
        self.assertEqual(source.read_text(), (self.args.out_dir/'diagram.drawio').read_text())

    def test_layout_failure_repair_and_budget(self):
        self.brief['nodes'][1]['x'] = 100
        code, report = self.execute()
        self.assertEqual(report['stage'], 'layout', report)
        self.assertEqual(code, 1)
        code, same = self.execute()
        self.assertEqual(same['render_attempts'], 1)
        self.assertTrue(any('未修改' in x for x in same['issues']))
        self.brief['nodes'][1]['x'] = 110
        code, second = self.execute()
        self.assertEqual(second['render_attempts'], 2)
        self.assertEqual(second['stage'], 'layout', second)
        self.brief['nodes'][1]['x'] = 340
        code, exhausted = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(exhausted['render_attempts'], 2)
        self.assertTrue(any('最多两次' in x for x in exhausted['issues']))

    def test_repair_success(self):
        self.brief['nodes'][1]['x'] = 100
        code, report = self.execute()
        self.assertEqual(report['stage'], 'layout', report)
        self.brief['nodes'][1]['x'] = 340
        code, report = self.execute()
        self.assertEqual(code, 0, report)
        self.assertEqual(report['render_attempts'], 2)

    def test_external_resource_blocked_by_service(self):
        xml = core.inspect_source(self.brief, core.generate(self.brief))
        xml = xml.replace('rounded=1;', 'shape=image;image=https://drawio-test.invalid/pixel.png;')
        with self.assertRaisesRegex(ValueError, '外部资源'):
            renderer.request('/render', {'xml': xml})

    def test_invalid_reuse_preserves_valid_package(self):
        code, report = self.execute()
        self.assertEqual(code, 0, report)
        self.args.reuse_valid_package = True
        self.brief['nodes'][0]['label'] = '其他客户端'
        code, rejected = self.execute()
        self.assertEqual(code, 1)
        self.assertTrue(rejected['existing_package_preserved'])
        core.verify_package(self.args.out_dir)


if __name__ == '__main__':
    unittest.main()
