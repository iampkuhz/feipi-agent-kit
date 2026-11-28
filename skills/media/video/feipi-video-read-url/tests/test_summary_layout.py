#!/usr/bin/env python3
"""分层摘要的真实构建、风险拒绝与引用回归。"""
import copy,json,sys,tempfile,unittest
from pathlib import Path
S=Path(__file__).resolve().parents[1]/'scripts';sys.path[:0]=[str(S),str(S/'lib')]
import content_manifest as cm
from summary_packet import prepare,build
from summary_layout import CHECKS
from frame_plan import prepare as frame_prepare,build as frame_build

class EditorialTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.text='- [00:00:01] 方案A更易操作，需要专业设备。\n- [00:00:04] 方案B价格较高，适合预算充足时使用。\n- [00:00:08] 台面九十公分。\n- [00:00:10] 高度90%，灶台八十八十五。\n- [00:00:14] 大部分家里托的就是80%的钻。\n'
  (self.root/'asr.txt').write_text(self.text)
  m=cm.new_manifest('https://example.invalid/video','bilibili','video');cm.artifact(m,self.root,'asr','asr',self.root/'asr.txt',{'type':'time_range','start_seconds':0});cm.channel(m,'asr','complete');cm.finish(m,self.root)
  packet=prepare(self.root)
  self.draft={'schema':'feipi-summary-draft-v2','source_digest':packet['source_digest'],'reviewed_artifact_ids':['asr'],'semantic_review':'all_units_checked','risk_checks':sorted(CHECKS),'highlights':['a'],'sections':[{'title':'方案比较','layout':'comparison','items':[{'id':'a','label':'方案A','text':'作者认为更易操作。','detail':'需要专业设备。','category':'comparison','evidence':['asr:0001']},{'id':'b','label':'方案B','text':'作者称价格较高。','detail':'适合预算充足时使用。','category':'condition','evidence':['asr:0002']},{'id':'uncertain','label':'高度','text':'高度和灶台数字识别含糊，不能确定尺寸。','category':'uncertainty','evidence':['asr:0004']}]}]}
 def run_build(self):
  p=self.root/'draft.json';p.write_text(json.dumps(self.draft,ensure_ascii=False));return build(self.root,p)
 def test_layout_and_highlights_bound_to_reviewed_items(self):
  self.draft['overview']='这个未绑定的旧字段不能进入新摘要'
  self.run_build();out=(self.root/'summary.md').read_text()
  self.assertIn('| **方案A** |',out);self.assertIn('> **待核验 · 高度**',out);self.assertIn('**方案A**：作者认为更易操作',out)
  self.assertIn('[^1]: 00:01',out);self.assertNotIn('asr.txt',out);self.assertNotIn('旧字段',out)
  coverage=json.loads((self.root/'summary_coverage.json').read_text());self.assertTrue(any(x['id']=='a-detail' for x in coverage['units']))
 def test_ambiguous_number_not_repaired_as_measurement(self):
  for text in ['洗菜区90cm。','灶台85cm。','高度90厘米。']:
   with self.subTest(text=text):
    self.draft['sections'][0]['items'][0].update(text=text,evidence=['asr:0004'])
    with self.assertRaisesRegex(ValueError,'measurement_not_explicit'):self.run_build()
 def test_explicit_chinese_measurement_can_be_normalized(self):
  self.draft['sections'][0]['items'][0].update(text='作者提到台面90cm。',detail='',evidence=['asr:0003']);self.run_build()
 def test_measurement_cannot_match_suffix_of_another_number(self):
  (self.root/'asr.txt').write_text('- [00:00:01] 台面190cm。\n')
  self.draft['source_digest']=prepare(self.root)['source_digest']
  self.draft['sections'][0]['items']=self.draft['sections'][0]['items'][:1]
  self.draft['sections'][0]['items'][0].update(text='台面90cm。',detail='',evidence=['asr:0001'])
  with self.assertRaisesRegex(ValueError,'measurement_not_explicit'):self.run_build()
 def test_area_unit_keeps_square_dimension(self):
  (self.root/'asr.txt').write_text('- [00:00:01] 面积五平方米。\n')
  self.draft['source_digest']=prepare(self.root)['source_digest']
  self.draft['sections'][0]['items']=self.draft['sections'][0]['items'][:1]
  row=self.draft['sections'][0]['items'][0];row.update(text='面积5平方米。',detail='',evidence=['asr:0001'])
  self.run_build()
  row['text']='长度5米。'
  with self.assertRaisesRegex(ValueError,'measurement_not_explicit'):self.run_build()
 def test_percentage_cannot_be_reinterpreted_as_improvement(self):
  self.draft['sections'][0]['items'][0].update(text='质感提升80%。',evidence=['asr:0005'])
  with self.assertRaisesRegex(ValueError,'percentage_requires'):self.run_build()
 def test_sparse_frames_not_generalized_to_whole_video(self):
  self.draft['sections'][0]['items'][0]['text']='视频仅展示水槽实物。'
  with self.assertRaisesRegex(ValueError,'sampled_images'):self.run_build()
 def test_fake_quote_or_uncertain_highlight_rejected(self):
  self.draft['highlights']=['uncertain']
  with self.assertRaisesRegex(ValueError,'cannot_be_highlight'):self.run_build()
  self.draft['highlights']=['b'];self.draft['sections'][0]['items'][0]['verbatim']=True
  with self.assertRaisesRegex(ValueError,'verbatim_quote_not_in_source'):self.run_build()
 def test_numbered_frame_selection_uses_exact_source_and_time(self):
  frame_prepare(self.root);p=self.root/'selections.json';p.write_text(json.dumps({'decision':'核对具体高度而非章节开头','frames':[{'source_id':'asr:0004','key_text':'90%','title':'高度核验','question':'百分号是否为误识别，画面能否确认数字及单位？'}]}))
  result=frame_build(self.root,p);plan=json.loads(Path(result['plan_path']).read_text());self.assertEqual(result['selected_times'],[10]);self.assertEqual(plan['frames'][0]['evidence']['quote'],self.text.splitlines()[3])
 def test_frame_source_change_or_wrong_target_rejected(self):
  frame_prepare(self.root);p=self.root/'selections.json';p.write_text(json.dumps({'decision':'核验','frames':[{'source_id':'asr:0001','key_text':'超白玻','title':'门','question':'是否可见超白玻？'}]}))
  with self.assertRaisesRegex(ValueError,'frame_key_must'):frame_build(self.root,p)
  (self.root/'asr.txt').write_text('改变来源')
  with self.assertRaisesRegex(ValueError,'sources_changed'):frame_build(self.root,p)

 def test_source_numbering_cannot_be_silently_merged(self):
  p=self.root/'extraction_manifest.json';m=json.loads(p.read_text());m['metadata']['title']='10个设计';p.write_text(json.dumps(m));self.draft['source_digest']=prepare(self.root)['source_digest']
  with self.assertRaisesRegex(ValueError,'source_numbering'):self.run_build()
  self.draft['numbering_uncertainty']=True
  with self.assertRaisesRegex(ValueError,'source_numbering'):self.run_build()
 def test_cli_build_budget_cannot_be_bypassed_by_prepare(self):
  import subprocess
  p=self.root/'draft.json';p.write_text('{}')
  for attempt in range(2):
   cp=subprocess.run([sys.executable,str(S/'summary_packet.py'),'build',str(self.root),str(p)],capture_output=True,text=True);self.assertNotEqual(cp.returncode,0)
  prepare(self.root)
  cp=subprocess.run([sys.executable,str(S/'summary_packet.py'),'build',str(self.root),str(p)],capture_output=True,text=True)
  self.assertIn('attempt_limit',cp.stderr)

if __name__=='__main__':unittest.main()
