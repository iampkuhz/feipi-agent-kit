"""安装依赖元数据与真正的开发目录引用必须区分。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('layout', Path(__file__).resolve().parents[1]/'scripts/harness/validate_skill_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class DevelopmentReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_root = layout.REPO_ROOT
        layout.REPO_ROOT = self.root
        self.skill = self.root/'skills/diagram/feipi-example-generate-diagram'
        (self.skill/'tests').mkdir(parents=True)
        (self.skill/'evals').mkdir()
        (self.skill/'tests/run.sh').write_text('#!/bin/sh\nexit 0\n')
        (self.skill/'tests/run.sh').chmod(0o755)
        (self.skill/'evals/cases.json').write_text(json.dumps({'schema_version':1,'skill':self.skill.name,'cases':[{'id':'sample','prompt':'生成图','expected':['验证'],'forbidden':['伪造']}]}))
        (self.skill/'SKILL.md').write_text('生成并验证图包。\n')

    def tearDown(self):
        layout.REPO_ROOT = self.old_root
        self.tmp.cleanup()

    def test_generated_lockfile_is_metadata(self):
        (self.skill/'package-lock.json').write_text(json.dumps({'packages':{'node_modules/example':{'workspaces':['tests/types']}}}))
        layout.validate_source_layout([self.skill])

    def test_runtime_reference_still_rejected(self):
        (self.skill/'SKILL.md').write_text('业务运行时读取 tests/fixture.json\n')
        with self.assertRaisesRegex(AssertionError,'运行内容引用开发目录'):
            layout.validate_source_layout([self.skill])

    def test_runtime_json_reference_still_rejected(self):
        (self.skill/'runtime.json').write_text(json.dumps({'input':'tests/fixture.json'}))
        with self.assertRaisesRegex(AssertionError,'运行内容引用开发目录'):
            layout.validate_source_layout([self.skill])


if __name__ == '__main__':
    unittest.main()
