"""失败路径、次数冻结、缓存与路径保护的可观察行为。"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model import ROOT,Invalid,load
from run import run

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.b=load(ROOT/'assets/examples/component.json');self.brief=self.root/'b.json';self.out=self.root/'package';self.save()
    def tearDown(self):self.temp.cleanup()
    def save(self):self.brief.write_text(json.dumps(self.b,ensure_ascii=False))
    def test_missing_renderer_preserves_source_without_attempt(self):
        with patch('run.invoke',side_effect=FileNotFoundError('node missing')) as call:
            r=run(self.brief,self.out)
        self.assertEqual(r['failure_class'],'renderer');self.assertEqual(r['attempt_index'],0)
        self.assertTrue((self.out/'diagram.mmd').is_file());self.assertFalse((self.out/'diagram.svg').exists());self.assertEqual(call.call_count,1)
    def test_failed_source_cannot_repeatedly_consume_attempts(self):
        with patch('run.invoke',side_effect=[{'renderer':{}},Invalid('syntax error')]) as call:
            r=run(self.brief,self.out)
        self.assertEqual(call.call_count,2);self.assertEqual(r['attempt_index'],1)
        for _ in range(3):
            with patch('run.invoke') as call:
                r=run(self.brief,self.out)
            call.assert_not_called();self.assertEqual(r['failure_class'],'retry_limit');self.assertEqual(r['attempt_index'],1)
        self.b['layout']['direction']='LR';self.save()
        with patch('run.invoke',side_effect=[{'renderer':{}},Invalid('syntax error')]):r=run(self.brief,self.out)
        self.assertEqual(r['attempt_index'],2)
        self.b['layout']['direction']='RL';self.save()
        with patch('run.invoke') as call:r=run(self.brief,self.out)
        call.assert_not_called();self.assertEqual(r['failure_class'],'retry_limit')
    def test_render_attempt_frozen_before_subprocess(self):
        def renderer(args,*unused):
            if '--check' in args:return {'renderer':{}}
            state=json.loads((self.out/'validation.json').read_text())
            self.assertEqual(state['attempt_index'],1);self.assertEqual(state['last_render_status'],'started')
            raise Invalid('interrupted')
        with patch('run.invoke',side_effect=renderer):r=run(self.brief,self.out)
        self.assertEqual(r['last_render_status'],'failed')
    def test_failed_render_never_returns_stale_image(self):
        self.out.mkdir();(self.out/'diagram.svg').write_text('<svg>old</svg>')
        with patch('run.invoke',side_effect=Invalid('renderer blocked')):r=run(self.brief,self.out)
        self.assertEqual(r['final_status'],'blocked');self.assertFalse((self.out/'diagram.svg').exists())
    def test_evidence_symlink_protected(self):
        self.out.mkdir();(self.out/'evidence').mkdir();target=self.root/'secret';target.write_text('keep')
        (self.out/'evidence/overview.json').symlink_to(target)
        with self.assertRaises(Invalid):run(self.brief,self.out)
        self.assertEqual(target.read_text(),'keep')
    def test_final_verifier_exception_blocks_report(self):
        # 渲染异常无论属于哪个库异常类型，都必须冻结 blocked 而非遗留 pending。
        with patch('run.invoke',side_effect=[{'renderer':{}},SyntaxError('bad XML')]):r=run(self.brief,self.out)
        self.assertEqual(r['final_status'],'blocked');self.assertEqual(json.loads((self.out/'validation.json').read_text())['final_status'],'blocked')
    def test_diagram_id_cannot_reset_budget(self):
        with patch('run.invoke',side_effect=[{'renderer':{}},Invalid('syntax')]):run(self.brief,self.out)
        self.b['diagram_id']='D2';self.save()
        with patch('run.invoke') as call:r=run(self.brief,self.out)
        call.assert_not_called();self.assertEqual(r['attempt_index'],1);self.assertEqual(r['final_status'],'blocked')

if __name__=='__main__':unittest.main()
